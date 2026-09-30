"""API de la simulación: catálogo, inicio y salida. Solo para superusuarios.

Se llama sin `X-HEN-Simulacion`: durante una simulación `request.user` es la
cuenta de referencia, que no es superusuario, así que desde adentro de una
simulación no se puede abrir otra ni leer el catálogo.
"""
from django.core.exceptions import ValidationError as ErrorDeModelo
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.auditoria.mixins import _ip

from .models import Ambito, SesionSimulacion
from .perfiles import catalogo, datos_de_sesion, iniciar


class SoloSuperusuario(BasePermission):
    message = "Solo un superusuario puede simular perfiles."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_superuser)


class IniciarSimulacionSerializer(serializers.Serializer):
    ambito = serializers.ChoiceField(choices=Ambito.choices)
    rol = serializers.CharField(max_length=20)
    institucion = serializers.IntegerField(min_value=1, required=False)
    financiador = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        ambito = attrs["ambito"]
        if ambito == Ambito.INSTITUCION and not attrs.get("institucion"):
            raise serializers.ValidationError({"institucion": "Indicá la institución que se simula."})
        if ambito == Ambito.FINANCIADOR and not attrs.get("financiador"):
            raise serializers.ValidationError({"financiador": "Indicá el financiador que se simula."})
        return attrs


def _ambito_de_consulta(params):
    institucion = (params.get("institucion") or "").strip()
    financiador = (params.get("financiador") or "").strip()
    if institucion and financiador:
        raise ValidationError("Elegí una institución o un financiador, no ambos.")
    for valor in (institucion, financiador):
        if valor and not valor.isdigit():
            raise ValidationError("Indicá un ámbito válido.")
    if institucion:
        return Ambito.INSTITUCION, int(institucion), None
    if financiador:
        return Ambito.FINANCIADOR, None, int(financiador)
    return Ambito.PLATAFORMA, None, None


class SimulacionViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, SoloSuperusuario]
    queryset = SesionSimulacion.objects.none()
    serializer_class = IniciarSimulacionSerializer

    @extend_schema(
        summary="Perfiles simulables de un ámbito",
        description="Sin parámetros, los perfiles de plataforma. Cada perfil indica si tiene cuenta preparada y, si no, el motivo.",
        parameters=[
            OpenApiParameter("institucion", int, required=False),
            OpenApiParameter("financiador", int, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    @action(detail=False, methods=["get"])
    def catalogo(self, request):
        ambito, institucion, financiador = _ambito_de_consulta(request.query_params)
        return Response({
            "ambito": ambito,
            "institucion": institucion,
            "financiador": financiador,
            "perfiles": catalogo(ambito, institucion, financiador),
        })

    @extend_schema(summary="Inicia una simulación", responses={201: OpenApiTypes.OBJECT})
    def create(self, request):
        entrada = self.get_serializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        d = entrada.validated_data
        try:
            sesion = iniciar(
                request.user, d["ambito"], d["rol"],
                institucion_id=d.get("institucion"), financiador_id=d.get("financiador"), ip=_ip(request),
            )
        except ErrorDeModelo as error:
            raise ValidationError({"detail": error.messages}) from error
        return Response(datos_de_sesion(sesion), status=status.HTTP_201_CREATED)

    @extend_schema(summary="Termina una simulación", request=None, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["post"])
    def finalizar(self, request, pk=None):
        try:
            sesion = SesionSimulacion.objects.select_related(
                "cuenta", "superusuario", "institucion", "financiador",
            ).get(pk=pk, superusuario=request.user)
        except (SesionSimulacion.DoesNotExist, ErrorDeModelo, ValueError):
            raise NotFound("No existe esa simulación.") from None
        motivo = request.data.get("motivo") if isinstance(request.data, dict) else None
        sesion.finalizar(SesionSimulacion.Fin.CIERRE if motivo == "cierre" else SesionSimulacion.Fin.SALIDA)
        return Response(datos_de_sesion(sesion))
