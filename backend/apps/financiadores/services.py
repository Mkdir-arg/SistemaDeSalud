"""Reglas administrativas y padrón. Todos los escritores de cupo bloquean al afiliado."""
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.registros.models import normalizar_documento

from .models import (
    Afiliado, ConsumoExterno, EventoCobertura, HistorialAfiliacion,
    PrestacionComun, ReglaCobertura, ReservaCobertura,
)
from .permisos import requerir_financiador


def auditar(usuario, accion, objeto, *, financiador=None, institucion=None, motivo=""):
    return EventoCobertura.objects.create(usuario=usuario, accion=accion, objeto=str(objeto), financiador=financiador, institucion=institucion, motivo=motivo)


def catalogo_financiador(financiador):
    reglas = ReglaCobertura.objects.filter(financiador=financiador)
    return PrestacionComun.objects.filter(activo=True).filter(
        Q(pk__in=reglas.exclude(prestacion=None).values("prestacion")) |
        Q(categoria__in=reglas.exclude(categoria="").values("categoria"))
    ).distinct()


@transaction.atomic
def registrar_afiliado(*, financiador, usuario, numero, documento, nombre, plan, desde):
    requerir_financiador(usuario, financiador.pk, escritura=True)
    numero, documento, nombre = str(numero).strip(), normalizar_documento(documento), str(nombre).strip()
    if not numero or not documento or not nombre:
        raise ValidationError("Completá número de afiliado, documento y nombre.")
    if plan and (plan.financiador_id != financiador.pk or not plan.activo):
        raise ValidationError("El plan debe estar activo y pertenecer al financiador.")
    if not isinstance(desde, date) or desde > timezone.localdate():
        raise ValidationError("La vigencia del padrón debe ser una fecha actual o anterior.")
    # El índice único resuelve altas simultáneas; nunca identificar por número familiar.
    afiliado, creado = Afiliado.objects.get_or_create(financiador=financiador, documento=documento, defaults={"numero": numero, "nombre": nombre, "plan": plan, "desde": desde})
    afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    if afiliado.finalizado_en:
        raise ValidationError("La afiliación está finalizada. Reactivala expresamente desde el padrón antes de actualizarla; la importación no reactiva afiliaciones.")
    if plan:
        plan = type(plan).objects.select_for_update().get(pk=plan.pk)
        if not plan.activo:
            raise ValidationError("El plan ya no está activo. Actualizá la selección.")
    if not creado and desde < afiliado.desde:
        raise ValidationError("La actualización no puede anteceder la última vigencia del padrón.")
    cambio = creado or (afiliado.numero, afiliado.plan_id, afiliado.desde) != (numero, getattr(plan, "pk", None), desde)
    afiliado.numero, afiliado.nombre, afiliado.plan, afiliado.desde = numero, nombre, plan, desde
    afiliado.full_clean()
    afiliado.save()
    if cambio:
        HistorialAfiliacion.objects.create(afiliado=afiliado, numero=numero, documento=documento, plan=plan, desde=desde, registrado_por=usuario)
        auditar(usuario, "actualizar_padron", afiliado.pk, financiador=financiador)
    return afiliado


@transaction.atomic
def corregir_identidad(*, afiliado, usuario, numero, documento, motivo):
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    numero, documento = numero.strip(), normalizar_documento(documento)
    if not numero or not documento or not motivo.strip():
        raise ValidationError("Completá los identificadores y el motivo de la corrección.")
    if Afiliado.objects.filter(financiador=afiliado.financiador, documento=documento).exclude(pk=afiliado.pk).exists():
        raise ValidationError("Ese documento ya pertenece a otro afiliado. La coincidencia requiere revisión; no se fusionan identidades.")
    afiliado.numero, afiliado.documento = numero, documento
    afiliado.full_clean()
    afiliado.save(update_fields=["numero", "documento"])
    HistorialAfiliacion.objects.create(afiliado=afiliado, numero=numero, documento=documento, plan=afiliado.plan, desde=afiliado.desde, registrado_por=usuario)
    auditar(usuario, "corregir_identidad", afiliado.pk, financiador=afiliado.financiador, motivo=motivo)
    return afiliado


