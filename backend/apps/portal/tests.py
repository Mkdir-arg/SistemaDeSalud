"""
Portal del paciente (#120): cuenta, sesión, enlaces e identidad.

Es la primera superficie pública con cuentas de terceros. Estas pruebas fijan
lo que no se puede romper sin que nadie lo note: que los tokens del portal y
del sistema no se crucen, que registro y recupero no digan si un email existe,
que un enlace sirva una sola vez, los límites de intentos y que el simulado de
RENAPER nunca valide en producción.
"""
import json
import os
import re
import subprocess
import unicodedata
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.contrib.auth.hashers import is_password_usable
from django.core import mail
from django.core.cache import caches
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import SimpleRateThrottle

from apps.accounts.models import Usuario

from . import renaper
from .models import CuentaPaciente, EnlacePortal, EventoPortal, SesionPortal
from .tokens import abrir_sesion, emitir_enlace, hash_token

CLAVE = "Una-clave-larga-2026"
DNI = {"documento": "34.521.521", "sexo": "F", "numero_tramite": "00412345678"}
SIMULADO = {"RENAPER_MODO": "simulado", "ENTORNO": "desarrollo"}


def token_del_correo(mensaje):
    return re.search(r"#token=(\S+)", mensaje.body).group(1)


@override_settings(PORTAL_CORREO_EN_SEGUNDO_PLANO=False)
class Base(APITestCase):
    def setUp(self):
        caches["portal"].clear()

    def cuenta(self, email="martina@correo.test", verificada=True, **extra):
        cuenta = CuentaPaciente(email=email, **extra)
        cuenta.set_password(CLAVE)
        if verificada:
            cuenta.email_verificado_at = timezone.now()
        cuenta.save()
        return cuenta

    def validada(self, email="martina@correo.test", documento="34521521"):
        return self.cuenta(
            email, identidad="validada", documento=documento, sexo="F", identidad_via="renaper",
            identidad_validada_at=timezone.now(), nombre="Martina", apellido="Sosa",
        )

    def cliente(self, cuenta):
        _, acceso, _ = abrir_sesion(cuenta)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {acceso}")
        return cliente

    def post(self, ruta, datos, cliente=None, **extra):
        return (cliente or self.client).post(f"/api/mi/{ruta}", datos, format="json", **extra)


class AislamientoDeTokensTests(Base):
    """Criterios: token del portal contra la API institucional, y al revés."""

    def test_token_del_portal_contra_la_api_institucional_da_401(self):
        cliente = self.cliente(self.validada())
        for ruta in ["/api/casos/", "/api/estado/", "/api/usuarios/me/", "/api/ciudadanos/", "/api/"]:
            with self.subTest(ruta=ruta):
                self.assertEqual(cliente.get(ruta).status_code, 401)

    def test_jwt_del_sistema_contra_el_portal_da_401(self):
        Usuario.objects.create_superuser("root@salud.test", CLAVE, nombre="Root")
        r = self.client.post("/api/auth/token/", {"email": "root@salud.test", "password": CLAVE}, format="json")
        self.assertEqual(r.status_code, 200)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        for ruta in ["cuenta/", "perfil/"]:
            with self.subTest(ruta=ruta):
                self.assertEqual(cliente.get(f"/api/mi/{ruta}").status_code, 401)
        self.assertEqual(self.post("cuenta/validar-identidad/", DNI, cliente).status_code, 401)

    def test_sesion_del_admin_de_django_no_entra_al_portal(self):
        admin = Usuario.objects.create_superuser("root@salud.test", CLAVE, nombre="Root")
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/api/mi/cuenta/").status_code, 401)

    def test_sin_token_da_401(self):
        self.assertEqual(self.client.get("/api/mi/cuenta/").status_code, 401)
        self.assertEqual(self.client.get("/api/mi/perfil/").status_code, 401)

    def test_el_token_no_es_un_jwt_y_en_la_base_solo_queda_su_hash(self):
        sesion, acceso, renovacion = abrir_sesion(self.cuenta())
        self.assertTrue(acceso.startswith("hp_"))
        self.assertEqual(acceso.count("."), 0)
        self.assertEqual(sesion.acceso_hash, hash_token(acceso))
        self.assertFalse(SesionPortal.objects.filter(acceso_hash=acceso).exists())

    def test_cuenta_dada_de_baja_no_entra_aunque_tenga_token(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        cuenta.activa = False
        cuenta.save()
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 401)


class RegistroTests(Base):
    def test_registro_nuevo_manda_el_correo_y_la_cuenta_queda_sin_verificar(self):
        r = self.post("cuenta/registro/", {"email": " Martina@Correo.test "})
        self.assertEqual(r.status_code, 202)
        cuenta = CuentaPaciente.objects.get(email="martina@correo.test")
        self.assertFalse(cuenta.email_verificado)
        # La clave se elige con el enlace: hasta entonces no hay con qué entrar.
        self.assertFalse(is_password_usable(cuenta.password))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/mi/verificar-email#token=hp_", mail.outbox[0].body)
        self.assertTrue(EventoPortal.objects.filter(tipo="alta", cuenta=cuenta).exists())

    def test_la_respuesta_es_identica_exista_o_no_el_email(self):
        self.cuenta()
        self.cuenta("pendiente@correo.test", verificada=False)
        respuestas = [
            self.post("cuenta/registro/", {"email": email})
            for email in ["martina@correo.test", "pendiente@correo.test", "nadie@correo.test"]
        ]
        self.assertEqual(len({(r.status_code, str(r.data)) for r in respuestas}), 1)

    def test_registrar_un_email_existente_no_le_cambia_la_contrasena(self):
        cuenta = self.cuenta()
        self.post("cuenta/registro/", {"email": cuenta.email, "password": "Otra-clave-larga-99"})
        cuenta.refresh_from_db()
        self.assertTrue(cuenta.check_password(CLAVE))
        self.assertIn("Ya tenés una cuenta", mail.outbox[-1].subject)

    def test_registro_y_despues_ingreso_no_dice_si_la_cuenta_esta_confirmada(self):
        """Antes, registrar con una clave elegida y probarla daba 403 o 401
        según la cuenta estuviera confirmada o no."""
        self.cuenta()
        resultados = []
        for email in ["martina@correo.test", "nadie@correo.test"]:
            self.post("cuenta/registro/", {"email": email, "password": "Clave-del-intruso-1"})
            r = self.post("cuenta/ingresar/", {"email": email, "password": "Clave-del-intruso-1"})
            resultados.append((r.status_code, r.data))
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(resultados[0][0], 401)

    def test_sin_email_verificado_no_valida_identidad_ni_ve_datos(self):
        """Criterio: mientras no verifique, no valida la identidad ni ve datos."""
        cliente = self.cliente(self.cuenta(verificada=False))
        with override_settings(**SIMULADO):
            r = self.post("cuenta/validar-identidad/", DNI, cliente)
        self.assertEqual((r.status_code, r.data["codigo"]), (403, "email_sin_verificar"))
        r = cliente.get("/api/mi/perfil/")
        self.assertEqual((r.status_code, r.data["codigo"]), (403, "email_sin_verificar"))

    def test_un_correo_que_no_sale_no_cambia_la_respuesta_ni_filtra_datos_al_log(self):
        with mock.patch("apps.portal.correo.send_mail", side_effect=OSError("smtp caído")), \
                self.assertLogs("apps.portal.correo", "ERROR") as logs:
            r = self.post("cuenta/registro/", {"email": "martina@correo.test"})
        self.assertEqual(r.status_code, 202)
        texto = "\n".join(logs.output)
        self.assertNotIn("martina@correo.test", texto)
        self.assertNotIn("hp_", texto)


