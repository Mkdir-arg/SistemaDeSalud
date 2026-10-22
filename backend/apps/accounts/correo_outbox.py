"""Outbox PostgreSQL: SMTP al menos una vez, con reservas y reintentos acotados.

No abre hilos ni envía al importar. El UUID impide que un worker con lease viejo
reescriba el resultado de otro; no hace idempotente al servidor SMTP.
"""
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import connection, transaction
from django.db.models import Count, Min, Q
from django.utils import timezone

from .models import CorreoInstitucionalOutbox

log = logging.getLogger(__name__)
Estado = CorreoInstitucionalOutbox.Estado
TERMINALES = (Estado.ENVIADO, Estado.DESCARTADO, Estado.ERROR)


def politica():
    from .credenciales import CorreoInstitucionalNoDisponible

    opciones = getattr(settings, "INSTITUCIONAL_OUTBOX_POLITICA", {})
    claves = ("max_intentos", "lease_segundos", "backoff_inicial_segundos", "backoff_maximo_segundos", "espera_segundos")
    if (getattr(settings, "INSTITUCIONAL_CORREO_MODO", "") != "outbox"
            or connection.vendor != "postgresql"
            or any(type(opciones.get(clave)) is not int or opciones[clave] <= 0 for clave in claves)
            or opciones["backoff_inicial_segundos"] > opciones["backoff_maximo_segundos"]):
        raise CorreoInstitucionalNoDisponible()
    return opciones


def encolar(solicitud):
    """INSERT en la transacción del llamador; sin lookup de usuario ni SMTP."""
    politica()
    from .credenciales import CorreoInstitucionalNoDisponible

    tipo = solicitud.get("tipo")
    permitidas = {
        "invitacion": {"tipo", "usuario_id", "actor_id", "institucion_id"},
        "recuperacion": {"tipo", "email", "usuario_id", "actor_id", "institucion_id"},
        "email": {"tipo", "usuario_id", "nuevo_email", "estado"},
        "email-confirmado": {"tipo", "usuario_id", "email_anterior"},
    }
    if tipo not in permitidas or set(solicitud) - permitidas[tipo]:
        raise CorreoInstitucionalNoDisponible()
    try:
        if ("usuario_id" in solicitud) == ("email" in solicitud):
            raise ValueError
        for clave in ("usuario_id", "actor_id", "institucion_id"):
            valor = solicitud.get(clave)
            if valor is not None and (type(valor) is not int or valor <= 0):
                raise ValueError
        if "usuario_id" in solicitud and solicitud["usuario_id"] is None:
            raise ValueError
        for clave in ("email", "nuevo_email", "email_anterior"):
            if clave in solicitud:
                if not isinstance(solicitud[clave], str) or len(solicitud[clave]) > 254:
                    raise ValueError
                validate_email(solicitud[clave])
        if tipo == "email" and ("nuevo_email" not in solicitud or not isinstance(solicitud.get("estado"), str)
                                or not solicitud["estado"] or len(solicitud["estado"]) > 128
                                or any(c not in "0123456789abcdef" for c in solicitud["estado"])):
            raise ValueError
        if tipo == "email-confirmado" and "email_anterior" not in solicitud:
            raise ValueError
    except (ValueError, TypeError, DjangoValidationError):
        raise CorreoInstitucionalNoDisponible() from None
    proposito = {"invitacion": "INVITACION", "recuperacion": "RECUPERACION", "email": "EMAIL", "email-confirmado": "EMAIL"}[tipo]
    ahora = timezone.now()
    return CorreoInstitucionalOutbox.objects.create(
        solicitud=solicitud, disponible_en=ahora,
        vence=ahora + timedelta(seconds=getattr(settings, f"INSTITUCIONAL_{proposito}_TIMEOUT")),
    )


def tomar_trabajo():
    from .credenciales import exigir_configuracion_correo

    exigir_configuracion_correo()
    opciones = politica()
    ahora = timezone.now()
    with transaction.atomic():
        trabajo = CorreoInstitucionalOutbox.objects.select_for_update(skip_locked=True).filter(
            Q(estado=Estado.PENDIENTE, disponible_en__lte=ahora)
            | Q(estado=Estado.PROCESANDO, reservado_hasta__lte=ahora),
        ).order_by("disponible_en", "pk").first()
        if trabajo is None:
            return None
        if trabajo.vence <= ahora or trabajo.intentos >= opciones["max_intentos"]:
            trabajo.estado = Estado.DESCARTADO if trabajo.vence <= ahora else Estado.ERROR
            trabajo.resultado = "vencido" if trabajo.vence <= ahora else "intentos_agotados"
            trabajo.terminado_en = ahora
            trabajo.reserva = None
            trabajo.reservado_hasta = None
        else:
            trabajo.estado = Estado.PROCESANDO
            trabajo.reserva = uuid.uuid4()
            trabajo.reservado_hasta = ahora + timedelta(seconds=opciones["lease_segundos"])
            trabajo.intentos += 1
            trabajo.resultado = ""
        trabajo.save(update_fields=["estado", "resultado", "terminado_en", "reserva", "reservado_hasta", "intentos"])
        return trabajo.pk, trabajo.reserva


