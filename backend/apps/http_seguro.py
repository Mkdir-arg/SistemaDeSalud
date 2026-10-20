"""Transporte de integraciones: el destino autorizado no puede redirigir.

No altera el opener global ni reemplaza la autorización del destino inicial.
DNS, proxies y política de egreso pertenecen a la configuración operacional.
"""
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, build_opener


class _SinRedirecciones(HTTPRedirectHandler):
    def http_error_302(self, request, respuesta, codigo, motivo, encabezados):
        # Rechazar antes de interpretar Location o construir otro Request.
        # No conservar URL, encabezados, cuerpo ni un socket abierto en el error.
        respuesta.close()
        raise HTTPError("", codigo, "Redirección rechazada.", None, None)

    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302
    http_error_308 = http_error_302


def abrir_sin_redirecciones(pedido, timeout):
    """Mismo Request y timeout existentes, sin seguir ningún redirect HTTP."""
    return build_opener(_SinRedirecciones()).open(pedido, timeout=timeout)
