"""Credenciales institucionales; intención durable y envío por worker separado."""
import logging
from smtplib import SMTPRecipientsRefused, SMTPResponseException
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.throttling import SimpleRateThrottle

from apps.simulacion import contexto
from apps.simulacion.perfiles import es_cuenta_referencia

from .models import Usuario

log = logging.getLogger(__name__)
MENSAJE_GENERICO = {"detail": "Si corresponde, recibirás las instrucciones por correo."}


class CorreoInstitucionalNoDisponible(APIException):
    status_code = 503
    default_detail = "El servicio institucional no está disponible. Intentá nuevamente más tarde."


def exigir_configuracion_correo():
    """Fallar antes de consultar identidad o aceptar una operación sin políticas."""
    try:
        base = getattr(settings, "INSTITUCIONAL_URL_BASE", "")
        partes = urlsplit(base)
        local = (getattr(settings, "ENTORNO", "") in {"demo", "desarrollo"}
                 and partes.hostname in {"localhost", "127.0.0.1", "::1"})
        if (not partes.hostname or partes.username or partes.password or partes.query or partes.fragment
                or partes.path not in {"", "/"}
                or partes.scheme not in ({"https", "http"} if local else {"https"})):
            raise ValueError
        for nombre in ("INSTITUCIONAL_INVITACION_TIMEOUT", "INSTITUCIONAL_RECUPERACION_TIMEOUT", "INSTITUCIONAL_EMAIL_TIMEOUT"):
            valor = getattr(settings, nombre, None)
            if type(valor) is not int or valor <= 0:
                raise ValueError
        from .correo_outbox import politica

        politica()
        tasas = getattr(settings, "INSTITUCIONAL_THROTTLE_RATES", {})
        for clave in ("ip", "email", "usuario"):
            # parse_rate no depende de estado; evitar __init__, que consulta
            # DEFAULT_THROTTLE_RATES antes de tener un scope institucional.
            cantidad, periodo = SimpleRateThrottle.parse_rate(None, tasas[clave])
            if cantidad <= 0 or periodo <= 0:
                raise ValueError
        if settings.CACHES["portal"]["BACKEND"] != "django.core.cache.backends.db.DatabaseCache":
            raise ValueError
        if not isinstance(settings.EMAIL_TIMEOUT, (int, float)) or settings.EMAIL_TIMEOUT <= 0:
            raise ValueError
        validate_email(settings.DEFAULT_FROM_EMAIL)
        if getattr(settings, "ENTORNO", "") == "produccion" and (
            settings.EMAIL_BACKEND != "django.core.mail.backends.smtp.EmailBackend"
            or not settings.EMAIL_HOST
            or getattr(settings, "INSTITUCIONAL_PROVEEDOR_CONFIRMADO", False) is not True
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError, KeyError, DjangoValidationError):
        raise CorreoInstitucionalNoDisponible() from None


def es_elegible(usuario):
    return bool(usuario and usuario.is_active and not es_cuenta_referencia(usuario))


def exigir_titular(usuario):
    if contexto.actual() or not es_elegible(usuario):
        raise PermissionDenied("Esta operación requiere una cuenta personal activa.")


def _autorizar_operador(usuario, actor, institucion):
    if actor is None:
        return
    exigir_titular(actor)
    if actor.is_superuser:
        return
    from apps.common import tiene_capacidad

    privilegiado = usuario.is_staff or usuario.is_superuser or usuario.membresias.filter(
        activo=True, institucion__isnull=True,
    ).exists()
    if privilegiado:
        raise PermissionDenied("No tenés autorización para iniciar esta solicitud.")
    if tiene_capacidad(actor, "gobierno_plataforma"):
        return
    if (institucion is None
            or not tiene_capacidad(actor, "config_institucional", institucion.pk)
            or not usuario.membresias.filter(institucion=institucion, activo=True).exists()):
        raise PermissionDenied("No tenés autorización para iniciar esta solicitud.")