def validar_consumo_externo(*, financiador, afiliado, prestacion, fecha, cantidad, referencia="", motivo_duplicado=""):
    if afiliado.financiador_id != financiador.pk:
        raise ValidationError("El afiliado no pertenece al financiador.")
    if not catalogo_financiador(financiador).filter(pk=prestacion.pk).exists():
        raise ValidationError("La prestación no forma parte del catálogo del financiador.")
    if not isinstance(fecha, date) or fecha > timezone.localdate():
        raise ValidationError("La fecha debe corresponder a una prestación ya realizada.")
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or cantidad <= 0 or cantidad > 100000:
        raise ValidationError("La cantidad debe ser un entero entre 1 y 100.000.")
    if len(referencia) > 120 or len(motivo_duplicado) > 255:
        raise ValidationError("La referencia o el motivo supera el largo permitido.")
    existentes = ConsumoExterno.objects.filter(financiador=financiador)
    if referencia:
        previo = existentes.filter(referencia=referencia).first()
        if previo:
            if (previo.afiliado_id, previo.prestacion_id, previo.fecha, previo.cantidad) != (afiliado.pk, prestacion.pk, fecha, cantidad):
                raise ValidationError("La referencia ya existe con otros datos.", code="referencia_conflictiva")
            return previo
    if not referencia and not motivo_duplicado.strip() and existentes.filter(afiliado=afiliado, prestacion=prestacion, fecha=fecha, cantidad=cantidad, corrige=None).exists():
        raise ValidationError("Posible duplicado: revisá la prestación e indicá un motivo para incorporarla.", code="posible_duplicado")
    return None


@transaction.atomic
def registrar_consumo_externo(*, financiador, usuario, afiliado, prestacion, fecha, cantidad, referencia="", motivo_duplicado=""):
    requerir_financiador(usuario, financiador.pk, escritura=True)
    afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
    referencia = referencia.strip()
    anterior = validar_consumo_externo(financiador=financiador, afiliado=afiliado, prestacion=prestacion, fecha=fecha, cantidad=cantidad, referencia=referencia, motivo_duplicado=motivo_duplicado)
    if anterior:
        return anterior
    consumo = ConsumoExterno.objects.create(financiador=financiador, afiliado=afiliado, prestacion=prestacion, fecha=fecha, cantidad=cantidad, referencia=referencia, motivo=motivo_duplicado, registrado_por=usuario)
    marcar_discrepancias(afiliado, prestacion)
    auditar(usuario, "consumo_externo", consumo.pk, financiador=financiador, motivo=motivo_duplicado)
    return consumo


def marcar_discrepancias(afiliado, prestacion):
    from .cobertura import cantidades_periodo, periodo
    # Q01: jamás modificar cubiertas, aceptación ni importes comprometidos.
    for reserva in ReservaCobertura.objects.filter(afiliado=afiliado, comun=prestacion, estado__in=["reservada", "realizada"], discrepancia=False):
        limite = reserva.evaluacion.get("cupo")
        if limite is not None:
            inicio, fin = periodo(reserva.fecha, reserva.evaluacion["periodo"])
            usado = cantidades_periodo(afiliado, prestacion, inicio, fin)
            if usado > limite:
                reserva.discrepancia = True
                reserva.save(update_fields=["discrepancia"])


@transaction.atomic
def corregir_consumo(*, consumo, usuario, cantidad, motivo):
    requerir_financiador(usuario, consumo.financiador_id, escritura=True)
    Afiliado.objects.select_for_update().get(pk=consumo.afiliado_id)
    if not motivo.strip() or not isinstance(cantidad, int) or cantidad < 0 or cantidad > 100000:
        raise ValidationError("Indicá la cantidad correcta (cero anula el consumo) y el motivo.")
    if consumo.corrige_id:
        raise ValidationError("La corrección se registra sobre el consumo original.")
    previo = ConsumoExterno.objects.filter(corrige=consumo).first()
    if previo:
        if previo.cantidad == cantidad - consumo.cantidad and previo.motivo == motivo:
            return previo
        raise ValidationError("Este consumo ya tiene una corrección registrada.")
    correccion = ConsumoExterno.objects.create(financiador=consumo.financiador, afiliado=consumo.afiliado, prestacion=consumo.prestacion, fecha=consumo.fecha, cantidad=cantidad-consumo.cantidad, corrige=consumo, motivo=motivo, registrado_por=usuario)
    marcar_discrepancias(consumo.afiliado, consumo.prestacion)
    auditar(usuario, "corregir_consumo", correccion.pk, financiador=consumo.financiador, motivo=motivo)
    return correccion