class VerificacionTests(Base):
    def registrar(self):
        self.post("cuenta/registro/", {"email": "martina@correo.test"})
        return token_del_correo(mail.outbox[-1])

    def confirmar(self, token, password=CLAVE):
        return self.post("cuenta/verificar-email/", {"token": token, "password": password})

    def test_el_enlace_confirma_fija_la_clave_y_abre_sesion_una_sola_vez(self):
        token = self.registrar()
        r = self.confirmar(token)
        self.assertEqual(r.status_code, 200)
        cuenta = CuentaPaciente.objects.get()
        self.assertTrue(cuenta.email_verificado)
        self.assertTrue(cuenta.check_password(CLAVE))
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(cliente.get("/api/mi/cuenta/").data["email_verificado"], True)
        self.assertTrue(EventoPortal.objects.filter(tipo="email_verificado", cuenta=cuenta).exists())
        r = self.confirmar(token, "Otra-clave-larga-99")
        self.assertEqual((r.status_code, r.data["codigo"]), (400, "enlace_invalido"))
        cuenta.refresh_from_db()
        self.assertTrue(cuenta.check_password(CLAVE))

    def test_una_clave_debil_no_gasta_el_enlace(self):
        token = self.registrar()
        r = self.confirmar(token, "123")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.data)
        self.assertFalse(CuentaPaciente.objects.get().email_verificado)
        self.assertEqual(self.confirmar(token).status_code, 200)

    def test_el_enlace_vencido_no_sirve(self):
        token = self.registrar()
        EnlacePortal.objects.update(vence=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirmar(token).status_code, 400)
        self.assertFalse(CuentaPaciente.objects.get().email_verificado)

    def test_un_enlace_nuevo_anula_el_anterior(self):
        viejo = self.registrar()
        self.post("cuenta/reenviar-verificacion/", {"email": "martina@correo.test"})
        nuevo = token_del_correo(mail.outbox[-1])
        self.assertEqual(self.confirmar(viejo).status_code, 400)
        self.assertEqual(self.confirmar(nuevo).status_code, 200)

    def test_un_enlace_de_recupero_no_verifica(self):
        cuenta = self.cuenta(verificada=False)
        token = emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO)
        self.assertEqual(self.confirmar(token).status_code, 400)

    def test_reenviar_responde_igual_exista_o_no(self):
        self.cuenta(verificada=False)
        a = self.post("cuenta/reenviar-verificacion/", {"email": "martina@correo.test"})
        b = self.post("cuenta/reenviar-verificacion/", {"email": "nadie@correo.test"})
        self.assertEqual((a.status_code, a.data), (b.status_code, b.data))
        self.assertEqual(len(mail.outbox), 1)


