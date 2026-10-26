"""Tolerancia de reloj JWT (#172): 30 s para iat futuro y exp vencido.

Los tokens se reescriben con la firma real; no se parchea el reloj global.
La revocación por sesión y por contraseña no usa la tolerancia.
"""
import time

from django.core.cache import caches
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Usuario
from .test_credenciales_auditoria172 import CONFIGURACION

CLAVE = "Clave-sintetica-reloj-172!"


@override_settings(**CONFIGURACION)
class ToleranciaRelojJWTTests(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.usuario = Usuario.objects.create_user("reloj@example.test", CLAVE)
        self.client = APIClient()
        respuesta = self.client.post("/api/auth/token/", {
            "email": self.usuario.email, "password": CLAVE,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.par = dict(respuesta.data)

    def access(self, *, iat=0, exp=None):
        """Access de la sesión real con iat/exp desplazados en segundos."""
        token = AccessToken(self.par["access"])
        ahora = int(time.time())
        token["iat"] = ahora + iat
        if exp is not None:
            token["exp"] = ahora + exp
        return str(token)

    def estado(self, crudo):
        return self.client.get("/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {crudo}").status_code

    def test_iat_futuro_dentro_de_la_tolerancia_se_acepta(self):
        self.assertEqual(self.estado(self.access(iat=10)), 200)

    def test_iat_futuro_fuera_de_la_tolerancia_se_rechaza(self):
        self.assertEqual(self.estado(self.access(iat=120)), 401)

    def test_access_vencido_hace_poco_sigue_valiendo(self):
        self.assertEqual(self.estado(self.access(iat=-600, exp=-10)), 200)

    def test_access_vencido_hace_mucho_se_rechaza(self):
        self.assertEqual(self.estado(self.access(iat=-600, exp=-120)), 401)

    def test_revocar_la_sesion_corta_al_instante_aunque_haya_tolerancia(self):
        vencido = self.access(iat=-600, exp=-10)
        respuesta = self.client.post("/api/auth/logout/", {"refresh": self.par["refresh"]}, format="json")
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(self.estado(vencido), 401)
        self.assertEqual(self.estado(self.access(iat=10)), 401)

    def test_cambiar_la_contrasena_corta_al_instante_aunque_haya_tolerancia(self):
        vencido = self.access(iat=-600, exp=-10)
        self.usuario.set_password("Otra-clave-sintetica-reloj-172!")
        self.usuario.save()
        self.assertEqual(self.estado(vencido), 401)
