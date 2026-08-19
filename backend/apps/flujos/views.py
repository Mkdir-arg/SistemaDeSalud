from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.casos import motor
from apps.casos.models import Caso
from apps.common import BaseModelViewSet

from .models import Conexion, Flujo, Nodo, VersionFlujo
from .serializers import (
    ConexionSerializer,
    FlujoSerializer,
    NodoSerializer,
    VersionFlujoSerializer,
    _vigente_de,
)


class VersionCongelada(APIException):
    """Se intentó tocar el grafo de una versión que ya no es borrador."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = (
        "Esta versión ya está publicada y no se edita: los casos en curso están "
        "parados sobre estos nodos. Sacá una versión nueva y trabajá sobre el borrador."
    )


def exigir_borrador(version):
    """Guarda de escritura del grafo.

    Publicar tiene que CONGELAR. Sin esto, mover, editar o borrar un nodo de una
    versión publicada es instantáneo para los pacientes que ya están adentro del
    circuito —`Caso.version` apunta a esa fila— y encima borrar un nodo se lleva
    puesta la fila de espera (ItemFila cae en cascada) y deja a cada caso con
    `nodo_actual` en NULL. Además, la institución pierde el grafo con el que
    atendió a alguien el mes pasado: ante una auditoría no hay nada que mostrar.
    """
    if version.estado != VersionFlujo.Estado.BORRADOR:
        raise VersionCongelada()


class SoloSobreBorrador:
    """Mixin: las escrituras del grafo sólo valen sobre una versión borrador."""

    def perform_create(self, serializer):
        exigir_borrador(serializer.validated_data["version"])
        serializer.save()

    def perform_update(self, serializer):
        exigir_borrador(serializer.instance.version)
        # Mover el objeto a otra versión también tiene que respetar el destino.
        destino = serializer.validated_data.get("version")
        if destino and destino.pk != serializer.instance.version_id:
            exigir_borrador(destino)
        serializer.save()

    def perform_destroy(self, instance):
        exigir_borrador(instance.version)
        instance.delete()


def clonar_grafo(origen: VersionFlujo, destino: VersionFlujo) -> None:
    """Copia nodos (con su config y sus grupos) y conexiones de una versión a otra.

    Es lo que hace que «Nueva versión» y «Duplicar» sirvan para algo: sin copiar
    condiciones, grupos responsables y configuración, la copia es un lienzo vacío
    con el nombre del original.
    """
    mapa = {}
    for n in origen.nodos.all().prefetch_related("grupos"):
        copia = Nodo.objects.create(
            version=destino,
            tipo=n.tipo,
            titulo=n.titulo,
            descripcion=n.descripcion,
            x=n.x,
            y=n.y,
            config=dict(n.config or {}),
            formulario_id=n.formulario_id,
        )
        # `pantalla_token` NO se copia a propósito: dos nodos con el mismo token
        # hacen que el televisor de una sala muestre los llamados de la otra.
        copia.grupos.set(list(n.grupos.all()))
        mapa[n.pk] = copia
    for c in origen.conexiones.all():
        Conexion.objects.create(
            version=destino,
            origen=mapa[c.origen_id],
            destino=mapa[c.destino_id],
            etiqueta=c.etiqueta,
            condicion=dict(c.condicion or {}),
        )


# Versiones con sus nodos de entrada y de derivación precargados. Los dos
# listados que los usan —el de flujos y el mapa— los piden por objeto, y sin esto
# son tres o cuatro consultas por flujo en pantallas que se abren todo el día.
VERSIONES_PRECARGADAS = Prefetch(
    "versiones",
    queryset=VersionFlujo.objects.order_by("-numero").prefetch_related(
        Prefetch("nodos", queryset=Nodo.objects.filter(tipo=Nodo.Tipo.INICIO), to_attr="nodos_inicio"),
        Prefetch("nodos", queryset=Nodo.objects.filter(tipo=Nodo.Tipo.DERIVAR), to_attr="nodos_derivar"),
    ),
)


class FlujoViewSet(BaseModelViewSet):
    queryset = (
        Flujo.objects.select_related("institucion", "area", "subarea")
        .prefetch_related(VERSIONES_PRECARGADAS)
        # Los casos activos del flujo, en la misma consulta del listado y no uno
        # por fila. `distinct` porque el join con versiones multiplica filas.
        .annotate(
            casos_activos_anot=Count(
                "versiones__casos",
                filter=~Q(versiones__casos__estado__in=Caso.ESTADOS_FINALIZADOS),
                distinct=True,
            )
        )
    )
    serializer_class = FlujoSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "subarea")
    search_fields = ["titulo"]
    ordering_fields = ["titulo", "creado"]

    def get_queryset(self):
        """Agrega `?estado=` sobre la versión VIGENTE del flujo.

        «Vigente» es la publicada si existe y, si no, la última por número — la
        misma regla que muestra el listado. No es un campo del flujo, así que no
        alcanza con `filter_fields`; se resuelve con subconsultas.

        Antes esto se filtraba en el frontend sobre los flujos ya traídos, con el
        problema de siempre: la API pagina de a 25 y el filtro sólo veía esos.
        """
        qs = super().get_queryset()
        estado = self.request.query_params.get("estado")
        if not estado or estado == "todos":
            return qs

        publicada = VersionFlujo.objects.filter(
            flujo=OuterRef("pk"), estado=VersionFlujo.Estado.PUBLICADA
        )
        if estado == VersionFlujo.Estado.PUBLICADA:
            return qs.filter(Exists(publicada))

        # Sin versión publicada, manda el estado de la última.
        ultima = (
            VersionFlujo.objects.filter(flujo=OuterRef("pk"))
            .order_by("-numero")
            .values("estado")[:1]
        )
        return (
            qs.filter(~Exists(publicada))
            .annotate(estado_vigente=Subquery(ultima))
            .filter(estado_vigente=estado)
        )

    @action(detail=False, methods=["get"])
    def mapa(self, request):
        """Grafo de derivaciones entre flujos (para el Mapa de flujos).

        Devuelve `nodos` (un flujo por bloque, con su estado vigente) y `aristas`
        (cada nodo de tipo «derivar» con `flujo_destino_id` es una flecha
        origen → destino). Una arista a un flujo fuera del conjunto se marca como
        externa para poder dibujarla distinto.
        """
        flujos = list(self.get_queryset())
        ids = {f.id for f in flujos}
        nodos, aristas = [], []
        for f in flujos:
            # Todo sale de las versiones ya precargadas: acá había cuatro
            # consultas por flujo y el mapa no pagina, así que una red con 200
            # procesos disparaba ochocientas.
            vigente = _vigente_de(f)
            nodos.append({
                "id": f.id,
                "titulo": f.titulo,
                "area_nombre": f.area.nombre if f.area_id else "Institución",
                "ambito": f.ambito,
                "estado": vigente.estado if vigente else "borrador",
                "versiones": len(f.versiones.all()),
            })
            if not vigente:
                continue
            # `is None` y no `or`: el `to_attr` del prefetch SIEMPRE existe, y para
            # un flujo que no deriva vale `[]`, que es falsy. Con `or`, el
            # precargado servía sólo para los flujos que sí derivan y los demás
            # —la mayoría— caían al queryset: una consulta por flujo en un
            # endpoint que a propósito no pagina.
            nodos_derivar = getattr(vigente, "nodos_derivar", None)
            if nodos_derivar is None:
                nodos_derivar = vigente.nodos.filter(tipo=Nodo.Tipo.DERIVAR)
            for nodo in nodos_derivar:
                destino = (nodo.config or {}).get("flujo_destino_id")
                if destino:
                    aristas.append({
                        "origen": f.id,
                        "destino": destino,
                        "etiqueta": nodo.titulo or "Derivar",
                        "externo": destino not in ids,
                    })
        return Response({"nodos": nodos, "aristas": aristas})

    @action(detail=True, methods=["post"])
    def duplicar(self, request, pk=None):
        """Copia el flujo con su versión vigente COMPLETA, como borrador v1.

        Duplicar es con lo que una red replica un circuito de 25 nodos en otro
        hospital. Antes creaba el flujo, una v1 y un único nodo Inicio, y avisaba
        «Se duplicó»: el configurador se enteraba del lienzo vacío recién al
        abrirlo, y ese flujo de un solo Inicio pasa la validación y se puede
        elegir como destino de una derivación (los casos derivados ahí quedan
        parados en Inicio con el evento «Caso sin salida»).
        """
        flujo = self.get_object()
        origen = _vigente_de(flujo)
        with transaction.atomic():
            copia = Flujo.objects.create(
                institucion=flujo.institucion,
                area=flujo.area,
                subarea=flujo.subarea,
                titulo=f"{flujo.titulo} (copia)",
                descripcion=flujo.descripcion,
            )
            nueva = VersionFlujo.objects.create(
                flujo=copia,
                numero=1,
                estado=VersionFlujo.Estado.BORRADOR,
                autor=request.user if request.user.is_authenticated else None,
                nota=f"Copia de «{flujo.titulo}»"
                     + (f" {origen.etiqueta}" if origen else ""),
            )
            if origen:
                clonar_grafo(origen, nueva)
            if not nueva.nodos.exists():
                # Un flujo sin ningún nodo no se puede ni empezar a diseñar.
                Nodo.objects.create(
                    version=nueva, tipo=Nodo.Tipo.INICIO, titulo="Inicio", x=80, y=220
                )
        return Response(
            FlujoSerializer(self.get_queryset().get(pk=copia.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class VersionFlujoViewSet(BaseModelViewSet):
    queryset = VersionFlujo.objects.select_related("flujo", "autor").prefetch_related(
        "nodos", "conexiones"
    )
    serializer_class = VersionFlujoSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "flujo__institucion"
    filter_fields = ("flujo", "estado")

    @action(detail=True, methods=["get"])
    def validar(self, request, pk=None):
        """Devuelve los problemas (errores/avisos) del grafo y si se puede publicar."""
        version = self.get_object()
        problemas = motor.validar_version(version)
        return Response({
            "problemas": problemas,
            "errores": sum(1 for p in problemas if p["sev"] == "error"),
            "avisos": sum(1 for p in problemas if p["sev"] == "aviso"),
            "puede_publicar": not any(p["sev"] == "error" for p in problemas),
        })

    @action(detail=True, methods=["post"], url_path="ensayo")
    def ensayo(self, request, pk=None):
        """
        «Probar» el flujo: lo corre con el motor real y deshace todo.

        Cuerpo: `{"pasos": [{...}, {...}]}` — los datos de cada parada, en el
        mismo formato que recibe `avanzar` (para un formulario,
        `{"valores": {<campo_id>: valor}}`).

        Devuelve por dónde pasó, dónde quedó y, si el motor se plantó, en qué
        nodo y por qué. Que el error viaje como parte del resultado y no como un
        400 es deliberado: «acá hace falta un médico con matrícula» es la
        respuesta correcta del ensayo, no una falla de la petición.
        """
        version = self.get_object()
        pasos = request.data.get("pasos") or []
        if not isinstance(pasos, list):
            return Response(
                {"detail": "«pasos» tiene que ser una lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(motor.ensayar(version, pasos, autor=request.user))

    @action(detail=True, methods=["post"])
    def publicar(self, request, pk=None):
        """Publica la versión si no tiene errores; marca las anteriores como reemplazadas."""
        version = self.get_object()
        problemas = motor.validar_version(version)
        if any(p["sev"] == "error" for p in problemas):
            return Response(
                {"detail": "La versión tiene errores y no puede publicarse.", "problemas": problemas},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            # Degradar la anterior y publicar ésta son una sola cosa o ninguna:
            # si el proceso se cae en el medio, el flujo queda con CERO versiones
            # publicadas y las derivaciones fallan con «no tiene un flujo
            # publicado para recibir el caso». El lock evita, además, que dos
            # publicaciones simultáneas dejen dos versiones publicadas a la vez,
            # que es un estado que el resto del código asume imposible.
            hermanas = list(
                VersionFlujo.objects.select_for_update().filter(flujo_id=version.flujo_id)
            )
            for v in hermanas:
                if v.pk != version.pk and v.estado == VersionFlujo.Estado.PUBLICADA:
                    v.estado = VersionFlujo.Estado.REEMPLAZADA
                    v.save(update_fields=["estado"])
            version.estado = VersionFlujo.Estado.PUBLICADA
            version.save(update_fields=["estado"])
        return Response(self.get_serializer(version).data)

    @action(detail=True, methods=["post"])
    def archivar(self, request, pk=None):
        """Retira el proceso de circulación: la versión publicada pasa a ARCHIVADA.

        Un proceso se discontinúa —cambia el protocolo, cierra un consultorio,
        termina la campaña de vacunación— y hasta acá no había forma de sacarlo:
        el estado ARCHIVADA existía en el modelo y en la pestaña del listado, y
        ningún código lo asignaba nunca. El flujo viejo seguía publicado para
        siempre y seguía apareciendo en el desplegable de «Nuevo caso», así que el
        administrativo del mostrador podía meter un paciente en un circuito que la
        institución dejó de usar.

        No se retira con casos en curso: esos casos están parados sobre estos
        nodos y el flujo tiene que poder terminarlos.
        """
        version = self.get_object()
        if version.estado != VersionFlujo.Estado.PUBLICADA:
            return Response(
                {"detail": "Sólo se retira la versión publicada: ésta está "
                           f"{version.get_estado_display().lower()}."},
                status=status.HTTP_409_CONFLICT,
            )
        from apps.casos.models import Caso

        activos = (
            Caso.objects.filter(version=version)
            .exclude(estado__in=Caso.ESTADOS_FINALIZADOS)
            .count()
        )
        if activos:
            return Response(
                {
                    "detail": f"El flujo tiene {activos} "
                              f"{'caso activo' if activos == 1 else 'casos activos'} en esta "
                              "versión. Terminalos o cerralos antes de retirarlo: si se retira "
                              "ahora, esos casos quedan corriendo un proceso que ya no figura "
                              "en ningún lado.",
                    "casos_activos": activos,
                },
                status=status.HTTP_409_CONFLICT,
            )
        version.estado = VersionFlujo.Estado.ARCHIVADA
        version.save(update_fields=["estado"])
        return Response(self.get_serializer(version).data)

    @action(detail=True, methods=["post"], url_path="nueva-version")
    def nueva_version(self, request, pk=None):
        """Clona el grafo de esta versión en un borrador nuevo (numero + 1).

        Es la salida que faltaba: una vez publicada, la versión se congela, y
        cambiar el circuito sin esto significaba editarlo abajo de los pacientes
        que ya estaban adentro. Los casos en curso siguen corriendo con la
        versión con la que arrancaron.
        """
        version = self.get_object()
        with transaction.atomic():
            hermanas = list(
                VersionFlujo.objects.select_for_update().filter(flujo_id=version.flujo_id)
            )
            borrador = next(
                (v for v in hermanas if v.estado == VersionFlujo.Estado.BORRADOR), None
            )
            if borrador:
                # Dos borradores del mismo flujo compitiendo terminan en que se
                # publica el equivocado. Se manda al que ya existe.
                return Response(
                    {
                        "detail": f"El flujo ya tiene un borrador ({borrador.etiqueta}): "
                                  "editá ese o publicalo antes de sacar otra versión.",
                        "borrador": borrador.pk,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            nueva = VersionFlujo.objects.create(
                flujo_id=version.flujo_id,
                numero=max((v.numero for v in hermanas), default=0) + 1,
                estado=VersionFlujo.Estado.BORRADOR,
                autor=request.user if request.user.is_authenticated else None,
                nota=f"Copia de {version.etiqueta}",
            )
            clonar_grafo(version, nueva)
        return Response(
            self.get_serializer(self.get_queryset().get(pk=nueva.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class NodoViewSet(SoloSobreBorrador, BaseModelViewSet):
    queryset = Nodo.objects.select_related("version", "formulario").prefetch_related("grupos__area")
    serializer_class = NodoSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version", "tipo")

    @action(detail=True, methods=["post"])
    def pantalla(self, request, pk=None):
        """Genera (si falta) y devuelve el token de la pantalla de llamados del nodo.

        La pantalla pública vive en `/pantalla/<token>` (sin login). Con `?rotar=1`
        en el cuerpo se reemplaza el token actual (invalida la URL anterior)."""
        import secrets

        nodo = self.get_object()
        if not nodo.pantalla_token or request.data.get("rotar"):
            nodo.pantalla_token = secrets.token_urlsafe(12)
            nodo.save(update_fields=["pantalla_token"])
        return Response({"token": nodo.pantalla_token, "ruta": f"/pantalla/{nodo.pantalla_token}"})


class ConexionViewSet(SoloSobreBorrador, BaseModelViewSet):
    queryset = Conexion.objects.select_related("version", "origen", "destino")
    serializer_class = ConexionSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version",)