class RecuperoTests(Base):
    def test_la_respuesta_es_identica_exista_o_no_el_email(self):
        """Criterio: misma respuesta; el enlace sirve una vez y vence."""
        self.cuenta()
        existe = self.post("cuenta/olvide/", {"email": "martina@correo.test"})
        no_existe = self.post("cuenta/olvide/", {"email": "nadie@correo.test"})
        self.assertEqual((existe.status_code, existe.data), (no_existe.status_code, no_existe.data))
        self.assertEqual([m.to for m in mail.outbox], [["martina@correo.test"]])

    def test_restablecer_sirve_una_vez_y_cierra_las_sesiones(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        self.post("cuenta/olvide/", {"email": cuenta.email})
        token = token_del_correo(mail.outbox[-1])
        self.assertIn("/mi/restablecer#token=", mail.outbox[-1].body)

        r = self.post("cuenta/restablecer/", {"token": token, "password": "Nueva-clave-2026"})
        self.assertEqual(r.status_code, 200)
        cuenta.refresh_from_db()
        self.assertTrue(cuenta.check_password("Nueva-clave-2026"))
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 401)
        self.assertTrue(EventoPortal.objects.filter(tipo="contrasena_restablecida").exists())

        r = self.post("cuenta/restablecer/", {"token": token, "password": "Otra-clave-2026"})
        self.assertEqual((r.status_code, r.data["codigo"]), (400, "enlace_invalido"))

    def test_el_enlace_vencido_no_sirve(self):
        cuenta = self.cuenta()
        token = emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO)
        EnlacePortal.objects.update(vence=timezone.now() - timedelta(seconds=1))
        r = self.post("cuenta/restablecer/", {"token": token, "password": "Nueva-clave-2026"})
        self.assertEqual(r.status_code, 400)
        cuenta.refresh_from_db()
        self.assertTrue(cuenta.check_password(CLAVE))

    def test_una_contrasena_debil_no_gasta_el_enlace(self):
        token = emitir_enlace(self.cuenta(), EnlacePortal.Tipo.RECUPERO)
        r = self.post("cuenta/restablecer/", {"token": token, "password": "123"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.data)
        self.assertEqual(self.post("cuenta/restablecer/", {"token": token, "password": "Nueva-clave-2026"}).status_code, 200)

    def test_un_enlace_de_verificacion_no_restablece(self):
        token = emitir_enlace(self.cuenta(), EnlacePortal.Tipo.VERIFICACION)
        self.assertEqual(
            self.post("cuenta/restablecer/", {"token": token, "password": "Nueva-clave-2026"}).status_code, 400
        )


class IngresoYSesionTests(Base):
    def ingresar(self, email="martina@correo.test", password=CLAVE, **extra):
        return self.post("cuenta/ingresar/", {"email": email, "password": password}, **extra)

    def test_ingresar_devuelve_los_tokens_y_la_cuenta(self):
        self.cuenta()
        r = self.ingresar("MARTINA@correo.test")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["cuenta"]["identidad"], "sin_validar")
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 200)

    def test_credenciales_malas_dan_el_mismo_401_y_se_auditan(self):
        self.cuenta()
        mala = self.ingresar(password="otra")
        inexistente = self.ingresar("nadie@correo.test")
        self.assertEqual((mala.status_code, mala.data), (inexistente.status_code, inexistente.data))
        self.assertEqual(mala.status_code, 401)
        self.assertEqual(EventoPortal.objects.filter(tipo="ingreso_fallido").count(), 2)

    def test_cuenta_dada_de_baja_no_ingresa(self):
        self.cuenta(activa=False)
        self.assertEqual(self.ingresar().status_code, 401)

    def test_429_al_superar_los_intentos_por_email(self):
        """Criterio: superados los intentos de login permitidos, 429."""
        self.cuenta()
        for i in range(10):
            # Mayúsculas y espacios no estrenan contador.
            email = ["martina@correo.test", " MARTINA@correo.test", "Martina@Correo.Test "][i % 3]
            self.assertEqual(self.ingresar(email, password="mala").status_code, 401)
        r = self.ingresar()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)

    def test_quien_prueba_claves_desde_otra_ip_no_deja_afuera_a_la_titular(self):
        self.cuenta()
        for _ in range(10):
            self.ingresar(password="mala", REMOTE_ADDR="198.51.100.9")
        self.assertEqual(self.ingresar(password="mala", REMOTE_ADDR="198.51.100.9").status_code, 429)
        self.assertEqual(self.ingresar(REMOTE_ADDR="203.0.113.20").status_code, 200)

    def test_el_tope_por_email_frena_la_fuerza_bruta_repartida_entre_ips(self):
        self.cuenta()
        for i in range(50):
            self.ingresar(password="mala", REMOTE_ADDR=f"198.51.100.{i}")
        self.assertEqual(self.ingresar(REMOTE_ADDR="203.0.113.20").status_code, 429)

    def test_sin_email_confirmado_no_hay_sesion_y_la_respuesta_es_la_de_siempre(self):
        self.cuenta(verificada=False)
        correcta, mala = self.ingresar(), self.ingresar(password="mala")
        self.assertEqual((correcta.status_code, correcta.data), (mala.status_code, mala.data))
        self.assertEqual(correcta.status_code, 401)
        self.assertFalse(SesionPortal.objects.exists())

    def test_un_limite_que_rechaza_no_le_cuenta_el_pedido_a_los_otros(self):
        """Desde una IP ya frenada no se agota el cupo por email de la titular."""
        self.cuenta()
        for _ in range(60):
            self.ingresar(password="mala", REMOTE_ADDR="198.51.100.9")
        self.assertEqual(self.ingresar(REMOTE_ADDR="203.0.113.20").status_code, 200)

    def test_la_auditoria_del_ingreso_fallido_guarda_email_e_ip(self):
        self.ingresar("nadie@correo.test", REMOTE_ADDR="198.51.100.7")
        evento = EventoPortal.objects.get(tipo="ingreso_fallido")
        self.assertEqual((evento.cuenta, evento.email, evento.ip), (None, "nadie@correo.test", "198.51.100.7"))

    def test_el_token_de_renovacion_vencido_no_sirve(self):
        sesion, _, renovacion = abrir_sesion(self.cuenta())
        SesionPortal.objects.filter(pk=sesion.pk).update(renovacion_vence=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post("cuenta/renovar/", {"refresh": renovacion}).status_code, 401)

    def test_429_al_superar_los_intentos_por_ip_con_emails_distintos(self):
        for i in range(30):
            self.ingresar(f"persona{i}@correo.test")
        self.assertEqual(self.ingresar("otra@correo.test").status_code, 429)

    def test_la_ip_sale_del_ultimo_proxy_y_no_del_x_forwarded_for_del_cliente(self):
        """Rotar un `X-Forwarded-For` inventado no estrena IP."""
        for i in range(30):
            self.ingresar(f"persona{i}@correo.test", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}, 203.0.113.7")
        r = self.ingresar("otra@correo.test", HTTP_X_FORWARDED_FOR="10.9.9.9, 203.0.113.7")
        self.assertEqual(r.status_code, 429)

    def test_renovar_rota_los_tokens_y_el_viejo_no_sirve(self):
        cuenta = self.cuenta()
        _, _, renovacion = abrir_sesion(cuenta)
        r = self.post("cuenta/renovar/", {"refresh": renovacion})
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["refresh"], renovacion)
        self.assertEqual(self.post("cuenta/renovar/", {"refresh": renovacion}).status_code, 401)

    def test_renovar_no_pasa_el_tope_de_la_sesion(self):
        sesion, _, renovacion = abrir_sesion(self.cuenta())
        SesionPortal.objects.filter(pk=sesion.pk).update(vence_maximo=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.post("cuenta/renovar/", {"refresh": renovacion}).status_code, 401)

    def test_el_acceso_vencido_da_401(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        SesionPortal.objects.update(acceso_vence=timezone.now() - timedelta(seconds=1))
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 401)

    def test_salir_revoca_el_acceso_y_la_renovacion(self):
        sesion, acceso, renovacion = abrir_sesion(self.cuenta())
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {acceso}")
        self.assertEqual(self.post("cuenta/salir/", {}, cliente).status_code, 204)
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 401)
        self.assertEqual(self.post("cuenta/renovar/", {"refresh": renovacion}).status_code, 401)

    def test_cambiar_contrasena_cierra_las_otras_sesiones(self):
        cuenta = self.cuenta()
        esta, otra = self.cliente(cuenta), self.cliente(cuenta)
        r = self.post("cuenta/cambiar-contrasena/", {"actual": "mala", "nueva": "Nueva-clave-2026"}, esta)
        self.assertEqual(r.status_code, 400)
        self.assertIn("actual", r.data)
        r = self.post("cuenta/cambiar-contrasena/", {"actual": CLAVE, "nueva": "Nueva-clave-2026"}, esta)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(esta.get("/api/mi/cuenta/").status_code, 200)
        self.assertEqual(otra.get("/api/mi/cuenta/").status_code, 401)
        self.assertTrue(EventoPortal.objects.filter(tipo="contrasena_cambiada", cuenta=cuenta).exists())


