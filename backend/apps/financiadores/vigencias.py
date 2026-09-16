"""Cierres explícitos: conservan identidades, decisiones y obligaciones anteriores."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Afiliado, Convenio, Financiador, HistorialAfiliacion, Plan
from .permisos import plataforma, requerir_financiador, requerir_hospital
from .services import auditar


def convenios_vigentes(corte=None):
    corte = corte or timezone.now()
    # Los activos anteriores a esta entrega pueden no tener fecha de aceptación.
    # Un nuevo convenio siempre la registra; cerrar no borra su intervalo anterior.
    return Convenio.objects.filter(estado__in=["activo", "finalizado"]).filter(
        Q(aceptado_en__isnull=True) | Q(aceptado_en__lte=corte),
        Q(cerrado_en__isnull=True) | Q(cerrado_en__gt=corte),
    )


def convenio_aplicable(financiador_id, institucion_id, corte, bloquear=False):
    qs = convenios_vigentes(corte).filter(financiador_id=financiador_id, institucion_id=institucion_id)
    if bloquear:
        qs = qs.select_for_update()
    return qs.order_by("-aceptado_en", "-pk").first()


def afiliados_vigentes():
    return Afiliado.objects.filter(finalizado_en__isnull=True, desde__lte=timezone.localdate(), financiador__activo=True)


def _motivo(valor):
    valor = valor.strip()
    if not valor or len(valor) > 255:
        raise ValidationError("Registrá un motivo de hasta 255 caracteres.")
    return valor


def _permiso_convenio(usuario, convenio, origen):
    if origen == "financiador":
        requerir_financiador(usuario, convenio.financiador_id, admin=True)
    else:
        requerir_hospital(usuario, convenio.institucion_id, "configurar_cobros")


@transaction.atomic
def proponer_convenio(*, usuario, financiador, institucion, origen):
    # Serializa las propuestas del mismo par, incluso antes de que exista la fila.
    Financiador.objects.select_for_update().get(pk=financiador.pk, activo=True)
    obj = Convenio(financiador=financiador, institucion=institucion, creado_por=usuario, propuesto_por=origen)
    _permiso_convenio(usuario, obj, origen)
    if Convenio.objects.filter(financiador=financiador, institucion=institucion, estado__in=["activo", "propuesto"]).exists():
        raise ValidationError("Ya existe un convenio activo o una propuesta pendiente con este hospital.")
    if origen == "financiador" and plataforma(usuario):
        obj.propuesto_por, obj.estado = "plataforma", "activo"
        obj.aceptado_por, obj.aceptado_en = usuario, timezone.now()
    obj.save()
    auditar(usuario, "proponer_convenio", obj.pk, financiador=financiador, institucion=institucion)
    return obj


@transaction.atomic
def aceptar_convenio(*, usuario, convenio, origen):
    obj = Convenio.objects.select_for_update().get(pk=convenio.pk)
    _permiso_convenio(usuario, obj, origen)
    contraparte = "hospital" if origen == "financiador" else "financiador"
    if obj.propuesto_por != contraparte and not plataforma(usuario):
        raise ValidationError("La aceptación corresponde a la otra parte del convenio.")
    if obj.estado != "propuesto":
        raise ValidationError("Sólo se puede aceptar una propuesta pendiente. Un convenio cerrado no se reactiva.")
    obj.estado, obj.aceptado_por, obj.aceptado_en = "activo", usuario, timezone.now()
    obj.save(update_fields=["estado", "aceptado_por", "aceptado_en"])
    auditar(usuario, "aceptar_convenio", obj.pk, financiador=obj.financiador, institucion=obj.institucion)
    return obj


@transaction.atomic
def cerrar_convenio(*, usuario, convenio, origen, motivo, rechazar=False):
    obj = Convenio.objects.select_for_update().get(pk=convenio.pk)
    _permiso_convenio(usuario, obj, origen)
    motivo = _motivo(motivo)
    destino = "rechazado" if rechazar else "finalizado"
    if rechazar and obj.propuesto_por == origen and not plataforma(usuario):
        raise ValidationError("El rechazo corresponde a la otra parte de la propuesta.")
    if obj.estado == destino and obj.motivo_cierre == motivo:
        return obj
    if obj.estado != ("propuesto" if rechazar else "activo"):
        raise ValidationError("Sólo se rechazan propuestas pendientes o se cierran convenios activos.")
    obj.estado, obj.cerrado_en, obj.cerrado_por, obj.motivo_cierre = destino, timezone.now(), usuario, motivo
    obj.save(update_fields=["estado", "cerrado_en", "cerrado_por", "motivo_cierre"])
    auditar(usuario, "rechazar_convenio" if rechazar else "cerrar_convenio", obj.pk, financiador=obj.financiador, institucion=obj.institucion, motivo=motivo)
    return obj


@transaction.atomic
def editar_plan(*, usuario, plan, nombre, activo, motivo):
    plan = Plan.objects.select_for_update().get(pk=plan.pk)
    requerir_financiador(usuario, plan.financiador_id, admin=True)
    motivo = _motivo(motivo)
    if not nombre.strip():
        raise ValidationError("Indicá el nombre del plan.")
    plan.nombre, plan.activo = nombre.strip(), activo
    plan.full_clean()
    plan.save(update_fields=["nombre", "activo"])
    auditar(usuario, "editar_plan", plan.pk, financiador=plan.financiador, motivo=motivo)
    return plan


def _historial(afiliado, usuario, tipo, motivo):
    HistorialAfiliacion.objects.create(
        afiliado=afiliado, numero=afiliado.numero, documento=afiliado.documento,
        plan=afiliado.plan, desde=timezone.localdate(), registrado_por=usuario, tipo=tipo, motivo=motivo,
    )


@transaction.atomic
def finalizar_afiliacion(*, usuario, afiliado, motivo):
    afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    motivo = _motivo(motivo)
    if afiliado.finalizado_en:
        if afiliado.motivo_finalizacion == motivo:
            return afiliado
        raise ValidationError("La afiliación ya está finalizada. Su cierre anterior se conserva.")
    afiliado.finalizado_en, afiliado.finalizado_por, afiliado.motivo_finalizacion = timezone.now(), usuario, motivo
    afiliado.save(update_fields=["finalizado_en", "finalizado_por", "motivo_finalizacion"])
    _historial(afiliado, usuario, "finalizacion", motivo)
    auditar(usuario, "finalizar_afiliacion", afiliado.pk, financiador=afiliado.financiador, motivo=motivo)
    return afiliado


@transaction.atomic
def reactivar_afiliacion(*, usuario, afiliado, plan, motivo):
    afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    motivo = _motivo(motivo)
    if not afiliado.finalizado_en:
        raise ValidationError("La afiliación ya está vigente.")
    if plan:
        plan = Plan.objects.select_for_update().get(pk=plan.pk)
        if plan.financiador_id != afiliado.financiador_id or not plan.activo:
            raise ValidationError("Elegí un plan activo del financiador.")
    afiliado.plan, afiliado.desde = plan, timezone.localdate()
    afiliado.finalizado_en, afiliado.finalizado_por, afiliado.motivo_finalizacion = None, None, ""
    afiliado.save(update_fields=["plan", "desde", "finalizado_en", "finalizado_por", "motivo_finalizacion"])
    _historial(afiliado, usuario, "reactivacion", motivo)
    auditar(usuario, "reactivar_afiliacion", afiliado.pk, financiador=afiliado.financiador, motivo=motivo)
    return afiliado
