"""Outbox real PostgreSQL; SMTP sintético, sin proveedor ni worker externo."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from smtplib import SMTPRecipientsRefused
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.auditoria import latidos

from . import correo_outbox, credenciales
from .models import CorreoInstitucionalOutbox, Usuario
from .test_credenciales_auditoria172 import CONFIGURACION

Estado = CorreoInstitucionalOutbox.Estado


@skipUnless(connection.vendor == "postgresql", "La reserva durable requiere PostgreSQL real")
@override_settings(**CONFIGURACION)
class OutboxInstitucionalTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("outbox-titular@example.test", "Clave-inicial-ficticia-172")
        self.cliente = APIClient()

    def solicitar(self):
        credenciales.solicitar_recuperacion_publica(self.usuario.email)
        return CorreoInstitucionalOutbox.objects.latest("pk")

    def test_aceptacion_persiste_sin_enviar_y_proceso_separado_entrega(self):
        trabajo = self.solicitar()
        self.assertEqual(trabajo.estado, Estado.PENDIENTE)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotIn("token", trabajo.solicitud)
        self.assertTrue(correo_outbox.procesar_siguiente())
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.ENVIADO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("#uid=", str(trabajo.solicitud))

    def test_alta_y_outbox_confirman_o_revierten_juntas(self):
        root = Usuario.objects.create_superuser("outbox-admin@example.test", "x")
        self.cliente.force_authenticate(root)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with transaction.atomic():
                respuesta = self.cliente.post("/api/usuarios/", {
                    "email": "invitacion-atomicidad@example.test", "nombre": "Invitado",
                }, format="json")
                self.assertEqual(respuesta.status_code, 201, respuesta.data)
                self.assertEqual(CorreoInstitucionalOutbox.objects.count(), 1)
                raise RuntimeError("rollback sintético")
        self.assertFalse(Usuario.objects.filter(email="invitacion-atomicidad@example.test").exists())
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_error_insert_outbox_no_deja_alta_y_no_expone_payload(self):
        root = Usuario.objects.create_superuser("outbox-error-admin@example.test", "x")
        self.cliente.force_authenticate(root)
        marcador = "dato-privado-no-registrar"
        with patch.object(CorreoInstitucionalOutbox.objects, "create", side_effect=DatabaseError(marcador)):
            with self.assertLogs("apps.accounts.credenciales", level="ERROR") as registros:
                respuesta = self.cliente.post("/api/usuarios/", {
                    "email": "no-crear@example.test", "nombre": "Invitado",
                }, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertNotIn(marcador, str(respuesta.data) + str(registros.output))
        self.assertFalse(Usuario.objects.filter(email="no-crear@example.test").exists())
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())

    def test_recuperacion_publica_encola_desconocido_sin_buscar_identidad(self):
        with patch("apps.accounts.credenciales.Usuario.objects.filter", side_effect=AssertionError("lookup público")):
            respuesta = self.cliente.post("/api/auth/recuperacion/", {"email": "desconocido@example.test"}, format="json")
        self.assertEqual(respuesta.status_code, 202, respuesta.data)
        trabajo = CorreoInstitucionalOutbox.objects.get()
        self.assertEqual(trabajo.estado, Estado.PENDIENTE)
        correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.DESCARTADO)
        self.assertEqual(len(mail.outbox), 0)

    def test_consumidor_revalida_inactivo_despues_de_aceptar(self):
        trabajo = self.solicitar()
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.DESCARTADO)
        self.assertEqual(trabajo.intentos, 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_payload_no_admite_tokens_ni_tipos_de_id_invalidos(self):
        for extra in ({"token": "no-persistir"}, {"actor_id": True}, {"actor_id": "1"}):
            with self.subTest(extra=extra), self.assertRaises(credenciales.CorreoInstitucionalNoDisponible):
                credenciales._programar({"tipo": "recuperacion", "email": self.usuario.email, **extra})
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())

    def test_tipo_corrupto_se_descarta_sin_reintentar_ni_enviar(self):
        ahora = timezone.now()
        trabajo = CorreoInstitucionalOutbox.objects.create(
            solicitud={"tipo": "desconocido"}, disponible_en=ahora, vence=ahora + timedelta(minutes=10),
        )
        correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.DESCARTADO)
        self.assertFalse(correo_outbox.procesar_siguiente())
        self.assertEqual(len(mail.outbox), 0)

    def test_reintentos_transitorios_tienen_backoff_y_tope(self):
        trabajo = self.solicitar()
        for intento in range(1, 4):
            CorreoInstitucionalOutbox.objects.filter(pk=trabajo.pk).update(disponible_en=timezone.now() - timedelta(seconds=1))
            with patch("django.core.mail.message.EmailMessage.send", return_value=0):
                self.assertTrue(correo_outbox.procesar_siguiente())
            trabajo.refresh_from_db()
            self.assertEqual(trabajo.intentos, intento)
            if intento < 3:
                self.assertEqual(trabajo.estado, Estado.PENDIENTE)
                self.assertGreater(trabajo.disponible_en, timezone.now())
                self.assertFalse(correo_outbox.procesar_siguiente())
        self.assertEqual(trabajo.estado, Estado.ERROR)
        self.assertIsNotNone(trabajo.terminado_en)
        self.assertFalse(correo_outbox.procesar_siguiente())

    def test_smtp_550_es_error_permanente_sanitizado(self):
        trabajo = self.solicitar()
        marcador = "dato-privado-proveedor"
        error = SMTPRecipientsRefused({self.usuario.email: (550, marcador.encode())})
        with patch("django.core.mail.message.EmailMessage.send", side_effect=error):
            with self.assertLogs("apps.accounts", level="ERROR") as registros:
                correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.ERROR)
        self.assertEqual(trabajo.resultado, "rechazo_permanente")
        self.assertEqual(trabajo.intentos, 1)
        self.assertFalse(correo_outbox.procesar_siguiente())
        self.assertNotIn(marcador, str(registros.output))
        self.assertNotIn(self.usuario.email, str(registros.output))

    def test_caida_tras_reserva_se_recupera_y_uuid_viejo_no_envia(self):
        trabajo = self.solicitar()
        primera = correo_outbox.tomar_trabajo()
        CorreoInstitucionalOutbox.objects.filter(pk=trabajo.pk).update(reservado_hasta=timezone.now() - timedelta(seconds=1))
        segunda = correo_outbox.tomar_trabajo()
        self.assertNotEqual(primera[1], segunda[1])
        self.assertFalse(correo_outbox.procesar_reserva(*primera))
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(correo_outbox.procesar_reserva(*segunda))
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.ENVIADO)
        self.assertEqual(trabajo.intentos, 2)

    def test_caida_tras_smtp_antes_de_confirmar_puede_duplicar(self):
        trabajo = self.solicitar()
        primera = correo_outbox.tomar_trabajo()
        with patch("django.db.models.query.QuerySet.update", side_effect=DatabaseError("caída sintética")):
            with self.assertRaises(DatabaseError):
                correo_outbox.procesar_reserva(*primera)
        self.assertEqual(len(mail.outbox), 1)
        CorreoInstitucionalOutbox.objects.filter(pk=trabajo.pk).update(reservado_hasta=timezone.now() - timedelta(seconds=1))
        self.assertTrue(correo_outbox.procesar_siguiente())
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.ENVIADO)
        self.assertEqual(len(mail.outbox), 2, "SMTP al menos una vez no equivale a exactamente una vez")

    def test_trabajo_vencido_no_envia(self):
        trabajo = self.solicitar()
        CorreoInstitucionalOutbox.objects.filter(pk=trabajo.pk).update(vence=timezone.now() - timedelta(seconds=1))
        correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.DESCARTADO)
        self.assertEqual(trabajo.resultado, "vencido")
        self.assertEqual(trabajo.intentos, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_configuracion_incompleta_no_reserva_ni_envia(self):
        trabajo = self.solicitar()
        with override_settings(INSTITUCIONAL_URL_BASE=""):
            with self.assertRaises(credenciales.CorreoInstitucionalNoDisponible):
                correo_outbox.procesar_siguiente()
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.PENDIENTE)
        self.assertEqual(trabajo.intentos, 0)

    def test_purga_manual_solo_limpia_payload_terminal(self):
        enviado = self.solicitar()
        correo_outbox.procesar_siguiente()
        pendiente = self.solicitar()
        cantidad = correo_outbox.purgar_payloads(timezone.now() + timedelta(seconds=1), limite=10)
        self.assertEqual(cantidad, 1)
        enviado.refresh_from_db(); pendiente.refresh_from_db()
        self.assertEqual(enviado.solicitud, {})
        self.assertEqual(enviado.estado, Estado.ENVIADO)
        self.assertIn("email", pendiente.solicitud)

    def test_estado_comando_no_expone_payload_y_pasada_con_error_no_sale_cero(self):
        trabajo = self.solicitar()
        salida = StringIO()
        call_command("procesar_correo_institucional", estado=True, stdout=salida)
        self.assertNotIn(self.usuario.email, salida.getvalue())
        with patch("apps.accounts.management.commands.procesar_correo_institucional.close_old_connections"):
            with patch("django.core.mail.message.EmailMessage.send", side_effect=SMTPRecipientsRefused({self.usuario.email: (550, b"privado")})):
                with self.assertRaises(CommandError):
                    call_command("procesar_correo_institucional", una_pasada=True, stdout=StringIO())
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.estado, Estado.ERROR)

    def test_latido_condicional_detecta_nunca_y_vencido_no_acredita_entrega(self):
        with override_settings(INSTITUCIONAL_CORREO_MODO=""):
            self.assertNotIn("correo_institucional", latidos.estado()["servicios"])
        self.assertIn("correo_institucional", latidos.estado()["atrasados"])
        latidos.latir("correo_institucional")
        self.assertEqual(latidos.estado()["servicios"]["correo_institucional"]["estado"], "al día")
        latidos.Latido.objects.filter(servicio="correo_institucional").update(momento=timezone.now() - timedelta(seconds=64))
        self.assertIn("correo_institucional", latidos.estado()["atrasados"])


@skipUnless(connection.vendor == "postgresql", "skip_locked debe probarse con conexiones PostgreSQL")
@override_settings(**CONFIGURACION)
class ReservaMultiworkerCorreoTests(TransactionTestCase):
    def test_dos_workers_no_reservan_mismo_trabajo_activo(self):
        credenciales.solicitar_recuperacion_publica("desconocido@example.test")
        barrera = Barrier(2, timeout=10)

        def reservar():
            connections.close_all()
            try:
                barrera.wait()
                return correo_outbox.tomar_trabajo()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = [futuro.result(timeout=15) for futuro in [pool.submit(reservar), pool.submit(reservar)]]
        self.assertEqual(sum(reserva is not None for reserva in resultados), 1)
        self.assertEqual(CorreoInstitucionalOutbox.objects.get().intentos, 1)
