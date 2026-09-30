"""Documenta el encabezado de simulación en el esquema OpenAPI."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SimulacionEsquema(OpenApiAuthenticationExtension):
    target_class = "apps.simulacion.autenticacion.SimulacionAuthentication"
    name = "simulacion"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-HEN-Simulacion",
            "description": (
                "Id de una sesión de simulación, junto con el token JWT del mismo "
                "superusuario. El pedido se autoriza con la cuenta de referencia."
            ),
        }
