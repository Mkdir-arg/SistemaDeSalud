"""Autenticación institucional: JWT y familia durable deben seguir vigentes."""
from rest_framework_simplejwt.authentication import JWTAuthentication

from .sesiones import activar_corte_membresias, sesion_de_token, validar_usuario_token


class AutenticacionInstitucional(JWTAuthentication):
    def get_user(self, validated_token):
        usuario = super().get_user(validated_token)
        validar_usuario_token(usuario, validated_token)
        sesion = sesion_de_token(validated_token, usuario)
        # Pertenencias dadas de baja después de este login no vuelven a valer
        # en esta sesión aunque se reactiven (#172, D-c).
        activar_corte_membresias(usuario.pk, sesion.creada)
        return usuario
