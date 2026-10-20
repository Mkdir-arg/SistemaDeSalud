"""Adjuntos sobre un almacenamiento de objetos, sin rutas locales (#171).

Se usa `InMemoryStorage` en lugar del bucket: no tiene `.path()` ni disco,
igual que `S3Storage`. Datos y archivos sintéticos.
"""
import hashlib

from django.core.files.storage import FileSystemStorage, InMemoryStorage, storages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.financiadores import models as fm
from apps.financiadores.facturas import almacenamiento_privado
from apps.instituciones.models import Institucion

from .models import ArchivoClinico

EN_MEMORIA = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "facturas": {"BACKEND": "django.core.files.storage.InMemoryStorage", "OPTIONS": {"location": "facturas"}},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PDF = b"%PDF-1.4 adjunto sintetico #171"


def bytes_de(respuesta):
    return b"".join(respuesta.streaming_content)


@override_settings(STORAGES=EN_MEMORIA)
class AdjuntoClinicoEnObjetosTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital sintético 171")
        self.medico = Usuario.objects.create_user("medico-171@example.test", "x")
        Membresia.objects.create(usuario=self.medico, institucion=self.inst, rol=Membresia.Rol.MEDICO)
        otra = Institucion.objects.create(nombre="Otro hospital 171")
        self.ajeno = Usuario.objects.create_user("ajeno-171@example.test", "x")
        Membresia.objects.create(usuario=self.ajeno, institucion=otra, rol=Membresia.Rol.MEDICO)

    def subir(self):
        self.client.force_authenticate(self.medico)
        respuesta = self.client.post("/api/archivos/", {
            "archivo": SimpleUploadedFile("informe.pdf", PDF, content_type="application/pdf"),
            "institucion": self.inst.pk,
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta.data["ruta"]

    def test_sube_y_descarga_el_mismo_contenido_guardando_solo_la_clave(self):
        self.assertIsInstance(storages["default"], InMemoryStorage)
        ruta = self.subir()
        self.assertRegex(ruta, rf"^uploads/{self.inst.pk}/[0-9a-f]{{32}}\.pdf$")
        meta = ArchivoClinico.objects.get(ruta=ruta)
        self.assertEqual(meta.sha256, hashlib.sha256(PDF).hexdigest())
        self.assertTrue(storages["default"].exists(ruta))

        respuesta = self.client.get(f"/api/archivos/descargar/{ruta}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/pdf")
        self.assertEqual(respuesta["Cache-Control"], "private, no-store")
        self.assertNotIn("Location", respuesta)
        self.assertEqual(hashlib.sha256(bytes_de(respuesta)).hexdigest(), meta.sha256)
        self.assertTrue(AccesoClinico.objects.filter(recurso="archivoclinico", objeto_id=str(meta.pk)).exists())

    def test_sin_historia_clinica_recibe_403_sin_contenido_ni_redireccion(self):
        ruta = self.subir()
        self.client.force_authenticate(self.ajeno)
        respuesta = self.client.get(f"/api/archivos/descargar/{ruta}")
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn("Location", respuesta)
        self.assertNotIn(PDF, respuesta.content)


@override_settings(STORAGES=EN_MEMORIA, SALUD_FACTURAS_ADJUNTOS=True)
class AdjuntoDeFacturaEnObjetosTests(APITestCase):
    def setUp(self):
        self.org = fm.Financiador.objects.create(nombre="Mutual sintética 171", tipo="mutual")
        self.user = Usuario.objects.create_user("facturas-171@example.test", "x")
        fm.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="operador")
        institucion = Institucion.objects.create(nombre="Hospital facturas 171")
        convenio = fm.Convenio.objects.create(financiador=self.org, institucion=institucion,
                                              propuesto_por="financiador", creado_por=self.user)
        self.client.force_authenticate(self.user)
        self.base = f"/api/financiadores/{self.org.pk}/facturas/"
        alta = self.client.post(self.base, {
            "direccion": "recibida", "contraparte_tipo": "institucion", "convenio": convenio.pk,
            "tipo": "factura", "letra": "A", "numero": "S171-001", "fecha": str(timezone.localdate()),
            "importe": "10.00",
        }, format="json")
        self.assertEqual(alta.status_code, 201, alta.data)
        self.pk = alta.data["id"]

    def test_el_almacenamiento_privado_es_storages_facturas_si_no_es_disco(self):
        self.assertIs(almacenamiento_privado(), storages["facturas"])

    def test_sube_y_descarga_en_el_almacenamiento_de_facturas(self):
        ruta = self.base + f"{self.pk}/adjunto/"
        subida = self.client.post(ruta, {"archivo": SimpleUploadedFile("f.pdf", PDF, content_type="application/pdf")},
                                  format="multipart")
        self.assertEqual(subida.status_code, 201, subida.data)
        obj = fm.RegistroFactura.objects.get(pk=self.pk)
        self.assertRegex(obj.adjunto_ruta, r"^[0-9a-f]{32}\.pdf$")
        self.assertTrue(storages["facturas"].exists(obj.adjunto_ruta))
        self.assertFalse(storages["default"].exists(obj.adjunto_ruta))
        descarga = self.client.get(ruta)
        self.assertEqual(descarga.status_code, 200)
        self.assertNotIn("Location", descarga)
        self.assertEqual(hashlib.sha256(bytes_de(descarga)).hexdigest(), obj.adjunto_sha256)


class FacturasEnDiscoTests(APITestCase):
    """Sin bucket se mantiene el disco local leído de la configuración vigente."""

    def test_en_disco_usa_la_carpeta_de_la_configuracion(self):
        almacenamiento = almacenamiento_privado()
        self.assertIsInstance(almacenamiento, FileSystemStorage)
