"""Elección del almacenamiento de archivos por variables de entorno (#171)."""
from django.test import SimpleTestCase

from config import almacenamiento

# Credenciales sintéticas: nunca se conectan a nada.
BUCKET = {
    "BUCKET": "bucket-sintetico",
    "ACCESS_KEY_ID": "clave-sintetica",
    "SECRET_ACCESS_KEY": "secreto-sintetico",
    "ENDPOINT": "https://s3.invalid",
}


class EleccionDeAlmacenamientoTests(SimpleTestCase):
    def test_sin_variables_sigue_en_disco_local(self):
        storages, en_bucket = almacenamiento.storages({}, "/privado/facturas")
        self.assertFalse(en_bucket)
        self.assertEqual(storages["default"]["BACKEND"], "django.core.files.storage.FileSystemStorage")
        self.assertEqual(storages["facturas"], {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": "/privado/facturas"},
        })

    def test_variables_vacias_cuentan_como_ausentes(self):
        _, en_bucket = almacenamiento.storages({nombre: " " for nombre in BUCKET}, "/f")
        self.assertFalse(en_bucket)

    def test_con_variables_usa_un_bucket_privado_con_prefijo_de_facturas(self):
        storages, en_bucket = almacenamiento.storages(BUCKET, "/privado/facturas")
        self.assertTrue(en_bucket)
        default, facturas = storages["default"], storages["facturas"]
        self.assertEqual(default["BACKEND"], "storages.backends.s3.S3Storage")
        self.assertEqual(facturas["BACKEND"], "storages.backends.s3.S3Storage")
        opciones = default["OPTIONS"]
        self.assertEqual(opciones["bucket_name"], "bucket-sintetico")
        self.assertEqual(opciones["endpoint_url"], "https://s3.invalid")
        self.assertEqual(opciones["region_name"], "auto")
        self.assertEqual(opciones["addressing_style"], "virtual")
        self.assertIsNone(opciones["default_acl"])
        self.assertTrue(opciones["querystring_auth"])
        self.assertFalse(opciones["file_overwrite"])
        self.assertNotIn("location", opciones)
        self.assertEqual(facturas["OPTIONS"]["location"], "facturas")

    def test_region_y_estilo_configurables(self):
        storages, _ = almacenamiento.storages({**BUCKET, "REGION": "sa-east-1", "BUCKET_ADDRESSING_STYLE": "path"}, "/f")
        self.assertEqual(storages["default"]["OPTIONS"]["region_name"], "sa-east-1")
        self.assertEqual(storages["default"]["OPTIONS"]["addressing_style"], "path")
        with self.assertRaisesMessage(ValueError, "BUCKET_ADDRESSING_STYLE"):
            almacenamiento.storages({**BUCKET, "BUCKET_ADDRESSING_STYLE": "otro"}, "/f")

    def test_configuracion_parcial_no_cae_a_disco_en_silencio(self):
        parcial = {**BUCKET, "SECRET_ACCESS_KEY": ""}
        with self.assertRaisesMessage(ValueError, "SECRET_ACCESS_KEY"):
            almacenamiento.storages(parcial, "/f")

    def test_las_opciones_son_validas_para_s3storage(self):
        from storages.backends.s3 import S3Storage

        storages, _ = almacenamiento.storages(BUCKET, "/f")
        for alias in ("default", "facturas"):
            storage = S3Storage(**storages[alias]["OPTIONS"])
            self.assertEqual(storage.bucket_name, "bucket-sintetico")
        self.assertEqual(S3Storage(**storages["facturas"]["OPTIONS"]).location, "facturas")
