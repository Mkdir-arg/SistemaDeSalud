"""Autoservicio institucional separado del portal de pacientes y simulaciones."""
import logging
import time

from django.conf import settings
from django.core.cache import caches
from django.utils.crypto import salted_hmac
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.portal.limites import origen

from . import credenciales

log = logging.getLogger(__name__)


class _LimiteInstitucional(SimpleRateThrottle):
    def __init__(self, clave, *, destino=None):
        self.clave = clave
        self.destino = destino
        self.scope = f"institucional_{clave}"
        self.rate = settings.INSTITUCIONAL_THROTTLE_RATES[clave]
        self.num_requests, self.duration = self.parse_rate(self.rate)

    @property
    def cache(self):
        return caches["portal"]

    def get_cache_key(self, request, view):
        if self.clave == "ip":
            identidad = origen(self, request)
        elif self.clave == "usuario":
            if not request.user.is_authenticated:
                return None
            identidad = str(request.user.pk)
        else:
            datos = request.data if isinstance(request.data, dict) else {}
            identidad = str(self.destino if self.destino is not None else (
                datos.get("email") or datos.get("nuevo_email") or datos.get("uid") or ""
            )).strip().lower()[:512]
        huella = salted_hmac("accounts.institucional.throttle", identidad).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": huella}


def limites_institucionales(*, destino=None):
    """Mismos cupos por origen, identidad destino y actor para ambas vías."""
    return [_LimiteInstitucional(clave, destino=destino) for clave in ("ip", "email", "usuario")]


class _CredencialesView(APIView):
    permission_classes = [AllowAny]

    def initial(self, request, *args, **kwargs):
        credenciales.exigir_configuracion_correo()
        if "HTTP_X_PLEXO_SIMULACION" in request.META or getattr(request, "simulacion", None):
            raise PermissionDenied("Esta operación no admite simulación.")
        super().initial(request, *args, **kwargs)

    def get_throttles(self):
        return limites_institucionales()

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def datos(self, serializer_class, request):
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class _EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class _PasswordSerializer(serializers.Serializer):
    nueva_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)


class _ResetSerializer(_PasswordSerializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=4096)


class _CambioPasswordSerializer(_PasswordSerializer):
    password_actual = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)


class _CambioEmailSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)
    nuevo_email = serializers.EmailField(max_length=254)


class _ConfirmacionEmailSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=4096)
    nuevo_email = serializers.EmailField(max_length=254)


class _MensajeSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RecuperacionInstitucionalView(_CredencialesView):
    authentication_classes = []
    serializer_class = _EmailSerializer

    @extend_schema(request=_EmailSerializer, responses={202: _MensajeSerializer})
    def post(self, request):
        datos = self.datos(_EmailSerializer, request)
        credenciales.solicitar_recuperacion_publica(datos["email"])
        return Response(credenciales.MENSAJE_GENERICO, status=202)


class RestablecerPasswordInstitucionalView(_CredencialesView):
    authentication_classes = []
    serializer_class = _ResetSerializer

    @extend_schema(request=_ResetSerializer, responses={204: None})
    def post(self, request):
        datos = self.datos(_ResetSerializer, request)
        credenciales.restablecer_password(datos["uid"], datos["token"], datos["nueva_password"])
        return Response(status=204)


class CambiarPasswordInstitucionalView(_CredencialesView):
    permission_classes = [IsAuthenticated]
    serializer_class = _CambioPasswordSerializer

    @extend_schema(request=_CambioPasswordSerializer, responses={204: None})
    def post(self, request):
        datos = self.datos(_CambioPasswordSerializer, request)
        credenciales.cambiar_password(request.user, datos["password_actual"], datos["nueva_password"])
        return Response(status=204)


class CambioEmailInstitucionalView(_CredencialesView):
    permission_classes = [IsAuthenticated]
    serializer_class = _CambioEmailSerializer

    @extend_schema(request=_CambioEmailSerializer, responses={202: _MensajeSerializer})
    def post(self, request):
        datos = self.datos(_CambioEmailSerializer, request)
        credenciales.solicitar_cambio_email(request.user, datos["password_actual"], datos["nuevo_email"])
        return Response(credenciales.MENSAJE_GENERICO, status=202)


