from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.registros.models import normalizar_documento

from .models import CuentaPaciente


def normalizar_email(valor):
    return str(valor or "").strip().lower()


def validar_contrasena(crudo, cuenta=None):
    try:
        validate_password(crudo, user=cuenta)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return crudo


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, valor):
        return normalizar_email(valor)


class IngresoSerializer(serializers.Serializer):
    # No es EmailField: un email mal escrito tiene que dar el mismo 401 que una
    # contraseña equivocada, no un 400 que diga otra cosa.
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(trim_whitespace=False, max_length=128)


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)


class RenovarSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=200)


class RestablecerSerializer(TokenSerializer):
    password = serializers.CharField(trim_whitespace=False, max_length=128)


class CambiarContrasenaSerializer(serializers.Serializer):
    actual = serializers.CharField(trim_whitespace=False, max_length=128)
    nueva = serializers.CharField(trim_whitespace=False, max_length=128)

    def validate_actual(self, valor):
        if not self.context["cuenta"].check_password(valor):
            raise serializers.ValidationError("La contraseña actual no es correcta.")
        return valor

    def validate_nueva(self, valor):
        return validar_contrasena(valor, self.context["cuenta"])


class ValidarIdentidadSerializer(serializers.Serializer):
    # Sin nombre ni apellido: los da RENAPER (ver renaper.py).
    documento = serializers.CharField(max_length=30)
    sexo = serializers.ChoiceField(choices=CuentaPaciente.Sexo.choices)
    numero_tramite = serializers.RegexField(
        # [0-9] y no \d: \d también acepta dígitos de otros alfabetos.
        r"^[0-9]{11}$",
        error_messages={"invalid": "Son los 11 números del trámite, al frente del DNI."},
    )

    def validate_documento(self, valor):
        documento = normalizar_documento(valor)
        # El cotejo de RENAPER es para el DNI: sólo números, 7 u 8 dígitos.
        if not documento.isascii() or not documento.isdigit():
            raise serializers.ValidationError("Ingresá el número de DNI, sin letras.")
        # «01234567» y «1234567» son el mismo DNI. Sin quitar los ceros, R2 los
        # veía como dos documentos y la misma persona podía validar dos cuentas.
        documento = documento.lstrip("0")
        if not 7 <= len(documento) <= 8:
            raise serializers.ValidationError("Ingresá el número de DNI, sin letras.")
        return documento


class CuentaSerializer(serializers.ModelSerializer):
    email_verificado = serializers.BooleanField(read_only=True)
    intentos_restantes = serializers.SerializerMethodField()

    class Meta:
        model = CuentaPaciente
        fields = [
            "email",
            "email_verificado",
            "identidad",
            "nombre",
            "apellido",
            "documento",
            "sexo",
            "identidad_validada_at",
            "validacion_bloqueada_hasta",
            "intentos_restantes",
        ]
        read_only_fields = fields

    def get_intentos_restantes(self, cuenta) -> int:
        if cuenta.validada or cuenta.validacion_bloqueada():
            return 0
        return max(settings.PORTAL_VALIDACION_INTENTOS - cuenta.intentos_validacion, 0)


class SesionSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    access_vence = serializers.DateTimeField()
    cuenta = CuentaSerializer()


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaPaciente
        fields = ["nombre", "apellido", "documento", "fecha_nacimiento"]
        read_only_fields = fields


class MensajeSerializer(serializers.Serializer):
    detail = serializers.CharField()
    codigo = serializers.CharField(required=False)
