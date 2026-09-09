"""Recalcula repartos de gastos aprobados sin intervenir en la atención clínica."""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.latidos import latir

from ...models import Gasto
from ...services import procesar_reparto_gasto


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Procesa en lotes los repartos de gastos aprobados por actividad."

    def add_arguments(self, parser):
        parser.add_argument("--seco", action="store_true", help="Muestra qué gastos procesaría, sin escribir.")
        parser.add_argument(
            "--limite", type=int, default=100,
            help="Tamaño de cada lote de lectura; la pasada recorre todos los gastos aprobados.",
        )

    def handle(self, *args, **opciones):
        limite = opciones["limite"]
        if limite <= 0:
            raise CommandError("--limite debe ser mayor que cero")
        seco = opciones["seco"]
        candidatos = Gasto.objects.filter(
            estado=Gasto.Estado.APROBADO,
        ).order_by("id")
        procesados = 0
        ultimo_id = 0
        while True:
            ids = list(
                candidatos.filter(id__gt=ultimo_id).values_list("id", flat=True)[:limite]
            )
            if not ids:
                break
            ultimo_id = ids[-1]
            for gasto_id in ids:
                if seco:
                    self.stdout.write(f"  procesaría el gasto #{gasto_id}")
                    procesados += 1
                    continue
                try:
                    procesar_reparto_gasto(gasto_id)
                    procesados += 1
                except Exception:  # noqa: BLE001
                    logger.exception("No se pudo procesar el reparto del gasto %s", gasto_id)
                    self.stderr.write(f"  gasto #{gasto_id}: no se pudo procesar; se reintentará en otra pasada")
        resumen = f"{procesados} gasto(s) procesado(s)"
        self.stdout.write(("[en seco] " if seco else "") + resumen)
        if not seco:
            latir("procesar_repartos", resumen)
