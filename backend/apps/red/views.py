from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.casos.models import Caso
from apps.common import BaseModelViewSet, CapacidadPermission, OrdenEstable, capacidades_de, tiene_capacidad
from apps.instituciones.models import Area, Institucion
from rest_framework.filters import SearchFilter

from . import motor
from .models import Red, Traslado
from .serializers import RedSerializer, TrasladoSerializer


class RedViewSet(BaseModelViewSet):
    """
    Redes de establecimientos. Definirlas es configuración de plataforma: quién
    puede derivarle a quién no lo decide un hospital solo.
    """

    queryset = Red.objects.prefetch_related("instituciones")
    serializer_class = RedSerializer
    capacidad_requerida = "gobierno_plataforma"
    # Por institución también: un hospital puede estar en la región sanitaria y
    # además en una red de patología (trauma, perinatal, quemados). Sin este
    # filtro la pantalla sólo puede quedarse con la primera de TODAS mis redes
    # por orden alfabético, que para una dirección de red con varios efectores
    # es el panorama de otro lado.
    filter_fields = ("activa", "instituciones")
    search_fields = ("nombre",)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not tiene_capacidad(user, "gobierno_plataforma"):
            # Sólo las redes donde participa alguna de mis instituciones.
            ids = user.membresias.filter(activo=True).values_list("institucion_id", flat=True)
            qs = qs.filter(instituciones__in=list(ids)).distinct()
        return qs

    @action(detail=True, methods=["get"])
    def tablero(self, request, pk=None):
        """
        Indicadores comparados de la red: `?dias=30`.

        Todo se calcula igual en todos los establecimientos —misma definición de
        ocupación, mismo rango— porque una región usa esto para decidir a dónde
        mandar recursos, y dos criterios distintos harían que la comparación
        mienta.
        """
        red = self.get_object()
        try:
            dias = max(1, min(int(request.query_params.get("dias", 30)), 365))
        except ValueError:
            dias = 30
        d = motor.tablero(red, dias=dias)
        return Response({
            "red": red.nombre,
            "dias": d["dias"],
            "establecimientos": [{
                "id": f["institucion"].id,
                "nombre": f["institucion"].nombre,
                **{k: v for k, v in f.items() if k != "institucion"},
            } for f in d["establecimientos"]],
            "totales": d["totales"],
            "saturados": d["saturados"],
        })

    @action(detail=True, methods=["get"])
    def camas(self, request, pk=None):
        """
        Disponibilidad de camas de toda la red.

        Es lo que permite derivar con criterio en vez de llamar por teléfono a
        preguntar si hay lugar.
        """
        red = self.get_object()
        datos = motor.camas_en_red(red)
        return Response({
            "red": red.nombre,
            "establecimientos": [{
                "id": d["institucion"].id,
                "nombre": d["institucion"].nombre,
                "total": d["total"],
                "operativas": d["operativas"],
                "ocupadas": d["ocupadas"],
                "libres": d["libres"],
                # Ni libres ni ocupadas: son las que se liberan con un llamado a
                # limpieza, o sea la diferencia entre «no hay lugar» y «hay lugar
                # en veinte minutos».
                "higiene": d["higiene"],
                "ocupacion": d["ocupacion"],
            } for d in datos],
            "saturados": [d["institucion"].nombre for d in motor.saturadas(red)],
        })


class TrasladoViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Traslados entre establecimientos.

    **El único recurso que cruza la frontera entre instituciones.** Se ve si una
    de mis instituciones está de alguno de los dos lados, y por eso no lleva
    datos clínicos más allá del resumen que el origen decidió escribir.

    No hay `create` ni `update` genéricos: todo el ciclo pasa por acciones,
    porque cada paso mueve además el caso de alguno de los dos lados.
    """

    serializer_class = TrasladoSerializer
    permission_classes = [IsAuthenticated, CapacidadPermission]
    capacidad_requerida = "traslados_red"
    filter_backends = [OrdenEstable, SearchFilter]
    search_fields = ("ciudadano__nombre", "ciudadano__apellido", "ciudadano__documento")
    ordering_fields = ("solicitado_at", "urgente", "estado")
    queryset = Traslado.objects.none()  # el real sale de `visibles_para`

    def get_queryset(self):
        qs = motor.visibles_para(self.request.user).select_related(
            "origen", "destino", "ciudadano", "area_destino", "solicitado_por",
            "caso_origen", "caso_destino",
        )
        p = self.request.query_params
        if (e := p.get("estado")):
            qs = qs.filter(estado=e)
        abiertos = [
            Traslado.Estado.SOLICITADO, Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO,
        ]
        if p.get("abiertos") == "true":
            qs = qs.filter(estado__in=abiertos)
        elif p.get("abiertos") == "false":
            # La otra mitad. Sin esto, la pantalla tiene que traerse el
            # histórico entero para separar «en curso» de «resueltos» en el
            # cliente, y un pedido sin responder se cae de la página.
            qs = qs.exclude(estado__in=abiertos)
        # De qué lado: quien recibe quiere ver lo que le mandan, no lo que mandó.
        actual = self._institucion_actual()
        ids = [actual] if actual is not None else self._mis_instituciones()
        if p.get("lado") == "entrantes":
            qs = qs.filter(destino_id__in=ids)
        elif p.get("lado") == "salientes":
            qs = qs.filter(origen_id__in=ids)
        return qs

    def _mis_instituciones(self):
        u = self.request.user
        if u.is_superuser:
            return list(Institucion.objects.values_list("id", flat=True))
        return list(u.membresias.filter(activo=True).values_list("institucion_id", flat=True))

    def _institucion_actual(self):
        """
        El establecimiento en el que está parado quien mira, si lo mandó.

        Sin esto, «de qué lado estoy» se resuelve contra el conjunto de mis
        membresías, y quien tiene dos efectores de la misma red —una dirección
        de red, una región, un superusuario— sale como origen en TODOS los
        traslados: la pestaña «Nos derivan» le esconde «Responder» y «Llegó», y
        el único botón que le queda cancela el pedido del otro hospital.
        """
        crudo = self.request.query_params.get("institucion")
        if crudo in (None, "") and self.request.method != "GET":
            crudo = self.request.data.get("institucion")
        try:
            valor = int(crudo)
        except (TypeError, ValueError):
            return None
        return valor if valor in self._mis_instituciones() else None

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["mis_instituciones"] = set(self._mis_instituciones())
        ctx["institucion_actual"] = self._institucion_actual()
        return ctx

    def _responder(self, t):
        return Response(self.get_serializer(t).data)

    def _de_mi_lado(self, t, lado):
        """
        ¿Puedo actuar de este lado? Origen pide; destino responde.

        Con la institución actual declarada se decide contra ella: quien tiene
        los dos efectores no puede quedar habilitado en los dos lados del mismo
        traslado, que es como termina cancelándole el pedido al otro hospital
        desde la fila que está leyendo como «me están derivando».
        """
        esperado = t.origen_id if lado == "origen" else t.destino_id
        actual = self._institucion_actual()
        if actual is not None:
            return esperado == actual
        return esperado in set(self._mis_instituciones())

    def _sin_capacidad(self, institucion_id):
        """
        La capacidad operativa EN ese establecimiento, o el 403 que corresponde.

        Dos agujeros tapa esto. Uno: `solicitar` es una acción de LISTA, y
        `CapacidadPermission` sólo valida la capacidad en `create` y en las
        acciones de detalle —que se revalidan contra el objeto—, así que un
        usuario de sólo diseño (el rol del proveedor, del consultor, de quien
        arma los flujos) podía pedir el traslado de un paciente real: el caso
        quedaba EN_ESPERA, el destino reservaba una cama, y después ni él podía
        cancelarlo ni nadie más podía derivar a ese paciente hasta que alguien
        diera de baja el pedido falso.

        Dos: este viewset no declara `institucion_path` —origen y destino son
        distintos según la acción—, así que `has_object_permission` resuelve la
        capacidad contra la UNIÓN de mis membresías: quien es jefe de área en un
        hospital y configurador en otro podía aceptar traslados en el segundo,
        donde no tiene ninguna capacidad operativa. Acá se valida contra el lado
        que manda en cada acción.
        """
        if self.capacidad_requerida in capacidades_de(self.request.user, institucion_id):
            return None
        return Response(
            {"detail": "No tenés permiso para operar traslados en este establecimiento."},
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=["post"])
    def solicitar(self, request):
        """
        Pide un traslado: {"caso", "destino", "motivo", "detalle", "area_destino"}.
        """
        caso = Caso.objects.filter(pk=request.data.get("caso")).first()
        destino = Institucion.objects.filter(pk=request.data.get("destino")).first()
        if caso is None or destino is None:
            return Response({"detail": "Falta el caso o el establecimiento de destino."},
                            status=status.HTTP_400_BAD_REQUEST)
        if caso.institucion_id not in self._mis_instituciones():
            return Response({"detail": "Ese caso no es de tu institución."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(caso.institucion_id)):
            return falta
        area = Area.objects.filter(pk=request.data.get("area_destino")).first()
        try:
            t = motor.solicitar(
                caso, destino,
                request.data.get("motivo") or Traslado.Motivo.COMPLEJIDAD,
                detalle=(request.data.get("detalle") or "").strip(),
                area_destino=area, autor=request.user,
                urgente=bool(request.data.get("urgente")),
            )
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(t).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def aceptar(self, request, pk=None):
        """Acepta y abre el caso del lado del destino: {"area_destino"}."""
        t = self.get_object()
        if not self._de_mi_lado(t, "destino"):
            return Response({"detail": "Sólo el establecimiento de destino puede aceptar."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.destino_id)):
            return falta
        area = Area.objects.filter(pk=request.data.get("area_destino")).first()
        try:
            t = motor.aceptar(t, autor=request.user, area_destino=area)
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        """Rechaza con motivo: {"motivo"}."""
        t = self.get_object()
        if not self._de_mi_lado(t, "destino"):
            return Response({"detail": "Sólo el establecimiento de destino puede rechazar."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.destino_id)):
            return falta
        try:
            t = motor.rechazar(t, request.data.get("motivo") or "", autor=request.user)
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """El origen se arrepiente, antes de que el destino haya abierto el caso."""
        t = self.get_object()
        if not self._de_mi_lado(t, "origen"):
            return Response({"detail": "Sólo el establecimiento de origen puede cancelar."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.origen_id)):
            return falta
        try:
            t = motor.cancelar(t, autor=request.user, motivo=(request.data.get("motivo") or ""))
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=True, methods=["post"], url_path="en-camino")
    def en_camino(self, request, pk=None):
        """Salió la ambulancia: {"movil"}."""
        t = self.get_object()
        if not self._de_mi_lado(t, "origen"):
            return Response({"detail": "Lo registra el establecimiento que traslada."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.origen_id)):
            return falta
        try:
            t = motor.marcar_en_camino(t, movil=(request.data.get("movil") or ""), autor=request.user)
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=True, methods=["post"])
    def recibido(self, request, pk=None):
        """Llegó. Recién acá se cierra el caso de origen."""
        t = self.get_object()
        if not self._de_mi_lado(t, "destino"):
            return Response({"detail": "Lo registra el establecimiento que recibe."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.destino_id)):
            return falta
        try:
            t = motor.marcar_recibido(t, autor=request.user)
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=True, methods=["post"], url_path="no-llego")
    def no_llego(self, request, pk=None):
        """
        El paciente no llegó: {"motivo"}.

        La registran los dos lados —el que se entera primero—: el que falleció
        en la ambulancia lo sabe el origen, y el que se desvió a otro efector
        puede saberlo cualquiera. Sin esto el caso de origen queda congelado
        EN_ESPERA para siempre.
        """
        t = self.get_object()
        mio = next((l for l in ("origen", "destino") if self._de_mi_lado(t, l)), None)
        if mio is None:
            return Response({"detail": "Sólo los establecimientos del traslado pueden registrarlo."},
                            status=status.HTTP_403_FORBIDDEN)
        if (falta := self._sin_capacidad(t.origen_id if mio == "origen" else t.destino_id)):
            return falta
        try:
            t = motor.no_llego(t, request.data.get("motivo") or "", autor=request.user)
        except motor.ErrorTraslado as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return self._responder(t)

    @action(detail=False, methods=["get"])
    def destinos(self, request):
        """A dónde puedo derivar: `?institucion=<id>`."""
        inst = Institucion.objects.filter(pk=request.query_params.get("institucion")).first()
        if inst is None or inst.id not in self._mis_instituciones():
            return Response({"destinos": []})
        # Con la ocupación y la distancia: elegir a dónde derivar sin eso es
        # elegir a ciegas entre opciones que en una lista alfabética se ven
        # iguales, cuando una puede estar llena y la otra a media hora más.
        from django.db.models import Count, Q

        from apps.instituciones.models import Cama

        posibles = list(motor.destinos_posibles(inst))
        # Los saturados, UNA vez y fuera del bucle. Calcularlos por destino
        # hacía el endpoint cuadrático —`saturadas()` recorre la red entera— y
        # el resultado es el mismo en cada vuelta. Es el endpoint que se abre
        # con un paciente esperando adelante.
        saturados_ids = {
            s["institucion"].id
            for red in inst.redes.filter(activa=True) for s in motor.saturadas(red)
        }
        # Las camas de todos los destinos en una consulta, no dos por destino.
        camas = {
            c["area__institucion"]: c
            for c in Cama.objects.filter(
                area__institucion__in=[i.id for i in posibles], activa=True
            ).values("area__institucion").annotate(
                libres=Count("id", filter=Q(estado=Cama.Estado.LIBRE)),
                operativas=Count("id", filter=~Q(estado=Cama.Estado.BLOQUEADA)),
            )
        }
        destinos = [{
            "id": i.id,
            "nombre": i.nombre,
            "km": motor.distancia_km(inst, i),
            "camas_libres": (camas.get(i.id) or {}).get("libres", 0),
            "camas_operativas": (camas.get(i.id) or {}).get("operativas", 0),
            # Por id y no por nombre: `Institucion.nombre` no es único, y dos
            # «Hospital Municipal» en la misma red hacían que el que tiene camas
            # libres se marcara SATURADO y cayera al fondo de la lista, en
            # silencio, detrás de opciones media hora más lejos.
            "saturado": i.id in saturados_ids,
        } for i in posibles]
        # Primero los que tienen lugar; entre ellos, el más cerca.
        destinos.sort(key=lambda d: (d["saturado"], d["km"] if d["km"] is not None else 1e9))
        return Response({"destinos": destinos})
