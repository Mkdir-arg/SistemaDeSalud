"""Resumen administrativo previo a la atención y convivencia con el texto legado."""
from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

from .administrativa import resumenes_administrativos
from .models import AfiliacionCaso, Afiliado, ConfiguracionHospital, Convenio, Financiador
from .test_cobertura import CoberturaSetup


class CoberturaAdministrativaTests(CoberturaSetup, TestCase):
    def setUp(self):
        super().setUp()
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="administrativo")
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)
        self.url = f"/api/ciudadanos/{self.paciente.pk}/"
        self.paciente.obra_social = "Declaración antigua"
        self.paciente.save(update_fields=["obra_social"])

    def resumen(self):
        response = self.client.get(self.url, {"institucion": self.institucion.pk})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["cobertura_administrativa"]

    def test_admision_ve_padron_sin_caso_ni_historia_y_no_crea_seleccion(self):
        AfiliacionCaso.objects.all().delete()
        dato = self.resumen()
        self.assertEqual(dato["estado"], "vigente")
        self.assertEqual(dato["declaracion_legada"], "Declaración antigua")
        self.assertEqual(dato["afiliaciones"][0]["numero"], "00001")
        response = self.client.get(self.url)
        self.assertEqual(response.data["condiciones"], "")
        self.assertFalse(AfiliacionCaso.objects.exists())
        self.assertNotIn("importe", str(dato))

    def test_cambio_padron_actualiza_resumen_y_preserva_eleccion_anterior(self):
        original = self.seleccion.plan_id
        self.afiliado.plan = None
        self.afiliado.save(update_fields=["plan"])
        self.assertIsNone(self.resumen()["afiliaciones"][0]["plan_id"])
        self.seleccion.refresh_from_db()
        self.assertEqual(self.seleccion.plan_id, original)

    def test_variaciones_de_vigencia_no_presentan_legado_como_verificado(self):
        for campo, valor in [("finalizado_en", timezone.now()), ("desde", self.hoy + timedelta(days=1))]:
            with self.subTest(campo=campo):
                Afiliado.objects.filter(pk=self.afiliado.pk).update(**{campo: valor})
                self.assertEqual(self.resumen()["estado"], "sin_padron")
                Afiliado.objects.filter(pk=self.afiliado.pk).update(finalizado_en=None, desde=self.hoy)
        self.convenio.estado, self.convenio.cerrado_en = "finalizado", timezone.now()
        self.convenio.save()
        self.assertEqual(self.resumen()["afiliaciones"], [])

    def test_plan_inactivo_se_informa_pero_no_se_ofrece_como_seleccionable(self):
        self.plan.activo = False
        self.plan.save(update_fields=["activo"])
        afiliacion = self.resumen()["afiliaciones"][0]
        self.assertFalse(afiliacion["seleccionable"])
        self.assertIn("inactivo", afiliacion["motivo"])

    def test_varias_afiliaciones_se_muestran_sin_elegir_otra_para_el_caso(self):
        financiador = Financiador.objects.create(nombre="Mutual", tipo="mutual")
        Convenio.objects.create(financiador=financiador, institucion=self.institucion,
                                estado="activo", propuesto_por="plataforma", creado_por=self.admin)
        Afiliado.objects.create(financiador=financiador, documento=self.paciente.documento,
                                nombre="Ana", numero="123", desde=self.hoy)
        self.assertEqual(self.resumen()["estado"], "multiple")
        self.assertEqual(len(self.resumen()["afiliaciones"]), 2)
        self.assertEqual(AfiliacionCaso.objects.get(caso=self.caso).afiliado_id, self.afiliado.pk)

    def test_nn_y_documento_ajeno_en_query_no_buscan_padron_arbitrario(self):
        self.paciente.documento = ""
        self.paciente.save(update_fields=["documento"])
        response = self.client.get(self.url, {"documento": self.afiliado.documento})
        self.assertEqual(response.data["cobertura_administrativa"]["estado"], "sin_documento")
        self.assertEqual(response.data["cobertura_administrativa"]["afiliaciones"], [])

    def test_hospital_habilitado_rechaza_cambio_legado_pero_acepta_reenvio_identico(self):
        for texto in ["Otra cobertura", ""]:
            response = self.client.patch(self.url, {"obra_social": texto}, format="json")
            self.assertEqual(response.status_code, 400)
        response = self.client.patch(self.url, {"obra_social": "Declaración antigua", "domicilio": "Nueva dirección"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.obra_social, "Declaración antigua")

    def test_hospital_habilitado_rechaza_alta_legada_incluso_sin_documento(self):
        datos = {"institucion": self.institucion.pk, "nombre": "NN", "obra_social": "inventada"}
        self.assertEqual(self.client.post("/api/ciudadanos/", datos, format="json").status_code, 400)
        datos.pop("obra_social")
        self.assertEqual(self.client.post("/api/ciudadanos/", datos, format="json").status_code, 201)

    def test_hospital_no_habilitado_conserva_edicion_declarada(self):
        ConfiguracionHospital.objects.filter(institucion=self.institucion).update(activo=False)
        response = self.client.patch(self.url, {"obra_social": "Declarada nueva"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.resumen()["estado"], "no_habilitada")
        self.assertEqual(self.resumen()["afiliaciones"], [])

    def test_rol_de_reportes_en_otro_hospital_no_amplia_padron(self):
        otro = Institucion.objects.create(nombre="Otro")
        Membresia.objects.create(usuario=self.usuario, institucion=otro, rol="reportes")
        ciudadano = Ciudadano.objects.create(institucion=otro, documento=self.paciente.documento, nombre="Otra ficha")
        response = self.client.get("/api/ciudadanos/", {"institucion": otro.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(self.client.get(f"/api/ciudadanos/{ciudadano.pk}/").status_code, 404)
        self.assertEqual(self.client.get(self.url, {"institucion": otro.pk}).status_code, 404)
        response = self.client.get("/api/ciudadanos/configuracion-cobertura/", {"institucion": otro.pk})
        self.assertEqual(response.status_code, 403)

    def test_configuracion_para_alta_exige_hospital_y_permiso(self):
        url = "/api/ciudadanos/configuracion-cobertura/"
        self.assertEqual(self.client.get(url).status_code, 400)
        response = self.client.get(url, {"institucion": self.institucion.pk})
        self.assertEqual(response.data, {"institucion": self.institucion.pk, "habilitada": True})
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(url, {"institucion": self.institucion.pk}).status_code, 403)

    def test_consultas_del_resumen_no_crecen_por_fila_y_separan_convenios(self):
        ciudadanos = [self.paciente]
        for i in range(29):
            ciudadanos.append(Ciudadano.objects.create(institucion=self.institucion, documento=f"0099{i:04d}", nombre="Paciente"))
            Afiliado.objects.create(financiador=self.financiador, documento=ciudadanos[-1].documento,
                                    nombre="Persona", numero=f"num-{i}", desde=self.hoy)
        cantidades = []
        for cantidad in (3, 30):
            with CaptureQueriesContext(connection) as consultas:
                resumen = resumenes_administrativos(ciudadanos[:cantidad])
            cantidades.append(len(consultas))
            self.assertEqual(len(resumen), cantidad)
            self.assertTrue(all(r["estado"] == "vigente" for r in resumen.values()))
        self.assertEqual(cantidades[0], cantidades[1])
        self.assertLessEqual(cantidades[1], 3)
