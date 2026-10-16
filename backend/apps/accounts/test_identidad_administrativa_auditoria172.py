"""AUD-001: administración de pertenencias separada de credenciales globales."""
from unittest.mock import patch

from django.core.cache import caches
from django.test import override_settings

from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from apps.instituciones.models import Institucion

from .models import CorreoInstitucionalOutbox, Membresia, Usuario
from .test_credenciales_auditoria172 import CONFIGURACION


@override_settings(**CONFIGURACION)
class IdentidadAdministrativaTests(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.a = Institucion.objects.create(nombre="Administrada A")
        self.b = Institucion.objects.create(nombre="Membresía B")
        self.admin = Usuario.objects.create_user("admin-mixto@test.local", "x")
        Membresia.objects.create(usuario=self.admin, institucion=self.a, rol=Membresia.Rol.ADMIN_INSTITUCION)
        Membresia.objects.create(usuario=self.admin, institucion=self.b, rol=Membresia.Rol.MEDICO)
        self.persona = Usuario.objects.create_user("compartida@test.local", "original")
        Membresia.objects.create(usuario=self.persona, institucion=self.a, rol=Membresia.Rol.MEDICO)
        Membresia.objects.create(usuario=self.persona, institucion=self.b, rol=Membresia.Rol.MEDICO)
        self.ajena = Usuario.objects.create_user("solo-b@test.local", "original")
        Membresia.objects.create(usuario=self.ajena, institucion=self.b, rol=Membresia.Rol.MEDICO)
        self.root = Usuario.objects.create_superuser("root-identidad@test.local", "original")
        self.client.force_authenticate(self.admin)

    def alta(self, **extra):
        return self.client.post("/api/usuarios/", {
            "email": "invitada@test.local", "nombre": "Invitada",
            "institucion": self.a.pk, "rol": Membresia.Rol.MEDICO, **extra,
        }, format="json")

    @override_settings(INSTITUCIONAL_CORREO_MODO="")
    def test_sin_configuracion_medico_no_administra_y_lectura_propia_sigue_disponible(self):
        self.client.force_authenticate(self.persona)
        for url, datos, esperado in (("/api/usuarios/", {"email": "invitada@test.local", "institucion": self.a.pk}, 403),
                                     (f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {}, 404)):
            with self.subTest(url=url):
                respuesta = self.client.post(url, datos, format="json")
                self.assertEqual(respuesta.status_code, esperado, respuesta.data)
        respuesta = self.client.get("/api/usuarios/me/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())

    @override_settings(INSTITUCIONAL_CORREO_MODO="", INSTITUCIONAL_THROTTLE_RATES={})
    def test_admin_sin_configuracion_recibe_503_antes_de_throttle_sin_crear_ni_encolar(self):
        miembros_antes = Membresia.objects.count()
        respuesta = self.alta()
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        respuesta = self.client.post(f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())
        self.assertEqual(Membresia.objects.count(), miembros_antes)
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())

    @patch("apps.accounts.views.invitar_usuario", create=True)
    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_alta_invita_sin_clave_administrativa_y_crea_pertenencia(self, configurar, invitar):
        respuesta = self.alta()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        usuario = Usuario.objects.get(pk=respuesta.data["id"])
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(usuario.membresias.filter(institucion=self.a, activo=True).exists())
        configurar.assert_called_once()
        invitar.assert_called_once()
        self.assertEqual(invitar.call_args.args[0], usuario)
        self.assertNotIn("password", respuesta.data)
        self.assertNotIn("token", respuesta.data)

    @patch("apps.accounts.views.invitar_usuario", create=True)
    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_admin_no_elige_clave_ni_privilegios_en_alta(self, configurar, invitar):
        for campo, valor in (("password", "Guardia-Diente-84"), ("is_active", False),
                             ("is_staff", True), ("is_superuser", True)):
            with self.subTest(campo=campo):
                respuesta = self.alta(**{campo: valor})
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())
        invitar.assert_not_called()

    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_correo_no_configurado_no_deja_identidad_ni_membresia(self, configurar):
        configurar.side_effect = ValidationError({"detail": "Configurar correo institucional."})
        respuesta = self.alta()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())

    @patch("apps.accounts.views.invitar_usuario", create=True)
    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_admin_a_miembro_b_no_crea_en_b(self, configurar, invitar):
        respuesta = self.alta(institucion=self.b.pk)
        self.assertIn(respuesta.status_code, (400, 403))
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())
        invitar.assert_not_called()

    @patch("apps.accounts.views.invitar_usuario", create=True)
    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_alta_sin_institucion_usa_unica_administrada_no_todas_las_membresias(self, configurar, invitar):
        respuesta = self.client.post("/api/usuarios/", {
            "email": "invitada@test.local", "nombre": "Invitada",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Membresia.objects.get(usuario_id=respuesta.data["id"]).institucion_id, self.a.pk)

    @patch("apps.accounts.views.invitar_usuario", create=True)
    @patch("apps.accounts.views.exigir_configuracion_correo", create=True)
    def test_fallo_preparando_invitacion_revierte_identidad_y_pertenencia(self, configurar, invitar):
        invitar.side_effect = ValidationError({"detail": "Invitación no disponible."})
        respuesta = self.alta()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())

    def test_simulacion_no_puede_crear_identidad(self):
        from .views import UsuarioViewSet

        request = APIRequestFactory().post("/api/usuarios/", {
            "email": "invitada@test.local", "nombre": "Invitada", "institucion": self.a.pk,
        }, format="json")
        request.simulacion = object()
        force_authenticate(request, user=self.admin)
        respuesta = UsuarioViewSet.as_view({"post": "create"})(request)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(Usuario.objects.filter(email="invitada@test.local").exists())

    def test_mutacion_administrativa_no_toca_credenciales_estado_o_privilegios(self):
        original = (self.persona.email, self.persona.password, self.persona.is_active, self.persona.nombre)
        for actor in (self.admin, self.root):
            self.client.force_authenticate(actor)
            for campo, valor in (("email", "otra@test.local"), ("password", "Guardia-Diente-84"),
                                 ("is_active", False), ("is_staff", True), ("is_superuser", True)):
                with self.subTest(actor=actor.pk, campo=campo):
                    respuesta = self.client.patch(f"/api/usuarios/{self.persona.pk}/", {
                        campo: valor, "nombre": "No aplicar parcialmente",
                    }, format="json")
                    self.assertEqual(respuesta.status_code, 400, respuesta.data)
                    self.persona.refresh_from_db()
                    self.assertEqual((self.persona.email, self.persona.password,
                                      self.persona.is_active, self.persona.nombre), original)
                    self.assertFalse(self.persona.is_staff)
                    self.assertFalse(self.persona.is_superuser)

    def test_put_tampoco_permite_cambiar_email(self):
        respuesta = self.client.put(f"/api/usuarios/{self.persona.pk}/", {
            "email": "reemplazo@test.local", "nombre": "Reemplazo",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.persona.refresh_from_db()
        self.assertEqual(self.persona.email, "compartida@test.local")

    def test_admin_institucional_no_borra_identidad_global(self):
        respuesta = self.client.delete(f"/api/usuarios/{self.persona.pk}/")
        self.assertEqual(respuesta.status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=self.persona.pk).exists())
        self.assertEqual(self.persona.membresias.count(), 2)

    @patch("apps.accounts.views.solicitar_recuperacion", return_value=True, create=True)
    def test_recuperacion_administrativa_no_suma_capacidad_a_con_pertenencia_b(self, recuperar):
        respuesta = self.client.post(f"/api/usuarios/{self.ajena.pk}/iniciar-recuperacion/", {}, format="json")
        self.assertEqual(respuesta.status_code, 404)
        recuperar.assert_not_called()

    @patch("apps.accounts.views.solicitar_recuperacion", return_value=True, create=True)
    def test_admin_inicia_recuperacion_sin_recibir_token(self, recuperar):
        respuesta = self.client.post(f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {}, format="json")
        self.assertEqual(respuesta.status_code, 202, getattr(respuesta, "data", None))
        recuperar.assert_called_once()
        self.assertEqual(recuperar.call_args.args[0], self.persona)
        self.assertEqual(recuperar.call_args.kwargs["actor"], self.admin)
        self.assertNotIn("token", respuesta.data)

    @patch("apps.accounts.views.solicitar_recuperacion", create=True)
    def test_recuperacion_no_admite_elegir_destino(self, recuperar):
        respuesta = self.client.post(f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {
            "email": "atacante@test.local",
        }, format="json")
        self.assertEqual(respuesta.status_code, 400)
        recuperar.assert_not_called()

    def test_baja_local_conserva_identidad_y_pertenencia_b(self):
        membresia = self.persona.membresias.get(institucion=self.a)
        respuesta = self.client.patch(f"/api/membresias/{membresia.pk}/", {"activo": False}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.persona.refresh_from_db()
        self.assertTrue(self.persona.is_active)
        self.assertTrue(self.persona.membresias.get(institucion=self.b).activo)

    def test_recuperacion_administrativa_respeta_cupo_destinatario_compartido_con_publica(self):
        with override_settings(
            INSTITUCIONAL_THROTTLE_RATES={"ip": "100/hour", "email": "1/hour", "usuario": "100/hour"},
        ):
            with self.captureOnCommitCallbacks(execute=True):
                respuesta = self.client.post(
                    f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {}, format="json",
                )
            self.assertEqual(respuesta.status_code, 202, respuesta.data)
            self.assertEqual(CorreoInstitucionalOutbox.objects.count(), 1)
            respuesta = self.client.post(
                f"/api/usuarios/{self.persona.pk}/iniciar-recuperacion/", {}, format="json",
            )
            self.assertEqual(respuesta.status_code, 429)
            self.client.force_authenticate(None)
            respuesta = self.client.post("/api/auth/recuperacion/", {"email": self.persona.email}, format="json")
            self.assertEqual(respuesta.status_code, 429)
            self.assertEqual(CorreoInstitucionalOutbox.objects.count(), 1)

    def test_alta_no_duplica_email_con_otra_capitalizacion(self):
        respuesta = self.alta(email=self.persona.email.upper())
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(Usuario.objects.filter(email__iexact=self.persona.email).count(), 1)
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())

    def test_publicos_no_exigen_jwt_valido_y_privados_si(self):
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer jwt-ficticio-invalido")
        for accion, datos, esperado in (
            ("recuperacion", {"email": self.persona.email}, 202),
            ("restablecer", {"uid": "invalid", "token": "invalid", "nueva_password": "Clave-nueva-ficticia-172"}, 400),
            ("confirmar-email", {"uid": "invalid", "token": "invalid", "nuevo_email": "otro@test.local"}, 400),
            ("cambiar-password", {"password_actual": "x", "nueva_password": "Clave-nueva-ficticia-172"}, 401),
            ("cambio-email", {"password_actual": "x", "nuevo_email": "otro@test.local"}, 401),
        ):
            with self.subTest(accion=accion):
                respuesta = self.client.post(f"/api/auth/{accion}/", datos, format="json")
                self.assertEqual(respuesta.status_code, esperado, getattr(respuesta, "data", None))
