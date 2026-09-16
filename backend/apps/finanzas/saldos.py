"""Saldos para consultas agregadas; la operatoria bloqueada sigue en dinero.py."""
from decimal import Decimal

from django.db.models import Case, DecimalField, F, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, Greatest

from .models import AjusteObligacion, MovimientoDinero


CAMPOS_SALDO = (
    "importe_original", "ajustes_aprobados", "obligacion_actual", "registrado_neto",
    "pendiente", "saldo_a_devolver", "por_aprobar", "reintegros_por_aprobar", "ajustes_por_aprobar",
)


def saldos_obligaciones(queryset):
    """Misma aritmética confirmada de estado_obligacion, en una sentencia SQL.

    Cada cuenta mantiene su deuda y su devolución separadas. Las subconsultas
    evitan el producto entre movimientos y ajustes. No calcula disponibles para
    escribir: eso requiere volver a bloquear y validar la cuenta en dinero.py.
    """
    dinero = DecimalField(max_digits=20, decimal_places=2)
    cero = Value(Decimal("0.00"), output_field=dinero)
    ajustes = AjusteObligacion.objects.filter(obligacion_id=OuterRef("pk"))
    movimientos = MovimientoDinero.objects.filter(obligacion_id=OuterRef("pk"))

    def suma(filas, expresion):
        total = filas.order_by().values("obligacion_id").annotate(total=Sum(expresion)).values("total")
        return Coalesce(Subquery(total, output_field=dinero), cero)

    return queryset.annotate(
        ajustes_aprobados=suma(ajustes.filter(estado="aprobado"), "importe"),
        registrado_neto=suma(movimientos.filter(estado="aprobado"), Case(
            When(tipo="reintegro", then=-F("importe")), default=F("importe"), output_field=dinero,
        )),
        por_aprobar=suma(movimientos.filter(estado="pendiente_aprobacion").exclude(tipo="reintegro"), "importe"),
        reintegros_por_aprobar=suma(movimientos.filter(estado="pendiente_aprobacion", tipo="reintegro"), "importe"),
        ajustes_por_aprobar=-suma(ajustes.filter(estado="pendiente_aprobacion"), "importe"),
    ).annotate(
        obligacion_actual=F("importe_original") + F("ajustes_aprobados"),
    ).annotate(
        pendiente=Greatest(F("obligacion_actual") - F("registrado_neto"), cero),
        saldo_a_devolver=Greatest(F("registrado_neto") - F("obligacion_actual"), cero),
    )
