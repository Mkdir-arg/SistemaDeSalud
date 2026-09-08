from django.db.models import Q
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from .models import ConcesionFinanciera, HechoAtencionCosteable
from .permisos import concesiones_financieras_de, tiene_concesion_financiera
from .serializers import HechoAtencionCosteableSerializer


class PuedeVerCostosPaciente(BasePermission):
    """Todo costo asociado a un paciente es sensible en este incremento."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.VER_COSTOS,
                    sensible=True,
                ).exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        return tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.VER_COSTOS,
            obj.institucion_id,
            obj.area_origen_id,
            sensible=True,
        )


class HechoAtencionCosteableViewSet(AuditaLecturaClinica, BaseModelViewSet):
    """Costos de atenciones, separados de los recursos clínicos."""

    queryset = (
        HechoAtencionCosteable.objects
        .select_related("ciudadano", "area")
        .prefetch_related(
            "componentes_esperados",
            "pendientes__componente",
            "imputaciones__componente",
            "imputaciones__ajustes",
        )
    )
    serializer_class = HechoAtencionCosteableSerializer
    permission_classes = [IsAuthenticated, PuedeVerCostosPaciente]
    institucion_path = "institucion"
    ciudadano_path = "ciudadano"
    http_method_names = ["get", "head", "options"]
    filter_fields = ("institucion", "ciudadano", "caso", "area")
    ordering = ("-ocurrida_en", "-id")
    ordering_fields = ("id", "ocurrida_en")

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs

        alcance = Q(pk__in=[])
        concesiones = concesiones_financieras_de(
            usuario,
            ConcesionFinanciera.Accion.VER_COSTOS,
            sensible=True,
        )
        for institucion_id in concesiones.filter(todas_las_areas=True).values_list(
            "membresia__institucion_id", flat=True
        ):
            alcance |= Q(institucion_id=institucion_id)
        for institucion_id, area_id in concesiones.filter(todas_las_areas=False).values_list(
            "membresia__institucion_id", "areas__id"
        ):
            if area_id is not None:
                alcance |= Q(institucion_id=institucion_id, area_origen_id=area_id)
        return qs.filter(alcance).distinct()
