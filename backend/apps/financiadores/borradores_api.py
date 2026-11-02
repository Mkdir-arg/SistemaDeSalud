"""API administrativa de borradores; no ofrece aprobación ni activación."""
from collections.abc import Mapping
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Afiliado
from .derechos_borrador import BorradorDerechos
from .borradores_derechos import consultar_borradores, guardar_borradores


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


class PropuestaBorradoresSerializer(EntradaControlada):
    propuesta = DescriptorBorradorSerializer(many=True)
    motivo = serializers.CharField(max_length=255)
    regimen = serializers.ChoiceField(choices=Afiliado._meta.get_field("regimen").choices)
    plan_id = serializers.IntegerField(min_value=1, allow_null=True)
    fecha = serializers.DateField()


class ListaBorradoresSerializer(serializers.Serializer):
    borradores = DescriptorBorradorSerializer(many=True)


class VistaBorradoresSerializer(serializers.Serializer):
    coincidencias = DescriptorBorradorSerializer(many=True)
    conflicto = serializers.BooleanField()


class ResultadoBorradoresSerializer(serializers.Serializer):
    nuevas = DescriptorBorradorSerializer(many=True)
    antes = VistaBorradoresSerializer()
    despues = VistaBorradoresSerializer()


class BorradoresDerechosMixin:
    @extend_schema(methods=["GET"], responses=ListaBorradoresSerializer)
    @extend_schema(methods=["POST"], request=PropuestaBorradoresSerializer, responses=ResultadoBorradoresSerializer)
    @action(detail=True, methods=["get", "post"], url_path="borradores-derechos")
    def borradores_derechos(self, request, pk=None):
        org = self.organizacion(admin=request.method == "POST")
        if request.method == "GET":
            versiones = consultar_borradores(usuario=request.user, financiador_id=org.pk)
            return Response(ListaBorradoresSerializer({"borradores": versiones}).data)
        entrada = PropuestaBorradoresSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        try:
            propuesta = tuple(BorradorDerechos(financiador_id=org.pk, **fila)
                              for fila in datos.pop("propuesta"))
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        resultado = guardar_borradores(usuario=request.user, financiador_id=org.pk,
                                       propuesta=propuesta, **datos)
        return Response(ResultadoBorradoresSerializer(resultado).data)
