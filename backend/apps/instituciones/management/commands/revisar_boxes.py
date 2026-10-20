"""Avisa boxes ocupados sin actividad con pacientes esperando (#172, AUD-048).

Corre en el bucle de `tiempos` junto a `correr_tiempos`. Es idempotente: cada
ocupación se avisa una sola vez y se toma con `skip_locked`. No libera boxes.
"""
from django.core.management.base import BaseCommand

from apps.auditoria.latidos import latir
from apps.instituciones import boxes


class Command(BaseCommand):
    help = "Avisa al jefe de área y a los admins los boxes ocupados e inactivos con pacientes esperando."

    def add_arguments(self, parser):
        parser.add_argument("--seco", action="store_true", help="Muestra qué haría, sin tocar nada.")

    def handle(self, *args, seco=False, **opciones):
        avisados = boxes.revisar(seco=seco)
        resumen = f"{avisados} box(es) {'por avisar' if seco else 'avisados'} por inactividad."
        self.stdout.write(resumen)
        if not seco:
            latir("revisar_boxes", resumen)