@override_settings(**SIMULADO)
class IdentidadTests(Base):
    def validar(self, cliente, **cambios):
        return self.post("cuenta/validar-identidad/", {**DNI, **cambios}, cliente)

    def test_valida_con_los_datos_que_coinciden(self):
        """Criterio: queda `validada` con la vía, la fecha y los datos devueltos."""
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        r = self.validar(cliente)
        self.assertEqual(r.status_code, 200)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.identidad, "validada")
        self.assertEqual(cuenta.identidad_via, "renaper")
        self.assertIsNotNone(cuenta.identidad_validada_at)
        self.assertEqual((cuenta.documento, cuenta.sexo, cuenta.nombre), ("34521521", "F", "Ana María"))
        evento = EventoPortal.objects.get(tipo="identidad_validada")
        self.assertNotIn("numero_tramite", evento.detalle)
        r = cliente.get("/api/mi/perfil/")
        self.assertEqual((r.status_code, r.data["documento"]), (200, "34521521"))

    def test_sin_identidad_validada_el_portal_responde_403_con_motivo(self):
        r = self.cliente(self.cuenta()).get("/api/mi/perfil/")
        self.assertEqual((r.status_code, r.data["codigo"]), (403, "identidad_sin_validar"))

    def test_los_rechazos_se_cuentan_y_al_llegar_al_tope_se_bloquea(self):
        """Criterio: sigue `sin_validar`, el intento se cuenta, y al tope se bloquea."""
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        tope = settings.PORTAL_VALIDACION_INTENTOS
        for restantes in range(tope - 1, 0, -1):
            r = self.validar(cliente, numero_tramite="00000000000")
            self.assertEqual((r.status_code, r.data["intentos_restantes"]), (422, restantes))
        r = self.validar(cliente, numero_tramite="00000000000")
        self.assertEqual((r.status_code, r.data["codigo"]), (423, "validacion_bloqueada"))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.identidad, "sin_validar")
        self.assertAlmostEqual(
            cuenta.validacion_bloqueada_hasta,
            timezone.now() + timedelta(hours=settings.PORTAL_VALIDACION_BLOQUEO_HORAS),
            delta=timedelta(minutes=1),
        )
        self.assertEqual(EventoPortal.objects.filter(tipo="identidad_rechazada").count(), tope)

        # Bloqueada: ni siquiera se consulta a RENAPER, aunque los datos sean buenos.
        with mock.patch.object(renaper.Simulado, "cotejar") as cotejar:
            self.assertEqual(self.validar(cliente).status_code, 423)
        cotejar.assert_not_called()

        # Pasado el tiempo, puede volver a probar.
        CuentaPaciente.objects.filter(pk=cuenta.pk).update(validacion_bloqueada_hasta=timezone.now())
        self.assertEqual(self.validar(cliente).status_code, 200)

    def test_renaper_caido_no_cuenta_como_intento(self):
        cuenta = self.cuenta()
        r = self.validar(self.cliente(cuenta), numero_tramite="99999999999")
        self.assertEqual((r.status_code, r.data["codigo"]), (503, "servicio_no_disponible"))
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.intentos_validacion, 0)

    def test_documento_validado_en_otra_cuenta_se_rechaza_y_se_avisa_a_la_titular(self):
        """Criterio y R2: un documento validado pertenece a una sola cuenta."""
        titular = self.validada("titular@correo.test")
        intrusa = self.cuenta("otra@correo.test")
        r = self.validar(self.cliente(intrusa))
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "documento_en_uso"))
        intrusa.refresh_from_db()
        self.assertEqual(intrusa.identidad, "sin_validar")
        self.assertEqual([m.to for m in mail.outbox], [[titular.email]])
        self.assertTrue(EventoPortal.objects.filter(tipo="documento_en_uso", cuenta=intrusa).exists())

    def test_ya_validada_no_vuelve_a_validar(self):
        r = self.validar(self.cliente(self.validada()))
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "ya_validada"))

    def test_el_tramite_tiene_once_digitos(self):
        r = self.validar(self.cliente(self.cuenta()), numero_tramite="123")
        self.assertEqual(r.status_code, 400)
        self.assertIn("numero_tramite", r.data)


class AdaptadorRenaperTests(Base):
    """Criterio: en producción sin credenciales falla y nunca usa el simulado."""

    def test_en_produccion_nunca_se_usa_el_simulado(self):
        cliente = self.cliente(self.cuenta())
        with override_settings(RENAPER_MODO="simulado", ENTORNO="produccion"), \
                mock.patch.object(renaper.Simulado, "cotejar") as simulado:
            r = self.post("cuenta/validar-identidad/", DNI, cliente)
        self.assertEqual((r.status_code, r.data["codigo"]), (503, "servicio_no_disponible"))
        simulado.assert_not_called()
        self.assertEqual(CuentaPaciente.objects.get().identidad, "sin_validar")

    def test_sin_pedir_el_simulado_se_usa_el_real_aun_en_desarrollo(self):
        with override_settings(RENAPER_MODO="real", ENTORNO="desarrollo"):
            self.assertIsInstance(renaper.adaptador(), renaper.Real)
        with override_settings(RENAPER_MODO="simulado", ENTORNO="demo"):
            self.assertIsInstance(renaper.adaptador(), renaper.Simulado)

    def test_el_real_falla_cerrado_sin_dejar_datos_en_el_log(self):
        with self.assertLogs("apps.portal.renaper", "ERROR") as logs, self.assertRaises(renaper.RenaperNoDisponible):
            renaper.Real().cotejar(renaper.DatosCotejo(documento="34521521", sexo="F", numero_tramite=DNI["numero_tramite"]))
        texto = "\n".join(logs.output)
        self.assertNotIn("34521521", texto)
        self.assertNotIn(DNI["numero_tramite"], texto)

    def test_settings_no_arranca_con_el_simulado_en_produccion(self):
        entorno = {**os.environ, "ENTORNO": "produccion", "RENAPER_MODO": "simulado", "DJANGO_DEBUG": "true"}
        entorno.pop("DATABASE_URL", None)
        r = subprocess.run(
            [sys.executable, "-c", "import config.settings"],
            cwd=Path(settings.BASE_DIR), env=entorno, capture_output=True, text=True,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("RENAPER_MODO=simulado", r.stderr)


class LimitesDeCorreoTests(Base):
    def test_429_al_pedir_demasiados_correos_para_el_mismo_email(self):
        for _ in range(3):
            self.assertEqual(self.post("cuenta/olvide/", {"email": "martina@correo.test"}).status_code, 202)
        self.assertEqual(self.post("cuenta/olvide/", {"email": "martina@correo.test"}).status_code, 429)


class PreRegistroTests(Base):
    """Alguien registra el email de otra persona, antes o después que ella."""

    def test_la_cuenta_es_de_quien_abre_el_correo(self):
        for orden in (["intruso", "victima"], ["victima", "intruso"]):
            with self.subTest(orden=orden):
                CuentaPaciente.objects.all().delete()
                mail.outbox.clear()
                caches["portal"].clear()
                for quien in orden:
                    self.post("cuenta/registro/", {"email": "vic@correo.test", "password": f"Clave-de-{quien}-1"})
                # La víctima abre el último correo, el único enlace que sirve.
                token = token_del_correo(mail.outbox[-1])
                r = self.post("cuenta/verificar-email/", {"token": token, "password": CLAVE})
                self.assertEqual(r.status_code, 200)
                for clave in ("Clave-de-intruso-1", "Clave-de-victima-1"):
                    r = self.post("cuenta/ingresar/", {"email": "vic@correo.test", "password": clave})
                    self.assertEqual(r.status_code, 401)
                r = self.post("cuenta/ingresar/", {"email": "vic@correo.test", "password": CLAVE})
                self.assertEqual(r.status_code, 200)

    def test_confirmar_el_email_cierra_cualquier_sesion_previa(self):
        cuenta = self.cuenta(verificada=False)
        cliente = self.cliente(cuenta)
        token = emitir_enlace(cuenta, EnlacePortal.Tipo.VERIFICACION)
        r = self.post("cuenta/verificar-email/", {"token": token, "password": CLAVE})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cliente.get("/api/mi/cuenta/").status_code, 401)

    def test_una_cuenta_dada_de_baja_no_recibe_ni_usa_enlaces(self):
        cuenta = self.cuenta(verificada=False)
        enlace = emitir_enlace(cuenta, EnlacePortal.Tipo.VERIFICACION)
        recupero = emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO)
        cuenta.activa = False
        cuenta.save()
        r = self.post("cuenta/registro/", {"email": cuenta.email, "password": CLAVE})
        self.assertEqual(r.status_code, 202)
        self.assertEqual(mail.outbox, [])
        self.assertEqual(
            self.post("cuenta/verificar-email/", {"token": enlace, "password": CLAVE}).status_code, 400
        )
        r = self.post("cuenta/restablecer/", {"token": recupero, "password": "Nueva-clave-2026"})
        self.assertEqual(r.status_code, 400)
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.email_verificado)
        self.assertTrue(cuenta.check_password(CLAVE))


