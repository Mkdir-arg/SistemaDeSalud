from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from .models import (
    AjusteCosto,
    ConcesionFinanciera,
    DefinicionComponente,
    HechoAtencionCosteable,
    Prestacion,
    ValorComponente,
)
from .permisos import concesiones_financieras_de, tiene_concesion_financiera
from .serializers import (
    AjusteCostoSerializer,
    ConcesionFinancieraSerializer,
    CorreccionSnapshotCosteoSerializer,
    DefinicionComponenteSerializer,
    HechoAtencionCosteableSerializer,
    PrestacionSerializer,
    ValorComponenteSerializer,
)
from .services import corregir_snapshot_componentes, registrar_ajuste_costo


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
        institucion_id = _institucion_catalogo(obj)
        return institucion_id is not None and tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            institucion_id,
        )


class PuedeGestionarValoresComponentes(BasePermission):
    """Lee valores configurables y habilita alta/corrección según su acción."""

    ACCIONES = (
        ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
        ConcesionFinanciera.Accion.CORREGIR_COSTOS,
    )

    def has_permission(self, request, view):
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            return False
        if usuario.is_superuser:
            return True
        return any(
            concesiones_financieras_de(usuario, accion).filter(todas_las_areas=True).exists()
            for accion in self.ACCIONES
        )

    def has_object_permission(self, request, view, obj):
        return any(
            tiene_concesion_financiera(
                request.user,
                accion,
                _institucion_catalogo(obj),
            )
            for accion in self.ACCIONES
        )


class PuedeCorregirCosto(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario,
                    ConcesionFinanciera.Accion.CORREGIR_COSTOS,
                    sensible=True,
                ).exists()
            )
        )


def _institucion_catalogo(obj):
    if getattr(obj, "institucion_id", None) is not None:
        return obj.institucion_id
    prestacion = getattr(obj, "prestacion", None)
    if prestacion is not None:
        return prestacion.institucion_id
    componente = getattr(obj, "componente", None)
    if componente is not None:
        return componente.prestacion.institucion_id
    return None


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

    def perform_update(self, serializer):
        if set(serializer.validated_data) != {"activo"}:
            raise ValidationError({"detail": "Sólo podés cambiar el estado activo del catálogo."})
        serializer.save()


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
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("institucion", "nodo", "activo")
    ordering_fields = ("codigo", "nombre", "id")

    def perform_create(self, serializer):
        self.verificar_institucion_configurable(serializer.validated_data["institucion"].id)
        serializer.save()


class DefinicionComponenteViewSet(CatalogoCostosInstitucionalMixin, BaseModelViewSet):
    queryset = DefinicionComponente.objects.select_related("prestacion__institucion", "prestacion__nodo")
    serializer_class = DefinicionComponenteSerializer
    institucion_path = "prestacion__institucion"
    http_method_names = ["get", "head", "options", "post", "patch"]
    filter_fields = ("prestacion", "fuente", "activo")
    ordering_fields = ("codigo", "nombre", "orden", "id")

    def perform_create(self, serializer):
        self.verificar_institucion_configurable(
            serializer.validated_data["prestacion"].institucion_id
        )
        serializer.save()


class ValorComponenteViewSet(BaseModelViewSet):
    queryset = ValorComponente.objects.select_related(
        "componente__prestacion__institucion", "reemplaza", "registrado_por"
    )
    serializer_class = ValorComponenteSerializer
    permission_classes = [IsAuthenticated, PuedeGestionarValoresComponentes]
    institucion_path = "componente__prestacion__institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("componente", "reemplaza")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return qs
        instituciones = set()
        for accion in PuedeGestionarValoresComponentes.ACCIONES:
            instituciones.update(
                concesiones_financieras_de(usuario, accion)
                .filter(todas_las_areas=True)
                .values_list("membresia__institucion_id", flat=True)
            )
        return qs.filter(componente__prestacion__institucion_id__in=instituciones).distinct()

    def perform_create(self, serializer):
        componente = serializer.validated_data["componente"]
        reemplaza = serializer.validated_data.get("reemplaza")
        es_correccion = reemplaza and (
            reemplaza.vigente_desde,
            reemplaza.vigente_hasta,
        ) == (
            serializer.validated_data["vigente_desde"],
            serializer.validated_data.get("vigente_hasta"),
        )
        accion = (
            ConcesionFinanciera.Accion.CORREGIR_COSTOS
            if es_correccion
            else ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES
        )
        if not tiene_concesion_financiera(
            self.request.user,
            accion,
            componente.prestacion.institucion_id,
        ):
            raise PermissionDenied("No tenés autorización para registrar este valor.")
        serializer.save(registrado_por=self.request.user)


class AjusteCostoViewSet(BaseModelViewSet):
    """Alta de correcciones históricas; se leen dentro del hecho costeable."""

    queryset = AjusteCosto.objects.none()
    serializer_class = AjusteCostoSerializer
    permission_classes = [IsAuthenticated, PuedeCorregirCosto]
    http_method_names = ["post", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ajuste = registrar_ajuste_costo(
            serializer.validated_data["imputacion"],
            serializer.validated_data["importe"],
            serializer.validated_data["motivo"],
            request.user,
        )
        return Response(self.get_serializer(ajuste).data, status=status.HTTP_201_CREATED)


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
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "ciudadano", "caso", "area")
    ordering = ("-ocurrida_en", "-id")
    ordering_fields = ("id", "ocurrida_en")

    @action(
        detail=True,
        methods=["post"],
        url_path="corregir-snapshot",
        permission_classes=[IsAuthenticated, PuedeCorregirCosto],
    )
    def corregir_snapshot(self, request, pk=None):
        """Reconstruye sólo un snapshot fallido, con autorización y motivo."""
        serializer = CorreccionSnapshotCosteoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            correccion = corregir_snapshot_componentes(
                pk,
                serializer.validated_data["motivo"],
                request.user,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error
        return Response(
            CorreccionSnapshotCosteoSerializer(correccion).data,
            status=status.HTTP_201_CREATED,
        )

    def create(self, request, *args, **kwargs):
        # El hecho nace sólo al completar la atención en el motor clínico.
        raise MethodNotAllowed("POST")

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
