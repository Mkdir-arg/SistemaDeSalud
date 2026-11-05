"""CODPAR de origen no se publica por el circuito administrativo."""
from copy import deepcopy
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from . import models as m
from .importacion_respuesta import huella_lote
from .ostel_synthetic import Lote, _persona, generar_xlsx
from .test_codpar_importacion import CodparImportacionFixture
from .serializers import (
    ImportacionSerializer, ImportacionRespuestaCompletaSerializer, ImportacionCambiosSerializer,
)


class PresentacionImportacionTests(SimpleTestCase):
    def test_presentacion_no_muta_fuente_ni_huella_y_conserva_v1_v2(self):
        for version in (1, 2, 3):
            original = ({"CODPAR": " 00-XD1 ", "CUILTIT": "FICTICIO"}
                        if version == 3 else ["CODPAR", "0007", "FICTICIO"])
            filas = [{"fila": 1, "original": original, "estado": "valida", "datos": {}}]
            lote = m.Importacion(id=71, tipo="padron", version=version,
                                filas=deepcopy(filas), resumen={}, estado="preview")
            lote.filas_cambiadas = deepcopy(filas)
            lote.modo_respuesta = "cambios"
            lote.huella_lote = huella_lote(lote)
            lote.base_huella = "b" * 64
            huella = huella_lote(lote)
            for serializer in (ImportacionSerializer, ImportacionRespuestaCompletaSerializer,
                               ImportacionCambiosSerializer):
                with self.subTest(version=version, serializer=serializer.__name__):
                    respuesta = serializer(lote).data
                    campo = "filas_cambiadas" if serializer is ImportacionCambiosSerializer else "filas"
                    esperado = {"CUILTIT": "FICTICIO"} if version == 3 else original
                    self.assertEqual(respuesta[campo][0]["original"], esperado)
                    self.assertEqual(lote.filas, filas)
                    self.assertEqual(lote.filas_cambiadas, filas)
                    self.assertEqual(huella_lote(lote), huella)


class PrivacidadImportacionTests(CodparImportacionFixture, APITestCase):
    def comprobar_respuesta(self, respuesta, campo="filas"):
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        for fila in respuesta.data[campo]:
            self.assertNotIn("CODPAR", fila["original"])
            self.assertIn("CUILTIT", fila["original"])

    def test_codpar_no_sale_por_preview_revision_listado_ni_confirmacion(self):
        archivo = generar_xlsx(Lote("privacidad", (
            _persona(2, NUMERO="000002", CODPAR=" 00-XD2 "),
        )))
        preview = self.client.post(self.base + "previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("ficticio.xlsx", archivo),
            "clave": str(uuid4()), "cobertura_habilitada": False,
        }, format="multipart")
        self.comprobar_respuesta(preview)
        lote = m.Importacion.objects.get(pk=preview.data["id"])
        originales = deepcopy(lote.filas[0]["original"])
        fila = preview.data["filas"][0]
        correccion = self.client.post(self.base + "subsanar-ostel/", {
            "importacion": lote.pk, "fila": fila["fila"], "revision": fila["revision"],
            "datos": fila["datos"], "motivo": "Revisión ficticia de privacidad",
        }, format="json")
        self.comprobar_respuesta(correccion)
        lote.refresh_from_db()
        self.assertEqual(lote.filas[0]["original"], originales)
        confirmacion = self.client.post(self.base + "confirmar-importacion/", {
            "importacion": lote.pk, "modo_respuesta": "cambios",
            "huella_lote": huella_lote(lote),
        }, format="json")
        self.assertEqual(confirmacion.data["modo_respuesta"], "cambios")
        self.assertTrue(confirmacion.data["filas_cambiadas"])
        self.comprobar_respuesta(confirmacion, "filas_cambiadas")
        completa = self.client.post(self.base + "confirmar-importacion/", {
            "importacion": lote.pk,
        }, format="json")
        self.comprobar_respuesta(completa)
        antes = list(m.Importacion.objects.order_by("pk").values())
        eventos = list(m.EventoCobertura.objects.order_by("pk").values())
        listado = self.client.get(self.base + "importaciones/")
        self.assertEqual(listado.status_code, 200)
        for registro in listado.data["results"]:
            for original in (f["original"] for f in registro["filas"]):
                self.assertNotIn("CODPAR", original)
        self.assertEqual(list(m.Importacion.objects.order_by("pk").values()), antes)
        despues = list(m.EventoCobertura.objects.order_by("pk").values())
        self.assertEqual(despues[:-1], eventos)
        self.assertEqual(despues[-1]["accion"], "consultar_importaciones")
        lote.refresh_from_db()
        self.assertEqual(lote.filas[0]["original"], originales)
        self.designar()
        copia = self.copiar()
        self.assertEqual(copia.status_code, 200, copia.data)
        self.assertEqual(copia.data["codpar_ostel"], " 00-XD1 ")
