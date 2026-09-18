"""Resumen agregado de costos por atención: mismas fuentes y permisos que el listado."""
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.instituciones.models import Area

from .auditoria import AuditaLecturaFinanciera
from .models import ConcesionFinanciera, HechoAtencionCosteable
from .permisos import (
    concesiones_financieras_de,
    hechos_en_alcance_financiero,
    instituciones_admin_financiero,
    tiene_concesion_financiera,
)
from .reportes_costos import rango_mes_local, resumir_costos


class ContextoCostos(serializers.Serializer):
    institucion = serializers.IntegerField(min_value=1)
    periodo_economico = serializers.DateField()
    area = serializers.IntegerField(min_value=1, required=False)
    area_sin_asignar = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if attrs["periodo_economico"].day != 1:
            raise serializers.ValidationError("Indicá el primer día del mes económico.")
        if attrs.get("area") and attrs["area_sin_asignar"]:
            raise serializers.ValidationError("Elegí un área o las atenciones institucionales sin área, no ambas.")
        return attrs


class ReporteCostosViewSet(AuditaLecturaFinanciera, viewsets.GenericViewSet):
    """Totales y desgloses del mes; nunca expone ciudadano, caso ni composición."""

    permission_classes = [IsAuthenticated]
    queryset = HechoAtencionCosteable.objects.none()
    serializer_class = ContextoCostos
    http_method_names = ["get", "head", "options"]

    def fuentes(self, request):
        entrada = ContextoCostos(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        ctx = entrada.validated_data
        usuario = request.user
        accion = ConcesionFinanciera.Accion.VER_COSTOS
        inst = ctx["institucion"]
        autoriza = usuario.is_superuser or instituciones_admin_financiero(usuario, accion).filter(
            institucion_id=inst,
        ).exists() or concesiones_financieras_de(usuario, accion).filter(membresia__institucion_id=inst).exists()
        if not usuario.is_active or not autoriza:
            raise PermissionDenied("No tenés autorización para consultar costos de esta institución.")
        if ("area" in ctx or ctx["area_sin_asignar"]) and not tiene_concesion_financiera(
            usuario, accion, inst, ctx.get("area"),
        ):
            raise PermissionDenied("No tenés autorización para consultar costos de esta área.")
        if ctx.get("area") and not Area.objects.filter(pk=ctx["area"], institucion_id=inst).exists():
            raise serializers.ValidationError("El área no pertenece a la institución elegida.")
        desde, hasta = rango_mes_local(ctx["periodo_economico"])
        hechos = hechos_en_alcance_financiero(HechoAtencionCosteable.objects.all(), usuario).filter(
            institucion_id=inst, ocurrida_en__gte=desde, ocurrida_en__lt=hasta,
        )
        # El alcance financiero se resuelve sobre el área de origen; el resumen
        # agrupa por el mismo campo para no mezclar permisos y presentación.
        if ctx.get("area"):
            hechos = hechos.filter(area_origen_id=ctx["area"])
        elif ctx["area_sin_asignar"]:
            hechos = hechos.filter(area_origen_id__isnull=True)
        return ctx, hechos

    def list(self, request):
        ctx, hechos = self.fuentes(request)
        datos, grupos = resumir_costos(hechos, ctx["institucion"], ctx["periodo_economico"], ctx.get("area"))
        datos.update(
            institucion=ctx["institucion"], area=ctx.get("area"),
            periodo_economico=ctx["periodo_economico"],
        )
        return self.auditar_respuesta(Response(datos), grupos=grupos)
