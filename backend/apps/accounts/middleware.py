"""Limpia el corte de pertenencias de la sesión en cada solicitud.

Un hilo del servidor atiende muchas solicitudes: la siguiente no puede heredar
el corte de la anterior, ni un worker sin solicitud quedar con uno puesto.
"""
from .sesiones import limpiar_corte_membresias


class CorteMembresiasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        limpiar_corte_membresias()
        try:
            return self.get_response(request)
        finally:
            limpiar_corte_membresias()