class ConfirmarEmailInstitucionalView(_CredencialesView):
    authentication_classes = []
    serializer_class = _ConfirmacionEmailSerializer

    @extend_schema(request=_ConfirmacionEmailSerializer, responses={204: None})
    def post(self, request):
        datos = self.datos(_ConfirmacionEmailSerializer, request)
        credenciales.confirmar_email(datos["uid"], datos["token"], datos["nuevo_email"])
        return Response(status=204)


class _LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)

    def validate(self, attrs):
        if set(self.initial_data) != {"refresh"}:
            raise serializers.ValidationError({"detail": "Enviá únicamente el refresh de la sesión a cerrar."})
        return attrs


MENSAJE_LOGIN_LIMITADO = "Demasiados intentos fallidos. Esperá unos minutos antes de volver a intentar."


def _claves_login(request):
    """Huellas del email y de la IP del intento; el email nunca va en claro al caché."""
    datos = request.data if isinstance(request.data, dict) else {}
    email = str(datos.get("email") or "").strip().lower()[:254]
    ip = origen(BaseThrottle(), request) or ""
    return {
        "email": salted_hmac("accounts.login.email", email).hexdigest(),
        "ip": salted_hmac("accounts.login.ip", ip).hexdigest(),
    }


def _reloj():
    # Punto único para las pruebas: parchar `time.time` alteraría todo el proceso.
    return time.time()


def _ventana_login():
    ventana = settings.INSTITUCIONAL_LOGIN_VENTANA_SEGUNDOS
    ahora = _reloj()
    return int(ahora // ventana), max(1, int(ventana - ahora % ventana)), ventana


def _clave_cache(tipo, huella, bloque):
    return f"accounts_login:{tipo}:{huella}:{bloque}"


def _espera_login(claves):
    """Segundos hasta el próximo intento si se agotó algún cupo, o 0."""
    bloque, restante, _ = _ventana_login()
    limites = {"email": settings.INSTITUCIONAL_LOGIN_FALLOS_EMAIL, "ip": settings.INSTITUCIONAL_LOGIN_FALLOS_IP}
    try:
        cache = caches["portal"]
        for tipo, limite in limites.items():
            if cache.get(_clave_cache(tipo, claves[tipo], bloque), 0) >= limite:
                return restante
    except Exception:
        # Sin caché no se bloquea el ingreso de un hospital; queda registrado.
        log.exception("límite de login institucional no disponible")
    return 0


def _contar_fallo_login(claves):
    bloque, _, ventana = _ventana_login()
    try:
        cache = caches["portal"]
        for tipo, huella in claves.items():
            clave = _clave_cache(tipo, huella, bloque)
            cache.add(clave, 0, timeout=ventana * 2)
            try:
                cache.incr(clave)
            except ValueError:
                cache.set(clave, 1, timeout=ventana * 2)
    except Exception:
        log.exception("límite de login institucional no disponible")


class LoginInstitucionalView(TokenObtainPairView):
    """Login con límite de intentos fallidos por email y por IP (#172, AUD-010).

    Solo cuentan los fallos de autenticación. Con el cupo agotado responde 429
    genérico aunque las credenciales sean correctas, para no confirmar cuáles lo
    son. Ventana fija en el caché compartido entre workers; su incremento no es
    atómico, así que una ráfaga paralela puede pasar algún intento de más.
    """

    def post(self, request, *args, **kwargs):
        claves = _claves_login(request)
        espera = _espera_login(claves)
        if espera:
            return Response({"detail": MENSAJE_LOGIN_LIMITADO}, status=429, headers={"Retry-After": str(espera)})
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            _contar_fallo_login(claves)
            raise


class LogoutInstitucionalView(APIView):
    # El refresh firmado del cuerpo es la autoridad. Un access vencido o cookie
    # ajena no deben impedir cerrar la sesión indicada ni cambiar su identidad.
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = _LogoutSerializer

    def get_authenticate_header(self, request):
        # APIView sin autenticadores convertiría AuthenticationFailed en 403.
        return "Bearer"

    def initial(self, request, *args, **kwargs):
        if "HTTP_X_PLEXO_SIMULACION" in request.META or getattr(request, "simulacion", None):
            raise PermissionDenied("Esta operación no admite simulación.")
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    @extend_schema(request=_LogoutSerializer, responses={204: None, 401: _MensajeSerializer})
    def post(self, request):
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        from .sesiones import MENSAJE_INVALIDO, revocar_sesion

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            revocar_sesion(serializer.validated_data["refresh"])
        except TokenError:
            raise InvalidToken(MENSAJE_INVALIDO) from None
        return Response(status=204)
