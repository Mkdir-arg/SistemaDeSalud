"""
Respaldo y endurecimiento para producción.

La restauración de verdad se prueba corriendo el comando —lo hace en cada
corrida, ése es el punto—. Acá se cubren las decisiones que, si se rompen, dejan
un archivo con nombre de respaldo o un sistema abierto, y que ningún ojo humano
va a revisar.
"""
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from apps.auditoria.management.commands.respaldar import TABLAS, Command


class VersionesTests(TestCase):
    """
    El cliente no puede ser de otra versión mayor que el servidor.

    Con `pg_dump` 17 contra un servidor 16 el volcado sale bien —tamaño
    razonable, código de salida cero— y no se puede restaurar. Es la peor forma
    de no tener respaldo, porque todo indica que sí.
    """

    def _correr(self, version_cliente):
        cmd = Command()
        salida = subprocess.CompletedProcess([], 0, stdout=version_cliente, stderr="")
        with patch("subprocess.run", return_value=salida):
            cmd._comprobar_versiones({})

    def test_un_cliente_de_otra_version_corta_antes_de_respaldar(self):
        with self.assertRaises(CommandError) as e:
            self._correr("pg_dump (PostgreSQL) 17.11 (Debian 17.11-0+deb13u1)")
        self.assertIn("17", str(e.exception))
        # Tiene que decir qué hacer: el error que da Postgres al restaurar es
        # «unrecognized configuration parameter» y no lleva a nadie a la causa.
        self.assertIn("PG_MAJOR", str(e.exception))

    def test_con_la_misma_version_sigue(self):
        self._correr("pg_dump (PostgreSQL) 16.15 (Debian 16.15-1.pgdg13+2)")

    def test_sin_pg_dump_lo_dice_en_vez_de_fallar_raro(self):
        cmd = Command()
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "no such file")):
            with self.assertRaises(CommandError) as e:
                cmd._comprobar_versiones({})
        self.assertIn("pg_dump", str(e.exception))


class RotacionTests(SimpleTestCase):
    """
    Sin rotación el disco se llena, y cuando se llena `pg_dump` escribe hasta
    donde puede: quedan archivos truncados con nombre de respaldo.
    """

    def _carpeta(self, cuantos):
        d = TemporaryDirectory()
        for i in range(cuantos):
            (Path(d.name) / f"cauce-2026081{i}-000000.sql.gz").write_bytes(b"x" * 2048)
        return d

    def test_deja_los_mas_nuevos_y_borra_los_viejos(self):
        with self._carpeta(6) as ruta:
            Command()._rotar(Path(ruta), conservar=3)
            quedan = sorted(p.name for p in Path(ruta).glob("*.sql.gz"))
        self.assertEqual(len(quedan), 3)
        self.assertIn("cauce-20260815-000000.sql.gz", quedan)
        self.assertNotIn("cauce-20260810-000000.sql.gz", quedan)

    def test_con_cero_no_borra_nada(self):
        """Hay instalaciones donde la retención la maneja el almacenamiento."""
        with self._carpeta(5) as ruta:
            Command()._rotar(Path(ruta), conservar=0)
            self.assertEqual(len(list(Path(ruta).glob("*.sql.gz"))), 5)


class QueSeVerificaTests(SimpleTestCase):
    def test_se_cuentan_las_tablas_que_dolería_perder(self):
        """
        No hacen falta todas: si estas están completas, el archivo se leyó
        entero. Pero tienen que estar la historia clínica y el registro de
        accesos, que son las que hay que conservar diez años por ley.
        """
        self.assertIn("registros_entradahistoria", TABLAS)
        self.assertIn("auditoria_accesoclinico", TABLAS)