def _programar(solicitud):
    exigir_configuracion_correo()
    from .correo_outbox import encolar

    try:
        # El savepoint permite sanitizar el error fuera de la transacción que
        # falló. El APIException revierte también el alta/cambio del llamador.
        with transaction.atomic():
            encolar(solicitud)
    except (DatabaseError, ValueError, TypeError, OverflowError):
        log.error("credenciales institucionales: no se pudo persistir la solicitud")
        raise CorreoInstitucionalNoDisponible() from None


def invitar_usuario(usuario, *, actor=None, institucion=None):
    exigir_configuracion_correo()
    if contexto.actual():
        raise PermissionDenied("Esta operación no admite simulación.")
    _autorizar_operador(usuario, actor, institucion)
    if es_elegible(usuario) and not usuario.has_usable_password():
        _programar({"tipo": "invitacion", "usuario_id": usuario.pk,
                    "actor_id": actor.pk if actor else None,
                    "institucion_id": institucion.pk if institucion else None})


def solicitar_recuperacion(usuario, *, actor=None, institucion=None):
    exigir_configuracion_correo()
    if contexto.actual():
        raise PermissionDenied("Esta operación no admite simulación.")
    _autorizar_operador(usuario, actor, institucion)
    if es_elegible(usuario):
        _programar({"tipo": "recuperacion", "usuario_id": usuario.pk,
                    "actor_id": actor.pk if actor else None,
                    "institucion_id": institucion.pk if institucion else None})


def solicitar_recuperacion_publica(email):
    # No buscar la cuenta en este request: existan o no las instrucciones,
    # siempre se acepta el mismo tipo de trabajo y se responde igual.
    _programar({"tipo": "recuperacion", "email": email})


class _GeneradorInstitucional(PasswordResetTokenGenerator):
    def __init__(self, proposito):
        super().__init__()
        self.key_salt = f"accounts.institucional.{proposito}"
        self.vigencia = getattr(settings, f"INSTITUCIONAL_{proposito.upper()}_TIMEOUT")

    def _make_hash_value(self, user, timestamp):
        # Django ya liga password/email/login; la revisión evita ABA del email
        # sin introducir una tabla o alterar el generador del portal paciente.
        return f"{super()._make_hash_value(user, timestamp)}|{user.actualizado.isoformat()}"

    def check_token(self, user, token):
        # Mismo algoritmo de Django, con plazo por propósito en esta instancia;
        # no mutar PASSWORD_RESET_TIMEOUT global durante requests concurrentes.
        if not user or not token:
            return False
        try:
            timestamp, _ = token.split("-")
            timestamp = base36_to_int(timestamp)
        except (ValueError, TypeError):
            return False
        if not any(constant_time_compare(self._make_token_with_timestamp(user, timestamp, secreto), token)
                   for secreto in [self.secret, *self.secret_fallbacks]):
            return False
        edad = self._num_seconds(self._now()) - timestamp
        return 0 <= edad <= self.vigencia


def _estado_email(usuario):
    # Reusar la revisión temporal existente impide revivir el enlace A→B→A.
    # También invalida enlaces pendientes cuando se actualiza el perfil.
    return salted_hmac("accounts.institucional.estado-email", f"{usuario.pk}|{usuario.email}|{usuario.password}|{usuario.actualizado.isoformat()}").hexdigest()


def bloquear_destino_email(email):
    """Serializar alta/confirmación sobre la misma equivalencia SQL que iexact."""
    if connection.vendor != "postgresql" or not connection.in_atomic_block:
        raise CorreoInstitucionalNoDisponible()
    with connection.cursor() as cursor:
        # El lock dura hasta commit/rollback; colisiones del hash solo hacen
        # esperar destinos distintos. No guardar el email como clave ni log.
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(UPPER(%s), 172))", [email])


def _destino_email(email):
    return salted_hmac("accounts.institucional.destino-email", email).hexdigest()


def _enlace(ruta, **datos):
    return f"{settings.INSTITUCIONAL_URL_BASE.rstrip('/')}/{ruta}#{urlencode(datos)}"