@override_settings(**SIMULADO)
class IdentidadDetalleTests(Base):
    def validar(self, cliente, **cambios):
        return self.post("cuenta/validar-identidad/", {**DNI, **cambios}, cliente)

    def test_se_guarda_lo_que_devuelve_renaper_y_no_lo_tipeado(self):
        devuelto = renaper.Resultado(
            coincide=True, nombre="MARTINA BELEN", apellido="SOSA", fecha_nacimiento=date(1989, 3, 2)
        )
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        with mock.patch.object(renaper.Simulado, "cotejar", return_value=devuelto):
            self.assertEqual(self.validar(cliente).status_code, 200)
        cuenta.refresh_from_db()
        self.assertEqual(
            (cuenta.nombre, cuenta.apellido, cuenta.fecha_nacimiento), ("MARTINA BELEN", "SOSA", date(1989, 3, 2))
        )
        perfil = cliente.get("/api/mi/perfil/").data
        self.assertEqual((perfil["nombre"], perfil["fecha_nacimiento"]), ("MARTINA BELEN", "1989-03-02"))

    @override_settings(PORTAL_VALIDACION_INTENTOS=2, PORTAL_VALIDACION_BLOQUEO_HORAS=1)
    def test_el_tope_y_el_bloqueo_se_configuran(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        self.assertEqual(self.validar(cliente, numero_tramite="00000000000").data["intentos_restantes"], 1)
        r = self.validar(cliente, numero_tramite="00000000000")
        self.assertEqual(r.status_code, 423)
        cuenta.refresh_from_db()
        self.assertAlmostEqual(
            cuenta.validacion_bloqueada_hasta, timezone.now() + timedelta(hours=1), delta=timedelta(minutes=1)
        )
        self.assertTrue(EventoPortal.objects.filter(tipo="validacion_bloqueada", cuenta=cuenta).exists())

    def test_validar_bien_reinicia_los_intentos(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        self.validar(cliente, numero_tramite="00000000000")
        self.assertEqual(self.validar(cliente).status_code, 200)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.intentos_validacion, 0)

    def test_renaper_caido_queda_auditado(self):
        cuenta = self.cuenta()
        self.validar(self.cliente(cuenta), numero_tramite="99999999999")
        self.assertTrue(EventoPortal.objects.filter(tipo="renaper_no_disponible", cuenta=cuenta).exists())
        cuenta.refresh_from_db()
        self.assertIsNone(cuenta.validacion_en_curso_hasta)

    def test_una_sola_consulta_a_renaper_por_cuenta_a_la_vez(self):
        cuenta = self.cuenta()
        CuentaPaciente.objects.filter(pk=cuenta.pk).update(
            validacion_en_curso_hasta=timezone.now() + timedelta(seconds=30)
        )
        with mock.patch.object(renaper.Simulado, "cotejar") as cotejar:
            r = self.validar(self.cliente(cuenta))
        self.assertEqual((r.status_code, r.data["codigo"]), (429, "validacion_en_curso"))
        cotejar.assert_not_called()

    def test_una_marca_vieja_de_consulta_en_curso_no_traba_la_cuenta(self):
        cuenta = self.cuenta()
        CuentaPaciente.objects.filter(pk=cuenta.pk).update(
            validacion_en_curso_hasta=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.validar(self.cliente(cuenta)).status_code, 200)

    def test_un_error_inesperado_de_renaper_libera_la_marca(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        cliente.raise_request_exception = False
        with mock.patch.object(renaper.Simulado, "cotejar", side_effect=RuntimeError("boom")):
            self.assertEqual(self.validar(cliente).status_code, 500)
        cuenta.refresh_from_db()
        self.assertIsNone(cuenta.validacion_en_curso_hasta)

    def test_si_se_bloquea_durante_la_consulta_no_valida(self):
        """Lo que valió antes de consultar se vuelve a mirar con la fila bloqueada."""
        cuenta = self.cuenta()

        def bloquear_mientras_consulta(datos):
            CuentaPaciente.objects.filter(pk=cuenta.pk).update(
                validacion_bloqueada_hasta=timezone.now() + timedelta(hours=1)
            )
            return renaper.Resultado(coincide=True, nombre="Martina", apellido="Sosa")

        with mock.patch.object(renaper.Simulado, "cotejar", side_effect=bloquear_mientras_consulta):
            r = self.validar(self.cliente(cuenta))
        self.assertEqual(r.status_code, 423)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.identidad, "sin_validar")

    def test_si_otra_cuenta_valida_el_documento_al_mismo_tiempo_se_rechaza_y_se_avisa(self):
        """La carrera de R2: la restricción de la base, no la consulta previa."""
        titular = self.validada("titular@correo.test")
        intrusa = self.cuenta("otra@correo.test")
        # La consulta previa no la ve, como si la titular se validara justo
        # entre esa consulta y el guardado.
        with mock.patch("apps.portal.views.ValidarIdentidadView._titular", return_value=None):
            r = self.validar(self.cliente(intrusa))
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "documento_en_uso"))
        intrusa.refresh_from_db()
        self.assertEqual(intrusa.identidad, "sin_validar")
        self.assertEqual([m.to for m in mail.outbox], [[titular.email]])


