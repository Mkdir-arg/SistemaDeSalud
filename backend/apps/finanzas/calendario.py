"""Proyección mensual de expectativas y cargas visibles para el solicitante."""
from django.db.models import Case, Count, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce

from .models import ConcesionFinanciera, Gasto, IndicacionCargaGasto
from .permisos import concesiones_financieras_de


def en_alcance_financiero(queryset, usuario, accion):
    """Filtra entidades con institución, área y sensibilidad en la misma concesión."""
    if usuario.is_superuser:
        return queryset
    alcance = Q(pk__in=[])
    for sensible in (False, True):
        concesiones = concesiones_financieras_de(usuario, accion, sensible=sensible)
        for institucion_id, todas, area_id in concesiones.values_list(
            "membresia__institucion_id", "todas_las_areas", "areas__id"
        ):
            if not todas and area_id is None:
                continue
            scope = Q(institucion_id=institucion_id, sensible=sensible)
            if not todas:
                scope &= Q(area_id=area_id)
            alcance |= scope
    return queryset.filter(alcance).distinct()


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

    return expectativas.annotate(
        indicacion_id=Subquery(ultima.values("pk")[:1]),
        estado_carga=Coalesce(
            Subquery(ultima.values("estado")[:1]), Value(IndicacionCargaGasto.Estado.FALTA_CARGAR)
        ),
        indicacion_registrada=Subquery(ultima.values("registrado")[:1]),
        gastos_pendientes=cantidad_por_ambito(Gasto.Estado.PENDIENTE_APROBACION),
        gastos_aprobados=cantidad_por_ambito(Gasto.Estado.APROBADO),
    )
