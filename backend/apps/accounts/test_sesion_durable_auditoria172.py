"""Sesión institucional durable: aceptación con JWT/API y locks PostgreSQL reales.

Todos los usuarios y credenciales son sintéticos. Nunca incluir JWT ni claves
como mensajes de assertions: ante una falla se informa sólo status/SQLSTATE.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from hashlib import sha256
from io import StringIO
from threading import Event
from time import monotonic
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.core.cache import caches
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import Usuario
from .test_credenciales_auditoria172 import CONFIGURACION


class EscenarioSesionDurable:
    clave = "Clave-sintetica-sesion-172!"
    nueva = "Nueva-clave-sintetica-sesion-172!"

    def preparar(self):
        caches["portal"].clear()
        self.usuario = Usuario.objects.create_user("sesion-durable@example.test", self.clave)
        self.client = APIClient()

    def modelo_sesion(self):
        return apps.get_model("accounts", "SesionInstitucional")

    def login(self, usuario=None, clave=None, cliente=None):
        respuesta = (cliente or self.client).post("/api/auth/token/", {
            "email": (usuario or self.usuario).email, "password": clave or self.clave,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(isinstance(respuesta.data.get("access"), str))
        self.assertTrue(isinstance(respuesta.data.get("refresh"), str))
        return dict(respuesta.data)

    def acceso(self, par, **headers):
        return self.client.get("/api/usuarios/me/", HTTP_AUTHORIZATION=f"Bearer {par['access']}", **headers).status_code

    def renovar(self, par):
        return self.client.post("/api/auth/token/refresh/", {"refresh": par["refresh"]}, format="json")

    def logout(self, par, **headers):
        return self.client.post("/api/auth/logout/", {"refresh": par["refresh"]}, format="json", **headers)

    def rechazar_par(self, par):
        self.assertEqual(self.acceso(par), 401)
        self.assertEqual(self.renovar(par).status_code, 401)


@override_settings(**CONFIGURACION)
class SesionDurableAceptacionTests(EscenarioSesionDurable, APITestCase):
    def setUp(self):
        self.preparar()

    def test_login_registra_sid_hash_y_conserva_ttl_configurado(self):
        par = self.login()
        acceso, refresh = AccessToken(par["access"]), RefreshToken(par["refresh"])
        self.assertTrue(isinstance(refresh.get("sid"), str))
        self.assertTrue(acceso.get("sid") == refresh.get("sid"))
        sesion = self.modelo_sesion().objects.get(pk=refresh["sid"])
        self.assertEqual(sesion.usuario_id, self.usuario.pk)
        self.assertIsNone(sesion.revocada_at)
        self.assertTrue(sesion.refresh_jti_hash == sha256(refresh[api_settings.JTI_CLAIM].encode()).hexdigest())
        self.assertEqual(int(sesion.refresh_vence.timestamp()), refresh["exp"])
        # SimpleJWT fija `iat` y `exp` en instantes distintos: pueden diferir en un
        # segundo al cruzar el borde (falla intermitente observada en PG).
        self.assertAlmostEqual(acceso["exp"] - acceso["iat"], int(api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()), delta=1)
        self.assertAlmostEqual(refresh["exp"] - refresh["iat"], int(api_settings.REFRESH_TOKEN_LIFETIME.total_seconds()), delta=1)
        self.assertEqual(self.acceso(par), 200)

    def test_logout_revoca_access_refresh_y_es_repetible(self):
        par = self.login()
        self.assertEqual(self.logout(par).status_code, 204)
        self.assertEqual(self.logout(par).status_code, 204)
        self.rechazar_par(par)
        sid = AccessToken(par["access"])["sid"]
        self.assertIsNotNone(self.modelo_sesion().objects.get(pk=sid).revocada_at)

    def test_logout_de_una_sesion_no_revoca_otro_login(self):
        primera, segunda = self.login(), self.login()
        self.assertTrue(AccessToken(primera["access"])["sid"] != AccessToken(segunda["access"])["sid"])
        self.assertEqual(self.logout(primera).status_code, 204)
        self.rechazar_par(primera)
        self.assertEqual(self.acceso(segunda), 200)
        self.assertEqual(self.renovar(segunda).status_code, 200)

    def test_logout_admite_access_vencido_y_no_depende_de_correo(self):
        par = self.login()
        vencido = AccessToken(par["access"])
        vencido.set_exp(lifetime=timedelta(seconds=-1))
        with override_settings(INSTITUCIONAL_CORREO_MODO=""):
            respuesta = self.logout(par, HTTP_AUTHORIZATION=f"Bearer {vencido}")
        self.assertEqual(respuesta.status_code, 204)
        self.rechazar_par(par)

    def test_logout_refresh_firmado_expirado_no_revoca_familia_vigente(self):
        par = self.login()
        expirado = RefreshToken(par["refresh"])
        # Más allá de SIMPLE_JWT["LEEWAY"] (30 s): dentro del margen la firma vale.
        expirado.set_exp(lifetime=timedelta(seconds=-120))
        respuesta = self.logout({"refresh": str(expirado)})
        self.assertEqual(respuesta.status_code, 401)
        sesion = self.modelo_sesion().objects.get(pk=AccessToken(par["access"])["sid"])
        self.assertIsNone(sesion.revocada_at)
        self.assertEqual(self.acceso(par), 200)
        self.assertEqual(self.renovar(par).status_code, 200)

    def test_vencimiento_durable_rechaza_access_refresh_y_logout_sin_restaurarse(self):
        par = self.login()
        sid = AccessToken(par["access"])["sid"]
        vencimiento = timezone.now() - timedelta(seconds=1)
        self.modelo_sesion().objects.filter(pk=sid).update(refresh_vence=vencimiento)
        self.rechazar_par(par)
        self.assertEqual(self.logout(par).status_code, 401)
        sesion = self.modelo_sesion().objects.get(pk=sid)
        self.assertEqual(sesion.refresh_vence, vencimiento)
        self.assertIsNone(sesion.revocada_at)
        self.assertEqual(self.modelo_sesion().objects.filter(usuario=self.usuario).count(), 1)

    def test_logout_rechaza_refresh_consumido_sin_revocar_ganador(self):
        anterior = self.login()
        respuesta = self.renovar(anterior)
        self.assertEqual(respuesta.status_code, 200)
        ganador = dict(respuesta.data)
        self.assertEqual(self.logout(anterior).status_code, 401)
        self.assertEqual(self.acceso(ganador), 200)
        self.assertEqual(self.renovar(ganador).status_code, 200)

    def test_refresh_un_solo_uso_replay_no_revoca_ganador(self):
        anterior = self.login()
        respuesta = self.renovar(anterior)
        self.assertEqual(respuesta.status_code, 200)
        ganador = dict(respuesta.data)
        self.assertEqual(self.renovar(anterior).status_code, 401)
        self.assertEqual(self.acceso(ganador), 200)
        self.assertEqual(self.renovar(ganador).status_code, 200)
        self.assertEqual(self.modelo_sesion().objects.filter(usuario=self.usuario).count(), 1)

    def test_cambiar_password_revoca_todos_los_logins(self):
        sesiones = [self.login(), self.login()]
        respuesta = self.client.post("/api/auth/cambiar-password/", {
            "password_actual": self.clave, "nueva_password": self.nueva,
        }, format="json", HTTP_AUTHORIZATION=f"Bearer {sesiones[0]['access']}")
        self.assertEqual(respuesta.status_code, 204)
        for indice, par in enumerate(sesiones):
            with self.subTest(sesion=indice):
                self.rechazar_par(par)
        self.assertEqual(self.acceso(self.login(clave=self.nueva)), 200)

    def test_rollback_de_login_no_deja_tokens_utilizables(self):
        with transaction.atomic():
            par = self.login()
            self.assertEqual(self.modelo_sesion().objects.filter(usuario=self.usuario).count(), 1)
            transaction.set_rollback(True)
        self.assertFalse(self.modelo_sesion().objects.filter(usuario=self.usuario).exists())
        self.rechazar_par(par)

    def test_jwt_firmado_sin_sid_malformado_inexistente_o_ajeno_es_401(self):
        par = self.login()
        otro = Usuario.objects.create_user("otra-sesion-durable@example.test", self.clave)
        ajeno = self.login(usuario=otro)
        sid_ajeno = AccessToken(ajeno["access"])["sid"]
        for indice, sid in enumerate((None, "no-es-uuid", [], {}, 123, str(uuid4()), sid_ajeno)):
            with self.subTest(variante=indice):
                alterados = {}
                for clave, clase in (("access", AccessToken), ("refresh", RefreshToken)):
                    token = clase(par[clave])
                    if sid is None:
                        token.payload.pop("sid", None)
                    else:
                        token["sid"] = sid
                    alterados[clave] = str(token)
                self.rechazar_par(alterados)
        self.assertEqual(self.acceso(par), 200)
        self.assertEqual(self.acceso(ajeno), 200)

    def test_sid_propietario_no_admite_claim_de_otro_usuario(self):
        par = self.login()
        otro = Usuario.objects.create_user("claim-ajeno-durable@example.test", self.clave)
        alterados = {}
        for clave, clase in (("access", AccessToken), ("refresh", RefreshToken)):
            token = clase(par[clave])
            token[api_settings.USER_ID_CLAIM] = str(otro.pk)
            alterados[clave] = str(token)
        self.rechazar_par(alterados)
        self.assertEqual(self.acceso(par), 200)

    def test_usuario_inactivo_y_eliminado_no_autorizan_access_ni_refresh(self):
        par = self.login()
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.rechazar_par(par)
        self.usuario.is_active = True
        self.usuario.save(update_fields=["is_active"])
        otro_par = self.login()
        self.usuario.delete()
        self.rechazar_par(otro_par)

    def test_logout_no_admite_simulacion_ni_cambio_de_identidad(self):
        par = self.login()
        respuesta = self.logout(par, HTTP_X_PLEXO_SIMULACION=str(uuid4()))
        self.assertEqual(respuesta.status_code, 403)
        respuesta = self.client.post("/api/auth/logout/", {
            "refresh": par["refresh"], "usuario": self.usuario.pk,
        }, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self.acceso(par), 200)

    def test_simulacion_no_acepta_actor_real_con_sesion_revocada(self):
        from apps.instituciones.models import Institucion

        institucion = Institucion.objects.create(nombre="Simulación durable sintética")
        call_command("preparar_cuentas_referencia", institucion=[institucion.pk], financiador=[],
                     ancla_estatal=institucion.pk, stdout=StringIO())
        actor = Usuario.objects.create_superuser("actor-durable@example.test", self.clave)
        par = self.login(usuario=actor)
        respuesta = self.client.post("/api/simulaciones/", {
            "ambito": "institucion", "rol": "medico", "institucion": institucion.pk,
        }, format="json", HTTP_AUTHORIZATION=f"Bearer {par['access']}")
        self.assertEqual(respuesta.status_code, 201)
        headers = {"HTTP_X_PLEXO_SIMULACION": respuesta.data["id"]}
        self.assertEqual(self.acceso(par, **headers), 200)
        self.assertEqual(self.logout(par).status_code, 204)
        self.assertEqual(self.acceso(par, **headers), 401)


@override_settings(**CONFIGURACION)
@skipUnless(connection.vendor == "postgresql", "Requiere locks y pg_blocking_pids PostgreSQL")
class SesionDurableConcurrenciaTests(EscenarioSesionDurable, TransactionTestCase):
    def setUp(self):
        self.preparar()
        self.par = self.login()

    def cruzar(self, primera, segunda):
        from . import sesiones

        retenido, liberar, segunda_iniciada = Event(), Event(), Event()
        pids = {}
        objeto, atributo = ((TokenRefreshSerializer, "validate") if primera == "refresh"
                            else (sesiones, "_marcar_revocada"))
        original = getattr(objeto, atributo)

        def pausar_con_locks(*args, **kwargs):
            retenido.set()
            if not liberar.wait(10):
                raise AssertionError("Timeout de la operación que mantiene locks reales")
            return original(*args, **kwargs)

        def operar(etiqueta, accion, es_segunda=False):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '6s'")
                    cursor.execute("SET statement_timeout = '9s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids[etiqueta] = cursor.fetchone()[0]
                if es_segunda:
                    segunda_iniciada.set()
                cliente = APIClient()
                url = "/api/auth/token/refresh/" if accion == "refresh" else "/api/auth/logout/"
                respuesta = cliente.post(url, {"refresh": self.par["refresh"]}, format="json")
                return respuesta.status_code, dict(respuesta.data) if isinstance(respuesta.data, dict) else None
            finally:
                connections.close_all()

        with patch.object(objeto, atributo, pausar_con_locks):
            with ThreadPoolExecutor(max_workers=2) as pool:
                uno = pool.submit(operar, "primera", primera)
                try:
                    self.assertTrue(retenido.wait(10), "No llegó al punto posterior a los locks")
                    dos = pool.submit(operar, "segunda", segunda, True)
                    self.assertTrue(segunda_iniciada.wait(10))
                    limite, bloqueo_real = monotonic() + 4, False
                    while monotonic() < limite:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pids["segunda"]])
                            bloqueo_real = pids["primera"] in cursor.fetchone()[0]
                        if bloqueo_real:
                            break
                        # Poll acotado de estado PG, no coordinación por tiempo.
                        Event().wait(0.02)
                    self.assertTrue(bloqueo_real, "La segunda conexión no esperó el lock real de la primera")
                finally:
                    liberar.set()
                resultados = uno.result(timeout=15), dos.result(timeout=15)
        return resultados

    def test_refresh_concurrente_solo_un_ganador_y_replay_preserva_sesion(self):
        primero, segundo = self.cruzar("refresh", "refresh")
        self.assertEqual((primero[0], segundo[0]), (200, 401))
        self.assertEqual(self.acceso(primero[1]), 200)
        self.assertEqual(self.renovar(primero[1]).status_code, 200)

    def test_logout_primero_revoca_refresh_que_espero_el_lock(self):
        primero, segundo = self.cruzar("logout", "refresh")
        self.assertEqual((primero[0], segundo[0]), (204, 401))
        self.rechazar_par(self.par)

    def test_refresh_primero_hace_obsoleto_logout_anterior_sin_revocar_ganador(self):
        primero, segundo = self.cruzar("refresh", "logout")
        self.assertEqual((primero[0], segundo[0]), (200, 401))
        self.assertEqual(self.acceso(primero[1]), 200)
        self.assertEqual(self.renovar(primero[1]).status_code, 200)
