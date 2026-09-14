"""Procesador de eventos financieros: LISTEN/NOTIFY y recuperación durable."""
import time

import psycopg
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, close_old_connections

from apps.auditoria.latidos import latir
from apps.finanzas.procesamiento import CANAL, SERVICIO, procesar_siguiente, recuperar_fuentes


class Command(BaseCommand):
    help = "Procesa repartos al confirmar cambios y recupera trabajo pendiente tras reinicios."

    def add_arguments(self, parser):
        parser.add_argument("--una-pasada", action="store_true", help="Vacía trabajos listos y termina, sin conciliación global.")

    def handle(self, *args, **options):
        if options["una_pasada"]:
            while procesar_siguiente():
                latir(SERVICIO)
            latir(SERVICIO)
            return
        if connection.vendor != "postgresql":
            raise CommandError("El procesamiento por eventos requiere PostgreSQL.")
        parametros = connection.get_connection_params()
        parametros.pop("cursor_factory", None)
        with psycopg.connect(**parametros, autocommit=True) as escucha:
            escucha.execute(f"LISTEN {CANAL}")
            # Escuchar ANTES de revisar la tabla evita perder el primer aviso.
            proxima_conciliacion = 0
            while True:
                close_old_connections()
                if time.monotonic() >= proxima_conciliacion:
                    recuperar_fuentes()
                    proxima_conciliacion = time.monotonic() + 600
                while procesar_siguiente():
                    latir(SERVICIO)
                latir(SERVICIO)
                # El timeout sólo atiende reintentos/reservas vencidas y latido;
                # los cambios normales despiertan inmediatamente con NOTIFY.
                for _ in escucha.notifies(timeout=2, stop_after=1):
                    break
