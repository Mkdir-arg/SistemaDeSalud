"""La recarga de la demo vacía los archivos de la app en el bucket (#171, D4).

`InMemoryStorage` hace de bucket. Datos sintéticos.
"""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from apps.demo import archivos

EN_MEMORIA = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "facturas": {"BACKEND": "django.core.files.storage.InMemoryStorage", "OPTIONS": {"location": "facturas"}},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
COMANDO = "apps.demo.management.commands.seed_entorno_demo"


def poblar():
    default, facturas = storages["default"], storages["facturas"]
    default.save("uploads/1/a.pdf", ContentFile(b"a"))
    default.save("uploads/2/b.pdf", ContentFile(b"b"))
    default.save("ajeno/c.txt", ContentFile(b"c"))
    facturas.save("f.pdf", ContentFile(b"f"))


class BucketEnMemoria(SimpleTestCase):
    """Un bucket vacío por test: cada override de STORAGES rehace los almacenamientos."""

    def setUp(self):
        ajuste = override_settings(STORAGES=EN_MEMORIA, ALMACENAMIENTO_EN_BUCKET=True, ENTORNO="demo")
        ajuste.enable()
        self.addCleanup(ajuste.disable)


class VaciadoDeArchivosTests(BucketEnMemoria):
    def test_lista_solo_los_prefijos_de_la_app(self):
        poblar()
        self.assertEqual(sorted(archivos.claves_a_vaciar()), [
            ("default", "uploads/1/a.pdf"), ("default", "uploads/2/b.pdf"), ("facturas", "f.pdf"),
        ])

    def test_borrar_deja_solo_lo_ajeno_a_la_app(self):
        poblar()
        self.assertEqual(archivos.borrar(archivos.claves_a_vaciar()), [])
        self.assertEqual(archivos.claves_a_vaciar(), [])
        self.assertTrue(storages["default"].exists("ajeno/c.txt"))

    def test_bucket_vacio(self):
        self.assertEqual(archivos.claves_a_vaciar(), [])

    def test_fuera_de_demo_o_sin_bucket_no_toca_nada(self):
        poblar()
        for ajuste in ({"ENTORNO": "produccion"}, {"ENTORNO": "desarrollo"}, {"ALMACENAMIENTO_EN_BUCKET": False}):
            with self.subTest(**ajuste), override_settings(**ajuste):
                self.assertEqual(archivos.claves_a_vaciar(), [])
        self.assertTrue(storages["default"].exists("uploads/1/a.pdf"))

    def test_un_borrado_fallido_se_informa_y_no_frena_el_resto(self):
        poblar()
        claves = archivos.claves_a_vaciar()
        original = storages["default"].delete

        def falla(nombre):
            if nombre == "uploads/1/a.pdf":
                raise OSError("sintético")
            return original(nombre)

        with patch.object(storages["default"], "delete", side_effect=falla), \
                self.assertLogs("apps.demo.archivos", "ERROR"):
            self.assertEqual(archivos.borrar(claves), [("default", "uploads/1/a.pdf")])
        self.assertFalse(storages["facturas"].exists("f.pdf"))


class SeedEntornoDemoVaciaArchivosTests(BucketEnMemoria):
    """El comando real exige PostgreSQL; se reemplazan la conexión y la carga."""

    def correr(self, carga):
        conexion = MagicMock(vendor="postgresql", settings_dict={"NAME": "sintetica"})
        salida = StringIO()
        with patch(f"{COMANDO}.connection", conexion), \
                patch(f"{COMANDO}.Command._cargar", side_effect=carga), \
                patch(f"{COMANDO}.Command._resumen"):
            call_command("seed_entorno_demo", interactive=False, stdout=salida)
        return salida.getvalue()

    def test_borra_lo_anterior_y_conserva_lo_que_crea_la_carga(self):
        poblar()

        def carga(*_):
            storages["default"].save("uploads/1/nuevo.pdf", ContentFile(b"n"))

        salida = self.correr(carga)
        self.assertEqual(archivos.claves_a_vaciar(), [("default", "uploads/1/nuevo.pdf")])
        self.assertIn("3 archivos", salida)

    def test_si_la_carga_falla_no_borra_archivos(self):
        poblar()

        def carga(*_):
            raise CommandError("paso sintético falló")

        with self.assertRaises(CommandError):
            self.correr(carga)
        self.assertEqual(len(archivos.claves_a_vaciar()), 3)

    def test_en_produccion_se_niega_sin_tocar_archivos(self):
        poblar()
        with override_settings(ENTORNO="produccion"), self.assertRaises(CommandError):
            self.correr(lambda *_: None)
        with override_settings(ENTORNO="demo"):
            self.assertEqual(len(archivos.claves_a_vaciar()), 3)
