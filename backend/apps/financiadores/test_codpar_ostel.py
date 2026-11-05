"""CODPAR literal en el bloque protegido; sólo datos creados para estas pruebas."""
from hashlib import sha256
import json

from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from . import models as m, padron


class CodparOstelTests(APITestCase):
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="OSTEL ficticia", tipo="obra_social")
        self.user = Usuario.objects.create_user("codpar@example.invalid")
        self.member = m.MembresiaFinanciador.objects.create(
            financiador=self.org, usuario=self.user, rol="operador",
            acceso_padron_salud=True, acceso_padron_cobranza=True,
        )
        self.afiliado = m.Afiliado.objects.create(
            financiador=self.org, numero="FICTICIO-01", documento="FICTICIO-01",
            nombre="Persona ficticia", desde=timezone.localdate(), cobertura_habilitada=False,
        )
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.url = self.base + f"padron/{self.afiliado.pk}/"
        self.client.force_authenticate(self.user)

    def patch(self, valor, revision=1, url=None):
        return self.client.patch(url or self.url + "salud/", {
            "codpar_ostel": valor, "revision": revision, "motivo": "Fuente ficticia",
        }, format="json")

    def test_codigo_literal_separado_con_historial_y_sin_efectos_generales(self):
        general = self.client.get(self.url).data
        response = self.patch(" 000-XD1 ")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["codpar_ostel"], " 000-XD1 ")
        self.assertEqual(response.data["revision"], 2)
        self.assertEqual(self.client.get(self.url + "salud/").data["codpar_ostel"], " 000-XD1 ")
        historia = self.client.get(self.url + "salud/historial/").data["results"]
        self.assertEqual(historia[0]["cambios"], {
            "codpar_ostel": {"anterior": "", "nuevo": " 000-XD1 "},
        })
        self.assertEqual(self.client.get(self.url).data, general)
        for ruta in (self.url, self.base + "padron/", self.url + "familia/", self.url + "historial/"):
            self.assertNotIn("codpar_ostel", str(self.client.get(ruta).data))
        self.assertEqual(self.patch(" 000-XD1 ", revision=2).data["revision"], 2)
        self.assertEqual(self.client.get(self.url + "salud/historial/").data["count"], 1)

    def test_rechazos_conservan_valor_revision_e_historial(self):
        self.assertEqual(self.patch("XD1").status_code, 200)
        antes = self.client.get(self.url + "salud/").data
        historia = self.client.get(self.url + "salud/historial/").data
        self.assertEqual(self.patch("OT1").status_code, 409)
        for valor in (None, 1, True, "X" * 41):
            with self.subTest(tipo=type(valor).__name__):
                self.assertEqual(self.patch(valor, revision=2).status_code, 400)
        self.assertEqual(self.patch("OT1", url=self.url).status_code, 400)
        self.assertEqual(self.patch("OT1", url=self.url + "cobranza/").status_code, 400)
        self.assertEqual(self.client.get(self.url + "salud/").data, antes)
        self.assertEqual(self.client.get(self.url + "salud/historial/").data, historia)
        # El PATCH parcial de un campo previo conserva el código y su contrato.
        respuesta = self.client.patch(self.url + "salud/", {
            "revision": 2, "motivo": "Regresión de campo previo", "cronicas": "Dato ficticio",
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["codpar_ostel"], "XD1")
        self.assertEqual(respuesta.data["cronicas"], "Dato ficticio")
        self.assertEqual(self.patch("", revision=3).data["codpar_ostel"], "")
        cambio = self.client.get(self.url + "salud/historial/").data["results"][0]
        self.assertEqual(cambio["cambios"]["codpar_ostel"], {"anterior": "XD1", "nuevo": ""})

    def test_designacion_rol_y_financiador_siguen_siendo_obligatorios(self):
        self.assertEqual(self.patch("IN1").status_code, 200)
        antes = self.client.get(self.url + "salud/").data
        historia = self.client.get(self.url + "salud/historial/").data
        self.member.acceso_padron_salud = False
        self.member.save()
        self.assertEqual(self.patch("OT1", revision=2).status_code, 403)
        for ruta in ("salud/", "salud/historial/"):
            self.assertEqual(self.client.get(self.url + ruta).status_code, 403)
        self.member.acceso_padron_salud = True
        self.member.rol = "auditor"
        self.member.save()
        self.assertEqual(self.patch("OT1", revision=2).status_code, 403)
        self.assertEqual(self.client.get(self.url + "salud/").data, antes)
        self.assertEqual(self.client.get(self.url + "salud/historial/").data, historia)
        otra = m.Financiador.objects.create(nombre="Otra ficticia", tipo="obra_social")
        ajeno = m.Afiliado.objects.create(
            financiador=otra, numero="FICTICIO-02", documento="FICTICIO-02",
            nombre="Persona ficticia ajena", desde=timezone.localdate(),
        )
        self.assertEqual(self.client.get(self.base + f"padron/{ajeno.pk}/salud/").status_code, 404)

    def test_servicio_rechaza_tipos_sin_modificar_datos(self):
        self.assertEqual(self.patch("XD1").status_code, 200)

        def huella():
            tablas = (m.SaludPadron, m.Afiliado, m.HistorialPadronProtegido)
            datos = [list(tabla.objects.order_by("pk").values()) for tabla in tablas]
            return sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()

        antes = huella()
        for valor in (None, 1, True, [], {}, "X" * 41):
            with self.assertRaises(ValidationError):
                padron.editar_protegido(afiliado=self.afiliado, usuario=self.user, bloque="salud",
                    entrada={"revision": 2, "motivo": "Fuente ficticia", "codpar_ostel": valor})
            self.assertEqual(huella(), antes)
        self.member.acceso_padron_salud = False
        self.member.save()
        self.assertEqual(self.patch("OT1", revision=2).status_code, 403)
        self.assertEqual(huella(), antes)


class CodparOstelMigracionTests(TransactionTestCase):
    def test_migracion_conserva_todos_los_campos_previos(self):
        anterior = ("financiadores", "0016_afiliado_geografia_afiliado_geografia_laboral")
        nueva = ("financiadores", "0017_saludpadron_codpar_ostel")
        executor = MigrationExecutor(connection)
        restaurar = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([anterior])
            apps = executor.loader.project_state([anterior]).apps
            org = apps.get_model("financiadores", "Financiador").objects.create(
                nombre="Migración ficticia", tipo="obra_social")
            afiliado = apps.get_model("financiadores", "Afiliado").objects.create(
                financiador=org, numero="FICTICIO-M", documento="FICTICIO-M",
                nombre="Persona ficticia", desde=timezone.localdate())
            salud = apps.get_model("financiadores", "SaludPadron")
            registro = salud.objects.create(afiliado=afiliado, revision=7, cronicas="Texto ficticio")
            antes = salud.objects.filter(pk=registro.pk).values().get()
            executor = MigrationExecutor(connection)
            executor.migrate([nueva])
            apps = executor.loader.project_state([nueva]).apps
            despues = apps.get_model("financiadores", "SaludPadron").objects.filter(
                pk=registro.pk).values().get()
            self.assertEqual(despues.pop("codpar_ostel"), "")
            self.assertEqual(despues, antes)
        finally:
            MigrationExecutor(connection).migrate(restaurar)
