"""Revisión opaca del estado exacto del asiento; no es un contador histórico.

A -> B -> A restaura la misma revisión: el contrato compara el estado actual
con el leído. No permite detectar cambios intermedios ni promete una secuencia
monótona. La revisión no sustituye permisos, autoría ni el sello de firma.
"""
from datetime import datetime, timezone
import json

from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework.exceptions import APIException, ValidationError


REVISION_REQUERIDA = "Se requiere la revisión del borrador mostrado."
REVISION_OBSOLETA = "El borrador cambió desde que lo leíste. Revisá la versión actual antes de guardar o firmar."


class RevisionBorradorObsoleta(APIException):
    status_code = 409
    default_detail = REVISION_OBSOLETA


def revision_de_entrada(entrada):
    # Campos concretos incluyen relaciones por ID y todo el estado de firma.
    # Fechas conservan microsegundos: truncarlas podría omitir un cambio real.
    estado = {}
    for campo in entrada._meta.concrete_fields:
        valor = getattr(entrada, campo.attname)
        if isinstance(valor, datetime):
            valor = valor.astimezone(timezone.utc).isoformat(timespec="microseconds")
        estado[campo.attname] = valor
    estado["ciudadano_id"] = entrada.historia.ciudadano_id
    canonico = json.dumps(estado, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "rev1." + salted_hmac("registros.revision-borrador.v1", canonico, algorithm="sha256").hexdigest()


def coincide_revision(entrada, esperada):
    return isinstance(esperada, str) and bool(esperada) and constant_time_compare(esperada, revision_de_entrada(entrada))


def exigir_revision(entrada, esperada):
    """Invocar después de permisos/autoría y dentro del lock Historia -> Entrada."""
    if not esperada:
        raise ValidationError({"revision_esperada": [REVISION_REQUERIDA]})
    if not coincide_revision(entrada, esperada):
        raise RevisionBorradorObsoleta()
