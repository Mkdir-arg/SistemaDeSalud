"""
Aviso de saturación en la red.

El panorama de camas ya existe, pero **hay que ir a mirarlo**. Una saturación
que nadie mira no cambia ninguna decisión: quien deriva se entera cuando el
traslado le vuelve rechazado, que es tarde y con una ambulancia ya en la calle.

Esto avisa a los establecimientos de la red cuando otro se satura, para que el
próximo paciente no salga hacia ahí.

**A quién se le avisa y a quién no.** El aviso va a los OTROS establecimientos
de la red: el saturado ya lo sabe —lo está viviendo— y sumarle una notificación
es ruido en el peor momento.

Se corre cada tanto:

    */30 * * * *  cd /app && python manage.py alertar_saturacion

No repite: se avisa cuando un establecimiento CRUZA el umbral, no en cada
pasada. Un aviso cada media hora sobre lo mismo se termina ignorando, y con él
se ignoran los que sí son nuevos.
"""
from django.core.management.base import BaseCommand
from datetime import timedelta

from django.utils import timezone

from apps.auditoria.latidos import latir
from apps.accounts.models import Membresia
from apps.casos.models import Notificacion
from apps.red import motor
from apps.red.models import Red

# Qué establecimientos ya fueron avisados, para no repetir. Vive en la base
# —en las notificaciones ya emitidas— y no en memoria: el comando corre en un
# proceso nuevo cada vez.
VENTANA_HORAS = 12


class Command(BaseCommand):
    help = "Avisa a la red cuando un establecimiento cruza el umbral de ocupación."

    def add_arguments(self, parser):
        parser.add_argument("--umbral", type=int, default=90,
                            help="Porcentaje de ocupación a partir del cual se avisa.")
        parser.add_argument("--seco", action="store_true", help="Muestra qué haría, sin avisar.")

    def handle(self, *args, **opciones):
        umbral = opciones["umbral"]
        seco = opciones["seco"]
        desde = timezone.now() - timedelta(hours=VENTANA_HORAS)
        avisos = 0

        for red in Red.objects.filter(activa=True).prefetch_related("instituciones"):
            saturados = motor.saturadas(red, umbral=umbral)
            if not saturados:
                continue
            otros = list(red.instituciones.filter(activa=True))

            for s in saturados:
                inst = s["institucion"]
                titulo = f"{inst.nombre} sin camas ({s['ocupacion']}% de ocupación)"

                # ¿Ya se avisó de este establecimiento hace poco?
                if Notificacion.objects.filter(titulo=titulo, creada__gte=desde).exists():
                    continue

                detalle = (
                    f"{s['libres']} libres de {s['operativas']} en servicio. "
                    f"Conviene derivar a otro efector de {red.nombre}."
                )
                destinatarios = Membresia.objects.filter(
                    activo=True,
                    institucion__in=[i for i in otros if i.id != inst.id],
                    rol__in=["jefe_area", "admin", "administrativo"],
                ).select_related("usuario").distinct()

                for m in destinatarios:
                    if seco:
                        self.stdout.write(f"  [seco] {m.usuario.email}: {titulo}")
                    else:
                        Notificacion.objects.create(
                            usuario=m.usuario, titulo=titulo, detalle=detalle[:255]
                        )
                    avisos += 1

                if not destinatarios:
                    # Una red de un solo establecimiento no tiene a quién avisarle.
                    # Decirlo evita buscar por qué la alerta «no anda».
                    self.stderr.write(
                        f"  {inst.nombre} está saturado pero no hay a quién avisarle: "
                        f"«{red.nombre}» no tiene otro establecimiento con personal."
                    )

        resumen = f"{avisos} aviso(s) de saturación"
        self.stdout.write(resumen + (" (en seco)" if seco else ""))
        if not seco:
            latir("alertar_saturacion", resumen)