class LimitesPorVistaTests(Base):
    """Cada vista pública o sensible declara su límite y responde 429."""

    def agotar(self, alcance, pedido, veces=2):
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {alcance: f"{veces}/hour"}):
            for _ in range(veces):
                self.assertNotEqual(pedido().status_code, 429)
            return pedido().status_code

    def test_cada_vista_tiene_su_limite(self):
        cliente = self.cliente(self.validada())
        sin_validar = self.cliente(self.cuenta("otra@correo.test"))
        casos = {
            "portal_alta_email": lambda: self.post("cuenta/registro/", {"email": "x@correo.test"}),
            "portal_alta_ip": lambda: self.post("cuenta/reenviar-verificacion/", {"email": "y@correo.test"}),
            "portal_recupero_ip": lambda: self.post("cuenta/olvide/", {"email": "z@correo.test"}),
            "portal_enlace_ip": lambda: self.post("cuenta/verificar-email/", {"token": "hp_x", "password": CLAVE}),
            "portal_renovar_ip": lambda: self.post("cuenta/renovar/", {"refresh": "hp_x"}),
            "portal_cuenta": lambda: self.post(
                "cuenta/cambiar-contrasena/", {"actual": "mala", "nueva": "Nueva-clave-2026"}, cliente
            ),
            "portal_identidad_ip": lambda: self.post("cuenta/validar-identidad/", {}, sin_validar),
        }
        for alcance, pedido in casos.items():
            with self.subTest(alcance=alcance):
                caches["portal"].clear()
                self.assertEqual(self.agotar(alcance, pedido), 429)

    def test_restablecer_tambien_tiene_limite(self):
        def pedido():
            return self.post("cuenta/restablecer/", {"token": "hp_x", "password": CLAVE})

        self.assertEqual(self.agotar("portal_enlace_ip", pedido), 429)


class CorreoTests(Base):
    @override_settings(PORTAL_CORREO_EN_SEGUNDO_PLANO=True)
    def test_el_correo_sale_despues_de_responder_en_otro_hilo(self):
        with self.captureOnCommitCallbacks() as callbacks:
            self.post("cuenta/registro/", {"email": "martina@correo.test"})
        self.assertEqual(mail.outbox, [])
        for arrancar in callbacks:
            hilo = arrancar.__self__
            hilo.start()
            hilo.join(5)
        self.assertEqual(len(mail.outbox), 1)

    def test_settings_del_correo_segun_el_entorno(self):
        def leer(**variables):
            entorno = {k: v for k, v in os.environ.items() if k not in VARIABLES_DE_CORREO}
            entorno.update(variables)
            r = subprocess.run(
                [sys.executable, "-c", "import config.settings as s; print(s.EMAIL_BACKEND); print(s.DEFAULT_FROM_EMAIL)"],
                cwd=Path(settings.BASE_DIR), env=entorno, capture_output=True, text=True, check=True,
            )
            return r.stdout.splitlines()

        smtp, consola = "django.core.mail.backends.smtp.EmailBackend", "django.core.mail.backends.console.EmailBackend"
        # Sin ENTORNO y sin DEBUG (un despliegue que se olvidó de fijarlo): SMTP,
        # nunca los enlaces en el log.
        self.assertEqual(leer(DJANGO_DEBUG="false", DJANGO_SECRET_KEY="x" * 50)[0], smtp)
        self.assertEqual(leer(DJANGO_DEBUG="true", ENTORNO="desarrollo")[0], consola)
        self.assertEqual(leer(DJANGO_DEBUG="true", ENTORNO="produccion")[0], smtp)
        # El compose pasa la variable vacía: no puede dejar el remitente vacío.
        self.assertTrue(leer(DJANGO_DEBUG="true", DEFAULT_FROM_EMAIL="")[1].strip())


VARIABLES_DE_CORREO = ("DATABASE_URL", "EMAIL_BACKEND", "ENTORNO", "DEFAULT_FROM_EMAIL", "DJANGO_DEBUG", "RENAPER_MODO")


class TerceraRondaTests(Base):
    """Lo que encontró el ataque al diseño final."""

    @override_settings(**SIMULADO)
    def test_un_cero_a_la_izquierda_no_saltea_r2(self):
        titular = self.validada("titular@correo.test", documento="1234567")
        r = self.post(
            "cuenta/validar-identidad/", {**DNI, "documento": "01.234.567"}, self.cliente(self.cuenta("otra@correo.test"))
        )
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "documento_en_uso"))
        self.assertEqual([m.to for m in mail.outbox], [[titular.email]])

    @override_settings(**SIMULADO)
    def test_el_tramite_solo_acepta_digitos_ascii(self):
        r = self.post("cuenta/validar-identidad/", {**DNI, "numero_tramite": "００４１２３４５６７８"}, self.cliente(self.cuenta()))
        self.assertEqual(r.status_code, 400)
        self.assertIn("numero_tramite", r.data)

    def test_cambiar_la_contrasena_anula_los_enlaces_pendientes(self):
        cuenta = self.cuenta()
        recupero = emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO)
        r = self.post("cuenta/cambiar-contrasena/", {"actual": CLAVE, "nueva": "Nueva-clave-2026"}, self.cliente(cuenta))
        self.assertEqual(r.status_code, 200)
        r = self.post("cuenta/restablecer/", {"token": recupero, "password": "Otra-clave-2026"})
        self.assertEqual((r.status_code, r.data["codigo"]), (400, "enlace_invalido"))

    def test_usar_un_enlace_anula_el_del_otro_tipo(self):
        cuenta = self.cuenta(verificada=False)
        verificacion = emitir_enlace(cuenta, EnlacePortal.Tipo.VERIFICACION)
        recupero = emitir_enlace(cuenta, EnlacePortal.Tipo.RECUPERO)
        self.assertEqual(self.post("cuenta/restablecer/", {"token": recupero, "password": CLAVE}).status_code, 200)
        r = self.post("cuenta/verificar-email/", {"token": verificacion, "password": "Otra-clave-2026"})
        self.assertEqual((r.status_code, r.data["codigo"]), (400, "enlace_invalido"))

    def test_ipv6_cuenta_por_red_y_no_por_direccion(self):
        """Rotar direcciones dentro de un /64 no estrena límite."""
        self.cuenta()
        for i in range(10):
            self.post("cuenta/ingresar/", {"email": "martina@correo.test", "password": "mala"},
                      REMOTE_ADDR=f"2001:db8:1:2::{i + 1:x}")
        r = self.post("cuenta/ingresar/", {"email": "martina@correo.test", "password": CLAVE},
                      REMOTE_ADDR="2001:db8:1:2::ffff")
        self.assertEqual(r.status_code, 429)
        r = self.post("cuenta/ingresar/", {"email": "martina@correo.test", "password": CLAVE},
                      REMOTE_ADDR="2001:db8:9:9::1")
        self.assertEqual(r.status_code, 200)


