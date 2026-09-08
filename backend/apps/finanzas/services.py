import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import AjusteCosto, ComponenteEsperadoHecho, ConcesionFinanciera, DefinicionComponente, HechoAtencionCosteable, ImputacionCosto, PendienteCosteo, Prestacion, ValorComponente
from .permisos import tiene_concesion_financiera


logger = logging.getLogger(__name__)


def registrar_atencion_completada(caso, nodo, evento, autor=None):
    """Crea una vez el hecho económico para el evento clínico ya confirmado."""
    hecho, _ = HechoAtencionCosteable.objects.get_or_create(
        evento_origen_id=evento.id,
        defaults={
            "institucion": caso.institucion,
            "caso": caso,
            "caso_origen_id": caso.id,
            "ciudadano": caso.ciudadano,
            "ciudadano_origen_id": caso.ciudadano_id,
            "evento": evento,
            "nodo": nodo,
            "nodo_origen_id": nodo.id,
            "area": caso.area_actual,
            "area_origen_id": caso.area_actual_id,
            "autor": autor,
            "ocurrida_en": timezone.now(),
        },
    )
    return hecho


def _pendiente(hecho, motivo, componente=None):
    pendiente, _ = PendienteCosteo.objects.get_or_create(hecho=hecho, componente=componente, motivo=motivo)
    if pendiente.resuelto:
        pendiente.resuelto, pendiente.resuelto_en = False, None
        pendiente.save(update_fields=["resuelto", "resuelto_en"])
    return pendiente


def _resolver(hecho, motivo, componente=None):
    PendienteCosteo.objects.filter(hecho=hecho, componente=componente, motivo=motivo, resuelto=False).update(resuelto=True, resuelto_en=timezone.now())


def procesar_hecho_atencion(hecho_id):
    """Calcula sólo componentes directos disponibles; es seguro reintentarlo."""
    with transaction.atomic():
        hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        esperados = ComponenteEsperadoHecho.objects.filter(hecho=hecho).select_related("componente")
        if esperados.exists():
            componentes = [esperado.componente for esperado in esperados]
        else:
            prestaciones = Prestacion.objects.filter(institucion=hecho.institucion, nodo_id=hecho.nodo_origen_id, activo=True)
            if not prestaciones.exists():
                return _pendiente(hecho, PendienteCosteo.Motivo.SIN_PRESTACION)
            _resolver(hecho, PendienteCosteo.Motivo.SIN_PRESTACION)
            componentes = list(DefinicionComponente.objects.filter(prestacion__in=prestaciones, activo=True, fuente=DefinicionComponente.Fuente.ATENCION_DIRECTA))
            if not componentes:
                return _pendiente(hecho, PendienteCosteo.Motivo.SIN_COMPONENTES)
            ComponenteEsperadoHecho.objects.bulk_create([ComponenteEsperadoHecho(hecho=hecho, componente=componente) for componente in componentes], ignore_conflicts=True)
            _resolver(hecho, PendienteCosteo.Motivo.SIN_COMPONENTES)
        for componente in componentes:
            valor = ValorComponente.objects.filter(componente=componente, vigente_desde__lte=hecho.ocurrida_en).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=hecho.ocurrida_en)).order_by("-vigente_desde", "-id").first()
            if valor is None:
                _pendiente(hecho, PendienteCosteo.Motivo.SIN_VALOR, componente)
                continue
            try:
                ImputacionCosto.objects.get_or_create(hecho=hecho, componente=componente, defaults={"valor": valor, "importe": valor.importe})
            except IntegrityError:
                pass
            _resolver(hecho, PendienteCosteo.Motivo.SIN_VALOR, componente)
        return hecho


def intentar_costeo_directo(hecho_id):
    """Intenta el costo local sin convertir una falla económica en clínica.

    Las fuentes pesadas o fallidas quedan para recuperación; la atención ya
    completada no se revierte ni se bloquea por ese trabajo.
    """
    try:
        procesar_hecho_atencion(hecho_id)
    except Exception:  # noqa: BLE001 - la recuperación posterior es deliberada.
        logger.exception("No se pudo costear de inmediato el hecho %s", hecho_id)
        with transaction.atomic():
            hecho = HechoAtencionCosteable.objects.get(pk=hecho_id)
            _pendiente(hecho, PendienteCosteo.Motivo.ERROR_RECUPERABLE)
        return False
    return True


def registrar_ajuste_costo(imputacion, importe, motivo, registrado_por):
    """Corrige un importe histórico con un asiento nuevo y autorizado."""
    if not tiene_concesion_financiera(
        registrado_por,
        ConcesionFinanciera.Accion.CORREGIR_COSTOS,
        imputacion.hecho.institucion_id,
        imputacion.hecho.area_origen_id,
        sensible=True,
    ):
        raise PermissionDenied("No tenés autorización para corregir este costo.")
    ajuste = AjusteCosto(
        imputacion=imputacion,
        importe=importe,
        motivo=motivo,
        registrado_por=registrado_por,
    )
    try:
        ajuste.save()
    except ValidationError:
        raise
    return ajuste
