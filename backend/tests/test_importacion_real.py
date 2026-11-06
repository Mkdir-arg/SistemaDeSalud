"""Guards del runner E2E: rechazar destinos ajenos antes de abrir una conexión."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from . import importacion_real as runner


class RunnerImportacionTests(TestCase):
    def test_enlace_familiar_no_borra_manifiestos_propios_ni_ajenos(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal, \
                TemporaryDirectory(prefix="ostel-ci-ajeno-") as destino:
            importacion = Path(temporal)
            familia = importacion.with_name("ostel-familia-ui-" + importacion.name)
            propio = importacion / "manifiesto.json"
            ajeno = Path(destino) / "manifiesto.json"
            propio.write_bytes(b"importacion ficticia")
            ajeno.write_bytes(b"archivo ajeno ficticio")
            try:
                familia.symlink_to(destino, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Enlaces simbólicos no disponibles: {error}")
            try:
                with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=temporal), clear=True), \
                        patch.object(runner.psycopg, "connect") as conectar:
                    with self.assertRaises(RuntimeError):
                        runner.limpiar()
                    conectar.assert_not_called()
                self.assertEqual(propio.read_bytes(), b"importacion ficticia")
                self.assertEqual(ajeno.read_bytes(), b"archivo ajeno ficticio")
            finally:
                self.assertTrue(familia.is_symlink())
                if os.name == "nt":
                    familia.rmdir()
                else:
                    familia.unlink()

    def test_preparar_incluye_ambas_fixtures_y_manifiestos(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal:
            directorio = Path(temporal + "-nuevo")
            familia = directorio.with_name("ostel-familia-ui-" + directorio.name)
            variables = self.variables(SALUD_IMPORTACION_DIRECTORIO=str(directorio))
            with patch.dict(os.environ, variables, clear=True), patch.object(runner.psycopg, "connect") as conectar, \
                    patch.object(runner.subprocess, "run") as ejecutar:
                conectar.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
                runner.preparar()
            comandos = [c.args[0] for c in ejecutar.call_args_list]
            self.assertEqual(len(comandos), 3)
            self.assertEqual(comandos[1][-2:], ["../frontend/e2e/fixtures/preparar_importacion_real.py", str(directorio)])
            self.assertEqual(comandos[2][-2:], ["../frontend/e2e/fixtures/preparar_familia_ostel.py", str(familia)])
            for llamada in ejecutar.call_args_list:
                env = llamada.kwargs["env"]
                self.assertEqual(env["SALUD_IMPORTACION_MANIFEST"], str(directorio / "manifiesto.json"))
                self.assertEqual(env["SALUD_FAMILIA_MANIFEST"], str(familia / "manifiesto.json"))
                self.assertEqual(env["PYTHON_DOTENV_DISABLED"], "1")
                self.assertEqual(env["DJANGO_SETTINGS_MODULE"], "config.settings_financiadores_postgres_test")

    def test_manifiesto_familiar_ajeno_no_abre_db_ni_borra_el_de_importacion(self):
        with TemporaryDirectory(prefix="salud-importacion182-test-") as temporal:
            propio = Path(temporal) / "manifiesto.json"
            ajeno = Path(temporal) / "ajeno.json"
            propio.write_text("{}", encoding="utf-8")
            ajeno.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=temporal,
                    SALUD_FAMILIA_MANIFEST=str(ajeno)), clear=True), patch.object(runner.psycopg, "connect") as conectar:
                for accion in (runner.preparar, runner.limpiar):
                    with self.subTest(accion=accion.__name__), self.assertRaises(RuntimeError):
                        accion()
                conectar.assert_not_called()
            self.assertEqual(propio.read_text(encoding="utf-8"), "{}")
            self.assertEqual(ajeno.read_text(encoding="utf-8"), "{}")

    def test_limpieza_retira_ambos_manifiestos_y_conserva_los_xlsx(self):
        with TemporaryDirectory(prefix="ostel-familia-ui-salud-importacion182-test-") as temporal_familia:
            familia = Path(temporal_familia)
            importacion = familia.with_name(familia.name.removeprefix("ostel-familia-ui-"))
            importacion.mkdir()
            try:
                for directorio in (importacion, familia):
                    (directorio / "manifiesto.json").write_text("{}", encoding="utf-8")
                    (directorio / "ficticio.xlsx").write_bytes(b"fixture ficticia")
                with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=str(importacion)), clear=True), \
                        patch.object(runner.psycopg, "connect") as conectar:
                    runner.limpiar()
                    runner.limpiar()
                    conectar.assert_not_called()
                for directorio in (importacion, familia):
                    self.assertFalse((directorio / "manifiesto.json").exists())
                    self.assertEqual((directorio / "ficticio.xlsx").read_bytes(), b"fixture ficticia")
            finally:
                for nombre in ("manifiesto.json", "ficticio.xlsx"):
                    (importacion / nombre).unlink(missing_ok=True)
                importacion.rmdir()

    def test_directorio_familiar_existente_no_se_sobrescribe_ni_abre_db(self):
        with TemporaryDirectory(prefix="ostel-familia-ui-salud-importacion182-test-") as temporal:
            importacion = Path(temporal).with_name(Path(temporal).name.removeprefix("ostel-familia-ui-"))
            with patch.dict(os.environ, self.variables(SALUD_IMPORTACION_DIRECTORIO=str(importacion)), clear=True), \
                    patch.object(runner.psycopg, "connect") as conectar:
                with self.assertRaises(RuntimeError):
                    runner.preparar()
                conectar.assert_not_called()

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
