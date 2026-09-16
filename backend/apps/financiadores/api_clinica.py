"""Acciones de cobertura bajo el ámbito del caso/paciente que se está operando."""
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.auditoria.mixins import registrar_acceso
from apps.finanzas.models import Prestacion
from . import clinica
from .models import Afiliado
from .views import datos


class ContextoPasoSerializer(serializers.Serializer):
    nodo = serializers.IntegerField(allow_null=True)
    actualizado = serializers.CharField(max_length=80)


def respuesta_privada(data, status=200):
    return Response(data, status=status, headers={"Cache-Control": "private, no-store"})


class CoberturaCasoMixin:
    def handle_exception(self, exc):
        if (getattr(self, "action", "") or "").startswith("cobertura") and isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
        return super().handle_exception(exc)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"])
    def cobertura(self, request, pk=None):
        caso = self.get_object()
        data = clinica.resumen_caso(caso, request.user)
        registrar_acceso(request, "detalle", "AfiliacionCaso", ciudadano=caso.ciudadano,
            objeto_id=caso.pk, detalle="Cobertura del caso", institucion_id=caso.institucion_id)
        return respuesta_privada(data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path="cobertura-afiliacion")
    def cobertura_afiliacion(self, request, pk=None):
        caso = self.get_object()
        d = datos(request, {"contexto": ContextoPasoSerializer(),
            "afiliado": serializers.PrimaryKeyRelatedField(queryset=Afiliado.objects.all(), allow_null=True, required=False),
            "particular": serializers.BooleanField(default=False),
            "declaracion": serializers.CharField(max_length=160, allow_blank=True, default=""),
            "motivo": serializers.CharField(max_length=255)})
        obj = clinica.seleccionar_en_paso(caso=caso, usuario=request.user, **d)
        return respuesta_privada(clinica.afiliacion_resumida(obj), status=201)

    def _entrada_cobertura(self, request, confirmar=False):
        campos = {"contexto": ContextoPasoSerializer(),
            "prestacion": serializers.PrimaryKeyRelatedField(queryset=Prestacion.objects.all())}
        if confirmar:
            campos.update(firma=serializers.CharField(max_length=10000),
                clave=serializers.UUIDField(), acepta=serializers.BooleanField(default=False),
                no_realizada=serializers.BooleanField(default=False))
        return datos(request, campos)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path="cobertura-evaluar")
    def cobertura_evaluar(self, request, pk=None):
        caso = self.get_object()
        d = self._entrada_cobertura(request)
        return respuesta_privada(clinica.cotizar_en_paso(caso=caso, usuario=request.user, **d))

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"], url_path="cobertura-confirmar")
    def cobertura_confirmar(self, request, pk=None):
        caso = self.get_object()
        d = self._entrada_cobertura(request, confirmar=True)
        obj = clinica.confirmar_en_paso(caso=caso, usuario=request.user, **d)
        return respuesta_privada(clinica.reserva_resumida(obj), status=201)


def historial_paciente(view, request, ciudadano):
    qs = clinica.historial_del_paciente(request.user, ciudadano)
    pagina = view.paginate_queryset(qs)
    data = [{**clinica.afiliacion_resumida(a), "flujo_titulo": a.caso.version.flujo.titulo} for a in pagina]
    registrar_acceso(request, "detalle", "AfiliacionCaso", ciudadano=ciudadano,
        objeto_id=ciudadano.pk, detalle="Historial de afiliaciones por caso", resultados=len(data))
    response = view.get_paginated_response(data)
    response["Cache-Control"] = "private, no-store"
    return response
