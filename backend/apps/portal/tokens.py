"""Tokens del portal: sesiones y enlaces de un solo uso.

Todos son 32 bytes aleatorios. En la base se guarda el SHA-256 y no un hash
lento: con 256 bits de entropía no hay diccionario que probar, y la búsqueda
por hash exacto evita comparar a mano.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import EnlacePortal, SesionPortal

# El prefijo hace que un token del portal se reconozca a simple vista (en un
# reporte, en un log que no debería tenerlo) y que no se parezca a un JWT.
PREFIJO = "hp_"


def nuevo_token():
    return PREFIJO + secrets.token_urlsafe(32)


def hash_token(token):
    return hashlib.sha256(str(token).encode()).hexdigest()


def abrir_sesion(cuenta):
    """Crea una sesión y devuelve `(sesion, acceso, renovacion)` en claro."""
    ahora = timezone.now()
    acceso, renovacion = nuevo_token(), nuevo_token()
    sesion = SesionPortal.objects.create(
        cuenta=cuenta,
        acceso_hash=hash_token(acceso),
        acceso_vence=ahora + timedelta(minutes=settings.PORTAL_ACCESO_MINUTOS),
        renovacion_hash=hash_token(renovacion),
        renovacion_vence=ahora + timedelta(minutes=settings.PORTAL_RENOVACION_MINUTOS),
        vence_maximo=ahora + timedelta(hours=settings.PORTAL_SESION_MAXIMA_HORAS),
    )
    return sesion, acceso, renovacion


def renovar_sesion(renovacion):
    """Rota los dos tokens. El de renovación viejo deja de servir.

    Devuelve `(sesion, acceso, renovacion)` o `None` si el token no sirve.
    """
    ahora = timezone.now()
    with transaction.atomic():
        sesion = (
            SesionPortal.objects.select_for_update()
            .select_related("cuenta")
            .filter(
                renovacion_hash=hash_token(renovacion),
                revocada_at__isnull=True,
                renovacion_vence__gt=ahora,
                vence_maximo__gt=ahora,
                cuenta__activa=True,
            )
            .first()
        )
        if sesion is None:
            return None
        acceso, nueva = nuevo_token(), nuevo_token()
        sesion.acceso_hash = hash_token(acceso)
        sesion.acceso_vence = min(ahora + timedelta(minutes=settings.PORTAL_ACCESO_MINUTOS), sesion.vence_maximo)
        sesion.renovacion_hash = hash_token(nueva)
        sesion.renovacion_vence = min(
            ahora + timedelta(minutes=settings.PORTAL_RENOVACION_MINUTOS), sesion.vence_maximo
        )
        sesion.save(update_fields=["acceso_hash", "acceso_vence", "renovacion_hash", "renovacion_vence"])
    return sesion, acceso, nueva


def revocar_sesiones(cuenta, salvo=None):
    qs = SesionPortal.objects.filter(cuenta=cuenta, revocada_at__isnull=True)
    if salvo is not None:
        qs = qs.exclude(pk=salvo.pk)
    qs.update(revocada_at=timezone.now())


def anular_enlaces(cuenta):
    """Borra los enlaces sin usar de la cuenta, de los dos tipos.

    Se llama cada vez que cambia la contraseña: un enlace que quedó en una
    casilla no puede servir después para cambiarla otra vez.
    """
    EnlacePortal.objects.filter(cuenta=cuenta, usado_at__isnull=True).delete()


def emitir_enlace(cuenta, tipo):
    """Crea un enlace y anula los anteriores del mismo tipo sin usar.

    Así sólo sirve el último correo: si el paciente pidió dos recuperos, el
    primero ya no abre nada.
    """
    vigencia = {
        EnlacePortal.Tipo.VERIFICACION: timedelta(hours=settings.PORTAL_VERIFICACION_HORAS),
        EnlacePortal.Tipo.RECUPERO: timedelta(minutes=settings.PORTAL_RECUPERO_MINUTOS),
    }[tipo]
    token = nuevo_token()
    with transaction.atomic():
        EnlacePortal.objects.filter(cuenta=cuenta, tipo=tipo, usado_at__isnull=True).delete()
        EnlacePortal.objects.create(
            cuenta=cuenta, tipo=tipo, token_hash=hash_token(token), vence=timezone.now() + vigencia
        )
    return token


def _enlaces_vigentes(token, tipo):
    return EnlacePortal.objects.filter(
        token_hash=hash_token(token), tipo=tipo, usado_at__isnull=True, vence__gt=timezone.now(), cuenta__activa=True
    )


def enlace_vigente(token, tipo):
    """La cuenta del enlace si todavía sirve, sin gastarlo."""
    enlace = _enlaces_vigentes(token, tipo).select_related("cuenta").first()
    return enlace.cuenta if enlace else None


def consumir_enlace(token, tipo):
    """Marca el enlace como usado y devuelve su cuenta, o `None` si no sirve.

    El `UPDATE ... WHERE usado_at IS NULL` es lo que lo hace de un solo uso
    aunque lleguen dos clics a la vez: sólo uno actualiza la fila.
    """
    filtro = _enlaces_vigentes(token, tipo)
    enlace = filtro.select_related("cuenta").first()
    if enlace is None or not filtro.filter(pk=enlace.pk).update(usado_at=timezone.now()):
        return None
    return enlace.cuenta
