"""API mínima de configuración y explicación del reparto por actividad."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.common import BaseModelViewSet

from .auditoria import AuditaLecturaFinanciera
from .models import CoberturaActividadCosteable, ConcesionFinanciera, ReglaRepartoActividad, RepartoGasto
from .permisos import concesiones_financieras_de
from .services import registrar_cobertura_actividad, registrar_regla_reparto


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


class CoberturaActividadSerializer(serializers.ModelSerializer):
    sensible = serializers.SerializerMethodField()

    class Meta:
        model = CoberturaActividadCosteable
        fields = [
            "id", "institucion", "area", "vigente_desde", "vigente_hasta",
            "reemplaza", "motivo_correccion", "registrado_por", "registrado", "sensible",
        ]
        read_only_fields = ["id", "registrado_por", "registrado", "sensible"]

    @staticmethod
    def get_sensible(obj) -> bool:
        return False

    def create(self, validated_data):
        try:
            return registrar_cobertura_actividad(
                registrado_por=self.context["request"].user, **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                getattr(error, "message_dict", error.messages)
            ) from error


class ReglaRepartoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglaRepartoActividad
        fields = [
            "id", "concepto", "institucion", "area", "vigente_desde", "vigente_hasta",
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
    area_nombre = serializers.CharField(source="gasto.area.nombre", read_only=True)
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
        return _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        )


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
        return _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            sensible_path="sensible",
        )


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
            return qs
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
        return qs.filter(alcance).distinct()
