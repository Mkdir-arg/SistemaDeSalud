"""Operaciones de stock idempotentes por clave (#172, AUD-053).

Serializar bajo lock no vuelve idempotente una entrega: dos pedidos iguales de
10 unidades sobre un parcial mueven 20. Un reintento tras un timeout tampoco
puede saber si el primero se aplicó. Por eso cada operación lleva una `clave`
UUID: la primera vez se ejecuta y se registra junto con sus movimientos; la
misma clave con el mismo contenido devuelve ese resultado sin mover stock; con
otro contenido se rechaza. Dos reintentos simultáneos se ordenan en la
unicidad (institución, clave): el segundo espera al primero y lee su resultado.
"""
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError

from .models import OperacionStock


class ClaveReutilizada(APIException):
    status_code = 409
    default_detail = "Esta clave ya fue utilizada para otra operación. No se registró ningún cambio."
    default_code = "clave_reutilizada"


def clave_de(datos):
    try:
        return UUID(str(datos.get("clave")))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({"clave": "Indicá una clave de operación (UUID) y repetila al reintentar."}) from None


def _repetida(existente, tipo, solicitud):
    if existente.tipo != tipo or existente.solicitud != solicitud:
        raise ClaveReutilizada()
    return existente.resultado, True


def ejecutar(*, institucion_id, clave, tipo, solicitud, autor, operar):
    """Ejecuta `operar()` una sola vez por (institución, clave).

    `operar` devuelve el resultado serializable (solo ids). Devuelve
    `(resultado, repetida)`. Si `operar` falla, la clave no queda registrada.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():
                operacion = OperacionStock.objects.create(
                    institucion_id=institucion_id, clave=clave, tipo=tipo, solicitud=solicitud, autor=autor,
                )
        except IntegrityError:
            existente = OperacionStock.objects.select_for_update().get(institucion_id=institucion_id, clave=clave)
            return _repetida(existente, tipo, solicitud)
        resultado = operar()
        operacion.resultado = resultado
        operacion.save(update_fields=["resultado"])
        return resultado, False
