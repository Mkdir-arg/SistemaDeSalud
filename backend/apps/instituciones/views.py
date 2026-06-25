from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common import BaseModelViewSet

from .models import Area, Box, Grupo, Institucion, Subarea
from .serializers import AreaSerializer, BoxSerializer, GrupoSerializer, InstitucionSerializer, SubareaSerializer


class InstitucionViewSet(BaseModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    institucion_path = "id"
    filter_fields = ("activa",)
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "cuit"]
    ordering_fields = ["nombre", "creada"]

    @action(detail=True, methods=["get"])
    def metricas(self, request, pk=None):
        """Conteos para el panel de la institución."""
        from apps.accounts.models import Membresia
        from apps.casos.models import Caso

        inst = self.get_object()
        return Response({
            "areas": inst.areas.count(),
            "subareas": Subarea.objects.filter(area__institucion=inst).count(),
            "staff": Membresia.objects.filter(institucion=inst).values("usuario").distinct().count(),
            "casos_activos": Caso.objects.filter(institucion=inst).exclude(estado=Caso.Estado.CERRADO).count(),
        })


class AreaViewSet(BaseModelViewSet):
    queryset = Area.objects.select_related("institucion").prefetch_related("subareas")
    serializer_class = AreaSerializer
    institucion_path = "institucion"
    filter_fields = ("institucion", "activa")


class SubareaViewSet(BaseModelViewSet):
    queryset = Subarea.objects.select_related("area")
    serializer_class = SubareaSerializer
    institucion_path = "area__institucion"
    filter_fields = ("area", "activa")


class GrupoViewSet(BaseModelViewSet):
    queryset = Grupo.objects.select_related("area").prefetch_related("miembros")
    serializer_class = GrupoSerializer
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activo")


class BoxViewSet(BaseModelViewSet):
    queryset = Box.objects.select_related("area")
    serializer_class = BoxSerializer
    institucion_path = "area__institucion"
    filter_fields = ("area", "area__institucion", "activo")
