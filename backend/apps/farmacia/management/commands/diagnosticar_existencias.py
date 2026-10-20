"""Diagnóstico read-only de claves de stock duplicadas, sin cantidades de stock."""
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models import Count

from apps.farmacia.models import Existencia


class Command(BaseCommand):
    help = "Lista claves técnicas de existencias duplicadas sin corregir ni borrar datos."

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS, choices=tuple(connections))

    def handle(self, *args, **options):
        duplicados = (
            Existencia.objects.using(options["database"]).order_by()
            .values("deposito_id", "insumo_id", "lote_id")
            .annotate(filas=Count("pk")).filter(filas__gt=1)
            .order_by("deposito_id", "insumo_id", "lote_id")
        )
        total = 0
        for grupo in duplicados.iterator():
            total += 1
            lote = grupo["lote_id"] if grupo["lote_id"] is not None else "NULL"
            self.stdout.write(
                f"deposito_id={grupo['deposito_id']} insumo_id={grupo['insumo_id']} "
                f"lote_id={lote} filas={grupo['filas']}"
            )
        if total:
            raise CommandError("Existen claves de stock duplicadas; no se modificó ningún dato.")
        self.stdout.write("Sin claves de stock duplicadas. No se modificó ningún dato.")
