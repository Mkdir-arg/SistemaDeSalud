"""Dinero por fecha efectiva, sin sumar de nuevo el gasto o la obligación."""
from decimal import Decimal

from django.db.models import Count, Sum
from rest_framework import serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.instituciones.models import Area
from .auditoria import AuditaLecturaFinanciera
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

    def list(self, request):
        entrada = ContextoDinero(data=request.query_params)
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
        # Agrupar únicamente movimientos: nunca unir colecciones de ajustes o
        # devoluciones que multipliquen importes del movimiento original.
        agrupaciones = list(fuentes.order_by().values(
            'tipo', 'estado', 'obligacion__tipo', 'obligacion__area_id',
            'obligacion__sensible', 'obligacion__periodo_economico',
        ).annotate(importe=Sum('importe'), cantidad=Count('id')))
        totales = dict.fromkeys(('cobros_brutos', 'pagos_brutos', 'reintegros_cobros', 'reintegros_pagos'), Decimal('0.00'))
        pendientes = dict.fromkeys(('cobros', 'pagos', 'reintegros_cobros', 'reintegros_pagos'), Decimal('0.00'))
        cantidad_pendientes = 0
        grupos = {}
        cantidad = 0
        for fila in agrupaciones:
            if fila['tipo'] == 'reintegro':
                clave = 'reintegros_cobros' if fila['obligacion__tipo'] == 'cobrar' else 'reintegros_pagos'
            else:
                clave = 'cobros_brutos' if fila['tipo'] == 'cobro' else 'pagos_brutos'
            if fila['estado'] == EstadoAprobacion.PENDIENTE:
                pendientes[clave.removesuffix('_brutos')] += fila['importe']
                cantidad_pendientes += fila['cantidad']
            else:
                totales[clave] += fila['importe']
                cantidad += fila['cantidad']
            grupo = (institucion, fila['obligacion__area_id'], fila['obligacion__sensible'], fila['obligacion__periodo_economico'])
            grupos[grupo] = grupos.get(grupo, 0) + fila['cantidad']
        totales['cobros_netos'] = totales['cobros_brutos'] - totales['reintegros_cobros']
        totales['pagos_netos'] = totales['pagos_brutos'] - totales['reintegros_pagos']
        totales['diferencia'] = totales['cobros_netos'] - totales['pagos_netos']
        respuesta = {clave: str(valor.quantize(Decimal('0.01'))) for clave, valor in totales.items()}
        respuesta['por_aprobar'] = {
            **{clave: str(valor.quantize(Decimal('0.01'))) for clave, valor in pendientes.items()},
            'cantidad': cantidad_pendientes,
        }
        respuesta.update(
            institucion=institucion, area=ctx.get('area'), fecha_desde=ctx['fecha_desde'],
            fecha_hasta=ctx['fecha_hasta'], moneda='ARS', cantidad_movimientos=cantidad,
            alcance='Dinero aprobado por fecha efectiva y según tu acceso; lo pendiente se muestra aparte. La diferencia no es saldo disponible ni rentabilidad.',
        )
        return self.auditar_respuesta(Response(respuesta), grupos=grupos)
