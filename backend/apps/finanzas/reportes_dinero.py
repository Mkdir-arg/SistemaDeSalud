"""Misma aritmética para dinero operativo, comparativas y desgloses."""
from decimal import Decimal
from collections import defaultdict
from django.db.models import Case, CharField, Count, F, Sum, Value, When
from django.db.models.functions import Coalesce
from rest_framework import serializers
from .models import EstadoAprobacion


def resumir_dinero(fuentes, institucion):
    # Agrupar únicamente movimientos: nunca unir colecciones de ajustes o
    # devoluciones que multipliquen importes del movimiento original.
    agrupaciones = list(fuentes.order_by().values(
        'tipo', 'estado', 'obligacion__tipo', 'obligacion__area_id',
        'obligacion__sensible', 'obligacion__periodo_economico',
    ).annotate(importe=Sum('importe'), cantidad=Count('id')))
    return resumir_agrupaciones(agrupaciones, institucion)


def resumir_agrupaciones(agrupaciones, institucion):
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
    respuesta["cantidad_movimientos"] = cantidad
    return respuesta, grupos


def dimensiones_dinero(fuentes):
    """Sólo relaciones 1:1 desde la obligación: nunca multiplicar movimientos.

    Un copago pertenece al paciente, no a su financiador. Los registros anteriores
    sin vínculo estructurado quedan sin identificar; no se interpreta texto libre.
    """
    base = "obligacion__"
    financiador = base + "distribucion_financiador__reserva__afiliado__financiador"
    paciente = base + "distribucion_paciente__reserva__prestacion"
    resolucion = base + "resolucionsaldo__"
    reserva = resolucion + "distribucion__reserva__"
    return fuentes.annotate(
        reporte_financiador=Coalesce(F(financiador + "_id"), Case(
            When(**{resolucion + "decision": "financiador"}, then=F(reserva + "afiliado__financiador_id")),
        )),
        reporte_financiador_nombre=Coalesce(F(financiador + "__nombre"), Case(
            When(**{resolucion + "decision": "financiador"}, then=F(reserva + "afiliado__financiador__nombre")),
        )),
        reporte_prestacion=Coalesce(F(base + "distribucion_financiador__reserva__prestacion_id"), F(paciente + "_id"), F(reserva + "prestacion_id")),
        reporte_prestacion_nombre=Coalesce(F(base + "distribucion_financiador__reserva__prestacion__nombre"), F(paciente + "__nombre"), F(reserva + "prestacion__nombre")),
        reporte_concepto=F(base + "gasto__concepto_id"),
        reporte_concepto_nombre=F(base + "gasto__concepto__nombre"),
        reporte_pagador=Case(
            When(obligacion__tipo="pagar", then=Value("proveedor")),
            When(reporte_financiador__isnull=False, then=Value("financiador")),
            When(obligacion__distribucion_paciente__isnull=False, then=Value("paciente")),
            When(**{resolucion + "decision": "paciente"}, then=Value("paciente")),
            default=Value("sin_identificar"), output_field=CharField(),
        ),
    )


class FiltrosDesglose(serializers.Serializer):
    tipo_cuenta = serializers.ChoiceField(choices=["pagar", "cobrar"], required=False)
    reporte_pagador = serializers.ChoiceField(choices=["proveedor", "financiador", "paciente", "sin_identificar"], required=False)
    reporte_financiador = serializers.RegexField(r"^(null|[1-9][0-9]*)$", required=False)
    reporte_prestacion = serializers.RegexField(r"^(null|[1-9][0-9]*)$", required=False)
    reporte_concepto = serializers.RegexField(r"^(null|[1-9][0-9]*)$", required=False)


def filtrar_desglose(fuentes, parametros):
    entrada = FiltrosDesglose(data=parametros)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data
    if "tipo_cuenta" in datos:
        fuentes = fuentes.filter(obligacion__tipo=datos.pop("tipo_cuenta"))
    if datos:
        fuentes = dimensiones_dinero(fuentes)
        for nombre, valor in datos.items():
            fuentes = fuentes.filter(**{nombre + "__isnull": True}) if valor == "null" else fuentes.filter(**{nombre: valor})
    return fuentes


def desglosar_dinero(fuentes, institucion):
    campos = ("obligacion__area_id", "obligacion__area__nombre", "obligacion__tipo", "reporte_pagador",
              "reporte_financiador", "reporte_financiador_nombre", "reporte_prestacion",
              "reporte_prestacion_nombre", "reporte_concepto", "reporte_concepto_nombre")
    filas = list(dimensiones_dinero(fuentes).order_by().values(
        *campos, "tipo", "estado", "obligacion__sensible", "obligacion__periodo_economico",
    ).annotate(importe=Sum("importe"), cantidad=Count("id")))
    resumen, auditoria = resumir_agrupaciones(filas, institucion)
    grupos = defaultdict(list)
    for fila in filas:
        grupos[tuple(fila[c] for c in campos)].append(fila)
    resultado = []
    for filas in grupos.values():
        fila = filas[0]
        area = fila["obligacion__area_id"]
        filtros = {c: str(fila[c]) if fila[c] is not None else "null" for c in ("reporte_financiador", "reporte_prestacion", "reporte_concepto", "reporte_pagador")}
        filtros.update(tipo_cuenta=fila["obligacion__tipo"], **({"area": area} if area else {"area_sin_asignar": True}))
        importes, _ = resumir_agrupaciones(filas, institucion)
        resultado.append({
            "area_nombre": fila["obligacion__area__nombre"] or "Institucional — sin área asignada",
            "concepto_nombre": fila["reporte_concepto_nombre"] or fila["reporte_prestacion_nombre"] or "Sin prestación identificada",
            "pagador_nombre": fila["reporte_financiador_nombre"] or {"paciente": "Paciente · copago", "proveedor": "Proveedores", "sin_identificar": "Pagador sin vínculo estructurado"}[fila["reporte_pagador"]],
            "filtros": filtros, **importes,
        })
    return sorted(resultado, key=lambda g: (g["area_nombre"], g["concepto_nombre"], g["pagador_nombre"], str(g["filtros"]))), resumen, auditoria
