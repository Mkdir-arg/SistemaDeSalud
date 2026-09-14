"""Proyección mensual de expectativas y cargas visibles para el solicitante."""
from django.db.models import Case, Count, DecimalField, Exists, F, IntegerField, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from .models import AjusteGasto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto
from .permisos import gastos_en_alcance_financiero


def en_alcance_financiero(queryset, usuario, accion):
    """Filtra entidades con institución, área y sensibilidad en la misma concesión."""
    return gastos_en_alcance_financiero(queryset, usuario, accion)


def calendario_mensual(expectativas, usuario, periodo):
    # Un sucesor futuro no borra los meses en que regía la versión anterior.
    expectativas = expectativas.filter(vigente_desde__lte=periodo).filter(
        Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=periodo)
    ).filter(
        Q(reemplazada_por__isnull=True) | Q(reemplazada_por__vigente_desde__gt=periodo)
    )
    ultima = IndicacionCargaGasto.objects.filter(
        expectativa_id=OuterRef("pk"), periodo_economico=periodo
    ).order_by("-registrado", "-id")
    gastos = en_alcance_financiero(
        Gasto.objects.all(), usuario, ConcesionFinanciera.Accion.VER_GASTOS
    ).filter(
        concepto_id=OuterRef("concepto_id"),
        institucion_id=OuterRef("institucion_id"),
        periodo_economico=periodo,
        reemplazado_por__isnull=True,
    )
    # SQL NULL no compara igual a NULL; separar el ámbito institucional evita
    # contar sus gastos dentro de cada área (y viceversa).
    def cantidad(estado, institucional):
        fuentes = gastos.filter(estado=estado)
        if institucional:
            fuentes = fuentes.filter(area_id__isnull=True)
        else:
            fuentes = fuentes.filter(area_id=OuterRef("area_id"))
        return fuentes.order_by().values("concepto_id").annotate(
            cantidad=Count("pk", distinct=True)
        ).values("cantidad")[:1]

    def cantidad_por_ambito(estado):
        return Coalesce(Case(
            When(area_id__isnull=True, then=Subquery(cantidad(estado, True))),
            default=Subquery(cantidad(estado, False)),
            output_field=IntegerField(),
        ), Value(0))

    moneda = DecimalField(max_digits=22, decimal_places=2)
    ajustes = AjusteGasto.objects.filter(gasto_id=OuterRef("pk")).order_by().values("gasto_id").annotate(
        total=Sum("importe"),
    ).values("total")[:1]

    def importe_aprobado(institucional):
        fuentes = gastos.filter(estado=Gasto.Estado.APROBADO)
        fuentes = fuentes.filter(area_id__isnull=True) if institucional else fuentes.filter(area_id=OuterRef("area_id"))
        # Subconsulta de ajustes evita multiplicar gastos por sus relaciones.
        return fuentes.order_by().values("concepto_id").annotate(total=Sum(
            F("importe") + Coalesce(Subquery(ajustes), Value(0), output_field=moneda), output_field=moneda,
        )).values("total")[:1]

    return expectativas.annotate(
        indicacion_id=Subquery(ultima.values("pk")[:1]),
        estado_carga=Coalesce(
            Subquery(ultima.values("estado")[:1]), Value(IndicacionCargaGasto.Estado.FALTA_CARGAR)
        ),
        indicacion_registrada=Subquery(ultima.values("registrado")[:1]),
        gastos_pendientes=cantidad_por_ambito(Gasto.Estado.PENDIENTE_APROBACION),
        gastos_aprobados=cantidad_por_ambito(Gasto.Estado.APROBADO),
        importe_aprobado=Coalesce(Case(
            When(area_id__isnull=True, then=Subquery(importe_aprobado(True))),
            default=Subquery(importe_aprobado(False)), output_field=moneda,
        ), Value(0), output_field=moneda),
    ).annotate(diferencia_referencia=F("monto_referencia") - F("importe_aprobado"))


def gastos_de_control_mensual(gastos, usuario):
    """Drill-down del histórico: misma vigencia, área (incluido NULL) y acceso."""
    controles = en_alcance_financiero(ExpectativaGasto.objects.all(), usuario, ConcesionFinanciera.Accion.VER_GASTOS).filter(
        institucion_id=OuterRef("institucion_id"), concepto_id=OuterRef("concepto_id"),
        vigente_desde__lte=OuterRef("periodo_economico"),
    ).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=OuterRef("periodo_economico"))).filter(
        Q(reemplazada_por__isnull=True) | Q(reemplazada_por__vigente_desde__gt=OuterRef("periodo_economico"))
    )
    return gastos.annotate(en_control_mensual=Case(
        When(area_id__isnull=True, then=Exists(controles.filter(area_id__isnull=True))),
        default=Exists(controles.filter(area_id=OuterRef("area_id"))),
    )).filter(en_control_mensual=True)
