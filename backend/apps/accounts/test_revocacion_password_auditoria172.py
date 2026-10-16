"""AUD-009: cambiar la clave invalida access y refresh, sin force_authenticate."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from urllib.parse import parse_qs, urlsplit
from unittest import skipUnless
from unittest.mock import patch

from django.core import mail
from django.core.cache import caches
from django.db import connection, connections
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.test import APITestCase
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Usuario
from .test_credenciales_auditoria172 import CONFIGURACION, consumir_correo_sintetico


def datos_enlace_recuperacion(destinatario):
    mensaje = next(m for m in reversed(mail.outbox) if m.to == [destinatario] and "#uid=" in m.body)
    url = next(p for p in mensaje.body.split() if p.startswith("https://") and "#uid=" in p)
    return {k: v[0] for k, v in parse_qs(urlsplit(url).fragment).items()}


@override_settings(**CONFIGURACION)
class RevocacionPasswordInstitucionalTests(APITestCase):
    inicial = "Clave-ficticia-inicial-172!"
    nueva = "Otra-clave-ficticia-172!"

    def setUp(self):
        caches["portal"].clear()
        self.usuario = Usuario.objects.create_user("sesion-ficticia@example.test", self.inicial)

    def login(self, password):
        respuesta = self.client.post("/api/auth/token/", {
            "email": self.usuario.email, "password": password,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def cambiar_clave(self):
        self.usuario.set_password(self.nueva)
        self.usuario.save(update_fields=["password"])

    def test_access_y_refresh_previos_se_rechazan_tras_cambiar_clave(self):
        tokens = self.login(self.inicial)
        self.cambiar_clave()
        respuesta = self.client.get("/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(respuesta.status_code, 401)

    def test_refresh_previo_no_reabre_sesion_tras_cambiar_clave(self):
        tokens = self.login(self.inicial)
        self.cambiar_clave()
        respuesta = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(respuesta.status_code, 401)

    def test_nuevo_login_y_refresh_siguen_funcionando(self):
        self.cambiar_clave()
        tokens = self.login(self.nueva)
        respuesta = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        acceso = respuesta.data["access"]
        self.assertEqual(self.client.get("/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {acceso}").status_code, 200)

    def test_tokens_sin_huella_no_reabren_sesion_aun_con_sid_valido(self):
        par = self.login(self.inicial)
        access = AccessToken(par["access"])
        refresh = RefreshToken(par["refresh"])
        for token in (access, refresh):
            token.payload.pop(api_settings.REVOKE_TOKEN_CLAIM, None)
        self.assertEqual(self.client.get("/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/token/refresh/", {"refresh": str(refresh)}, format="json").status_code, 401)

    def test_refresh_de_usuario_inexistente_es_rechazo_controlado(self):
        refresh = RefreshToken.for_user(self.usuario)
        self.usuario.delete()
        respuesta = self.client.post("/api/auth/token/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(respuesta.status_code, 401)

    def comprobar_sesiones_revocadas(self, sesiones):
        for indice, sesion in enumerate(sesiones):
            with self.subTest(sesion=indice):
                self.assertEqual(self.client.get(
                    "/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {sesion['access']}",
                ).status_code, 401)
                self.assertEqual(self.client.post(
                    "/api/auth/token/refresh/", {"refresh": sesion["refresh"]}, format="json",
                ).status_code, 401)

    def test_endpoint_cambiar_password_revoca_los_dos_logins(self):
        sesiones = [self.login(self.inicial), self.login(self.inicial)]
        self.assertNotEqual(sesiones[0]["refresh"], sesiones[1]["refresh"])
        respuesta = self.client.post("/api/auth/cambiar-password/", {
            "password_actual": self.inicial, "nueva_password": self.nueva,
        }, format="json", HTTP_AUTHORIZATION=f"Bearer {sesiones[0]['access']}")
        self.assertEqual(respuesta.status_code, 204, respuesta.data)
        self.comprobar_sesiones_revocadas(sesiones)
        nuevos = self.login(self.nueva)
        self.assertEqual(self.client.get(
            "/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {nuevos['access']}",
        ).status_code, 200)

    def test_endpoint_restablecer_por_enlace_revoca_los_dos_logins(self):
        sesiones = [self.login(self.inicial), self.login(self.inicial)]
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post("/api/auth/recuperacion/", {"email": self.usuario.email}, format="json")
        consumir_correo_sintetico()
        self.assertEqual(respuesta.status_code, 202)
        enlace = datos_enlace_recuperacion(self.usuario.email)
        respuesta = self.client.post("/api/auth/restablecer/", {**enlace, "nueva_password": self.nueva}, format="json")
        self.assertEqual(respuesta.status_code, 204, respuesta.data)
        self.comprobar_sesiones_revocadas(sesiones)
        nuevos = self.login(self.nueva)
        respuesta = self.client.post("/api/auth/token/refresh/", {"refresh": nuevos["refresh"]}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_refresh_se_rechaza_si_usuario_fue_desactivado(self):
        sesiones = [self.login(self.inicial)]
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.comprobar_sesiones_revocadas(sesiones)

    def test_refresh_no_admite_cuenta_de_referencia_aun_con_token_firmado(self):
        referencia = Usuario.objects.create_user("medico@referencia.plexo.invalid", self.inicial)
        # Emisión directa sólo para probar la regla del receptor con JWT válido:
        # la cuenta de referencia no puede obtenerlo mediante el login público.
        refresh = RefreshToken.for_user(referencia)
        respuesta = self.client.post("/api/auth/token/refresh/", {"refresh": str(refresh)}, format="json")
        self.assertEqual(respuesta.status_code, 401)


@override_settings(**CONFIGURACION)
@skipUnless(connection.vendor == "postgresql", "Requiere locks y pg_blocking_pids de PostgreSQL")
class RefreshContraResetConcurrenteTests(TransactionTestCase):
    inicial = RevocacionPasswordInstitucionalTests.inicial
    nueva = RevocacionPasswordInstitucionalTests.nueva

    def setUp(self):
        caches["portal"].clear()
        self.usuario = Usuario.objects.create_user("concurrente-ficticio@example.test", self.inicial)
        self.client = APIClient()
        respuesta = self.client.post("/api/auth/token/", {
            "email": self.usuario.email, "password": self.inicial,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.sesion = respuesta.data
        respuesta = self.client.post("/api/auth/recuperacion/", {"email": self.usuario.email}, format="json")
        consumir_correo_sintetico()
        self.assertEqual(respuesta.status_code, 202)
        self.enlace = datos_enlace_recuperacion(self.usuario.email)

    def _cruzar(self, primero):
        from . import credenciales

        bloqueado = Event()
        liberar = Event()
        segundo_listo = Event()
        pids = {}
        tipo, objeto, atributo = (
            ("refresh", TokenRefreshSerializer, "validate") if primero == "refresh"
            else ("reset", credenciales, "_guardar_password")
        )
        original = getattr(objeto, atributo)

        def pausar_con_lock(*args, **kwargs):
            bloqueado.set()
            if not liberar.wait(timeout=10):
                raise AssertionError("No se liberó la operación que mantiene el lock")
            return original(*args, **kwargs)

        def operar(accion, segundo=False):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids[accion] = cursor.fetchone()[0]
                if segundo:
                    segundo_listo.set()
                cliente = APIClient()
                if accion == "refresh":
                    respuesta = cliente.post("/api/auth/token/refresh/", {"refresh": self.sesion["refresh"]}, format="json")
                else:
                    respuesta = cliente.post("/api/auth/restablecer/", {**self.enlace, "nueva_password": self.nueva}, format="json")
                return respuesta.status_code, respuesta.data
            finally:
                connections.close_all()

        segundo = "reset" if primero == "refresh" else "refresh"
        with patch.object(objeto, atributo, pausar_con_lock):
            with ThreadPoolExecutor(max_workers=2) as pool:
                primero_futuro = pool.submit(operar, tipo)
                try:
                    self.assertTrue(bloqueado.wait(timeout=10), "La primera operación no adquirió el lock")
                    segundo_futuro = pool.submit(operar, segundo, True)
                    self.assertTrue(segundo_listo.wait(timeout=10))
                    limite = monotonic() + 3
                    espera_real = False
                    while monotonic() < limite:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pids[segundo]])
                            espera_real = pids[primero] in cursor.fetchone()[0]
                        if espera_real:
                            break
                        sleep(0.02)
                    self.assertTrue(espera_real, "La segunda conexión no esperó por el lock de la primera")
                finally:
                    liberar.set()
                primero_resultado = primero_futuro.result(timeout=12)
                segundo_resultado = segundo_futuro.result(timeout=12)
        resultados = {primero: primero_resultado, segundo: segundo_resultado}
        self.assertEqual(resultados["reset"][0], 204, resultados["reset"][1])
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(self.nueva))
        for sesion in [self.sesion, *([resultados["refresh"][1]] if resultados["refresh"][0] == 200 else [])]:
            self.assertEqual(self.client.get(
                "/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {sesion['access']}",
            ).status_code, 401)
            self.assertEqual(self.client.post(
                "/api/auth/token/refresh/", {"refresh": sesion["refresh"]}, format="json",
            ).status_code, 401)
        return resultados

    def test_refresh_primero_no_legitima_tokens_tras_reset(self):
        resultados = self._cruzar("refresh")
        self.assertEqual(resultados["refresh"][0], 200, resultados["refresh"][1])

    def test_reset_primero_hace_fallar_refresh_que_espero_el_lock(self):
        resultados = self._cruzar("reset")
        self.assertEqual(resultados["refresh"][0], 401, resultados["refresh"][1])
