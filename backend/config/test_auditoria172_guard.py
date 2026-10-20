"""Tests stdlib, sin Django/DB ni lectura de .env: python -m unittest ..."""
import secrets
import unittest

from config.auditoria172_guard import validar_laboratorio


class LaboratorioGuardTests(unittest.TestCase):
    def setUp(self):
        self.entorno = {
            "SALUD_AUDITORIA172": "1",
            "SALUD_TEST_DOCKER_PROJECT": "salud-auditoria172",
            "ENTORNO": "demo",
            "DATABASE_URL": f"postgres://auditoria172:{secrets.token_urlsafe(24)}@db-auditoria172:5432/auditoria172",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(32),
        }

    def test_destino_exclusivo(self):
        self.assertEqual(validar_laboratorio(self.entorno), self.entorno["DATABASE_URL"])

    def test_rechaza_destinos_ajenos_y_opciones_de_driver(self):
        url = self.entorno["DATABASE_URL"]
        for destino in (
            url.replace("db-auditoria172", "localhost"),
            url.replace("db-auditoria172", "db"),
            url.replace("/auditoria172", "/salud"),
            url.replace(":5432/", ":5433/"),
            url.replace("postgres:", "sqlite:"),
            url.replace("postgres://auditoria172:", "postgres://salud:"),
            url + "?host=otro",
            url + "#fragmento",
            "postgres://[malformado",
        ):
            with self.subTest(destino=destino.split("@")[-1]):
                with self.assertRaises(ValueError):
                    validar_laboratorio({**self.entorno, "DATABASE_URL": destino})

    def test_rechaza_marcadores_incompletos_y_url_alternativa(self):
        for clave, valor in (
            ("SALUD_AUDITORIA172", ""),
            ("SALUD_TEST_DOCKER_PROJECT", "salud-padron-130"),
            ("ENTORNO", "produccion"),
            ("DJANGO_SECRET_KEY", ""),
            ("SALUD_TEST_POSTGRES_URL", "postgres://otro"),
        ):
            with self.subTest(clave=clave), self.assertRaises(ValueError):
                validar_laboratorio({**self.entorno, clave: valor})


if __name__ == "__main__":
    unittest.main()
