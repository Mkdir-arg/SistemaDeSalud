"""Confirmación OSTEL con respuestas acotadas y recuperación de estado."""
from copy import deepcopy
from hashlib import sha256
import json


def huella_lote(lote):
    estado = {"id": lote.pk, "version": lote.version, "estado": lote.estado,
              "resumen": lote.resumen, "filas": lote.filas}
    contenido = json.dumps(estado, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    return sha256(contenido).hexdigest()


def marcar_respuesta(lote, *, huella_cliente, huella_base, anteriores):
    """La huella es control de sincronización; nunca permiso ni identidad."""
    lote.huella_lote = huella_lote(lote)
    lote.modo_respuesta = "completa"
    if huella_cliente and huella_cliente == huella_base:
        lote.modo_respuesta = "cambios"
        lote.base_huella = huella_base
        lote.filas_cambiadas = [fila for fila in lote.filas
                               if anteriores[fila["fila"]] != fila]
    return lote


def confirmar_con_cambios(*, importacion, usuario, huella_cliente=None):
    from django.db import transaction
    from .models import Importacion
    from .ostel_importacion import aplicar

    # Sólo v3: conserva la unidad de commit de #186 (una tanda), nunca envuelve
    # el importador genérico de transacciones por fila en una transacción nueva.
    with transaction.atomic():
        lote = Importacion.objects.select_for_update().get(pk=importacion.pk)
        base = huella_lote(lote)
        anteriores = {fila["fila"]: deepcopy(fila) for fila in lote.filas} if huella_cliente == base else {}
        # aplicar conserva autorización, locks, validación y auditoría de #186.
        resultado = aplicar(importacion=lote, usuario=usuario)
    # Los objetos locales son snapshots; no se recarga después de liberar el
    # lock. Formatear fuera conserva commit antes de respuesta, como en #186.
    return marcar_respuesta(resultado, huella_cliente=huella_cliente,
                            huella_base=base, anteriores=anteriores)
