"""Consulta financiera del circuito de coberturas hospitalarias."""
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from config.pagination import Paginacion
from apps.financiadores.seguimiento import (
    FiltrosSeguimiento, capturas_cobertura, cuentas_cobertura, fila_seguimiento,
    filtrar_seguimiento, opciones_seguimiento, pendientes_cobertura,
    puede_seguimiento, resumen_seguimiento,
)
from apps.financiadores.seguimiento_csv import LIMITE_EXPORTACION, exportar_seguimiento
from apps.instituciones.models import Area
from .auditoria import AuditaLecturaFinanciera
from .models import ObligacionFinanciera


class SeguimientoCobrosViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FiltrosSeguimiento
    pagination_class = Paginacion
    queryset = ObligacionFinanciera.objects.none()
    http_method_names = ["get", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    @extend_schema(parameters=[FiltrosSeguimiento], responses={
        (200, "application/json"): OpenApiTypes.OBJECT, (200, "text/csv"): OpenApiTypes.BINARY,
    })
    def list(self, request):
        entrada = FiltrosSeguimiento(data=request.query_params.dict())
        entrada.is_valid(raise_exception=True)
        filtros = entrada.validated_data
        institucion, vista = filtros["institucion"], filtros["vista"]
        if not puede_seguimiento(request.user, institucion):
            raise PermissionDenied("Necesitás permiso para consultar dinero de esta institución.")
        if "area" in filtros and not Area.objects.filter(pk=filtros["area"], institucion_id=institucion).exists():
            raise serializers.ValidationError({"area": "El área no pertenece a la institución."})
        fuentes = {"cuentas": cuentas_cobertura, "pendientes": pendientes_cobertura, "captura": capturas_cobertura}
        visible = fuentes[vista](request.user, institucion)
        qs = filtrar_seguimiento(visible, filtros).order_by("-fecha_reporte", "-pk")
        generado_en = timezone.now()
        if filtros["formato"] == "csv":
            return exportar_seguimiento(self, qs, institucion=institucion, vista=vista, generado_en=generado_en)
        pagina = list(self.paginate_queryset(qs))
        respuesta = self.get_paginated_response([fila_seguimiento(obj, vista) for obj in pagina])
        respuesta.data.update(resumen=resumen_seguimiento(qs, vista), opciones=opciones_seguimiento(visible, vista), generado_en=generado_en, limite_exportacion=LIMITE_EXPORTACION)
        # Auditar también las fuentes de los totales, no sólo la página visible.
        agrupados = qs.order_by().annotate(mes_reporte=TruncMonth("fecha_reporte")).values(
            "area_reporte", "sensible_reporte", "mes_reporte",
        ).annotate(cantidad=Count("pk"))
        grupos = {(institucion, fila["area_reporte"], fila["sensible_reporte"], fila["mes_reporte"]): fila["cantidad"] for fila in agrupados}
        if not grupos:
            grupos = {(institucion, None, False, None): 0}
        # Reusar la escritura estricta sin heredar las rutas list/retrieve del
        # mixin: este reporte no tiene un recurso de detalle independiente.
        return AuditaLecturaFinanciera.auditar_respuesta(
            self, respuesta, grupos=grupos, recurso="seguimiento-cobros", accion=vista,
        )
