"""Sesiones JWT durables. Orden de escrituras: Usuario → Sesión.

El refresh consumido se rechaza sin revocar la renovación ganadora. No cambia
pertenencias institucionales ni administra las cookies de Django o el portal.
"""
import hashlib
import uuid
from contextvars import ContextVar
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

# Corte de pertenencias de la solicitud: (usuario_id, inicio de sesión, ids de
# institución y de financiador con baja posterior, o None si aún no se
# consultaron). Lo fija el autenticador y lo limpia CorteMembresiasMiddleware al
# entrar y al salir de cada solicitud.
_corte = ContextVar("accounts_corte_membresias", default=None)


def activar_corte_membresias(usuario_id, inicio):
    _corte.set([usuario_id, inicio, None, None])


def limpiar_corte_membresias():
    _corte.set(None)


def aplicar_corte_membresias(qs):
    corte = _corte.get()
    if corte is None:
        return qs
    usuario_id, inicio, cortadas, _ = corte
    if cortadas is None:
        from .models import BajaMembresia

        # Una sola consulta por solicitud; las bajas no se cachean entre ellas.
        cortadas = set(BajaMembresia.objects.filter(
            usuario_id=usuario_id, momento__gte=inicio,
        ).values_list("institucion_id", flat=True))
        corte[2] = cortadas
    if not cortadas:
        return qs
    ids = [i for i in cortadas if i is not None]
    if ids:
        qs = qs.exclude(usuario_id=usuario_id, institucion_id__in=ids)
    if None in cortadas:
        qs = qs.exclude(usuario_id=usuario_id, institucion__isnull=True)
    return qs


def aplicar_corte_financiadores(qs):
    """La misma regla para `MembresiaFinanciador`, con su propia consulta perezosa."""
    corte = _corte.get()
    if corte is None:
        return qs
    usuario_id, inicio, _, cortados = corte
    if cortados is None:
        from apps.financiadores.models import BajaMembresiaFinanciador

        cortados = set(BajaMembresiaFinanciador.objects.filter(
            usuario_id=usuario_id, momento__gte=inicio,
        ).values_list("financiador_id", flat=True))
        corte[3] = cortados
    if cortados:
        qs = qs.exclude(usuario_id=usuario_id, financiador_id__in=cortados)
    return qs


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