def _enviar(destino, asunto, cuerpo):
    try:
        conexion = get_connection(timeout=settings.EMAIL_TIMEOUT)
        enviados = EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destino], connection=conexion).send()
        return "enviado" if enviados == 1 else "error"
    except SMTPRecipientsRefused as error:
        codigos = [respuesta[0] for respuesta in error.recipients.values()]
        permanente = bool(codigos) and all(isinstance(codigo, int) and 500 <= codigo < 600 for codigo in codigos)
        log.error("credenciales institucionales: destinatario rechazado por proveedor")
        return "error_permanente" if permanente else "error"
    except SMTPResponseException as error:
        log.error("credenciales institucionales: rechazo del proveedor")
        return "error_permanente" if 500 <= error.smtp_code < 600 else "error"
    except Exception:  # noqa: BLE001
        # No incluir excepción, correo, enlaces ni cuerpo en registros.
        log.error("credenciales institucionales: fallo de envío; requiere reintento")
        return "error"


def _resultado_envios(*resultados):
    if all(resultado == "enviado" for resultado in resultados):
        return "enviado"
    return "error_permanente" if "error_permanente" in resultados else "error"


def procesar_solicitud_correo(solicitud):
    """Resolver elegibilidad y generar enlaces solo al consumir la outbox."""
    exigir_configuracion_correo()
    from .models import CorreoInstitucionalOutbox

    estado = CorreoInstitucionalOutbox.Estado
    tipo = solicitud.get("tipo")
    if tipo not in {"invitacion", "recuperacion", "email", "email-confirmado"}:
        return estado.DESCARTADO
    if "usuario_id" in solicitud:
        usuario = Usuario.objects.filter(pk=solicitud["usuario_id"]).first()
    else:
        # Una colisión legacy por case no se resuelve eligiendo una identidad.
        usuarios = list(Usuario.objects.filter(email__iexact=solicitud["email"])[:2])
        usuario = usuarios[0] if len(usuarios) == 1 else None
    if not es_elegible(usuario):
        return estado.DESCARTADO
    if solicitud.get("actor_id"):
        from apps.instituciones.models import Institucion

        actor = Usuario.objects.filter(pk=solicitud["actor_id"]).first()
        institucion = Institucion.objects.filter(pk=solicitud.get("institucion_id")).first()
        if actor is None:
            return estado.DESCARTADO
        try:
            _autorizar_operador(usuario, actor, institucion)
        except PermissionDenied:
            return estado.DESCARTADO
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    if tipo in {"invitacion", "recuperacion"}:
        if tipo == "invitacion" and usuario.has_usable_password():
            return estado.DESCARTADO
        proposito = "recuperacion" if usuario.has_usable_password() else "invitacion"
        token = f"{proposito}.{_GeneradorInstitucional(proposito).make_token(usuario)}"
        enlace = _enlace("restablecer-acceso", uid=uid, token=token)
        enviado = _enviar(usuario.email, "Tu acceso institucional", f"Para establecer tu contraseña, abrí:\n\n{enlace}\n\nSi no pediste esto, ignorá este correo.")
    elif tipo == "email":
        if not constant_time_compare(solicitud["estado"], _estado_email(usuario)):
            return estado.DESCARTADO
        nuevo = solicitud["nuevo_email"]
        if Usuario.objects.filter(email__iexact=nuevo).exists():
            return estado.DESCARTADO
        token = signing.dumps({"uid": uid, "estado": _estado_email(usuario), "destino": _destino_email(nuevo)},
                              salt="accounts.institucional.confirmar-email")
        enlace = _enlace("confirmar-email", uid=uid, token=token, nuevo_email=nuevo)
        enviado = _enviar(nuevo, "Confirmá tu email institucional", f"Para confirmar el cambio, abrí:\n\n{enlace}\n\nSi no pediste esto, ignorá este correo.")
        aviso = _enviar(usuario.email, "Solicitud de cambio de email institucional", "Se solicitó cambiar el email de tu cuenta. El cambio requiere confirmar la nueva dirección. Si no lo solicitaste, contactá al soporte.")
        enviado = _resultado_envios(enviado, aviso)
    elif tipo == "email-confirmado":
        enviado = _enviar(usuario.email, "Email institucional actualizado", "Se confirmó el cambio de email de tu cuenta institucional.")
        aviso = _enviar(solicitud["email_anterior"], "Email institucional actualizado", "Se confirmó el cambio de email de tu cuenta institucional. Si no lo solicitaste, contactá al soporte.")
        enviado = _resultado_envios(enviado, aviso)
    else:
        return estado.DESCARTADO
    log.info("credenciales institucionales: procesamiento tipo=%s usuario_id=%s actor_id=%s institucion_id=%s resultado=%s",
             tipo, usuario.pk, solicitud.get("actor_id"), solicitud.get("institucion_id"), enviado)
    return enviado


