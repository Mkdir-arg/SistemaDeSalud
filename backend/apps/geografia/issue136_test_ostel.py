"""Convivencia de #136 con el importador ya integrado en main; sólo XLSX sintéticos."""
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.financiadores.models import Afiliado
from apps.financiadores.ostel_synthetic import COLUMNAS, _persona
from apps.financiadores import test_ostel_importacion as escenario
from .contrato import validar_catalogo
from .issue136_test_puros import catalogo_ficticio
from .models import Lugar
from .servicios import ambito, resolver
from .sincronizacion import sincronizar


class ImportacionGeografiaOstelTest(APITestCase):
    setUpTestData = classmethod(escenario.ImportacionAdministrativaTests.setUpTestData.__func__)
    setUp = escenario.ImportacionAdministrativaTests.setUp
    preview = escenario.ImportacionAdministrativaTests.preview
    aplicar = escenario.ImportacionAdministrativaTests.aplicar
    corregir = escenario.ImportacionAdministrativaTests.corregir

    def importar(self, fila):
        respuesta = self.preview([fila], cobertura_habilitada=True)
        self.assertEqual(respuesta.status_code, 200)
        lote = respuesta.data
        if lote["resumen"]["revision"]:
            respuesta = self.corregir(lote)
            self.assertEqual(respuesta.status_code, 200)
            lote = respuesta.data
        aplicada = self.aplicar(lote)
        self.assertEqual(aplicada.status_code, 200)
        self.assertEqual(aplicada.data["resumen"]["aplicada"], 1)

    def existente(self, fila):
        raw = dict(zip(COLUMNAS, fila))
        sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()))
        entrada = {n: {"id": Lugar.objects.get(tipo=n, codigo=c).pk} for n, c in
            (("provincia", "01"), ("partido", "01001"), ("localidad", "01001000001"))}
        geo = resolver(entrada, dueno=ambito(financiador_id=self.org.pk))
        return Afiliado.objects.create(financiador=self.org, numero=raw["NROAFI"], numero_interno=raw["NUMERO"],
            documento=raw["NRODOC"], nombre=raw["APENOM"], cuil=raw["CUIL"], desde=timezone.localdate(),
            geografia=geo, **geo.textos)

    def test_alta_ostel_conserva_texto_sin_homologar_codloca(self):
        self.importar(_persona(136, NUMERO="00136", CODPROV="B", DESLOCA="Lugar importado ficticio", CODLOCA="999999"))
        obj = Afiliado.objects.get()
        self.assertEqual(obj.provincia, "Buenos Aires")
        self.assertEqual(obj.localidad, "Lugar importado ficticio")
        self.assertIsNone(obj.geografia_id)
        self.assertFalse(Lugar.objects.exists())

    def test_texto_ostel_nuevo_retira_referencias_previas_sin_modificar_catalogo(self):
        fila = _persona(137, NUMERO="00137", CODPROV="B", DESLOCA="Lugar importado ficticio")
        obj = self.existente(fila)
        anterior = obj.geografia
        self.importar(fila)
        obj.refresh_from_db()
        self.assertEqual((obj.provincia, obj.localidad), ("Buenos Aires", "Lugar importado ficticio"))
        self.assertIsNone(obj.geografia.provincia_id)
        self.assertIsNone(obj.geografia.partido_id)
        self.assertIsNone(obj.geografia.localidad_id)
        self.assertTrue(all(v["origen"] == "legado" for v in obj.geografia.datos().values()))
        anterior.refresh_from_db()
        self.assertEqual(anterior.datos()["provincia"]["nombre"], "Provincia de prueba")
        self.assertEqual(Lugar.objects.count(), 4)
        self.assertTrue(obj.historial.filter(cambios__has_key="geografia", origen="importacion").exists())

    def test_textos_ostel_vacios_no_borran_ubicacion_existente(self):
        fila = _persona(138, NUMERO="00138", CODPROV=None, DESLOCA=None)
        obj = self.existente(fila)
        anterior = obj.geografia_id
        self.importar(fila)
        obj.refresh_from_db()
        self.assertEqual(obj.geografia_id, anterior)
        self.assertEqual(obj.provincia, "Provincia de prueba")
        self.assertEqual(obj.localidad, "Localidad de prueba")
