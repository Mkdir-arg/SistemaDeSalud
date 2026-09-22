"""Costos conocidos de las atenciones del mes, agregados sin volver a sumar el gasto.

El costo directo proviene de las imputaciones congeladas y de sus ajustes
aprobados. El compartido es la parte de gastos aprobados ya atribuida a esas
atenciones: explica ese mismo gasto, no es un costo adicional y no se suma a
los totales de gastos ni a los movimientos de dinero del mes.
"""
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Count, Exists, F, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.instituciones.models import Area

from .models import (
    AjusteCosto,
    AtribucionReparto,
    ComponenteEsperadoHecho,
    EstadoAprobacion,
    HechoAtencionCosteable,
    ImputacionCosto,
    PendienteCosteo,
    Prestacion,
    TrabajoReparto,
)

CENTAVO = Decimal("0.01")
SIN_AREA = "Institucional — sin área asignada"
AREA_NO_DISPONIBLE = "Área no disponible"
SIN_PRESTACION = "Sin prestación configurada"
ALCANCE = (
    "Costos conocidos de las atenciones completadas en el mes, según tus permisos. "
    "El directo incluye sólo componentes configurados y ajustes aprobados; el compartido "
    "es gasto aprobado ya atribuido, no un costo adicional. No es el costo total del "
    "paciente ni del hospital, y no se suma a gastos ni a pagos y cobros."
)


def rango_mes_local(inicio):
    """Mes económico como intervalo local semiabierto, igual que el listado."""
    fin = date(inicio.year + (inicio.month == 12), inicio.month % 12 + 1, 1)
    return (
        timezone.make_aware(datetime.combine(inicio, time.min)),
        timezone.make_aware(datetime.combine(fin, time.min)),
    )


def _conteo(modelo, campo="hecho", **filtros):
    """Cuenta por hecho sin unir colecciones: nunca multiplica importes."""
    relacionados = (
        modelo.objects.filter(**{campo: OuterRef("pk")}, **filtros)
        .order_by()
        .values(campo)
        .annotate(cantidad=Count("pk"))
        .values("cantidad")[:1]
    )
    return Coalesce(Subquery(relacionados), 0)


def _prestacion(campo="pk"):
    """Prestación congelada del hecho; los componentes esperados son su origen."""
    return Subquery(
        ComponenteEsperadoHecho.objects.filter(hecho=OuterRef(campo))
        .order_by("componente__prestacion_id")
        .values("componente__prestacion_id")[:1]
    )


def _incompletos(base):
    """Sin componentes congelados, con imputaciones faltantes o con pendientes abiertos."""
    return base.annotate(
        esperados=_conteo(ComponenteEsperadoHecho),
        imputados=_conteo(ImputacionCosto),
        abiertos=_conteo(PendienteCosteo, resuelto=False),
    ).exclude(esperados__gt=0, esperados=F("imputados"), abiertos=0)


def _fila():
    return {"atenciones": 0, "incompletas": 0, "directo": Decimal("0.00"), "compartido": Decimal("0.00")}


def _sumar(destino, clave, campo, valor):
    destino.setdefault(clave, _fila())[campo] += valor


def _atribuciones_vigentes(ids):
    return AtribucionReparto.objects.filter(hecho__in=ids, reparto__reemplazado_por__isnull=True)


def _dimension(destino, ids, incompletos, clave_hecho, clave_imputacion, clave_ajuste, atribuciones):
    """Mismo cálculo para cualquier agrupación: una consulta por fuente, sin cruces."""
    for fila in incompletos.order_by().values(clave_hecho).annotate(cantidad=Count("pk")):
        _sumar(destino, fila[clave_hecho], "incompletas", fila["cantidad"])
    for fila in ImputacionCosto.objects.filter(hecho__in=ids).order_by().values(clave_imputacion).annotate(total=Sum("importe")):
        _sumar(destino, fila[clave_imputacion], "directo", fila["total"])
    for fila in (
        AjusteCosto.objects.filter(imputacion__hecho__in=ids, estado=EstadoAprobacion.APROBADO)
        .order_by().values(clave_ajuste).annotate(total=Sum("importe"))
    ):
        _sumar(destino, fila[clave_ajuste], "directo", fila["total"])
    for clave, centavos in atribuciones:
        _sumar(destino, clave, "compartido", Decimal(centavos) / 100)


