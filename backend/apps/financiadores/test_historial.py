"""Cambios de configuración posteriores no alteran el hecho ni su responsable."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.finanzas.cobros import capturar_cobros_atencion
from apps.finanzas.models import ObligacionFinanciera
from apps.flujos.models import Nodo
from apps.registros.models import Ciudadano
from .cobros import resolver_saldo
from .models import ArancelConvenio, Convenio, Financiador, MembresiaFinanciador, ReservaCobertura
from .test_cobertura import CoberturaSetup


class HistorialCoberturaTests(CoberturaSetup, TestCase):
    def test_arancel_programado_para_mas_tarde_no_se_aplica_antes(self):
        self.politica(importe=Decimal("200"), vigente_desde=timezone.now()+timedelta(minutes=1))
        self.assertEqual(self.evaluar()["arancel"], "100.00")

    def test_retorno_general_queda_explicito_en_evaluacion(self):
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion, importe=None, vigente_desde=self.hoy, creado_por=self.admin)
        evaluacion = self.evaluar()
        self.assertEqual(evaluacion["arancel"], "100.00")
        self.assertEqual(evaluacion["origen_arancel"], "general_hospital")
        self.assertTrue(evaluacion["retorno_arancel_general"])

    def test_recuperacion_usa_nodo_original_aunque_se_mueva_catalogo(self):
        with patch("apps.financiadores.cobros.distribuir", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        nuevo = Nodo.objects.create(version=self.caso.version, tipo=Nodo.Tipo.ATENCION, titulo="Otra atención")
        self.prestacion.nodo = nuevo
        self.prestacion.save(update_fields=["nodo"])
        capturar_cobros_atencion(hecho.pk)
        cargo = ObligacionFinanciera.objects.get(hecho=hecho)
        self.assertEqual(cargo.importe_original, Decimal("80"))

    def test_resolucion_conserva_paciente_del_hecho(self):
        hecho = self.atencion()
        reserva = ReservaCobertura.objects.get(hecho=hecho)
        otro = Ciudadano.objects.create(institucion=self.institucion, nombre="Otra", apellido="Persona", documento="99999")
        self.caso.ciudadano = otro
        self.caso.save(update_fields=["ciudadano"])
        reserva.refresh_from_db()
        resolucion = resolver_saldo(reserva=reserva, usuario=self.admin, decision="paciente", importe=Decimal("20"), motivo="Acuerdo de la prestación original", evidencia="Constancia original", clave=uuid4())
        self.assertEqual(resolucion.obligacion.contraparte_referencia, f"paciente:{self.paciente.pk}")


class ConsultaFinanciadorTests(CoberturaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.operador)
        self.url = f"/api/financiadores/{self.financiador.pk}/aranceles/"

    def consultar_precio(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        return response.data["results"][0]

    def test_consulta_muestra_general_excepcion_y_retorno_sin_modificar_cupo(self):
        self.assertEqual(self.consultar_precio()["arancel"], "100.00")
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion, importe=Decimal("150"), vigente_desde=self.hoy, creado_por=self.admin)
        precio = self.consultar_precio()
        self.assertEqual(precio["arancel"], self.evaluar()["arancel"])
        self.assertEqual(precio["arancel_general"], "100.00")
        self.assertEqual(precio["origen_arancel"], "acordado_financiador")
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion, importe=None, vigente_desde=self.hoy, creado_por=self.admin)
        precio = self.consultar_precio()
        self.assertTrue(precio["retorno_arancel_general"])
        self.assertEqual(precio["arancel"], "100.00")
        self.assertFalse(ReservaCobertura.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_precio_pendiente_y_sin_cobro_no_se_confunden(self):
        self.politica(importe=None)
        precio = self.consultar_precio()
        self.assertEqual(precio["estado"], "arancel_pendiente")
        self.assertIsNone(precio["arancel"])
        self.politica(cobrar=False)
        precio = self.consultar_precio()
        self.assertEqual(precio["estado"], "sin_cobro")
        self.assertEqual(precio["arancel"], "0.00")

    def test_aranceles_restringidos_al_convenio_activo_y_solo_lectura(self):
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.consultar_precio()["arancel"], "100.00")
        self.assertEqual(self.client.post(self.url, {"arancel": "1"}).status_code, 405)
        otra = Financiador.objects.create(nombre="Otro financiador", tipo="mutual")
        self.assertEqual(self.client.get(f"/api/financiadores/{otra.pk}/aranceles/").status_code, 404)
        self.convenio.estado = "propuesto"
        self.convenio.save(update_fields=["estado"])
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    def test_excepcion_ajena_y_precio_futuro_no_se_filtran(self):
        otra = Financiador.objects.create(nombre="Otro financiador", tipo="mutual")
        convenio = Convenio.objects.create(financiador=otra, institucion=self.institucion, estado="activo", propuesto_por="plataforma", creado_por=self.admin)
        ArancelConvenio.objects.create(convenio=convenio, prestacion=self.prestacion, importe=Decimal("999"), vigente_desde=self.hoy, creado_por=self.admin)
        self.politica(importe=Decimal("200"), vigente_desde=timezone.now()+timedelta(minutes=1))
        self.assertEqual(self.consultar_precio()["arancel"], "100.00")

    def test_actividad_no_mezcla_organizaciones_ni_expone_contexto_clinico(self):
        self.reservar()
        url = f"/api/financiadores/{self.financiador.pk}/actividad/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(set(response.data["results"][0]), {
            "id", "fecha", "hospital", "prestacion", "numero", "documento", "cantidad",
            "cubiertas", "estado", "discrepancia", "importe_financiador", "estado_cobro", "acceso",
            "nombre", "plan", "codigo", "importe_acuerdos", "importe_asignado",
        })
        otra = Financiador.objects.create(nombre="Otro financiador", tipo="mutual")
        MembresiaFinanciador.objects.create(financiador=otra, usuario=self.operador, rol="auditor")
        response = self.client.get(f"/api/financiadores/{otra.pk}/actividad/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
