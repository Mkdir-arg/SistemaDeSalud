"""Vinculación explícita desde evidencia OSTEL aplicada, sin clasificar CODPAR."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from . import models as m, padron
from .ostel_importacion import VERSION, _texto
from .permisos import requerir_financiador


def _cuil_fuente(fila):
    try:
        return _texto(fila.get("original", {}).get("CUIL"))
    except ValidationError:
        return ""


def _identidad(lote, fila):
    if fila.get("estado") != "aplicada" or fila.get("bloqueo_fuente"):
        raise ValidationError("La fila debe estar aplicada sin bloqueo de fuente; requiere revisión.")
    obj = get_object_or_404(m.Afiliado, pk=fila.get("afiliado"), financiador=lote.financiador)
    cuil = _cuil_fuente(fila)
    if not cuil:
        raise ValidationError("Falta el CUIL original; requiere revisión.")
    padron.validar_cuit(cuil)
    if obj.cuil != cuil or any(getattr(obj, k) != fila["datos"].get(k) for k in ("cuil", "documento", "numero_interno")):
        raise ValidationError("La identidad actual no coincide con la fila aplicada; requiere revisión.")
    if obj.finalizado_en or obj.baja_efectiva:
        raise ValidationError("La afiliación tiene una baja informada; requiere revisión expresa.")
    return obj


def _resolver(lote, afiliado, fila):
    if lote.version != VERSION or lote.tipo != "padron":
        raise ValidationError("Se requiere un lote de padrón OSTEL.")
    fuentes = [f for f in lote.filas if f.get("fila") == fila]
    if len(fuentes) != 1:
        raise ValidationError("La fila de origen no es única o no existe.")
    fuente = fuentes[0]
    obj = _identidad(lote, fuente)
    if obj.pk != afiliado.pk:
        raise ValidationError("La fila no corresponde al afiliado solicitado.")
    referencia = _texto(fuente["original"].get("CUILTIT"))
    if not referencia:
        raise ValidationError("Falta CUILTIT; requiere revisión.")
    padron.validar_cuit(referencia, "CUILTIT")
    if referencia == obj.cuil:
        raise ValidationError("La fila se identifica como titular; no requiere vinculación.")
    propias = [f for f in lote.filas if _cuil_fuente(f) == obj.cuil]
    candidatas = [f for f in lote.filas if _cuil_fuente(f) == referencia]
    if len(propias) != 1 or len(candidatas) != 1:
        raise ValidationError("La referencia familiar está ausente o es ambigua en el lote; requiere revisión.")
    fuente_titular = candidatas[0]
    titular = _identidad(lote, fuente_titular)
    if _texto(fuente_titular["original"].get("CUILTIT")) != titular.cuil or titular.titular_id or obj.familiares.exists():
        raise ValidationError("La referencia no identifica una raíz familiar de un nivel; requiere revisión.")
    if obj.titular_id not in (None, titular.pk):
        raise ValidationError("Existe otro titular registrado; no se reemplaza desde el lote.")
    return obj, titular, fuente_titular


def proponer(*, afiliado, usuario, importacion_id, fila):
    requerir_financiador(usuario, afiliado.financiador_id)
    lote = get_object_or_404(m.Importacion, pk=importacion_id, financiador_id=afiliado.financiador_id)
    obj, titular, _ = _resolver(lote, afiliado, fila)
    return {"titular": titular.pk, "revision": obj.revision, "revision_titular": titular.revision}


@transaction.atomic
def confirmar(*, afiliado, usuario, importacion_id, fila, titular, revision, revision_titular):
    requerir_financiador(usuario, afiliado.financiador_id, escritura=True)
    lote = get_object_or_404(m.Importacion.objects.select_for_update(), pk=importacion_id,
                            financiador_id=afiliado.financiador_id)
    m.Financiador.objects.select_for_update(no_key=True).get(pk=lote.financiador_id)
    obj, raiz, _ = _resolver(lote, afiliado, fila)
    list(m.Afiliado.objects.select_for_update().filter(pk__in=[obj.pk, raiz.pk]).order_by("pk"))
    # Una edición de identidad puede preceder a estos locks: releer, no confiar
    # en la propuesta ni en la consulta previa a bloquear ambas personas.
    obj, raiz, fuente_raiz = _resolver(lote, afiliado, fila)
    if raiz.pk != titular:
        raise ValidationError("El titular esperado no coincide; consulte nuevamente la propuesta.")
    padron.comprobar_revision(obj, revision)
    padron.comprobar_revision(raiz, revision_titular)
    return padron.editar_ficha(
        afiliado=obj, usuario=usuario, origen="importacion", lote=lote,
        entrada={"revision": revision, "titular": raiz.pk,
                 "motivo": f"Vínculo OSTEL: lote {lote.pk}, fila {fila}, titular en fila {fuente_raiz['fila']}."},
    )
