"""Sesiones JWT durables. Orden de escrituras: Usuario → Sesión.

El refresh consumido se rechaza sin revocar la renovación ganadora. No cambia
pertenencias institucionales ni administra las cookies de Django o el portal.
"""
import hashlib
import uuid
from datetime import datetime, timezone as tz

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from .models import SesionInstitucional

MENSAJE_INVALIDO = "La sesión ya no es válida."


def huella_jti(token):
    jti = token.get(api_settings.JTI_CLAIM)
    if not isinstance(jti, str) or not jti:
        raise InvalidToken(MENSAJE_INVALIDO)
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def vencimiento_refresh(token):
    return datetime.fromtimestamp(token["exp"], tz=tz.utc)


def validar_usuario_token(usuario, token):
    huella = token.get(api_settings.REVOKE_TOKEN_CLAIM)
    if (not api_settings.USER_AUTHENTICATION_RULE(usuario)
            or not isinstance(huella, str)
            or not constant_time_compare(huella, get_md5_hash_password(usuario.password))):
        raise InvalidToken(MENSAJE_INVALIDO)


def bloquear_usuario_token(token):
    modelo = get_user_model()
    try:
        usuario = modelo.objects.select_for_update().get(
            **{api_settings.USER_ID_FIELD: token.get(api_settings.USER_ID_CLAIM)}
        )
    except (modelo.DoesNotExist, ValueError, TypeError, OverflowError):
        raise InvalidToken(MENSAJE_INVALIDO) from None
    validar_usuario_token(usuario, token)
    return usuario


def sesion_de_token(token, usuario, *, bloquear=False, permitir_revocada=False):
    try:
        sid = token.get("sid")
        if not isinstance(sid, str):
            raise ValueError
        sid = uuid.UUID(sid)
    except (ValueError, TypeError, AttributeError):
        raise InvalidToken(MENSAJE_INVALIDO) from None
    consulta = SesionInstitucional.objects
    if bloquear:
        consulta = consulta.select_for_update()
    try:
        sesion = consulta.get(pk=sid, usuario_id=usuario.pk)
    except SesionInstitucional.DoesNotExist:
        raise InvalidToken(MENSAJE_INVALIDO) from None
    if ((sesion.revocada_at is not None and not permitir_revocada)
            or sesion.refresh_vence <= timezone.now()):
        raise InvalidToken(MENSAJE_INVALIDO)
    return sesion


def exigir_refresh_vigente(sesion, token):
    if not constant_time_compare(sesion.refresh_jti_hash, huella_jti(token)):
        raise InvalidToken(MENSAJE_INVALIDO)


def _marcar_revocada(sesion):
    if sesion.revocada_at is None:
        sesion.revocada_at = timezone.now()
        sesion.save(update_fields=["revocada_at"])


@transaction.atomic
def revocar_sesion(refresh_crudo):
    # Firma, propósito y expiración se verifican antes de tocar las filas.
    token = RefreshToken(refresh_crudo)
    usuario = bloquear_usuario_token(token)
    sesion = sesion_de_token(token, usuario, bloquear=True, permitir_revocada=True)
    exigir_refresh_vigente(sesion, token)
    _marcar_revocada(sesion)
