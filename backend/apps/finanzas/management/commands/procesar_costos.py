"""Recupera costos directos pendientes sin entrar en el recorrido clínico."""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.auditoria.latidos import latir

from ...models import HechoAtencionCosteable, PendienteCosteo
from ...services import procesar_hecho_atencion


class Command(BaseCommand):
    help = "Procesa en lotes los hechos de atención con costos pendientes."

    def add_arguments(self, parser):
        parser.add_argument("--seco", action="store_true", help="Muestra qué hechos procesaría, sin escribir.")
        parser.add_argument("--limite", type=int, default=100, help="Tope de hechos por pasada.")

    def handle(self, *args, **opciones):
        limite = opciones["limite"]
        seco = opciones["seco"]
        ids = list(
            HechoAtencionCosteable.objects.filter(
                Q(pendientes__resuelto=False) | Q(componentes_esperados__isnull=True)
            ).order_by("ocurrida_en", "id").distinct().values_list("id", flat=True)[:limite]
        )
        procesados = 0
        for hecho_id in ids:
            if seco:
                self.stdout.write(f"  procesaría el hecho #{hecho_id}")
                procesados += 1
                continue
            try:
                procesar_hecho_atencion(hecho_id)
                procesados += 1
            except Exception:  # noqa: BLE001
                PendienteCosteo.objects.get_or_create(
                    hecho_id=hecho_id,
                    componente=None,
                    motivo=PendienteCosteo.Motivo.ERROR_RECUPERABLE,
                )
                self.stderr.write(f"  hecho #{hecho_id}: no se pudo procesar; quedará para recuperar")
        resumen = f"{procesados} hecho(s) procesado(s)"
        self.stdout.write(("[en seco] " if seco else "") + resumen)
        if not seco:
            latir("procesar_costos", resumen)
