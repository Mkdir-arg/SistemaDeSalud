"""
Latido de los procesos periódicos.

**El problema que resuelve.** El reloj del motor (`correr_tiempos`) es un bucle
en un contenedor. Si muere —se cae, se lo olvidan de levantar después de un
mantenimiento, el contenedor queda en `restarting`— no pasa nada visible: la
aplicación responde, las pantallas cargan, todo se ve bien. Pero un paciente que
entró a «Observación 6 horas» no vuelve nunca, los avisos de demora no salen, y
los recordatorios de turno tampoco.

Ese es el peor tipo de falla: silenciosa y clínica. Nadie la descubre hasta que
alguien pregunta por qué un caso quedó parado tres días.

Cada proceso periódico deja su latido al terminar. `/api/estado/` compara contra
el intervalo esperado y dice cuál se quedó callado, que es lo que un monitor
externo puede vigilar.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Latido(models.Model):
    """La última vez que un proceso periódico terminó de correr."""

    # Una fila por servicio, no un histórico: lo que se pregunta es «¿sigue
    # vivo?». Guardar cada pasada llenaría la tabla con millones de filas para
    # contestar algo que se lee de la última.
    servicio = models.CharField(max_length=60, unique=True)
    momento = models.DateTimeField(auto_now=True)
    detalle = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "latido de servicio"
        verbose_name_plural = "latidos de servicio"
        ordering = ["servicio"]

    def __str__(self):
        return f"{self.servicio} · {self.momento:%d/%m/%Y %H:%M}"


def latir(servicio: str, detalle: str = ""):
    """
    Deja constancia de que `servicio` terminó de correr recién.

    Nunca falla hacia afuera: que no se pueda escribir el latido no puede
    impedir que el reloj reactive las esperas. Sería exactamente al revés de lo
    que este archivo existe para lograr.
    """
    try:
        Latido.objects.update_or_create(servicio=servicio, defaults={"detalle": detalle[:200]})
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("no se pudo registrar el latido de %s", servicio)


# Cada cuánto se espera que corra cada proceso, y a partir de cuándo preocuparse.
#
# El margen es generoso a propósito —varias veces el intervalo—: un monitor que
# grita porque una pasada se atrasó treinta segundos enseña a ignorar la alarma,
# y entonces no sirve el día que el proceso se muere de verdad.
ESPERADOS = {
    "correr_tiempos": 15 * 60,
    # Detecta un worker caído; no promete que todos sus costos estén calculados.
    "procesar_costos": 15 * 60,
    "recordar_turnos": 60 * 60,
    "alertar_saturacion": 60 * 60,
    # Avisos de boxes ocupados sin actividad (#172); corre en el bucle de tiempos.
    "revisar_boxes": 15 * 60,
    "respaldar": 36 * 60 * 60,
}


# Un trabajo de reparto disponible no debería esperar más que esto con el
# listener sano (se procesa en segundos).
ESPERA_MAXIMA_REPARTOS = 15 * 60


def _arranque(ultimos):
    """Desde cuándo el sistema está en marcha, para dar por vencido un `nunca`."""
    if ultimos:
        return min(l.momento for l in ultimos.values())
    from django.db.migrations.recorder import MigrationRecorder
    from django.db.models import Max

    return MigrationRecorder.Migration.objects.aggregate(m=Max("applied"))["m"]


def estado() -> dict:
    """
    Qué procesos están al día y cuáles se quedaron callados.

    `nunca` no es lo mismo que `atrasado`: un sistema recién instalado todavía
    no corrió nada, y confundirlo con un proceso muerto haría que la primera
    alarma de la vida del sistema sea falsa. Pero `nunca` tampoco puede durar
    para siempre (#172, AUD-018): un worker que no arrancó nunca deja de ser
    «nuevo» cuando el sistema ya lleva andando más que su intervalo. La
    referencia es el latido más viejo de cualquier proceso o, sin ninguno, la
    última migración aplicada.
    """
    ahora = timezone.now()
    ultimos = {l.servicio: l for l in Latido.objects.all()}
    arranque = _arranque(ultimos)

    servicios, atrasados = {}, []
    esperados = dict(ESPERADOS)
    if getattr(settings, "INSTITUCIONAL_CORREO_MODO", "") == "outbox":
        politica = getattr(settings, "INSTITUCIONAL_OUTBOX_POLITICA", {})
        lease, espera = politica.get("lease_segundos"), politica.get("espera_segundos")
        # Margen operativo: un lease más tres esperas. Solo vigila ejecución,
        # no SMTP recibido; errores/edad de cola se consultan en estado_outbox.
        esperados["correo_institucional"] = lease + 3 * espera if (
            type(lease) is int and lease > 0 and type(espera) is int and espera > 0
        ) else 0
    for nombre, intervalo in esperados.items():
        l = ultimos.get(nombre)
        if nombre == "correo_institucional" and intervalo == 0:
            servicios[nombre] = {"estado": "atrasado", "hace_segundos": None, "detalle": "Configuración de outbox incompleta."}
            atrasados.append(nombre)
            continue
        if l is None:
            vencida = arranque is not None and (ahora - arranque).total_seconds() > intervalo
            servicios[nombre] = {
                "estado": "atrasado" if vencida else "nunca", "hace_segundos": None,
                "detalle": "Nunca corrió desde que el sistema está en marcha." if vencida else "",
            }
            if vencida or nombre == "correo_institucional":
                atrasados.append(nombre)
            continue
        hace = int((ahora - l.momento).total_seconds())
        al_dia = hace <= intervalo
        servicios[nombre] = {
            "estado": "al día" if al_dia else "atrasado",
            "hace_segundos": hace,
            "detalle": l.detalle,
        }
        if not al_dia:
            atrasados.append(nombre)

    # Accesos clínicos que no se pudieron registrar (#172): la atención siguió,
    # pero el hueco queda visible hasta que alguien lo marque revisado.
    from .models import FalloAuditoria

    pendientes = FalloAuditoria.objects.filter(revisado_at__isnull=True)
    cantidad = pendientes.count()
    if cantidad:
        ultimo = pendientes.order_by("-momento").values_list("momento", flat=True).first()
        servicios["registro_accesos"] = {
            "estado": "atrasado", "hace_segundos": int((ahora - ultimo).total_seconds()),
            "detalle": f"{cantidad} acceso(s) clínico(s) sin registrar; revisar en Admin.",
        }
        atrasados.append("registro_accesos")
    else:
        servicios["registro_accesos"] = {"estado": "al día", "hace_segundos": None, "detalle": ""}

    # La cola de repartos (#172, AUD-018): NOTIFY despierta, TrabajoReparto es
    # la cola. Un listener vivo que no procesa no deja latido distinto; la edad
    # del trabajo disponible más viejo sí lo muestra.
    from django.db.models import F

    from apps.finanzas.models import TrabajoReparto

    viejo = TrabajoReparto.objects.filter(revision__gt=F("revision_procesada"), reintentar_en__lte=ahora) \
        .order_by("reintentar_en").values_list("reintentar_en", flat=True).first()
    espera = int((ahora - viejo).total_seconds()) if viejo else None
    if espera is not None and espera > ESPERA_MAXIMA_REPARTOS:
        servicios["cola_repartos"] = {"estado": "atrasado", "hace_segundos": espera,
                                      "detalle": "Hay repartos disponibles sin procesar."}
        atrasados.append("cola_repartos")
    else:
        servicios["cola_repartos"] = {"estado": "al día", "hace_segundos": espera, "detalle": ""}

    return {"servicios": servicios, "atrasados": atrasados}