class ProduccionTests(SimpleTestCase):
    """
    Lo que tiene que estar puesto cuando DEBUG se apaga.

    Se leen del módulo con `DEBUG=False` simulado, porque el bloque de
    endurecimiento corre una sola vez al importar los settings.
    """

    @staticmethod
    def _cargar(**entorno):
        """
        Importa los settings de cero con este entorno.

        Se saca de `sys.modules` en vez de usar `importlib.reload`: recargar
        re-ejecuta el módulo sobre el MISMO espacio de nombres, así que lo que
        puso una pasada anterior sobrevive. Con reload, el caso «en desarrollo
        no se fuerza HTTPS» leía el `SECURE_SSL_REDIRECT` que había dejado la
        carga de producción y daba un rojo que no era.
        """
        import importlib
        import sys

        with patch.dict("os.environ", entorno, clear=False):
            sys.modules.pop("cauce.settings", None)
            try:
                return importlib.import_module("cauce.settings")
            finally:
                sys.modules.pop("cauce.settings", None)

    def _settings_de_produccion(self, **entorno):
        return self._cargar(**{
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "x" * 64,
            "DATABASE_URL": "postgres://u:p@localhost:5432/x",
            **entorno,
        })

    def test_la_clave_de_desarrollo_no_arranca_en_produccion(self):
        """
        Está publicada en el repositorio: con ella cualquiera firma un JWT y
        entra como quien quiera, sin tocar la base ni conocer una contraseña. Y
        no hay señal de que esté pasando —los tokens falsos son indistinguibles
        de los buenos—, así que tiene que fallar al arrancar y no avisar en un
        log que nadie lee el día del despliegue.
        """
        with self.assertRaises(RuntimeError) as e:
            self._settings_de_produccion(DJANGO_SECRET_KEY="django-insecure-dev-key-change-me")
        self.assertIn("DJANGO_SECRET_KEY", str(e.exception))

    def test_en_desarrollo_la_clave_de_desarrollo_no_molesta(self):
        s = self._cargar(
            DJANGO_DEBUG="true", DJANGO_SECRET_KEY="django-insecure-dev-key-change-me",
        )
        self.assertTrue(s.DEBUG)

    def test_las_cookies_de_sesion_van_por_https(self):
        """La API usa JWT, pero el admin de Django existe y por ahí se entra a todo."""
        s = self._settings_de_produccion()
        self.assertTrue(s.SESSION_COOKIE_SECURE)
        self.assertTrue(s.CSRF_COOKIE_SECURE)

    def test_no_se_puede_embeber_en_un_iframe_ajeno(self):
        """Clickjacking sobre «llamar paciente» o «dar el alta»."""
        self.assertEqual(self._settings_de_produccion().X_FRAME_OPTIONS, "DENY")

    def test_reconoce_el_https_que_termina_el_proxy(self):
        """Sin esto Django ve http detrás del balanceador y redirige para siempre."""
        s = self._settings_de_produccion()
        self.assertEqual(s.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_hsts_se_puede_bajar_para_el_primer_despliegue(self):
        """El navegador lo recuerda: equivocarse con un año puesto se paga caro."""
        self.assertEqual(self._settings_de_produccion(DJANGO_HSTS_SECONDS="300").SECURE_HSTS_SECONDS, 300)

    def test_en_desarrollo_no_se_fuerza_https(self):
        """Forzarlo en local deja a todo el equipo con un redirect infinito."""
        s = self._cargar(DJANGO_DEBUG="true")
        self.assertFalse(getattr(s, "SECURE_SSL_REDIRECT", False))


class ChecklistDeDjangoTests(SimpleTestCase):
    def test_check_deploy_no_tiene_avisos(self):
        """
        `manage.py check --deploy` es la lista de Django, y se corre acá para que
        no dependa de que alguien se acuerde de mirarla. Cada vez que se agregue
        un aviso nuevo, esto se pone en rojo en vez de quedar pendiente.
        """
        import io

        from django.core.management import call_command as cc

        env = {
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "N7qL2xV9pR4tYw8mZ1cB6hJ3kD5fS0gA7eU2iO9lP4nQ8rT1vX6yW3zC5bM0jH2k",
            "DATABASE_URL": "postgres://u:p@localhost:5432/x",
        }
        import importlib

        with patch.dict("os.environ", env, clear=False):
            importlib.reload(importlib.import_module("cauce.settings"))
            from django.conf import settings as s
            from django.test import override_settings

            nuevos = importlib.import_module("cauce.settings")
            extra = {
                k: getattr(nuevos, k) for k in dir(nuevos)
                if k.isupper() and not k.startswith("_")
            }
            salida = io.StringIO()
            with override_settings(**extra):
                try:
                    cc("check", "--deploy", "--fail-level", "WARNING", stdout=salida, stderr=salida)
                except SystemExit:
                    self.fail(f"check --deploy tiene avisos:\n{salida.getvalue()}")
                except Exception as e:  # CommandError con los avisos adentro
                    self.fail(f"check --deploy tiene avisos:\n{salida.getvalue()}\n{e}")

        importlib.reload(importlib.import_module("cauce.settings"))
