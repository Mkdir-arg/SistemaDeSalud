"""Cola durable de reparto, despertada por PostgreSQL después del commit.

La notificación sólo despierta: la tabla conserva el trabajo aunque el proceso
esté detenido. Reservas vencidas se recuperan; las generaciones evitan perder
cambios que llegaron durante un cálculo. No abre hilos en el servidor web.
"""
import logging
import uuid
from datetime import timedelta

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import Gasto, TrabajoReparto

logger = logging.getLogger(__name__)
CANAL = "finanzas_repartos"
SERVICIO = "repartos_eventos"


def solicitar_reparto(gasto_id):
    """Se llama dentro de la transacción de la modificación financiera."""
    with transaction.atomic():
        ahora = timezone.now()
        trabajo, creado = TrabajoReparto.objects.select_for_update().get_or_create(
            gasto_id=gasto_id, defaults={"reintentar_en": ahora},
        )
        if not creado:
            trabajo.revision += 1
            trabajo.solicitado_en = ahora
            trabajo.ultimo_error = ""
            trabajo.intentos = 0
            if trabajo.reserva is None:
                trabajo.reintentar_en = ahora
            trabajo.save(update_fields=["revision", "solicitado_en", "ultimo_error", "intentos", "reintentar_en"])
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                # PostgreSQL entrega NOTIFY sólo si esta transacción confirma.
                cursor.execute("SELECT pg_notify(%s, '')", [CANAL])
        return trabajo


def solicitar_en_area(institucion_id, area_id, *, periodo=None, desde=None, concepto_id=None):
    gastos = Gasto.objects.filter(
        institucion_id=institucion_id, area_id=area_id, estado=Gasto.Estado.APROBADO,
        reemplazado_por__isnull=True,
    )
    if periodo is not None:
        gastos = gastos.filter(periodo_economico=periodo)
    if desde is not None:
        gastos = gastos.filter(periodo_economico__gte=desde)
    if concepto_id is not None:
        gastos = gastos.filter(concepto_id=concepto_id)
    for gasto_id in gastos.order_by("id").values_list("id", flat=True).iterator(chunk_size=100):
        solicitar_reparto(gasto_id)


def tomar_trabajo():
    ahora = timezone.now()
    with transaction.atomic():
        trabajo = TrabajoReparto.objects.filter(
            revision__gt=F("revision_procesada"), reintentar_en__lte=ahora,
        ).select_for_update(skip_locked=True).order_by("reintentar_en", "id").first()
        if trabajo is None:
            return None
        trabajo.reserva = uuid.uuid4()
        trabajo.iniciado_en = ahora
        trabajo.reintentar_en = ahora + timedelta(minutes=5)
        trabajo.intentos += 1
        trabajo.ultimo_error = ""
        trabajo.save(update_fields=["reserva", "iniciado_en", "reintentar_en", "intentos", "ultimo_error"])
        return trabajo.pk, trabajo.gasto_id, trabajo.revision, trabajo.reserva, trabajo.intentos


def procesar_siguiente():
    from .services import procesar_reparto_gasto
    reserva = tomar_trabajo()
    if reserva is None:
        return False
    pk, gasto_id, revision, token, intentos = reserva
    try:
        with transaction.atomic():
            # Orden de bloqueo compartido con aprobación/ajuste: fuente, trabajo.
            Gasto.objects.select_for_update().get(pk=gasto_id)
            if not TrabajoReparto.objects.filter(pk=pk, reserva=token).exists():
                return True
            procesar_reparto_gasto(gasto_id)
            trabajo = TrabajoReparto.objects.select_for_update().get(pk=pk)
            if trabajo.reserva == token:
                trabajo.revision_procesada = max(trabajo.revision_procesada, revision)
                trabajo.procesado_en = timezone.now()
                trabajo.reintentar_en = timezone.now()
                trabajo.reserva = None
                trabajo.iniciado_en = None
                trabajo.ultimo_error = ""
                trabajo.save(update_fields=["revision_procesada", "procesado_en", "reintentar_en", "reserva", "iniciado_en", "ultimo_error"])
    except Exception as error:
        # No copiar excepción, importes, nombres ni SQL a la respuesta o la cola.
        logger.error("No se pudo completar un reparto (%s).", type(error).__name__)
        TrabajoReparto.objects.filter(pk=pk, reserva=token).update(
            reserva=None, iniciado_en=None,
            ultimo_error="No se pudo actualizar el reparto. Se reintentará automáticamente.",
            reintentar_en=timezone.now() + timedelta(seconds=min(300, 2 ** min(intentos, 8))),
        )
    return True


def recuperar_fuentes():
    """Conciliación de seguridad al iniciar y espaciada, no disparador normal.

    Incluye fuentes anteriores a la cola y actividad cuyo aviso financiero pudo
    fallar sin deshacer una atención clínica. El motor evita versiones idénticas.
    """
    for gasto_id in Gasto.objects.filter(
        estado=Gasto.Estado.APROBADO, reemplazado_por__isnull=True,
    ).order_by("id").values_list("id", flat=True).iterator(chunk_size=100):
        solicitar_reparto(gasto_id)
