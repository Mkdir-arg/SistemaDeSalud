"""
Bordes del pedido simulado: limpieza, rutas sin simulación y registro.

- El contexto de la simulación se limpia al entrar y al salir de cada pedido:
  un hilo del servidor atiende muchos pedidos y el siguiente no puede heredar
  la simulación del anterior.
- Si una vista no autentica con `SimulacionAuthentication` (vistas que no son
  de DRF o que declaran otros autenticadores), el encabezado se rechaza. Sin
  este control, esa vista atendería con el acceso total del superusuario
  mientras la pantalla muestra un perfil simulado.
- Cada escritura simulada queda en `OperacionSimulada`, con su resultado. Si no se
  puede registrar, se revierte la transacción y se responde 503.
"""
import logging
from contextlib import nullcontext

from django.db import transaction
from django.http import JsonResponse

from . import contexto
from .autenticacion import ENCABEZADO, SimulacionAuthentication
from .models import OperacionSimulada

log = logging.getLogger(__name__)
METODOS_DE_LECTURA = {"GET", "HEAD", "OPTIONS"}


class ErrorRegistroSimulacion(Exception):
    pass


def _admite_simulacion(view_func):
    cls = getattr(view_func, "cls", None)
    if cls is None:
        return False
    iniciales = getattr(view_func, "initkwargs", None) or {}
    clases = iniciales.get("authentication_classes", getattr(cls, "authentication_classes", ()))
    return any(issubclass(c, SimulacionAuthentication) for c in clases)


class SimulacionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        contexto.limpiar()
        try:
            escritura = ENCABEZADO in request.META and request.method not in METODOS_DE_LECTURA
            try:
                with transaction.atomic() if escritura else nullcontext():
                    respuesta = self.get_response(request)
                    self._registrar(request, respuesta)
                    return respuesta
            except ErrorRegistroSimulacion:
                return JsonResponse(
                    {"detail": "No se pudo registrar la operación simulada. No se aplicó la operación."}, status=503,
                )
        finally:
            contexto.limpiar()

    def process_view(self, request, view_func, view_args, view_kwargs):
        if ENCABEZADO in request.META and not _admite_simulacion(view_func):
            return JsonResponse(
                {"detail": "Esta ruta no admite simulación.", "simulacion": "rechazada"}, status=403,
            )
        return None

    @staticmethod
    def _registrar(request, respuesta):
        sesion = getattr(request, "simulacion", None)
        if sesion is None or request.method in METODOS_DE_LECTURA:
            return
        try:
            OperacionSimulada.objects.create(
                sesion=sesion, metodo=request.method, ruta=request.path[:300], estado=respuesta.status_code,
            )
        except Exception as exc:
            log.exception("no se pudo registrar la operación simulada")
            raise ErrorRegistroSimulacion() from exc
