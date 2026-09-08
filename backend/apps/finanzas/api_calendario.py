"""API de configuración e indicaciones del calendario de gastos esperados."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common import BaseModelViewSet
from .calendario import calendario_mensual, en_alcance_financiero
from .models import ConcesionFinanciera, ExpectativaGasto, IndicacionCargaGasto
from .services import indicar_carga_esperada, registrar_expectativa_gasto
from .views import PuedeRegistrarGastos, PuedeVerGastos


class PeriodoMensualSerializer(serializers.Serializer):
    periodo_economico = serializers.DateField()

    def validate_periodo_economico(self, valor):
        if valor.day != 1:
            raise serializers.ValidationError("Indicá el primer día del mes (AAAA-MM-01).")
        return valor


class NuevaIndicacionSerializer(PeriodoMensualSerializer):
    estado = serializers.ChoiceField(choices=IndicacionCargaGasto.Estado.choices)


class IndicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IndicacionCargaGasto
        fields = ["id", "expectativa", "periodo_economico", "estado", "registrado_por", "registrado"]
        read_only_fields = fields


class ExpectativaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpectativaGasto
        fields = [
            "id", "concepto", "institucion", "area", "vigente_desde", "vigente_hasta",
            "sensible", "reemplaza", "motivo_correccion", "registrado_por", "registrado",
        ]
        read_only_fields = ["id", "sensible", "registrado_por", "registrado"]


class CalendarioSerializer(ExpectativaSerializer):
    indicacion_id = serializers.IntegerField(read_only=True, allow_null=True)
    estado_carga = serializers.CharField(read_only=True)
    indicacion_registrada = serializers.DateTimeField(read_only=True, allow_null=True)
    gastos_pendientes = serializers.IntegerField(read_only=True)
    gastos_aprobados = serializers.IntegerField(read_only=True)

    class Meta(ExpectativaSerializer.Meta):
        fields = ExpectativaSerializer.Meta.fields + [
            "indicacion_id", "estado_carga", "indicacion_registrada",
            "gastos_pendientes", "gastos_aprobados",
        ]
        read_only_fields = fields


class PuedeConfigurarGastosEsperados(PuedeRegistrarGastos):
    accion = ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS


class ExpectativaGastoViewSet(BaseModelViewSet):
    queryset = ExpectativaGasto.objects.select_related("concepto", "institucion", "area")
    serializer_class = ExpectativaSerializer
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area", "concepto")
    ordering_fields = ("vigente_desde", "id")

    def get_permissions(self):
        permiso = PuedeConfigurarGastosEsperados if self.action in {"create", "indicar"} else PuedeVerGastos
        return [IsAuthenticated(), permiso()]

    def get_queryset(self):
        accion = (
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS
            if self.action == "indicar" else ConcesionFinanciera.Accion.VER_GASTOS
        )
        return en_alcance_financiero(super().get_queryset(), self.request.user, accion)

    def perform_create(self, serializer):
        try:
            serializer.instance = registrar_expectativa_gasto(
                registrado_por=self.request.user, **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(getattr(error, "message_dict", error.messages)) from error

    @action(detail=True, methods=["post"])
    def indicar(self, request, pk=None):
        expectativa = self.get_object()
        entrada = NuevaIndicacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            indicacion = indicar_carga_esperada(
                expectativa.pk, registrado_por=request.user, **entrada.validated_data
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(getattr(error, "message_dict", error.messages)) from error
        return Response(IndicacionSerializer(indicacion).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def indicaciones(self, request, pk=None):
        expectativa = self.get_object()
        historial = expectativa.indicaciones_carga.order_by("-registrado", "-id")
        pagina = self.paginate_queryset(historial)
        if pagina is not None:
            return self.get_paginated_response(IndicacionSerializer(pagina, many=True).data)
        return Response(IndicacionSerializer(historial, many=True).data)

    @action(detail=False, methods=["get"])
    def calendario(self, request):
        entrada = PeriodoMensualSerializer(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        periodo = entrada.validated_data["periodo_economico"]
        filas = self.filter_queryset(calendario_mensual(self.get_queryset(), request.user, periodo))
        pagina = self.paginate_queryset(filas)
        datos = CalendarioSerializer(pagina if pagina is not None else filas, many=True).data
        respuesta = self.get_paginated_response(datos) if pagina is not None else Response({"results": datos})
        respuesta.data.update(
            periodo_economico=periodo.isoformat(),
            limites="Sólo expectativas configuradas y gastos visibles según tus permisos. "
            "Carga completa no implica aprobación, distribución ni cobertura de gastos no declarados.",
        )
        return respuesta
