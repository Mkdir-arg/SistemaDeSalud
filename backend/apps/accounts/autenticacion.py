"""Autenticación institucional: JWT y familia durable deben seguir vigentes."""
from rest_framework_simplejwt.authentication import JWTAuthentication

from .sesiones import sesion_de_token, validar_usuario_token


class AutenticacionInstitucional(JWTAuthentication):
    def get_user(self, validated_token):
        usuario = super().get_user(validated_token)
        validar_usuario_token(usuario, validated_token)
        sesion_de_token(validated_token, usuario)
        return usuario