def respuesta_renaper(**cambios):
    """Una respuesta con la forma de la real y datos inventados."""
    resultado = {
        "iD_TRAMITE_PRINCIPAL": 412345678,
        "iD_TRAMITE_TARJETA_REIMPRESA": 0,
        "ejemplar": "B",
        "vencimiento": "01/02/2030",
        "emision": "01/02/2015",
        "apellido": "SOSA",
        "nombres": "Martina Belén",
        "fechaNacimiento": "1989-03-02",
        "cuil": "27000000000",
        "calle": "CALLE FALSA",
        "numero": "123",
        "ciudad": "CIUDAD",
        "provincia": "PROVINCIA",
        "pais": "ARGENTINA",
        "codigoError": 99,
        "codigof": 3,
        "mensaf": "Sin Aviso de Fallecimiento",
        "origenf": "RENAPER",
        "fechaf": "-",
        "idciudadano": "1",
        "nroError": 0,
        "descripcionError": "DNI/PAS Firmado",
    }
    resultado.update(cambios)
    return {"isSuccess": True, "message": "", "result": resultado}


COTEJO = renaper.DatosCotejo(documento="34521521", sexo="F", numero_tramite="00412345678")


class InterpretarRespuestaTests(APITestCase):
    def test_coincide_comparando_el_tramite_sin_ceros_adelante(self):
        r = renaper.interpretar(respuesta_renaper(), COTEJO)
        self.assertEqual(
            (r.coincide, r.nombre, r.apellido, r.fecha_nacimiento), (True, "Martina Belén", "Sosa", date(1989, 3, 2))
        )

    def test_vale_el_tramite_de_la_tarjeta_reimpresa(self):
        respuesta = respuesta_renaper(iD_TRAMITE_PRINCIPAL=999, iD_TRAMITE_TARJETA_REIMPRESA=412345678)
        self.assertTrue(renaper.interpretar(respuesta, COTEJO).coincide)

    def test_otro_tramite_no_coincide(self):
        r = renaper.interpretar(respuesta_renaper(iD_TRAMITE_PRINCIPAL=412345679), COTEJO)
        self.assertEqual((r.coincide, r.motivo), (False, "tramite_distinto"))

    def test_un_dni_que_no_existe_no_coincide(self):
        for respuesta in (
            {"isSuccess": False, "message": "No encontrado", "result": None},
            {"isSuccess": True, "result": None},
            respuesta_renaper(iD_TRAMITE_PRINCIPAL=0, iD_TRAMITE_TARJETA_REIMPRESA=0),
            respuesta_renaper(iD_TRAMITE_PRINCIPAL=None, iD_TRAMITE_TARJETA_REIMPRESA=None),
        ):
            with self.subTest(respuesta=respuesta):
                r = renaper.interpretar(respuesta, COTEJO)
                self.assertEqual((r.coincide, r.motivo), (False, "no_encontrado"))

    def test_con_aviso_de_fallecimiento_o_sin_dato_no_valida(self):
        for cambios in (
            {"mensaf": "Con Aviso de Fallecimiento", "fechaf": "2020-01-01"},
            {"fechaf": "2020-01-01"},
            {"mensaf": ""},
            {"mensaf": None},
        ):
            with self.subTest(cambios=cambios):
                r = renaper.interpretar(respuesta_renaper(**cambios), COTEJO)
                self.assertEqual((r.coincide, r.motivo), (False, "aviso_fallecimiento"))

    def test_una_respuesta_sin_forma_es_falla_tecnica(self):
        for respuesta in (None, [], "texto"):
            with self.subTest(respuesta=respuesta), self.assertRaises(renaper.RenaperNoDisponible):
                renaper.interpretar(respuesta, COTEJO)

    def test_una_fecha_ilegible_no_rompe_la_validacion(self):
        r = renaper.interpretar(respuesta_renaper(fechaNacimiento="01/03/1989"), COTEJO)
        self.assertEqual((r.coincide, r.fecha_nacimiento), (True, None))


class _Respuesta:
    def __init__(self, cuerpo):
        self.cuerpo = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()

    def read(self, tope):
        return self.cuerpo[:tope]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http(codigo):
    return HTTPError("https://renaper.test", codigo, "error", {}, None)


CONFIGURADO = {
    "RENAPER_URL": "https://renaper.test/api",
    "RENAPER_USUARIO": "usuario-de-prueba",
    "RENAPER_CLAVE": "clave-de-prueba",
    "RENAPER_TIMEOUT": 8,
    "ENTORNO": "produccion",
}
LOGIN = {"token": "token-de-prueba", "expiration": "2099-01-01T00:00:00Z"}
DATOS_SENSIBLES = ("34521521", "412345678", "usuario-de-prueba", "clave-de-prueba", "token-de-prueba", "renaper.test")


