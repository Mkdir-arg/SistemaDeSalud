"""Guards del runner E2E: rechazar destinos ajenos antes de abrir una conexión."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from . import importacion_real as runner


class RunnerImportacionTests(TestCase):
    def variables(self, **cambios):
        return {
            "SALUD_IMPORTACION_E2E_AISLADO": "1", "ENTORNO": "desarrollo",
            "SALUD_TEST_POSTGRES_URL": "postgresql://ficticio@127.0.0.1:55443/salud_financiadores_test",
            "SALUD_IMPORTACION_DIRECTORIO": str(Path(gettempdir()) / "salud-importacion182-test"),
            "SALUD_IMPORTACION_MANIFEST": "",
            **cambios,
        }

    def test_rechaza_ausencia_de_marca_o_entorno_productivo_antes_de_conectar(self):
        for cambios in ({"SALUD_IMPORTACION_E2E_AISLADO": ""}, {"ENTORNO": "produccion"}):
            with self.subTest(cambios=cambios), patch.dict(os.environ, self.variables(**cambios)), patch.object(runner.psycopg, "connect") as conectar:
                with self.assertRaises(RuntimeError):
                    runner.preparar()
                conectar.assert_not_called()

    def test_rechaza_base_operativa_host_remoto_y_parametros_que_sustituyen_destino(self):
        for url in (
            "postgresql://ficticio@127.0.0.1:55443/salud_operativa",
            "postgresql://ficticio@db.example.invalid/salud_financiadores_test",
            "postgresql://ficticio@127.0.0.1:55443/salud_financiadores_test?host=db.example.invalid",
        ):
            with self.subTest(url=url), patch.dict(os.environ, self.variables(SALUD_TEST_POSTGRES_URL=url)), patch.object(runner.psycopg, "connect") as conectar:
                with self.assertRaises(ImproperlyConfigured):
                    runner.preparar()
                conectar.assert_not_called()

    def test_entorno_no_hereda_conexion_settings_ni_ssl_productivos(self):
        env = runner.entorno(self.variables(DATABASE_URL="destino-ajeno", DJANGO_SETTINGS_MODULE="config.settings",
            DJANGO_SSL_REDIRECT="true", PYTHON_DOTENV_DISABLED="0"))
        self.assertEqual(env["DATABASE_URL"], env["SALUD_TEST_POSTGRES_URL"])
        self.assertEqual(env["DJANGO_SETTINGS_MODULE"], "config.settings_financiadores_postgres_test")
        self.assertEqual(env["PYTHON_DOTENV_DISABLED"], "1")
        self.assertEqual(env["DJANGO_SSL_REDIRECT"], "false")

    def test_directorio_existente_no_se_sobrescribe_ni_abre_db(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal:
            with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=temporal)), patch.object(runner.psycopg, "connect") as conectar:
                with self.assertRaises(RuntimeError):
                    runner.preparar()
                conectar.assert_not_called()

    def test_base_existente_impide_creacion_y_preparacion_de_datos(self):
        with patch.dict(os.environ, self.variables()), patch.object(runner.psycopg, "connect") as conectar, patch.object(runner.subprocess, "run") as ejecutar:
            conexion = conectar.return_value.__enter__.return_value
            conexion.execute.return_value.fetchone.return_value = (1,)
            with self.assertRaises(RuntimeError):
                runner.preparar()
            self.assertEqual(conexion.execute.call_count, 1)
            self.assertTrue(conexion.execute.call_args.args[0].startswith("SELECT"))
            ejecutar.assert_not_called()

    def test_limpieza_retira_solo_el_manifiesto_y_es_repetible(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal:
            carpeta = Path(temporal)
            manifiesto = carpeta / "manifiesto.json"
            manifiesto.write_text("{}", encoding="utf-8")
            fixture = carpeta / "ficticio.xlsx"
            fixture.write_bytes(b"fixture ficticia")
            with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=temporal)), patch.object(runner.psycopg, "connect") as conectar:
                runner.limpiar()
                runner.limpiar()
                conectar.assert_not_called()
            self.assertFalse(manifiesto.exists())
            self.assertTrue(fixture.exists())

    def test_limpieza_no_toca_manifiesto_ajeno(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal:
            ajeno = Path(temporal) / "ajeno.json"
            ajeno.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=temporal,
                SALUD_IMPORTACION_MANIFEST=str(ajeno))):
                with self.assertRaises(RuntimeError):
                    runner.limpiar()
            self.assertTrue(ajeno.exists())
