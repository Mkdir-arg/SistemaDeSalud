from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.casos.models import Caso
from apps.common import BaseModelViewSet, CapacidadPermission, OrdenEstable
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
    capacidad_requerida = "config"
    filter_fields = ("activa",)
    search_fields = ("nombre",)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
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
    capacidad_requerida = "trabajo"
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
        if p.get("abiertos") == "true":
            qs = qs.filter(estado__in=[
                Traslado.Estado.SOLICITADO, Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO,
            ])
        # De qué lado: quien recibe quiere ver lo que le mandan, no lo que mandó.
        ids = self._mis_instituciones()
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

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["mis_instituciones"] = set(self._mis_instituciones())
        return ctx

    def _responder(self, t):
        return Response(self.get_serializer(t).data)

    def _de_mi_lado(self, t, lado):
        """¿Puedo actuar de este lado? Origen pide; destino responde."""
        mis = set(self._mis_instituciones())
        return (t.origen_id if lado == "origen" else t.destino_id) in mis

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
        try:
            t = motor.marcar_recibido(t, autor=request.user)
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
        from apps.instituciones.models import Cama

        destinos = []
        for i in motor.destinos_posibles(inst):
            camas = Cama.objects.filter(area__institucion=i, activa=True)
            operativas = camas.exclude(estado=Cama.Estado.BLOQUEADA).count()
            destinos.append({
                "id": i.id,
                "nombre": i.nombre,
                "km": motor.distancia_km(inst, i),
                "camas_libres": camas.filter(estado=Cama.Estado.LIBRE).count(),
                "camas_operativas": operativas,
                "saturado": i.nombre in [
                    s["institucion"].nombre
                    for red in inst.redes.filter(activa=True) for s in motor.saturadas(red)
                ],
            })
        # Primero los que tienen lugar; entre ellos, el más cerca.
        destinos.sort(key=lambda d: (d["saturado"], d["km"] if d["km"] is not None else 1e9))
        return Response({"destinos": destinos})
