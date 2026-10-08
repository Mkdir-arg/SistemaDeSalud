"""Documenta el token del portal en el esquema OpenAPI."""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class PortalEsquema(OpenApiAuthenticationExtension):
    target_class = "apps.portal.autenticacion.PortalAuthentication"
    name = "portal"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "Token del portal del paciente, de `POST /api/mi/cuenta/ingresar/`. "
                "No sirve contra la API institucional, y el JWT del sistema no sirve acá."
            ),
        }
