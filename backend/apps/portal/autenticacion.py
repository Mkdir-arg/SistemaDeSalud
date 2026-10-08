"""
Autenticación y permisos de `/api/mi/*`.

El aislamiento va en las dos direcciones:

- **Token del portal contra la API institucional.** Esas vistas usan la cadena
  global (`SimulacionAuthentication`, `JWTAuthentication`, sesión). Ninguna
  conoce este autenticador, y el token del portal no es un JWT: simplejwt no lo
  puede decodificar y responde 401.
- **JWT del sistema contra el portal.** Las vistas del portal declaran
  `authentication_classes = [PortalAuthentication]` y nada más, así que no
  heredan la cadena global. Un JWT no está en `SesionPortal`: 401. La cookie
  de sesión del admin ni se mira.
"""
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.permissions import BasePermission

from .models import SesionPortal
from .tokens import hash_token

PALABRA_CLAVE = b"bearer"


class PortalAuthentication(BaseAuthentication):
    def authenticate(self, request):
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != PALABRA_CLAVE:
            return None
        if len(partes) != 2:
            raise exceptions.AuthenticationFailed("Encabezado de autorización inválido.")
        token = partes[1].decode("latin-1")
        sesion = (
            SesionPortal.objects.select_related("cuenta")
            .filter(
                acceso_hash=hash_token(token),
                revocada_at__isnull=True,
                acceso_vence__gt=timezone.now(),
                cuenta__activa=True,
            )
            .first()
        )
        if sesion is None:
            raise exceptions.AuthenticationFailed("La sesión venció o no es válida. Ingresá de nuevo.")
        return sesion.cuenta, sesion

    def authenticate_header(self, request):
        # Sin esto DRF convierte la falta de credenciales en 403 y no en 401.
        return 'Bearer realm="portal"'


class EsCuentaDelPortal(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.auth, SesionPortal)


class SinAcceso(exceptions.PermissionDenied):
    """403 con un `codigo` estable que la app usa para elegir la pantalla."""

    def __init__(self, detail, codigo):
        super().__init__({"detail": detail, "codigo": codigo})


class IdentidadValidada(EsCuentaDelPortal):
    """R1: sin email verificado y sin identidad validada no se ve ningún dato."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        cuenta = request.user
        if not cuenta.email_verificado:
            raise SinAcceso("Primero confirmá tu email.", "email_sin_verificar")
        if not cuenta.validada:
            raise SinAcceso("Todavía no validaste tu identidad.", "identidad_sin_validar")
        return True
