"""Datos hospitalarios que puede consultar el pagador y evidencia de esa lectura."""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Case, DecimalField, Exists, F, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.auditoria.mixins import registrar_accesos
from apps.auditoria.models import AccesoClinico
from apps.finanzas.models import AjusteObligacion, MovimientoDinero, ObligacionFinanciera
from .models import ReservaCobertura, ResolucionSaldo
from .vigencias import convenios_vigentes


def obligaciones_pendientes():
    """Misma aritmética de dinero.estado_obligacion, antes de paginar el acceso.

    Una resolución administrativa no demuestra pago. También quedan pendientes
    los reintegros, reducciones y movimientos que aún requieren aprobación.
    Subconsultas separadas evitan multiplicar importes al cruzar ambas tablas.
    """
    dinero = DecimalField(max_digits=18, decimal_places=2)
    cero = Value(Decimal("0.00"), output_field=dinero)
    ajustes = AjusteObligacion.objects.filter(obligacion_id=OuterRef("pk"), estado="aprobado").order_by().values("obligacion_id").annotate(total=Sum("importe")).values("total")
    movimientos = MovimientoDinero.objects.filter(obligacion_id=OuterRef("pk"), estado="aprobado").order_by().values("obligacion_id").annotate(total=Sum(Case(When(tipo="reintegro", then=-F("importe")), default=F("importe"), output_field=dinero))).values("total")
    return ObligacionFinanciera.objects.annotate(
        ajuste_aprobado=Coalesce(Subquery(ajustes, output_field=dinero), cero),
        neto_aprobado=Coalesce(Subquery(movimientos, output_field=dinero), cero),
        movimiento_pendiente=Exists(MovimientoDinero.objects.filter(obligacion_id=OuterRef("pk"), estado="pendiente_aprobacion")),
        ajuste_pendiente=Exists(AjusteObligacion.objects.filter(obligacion_id=OuterRef("pk"), estado="pendiente_aprobacion")),
    ).annotate(saldo_acceso=F("importe_original") + F("ajuste_aprobado") - F("neto_aprobado")).filter(
        ~Q(saldo_acceso=0) | Q(movimiento_pendiente=True) | Q(ajuste_pendiente=True)
    )


def actividad_visible(financiador):
    pendientes = obligaciones_pendientes().values("pk")
    convenio = convenios_vigentes().filter(financiador=financiador, institucion_id=OuterRef("hospital_origen"))
    acuerdo_pendiente = ResolucionSaldo.objects.filter(
        distribucion__reserva_id=OuterRef("pk"), decision="financiador", obligacion_id__in=pendientes,
    )
    qs = ReservaCobertura.objects.filter(afiliado__financiador=financiador).annotate(
        hospital_origen=Case(When(hecho__isnull=False, then=F("hecho__institucion_id")), default=F("caso__institucion_id")),
    ).annotate(convenio_vigente=Exists(convenio), acuerdo_pendiente=Exists(acuerdo_pendiente))
    vigente = Q(convenio_vigente=True, afiliado__finalizado_en__isnull=True, afiliado__desde__lte=timezone.localdate(), afiliado__financiador__activo=True)
    pendiente = (
        Q(estado="reservada", cubiertas__gt=0)
        | Q(distribucion__obligacion_financiador_id__in=pendientes)
        | Q(acuerdo_pendiente=True)
        | (Q(distribucion__estado__in=["arancel_pendiente", "evaluacion_pendiente", "autorizacion_pendiente"]) & (Q(cubiertas__gt=0) | Q(evaluacion__convenio__gt=0)))
    )
    # Ni el copago impago ni una discrepancia ya resuelta amplían el acceso del pagador.
    return qs.filter(vigente | pendiente).annotate(
        acceso=Case(When(vigente, then=Value("vigente")), default=Value("pendiente_historico")),
    ).select_related("afiliado", "prestacion", "caso__institucion", "caso__ciudadano", "hecho__institucion", "hecho__ciudadano", "distribucion")


def auditar_actividad(request, financiador, reservas, *, recurso="financiadores-actividad"):
    # Sólo las personas realmente devueltas en la página o archivo. Nunca se atribuye
    # a otro hospital un acceso porque el caso haya cambiado después del hecho.
    personas = defaultdict(list)
    for reserva in reservas:
        fuente = reserva.hecho if reserva.hecho_id else reserva.caso
        personas[(fuente.institucion_id, fuente.ciudadano)].append(reserva.pk)
    def accesos():
        for (institucion_id, ciudadano), ids in personas.items():
            # El detalle admite 300 caracteres. Diez IDs de 64 bits entran completos;
            # una exportación grande no debe perder la evidencia por truncamiento.
            for inicio in range(0, len(ids), 10):
                bloque = ids[inicio:inicio + 10]
                yield {
                    "ciudadano": ciudadano, "institucion_id": institucion_id,
                    "objeto_id": bloque[0], "resultados": len(bloque),
                    "detalle": f"financiador={financiador.pk} reservas={','.join(map(str, bloque))}",
                }

    registrar_accesos(request, AccesoClinico.Tipo.FINANCIADOR, recurso, accesos(), estricto=True)
