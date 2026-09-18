"""Dinero por fecha efectiva, sin sumar de nuevo el gasto o la obligación."""
from calendar import monthrange
from collections import Counter
from django.utils import timezone

from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.instituciones.models import Area
from .auditoria import AuditaLecturaFinanciera
from .comparativas import ContextoComparativa, periodos_comparados, comparar
from .reportes_dinero import filas_dinero, resumir_agrupaciones, resumir_dinero, resumir_dinero_por_area, desglosar_dinero
from .models import ConcesionFinanciera, EstadoAprobacion, MovimientoDinero
from .permisos import alcance_financiero_q, concesiones_financieras_de, tiene_concesion_financiera


class ContextoDinero(serializers.Serializer):
    institucion = serializers.IntegerField(min_value=1)
    area = serializers.IntegerField(min_value=1, required=False)
    area_sin_asignar = serializers.BooleanField(default=False)
    fecha_desde = serializers.DateField()
    fecha_hasta = serializers.DateField()

    def validate(self, attrs):
        if attrs['fecha_hasta'] < attrs['fecha_desde']:
            raise serializers.ValidationError('La fecha final no puede ser anterior a la inicial.')
        if attrs.get('area') and attrs['area_sin_asignar']:
            raise serializers.ValidationError('Elegí un área o los movimientos institucionales, no ambos.')
        return attrs


class ReporteDineroViewSet(AuditaLecturaFinanciera, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = MovimientoDinero.objects.none()
    serializer_class = ContextoDinero
    http_method_names = ['get', 'head', 'options']

    @action(detail=False, methods=["get"], serializer_class=ContextoComparativa)
    def comparativa(self, request):
        actual, anterior, serie = periodos_comparados(request.query_params)
        resultados, auditoria = {}, Counter()
        desglose = []
        for mes in sorted(set([*serie, anterior])):
            parametros = request.query_params.dict()
            parametros.update(fecha_desde=mes.isoformat(), fecha_hasta=mes.replace(day=monthrange(mes.year, mes.month)[1]).isoformat())
            ctx, fuentes = self.fuentes(request, parametros)
            if mes == actual:
                desglose, datos, grupos = desglosar_dinero(fuentes, ctx["institucion"])
            else:
                datos, grupos = resumir_dinero(fuentes, ctx["institucion"])
            auditoria.update(grupos)
            datos.update(periodo_economico=mes.isoformat(), fecha_desde=parametros["fecha_desde"], fecha_hasta=parametros["fecha_hasta"], mes_abierto=mes >= timezone.localdate().replace(day=1))
            resultados[mes] = datos
        presente, previo = resultados[actual], resultados[anterior]
        return self.auditar_respuesta(Response({
            "actual": presente, "anterior": previo, "serie": [resultados[m] for m in serie],
            "variaciones": {c: comparar(presente[c], previo[c], presente["cantidad_movimientos"] > 0 and previo["cantidad_movimientos"] > 0) for c in ("cobros_netos", "pagos_netos", "diferencia")},
            "agrupaciones": desglose, "moneda": "ARS", "calculado_en": timezone.now(),
            "alcance": "Dinero aprobado por fecha efectiva y según tus permisos. Cobros y pagos netos de reintegros. La diferencia no es disponibilidad ni rentabilidad. Las prestaciones y los financiadores provienen de vínculos estructurados de las obligaciones.",
        }), grupos=auditoria)

    def fuentes(self, request, parametros=None):
        entrada = ContextoDinero(data=parametros if parametros is not None else request.query_params)
        entrada.is_valid(raise_exception=True)
        ctx = entrada.validated_data
        usuario = request.user
        accion = ConcesionFinanciera.Accion.VER_DINERO
        institucion = ctx['institucion']
        if not usuario.is_active or not (usuario.is_superuser or concesiones_financieras_de(
            usuario, accion,
        ).filter(membresia__institucion_id=institucion).exists()):
            raise PermissionDenied('No tenés autorización para consultar dinero de esta institución.')
        if ('area' in ctx or ctx['area_sin_asignar']) and not tiene_concesion_financiera(
            usuario, accion, institucion, ctx.get('area'),
        ):
            raise PermissionDenied('No tenés autorización para consultar dinero de esta área.')
        if ctx.get('area') and not Area.objects.filter(pk=ctx['area'], institucion_id=institucion).exists():
            raise serializers.ValidationError('El área no pertenece a la institución elegida.')
        fuentes = MovimientoDinero.objects.exclude(estado=EstadoAprobacion.RECHAZADO).filter(alcance_financiero_q(
            usuario, accion, institucion_path='obligacion__institucion_id',
            area_path='obligacion__area_id', sensible_path='obligacion__sensible',
        )).filter(obligacion__institucion_id=institucion, fecha__range=(ctx['fecha_desde'], ctx['fecha_hasta']))
        if ctx.get('area'):
            fuentes = fuentes.filter(obligacion__area_id=ctx['area'])
        elif ctx['area_sin_asignar']:
            fuentes = fuentes.filter(obligacion__area_id__isnull=True)
        return ctx, fuentes

    def list(self, request):
        ctx, fuentes = self.fuentes(request)
        institucion = ctx['institucion']
        # Un solo recorrido de movimientos alimenta el total y su reparto por área.
        filas = filas_dinero(fuentes)
        respuesta, grupos = resumir_agrupaciones(filas, institucion)
        respuesta.update(
            institucion=institucion, area=ctx.get('area'), fecha_desde=ctx['fecha_desde'],
            fecha_hasta=ctx['fecha_hasta'], moneda='ARS',
            agrupaciones=resumir_dinero_por_area(filas, institucion),
            alcance='Dinero aprobado por fecha efectiva y según tu acceso; lo pendiente se muestra aparte. La diferencia no es saldo disponible ni rentabilidad.',
        )
        return self.auditar_respuesta(Response(respuesta), grupos=grupos)
