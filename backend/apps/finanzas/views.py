from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from .models import ConcesionFinanciera, HechoAtencionCosteable, Prestacion
from .permisos import concesiones_financieras_de, tiene_concesion_financiera
from .serializers import (
    ConcesionFinancieraSerializer,
    HechoAtencionCosteableSerializer,
    PrestacionSerializer,
)


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


class PuedeConfigurarCatalogoCostos(BasePermission):
    """La configuración de catálogo es institucional, no clínica."""

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
                ).filter(todas_las_areas=True).exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        institucion_id = getattr(obj, "institucion_id", None)
        return institucion_id is not None and tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            institucion_id,
        )


class CatalogoCostosInstitucionalMixin:
    permission_classes = [IsAuthenticated, PuedeConfigurarCatalogoCostos]

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs
        instituciones = concesiones_financieras_de(
            usuario,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
        ).filter(todas_las_areas=True).values_list("membresia__institucion_id", flat=True)
        return qs.filter(**{f"{self.institucion_path}__in": instituciones}).distinct()

    def verificar_institucion_configurable(self, institucion_id):
        if not tiene_concesion_financiera(
            self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            institucion_id,
        ):
            raise PermissionDenied("No tenés autorización para configurar costos en esta institución.")


class ConcesionFinancieraViewSet(BaseModelViewSet):
    """Administración institucional de los permisos propios de Finanzas."""

    queryset = ConcesionFinanciera.objects.select_related(
        "membresia__usuario", "membresia__institucion"
    ).prefetch_related("areas")
    serializer_class = ConcesionFinancieraSerializer
    capacidad_requerida = "config_institucional"
    protege_lectura = True
    institucion_path = "membresia__institucion"
    filter_fields = ("membresia", "accion", "todas_las_areas", "permite_sensibles", "areas")


class PrestacionViewSet(CatalogoCostosInstitucionalMixin, BaseModelViewSet):
    queryset = Prestacion.objects.select_related("institucion", "nodo")
    serializer_class = PrestacionSerializer
    institucion_path = "institucion"
    filter_fields = ("institucion", "nodo", "activo")
    ordering_fields = ("codigo", "nombre", "id")

    def perform_create(self, serializer):
        self.verificar_institucion_configurable(serializer.validated_data["institucion"].id)
        serializer.save()


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
