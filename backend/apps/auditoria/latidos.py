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
    "recordar_turnos": 60 * 60,
    "alertar_saturacion": 60 * 60,
    "respaldar": 36 * 60 * 60,
}


def estado() -> dict:
    """
    Qué procesos están al día y cuáles se quedaron callados.

    `nunca` no es lo mismo que `atrasado`: un sistema recién instalado todavía
    no corrió nada, y confundirlo con un proceso muerto haría que la primera
    alarma de la vida del sistema sea falsa.
    """
    ahora = timezone.now()
    ultimos = {l.servicio: l for l in Latido.objects.all()}

    servicios, atrasados = {}, []
    for nombre, intervalo in ESPERADOS.items():
        l = ultimos.get(nombre)
        if l is None:
            servicios[nombre] = {"estado": "nunca", "hace_segundos": None, "detalle": ""}
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

    return {"servicios": servicios, "atrasados": atrasados}