@override_settings(**CONFIGURADO)
class AdaptadorRealTests(APITestCase):
    def setUp(self):
        renaper._sesion.olvidar()

    def consultar(self, *respuestas):
        """`respuestas` son, en orden, lo que contesta cada pedido (o la excepción)."""
        with mock.patch("apps.portal.renaper.urlopen", side_effect=list(respuestas)) as llamada:
            return renaper.Real().cotejar(COTEJO), llamada

    def test_hace_login_y_consulta_por_dni_y_sexo_con_el_token(self):
        resultado, llamada = self.consultar(_Respuesta(LOGIN), _Respuesta(respuesta_renaper()))
        self.assertTrue(resultado.coincide)
        login, consulta = (c.args[0] for c in llamada.call_args_list)
        self.assertEqual((login.get_method(), login.full_url), ("POST", "https://renaper.test/api/auth/login"))
        self.assertEqual(json.loads(login.data), {"username": "usuario-de-prueba", "password": "clave-de-prueba"})
        self.assertEqual(consulta.full_url, "https://renaper.test/api/consultarenaper?dni=34521521&sexo=F")
        self.assertEqual(consulta.get_header("Authorization"), "Bearer token-de-prueba")
        self.assertEqual(llamada.call_args.kwargs["timeout"], 8)

    def test_reusa_el_token_hasta_que_vence(self):
        self.consultar(_Respuesta(LOGIN), _Respuesta(respuesta_renaper()))
        _, llamada = self.consultar(_Respuesta(respuesta_renaper()))
        self.assertEqual(llamada.call_count, 1)  # sin login

        renaper._sesion._vence = timezone.now() + timedelta(seconds=30)  # dentro del margen
        _, llamada = self.consultar(_Respuesta(LOGIN), _Respuesta(respuesta_renaper()))
        self.assertEqual(llamada.call_count, 2)

    def test_sin_vencimiento_informado_lo_renueva_pronto(self):
        self.consultar(_Respuesta({"token": "token-de-prueba"}), _Respuesta(respuesta_renaper()))
        self.assertLessEqual(renaper._sesion._vence, timezone.now() + timedelta(minutes=5))

    def test_un_token_rechazado_se_renueva_una_sola_vez(self):
        resultado, llamada = self.consultar(
            _Respuesta(LOGIN), _http(401), _Respuesta(LOGIN), _Respuesta(respuesta_renaper())
        )
        self.assertTrue(resultado.coincide)
        self.assertEqual(llamada.call_count, 4)

        with self.assertLogs("apps.portal.renaper", "ERROR"), self.assertRaises(renaper.RenaperNoDisponible):
            self.consultar(_http(403), _Respuesta(LOGIN), _http(401))

    def test_404_es_dni_inexistente_y_cuenta_como_intento(self):
        resultado, _ = self.consultar(_Respuesta(LOGIN), _http(404))
        self.assertEqual((resultado.coincide, resultado.motivo), (False, "no_encontrado"))

    def test_las_fallas_tecnicas_son_no_disponible_y_no_filtran_datos_al_log(self):
        fallas = {
            "login rechazado": [_http(401)],
            "login sin token": [_Respuesta({"error": "x"})],
            "login caído": [URLError("sin ruta")],
            "consulta 5xx": [_Respuesta(LOGIN), _http(503)],
            "consulta timeout": [_Respuesta(LOGIN), TimeoutError()],
            "no es json": [_Respuesta(LOGIN), _Respuesta(b"<html>")],
            "demasiado grande": [_Respuesta(LOGIN), _Respuesta(b"{" + b" " * renaper.TOPE_RESPUESTA + b"}")],
        }
        for nombre, respuestas in fallas.items():
            renaper._sesion.olvidar()
            with self.subTest(falla=nombre), self.assertLogs("apps.portal.renaper", "ERROR") as logs, \
                    self.assertRaises(renaper.RenaperNoDisponible):
                self.consultar(*respuestas)
            texto = "\n".join(logs.output)
            for dato in DATOS_SENSIBLES:
                self.assertNotIn(dato, texto)

    def test_sin_configurar_falla_cerrado_sin_consultar(self):
        for faltante in ({"RENAPER_URL": ""}, {"RENAPER_USUARIO": ""}, {"RENAPER_CLAVE": ""}):
            with self.subTest(faltante=faltante), override_settings(**faltante), \
                    mock.patch("apps.portal.renaper.urlopen") as llamada, \
                    self.assertLogs("apps.portal.renaper", "ERROR"), self.assertRaises(renaper.RenaperNoDisponible):
                renaper.Real().cotejar(COTEJO)
            llamada.assert_not_called()

    def test_en_produccion_exige_https(self):
        with override_settings(RENAPER_URL="http://renaper.test/api"), \
                mock.patch("apps.portal.renaper.urlopen") as llamada, \
                self.assertLogs("apps.portal.renaper", "ERROR"), self.assertRaises(renaper.RenaperNoDisponible):
            renaper.Real().cotejar(COTEJO)
        llamada.assert_not_called()


@override_settings(**SIMULADO)
class ValidacionConLaRespuestaRealTests(Base):
    def test_el_rechazo_se_audita_con_su_motivo_y_el_paciente_ve_siempre_lo_mismo(self):
        cuenta = self.cuenta()
        cliente = self.cliente(cuenta)
        respuestas = {}
        for tramite, motivo in (("00000000000", "no_encontrado"), ("11111111111", "aviso_fallecimiento")):
            r = self.post("cuenta/validar-identidad/", {**DNI, "numero_tramite": tramite}, cliente)
            respuestas[motivo] = (r.status_code, r.data["codigo"], r.data["detail"])
            self.assertTrue(
                EventoPortal.objects.filter(tipo="identidad_rechazada", detalle__motivo=motivo).exists()
            )
        self.assertEqual(respuestas["no_encontrado"], respuestas["aviso_fallecimiento"])

    def test_no_se_guarda_nada_de_la_respuesta_salvo_nombre_apellido_y_nacimiento(self):
        cuenta = self.cuenta()
        r = self.post("cuenta/validar-identidad/", DNI, self.cliente(cuenta))
        self.assertEqual(r.status_code, 200)
        evento = EventoPortal.objects.get(tipo="identidad_validada")
        self.assertEqual(set(evento.detalle), {"documento", "sexo", "via"})

    def test_la_marca_de_consulta_en_curso_supera_el_timeout(self):
        from .views import _consulta_en_curso_segundos

        with override_settings(RENAPER_TIMEOUT=40):
            self.assertGreater(_consulta_en_curso_segundos(), 40)


class FormatoDeNombresTests(APITestCase):
    """RENAPER manda los nombres en mayúsculas y, a veces, con el encoding roto."""

    def test_primera_mayuscula_y_el_resto_minuscula(self):
        casos = {
            "OCHOA": "Ochoa",
            "JULIAN DAMIAN": "Julian Damian",
            "  DE   LOS  SANTOS ": "De Los Santos",
            "ÁLVAREZ ÑANDÚ": "Álvarez Ñandú",
            "D'ANGELO": "D'Angelo",
            "PÉREZ-GARCÍA": "Pérez-García",
            "MARÍA_JOSÉ": "María José",
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(renaper.formatear_nombre(crudo), esperado)

    def test_tildes_en_minuscula_dentro_de_mayusculas(self):
        self.assertEqual(renaper.formatear_nombre("SáENZ PEñA"), "Sáenz Peña")

    def test_tilde_como_caracter_aparte(self):
        crudo = unicodedata.normalize("NFD", "JOSÉ MARÍA")
        self.assertEqual(renaper.formatear_nombre(crudo), "José María")

    def test_utf8_leido_como_latin1_o_windows1252(self):
        casos = {"PÃ‰REZ": "Pérez", "MUÃ‘OZ": "Muñoz", "GARC\u00c3\u008dA": "García", "PÃƒÂ©REZ": "Pérez"}
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(renaper.formatear_nombre(crudo), esperado)

    def test_una_a_con_tilde_legitima_no_se_toca(self):
        self.assertEqual(renaper.formatear_nombre("JOÃO"), "João")

    def test_una_letra_perdida_no_corta_la_palabra_y_se_avisa_sin_el_nombre(self):
        with self.assertLogs("apps.portal.renaper", "WARNING") as logs:
            self.assertEqual(renaper.formatear_nombre("GARC\ufffdA"), "Garc\ufffda")
        self.assertNotIn("GARC", "\n".join(logs.output))

    def test_la_validacion_guarda_el_nombre_formateado(self):
        r = renaper.interpretar(respuesta_renaper(apellido="PÃ‰REZ", nombres="ANA MARíA"), COTEJO)
        self.assertEqual((r.nombre, r.apellido), ("Ana María", "Pérez"))
