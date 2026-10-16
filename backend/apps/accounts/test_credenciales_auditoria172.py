"""Identidad institucional: el enlace pertenece al titular, nunca al operador."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
import time

from django.core import mail
from django.core.cache import caches
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import CorreoInstitucionalOutbox, Membresia, Usuario


def consumir_correo_sintetico():
    """El test ejecuta el consumidor explícitamente; no corre en el request."""
    from apps.accounts.correo_outbox import procesar_siguiente

    while procesar_siguiente():
        pass


CONFIGURACION = {
    "INSTITUCIONAL_URL_BASE": "https://institucional.example.test",
    "INSTITUCIONAL_INVITACION_TIMEOUT": 86400,
    "INSTITUCIONAL_RECUPERACION_TIMEOUT": 1800,
    "INSTITUCIONAL_EMAIL_TIMEOUT": 1800,
    "INSTITUCIONAL_THROTTLE_RATES": {"ip": "1000/min", "email": "1000/min", "usuario": "1000/min"},
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "EMAIL_TIMEOUT": 3,
    "DEFAULT_FROM_EMAIL": "sistema@example.test",
    "INSTITUCIONAL_CORREO_MODO": "outbox",
    "INSTITUCIONAL_OUTBOX_POLITICA": {
        "max_intentos": 3, "lease_segundos": 60, "backoff_inicial_segundos": 1,
        "backoff_maximo_segundos": 30, "espera_segundos": 1,
    },
}
CLAVE = "Clave-ficticia-inicial-172!"
NUEVA_CLAVE = "Otra-clave-ficticia-172!"


@override_settings(**CONFIGURACION)
class CredencialesInstitucionalesTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("titular@example.test", CLAVE)
        self.client = APIClient()
        caches["portal"].clear()

    def post(self, accion, datos):
        respuesta = self.client.post(f"/api/auth/{accion}/", datos, format="json")
        if respuesta.status_code < 500:
            consumir_correo_sintetico()
        return respuesta

    def enlace(self, destinatario):
        mensaje = next(m for m in reversed(mail.outbox) if m.to == [destinatario] and "#uid=" in m.body)
        url = next(p for p in mensaje.body.split() if p.startswith("https://") and "#uid=" in p)
        self.assertTrue(url.startswith(CONFIGURACION["INSTITUCIONAL_URL_BASE"]))
        return {k: v[0] for k, v in parse_qs(urlsplit(url).fragment).items()}

    def test_recuperacion_es_generica_y_enlace_solo_va_al_titular(self):
        respuestas = []
        for email in (self.usuario.email, "inexistente@example.test"):
            respuesta = self.post("recuperacion", {"email": email})
            self.assertEqual(respuesta.status_code, 202)
            respuestas.append(respuesta.data)
            self.assertNotIn("token", str(respuesta.data))
        self.assertEqual(*respuestas)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.usuario.email])
        self.assertNotIn("inexistente", mail.outbox[0].body)

    def test_inactivo_y_referencia_no_reciben_recuperacion(self):
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        ref = Usuario.objects.create_user("medico@referencia.plexo.invalid", CLAVE)
        for email in (self.usuario.email, ref.email):
            respuesta = self.post("recuperacion", {"email": email})
            self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_configuracion_correo_falla_igual_antes_de_buscar_usuario(self):
        with override_settings(INSTITUCIONAL_URL_BASE=""):
            for email in (self.usuario.email, "inexistente@example.test"):
                with self.subTest(email=email):
                    respuesta = self.post("recuperacion", {"email": email})
                    self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(len(mail.outbox), 0)

    def test_base_institucional_con_path_no_genera_enlaces_que_spa_no_atiende(self):
        with override_settings(INSTITUCIONAL_URL_BASE="https://institucional.example.test/auth"):
            self.assertEqual(self.post("recuperacion", {"email": self.usuario.email}).status_code, 503)
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_tasas_explicitas_no_habilita_ruta(self):
        with override_settings(INSTITUCIONAL_THROTTLE_RATES={}):
            respuesta = self.post("recuperacion", {"email": self.usuario.email})
        self.assertEqual(respuesta.status_code, 503)

    def test_sin_modo_durable_no_habilita_ruta(self):
        with override_settings(INSTITUCIONAL_CORREO_MODO=""):
            respuesta = self.client.post("/api/auth/recuperacion/", {"email": self.usuario.email}, format="json")
        self.assertEqual(respuesta.status_code, 503)

    def test_request_publica_solo_encola_sin_buscar_identidad(self):
        with patch("apps.accounts.credenciales.Usuario.objects.filter", side_effect=AssertionError("consulta en request")):
            respuesta = self.client.post("/api/auth/recuperacion/", {"email": self.usuario.email}, format="json")
        self.assertEqual(respuesta.status_code, 202)
        self.assertEqual(CorreoInstitucionalOutbox.objects.get().solicitud,
                         {"tipo": "recuperacion", "email": self.usuario.email})
        self.assertEqual(len(mail.outbox), 0)

    def test_limites_se_aplican_a_direcciones_inexistentes(self):
        with override_settings(INSTITUCIONAL_THROTTLE_RATES={"ip": "1000/min", "email": "1/hour", "usuario": "1000/min"}):
            self.assertEqual(self.post("recuperacion", {"email": "ausente@example.test"}).status_code, 202)
            self.assertEqual(self.post("recuperacion", {"email": "ausente@example.test"}).status_code, 429)

    def test_reset_valida_password_y_el_enlace_no_admite_replay(self):
        self.assertEqual(self.post("recuperacion", {"email": self.usuario.email}).status_code, 202)
        datos = self.enlace(self.usuario.email)
        self.assertEqual(self.post("restablecer", {**datos, "nueva_password": "123"}).status_code, 400)
        respuesta = self.post("restablecer", {**datos, "nueva_password": NUEVA_CLAVE})
        self.assertEqual(respuesta.status_code, 204)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA_CLAVE))
        self.assertEqual(self.post("restablecer", {**datos, "nueva_password": CLAVE}).status_code, 400)

    def test_reset_no_activa_usuario_bloqueado_despues_del_envio(self):
        self.post("recuperacion", {"email": self.usuario.email})
        datos = self.enlace(self.usuario.email)
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.assertEqual(self.post("restablecer", {**datos, "nueva_password": NUEVA_CLAVE}).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE))

    def test_reset_rechaza_usuario_o_proposito_sustituidos_y_vencimiento(self):
        from apps.accounts.credenciales import _GeneradorInstitucional
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.post("recuperacion", {"email": self.usuario.email})
        datos = self.enlace(self.usuario.email)
        otro = Usuario.objects.create_user("otro@example.test", CLAVE)
        uid_otro = urlsafe_base64_encode(force_bytes(otro.pk))
        self.assertEqual(self.post("restablecer", {**datos, "uid": uid_otro, "nueva_password": NUEVA_CLAVE}).status_code, 400)
        token_otro = datos["token"].replace("recuperacion.", "invitacion.", 1)
        self.assertEqual(self.post("restablecer", {**datos, "token": token_otro, "nueva_password": NUEVA_CLAVE}).status_code, 400)
        futuro = _GeneradorInstitucional("recuperacion")._now() + timedelta(seconds=1801)
        with patch.object(_GeneradorInstitucional, "_now", return_value=futuro):
            self.assertEqual(self.post("restablecer", {**datos, "nueva_password": NUEVA_CLAVE}).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE))

    def test_cambio_propio_exige_password_actual(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.post("cambiar-password", {"password_actual": "incorrecta", "nueva_password": NUEVA_CLAVE})
        self.assertEqual(respuesta.status_code, 400)
        respuesta = self.post("cambiar-password", {"password_actual": CLAVE, "nueva_password": NUEVA_CLAVE})
        self.assertEqual(respuesta.status_code, 204)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA_CLAVE))

    def test_cambio_email_no_aplica_hasta_confirmar_y_destino_no_se_sustituye(self):
        self.client.force_authenticate(self.usuario)
        nuevo = "nuevo@example.test"
        self.assertEqual(self.post("cambio-email", {"password_actual": CLAVE, "nuevo_email": nuevo}).status_code, 202)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "titular@example.test")
        datos = self.enlace(nuevo)
        self.client.force_authenticate(None)
        self.assertEqual(self.post("confirmar-email", {**datos, "nuevo_email": "otro@example.test"}).status_code, 400)
        self.assertEqual(self.post("confirmar-email", datos).status_code, 204)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, nuevo)
        self.assertEqual(self.post("confirmar-email", datos).status_code, 400)

    def test_email_duplicado_no_cambia_identidad_ni_revela_propietario(self):
        otro = Usuario.objects.create_user("ocupado@example.test", CLAVE)
        self.client.force_authenticate(self.usuario)
        respuesta = self.post("cambio-email", {"password_actual": CLAVE, "nuevo_email": otro.email})
        self.assertEqual(respuesta.status_code, 202)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "titular@example.test")
        self.assertNotIn(str(otro.pk), str(respuesta.data))

    def test_email_vencido_o_emitido_antes_de_cambiar_password_no_sirve(self):
        self.client.force_authenticate(self.usuario)
        self.post("cambio-email", {"password_actual": CLAVE, "nuevo_email": "futuro@example.test"})
        datos = self.enlace("futuro@example.test")
        with patch("django.core.signing.time.time", return_value=time.time() + 1801):
            self.assertEqual(self.post("confirmar-email", datos).status_code, 400)
        self.assertEqual(self.post("cambiar-password", {"password_actual": CLAVE, "nueva_password": NUEVA_CLAVE}).status_code, 204)
        self.assertEqual(self.post("confirmar-email", datos).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "titular@example.test")

    def test_email_no_revive_al_volver_a_direccion_anterior(self):
        self.client.force_authenticate(self.usuario)
        original = self.usuario.email
        self.post("recuperacion", {"email": original})
        reset_anterior = self.enlace(original)
        self.post("cambio-email", {"password_actual": CLAVE, "nuevo_email": "intermedio@example.test"})
        primer_enlace = self.enlace("intermedio@example.test")
        self.assertEqual(self.post("confirmar-email", primer_enlace).status_code, 204)
        self.post("cambio-email", {"password_actual": CLAVE, "nuevo_email": original})
        self.assertEqual(self.post("confirmar-email", self.enlace(original)).status_code, 204)
        self.assertEqual(self.post("confirmar-email", primer_enlace).status_code, 400)
        self.assertEqual(self.post("restablecer", {**reset_anterior, "nueva_password": NUEVA_CLAVE}).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, original)

    def test_invitar_no_envia_si_hay_rollback_y_nunca_devuelve_token(self):
        from apps.accounts.credenciales import invitar_usuario

        invitado = Usuario.objects.create_user("invitado@example.test", None)
        operador = Usuario.objects.create_superuser("operador@example.test", CLAVE)
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.assertIsNone(invitar_usuario(invitado, actor=operador))
                    raise RuntimeError("rollback sintético")
            except RuntimeError:
                pass
        self.assertEqual(len(mail.outbox), 0)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(invitar_usuario(invitado, actor=operador))
        consumir_correo_sintetico()
        self.assertEqual(mail.outbox[0].to, [invitado.email])
        datos = self.enlace(invitado.email)
        self.assertEqual(self.post("restablecer", {**datos, "nueva_password": NUEVA_CLAVE}).status_code, 204)
        invitado.refresh_from_db()
        self.assertTrue(invitado.check_password(NUEVA_CLAVE))

    def test_gobierno_plataforma_invita_sin_institucion_sin_ganar_control_de_privilegiados(self):
        from apps.accounts.credenciales import invitar_usuario, solicitar_recuperacion
        from rest_framework.exceptions import PermissionDenied

        operador = Usuario.objects.create_user("gobierno@example.test", CLAVE)
        Membresia.objects.create(usuario=operador, rol=Membresia.Rol.PLATAFORMA)
        invitado = Usuario.objects.create_user("nuevo-global@example.test", None)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertIsNone(invitar_usuario(invitado, actor=operador))
        consumir_correo_sintetico()
        self.assertEqual(mail.outbox[-1].to, [invitado.email])
        root = Usuario.objects.create_superuser("privilegiado@example.test", CLAVE)
        with self.assertRaises(PermissionDenied):
            solicitar_recuperacion(root, actor=operador)

    def test_error_correo_no_revela_identidad_ni_imprime_mensaje_proveedor(self):
        with patch("django.core.mail.message.EmailMessage.send", side_effect=OSError("dato-privado-ficticio")):
            respuesta = self.post("recuperacion", {"email": self.usuario.email})
        self.assertEqual(respuesta.status_code, 202)
        self.assertNotIn("dato-privado", str(respuesta.data))

    def test_header_simulacion_no_cambia_credenciales(self):
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post(
            "/api/auth/cambiar-password/", {"password_actual": CLAVE, "nueva_password": NUEVA_CLAVE},
            format="json", HTTP_X_PLEXO_SIMULACION="simulacion-ficticia",
        )
        self.assertEqual(respuesta.status_code, 403)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(CLAVE))


@skipUnless(connection.vendor == "postgresql", "Requiere locks y conexiones PostgreSQL")
@override_settings(**CONFIGURACION)
class EmailConcurrenteInstitucionalTests(TransactionTestCase):
    def test_confirmaciones_con_variantes_case_no_crean_dos_identidades(self):
        from apps.accounts import credenciales

        caches["portal"].clear()
        usuarios = [Usuario.objects.create_user(f"original-{n}@example.test", CLAVE) for n in range(2)]
        destinos = ["Compartido@example.test", "compartido@example.test"]
        solicitudes = []
        for usuario, destino in zip(usuarios, destinos):
            credenciales.solicitar_cambio_email(usuario, CLAVE, destino)
            consumir_correo_sintetico()
            mensaje = next(m for m in reversed(mail.outbox) if m.to == [destino] and "#uid=" in m.body)
            url = next(p for p in mensaje.body.split() if p.startswith("https://") and "#uid=" in p)
            solicitudes.append({k: v[0] for k, v in parse_qs(urlsplit(url).fragment).items()})

        ambos = Barrier(2, timeout=10)
        bloquear = credenciales.bloquear_destino_email

        def esperar(email):
            ambos.wait()
            return bloquear(email)

        def confirmar(datos):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                return APIClient().post("/api/auth/confirmar-email/", datos, format="json").status_code
            finally:
                connections.close_all()

        with patch.object(credenciales, "bloquear_destino_email", side_effect=esperar):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futuros = [pool.submit(confirmar, datos) for datos in solicitudes]
                codigos = [f.result(timeout=15) for f in futuros]
        self.assertCountEqual(codigos, [204, 400])
        self.assertEqual(Usuario.objects.filter(email__iexact=destinos[0]).count(), 1)

    def test_alta_y_confirmacion_comparten_lock_de_destino(self):
        from apps.accounts import credenciales, views

        caches["portal"].clear()
        titular = Usuario.objects.create_user("titular-concurrente@example.test", CLAVE)
        operador = Usuario.objects.create_superuser("operador-concurrente@example.test", CLAVE)
        destino = "Compartido-alta@example.test"
        credenciales.solicitar_cambio_email(titular, CLAVE, destino)
        consumir_correo_sintetico()
        mensaje = next(m for m in reversed(mail.outbox) if m.to == [destino] and "#uid=" in m.body)
        url = next(p for p in mensaje.body.split() if p.startswith("https://") and "#uid=" in p)
        datos = {k: v[0] for k, v in parse_qs(urlsplit(url).fragment).items()}
        ambos = Barrier(2, timeout=10)
        bloquear = credenciales.bloquear_destino_email

        def esperar(email):
            ambos.wait()
            return bloquear(email)

        def solicitar(alta):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                cliente = APIClient()
                if alta:
                    cliente.force_authenticate(operador)
                    return cliente.post("/api/usuarios/", {"email": destino.lower(), "nombre": "Invitado"}, format="json").status_code
                return cliente.post("/api/auth/confirmar-email/", datos, format="json").status_code
            finally:
                connections.close_all()

        with patch.object(credenciales, "bloquear_destino_email", side_effect=esperar), \
                patch.object(views, "bloquear_destino_email", side_effect=esperar):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futuros = [pool.submit(solicitar, alta) for alta in (True, False)]
                codigos = [f.result(timeout=15) for f in futuros]
        self.assertEqual(codigos.count(400), 1)
        self.assertTrue(201 in codigos or 204 in codigos, codigos)
        self.assertEqual(Usuario.objects.filter(email__iexact=destino).count(), 1)
