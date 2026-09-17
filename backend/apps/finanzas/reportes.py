"""Agregaciones compartidas por el resumen operativo y la lectura ejecutiva."""
from decimal import Decimal

from django.db.models import BigIntegerField, Case, Count, DecimalField, F, IntegerField, Max, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from .models import AjusteGasto, AtribucionReparto, Gasto


def resumir_gastos(qs):
    moneda = DecimalField(max_digits=24, decimal_places=2)
    ajustes = AjusteGasto.objects.filter(gasto_id=OuterRef("pk"), estado="aprobado").order_by().values("gasto_id").annotate(total=Sum("importe")).values("total")[:1]
    ajustes_por_aprobar = AjusteGasto.objects.filter(
        gasto_id=OuterRef("pk"), estado="pendiente_aprobacion",
    ).order_by().values("gasto_id").annotate(cantidad=Count("pk")).values("cantidad")[:1]
    atribuciones = AtribucionReparto.objects.filter(
        reparto__gasto_id=OuterRef("pk"), reparto__reemplazado_por__isnull=True,
    ).order_by().values("reparto__gasto_id").annotate(total=Sum("importe_centavos")).values("total")[:1]
    qs = qs.annotate(
        importe_resultante=F("importe") + Coalesce(Subquery(ajustes, output_field=moneda), Value(Decimal("0"))),
        atribuido_centavos=Coalesce(Subquery(atribuciones), Value(0), output_field=BigIntegerField()),
        cantidad_ajustes_pendientes=Coalesce(Subquery(ajustes_por_aprobar), Value(0), output_field=IntegerField()),
    )
    # La identidad es área + concepto. Agrupar por el nombre congelado en cada
    # gasto separaría un concepto renombrado en cifras con el mismo enlace.
    grupos = qs.values("area_id", "area__nombre", "concepto_id", "concepto__nombre").annotate(
        aprobado=Coalesce(Sum(Case(When(estado=Gasto.Estado.APROBADO, then=F("importe_resultante")), default=Value(Decimal("0")), output_field=moneda)), Value(Decimal("0"))),
        por_aprobar=Coalesce(Sum(Case(When(estado=Gasto.Estado.PENDIENTE_APROBACION, then=F("importe_resultante")), default=Value(Decimal("0")), output_field=moneda)), Value(Decimal("0"))),
        ajustes_pendientes=Coalesce(Sum("cantidad_ajustes_pendientes"), Value(0)),
        distribuido_centavos=Coalesce(Sum(Case(When(estado=Gasto.Estado.APROBADO, then=F("atribuido_centavos")), default=Value(0), output_field=BigIntegerField())), Value(0), output_field=BigIntegerField()),
        actualizando=Max(Case(When(Q(estado=Gasto.Estado.APROBADO) & Q(trabajo_reparto__revision__gt=F("trabajo_reparto__revision_procesada")), then=Value(1)), default=Value(0), output_field=IntegerField())),
    ).order_by("area__nombre", "concepto__nombre", "area_id", "concepto_id")
    agrupaciones = []
    totales = {"aprobados": Decimal("0"), "pendientes_aprobacion": Decimal("0"), "distribuido": Decimal("0")}
    actualizando = False
    ajustes_pendientes = 0
    dinero = lambda valor: str(valor.quantize(Decimal("0.01")))
    for grupo in grupos:
        distribuido = Decimal(grupo["distribuido_centavos"]) / 100
        pendiente = bool(grupo["actualizando"])
        actualizando |= pendiente
        totales["aprobados"] += grupo["aprobado"]
        totales["pendientes_aprobacion"] += grupo["por_aprobar"]
        ajustes_pendientes += grupo["ajustes_pendientes"]
        totales["distribuido"] += distribuido
        agrupaciones.append({
            "area": grupo["area_id"], "area_nombre": grupo["area__nombre"] or "Institucional — sin área asignada",
            "concepto": grupo["concepto_id"], "concepto_nombre": grupo["concepto__nombre"],
            "aprobados": dinero(grupo["aprobado"]), "pendientes_aprobacion": dinero(grupo["por_aprobar"]),
            "ajustes_pendientes": grupo["ajustes_pendientes"],
            "distribuido": None if pendiente else dinero(distribuido),
            "sin_distribuir": None if pendiente else dinero(grupo["aprobado"] - distribuido),
            "actualizando": pendiente,
        })
    totales["sin_distribuir"] = totales["aprobados"] - totales["distribuido"]
    datos = {nombre: None if actualizando and nombre in {"distribuido", "sin_distribuir"} else dinero(valor) for nombre, valor in totales.items()}
    datos.update(
        moneda="ARS", agrupaciones=agrupaciones, actualizando=actualizando,
        ajustes_pendientes=ajustes_pendientes, cantidad_registros=qs.exclude(estado="rechazado").count(),
        alcance="Gastos registrados visibles según tus permisos; no equivale al costo total del hospital.",
    )
    return datos
