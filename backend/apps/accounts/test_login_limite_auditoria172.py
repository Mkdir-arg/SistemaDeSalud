"""Límite de intentos fallidos en el login institucional (#172, AUD-010).

10 fallos por email y 100 por IP en 15 minutos (decisión del dueño). Solo
cuentan los fallos; con el cupo agotado la respuesta es 429 genérica aunque la
clave sea correcta. Credenciales sintéticas.
"""
from unittest.mock import patch

from django.core.cache import caches
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Usuario

CLAVE = "Clave-sintetica-login-172!"


class LimiteLoginAuditoria172Tests(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.usuario = Usuario.objects.create_user("login-limite@example.test", CLAVE, nombre="Persona")
        self.otra = Usuario.objects.create_user("otra-login@example.test", CLAVE, nombre="Otra")

    def login(self, email, clave, ip="192.0.2.30"):
        return self.client.post("/api/auth/token/", {"email": email, "password": clave}, format="json",
                                HTTP_X_FORWARDED_FOR=ip)

    def test_diez_fallos_bloquean_esa_cuenta_aunque_la_clave_sea_correcta(self):
        for _ in range(10):
            self.assertEqual(self.login(self.usuario.email, "incorrecta").status_code, 401)
        bloqueado = self.login(self.usuario.email, CLAVE)
        self.assertEqual(bloqueado.status_code, 429)
        self.assertTrue(int(bloqueado["Retry-After"]) > 0)
        self.assertNotIn("access", bloqueado.data)
        # Mayúsculas o espacios no esquivan el cupo; otra cuenta de la misma IP sigue.
        self.assertEqual(self.login("  LOGIN-LIMITE@example.test ", CLAVE).status_code, 429)
        self.assertEqual(self.login(self.otra.email, CLAVE).status_code, 200)

    @override_settings(INSTITUCIONAL_LOGIN_FALLOS_IP=3)
    def test_el_cupo_por_ip_frena_probar_muchas_cuentas(self):
        for i in range(3):
            self.assertEqual(self.login(f"inexistente{i}@example.test", "x").status_code, 401)
        self.assertEqual(self.login(self.otra.email, CLAVE).status_code, 429)
        # Desde otra IP la misma cuenta entra.
        self.assertEqual(self.login(self.otra.email, CLAVE, ip="192.0.2.31").status_code, 200)

    def test_los_ingresos_correctos_no_consumen_cupo(self):
        for _ in range(15):
            self.assertEqual(self.login(self.usuario.email, CLAVE).status_code, 200)

    def test_la_ventana_siguiente_vuelve_a_permitir(self):
        ahora = 1_800_000_000.0
        with patch("apps.accounts.auth_views._reloj", return_value=ahora):
            for _ in range(10):
                self.login(self.usuario.email, "incorrecta")
            self.assertEqual(self.login(self.usuario.email, CLAVE).status_code, 429)
        with patch("apps.accounts.auth_views._reloj", return_value=ahora + 900):
            self.assertEqual(self.login(self.usuario.email, CLAVE).status_code, 200)

    def test_el_cache_no_guarda_el_email_en_claro(self):
        self.login(self.usuario.email, "incorrecta")
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT cache_key FROM portal_cache")
            claves = [fila[0] for fila in cursor.fetchall()]
        self.assertTrue(claves)
        self.assertFalse(any("login-limite" in clave for clave in claves))
