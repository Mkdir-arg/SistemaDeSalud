"""`migrate` con exclusión entre procesos (#172, AUD-023).

`EJECUTAR_MIGRACIONES` decide qué servicio migra, pero dos réplicas web que
arrancan juntas, o un worker mal configurado, migraban a la vez: dos `migrate`
concurrentes toman locks de DDL en distinto orden y pueden dejar la migración a
medias. Acá cada proceso espera un advisory lock de PostgreSQL de sesión; el
segundo entra cuando el primero terminó y no encuentra nada pendiente.

Si `migrate` falla, el comando falla y el entrypoint (`set -e`) no arranca el
servidor: un release sin su esquema no recibe tráfico.
"""
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

# Constante del proyecto para este candado; no compartir con otros usos.
CANDADO_MIGRACIONES = 172_023_001


class Command(BaseCommand):
    help = "Aplica las migraciones de a un proceso por vez (advisory lock de PostgreSQL)."

    def add_arguments(self, parser):
        parser.add_argument("--espera", type=int, default=600, help="Segundos máximos esperando el candado.")

    def handle(self, *args, espera=600, **opciones):
        if connection.vendor != "postgresql":
            # SQLite de desarrollo: un solo proceso, sin candado posible.
            call_command("migrate", interactive=False, verbosity=opciones.get("verbosity", 1))
            return
        limite = time.monotonic() + espera
        with connection.cursor() as cursor:
            while True:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [CANDADO_MIGRACIONES])
                if cursor.fetchone()[0]:
                    break
                if time.monotonic() > limite:
                    raise CommandError("Otro proceso sigue migrando: no se arranca sin el esquema completo.")
                self.stdout.write("Otro proceso está migrando; espero…")
                time.sleep(2)
            try:
                call_command("migrate", interactive=False, verbosity=opciones.get("verbosity", 1))
            finally:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [CANDADO_MIGRACIONES])