def _usuario_bloqueado(uid):
    try:
        pk = urlsafe_base64_decode(uid).decode()
        return Usuario.objects.select_for_update().get(pk=pk)
    except (ValueError, TypeError, UnicodeDecodeError, OverflowError, Usuario.DoesNotExist):
        raise ValidationError({"detail": "El enlace no es válido o venció."}) from None


def _guardar_password(usuario, nueva):
    try:
        validate_password(nueva, user=usuario)
    except DjangoValidationError as error:
        raise ValidationError({"nueva_password": error.messages}) from None
    usuario.set_password(nueva)
    usuario.save(update_fields=["password", "actualizado"])


def restablecer_password(uid, token, nueva):
    exigir_configuracion_correo()
    with transaction.atomic():
        usuario = _usuario_bloqueado(uid)
        try:
            proposito, crudo = token.split(".", 1)
            valido = proposito in {"invitacion", "recuperacion"} and _GeneradorInstitucional(proposito).check_token(usuario, crudo)
        except (ValueError, TypeError):
            valido = False
        if not es_elegible(usuario) or not valido:
            raise ValidationError({"detail": "El enlace no es válido o venció."})
        _guardar_password(usuario, nueva)


def cambiar_password(usuario, actual, nueva):
    exigir_configuracion_correo()
    with transaction.atomic():
        titular = Usuario.objects.select_for_update().get(pk=usuario.pk)
        exigir_titular(titular)
        if not titular.check_password(actual):
            raise ValidationError({"password_actual": "La contraseña actual no es válida."})
        _guardar_password(titular, nueva)


def solicitar_cambio_email(usuario, actual, nuevo):
    exigir_configuracion_correo()
    with transaction.atomic():
        titular = Usuario.objects.select_for_update().get(pk=usuario.pk)
        exigir_titular(titular)
        if not titular.check_password(actual):
            raise ValidationError({"password_actual": "La contraseña actual no es válida."})
        # Encolar también destinos ocupados: la aceptación y el costo del
        # adapter no deben convertirse en una consulta de existencia.
        _programar({"tipo": "email", "usuario_id": titular.pk,
                    "nuevo_email": nuevo, "estado": _estado_email(titular)})


def confirmar_email(uid, token, nuevo):
    exigir_configuracion_correo()
    try:
        datos = signing.loads(token, salt="accounts.institucional.confirmar-email",
                              max_age=settings.INSTITUCIONAL_EMAIL_TIMEOUT)
    except signing.BadSignature:
        raise ValidationError({"detail": "El enlace no es válido o venció."}) from None
    try:
        with transaction.atomic():
            usuario = _usuario_bloqueado(uid)
            if (not es_elegible(usuario) or datos.get("uid") != uid
                    or not constant_time_compare(datos.get("estado", ""), _estado_email(usuario))
                    or not constant_time_compare(datos.get("destino", ""), _destino_email(nuevo))):
                raise ValidationError({"detail": "El enlace no es válido o venció."})
            bloquear_destino_email(nuevo)
            if Usuario.objects.exclude(pk=usuario.pk).filter(email__iexact=nuevo).exists():
                raise ValidationError({"detail": "No se pudo confirmar el cambio de email."})
            anterior = usuario.email
            usuario.email = nuevo
            usuario.save(update_fields=["email", "actualizado"])
            _programar({"tipo": "email-confirmado", "usuario_id": usuario.pk, "email_anterior": anterior})
    except IntegrityError:
        raise ValidationError({"detail": "No se pudo confirmar el cambio de email."}) from None