def _presentar(destino, nombres, campo, sin_asignar):
    filas = [
        {
            campo: clave,
            "nombre": nombres.get(clave, sin_asignar if clave is None else AREA_NO_DISPONIBLE),
            "atenciones": valores["atenciones"],
            "incompletas": valores["incompletas"],
            "directo_conocido": str(valores["directo"].quantize(CENTAVO)),
            "compartido_conocido": str(valores["compartido"].quantize(CENTAVO)),
        }
        for clave, valores in destino.items()
    ]
    return sorted(filas, key=lambda f: (f["nombre"], f[campo] or 0))


def resumir_costos(hechos, institucion, periodo, area=None):
    """Totales y desgloses del mes; devuelve también los grupos de auditoría."""
    ids = hechos.values("pk")
    base = HechoAtencionCosteable.objects.filter(pk__in=ids)
    con_prestacion = base.annotate(prestacion=_prestacion())
    por_area, por_prestacion = {}, {}
    grupos = defaultdict(int)
    # Una sola consulta resuelve las atenciones por área y la evidencia de auditoría.
    conteos = (
        base.annotate(
            sensible_componente=Exists(ComponenteEsperadoHecho.objects.filter(hecho=OuterRef("pk"), sensible=True)),
            sensible_reparto=Exists(AtribucionReparto.objects.filter(
                hecho=OuterRef("pk"), reparto__reemplazado_por__isnull=True, reparto__gasto__sensible=True,
            )),
        )
        .order_by().values("area_origen_id", "sensible_componente", "sensible_reparto").annotate(cantidad=Count("pk"))
    )
    for fila in conteos:
        _sumar(por_area, fila["area_origen_id"], "atenciones", fila["cantidad"])
        sensible = fila["sensible_componente"] or fila["sensible_reparto"]
        grupos[(institucion, fila["area_origen_id"], sensible, periodo)] += fila["cantidad"]
    for fila in con_prestacion.order_by().values("prestacion").annotate(cantidad=Count("pk")):
        _sumar(por_prestacion, fila["prestacion"], "atenciones", fila["cantidad"])
    _dimension(
        por_area, ids, _incompletos(base), "area_origen_id",
        "hecho__area_origen_id", "imputacion__hecho__area_origen_id",
        [(f["hecho__area_origen_id"], f["centavos"]) for f in
         _atribuciones_vigentes(ids).order_by().values("hecho__area_origen_id").annotate(centavos=Sum("importe_centavos"))],
    )
    _dimension(
        por_prestacion, ids, _incompletos(base).annotate(prestacion=_prestacion()), "prestacion",
        "componente__prestacion_id", "imputacion__componente__prestacion_id",
        [(f["prestacion"], f["centavos"]) for f in
         _atribuciones_vigentes(ids).annotate(prestacion=_prestacion("hecho")).order_by()
         .values("prestacion").annotate(centavos=Sum("importe_centavos"))],
    )
    areas = dict(Area.objects.filter(pk__in=[c for c in por_area if c is not None]).values_list("pk", "nombre"))
    prestaciones = dict(Prestacion.objects.filter(pk__in=[c for c in por_prestacion if c is not None]).values_list("pk", "nombre"))
    trabajos = TrabajoReparto.objects.filter(
        gasto__institucion_id=institucion, gasto__periodo_economico=periodo,
        gasto__reemplazado_por__isnull=True, revision__gt=F("revision_procesada"),
    )
    if area is not None:
        trabajos = trabajos.filter(gasto__area_id=area)
    totales = {
        campo: sum((valores[campo] for valores in por_area.values()), inicial)
        for campo, inicial in (("atenciones", 0), ("incompletas", 0), ("directo", Decimal("0.00")), ("compartido", Decimal("0.00")))
    }
    datos = {
        "atenciones": totales["atenciones"],
        "atenciones_incompletas": totales["incompletas"],
        "directo_conocido": str(totales["directo"].quantize(CENTAVO)),
        "compartido_conocido": str(totales["compartido"].quantize(CENTAVO)),
        "ajustes_pendientes": AjusteCosto.objects.filter(
            imputacion__hecho__in=ids, estado=EstadoAprobacion.PENDIENTE,
        ).count(),
        "reparto_actualizando": trabajos.exists(),
        "agrupaciones": {
            "area": _presentar(por_area, areas, "area", SIN_AREA),
            "prestacion": _presentar(por_prestacion, prestaciones, "prestacion", SIN_PRESTACION),
        },
        "moneda": "ARS",
        "alcance": ALCANCE,
    }
    return datos, dict(grupos)
