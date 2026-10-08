"""
Correos del portal.

El proveedor se elige por variables de entorno (`EMAIL_*`, ver settings). Con
SMTP alcanza para cualquier proveedor sin sumar dependencias. **Es provisorio:**
el proveedor de producción todavía no está elegido; se resuelve en el #123.

**Un correo que no sale no cambia la respuesta.** Registro y recupero tienen que
contestar lo mismo exista o no el email (R3). Si un fallo de envío devolviera un
error sólo cuando la cuenta existe, el error mismo diría que existe. Por eso el
fallo se registra en el log, sin el destinatario ni el enlace, y el pedido
sigue igual.

**El SMTP no cambia el tiempo de respuesta.** A un email sin cuenta no se le
manda nada; si el envío fuera dentro del pedido, la demora (de cientos de ms a
segundos) diría cuáles tienen cuenta. Sale en un hilo aparte, después de
confirmar la transacción (`PORTAL_CORREO_EN_SEGUNDO_PLANO`). Si el proceso se
reinicia justo en ese momento, el correo se pierde y el paciente lo vuelve a
pedir. Queda una diferencia de pocos milisegundos por las escrituras del enlace
en la base: es un riesgo aceptado, acotado por los límites de intentos.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

log = logging.getLogger(__name__)

FIRMA = "\n\n—\nMi portal de salud\nSi no pediste esto, ignorá este correo."


def _url(ruta, token):
    # El token va en el fragmento: el navegador no lo manda al servidor, así
    # que no queda en los logs de nginx ni sale en el Referer.
    return f"{settings.PORTAL_URL_BASE.rstrip('/')}{ruta}#token={token}"


def _mandar(destino, asunto, cuerpo, motivo):
    try:
        send_mail(asunto, cuerpo + FIRMA, settings.DEFAULT_FROM_EMAIL, [destino], fail_silently=False)
    except Exception as exc:  # noqa: BLE001
        log.error("portal: no se pudo enviar el correo de %s (%s)", motivo, type(exc).__name__)


def _enviar(destino, asunto, cuerpo, motivo):
    if not settings.PORTAL_CORREO_EN_SEGUNDO_PLANO:
        _mandar(destino, asunto, cuerpo, motivo)
        return
    hilo = threading.Thread(target=_mandar, args=(destino, asunto, cuerpo, motivo), daemon=True)
    transaction.on_commit(hilo.start)


def verificacion(cuenta, token):
    _enviar(
        cuenta.email,
        "Confirmá tu email",
        "Para terminar de crear tu cuenta, abrí este enlace y elegí tu contraseña:\n\n"
        f"{_url('/mi/verificar-email', token)}\n\n"
        f"Vence en {settings.PORTAL_VERIFICACION_HORAS} horas y sirve una sola vez.",
        "verificación",
    )


def ya_registrada(cuenta):
    _enviar(
        cuenta.email,
        "Ya tenés una cuenta",
        "Alguien intentó crear una cuenta con este email, pero ya tenés una.\n\n"
        f"Para entrar: {settings.PORTAL_URL_BASE.rstrip('/')}/mi/ingresar\n"
        f"Si no recordás la contraseña: {settings.PORTAL_URL_BASE.rstrip('/')}/mi/olvide",
        "cuenta existente",
    )


def recupero(cuenta, token):
    _enviar(
        cuenta.email,
        "Elegí una contraseña nueva",
        "Para elegir una contraseña nueva, abrí este enlace:\n\n"
        f"{_url('/mi/restablecer', token)}\n\n"
        f"Vence en {settings.PORTAL_RECUPERO_MINUTOS} minutos y sirve una sola vez.",
        "recupero",
    )


def documento_en_uso(cuenta):
    _enviar(
        cuenta.email,
        "Intentaron validar tu documento en otra cuenta",
        "Alguien intentó validar tu documento en una cuenta distinta de la tuya y lo rechazamos. "
        "Tu cuenta sigue igual.\n\n"
        "Si fuiste vos con otro email, ingresá con el de esta cuenta. Si no fuiste vos, "
        "te recomendamos cambiar tu contraseña.",
        "documento en uso",
    )
