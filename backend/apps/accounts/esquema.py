"""El autenticador durable conserva el contrato HTTP Bearer JWT existente."""
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class JWTInstitucionalEsquema(SimpleJWTScheme):
    target_class = "apps.accounts.autenticacion.AutenticacionInstitucional"
