"""Release y configuración productiva (#172, AUD-023/026).

- Con ENTORNO=produccion no se arranca con DEBUG, sobre SQLite ni sembrando
  datos ficticios.
- Las migraciones se aplican de a un proceso por vez.
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest import skipUnless

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections
from django.test import SimpleTestCase, TransactionTestCase

from .management.commands.migrar_con_candado import CANDADO_MIGRACIONES

COMPLETA = {
    "ENTORNO": "produccion", "DJANGO_DEBUG": "false", "DJANGO_SECRET_KEY": "x" * 64,
    "DATABASE_URL": "postgres://u:p@localhost:5432/x", "SEED_DEMO": "0", "SEED_GUARDIA": "0",
    "RENAPER_MODO": "real",
}


def importar_settings(**variables):
    entorno = {k: v for k, v in os.environ.items() if k not in COMPLETA}
    entorno.update(variables)
    entorno = {k: v for k, v in entorno.items() if v is not None}
    return subprocess.run([sys.executable, "-c", "import config.settings"], cwd=Path(settings.BASE_DIR),
                          env=entorno, capture_output=True, text=True)


class ProduccionIncompletaAuditoria172Tests(SimpleTestCase):
    def test_produccion_completa_arranca(self):
        r = importar_settings(**COMPLETA)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])

    def test_produccion_incompleta_no_arranca_y_dice_que_falta(self):
        casos = {
            "DJANGO_DEBUG": {"DJANGO_DEBUG": None},
            "DATABASE_URL": {"DATABASE_URL": None},
            "SEED_DEMO=0": {"SEED_DEMO": "1"},
            "SEED_GUARDIA=0": {"SEED_GUARDIA": "1"},
        }
        for falta, cambio in casos.items():
            with self.subTest(falta=falta):
                r = importar_settings(**{**COMPLETA, **cambio})
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(falta, r.stderr)

    def test_desarrollo_no_cambia(self):
        r = importar_settings(ENTORNO="desarrollo", DJANGO_DEBUG="true", DATABASE_URL=None, SEED_DEMO="1")
        self.assertEqual(r.returncode, 0, r.stderr[-400:])


@skipUnless(connection.vendor == "postgresql", "El candado es un advisory lock de PostgreSQL")
class MigrarConCandadoAuditoria172Tests(TransactionTestCase):
    def test_espera_al_otro_proceso_y_no_migra_mientras_tanto(self):
        otra = connections.create_connection("default")
        try:
            with otra.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_lock(%s)", [CANDADO_MIGRACIONES])
            with self.assertRaises(CommandError):
                call_command("migrar_con_candado", espera=1, verbosity=0)
            with otra.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [CANDADO_MIGRACIONES])
            call_command("migrar_con_candado", espera=1, verbosity=0)
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = %s",
                               [CANDADO_MIGRACIONES])
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            otra.close()
