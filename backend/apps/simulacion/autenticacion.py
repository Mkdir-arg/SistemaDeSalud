"""
Separación entre la identidad autenticada y la identidad efectiva.

Con `X-HEN-Simulacion: <id de sesión>`, un pedido del superusuario se autoriza
como la cuenta de referencia de esa sesión:

- `request.user` es la cuenta, y con ella se evalúan todos los permisos y
  alcances existentes, que ya preguntan por `request.user`.
- `request.usuario_real` y `request.simulacion` conservan quién actúa y qué
  simula. La autoría se corrige en `contexto.py`.

El pedido falla cerrado: si la sesión terminó, venció, es de otro usuario, o la
cuenta dejó de coincidir con su perfil, se responde 403. Nunca se atiende con el
acceso total del superusuario, porque la pantalla cree estar simulando.

Las cuentas de referencia tampoco pueden iniciar sesión por su cuenta: el login
y el refresco de tokens las rechazan aunque alguien les ponga contraseña.
"""
import uuid

from django.contrib.auth.backends import ModelBackend
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.authentication import JWTAuthentication, default_user_authentication_rule

from . import contexto
from .models import SesionSimulacion
from .perfiles import es_cuenta_referencia, problema_de_sesion

ENCABEZADO = "HTTP_X_HEN_SIMULACION"


class SimulacionRechazada(APIException):
    """403 con una marca que el frontend usa para salir de la simulación."""

    status_code = 403
    default_code = "simulacion_rechazada"

    def __init__(self, motivo):
        super().__init__({"detail": motivo, "simulacion": "rechazada"})


class SimulacionAuthentication(JWTAuthentication):
    """Va primera en la cadena. Sin el encabezado no interviene."""

    def authenticate(self, request):
        sesion_id = request.META.get(ENCABEZADO)
        if ENCABEZADO not in request.META:
            return None
        # Un token vencido responde 401 como siempre, para que el frontend lo
        # renueve y reintente con el mismo encabezado.
        resultado = super().authenticate(request)
        if resultado is None:
            raise SimulacionRechazada("La simulación requiere la sesión del superusuario.")
        real, token = resultado
        if not (real.is_active and real.is_superuser):
            raise SimulacionRechazada("Solo un superusuario puede simular perfiles.")
        sesion = self._sesion(real, sesion_id)
        request._request.usuario_real = real
        request._request.simulacion = sesion
        contexto.activar(sesion, real)
        return sesion.cuenta, token

    @staticmethod
    def _sesion(real, sesion_id):
        try:
            uuid.UUID(str(sesion_id))
        except ValueError:
            raise SimulacionRechazada("La simulación no es válida.") from None
        sesion = SesionSimulacion.objects.select_related(
            "cuenta", "superusuario", "institucion", "financiador",
        ).filter(pk=sesion_id, superusuario=real).first()
        if sesion is None or sesion.finalizada is not None:
            raise SimulacionRechazada("La simulación terminó. Volvé a elegir un perfil.")
        problema = problema_de_sesion(sesion)
        if problema:
            fin, motivo = problema
            sesion.finalizar(fin)
            raise SimulacionRechazada(motivo)
        return sesion


class BackendSinCuentasDeReferencia(ModelBackend):
    """Login por email y contraseña, salvo para las cuentas de referencia."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not es_cuenta_referencia(user)


def regla_de_autenticacion(user):
    """`SIMPLE_JWT["USER_AUTHENTICATION_RULE"]`: vale para el login y el refresco."""
    return default_user_authentication_rule(user) and not es_cuenta_referencia(user)
