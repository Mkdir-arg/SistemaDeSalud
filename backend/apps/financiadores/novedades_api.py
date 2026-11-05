"""Interfaz propia de propuestas; no reutiliza confirmación de importaciones."""
from collections.abc import Mapping

from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import novedades as servicio
from .models import Importacion


class EntradaEstricta(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["La solicitud contiene campos no admitidos."]})
        return super().to_internal_value(data)


class PropuestaNovedad(EntradaEstricta):
    clave = serializers.UUIDField()
    afiliado = serializers.IntegerField(min_value=1)
    fuente = serializers.CharField(max_length=80, trim_whitespace=False)
    referencia = serializers.CharField(max_length=120, allow_blank=True, required=False, default="", trim_whitespace=False)
    codigo = serializers.CharField(max_length=80, allow_blank=True, required=False, default="", trim_whitespace=False)
    fecha_informada = serializers.DateField(allow_null=True, required=False, default=None)
    descripcion = serializers.CharField(max_length=2000, trim_whitespace=False)
    motivo = serializers.CharField(max_length=255)
    rectifica = serializers.IntegerField(min_value=1, allow_null=True, required=False, default=None)

    def validate(self, attrs):
        for campo in ("fuente", "descripcion"):
            if not attrs[campo].strip():
                raise serializers.ValidationError({campo: "No puede contener solamente espacios."})
        return attrs


class DecisionNovedad(EntradaEstricta):
    revision = serializers.IntegerField(min_value=1)
    revision_padron = serializers.IntegerField(min_value=1)
    accion = serializers.ChoiceField(choices=["conciliar", "descartar"])
    motivo = serializers.CharField(max_length=255)
    confirmar_conflictos = serializers.BooleanField(required=False, default=False)


class NovedadesMixin:
    @extend_schema(methods=["GET"], responses=OpenApiTypes.OBJECT)
    @extend_schema(methods=["POST"], request=PropuestaNovedad, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get", "post"])
    def novedades(self, request, pk=None):
        org = self.organizacion(escritura=request.method == "POST")
        if request.method == "POST":
            datos = PropuestaNovedad(data=request.data)
            datos.is_valid(raise_exception=True)
            obj, nueva = servicio.registrar(financiador=org, usuario=request.user, **datos.validated_data)
            return Response(servicio.presentar(obj), status=201 if nueva else 200)
        qs = Importacion.objects.filter(financiador=org, tipo=servicio.TIPO,
                                         version=servicio.VERSION).order_by("-pk")
        if request.query_params.get("estado"):
            estado = serializers.ChoiceField(choices=servicio.ESTADOS).run_validation(request.query_params["estado"])
            qs = qs.filter(estado=estado)
        if request.query_params.get("afiliado"):
            afiliado = serializers.IntegerField(min_value=1).run_validation(request.query_params["afiliado"])
            qs = qs.filter(resumen__afiliado=afiliado)
        pagina = self.paginate_queryset(qs)
        return self.get_paginated_response([servicio.resumir(obj) for obj in pagina])

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"], url_path=r"novedades/(?P<novedad_id>\d+)")
    def novedad_detalle(self, request, pk=None, novedad_id=None):
        org = self.organizacion()
        return Response(servicio.presentar(servicio.consultar(financiador=org, novedad_id=novedad_id)))

    @extend_schema(request=DecisionNovedad, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path=r"novedades/(?P<novedad_id>\d+)/resolver")
    def novedad_resolver(self, request, pk=None, novedad_id=None):
        org = self.organizacion(escritura=True)
        datos = DecisionNovedad(data=request.data)
        datos.is_valid(raise_exception=True)
        obj = servicio.resolver(financiador=org, usuario=request.user,
            novedad_id=novedad_id, **datos.validated_data)
        return Response(servicio.presentar(obj))
