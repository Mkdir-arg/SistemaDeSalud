"""Login y refresh institucionales con familia revocable en PostgreSQL."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from .models import SesionInstitucional
from .sesiones import (
    MENSAJE_INVALIDO, bloquear_usuario_token, exigir_refresh_vigente,
    huella_jti, sesion_de_token, vencimiento_refresh,
)


class TokenObtainPairInstitucionalSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Reusar autenticación y extensiones de SimpleJWT. Estos tokens aún no
        # salen del proceso; se vinculan a la fila durable antes de responder.
        datos = super().validate(attrs)
        modelo = get_user_model()
        with transaction.atomic():
            try:
                usuario = modelo.objects.select_for_update().get(pk=self.user.pk)
            except modelo.DoesNotExist:
                raise InvalidToken(MENSAJE_INVALIDO) from None
            # La contraseña validada no puede cambiar entre autenticar y emitir.
            if (not api_settings.USER_AUTHENTICATION_RULE(usuario)
                    or not constant_time_compare(usuario.password, self.user.password)):
                raise InvalidToken(MENSAJE_INVALIDO)
            self.user = usuario
            refresh = self.token_class(datos["refresh"])
            sesion = SesionInstitucional.objects.create(
                usuario=usuario, refresh_jti_hash=huella_jti(refresh),
                refresh_vence=vencimiento_refresh(refresh),
            )
            refresh["sid"] = str(sesion.pk)
            datos["refresh"] = str(refresh)
            datos["access"] = str(refresh.access_token)
        return datos


class TokenRefreshInstitucionalSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        with transaction.atomic():
            usuario = bloquear_usuario_token(token)
            sesion = sesion_de_token(token, usuario, bloquear=True)
            exigir_refresh_vigente(sesion, token)
            # La huella ya se validó bajo lock de Usuario. Mantener super()
            # bajo ambos locks conserva extensiones y la rotación/TTL rolling.
            datos = super().validate(attrs)
            if "refresh" not in datos:
                raise InvalidToken(MENSAJE_INVALIDO)
            sustituto = self.token_class(datos["refresh"])
            sesion.refresh_jti_hash = huella_jti(sustituto)
            sesion.refresh_vence = vencimiento_refresh(sustituto)
            sesion.save(update_fields=["refresh_jti_hash", "refresh_vence"])
        return datos
