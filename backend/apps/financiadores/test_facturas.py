"""Contrato HTTP, aislamiento y almacenamiento privado de facturas v0."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion
from . import models as m
from .management.commands.seed_financiadores import sembrar_facturas_demo


class FacturasTests(APITestCase):
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="Mutual ficticia", tipo="mutual")
        self.otra = m.Financiador.objects.create(nombre="Otra mutual", tipo="mutual")
        self.user = Usuario.objects.create_user("facturas@test.local", "clave")
        self.membresia = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="operador")
        self.institucion = Institucion.objects.create(nombre="Hospital ficticio")
        self.convenio = m.Convenio.objects.create(financiador=self.org, institucion=self.institucion, propuesto_por="financiador", creado_por=self.user)
        self.convenio_ajeno = m.Convenio.objects.create(financiador=self.otra, institucion=self.institucion, propuesto_por="financiador", creado_por=self.user)
        self.afiliado = m.Afiliado.objects.create(financiador=self.org, numero="DEMO-1", documento="FIC-1", nombre="Persona ficticia", desde=timezone.localdate())
        self.afiliado_ajeno = m.Afiliado.objects.create(financiador=self.otra, numero="DEMO-2", documento="FIC-2", nombre="Otra persona", desde=timezone.localdate())
        self.base = f"/api/financiadores/{self.org.pk}/facturas/"
        self.otra_base = f"/api/financiadores/{self.otra.pk}/facturas/"
        self.payload = {"direccion": "recibida", "contraparte_tipo": "institucion", "convenio": self.convenio.pk,
                        "tipo": "factura", "letra": "A", "numero": "DEMO-001", "fecha": str(timezone.localdate()), "importe": "125.50"}
        self.client.force_authenticate(self.user)

    def alta(self, **cambios):
        return self.client.post(self.base, {**self.payload, **cambios}, format="json")

    def test_alta_listado_filtro_detalle_y_edicion_auditada(self):
        alta = self.alta()
        self.assertEqual(alta.status_code, 201, alta.data)
        self.assertEqual(alta["Cache-Control"], "private, no-store")
        pk = alta.data["id"]
        self.assertEqual(self.client.get(self.base + "?direccion=recibida").data["count"], 1)
        self.assertEqual(self.client.get(self.base + "?direccion=emitida").data["count"], 0)
        self.assertEqual(self.client.get(self.base + f"{pk}/").data["numero"], "DEMO-001")
        cambio = self.client.patch(self.base + f"{pk}/", {"concepto": "Reintegro"}, format="json")
        self.assertEqual(cambio.status_code, 200, cambio.data)
        self.assertTrue(m.EventoCobertura.objects.filter(accion="crear_factura", objeto=str(pk)).exists())
        self.assertIn("concepto", m.EventoCobertura.objects.get(accion="editar_factura", objeto=str(pk)).motivo)

    def test_otro_financiador_y_vinculos_ajenos(self):
        pk = self.alta().data["id"]
        for metodo, ruta, data in [(self.client.get, f"{pk}/", None), (self.client.patch, f"{pk}/", {"concepto": "x"}), (self.client.get, f"{pk}/adjunto/", None)]:
            respuesta = metodo(self.otra_base + ruta, data, format="json") if data else metodo(self.otra_base + ruta)
            self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self.alta(convenio=self.convenio_ajeno.pk, numero="DEMO-002").status_code, 400)
        self.assertEqual(self.alta(contraparte_tipo="afiliado", convenio=None, afiliado=self.afiliado_ajeno.pk, numero="DEMO-003").status_code, 400)

    def test_roles_y_membresia(self):
        self.alta()
        self.membresia.rol = "auditor"; self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.client.get(self.base).status_code, 200)
        self.assertEqual(self.alta(numero="DEMO-002").status_code, 403)
        self.assertEqual(self.client.patch(self.base + "1/", {"concepto": "x"}, format="json").status_code, 403)
        self.assertEqual(self.client.post(self.base + "1/adjunto/", {}).status_code, 403)
        self.client.force_authenticate(Usuario.objects.create_user("sin@test.local", "clave"))
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.client.force_authenticate(self.user)
        self.membresia.activo = False; self.membresia.save(update_fields=["activo"])
        self.assertEqual(self.client.get(self.base).status_code, 404)

    def test_duplicados_y_validaciones(self):
        self.assertEqual(self.alta().status_code, 201)
        duplicado = self.alta()
        self.assertEqual(duplicado.status_code, 400)
        self.assertIn("misma dirección", str(duplicado.data))
        sin_vinculo = {"convenio": None, "contraparte_nombre": "  Clínica Álamo  ", "contraparte_identificador": "FIC-3", "numero": "DEMO-002"}
        self.assertEqual(self.alta(**sin_vinculo).status_code, 201)
        self.assertEqual(self.alta(**{**sin_vinculo, "contraparte_nombre": "clinica  alamo"}).status_code, 400)
        self.assertEqual(self.alta(numero="DEMO-003", fecha=str(timezone.localdate() + timedelta(days=1))).status_code, 400)
        self.assertEqual(self.alta(numero="DEMO-004", importe="0").status_code, 400)
        otra = self.alta(numero="DEMO-005").data["id"]
        self.assertEqual(self.client.patch(self.base + f"{otra}/", {"numero": "DEMO-001"}, format="json").status_code, 400)
        self.convenio.estado = "finalizado"; self.convenio.save(update_fields=["estado"])
        self.assertEqual(self.alta(numero="DEMO-006").status_code, 201)
        self.assertEqual(self.alta(contraparte_tipo="afiliado", numero="DEMO-007").status_code, 400)

    def test_interruptor_apagado_rechaza_archivo(self):
        alta_con_archivo = self.client.post(self.base, {**self.payload, "archivo": self.pdf()}, format="multipart")
        self.assertEqual(alta_con_archivo.status_code, 400)
        self.assertIn("no están disponibles", str(alta_con_archivo.data))
        pk = self.alta().data["id"]
        respuesta = self.client.post(self.base + f"{pk}/adjunto/", {"archivo": self.pdf()}, format="multipart")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no están disponibles", str(respuesta.data))
        self.assertEqual(self.client.get(self.base + f"{pk}/adjunto/").status_code, 400)
        self.assertEqual(m.RegistroFactura.objects.get(pk=pk).adjunto_ruta, "")

    @staticmethod
    def pdf(contenido=b"%PDF-1.4\nprueba", nombre="factura.pdf", tipo="application/pdf"):
        return SimpleUploadedFile(nombre, contenido, content_type=tipo)

    def test_adjunto_privado_validacion_descarga_y_duplicado(self):
        pk = self.alta().data["id"]
        with TemporaryDirectory() as temporal:
            media = Path(temporal) / "media"
            privado = Path(temporal) / "privado"
            with override_settings(SALUD_FACTURAS_ADJUNTOS=True, SALUD_FACTURAS_ADJUNTOS_DIR=privado, MEDIA_ROOT=media):
                ruta = self.base + f"{pk}/adjunto/"
                for archivo in [self.pdf(b"texto", "f.txt", "text/plain"), self.pdf(b"falso", "f.pdf"), self.pdf(b"%PDF-" + b"x" * (10 * 1024 * 1024), "grande.pdf")]:
                    self.assertEqual(self.client.post(ruta, {"archivo": archivo}, format="multipart").status_code, 400)
                subido = self.client.post(ruta, {"archivo": self.pdf()}, format="multipart")
                self.assertEqual(subido.status_code, 201, subido.data)
                obj = m.RegistroFactura.objects.get(pk=pk)
                self.assertTrue((privado / obj.adjunto_ruta).is_file())
                self.assertFalse((media / obj.adjunto_ruta).exists())
                self.assertEqual(self.client.post(ruta, {"archivo": self.pdf()}, format="multipart").status_code, 400)
                self.assertEqual(self.client.get(self.otra_base + f"{pk}/adjunto/").status_code, 404)
                descarga = self.client.get(ruta)
                self.assertEqual(descarga.status_code, 200)
                self.assertEqual(descarga["Cache-Control"], "private, no-store")
                self.assertTrue(m.EventoCobertura.objects.filter(accion="descargar_factura", objeto=str(pk)).exists())
                # Consumir el stream cierra el archivo; close() emitiría
                # request_finished y en Postgres cerraría la conexión del test.
                self.assertEqual(b"".join(descarga.streaming_content), b"%PDF-1.4\nprueba")
                self.membresia.rol = "auditor"
                self.membresia.save(update_fields=["rol"])
                descarga_auditor = self.client.get(ruta)
                self.assertEqual(descarga_auditor.status_code, 200)
                b"".join(descarga_auditor.streaming_content)
                with override_settings(SALUD_FACTURAS_ADJUNTOS_DIR=media / "facturas"):
                    self.assertEqual(self.client.get(ruta).status_code, 400)

    def test_seed_ocho_por_financiador_idempotente(self):
        for org, convenio, afiliado in [(self.org, self.convenio, self.afiliado), (self.otra, self.convenio_ajeno, self.afiliado_ajeno)]:
            for _ in range(2):
                sembrar_facturas_demo(org, convenio, afiliado, self.user, timezone.localdate())
            registros = m.RegistroFactura.objects.filter(financiador=org)
            self.assertEqual(registros.count(), 8)
            self.assertTrue(all(x.numero.startswith("DEMO-") and not x.adjunto_ruta and not x.contraparte_identificador for x in registros))
