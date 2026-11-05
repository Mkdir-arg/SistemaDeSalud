"""API administrativa de borradores; no ofrece aprobación ni activación."""
from collections.abc import Mapping
from datetime import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Afiliado
from .derechos_borrador import BorradorDerechos, MAX_DIAS_CORRIDOS
from .borradores_derechos import consultar_borradores, guardar_borradores, previsualizar_propuesta, consultar_historial_borradores


class EntradaControlada(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            desconocidos = set(data) - set(self.fields)
            if desconocidos:
                raise serializers.ValidationError({c: "Campo no admitido." for c in desconocidos})
        return super().to_internal_value(data)


class DescriptorBorradorSerializer(EntradaControlada):
    codigo = serializers.CharField(max_length=60, trim_whitespace=False)
    version = serializers.IntegerField(min_value=1)
    fuente = serializers.CharField(max_length=255, trim_whitespace=False)
    regimen = serializers.ChoiceField(choices=Afiliado._meta.get_field("regimen").choices)
    plan_id = serializers.IntegerField(min_value=1, allow_null=True)
    desde = serializers.DateField()
    hasta = serializers.DateField(allow_null=True, required=False, default=None)
    plazo_dias_corridos = serializers.IntegerField(min_value=0, max_value=MAX_DIAS_CORRIDOS, allow_null=True, required=False, default=None)

    def to_representation(self, instance):
        datos = super().to_representation(instance)
        if datos.get("plazo_dias_corridos") is None:
            datos.pop("plazo_dias_corridos", None)
        return datos


class PropuestaBorradoresSerializer(EntradaControlada):
    propuesta = DescriptorBorradorSerializer(many=True)
    motivo = serializers.CharField(max_length=255)
    regimen = serializers.ChoiceField(choices=Afiliado._meta.get_field("regimen").choices)
    plan_id = serializers.IntegerField(min_value=1, allow_null=True)
    fecha = serializers.DateField()


class ListaBorradoresSerializer(serializers.Serializer):
    borradores = DescriptorBorradorSerializer(many=True)


class RegistroBorradorSerializer(serializers.Serializer):
    regla = DescriptorBorradorSerializer()
    creado_por_id = serializers.IntegerField()
    creado = serializers.DateTimeField(default_timezone=timezone.utc)
    motivo = serializers.CharField()


class HistorialBorradoresSerializer(serializers.Serializer):
    historial = RegistroBorradorSerializer(many=True)


class VistaBorradoresSerializer(serializers.Serializer):
    coincidencias = DescriptorBorradorSerializer(many=True)
    conflicto = serializers.BooleanField()


class ResultadoBorradoresSerializer(serializers.Serializer):
    nuevas = DescriptorBorradorSerializer(many=True)
    antes = VistaBorradoresSerializer()
    despues = VistaBorradoresSerializer()


def _leer_propuesta(request, financiador_id):
    entrada = PropuestaBorradoresSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    datos = dict(entrada.validated_data)
    try:
        propuesta = tuple(BorradorDerechos(financiador_id=financiador_id, **fila)
                          for fila in datos.pop("propuesta"))
    except ValueError as exc:
        raise serializers.ValidationError(str(exc)) from exc
    return {"propuesta": propuesta, **datos}


class BorradoresDerechosMixin:
    @extend_schema(methods=["GET"], responses=ListaBorradoresSerializer)
    @extend_schema(methods=["POST"], request=PropuestaBorradoresSerializer, responses=ResultadoBorradoresSerializer)
    @action(detail=True, methods=["get", "post"], url_path="borradores-derechos")
    def borradores_derechos(self, request, pk=None):
        org = self.organizacion(admin=request.method == "POST")
        if request.method == "GET":
            versiones = consultar_borradores(usuario=request.user, financiador_id=org.pk)
            return Response(ListaBorradoresSerializer({"borradores": versiones}).data)
        resultado = guardar_borradores(usuario=request.user, financiador_id=org.pk,
                                       **_leer_propuesta(request, org.pk))
        return Response(ResultadoBorradoresSerializer(resultado).data)

    @extend_schema(request=PropuestaBorradoresSerializer, responses=ResultadoBorradoresSerializer)
    @action(detail=True, methods=["post"], url_path="borradores-derechos/previsualizar")
    def previsualizar_borradores(self, request, pk=None):
        org = self.organizacion(admin=True)
        resultado = previsualizar_propuesta(usuario=request.user, financiador_id=org.pk,
                                           **_leer_propuesta(request, org.pk))
        return Response(ResultadoBorradoresSerializer(resultado).data)

    @extend_schema(responses=HistorialBorradoresSerializer)
    @action(detail=True, methods=["get"], url_path="borradores-derechos/historial")
    def historial_borradores(self, request, pk=None):
        org = self.organizacion()
        historial = consultar_historial_borradores(usuario=request.user, financiador_id=org.pk)
        return Response(HistorialBorradoresSerializer({"historial": historial}).data)
