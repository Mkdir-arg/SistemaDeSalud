"""IP confiable y alerta durable del registro de accesos (#172, AUD-044).

El cliente no elige la IP auditada: vale la que agrega el proxy propio
(NUM_PROXIES). Una IP inválida no pierde el evento. Si el registro falla, la
atención sigue, el fallo queda en FalloAuditoria y `/api/estado/` responde 503
hasta que alguien lo revise. Datos sintéticos.
"""
from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano, HistoriaClinica

from .mixins import ip_cliente
from .models import AccesoClinico, FalloAuditoria


class IpClienteAuditoria172Tests(TestCase):
    def pedido(self, xff=None, remoto="10.0.0.5"):
        extra = {"REMOTE_ADDR": remoto}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return APIRequestFactory().get("/", **extra)

    def test_vale_el_valor_del_proxy_propio_y_no_el_del_cliente(self):
        self.assertEqual(ip_cliente(self.pedido("6.6.6.6, 192.0.2.10")), "192.0.2.10")
        self.assertEqual(ip_cliente(self.pedido("192.0.2.10")), "192.0.2.10")

    def test_un_valor_invalido_queda_como_ip_no_confiable(self):
        for xff in ("6.6.6.6, no-es-una-ip", "6.6.6.6, ", "999.1.1.1"):
            with self.subTest(xff=xff):
                self.assertIsNone(ip_cliente(self.pedido(xff)))

    def test_sin_proxy_de_confianza_se_usa_la_conexion(self):
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}):
            self.assertEqual(ip_cliente(self.pedido("6.6.6.6", remoto="192.0.2.20")), "192.0.2.20")


class RegistroAccesosAuditoria172Tests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital sintético de ingreso")
        self.medica = Usuario.objects.create_user("medica-ingreso@example.test", "x", nombre="Médica")
        Membresia.objects.create(usuario=self.medica, institucion=self.inst, rol=Membresia.Rol.MEDICO)
        self.paciente = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente sintético")
        self.api = APIClient()
        self.api.force_authenticate(self.medica)
        self.root = Usuario.objects.create_superuser("root-ingreso@example.test", "x", nombre="Root")

    def leer(self, **extra):
        return self.api.get(f"/api/ciudadanos/{self.paciente.pk}/", **extra)

    def test_cabecera_falsa_no_suplanta_la_ip_ni_una_invalida_pierde_el_evento(self):
        self.assertEqual(self.leer(HTTP_X_FORWARDED_FOR="6.6.6.6, 192.0.2.10").status_code, 200)
        self.assertEqual(AccesoClinico.objects.latest("pk").ip, "192.0.2.10")
        self.assertEqual(self.leer(HTTP_X_FORWARDED_FOR="6.6.6.6, basura").status_code, 200)
        acceso = AccesoClinico.objects.latest("pk")
        self.assertIsNone(acceso.ip)
        self.assertEqual(acceso.ciudadano_id, self.paciente.pk)
        self.assertFalse(FalloAuditoria.objects.exists())

    def test_fallo_del_registro_no_corta_la_atencion_y_queda_visible_hasta_revisarlo(self):
        historia = HistoriaClinica.objects.create(ciudadano=self.paciente)
        with patch.object(AccesoClinico.objects, "create", side_effect=DatabaseError("sintético")):
            # La atención clínica sigue; la ficha administrativa es estricta y no
            # revela datos sin registro. Ambas dejan el fallo a la vista.
            self.assertEqual(self.api.get(f"/api/historias-clinicas/{historia.pk}/").status_code, 200)
            self.assertEqual(self.leer().status_code, 503)
        fallos = list(FalloAuditoria.objects.order_by("pk"))
        self.assertEqual([(f.recurso, f.error, f.institucion_id) for f in fallos],
                         [("historiaclinica", "DatabaseError", self.inst.pk), ("ciudadano", "DatabaseError", self.inst.pk)])
        fallo = fallos[0]
        self.assertIsNone(fallo.revisado_at)

        estado = APIClient()
        estado.force_authenticate(self.root)
        respuesta = estado.get("/api/estado/")
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("registro_accesos", respuesta.data["atrasados"])

        self.client.force_login(self.root)
        self.assertEqual(self.client.post("/admin/auditoria/falloauditoria/", {
            "action": "marcar_revisado", "_selected_action": [str(f.pk) for f in fallos],
        }).status_code, 302)
        fallo.refresh_from_db()
        self.assertEqual(fallo.revisado_por_id, self.root.pk)
        self.assertNotIn("registro_accesos", estado.get("/api/estado/").data["atrasados"])

    def test_el_fallo_no_se_borra_ni_se_crea_desde_el_admin(self):
        fallo = FalloAuditoria.objects.create(tipo="detalle", recurso="ciudadano", error="DatabaseError")
        self.client.force_login(self.root)
        self.assertEqual(self.client.get(f"/admin/auditoria/falloauditoria/{fallo.pk}/delete/").status_code, 403)
        self.assertEqual(self.client.get("/admin/auditoria/falloauditoria/add/").status_code, 403)
        self.assertTrue(FalloAuditoria.objects.filter(pk=fallo.pk).exists())
