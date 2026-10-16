
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from apps.common import BaseModelViewSet

from .integridad import bloquear_formularios, exigir_editable
from .models import Campo, Formulario
from .serializers import (
    CampoSerializer,
    CondicionQueUsaCampoSerializer,
    FormularioSerializer,
    UsoFormularioSerializer,
)


class FormularioEnUso(APIException):
    """Se intentó borrar un formulario que algún paso de algún flujo todavía pide."""

    status_code = status.HTTP_409_CONFLICT


class FormularioViewSet(BaseModelViewSet):
    queryset = Formulario.objects.select_related("institucion", "area").prefetch_related(
        # El conteo de valores viaja con cada campo (lo usa el diálogo de borrado
        # para decir cuántos datos están en juego). Anotado en el prefetch y no
        # por campo: la pantalla de detalle abre todos los campos de una.
        #
        # El `order_by` es explícito porque `annotate` arma un GROUP BY y ahí
        # Django IGNORA el `Meta.ordering` del modelo: sin esto los campos
        # salían en el orden en que se crearon, así que reordenarlos no cambiaba
        # nada en la pantalla que completa el administrativo ni en la vista previa.
        Prefetch(
            "campos",
            queryset=Campo.objects.annotate(valores_n=Count("valores")).order_by("orden", "id"),
        )
    ).annotate(
        # En cuántos FLUJOS distintos se pide este formulario. Anotado y no
        # calculado por fila: el listado abre todos los formularios de la
        # institución y una consulta por fila los multiplica.
        #
        # Las versiones archivadas no cuentan: son el registro de un circuito que
        # ya no se ejecuta, y contarlas haría ver como «en uso» a un formulario
        # que ningún flujo vigente pide.
        usos_n_anotado=Count(
            "nodos__version__flujo",
            filter=~Q(nodos__version__estado="archivada"),
            distinct=True,
        )
    )
    serializer_class = FormularioSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area")
    # La descripción también se busca: el listado la muestra como columna, así que
    # buscar por algo que está a la vista y no encontrarlo se siente roto.
    search_fields = ["titulo", "descripcion"]
    ordering_fields = ["titulo", "creado"]

    @transaction.atomic
    def perform_update(self, serializer):
        formulario = bloquear_formularios([serializer.instance.pk])[serializer.instance.pk]
        serializer.instance = formulario
        serializer._validated_data = serializer.run_validation(serializer.initial_data)
        exigir_editable(formulario, cambios=serializer.validated_data)
        serializer.save()

    @extend_schema(
        responses=inline_serializer(
            name="UsosDelFormulario",
            fields={
                "usos": UsoFormularioSerializer(many=True),
                "condiciones": CondicionQueUsaCampoSerializer(many=True),
            },
        )
    )
    @action(detail=True, methods=["get"])
    def usos(self, request, pk=None):
        """Qué pasos de qué flujos piden este formulario, y qué ramas leen sus campos.

        Sin esto el constructor era una pantalla a ciegas: agregar un campo
        requerido TRABA en el acto los casos que están parados en ese paso (el
        motor no los deja avanzar hasta cargarlo) y quitar un campo rompe las
        Decisiones que lo comparan por id —los casos se van por la rama que no
        era—, y nada de eso se podía saber sin abrir los flujos de a uno.

        Devuelve también las condiciones que mencionan cada campo, para que el
        diálogo de borrado pueda nombrar la rama que se rompería —y las busca en
        todos los flujos vigentes de la institución, porque el constructor de
        reglas ofrece los campos de todos los formularios.
        """
        from apps.casos.models import Caso
        from apps.casos.motor import campos_de_condicion
        from apps.flujos.models import Conexion, Nodo, VersionFlujo

        formulario = self.get_object()
        campos_ids = set(Campo.objects.filter(formulario=formulario).values_list("id", flat=True))

        nodos = list(
            Nodo.objects.filter(formulario=formulario)
            .exclude(version__estado=VersionFlujo.Estado.ARCHIVADA)
            .select_related("version", "version__flujo")
            .order_by("version__flujo__titulo", "-version__numero", "id")
        )
        # Casos parados justo en ese paso: son los que un campo requerido nuevo
        # traba de inmediato. Una sola consulta agrupada, no una por nodo.
        parados = dict(
            Caso.objects.filter(nodo_actual__in=nodos)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .values_list("nodo_actual")
            .annotate(n=Count("id"))
        )
        usos = [
            {
                "flujo_id": n.version.flujo_id,
                "flujo": n.version.flujo.titulo,
                "version_id": n.version_id,
                "version_numero": n.version.numero,
                "version_estado": n.version.estado,
                "nodo_id": n.id,
                "nodo_titulo": n.titulo or "Paso sin título",
                "casos_activos": parados.get(n.id, 0),
            }
            for n in nodos
        ]

        condiciones = []
        if campos_ids:
            # Se buscan las ramas en TODOS los flujos vigentes de la institución,
            # no sólo en los que usan este formulario: el constructor de reglas
            # ofrece los campos de todos los formularios, así que una Decisión de
            # otro flujo puede estar comparando un campo de acá. Limitarlo a los
            # flujos que lo piden dejaría fuera justo las ramas que nadie va a ir
            # a revisar.
            conexiones = (
                Conexion.objects.filter(
                    version__flujo__institucion=formulario.institucion_id
                )
                .exclude(version__estado=VersionFlujo.Estado.ARCHIVADA)
                .exclude(condicion={})
                .select_related("version", "version__flujo", "origen", "destino")
            )
            for c in conexiones:
                for campo_id in sorted(campos_de_condicion(c.condicion) & campos_ids):
                    condiciones.append({
                        "campo_id": campo_id,
                        "flujo": c.version.flujo.titulo,
                        "version_estado": c.version.estado,
                        "desde": c.origen.titulo or "Paso sin título",
                        "hasta": c.destino.titulo or "Paso sin título",
                        "etiqueta": c.etiqueta or "sin etiqueta",
                    })

        return Response({"usos": usos, "condiciones": condiciones})

    @action(detail=True, methods=["post"])
    def duplicar(self, request, pk=None):
        """Copia el formulario con TODOS sus campos, sin ningún dato cargado.

        «Admisión adultos» y «Admisión pediatría» comparten diez de doce campos:
        sin duplicar hay que recrearlos de a uno, y cada campo recreado a mano es
        una etiqueta distinta que las Decisiones no van a poder reusar. Los campos
        se copian en una transacción y con el `orden` normalizado al índice, para
        que la copia no herede los órdenes repetidos de los formularios viejos.
        """
        formulario = self.get_object()
        with transaction.atomic():
            formulario = bloquear_formularios([formulario.pk])[formulario.pk]
            campos = list(Campo.objects.select_for_update().filter(formulario=formulario).order_by("pk"))
            copia = Formulario.objects.create(
                institucion=formulario.institucion,
                area=formulario.area,
                # Recortado a `max_length`: un título ya largo más « (copia)» se
                # pasa del campo y la copia falla con un error de base.
                titulo=f"{formulario.titulo} (copia)"[:200],
                descripcion=formulario.descripcion,
            )
            Campo.objects.bulk_create([
                Campo(
                    formulario=copia,
                    label=c.label,
                    tipo=c.tipo,
                    requerido=c.requerido,
                    ayuda=c.ayuda,
                    opciones=c.opciones,
                    unidad=c.unidad,
                    minimo=c.minimo,
                    maximo=c.maximo,
                    origen=c.origen,
                    orden=i,
                )
                for i, c in enumerate(
                    sorted(campos, key=lambda c: (c.orden, c.pk))
                )
            ])
        return Response(
            self.get_serializer(self.get_queryset().get(pk=copia.pk)).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def reordenar(self, request, pk=None):
        """Fija el orden de TODOS los campos de una vez: `{"campos": [id, id, …]}`.

        Antes la pantalla mandaba un PATCH por campo movido, en serie: mover el
        último de doce eran doce pedidos encadenados y, si el quinto fallaba, el
        formulario quedaba con la mitad del orden nuevo y la mitad del viejo —o
        con órdenes repetidos, que es exactamente lo que hacía que reordenar «no
        hiciera nada». Acá es una transacción y un `bulk_update`.

        Se exige la lista COMPLETA y exacta: si el cliente venía con una vista
        vieja (alguien agregó o quitó un campo en otra pestaña), aplicar lo que
        mandó dejaría campos sin orden asignado. Mejor rechazarlo y que recargue.
        """
        formulario = self.get_object()
        pedido = request.data.get("campos")
        if not isinstance(pedido, list):
            raise ValidationError({"campos": "Se espera la lista de ids de los campos, en orden."})
        try:
            pedido = [int(c) for c in pedido]
        except (TypeError, ValueError):
            raise ValidationError({"campos": "Los ids de los campos tienen que ser números."})

        with transaction.atomic():
            formulario = bloquear_formularios([formulario.pk])[formulario.pk]
            campos = {c.pk: c for c in Campo.objects.select_for_update().filter(formulario=formulario).order_by("pk")}
            if sorted(pedido) != sorted(campos):
                raise ValidationError({"campos": "La lista no coincide con los campos del formulario. Recargá la pantalla."})
            cambiados = []
            for i, campo_id in enumerate(pedido):
                campo = campos[campo_id]
                exigir_editable(formulario, instancia=campo, cambios={"orden": i})
                if campo.orden != i:
                    campo.orden = i
                    cambiados.append(campo)
            if cambiados:
                Campo.objects.bulk_update(cambiados, ["orden"])
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def perform_destroy(self, instance):
        """No se borra un formulario que un flujo todavía pide, ni uno con datos cargados.

        `Nodo.formulario` es SET_NULL: borrarlo no rompe la base pero deja el paso
        «Sin formulario» en flujos publicados, y el caso que llegue ahí se para en
        una pantalla que no pide nada y no tiene con qué avanzar. Y `Campo` es
        CASCADE desde el formulario y `ValorCampo` CASCADE desde el campo, así que
        borrar el formulario de admisión se lleva el motivo de consulta y el nivel
        de triage de cada caso que pasó por ahí, sin dejar rastro.
        """
        instance = bloquear_formularios([instance.pk])[instance.pk]
        exigir_editable(instance)
        nodos = list(
            instance.nodos.exclude(version__estado="archivada").select_related(
                "version", "version__flujo"
            )
        )
        if nodos:
            flujos = sorted({n.version.flujo.titulo for n in nodos})
            raise FormularioEnUso({
                "detail": (
                    f"«{instance.titulo}» se pide en "
                    + ("el flujo " if len(flujos) == 1 else "los flujos ")
                    + ", ".join(f"«{t}»" for t in flujos)
                    + ". Quitalo de esos pasos primero: si se borra ahora, el paso queda "
                    "sin formulario y el caso que llegue no tiene con qué avanzar."
                ),
                "flujos": flujos,
            })

        cargados = sum(
            Campo.objects.filter(formulario=instance)
            .annotate(n=Count("valores"))
            .values_list("n", flat=True)
        )
        if cargados:
            raise FormularioEnUso({
                "detail": (
                    f"«{instance.titulo}» tiene {cargados} "
                    f"{'valor cargado' if cargados == 1 else 'valores cargados'} en casos "
                    "reales. Borrarlo los borraría a todos y no hay de dónde recuperarlos."
                ),
                "valores": cargados,
            })
        instance.delete()


class CampoViewSet(BaseModelViewSet):
    # Mismo motivo que en el prefetch de arriba: con `annotate` el `Meta.ordering`
    # no se aplica, y una lista sin orden explícito pagina mal (una fila puede
    # salir en dos páginas o en ninguna).
    queryset = (
        Campo.objects.select_related("formulario")
        .annotate(valores_n=Count("valores"))
        .order_by("formulario", "orden", "id")
    )
    serializer_class = CampoSerializer
    capacidad_requerida = "diseno_flujos"
    institucion_path = "formulario__institucion"
    filter_fields = ("formulario", "tipo", "requerido", "origen")

    @transaction.atomic
    def perform_create(self, serializer):
        pk = serializer.validated_data["formulario"].pk
        formulario = bloquear_formularios([pk])[pk]
        exigir_editable(formulario)
        serializer.save(formulario=formulario)

    @transaction.atomic
    def perform_update(self, serializer):
        pk = serializer.instance.formulario_id
        formulario = bloquear_formularios([pk])[pk]
        campo = get_object_or_404(Campo.objects.order_by().select_for_update(), pk=serializer.instance.pk, formulario_id=pk)
        serializer.instance = campo
        serializer._validated_data = serializer.run_validation(serializer.initial_data)
        exigir_editable(formulario, instancia=campo, cambios=serializer.validated_data)
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        formulario = bloquear_formularios([instance.formulario_id])[instance.formulario_id]
        campo = get_object_or_404(Campo.objects.order_by().select_for_update(), pk=instance.pk, formulario_id=formulario.pk)
        exigir_editable(formulario)
        campo.delete()
