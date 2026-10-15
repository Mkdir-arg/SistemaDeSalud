"""La renovación conserva la misma revocación por contraseña que el acceso."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password


class TokenRefreshInstitucionalSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        usuario_model = get_user_model()
        with transaction.atomic():
            try:
                usuario = usuario_model.objects.select_for_update().get(
                    **{api_settings.USER_ID_FIELD: token.get(api_settings.USER_ID_CLAIM)}
                )
            except (usuario_model.DoesNotExist, ValueError, TypeError, OverflowError):
                raise InvalidToken("La sesión ya no es válida.") from None
            huella = token.get(api_settings.REVOKE_TOKEN_CLAIM)
            if (not api_settings.USER_AUTHENTICATION_RULE(usuario)
                    or not isinstance(huella, str)
                    or not constant_time_compare(huella, get_md5_hash_password(usuario.password))):
                raise InvalidToken("La sesión ya no es válida.")
            # El lock impide cambiar la contraseña o borrar el usuario entre
            # esta comprobación y la renovación de SimpleJWT.
            return super().validate(attrs)
