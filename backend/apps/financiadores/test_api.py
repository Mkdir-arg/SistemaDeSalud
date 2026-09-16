"""Aislamiento HTTP y permisos de los nuevos ámbitos de cobertura."""
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.finanzas.test_cobros import CobrosSetup
from . import models as m
from .importaciones import generar_plantilla


class ApiFinanciadoresTests(CobrosSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = m.Financiador.objects.create(nombre="Mutual A", tipo="mutual")
        self.otra = m.Financiador.objects.create(nombre="Mutual B", tipo="mutual")
        self.operador = Usuario.objects.create_user("financiador@test.local", "clave")
        self.membresia = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.operador, rol="admin")
        self.plan = m.Plan.objects.create(financiador=self.org, codigo="A", nombre="Plan A")
        self.comun = m.PrestacionComun.objects.create(codigo="RX", nombre="Radiografía", categoria="Imágenes")
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.client.force_authenticate(self.operador)

    def post(self, action, data):
        return self.client.post(self.base+action+"/", data, format="json")

    def test_listado_organizaciones_y_me_no_mezclan_hospitales(self):
        response = self.client.get("/api/financiadores/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([x["id"] for x in response.data["results"]], [self.org.pk])
        me = self.client.get("/api/usuarios/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["financiadores"][0]["id"], self.org.pk)
        self.assertEqual(me.data["capacidades_por_institucion"], {})

    def test_otra_organizacion_y_alta_reservadas_a_plataforma(self):
        self.assertEqual(self.client.get(f"/api/financiadores/{self.otra.pk}/padron/").status_code, 404)
        self.assertEqual(self.client.post("/api/financiadores/", {"nombre": "Intrusa", "tipo": "otro"}).status_code, 403)
        self.assertEqual(self.client.get(f"/api/coberturas/opciones/?institucion={self.institucion.pk}").status_code, 403)

    def test_plan_ajeno_no_puede_usarse_en_regla_ni_padron(self):
        plan_b = m.Plan.objects.create(financiador=self.otra, codigo="B", nombre="B")
        response = self.post("reglas", {"plan": plan_b.pk, "prestacion": self.comun.pk, "porcentaje": "80", "cupo": 6, "periodo": "anio", "vigente_desde": str(timezone.localdate())})
        self.assertEqual(response.status_code, 400)
        response = self.post("padron", {"numero": "001", "documento": "0001", "nombre": "Prueba", "plan": plan_b.pk, "desde": str(timezone.localdate())})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(m.Afiliado.objects.exists())

    def test_regla_nueva_no_admite_porcentaje_invalido_ni_retroactividad(self):
        payload = {"prestacion": self.comun.pk, "porcentaje": "101", "cupo": 6, "periodo": "anio", "vigente_desde": str(timezone.localdate())}
        self.assertEqual(self.post("reglas", payload).status_code, 400)
        payload.update(porcentaje="80", vigente_desde=str(timezone.localdate()-timedelta(days=1)))
        self.assertEqual(self.post("reglas", payload).status_code, 400)
        self.assertFalse(m.ReglaCobertura.objects.exists())

    def test_operador_no_configura_plan_auditor_no_actualiza_padron(self):
        self.membresia.rol = "operador"
        self.membresia.save()
        self.assertEqual(self.post("planes", {"codigo": "X", "nombre": "X"}).status_code, 403)
        self.membresia.rol = "auditor"
        self.membresia.save()
        self.assertEqual(self.post("padron", {}).status_code, 403)
        self.assertEqual(self.client.get(self.base+"padron/").status_code, 200)

    def test_convenio_no_puede_autoaceptarse(self):
        response = self.post("convenios", {"institucion": self.institucion.pk})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post("aceptar-convenio", {"convenio": response.data["id"]}).status_code, 400)
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/coberturas/aceptar-convenio/", {"convenio": response.data["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["estado"], "activo")

    def test_membresia_revocada_invalida_lecturas(self):
        self.membresia.activo = False
        self.membresia.save()
        self.assertEqual(self.client.get(self.base+"padron/").status_code, 404)

    def test_descarga_privada_auditada_sin_url_publica(self):
        response = self.client.get(self.base+"plantilla/?tipo=padron")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(m.EventoCobertura.objects.filter(accion="descargar_plantilla", usuario=self.operador).exists())
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.base+"plantilla/?tipo=padron").status_code, 401)

    def test_lote_de_otro_financiador_no_se_confirma_ni_descarga(self):
        lote = m.Importacion.objects.create(financiador=self.otra, tipo="padron", clave=uuid4(), huella="x"*64, creado_por=self.admin)
        self.assertEqual(self.post("confirmar-importacion", {"importacion": lote.pk}).status_code, 400)
        self.assertEqual(self.client.get(self.base+f"rechazos/?importacion={lote.pk}").status_code, 404)

    def test_activacion_nueva_cuenta_de_un_uso_no_resetea_cuenta_existente(self):
        from urllib.parse import urlparse, parse_qs
        response = self.post("usuarios", {"email": "nueva@test.local", "nombre": "Nueva", "rol": "operador"})
        self.assertEqual(response.status_code, 201)
        enlace = parse_qs(urlparse(response.data["activacion"]).query)
        payload = {"uid": enlace["uid"][0], "token": enlace["token"][0], "password": "UnaClaveRobusta!4861"}
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/financiadores/activar/", payload).status_code, 200)
        self.assertEqual(self.client.post("/api/financiadores/activar/", payload).status_code, 400)
        self.client.force_authenticate(self.operador)
        response = self.post("usuarios", {"email": self.usuario.email, "nombre": "Intento", "rol": "auditor"})
        self.assertNotIn("activacion", response.data)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("x"))

    def test_hospital_sin_permiso_explicito_no_activa_cobertura(self):
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="admin")
        self.client.force_authenticate(self.usuario)
        response = self.client.post("/api/coberturas/configurar/", {"institucion": self.institucion.pk, "activo": True, "dias_reserva_antigua": 7})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(m.ConfiguracionHospital.objects.exists())

    def test_reemitir_activacion_solo_desde_organizacion_que_creo_cuenta(self):
        payload = {"email": "por-activar@test.local", "nombre": "Pendiente", "rol": "operador"}
        self.assertIn("activacion", self.post("usuarios", payload).data)
        self.assertIn("activacion", self.post("usuarios", payload).data)
        m.MembresiaFinanciador.objects.create(financiador=self.otra, usuario=self.operador, rol="admin")
        respuesta = self.client.post(f"/api/financiadores/{self.otra.pk}/usuarios/", payload, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertNotIn("activacion", respuesta.data)
        payload["activo"] = False
        self.assertNotIn("activacion", self.post("usuarios", payload).data)

    def test_opciones_hospital_contrato_selectores_y_concesiones(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/coberturas/opciones/?institucion={self.institucion.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("registrar_aceptacion", response.data["permisos"])
        self.assertEqual(response.data["casos"][0]["id"], self.caso.pk)
        self.assertIn("comun", response.data["prestaciones"][0])

    def test_arancel_excepcional_valida_decimal_y_hospital(self):
        convenio = m.Convenio.objects.create(financiador=self.org, institucion=self.institucion, estado="activo", propuesto_por="plataforma", creado_por=self.admin)
        self.client.force_authenticate(self.admin)
        payload = {"convenio": convenio.pk, "prestacion": self.prestacion.pk, "importe": "80.50", "vigente_desde": str(timezone.localdate())}
        self.assertEqual(self.client.post("/api/coberturas/arancel/", payload).status_code, 201)
        payload["importe"] = "0"
        self.assertEqual(self.client.post("/api/coberturas/arancel/", payload).status_code, 400)

    def test_busqueda_padron_filtra_y_normaliza_documento(self):
        for numero, documento in [("001", "000123"), ("002", "000456")]:
            self.post("padron", {"numero": numero, "documento": documento, "nombre": numero, "plan": self.plan.pk, "desde": str(timezone.localdate())})
        response = self.client.get(self.base+"padron/?documento=000.123")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["numero"], "001")

    def test_importacion_http_y_descarga_rechazos(self):
        from openpyxl import load_workbook
        contenido = generar_plantilla(financiador=self.org, usuario=self.operador, tipo="padron")
        libro = load_workbook(BytesIO(contenido))
        libro["Carga"].append(["001", "000123", "Prueba", "A", timezone.localdate()])
        libro["Carga"].append(["002", "000456", "Prueba", "AJENO", timezone.localdate()])
        buffer = BytesIO()
        libro.save(buffer)
        archivo = SimpleUploadedFile("padron.xlsx", buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(self.base+"importaciones/", {"archivo": archivo, "tipo": "padron", "clave": str(uuid4())}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["resumen"]["valida"], 1)
        self.assertEqual(response.data["resumen"]["rechazada"], 1)
        lote_id = response.data["id"]
        response = self.post("confirmar-importacion", {"importacion": lote_id})
        self.assertEqual(response.data["resumen"]["aplicada"], 1)
        self.assertEqual(m.Afiliado.objects.count(), 1)
        response = self.client.get(self.base+f"rechazos/?importacion={lote_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(m.EventoCobertura.objects.filter(accion="descargar_rechazos").exists())

    def test_corregir_identidad_conserva_pk_y_rechaza_documento_ajeno(self):
        payload = {"numero": "0001", "documento": "001234", "nombre": "Persona", "plan": self.plan.pk, "desde": str(timezone.localdate())}
        primero = self.post("padron", payload).data
        payload.update(numero="0002", documento="005678")
        segundo = self.post("padron", payload).data
        cambio = {"afiliado": primero["id"], "numero": "1000", "documento": "009999", "motivo": "Documento verificado"}
        response = self.post("corregir-identidad", cambio)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], primero["id"])
        self.assertEqual(m.Afiliado.objects.count(), 2)
        self.assertEqual(m.HistorialAfiliacion.objects.filter(afiliado_id=primero["id"]).count(), 2)
        cambio["documento"] = segundo["documento"]
        self.assertEqual(self.post("corregir-identidad", cambio).status_code, 400)

    def test_no_se_retira_el_ultimo_administrador(self):
        response = self.post("usuarios", {"email": self.operador.email, "nombre": "Operador", "rol": "auditor", "activo": False})
        self.assertEqual(response.status_code, 400)
        self.membresia.refresh_from_db()
        self.assertTrue(self.membresia.activo)
        self.assertEqual(self.membresia.rol, "admin")
