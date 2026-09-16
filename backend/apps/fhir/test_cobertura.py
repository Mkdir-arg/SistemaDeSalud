"""FHIR administrativo: referencia hospitalaria, padrón actual y evidencia de lectura."""
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia
from apps.auditoria.models import AccesoClinico
from apps.financiadores.models import Afiliado, ConfiguracionHospital, Convenio, Financiador
from apps.financiadores.test_cobertura import CoberturaSetup
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano


class CoverageTests(CoberturaSetup, TestCase):
    def setUp(self):
        super().setUp()
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="administrativo")
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)
        self.url = f"/fhir/Coverage?beneficiary=Patient/{self.paciente.pk}"

    def datos(self, url=None):
        response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200, response.content)
        return json.loads(response.content)

    def test_contrato_r4_minimo_y_auditoria_identificada_sin_historia_ni_importes(self):
        recurso = self.datos()["entry"][0]["resource"]
        self.assertEqual(recurso["resourceType"], "Coverage")
        self.assertEqual(recurso["status"], "active")
        self.assertEqual(recurso["beneficiary"]["reference"], f"Patient/{self.paciente.pk}")
        self.assertEqual(recurso["identifier"][0]["value"], "00001")
        self.assertEqual(recurso["contained"][0]["resourceType"], "Organization")
        self.assertEqual(recurso["payor"][0]["reference"], "#financiador")
        self.assertEqual(recurso["class"][0]["name"], self.plan.nombre)
        self.assertEqual(recurso["period"], {"start": self.hoy.isoformat()})
        self.assertNotIn("costToBeneficiary", recurso)
        self.assertEqual(self.datos(f"/fhir/Coverage/{recurso['id']}"), recurso)
        self.assertEqual(AccesoClinico.objects.filter(ciudadano=self.paciente, recurso="cobertura").count(), 2)

    def test_no_hay_busqueda_masiva_por_documento_y_no_exporta_texto_como_afiliacion(self):
        self.paciente.obra_social = "Nombre sin verificar"
        self.paciente.save(update_fields=["obra_social"])
        self.assertEqual(self.client.get("/fhir/Coverage?identifier=00111222").status_code, 400)
        Afiliado.objects.filter(pk=self.afiliado.pk).update(finalizado_en=timezone.now())
        self.assertEqual(self.datos()["total"], 0)
        self.assertEqual(self.client.get(f"/fhir/Coverage/{self.paciente.pk}-{self.afiliado.pk}").status_code, 404)
        paciente = self.datos(f"/fhir/Patient/{self.paciente.pk}")
        self.assertEqual(paciente["extension"][0]["valueString"], "Nombre sin verificar")

    def test_convenio_cerrado_plan_inactivo_y_hospital_no_habilitado_no_exportan(self):
        self.convenio.cerrado_en, self.convenio.estado = timezone.now(), "finalizado"
        self.convenio.save()
        self.assertEqual(self.datos()["total"], 0)
        self.convenio.cerrado_en, self.convenio.estado = None, "activo"
        self.convenio.save()
        self.plan.activo = False
        self.plan.save(update_fields=["activo"])
        self.assertEqual(self.datos()["total"], 0)
        self.plan.activo = True
        self.plan.save(update_fields=["activo"])
        ConfiguracionHospital.objects.filter(institucion=self.institucion).update(activo=False)
        self.assertEqual(self.datos()["total"], 0)

    def test_varias_afiliaciones_paginadas_y_no_seleccionadas_automaticamente(self):
        otro = Financiador.objects.create(nombre="Otra mutual", tipo="mutual")
        Convenio.objects.create(financiador=otro, institucion=self.institucion, estado="activo", creado_por=self.admin)
        Afiliado.objects.create(financiador=otro, numero="00003", documento=self.paciente.documento,
                                nombre="Ana", desde=self.hoy)
        primera = self.datos(self.url + "&_count=1")
        self.assertEqual(primera["total"], 2)
        siguiente = next(e["url"] for e in primera["link"] if e["relation"] == "next")
        segunda = self.datos(siguiente)
        self.assertNotEqual(primera["entry"][0]["resource"]["id"], segunda["entry"][0]["resource"]["id"])
        self.seleccion.refresh_from_db()
        self.assertEqual(self.seleccion.afiliado_id, self.afiliado.pk)

    def test_institucion_y_permiso_se_validan_juntos_aun_con_documento_coincidente(self):
        otra = Institucion.objects.create(nombre="Otro hospital")
        paciente = Ciudadano.objects.create(institucion=otra, documento=self.paciente.documento, nombre="Ana")
        Membresia.objects.create(usuario=self.usuario, institucion=otra, rol="reportes")
        self.assertEqual(self.client.get(f"/fhir/Coverage?beneficiary=Patient/{paciente.pk}").status_code, 404)
        self.assertEqual(self.client.get(f"/fhir/Coverage/{paciente.pk}-{self.afiliado.pk}").status_code, 404)
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_error_auditoria_impide_entregar_afiliacion(self):
        self.client.raise_request_exception = False
        with patch("apps.auditoria.mixins.AccesoClinico.objects.create", side_effect=RuntimeError("prueba")):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'"resourceType": "Coverage"', response.content)
