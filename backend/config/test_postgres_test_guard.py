"""La guarda de configuración se prueba sin PostgreSQL ni credenciales reales."""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .postgres_test_guard import validar_destino_postgres


class DestinoPostgresTests(SimpleTestCase):
    def test_localhost_preserva_destino_dedicado(self):
        for host in ("localhost", "127.0.0.1", "[::1]"):
            validar_destino_postgres(f"postgresql://{host}/salud_financiadores_test", entorno="desarrollo", proyecto_docker="")

    def test_db_solo_demo_con_marcador_exacto(self):
        validar_destino_postgres("postgresql://db/salud_financiadores_test", entorno="demo", proyecto_docker="salud-padron-130")
        for entorno, marcador in (("demo", ""), ("desarrollo", "salud-padron-130"), ("produccion", "salud-padron-130"), ("demo", "otro")):
            with self.subTest(entorno=entorno, marcador=marcador), self.assertRaises(ImproperlyConfigured):
                validar_destino_postgres("postgresql://db/salud_financiadores_test", entorno=entorno, proyecto_docker=marcador)

    def test_rechaza_produccion_base_operativa_host_ajeno_y_query_override(self):
        with self.assertRaises(ImproperlyConfigured):
            validar_destino_postgres("postgresql://localhost/salud_financiadores_test", entorno="produccion", proyecto_docker="")
        for url in ("postgresql://db/salud", "postgresql://db/test_salud_financiadores_test", "postgresql://otro/salud_financiadores_test", "postgresql://db/salud_financiadores_test?host=otro", "postgresql://db/salud_financiadores_test?options=otro", "postgresql://db/salud_financiadores_test?dbname=salud", "sqlite://db/salud_financiadores_test", ""):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                validar_destino_postgres(url, entorno="demo", proyecto_docker="salud-padron-130")
