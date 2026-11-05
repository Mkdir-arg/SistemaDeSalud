"""Copia explícita desde evidencia OSTEL al bloque protegido de salud."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from . import models as m, padron
from .ostel_importacion import VERSION
from .permisos import requerir_padron_protegido


@transaction.atomic
def copiar_desde_importacion(*, afiliado, usuario, importacion_id, fila, revision):
    requerir_padron_protegido(usuario, afiliado.financiador_id, "salud", escritura=True)
    lote = get_object_or_404(
        m.Importacion.objects.select_for_update(),
        pk=importacion_id, financiador_id=afiliado.financiador_id,
    )
    if lote.version != VERSION or lote.tipo != "padron":
        raise ValidationError("Se requiere un lote de padrón OSTEL.")
    filas = [f for f in lote.filas if f.get("fila") == fila]
    if len(filas) != 1 or filas[0].get("estado") != "aplicada":
        raise ValidationError("Se requiere una única fila aplicada del lote.")
    fuente = filas[0]
    if fuente.get("afiliado") != afiliado.pk:
        raise ValidationError("La fila aplicada no corresponde al afiliado solicitado.")
    original = fuente.get("original") or {}
    codigo = original.get("CODPAR")
    limite = m.SaludPadron._meta.get_field("codpar_ostel").max_length
    if not isinstance(codigo, str) or not codigo.strip() or len(codigo) > limite:
        raise ValidationError("El CODPAR original debe ser texto no vacío de hasta 40 caracteres.")
    # No se vuelve a resolver identidad por NUMERO, CUIL ni NROAFI.
    # Lote antes de membresía/afiliado; el servicio conserva sus locks y revisión.
    motivo = f"Copia CODPAR OSTEL: lote {lote.pk}, hoja {fuente['hoja']}, fila Excel {fuente['fila_excel']}."
    return padron.editar_protegido(
        afiliado=afiliado, usuario=usuario, bloque="salud",
        entrada={"revision": revision, "motivo": motivo, "codpar_ostel": codigo},
    )
