"""Simulación de consulta: recupera la versión persistida, sin escribir."""
from datetime import date
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Afiliado
from .borradores_api import EntradaControlada, DescriptorBorradorSerializer
from .borradores_derechos import consultar_borradores
from .simulacion_plazo import simular_plazo


class IdentidadReglaSerializer(EntradaControlada):
    codigo = serializers.CharField(max_length=60, trim_whitespace=False)
    version = serializers.IntegerField(min_value=1)
    regimen = serializers.ChoiceField(choices=Afiliado._meta.get_field("regimen").choices)
    plan_id = serializers.IntegerField(min_value=1, allow_null=True)


class EntradaSimulacionPlazoSerializer(EntradaControlada):
    regla = IdentidadReglaSerializer()
    dias_corridos = serializers.IntegerField(min_value=0, max_value=(date.max - date.min).days)
    fecha = serializers.DateField()
    referencia = serializers.DateField(allow_null=True, required=False, default=None)
    evidencia = serializers.CharField(max_length=255, allow_null=True, required=False, default=None, trim_whitespace=False)


class SalidaSimulacionPlazoSerializer(serializers.Serializer):
    regla = DescriptorBorradorSerializer()
    dias_corridos = serializers.IntegerField()
    financiador_id = serializers.IntegerField()
    regimen = serializers.CharField()
    plan_id = serializers.IntegerField(allow_null=True)
    fecha = serializers.DateField()
    referencia = serializers.DateField(allow_null=True)
    evidencia = serializers.CharField(allow_null=True)
    estado = serializers.ChoiceField(choices=["calculado", "requiere_evidencia", "sin_coincidencia"])
    limite = serializers.DateField(allow_null=True)
    relacion = serializers.ChoiceField(choices=["antes", "en", "despues"], allow_null=True)


class SimulacionPlazoMixin:
    @extend_schema(request=EntradaSimulacionPlazoSerializer, responses=SalidaSimulacionPlazoSerializer)
    @action(detail=True, methods=["post"], url_path="borradores-derechos/simular-plazo")
    def simular_plazo_derechos(self, request, pk=None):
        org = self.organizacion()
        entrada = EntradaSimulacionPlazoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        identidad = datos.pop("regla")
        versiones = [r for r in consultar_borradores(usuario=request.user, financiador_id=org.pk)
                     if all(getattr(r, campo) == valor for campo, valor in identidad.items())]
        if len(versiones) != 1:
            raise serializers.ValidationError("La versión no está disponible en este financiador. Consultá nuevamente.")
        regla = versiones[0]
        try:
            resultado = simular_plazo(regla, financiador_id=org.pk, regimen=regla.regimen,
                                       plan_id=regla.plan_id, **datos)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(SalidaSimulacionPlazoSerializer(resultado).data)