def procesar_reserva(pk, reserva):
    """SMTP fuera de locks/atomic; el resultado se publica solo con reserva vigente."""
    if reserva is None:
        return False
    from .credenciales import exigir_configuracion_correo

    exigir_configuracion_correo()
    opciones = politica()
    ahora = timezone.now()
    trabajo = CorreoInstitucionalOutbox.objects.filter(
        pk=pk, estado=Estado.PROCESANDO, reserva=reserva, reservado_hasta__gt=ahora,
    ).first()
    if trabajo is None:
        return False
    if trabajo.vence <= ahora:
        resultado = Estado.DESCARTADO
        codigo = "vencido"
    else:
        from .credenciales import procesar_solicitud_correo

        try:
            resultado = procesar_solicitud_correo(trabajo.solicitud)
            permanente = resultado == "error_permanente"
            if resultado not in (Estado.ENVIADO, Estado.DESCARTADO, Estado.ERROR, "error_permanente"):
                resultado = Estado.ERROR
            if permanente:
                resultado = Estado.ERROR
            codigo = "rechazo_permanente" if permanente else "enviado" if resultado == Estado.ENVIADO else "no_elegible" if resultado == Estado.DESCARTADO else "envio_fallido"
        except Exception:  # noqa: BLE001
            log.error("correo institucional: fallo al procesar trabajo_id=%s", pk)
            resultado, codigo = Estado.ERROR, "procesamiento_fallido"
    ahora = timezone.now()
    campos = {"reserva": None, "reservado_hasta": None, "resultado": codigo}
    if resultado == Estado.ERROR:
        espera = min(opciones["backoff_maximo_segundos"],
                     opciones["backoff_inicial_segundos"] * 2 ** min(trabajo.intentos - 1, 30))
        siguiente = ahora + timedelta(seconds=espera)
        if codigo != "rechazo_permanente" and trabajo.intentos < opciones["max_intentos"] and siguiente < trabajo.vence:
            campos.update(estado=Estado.PENDIENTE, disponible_en=siguiente, terminado_en=None)
        else:
            campos.update(estado=Estado.ERROR, terminado_en=ahora)
    else:
        campos.update(estado=resultado, terminado_en=ahora)
    actualizado = CorreoInstitucionalOutbox.objects.filter(
        pk=pk, estado=Estado.PROCESANDO, reserva=reserva,
    ).update(**campos)
    if actualizado:
        log.info("correo institucional: trabajo_id=%s estado=%s codigo=%s", pk, campos["estado"], codigo)
    return bool(actualizado)


def procesar_siguiente():
    reserva = tomar_trabajo()
    if reserva is None:
        return False
    procesar_reserva(*reserva)
    return True


def estado_outbox():
    """Agregados operativos, nunca direcciones, payloads o errores del proveedor."""
    ahora = timezone.now()
    filas = CorreoInstitucionalOutbox.objects.values("estado").annotate(cantidad=Count("pk"))
    cantidades = {estado: 0 for estado in Estado.values}
    cantidades.update({fila["estado"]: fila["cantidad"] for fila in filas})
    pendientes = CorreoInstitucionalOutbox.objects.filter(estado__in=(Estado.PENDIENTE, Estado.PROCESANDO))
    primero = pendientes.aggregate(primero=Min("creado"))["primero"]
    return {
        **cantidades,
        "antiguedad_pendiente_segundos": max(0, int((ahora - primero).total_seconds())) if primero else 0,
        "reservas_vencidas": pendientes.filter(estado=Estado.PROCESANDO, reservado_hasta__lte=ahora).count(),
        "plazos_vencidos": CorreoInstitucionalOutbox.objects.filter(
            Q(estado__in=(Estado.PENDIENTE, Estado.PROCESANDO), vence__lte=ahora) | Q(resultado="vencido"),
        ).count(),
    }


def purgar_payloads(antes, *, limite):
    """Minimización explícita: conserva metadatos, no promete borrar backups/WAL."""
    politica()
    if timezone.is_naive(antes) or type(limite) is not int or limite <= 0:
        raise ValueError("La purga exige fecha con zona y límite positivo.")
    with transaction.atomic():
        ids = list(CorreoInstitucionalOutbox.objects.select_for_update(skip_locked=True).filter(
            estado__in=TERMINALES, terminado_en__lt=antes,
        ).exclude(solicitud={}).order_by("pk").values_list("pk", flat=True)[:limite])
        return CorreoInstitucionalOutbox.objects.filter(pk__in=ids).update(solicitud={})
