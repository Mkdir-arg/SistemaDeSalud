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
        parser.add_argument("--limite", type=int, default=100, help="Tope de gastos por pasada.")

    def handle(self, *args, **opciones):
        limite = opciones["limite"]
        if limite <= 0:
            raise CommandError("--limite debe ser mayor que cero")
        seco = opciones["seco"]
        ids = list(
            Gasto.objects.filter(
                estado=Gasto.Estado.APROBADO,
                area__isnull=False,
            ).order_by("periodo_economico", "id").values_list("id", flat=True)[:limite]
        )
        procesados = 0
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
