"""
Endpoints de la cuenta del paciente: `/api/mi/cuenta/*` y `/api/mi/perfil/`.

Ninguna vista de este módulo usa la cadena de autenticación global: las
públicas no autentican y las demás aceptan sólo el token del portal (ver
`autenticacion.py`).
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from . import correo, renaper
from .autenticacion import EsCuentaDelPortal, IdentidadValidada, PortalAuthentication
from .limites import limites
from .models import CuentaPaciente, EnlacePortal, EventoPortal
from .serializers import (
    CambiarContrasenaSerializer,
    CuentaSerializer,
    EmailSerializer,
    IngresoSerializer,
    MensajeSerializer,
    PerfilSerializer,
    RenovarSerializer,
    RestablecerSerializer,
    SesionSerializer,
    ValidarIdentidadSerializer,
    normalizar_email,
    validar_contrasena,
)
from .tokens import (
    abrir_sesion,
    anular_enlaces,
    consumir_enlace,
    emitir_enlace,
    enlace_vigente,
    renovar_sesion,
    revocar_sesiones,
)

# R3: el mismo texto exista o no el email.
MENSAJE_REGISTRO = (
    "Si el email es válido, te mandamos un correo para confirmarlo. "
    "Revisá tu casilla, también la carpeta de spam."
)
MENSAJE_RECUPERO = (
    "Si hay una cuenta con ese email, te mandamos un correo para elegir una contraseña nueva."
)
ENLACE_INVALIDO = "El enlace no es válido, ya se usó o venció. Pedí uno nuevo."

ETIQUETA = ["portal"]

# Cuánto dura la marca de «consulta a RENAPER en curso» si el proceso muere a
# mitad de camino. Tiene que superar al timeout de la consulta: si venciera
# antes, un segundo pedido lanzaría otra consulta en paralelo.
CONSULTA_EN_CURSO_MINIMO_SEGUNDOS = 60


def _consulta_en_curso_segundos():
    return max(CONSULTA_EN_CURSO_MINIMO_SEGUNDOS, 3 * settings.RENAPER_TIMEOUT)


def _error(detail, codigo, estado, **extra):
    return Response({"detail": detail, "codigo": codigo, **extra}, status=estado)


def _ip(request):
    return BaseThrottle().get_ident(request) or ""


def _evento(request, tipo, cuenta=None, email="", **detalle):
    EventoPortal.objects.create(
        tipo=tipo,
        cuenta=cuenta,
        email=(email or (cuenta.email if cuenta else ""))[:254],
        ip=_ip(request)[:64],
        detalle=detalle,
    )


def _sesion(sesion, acceso, renovacion):
    return {
        "access": acceso,
        "refresh": renovacion,
        "access_vence": sesion.acceso_vence,
        "cuenta": CuentaSerializer(sesion.cuenta).data,
    }


class _LimitesQueCortan:
    """El primer límite que rechaza corta, y los siguientes no cuentan el pedido.

    DRF evalúa todos los límites aunque uno ya haya rechazado, y cada uno anota
    el pedido. Así, desde una sola IP ya frenada se seguía llenando el cupo por
    email de otra persona hasta dejarla sin ingresar.
    """

    def check_throttles(self, request):
        for limite in self.get_throttles():
            if not limite.allow_request(request, self):
                self.throttled(request, limite.wait())


class _Publica(_LimitesQueCortan, APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class _ConCuenta(_LimitesQueCortan, APIView):
    authentication_classes = [PortalAuthentication]
    permission_classes = [EsCuentaDelPortal]


class RegistroView(_Publica):
    throttle_classes = limites(ip="portal_alta_ip", email="portal_alta_email")

    @extend_schema(tags=ETIQUETA, summary="Crear cuenta", request=EmailSerializer,
                   responses={202: MensajeSerializer})
    def post(self, request):
        """Sólo el email. La contraseña se elige al abrir el enlace del correo.

        Si se eligiera acá, quien registra antes (o después) el email de otra
        persona decidiría la clave de la cuenta que esa persona confirma al
        abrir su correo. Con la clave elegida desde el enlace, la cuenta es de
        quien tiene la casilla, sin importar quién o cuántas veces la registró.
        """
        datos = EmailSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        email = datos.validated_data["email"]

        cuenta = CuentaPaciente.objects.filter(email=email).first()
        if cuenta is None:
            try:
                with transaction.atomic():
                    cuenta = CuentaPaciente(email=email)
                    cuenta.set_unusable_password()
                    cuenta.save()
            except IntegrityError:
                # Otro registro con el mismo email ganó la carrera.
                cuenta = CuentaPaciente.objects.get(email=email)
            else:
                _evento(request, EventoPortal.Tipo.ALTA, cuenta)
        if not cuenta.activa:
            pass
        elif cuenta.email_verificado:
            correo.ya_registrada(cuenta)
        else:
            correo.verificacion(cuenta, emitir_enlace(cuenta, EnlacePortal.Tipo.VERIFICACION))
        return Response({"detail": MENSAJE_REGISTRO}, status=status.HTTP_202_ACCEPTED)


class ReenviarVerificacionView(_Publica):
    throttle_classes = limites(ip="portal_alta_ip", email="portal_alta_email")

    @extend_schema(tags=ETIQUETA, summary="Reenviar el correo de verificación", request=EmailSerializer,
                   responses={202: MensajeSerializer})
    def post(self, request):
        datos = EmailSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        cuenta = CuentaPaciente.objects.filter(
            email=datos.validated_data["email"], activa=True, email_verificado_at__isnull=True
        ).first()
        if cuenta is not None:
            correo.verificacion(cuenta, emitir_enlace(cuenta, EnlacePortal.Tipo.VERIFICACION))
        return Response({"detail": MENSAJE_REGISTRO}, status=status.HTTP_202_ACCEPTED)


def _canjear_enlace(request, tipo, evento):
    """Gasta un enlace del correo y fija la contraseña que eligió quien lo abrió.

    Devuelve la cuenta, o la `Response` de error. La contraseña se valida antes
    de gastar el enlace: si no cumple, se corrige y se reintenta con el mismo.
    Abrir el enlace prueba que la casilla es suya, así que también confirma el
    email y cierra cualquier sesión anterior.
    """
    datos = RestablecerSerializer(data=request.data)
    datos.is_valid(raise_exception=True)
    token, crudo = datos.validated_data["token"], datos.validated_data["password"]
    cuenta = enlace_vigente(token, tipo)
    if cuenta is None:
        return _error(ENLACE_INVALIDO, "enlace_invalido", status.HTTP_400_BAD_REQUEST)
    try:
        validar_contrasena(crudo, cuenta)
    except ValidationError as exc:
        return Response({"password": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        cuenta = consumir_enlace(token, tipo)
        if cuenta is None:
            return _error(ENLACE_INVALIDO, "enlace_invalido", status.HTTP_400_BAD_REQUEST)
        cuenta.set_password(crudo)
        campos = ["password"]
        if not cuenta.email_verificado:
            cuenta.email_verificado_at = timezone.now()
            campos.append("email_verificado_at")
        cuenta.save(update_fields=campos)
        revocar_sesiones(cuenta)
        anular_enlaces(cuenta)
        _evento(request, evento, cuenta)
    return cuenta


class VerificarEmailView(_Publica):
    throttle_classes = limites(ip="portal_enlace_ip")

    @extend_schema(tags=ETIQUETA, summary="Confirmar el email y elegir la contraseña", request=RestablecerSerializer,
                   responses={200: SesionSerializer, 400: MensajeSerializer})
    def post(self, request):
        cuenta = _canjear_enlace(request, EnlacePortal.Tipo.VERIFICACION, EventoPortal.Tipo.EMAIL_VERIFICADO)
        if isinstance(cuenta, Response):
            return cuenta
        _evento(request, EventoPortal.Tipo.INGRESO, cuenta)
        return Response(_sesion(*abrir_sesion(cuenta)))


class IngresarView(_Publica):
    # Por email e IP frena la fuerza bruta desde una máquina sin dejar que un
    # tercero bloquee a la titular desde otra; el tope por email, más alto,
    # frena la que se reparte entre muchas IP.
    throttle_classes = limites(
        ip="portal_ingreso_ip", email_ip="portal_ingreso_email_ip", email="portal_ingreso_email"
    )

    @extend_schema(tags=ETIQUETA, summary="Ingresar con email y contraseña", request=IngresoSerializer,
                   responses={200: SesionSerializer, 401: MensajeSerializer})
    def post(self, request):
        datos = IngresoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        email = normalizar_email(datos.validated_data["email"])
        crudo = datos.validated_data["password"]
        cuenta = CuentaPaciente.objects.filter(email=email, activa=True).first()
        if cuenta is None:
            make_password(crudo)  # mismo tiempo que una contraseña equivocada
            correcta = False
        else:
            # Sin email confirmado la cuenta no tiene contraseña usable (se elige
            # con el enlace), y la respuesta es la misma que con una clave mala:
            # un 403 propio diría qué cuentas están confirmadas.
            correcta = cuenta.check_password(crudo) and cuenta.email_verificado
        if not correcta:
            _evento(request, EventoPortal.Tipo.INGRESO_FALLIDO, cuenta, email=email)
            return _error("Email o contraseña incorrectos.", "credenciales_invalidas", status.HTTP_401_UNAUTHORIZED)
        _evento(request, EventoPortal.Tipo.INGRESO, cuenta)
        return Response(_sesion(*abrir_sesion(cuenta)))


class RenovarView(_Publica):
    throttle_classes = limites(ip="portal_renovar_ip")

    @extend_schema(tags=ETIQUETA, summary="Renovar la sesión", request=RenovarSerializer,
                   responses={200: SesionSerializer, 401: MensajeSerializer})
    def post(self, request):
        datos = RenovarSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        renovada = renovar_sesion(datos.validated_data["refresh"])
        if renovada is None:
            return _error("La sesión venció. Ingresá de nuevo.", "sesion_vencida", status.HTTP_401_UNAUTHORIZED)
        return Response(_sesion(*renovada))


class OlvideView(_Publica):
    throttle_classes = limites(ip="portal_recupero_ip", email="portal_recupero_email")

    @extend_schema(tags=ETIQUETA, summary="Pedir el correo para elegir una contraseña nueva",
                   request=EmailSerializer, responses={202: MensajeSerializer})
    def post(self, request):
        datos = EmailSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        cuenta = CuentaPaciente.objects.filter(email=datos.validated_data["email"], activa=True).first()
        if cuenta is not None:
            correo.recupero(cuenta, emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO))
        return Response({"detail": MENSAJE_RECUPERO}, status=status.HTTP_202_ACCEPTED)


class RestablecerView(_Publica):
    throttle_classes = limites(ip="portal_enlace_ip")

    @extend_schema(tags=ETIQUETA, summary="Elegir una contraseña nueva con el enlace del correo",
                   request=RestablecerSerializer, responses={200: MensajeSerializer, 400: MensajeSerializer})
    def post(self, request):
        cuenta = _canjear_enlace(request, EnlacePortal.Tipo.RECUPERO, EventoPortal.Tipo.CONTRASENA_RESTABLECIDA)
        if isinstance(cuenta, Response):
            return cuenta
        return Response({"detail": "Listo, cambiaste tu contraseña. Ingresá con la nueva."})


class CuentaView(_ConCuenta):
    @extend_schema(tags=ETIQUETA, summary="Mi cuenta", responses={200: CuentaSerializer})
    def get(self, request):
        return Response(CuentaSerializer(request.user).data)


class SalirView(_ConCuenta):
    @extend_schema(tags=ETIQUETA, summary="Cerrar sesión", request=None, responses={204: None})
    def post(self, request):
        request.auth.revocada_at = timezone.now()
        request.auth.save(update_fields=["revocada_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CambiarContrasenaView(_ConCuenta):
    throttle_classes = limites(cuenta="portal_cuenta")

    @extend_schema(tags=ETIQUETA, summary="Cambiar la contraseña", request=CambiarContrasenaSerializer,
                   responses={200: MensajeSerializer})
    def post(self, request):
        cuenta = request.user
        datos = CambiarContrasenaSerializer(data=request.data, context={"cuenta": cuenta})
        datos.is_valid(raise_exception=True)
        cuenta.set_password(datos.validated_data["nueva"])
        cuenta.save(update_fields=["password"])
        revocar_sesiones(cuenta, salvo=request.auth)
        anular_enlaces(cuenta)
        _evento(request, EventoPortal.Tipo.CONTRASENA_CAMBIADA, cuenta)
        return Response({"detail": "Listo, cambiaste tu contraseña."})


class ValidarIdentidadView(_ConCuenta):
    throttle_classes = limites(ip="portal_identidad_ip", cuenta="portal_cuenta")

    @extend_schema(
        tags=ETIQUETA,
        summary="Validar la identidad contra RENAPER",
        request=ValidarIdentidadSerializer,
        responses={
            200: CuentaSerializer,
            403: OpenApiResponse(MensajeSerializer, description="El email no está confirmado."),
            409: OpenApiResponse(MensajeSerializer, description="Ya validada, o el documento es de otra cuenta."),
            422: OpenApiResponse(MensajeSerializer, description="RENAPER no confirmó los datos."),
            423: OpenApiResponse(MensajeSerializer, description="Superó los intentos permitidos."),
            503: OpenApiResponse(MensajeSerializer, description="RENAPER no está disponible."),
        },
    )
    def post(self, request):
        datos = ValidarIdentidadSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        cotejo = renaper.DatosCotejo(**datos.validated_data)

        # Una sola consulta a RENAPER por cuenta a la vez. Sin esto, varios
        # pedidos en paralelo pasaban todos el control de bloqueo antes de que
        # el primero contara su rechazo: más de N cotejos por bloqueo (R5), y
        # una validación podía terminar bien con la cuenta ya bloqueada.
        ahora = timezone.now()
        with transaction.atomic():
            cuenta = CuentaPaciente.objects.select_for_update().get(pk=request.user.pk)
            rechazo = self._rechazo_previo(cuenta, ahora)
            if rechazo is not None:
                return rechazo
            cuenta.validacion_en_curso_hasta = ahora + timedelta(seconds=_consulta_en_curso_segundos())
            cuenta.save(update_fields=["validacion_en_curso_hasta"])

        try:
            resultado = renaper.adaptador().cotejar(cotejo)
        except renaper.RenaperNoDisponible:
            resultado = None
        except Exception:
            CuentaPaciente.objects.filter(pk=cuenta.pk).update(validacion_en_curso_hasta=None)
            raise

        with transaction.atomic():
            cuenta = CuentaPaciente.objects.select_for_update().get(pk=cuenta.pk)
            cuenta.validacion_en_curso_hasta = None
            cuenta.save(update_fields=["validacion_en_curso_hasta"])
            # Lo que se miró antes de consultar puede haber cambiado mientras
            # tanto (un bloqueo desde el admin, otra validación): con la fila
            # bloqueada se vuelve a mirar antes de aplicar el resultado.
            if cuenta.validada:
                return _error("Tu identidad ya está validada.", "ya_validada", status.HTTP_409_CONFLICT)
            if cuenta.validacion_bloqueada():
                return self._bloqueada(cuenta)
            if resultado is None:
                _evento(request, EventoPortal.Tipo.RENAPER_NO_DISPONIBLE, cuenta)
                return _error(
                    "No pudimos validar tu identidad ahora. Probá de nuevo más tarde; este intento no cuenta.",
                    "servicio_no_disponible",
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return self._aplicar(request, cuenta, cotejo, resultado)

    def _rechazo_previo(self, cuenta, ahora):
        if not cuenta.email_verificado:
            return _error("Primero confirmá tu email.", "email_sin_verificar", status.HTTP_403_FORBIDDEN)
        if cuenta.validada:
            return _error("Tu identidad ya está validada.", "ya_validada", status.HTTP_409_CONFLICT)
        if cuenta.validacion_bloqueada(ahora):
            return self._bloqueada(cuenta)
        if cuenta.validacion_en_curso_hasta and cuenta.validacion_en_curso_hasta > ahora:
            return _error(
                "Ya estamos validando tu identidad. Esperá unos segundos.",
                "validacion_en_curso",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return None

    def _aplicar(self, request, cuenta, cotejo, resultado):
        """Aplica la respuesta de RENAPER con la fila bloqueada."""
        detalle = {"documento": cotejo.documento, "sexo": cotejo.sexo}
        if not resultado.coincide:
            return self._no_coincide(request, cuenta, {**detalle, "motivo": resultado.motivo})

        titular = self._titular(cotejo.documento, cuenta)
        if titular is None:
            cuenta.documento = cotejo.documento
            cuenta.sexo = cotejo.sexo
            cuenta.identidad = CuentaPaciente.Identidad.VALIDADA
            cuenta.identidad_via = CuentaPaciente.Via.RENAPER
            cuenta.identidad_validada_at = timezone.now()
            cuenta.nombre = resultado.nombre
            cuenta.apellido = resultado.apellido
            cuenta.fecha_nacimiento = resultado.fecha_nacimiento
            cuenta.intentos_validacion = 0
            try:
                with transaction.atomic():
                    cuenta.save()
            except IntegrityError:
                # Otra cuenta validó el mismo documento al mismo tiempo.
                titular = CuentaPaciente.objects.filter(
                    documento=cotejo.documento, identidad=CuentaPaciente.Identidad.VALIDADA
                ).first()
            else:
                _evento(request, EventoPortal.Tipo.IDENTIDAD_VALIDADA, cuenta, via="renaper", **detalle)
                return Response(CuentaSerializer(cuenta).data)

        # R2: el documento ya es de otra cuenta. Se rechaza y se avisa a la titular.
        _evento(request, EventoPortal.Tipo.DOCUMENTO_EN_USO, cuenta, titular=titular.pk if titular else None,
                **detalle)
        if titular is not None:
            correo.documento_en_uso(titular)
        return _error(
            "Ese documento ya está validado en otra cuenta. Si es tuyo, ingresá con esa cuenta o recuperá su "
            "contraseña.",
            "documento_en_uso",
            status.HTTP_409_CONFLICT,
        )

    @staticmethod
    def _titular(documento, cuenta):
        return (
            CuentaPaciente.objects.filter(documento=documento, identidad=CuentaPaciente.Identidad.VALIDADA)
            .exclude(pk=cuenta.pk)
            .first()
        )

    def _no_coincide(self, request, cuenta, detalle):
        cuenta.intentos_validacion += 1
        if cuenta.intentos_validacion >= settings.PORTAL_VALIDACION_INTENTOS:
            cuenta.intentos_validacion = 0
            cuenta.validacion_bloqueada_hasta = timezone.now() + timedelta(hours=settings.PORTAL_VALIDACION_BLOQUEO_HORAS)
            cuenta.save(update_fields=["intentos_validacion", "validacion_bloqueada_hasta"])
            _evento(request, EventoPortal.Tipo.IDENTIDAD_RECHAZADA, cuenta, **detalle)
            _evento(request, EventoPortal.Tipo.VALIDACION_BLOQUEADA, cuenta,
                    hasta=cuenta.validacion_bloqueada_hasta.isoformat())
            return self._bloqueada(cuenta)
        cuenta.save(update_fields=["intentos_validacion"])
        _evento(request, EventoPortal.Tipo.IDENTIDAD_RECHAZADA, cuenta, **detalle)
        restantes = settings.PORTAL_VALIDACION_INTENTOS - cuenta.intentos_validacion
        return _error(
            "RENAPER no confirmó esos datos. Revisalos tal como figuran en tu DNI.",
            "no_coincide",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            intentos_restantes=restantes,
        )

    @staticmethod
    def _bloqueada(cuenta):
        return _error(
            "Superaste los intentos para validar tu identidad. Vas a poder probar de nuevo más tarde.",
            "validacion_bloqueada",
            status.HTTP_423_LOCKED,
            bloqueada_hasta=cuenta.validacion_bloqueada_hasta,
        )


class PerfilView(_ConCuenta):
    permission_classes = [IdentidadValidada]

    @extend_schema(tags=ETIQUETA, summary="Mis datos validados", responses={200: PerfilSerializer})
    def get(self, request):
        return Response(PerfilSerializer(request.user).data)
