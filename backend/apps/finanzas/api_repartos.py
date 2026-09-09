"""API mínima de configuración y explicación del reparto por actividad."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.common import BaseModelViewSet
from apps.instituciones.models import Area, Institucion

from .auditoria import AuditaLecturaFinanciera
from .models import (
    CoberturaActividadCosteable,
    ConceptoGasto,
    ConcesionFinanciera,
    ReglaRepartoActividad,
    RepartoGasto,
)
from .permisos import concesiones_financieras_de, tiene_concesion_financiera
from .services import registrar_cobertura_actividad, registrar_regla_reparto, resumen_actividad_reparto


class PuedeConfigurarRepartos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario, ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
                ).exists()
            )
        )


class PuedeVerRepartos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(usuario, ConcesionFinanciera.Accion.VER_GASTOS).exists()
            )
        )


def _alcance(queryset, usuario, accion, *, sensible_path=None):
    if usuario.is_superuser:
        return queryset
    alcance = Q(pk__in=[])
    concesiones = concesiones_financieras_de(usuario, accion)
    for institucion_id, permite_sensibles in concesiones.filter(todas_las_areas=True).values_list(
        "membresia__institucion_id", "permite_sensibles"
    ):
        scope = Q(institucion_id=institucion_id)
        if sensible_path and not permite_sensibles:
            scope &= ~Q(**{sensible_path: True})
        alcance |= scope
    for institucion_id, area_id, permite_sensibles in concesiones.filter(todas_las_areas=False).values_list(
        "membresia__institucion_id", "areas__id", "permite_sensibles"
    ):
        if area_id is not None:
            scope = Q(institucion_id=institucion_id, area_id=area_id)
            if sensible_path and not permite_sensibles:
                scope &= ~Q(**{sensible_path: True})
            alcance |= scope
    return queryset.filter(alcance).distinct()


def _filtrar_vigencia(queryset, valor):
    if valor in {"1", "true", "True"}:
        return queryset.filter(reemplazado_por__isnull=True)
    if valor in {"0", "false", "False"}:
        return queryset.filter(reemplazado_por__isnull=False)
    return queryset


class VerificacionActividadEntradaSerializer(serializers.Serializer):
    institucion = serializers.PrimaryKeyRelatedField(queryset=Institucion.objects.all())
    area = serializers.PrimaryKeyRelatedField(queryset=Area.objects.all())
    periodo_economico = serializers.DateField()
    concepto = serializers.PrimaryKeyRelatedField(
        queryset=ConceptoGasto.objects.all(), required=False, allow_null=True,
    )

    def validate(self, attrs):
        if attrs["periodo_economico"].day != 1:
            raise serializers.ValidationError("Indicá el primer día del mes (AAAA-MM-01).")
        if attrs["area"].institucion_id != attrs["institucion"].id:
            raise serializers.ValidationError("El área debe pertenecer a la institución elegida.")
        concepto = attrs.get("concepto")
        if concepto and concepto.institucion_id != attrs["institucion"].id:
            raise serializers.ValidationError("El concepto debe pertenecer a la institución elegida.")
        return attrs


class CoberturaActividadSerializer(serializers.ModelSerializer):
    sensible = serializers.SerializerMethodField()
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)
    confirmacion_operativa = serializers.BooleanField(write_only=True)

    class Meta:
        model = CoberturaActividadCosteable
        fields = [
            "id", "institucion", "area", "area_nombre", "vigente_desde", "vigente_hasta",
            "reemplaza", "motivo_correccion", "registrado_por", "registrado", "sensible",
            "confirmacion_operativa",
        ]
        read_only_fields = ["id", "registrado_por", "registrado", "sensible"]

    @staticmethod
    def get_sensible(obj) -> bool:
        return False

    def create(self, validated_data):
        confirmacion_operativa = validated_data.pop("confirmacion_operativa")
        try:
            return registrar_cobertura_actividad(
                registrado_por=self.context["request"].user,
                confirmacion_operativa=confirmacion_operativa,
                **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                getattr(error, "message_dict", error.messages)
            ) from error


class ReglaRepartoSerializer(serializers.ModelSerializer):
    concepto_nombre = serializers.CharField(source="concepto.nombre", read_only=True)
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)

    class Meta:
        model = ReglaRepartoActividad
        fields = [
            "id", "concepto", "concepto_nombre", "institucion", "area", "area_nombre",
            "vigente_desde", "vigente_hasta",
            "sensible", "reemplaza", "motivo_correccion", "registrado_por", "registrado",
        ]
        read_only_fields = ["id", "sensible", "registrado_por", "registrado"]

    def create(self, validated_data):
        try:
            return registrar_regla_reparto(
                registrado_por=self.context["request"].user, **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                getattr(error, "message_dict", error.messages)
            ) from error


class RepartoGastoSerializer(serializers.ModelSerializer):
    institucion = serializers.IntegerField(source="gasto.institucion_id", read_only=True)
    area = serializers.IntegerField(source="gasto.area_id", read_only=True)
    area_nombre = serializers.CharField(source="gasto.area.nombre", read_only=True, default=None)
    concepto = serializers.IntegerField(source="gasto.concepto_id", read_only=True)
    concepto_nombre = serializers.CharField(source="gasto.concepto.nombre", read_only=True)
    periodo_economico = serializers.DateField(source="gasto.periodo_economico", read_only=True)
    sensible = serializers.BooleanField(source="gasto.sensible", read_only=True)
    atribuciones = serializers.IntegerField(source="atribuciones.count", read_only=True)
    vigente = serializers.SerializerMethodField()

    class Meta:
        model = RepartoGasto
        fields = [
            "id", "gasto", "concepto", "concepto_nombre", "institucion", "area", "area_nombre",
            "periodo_economico",
            "sensible", "regla", "cobertura", "version", "estado", "motivo",
            "importe_fuente_centavos", "importe_ajustes_centavos", "saldo_centavos",
            "saldo_no_atribuido_centavos", "atribuciones", "reemplaza", "vigente", "calculado",
        ]
        read_only_fields = fields

    @staticmethod
    def get_vigente(obj) -> bool:
        try:
            obj.reemplazado_por
        except ObjectDoesNotExist:
            return True
        return False


class CoberturaActividadViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = CoberturaActividadCosteable.objects.select_related("institucion", "area", "reemplaza")
    serializer_class = CoberturaActividadSerializer
    permission_classes = [IsAuthenticated, PuedeConfigurarRepartos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        queryset = _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        )
        return _filtrar_vigencia(queryset, self.request.query_params.get("vigente"))

    @action(detail=False, methods=["get"])
    def verificacion(self, request):
        entrada = VerificacionActividadEntradaSerializer(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        institucion = entrada.validated_data["institucion"]
        area = entrada.validated_data["area"]
        concepto = entrada.validated_data.get("concepto")
        sensible = bool(concepto and concepto.sensible)
        if not tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            institucion.id,
            area.id,
            sensible=sensible,
        ):
            raise PermissionDenied("No tenés autorización para verificar este reparto.")
        incluir_sensibles = sensible or tiene_concesion_financiera(
            request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            institucion.id,
            area.id,
            sensible=True,
        )
        return Response(resumen_actividad_reparto(
            institucion_id=institucion.id,
            area_id=area.id,
            periodo=entrada.validated_data["periodo_economico"],
            concepto_id=concepto.id if concepto else None,
            incluir_sensibles=incluir_sensibles,
        ))


class ReglaRepartoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = ReglaRepartoActividad.objects.select_related(
        "concepto", "institucion", "area", "reemplaza",
    )
    serializer_class = ReglaRepartoSerializer
    permission_classes = [IsAuthenticated, PuedeConfigurarRepartos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area", "concepto", "sensible")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        queryset = _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            sensible_path="sensible",
        )
        return _filtrar_vigencia(queryset, self.request.query_params.get("vigente"))


class RepartoGastoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = RepartoGasto.objects.select_related(
        "gasto", "gasto__concepto", "gasto__area", "regla", "cobertura", "reemplaza",
        "reemplazado_por",
    ).prefetch_related("atribuciones")
    serializer_class = RepartoGastoSerializer
    permission_classes = [IsAuthenticated, PuedeVerRepartos]
    institucion_path = "gasto__institucion"
    http_method_names = ["get", "head", "options"]
    filter_fields = (
        "gasto", "gasto__institucion", "gasto__area", "gasto__periodo_economico",
        "estado", "motivo",
    )
    ordering_fields = ("calculado", "version", "id")

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        if usuario.is_superuser:
            return _filtrar_vigencia(qs, self.request.query_params.get("vigente"))
        alcance = Q(pk__in=[])
        concesiones = concesiones_financieras_de(usuario, ConcesionFinanciera.Accion.VER_GASTOS)
        for institucion_id, permite_sensibles in concesiones.filter(todas_las_areas=True).values_list(
            "membresia__institucion_id", "permite_sensibles"
        ):
            scope = Q(gasto__institucion_id=institucion_id)
            if not permite_sensibles:
                scope &= ~Q(gasto__sensible=True)
            alcance |= scope
        for institucion_id, area_id, permite_sensibles in concesiones.filter(todas_las_areas=False).values_list(
            "membresia__institucion_id", "areas__id", "permite_sensibles"
        ):
            if area_id is not None:
                scope = Q(gasto__institucion_id=institucion_id, gasto__area_id=area_id)
                if not permite_sensibles:
                    scope &= ~Q(gasto__sensible=True)
                alcance |= scope
        qs = qs.filter(alcance).distinct()
        return _filtrar_vigencia(qs, self.request.query_params.get("vigente"))
