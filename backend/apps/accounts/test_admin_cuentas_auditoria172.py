"""Django Admin de cuentas y cookies fuera de la API (#172, decisiones D-a/D-b).

El titular administra sus credenciales: el Admin no fija contraseña ni email ni
otorga privilegios. La recuperación excepcional sale como enlace al titular.
La cookie de sesión del Admin no autentica en la API.
"""
from io import StringIO

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.simulacion.perfiles import DOMINIO

from .models import CorreoInstitucionalOutbox, Usuario
from .test_credenciales_auditoria172 import CONFIGURACION

CLAVE = "Clave-ficticia-admin-172!"


class AdminCuentasAuditoria172Tests(TestCase):
    def setUp(self):
        self.root = Usuario.objects.create_superuser("root-admin@example.test", CLAVE, nombre="Root")
        self.titular = Usuario.objects.create_user("titular-admin@example.test", CLAVE, nombre="Titular")
        self.url = f"/admin/accounts/usuario/{self.titular.pk}/change/"

    def datos(self, **extra):
        return {
            "nombre": "Titular", "apellido": "Editado", "is_active": "on",
            "membresias-TOTAL_FORMS": "0", "membresias-INITIAL_FORMS": "0",
            "membresias-MIN_NUM_FORMS": "0", "membresias-MAX_NUM_FORMS": "1000",
            "_save": "Guardar", **extra,
        }

    def test_formulario_no_expone_credenciales_ni_privilegios(self):
        self.client.force_login(self.root)
        pagina = self.client.get(self.url)
        self.assertEqual(pagina.status_code, 200)
        editables = set(pagina.context["adminform"].form.fields)
        self.assertEqual(editables & {"password", "email", "is_staff", "is_superuser", "groups", "user_permissions"}, set())
        self.assertIn("is_active", editables)

    def test_post_con_credenciales_y_privilegios_solo_aplica_datos_permitidos(self):
        self.client.force_login(self.root)
        respuesta = self.client.post(self.url, self.datos(
            email="otro-destino@example.test", password="Elegida-por-admin-172!",
            password1="Elegida-por-admin-172!", password2="Elegida-por-admin-172!",
            is_staff="on", is_superuser="on",
        ))
        self.assertEqual(respuesta.status_code, 302)
        self.titular.refresh_from_db()
        self.assertEqual(self.titular.apellido, "Editado")
        self.assertEqual(self.titular.email, "titular-admin@example.test")
        self.assertTrue(self.titular.check_password(CLAVE))
        self.assertFalse(self.titular.is_staff)
        self.assertFalse(self.titular.is_superuser)

    def test_cambio_de_contrasena_y_alta_por_admin_rechazados(self):
        self.client.force_login(self.root)
        url = f"/admin/accounts/usuario/{self.titular.pk}/password/"
        self.assertEqual(self.client.get(url).status_code, 403)
        respuesta = self.client.post(url, {"password1": "Elegida-por-admin-172!", "password2": "Elegida-por-admin-172!"})
        self.assertEqual(respuesta.status_code, 403)
        self.titular.refresh_from_db()
        self.assertTrue(self.titular.check_password(CLAVE))
        self.assertEqual(self.client.get("/admin/accounts/usuario/add/").status_code, 403)

    def test_staff_sin_superusuario_no_modifica_a_un_superusuario(self):
        staff = Usuario.objects.create_user("staff-admin@example.test", CLAVE, nombre="Staff", is_staff=True)
        staff.user_permissions.add(*Permission.objects.filter(codename__in=["view_usuario", "change_usuario"]))
        self.client.force_login(staff)
        respuesta = self.client.post(f"/admin/accounts/usuario/{self.root.pk}/change/", self.datos(nombre="Root", is_active=""))
        self.assertEqual(respuesta.status_code, 403)
        self.root.refresh_from_db()
        self.assertTrue(self.root.is_active)
        # Una cuenta común sigue administrable en sus datos permitidos.
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, 302)

    @override_settings(**CONFIGURACION)
    def test_accion_envia_recuperacion_al_titular_sin_tocar_la_contrasena(self):
        self.client.force_login(self.root)
        respuesta = self.client.post("/admin/accounts/usuario/", {
            "action": "iniciar_recuperacion", "_selected_action": [str(self.titular.pk)],
        }, follow=True)
        mensajes = [str(m) for m in respuesta.context["messages"]]
        self.assertEqual(mensajes, ["Recuperación solicitada para 1 titular(es)."])
        solicitud = CorreoInstitucionalOutbox.objects.get()
        self.assertEqual(solicitud.solicitud["tipo"], "recuperacion")
        self.assertEqual(solicitud.solicitud["usuario_id"], self.titular.pk)
        self.assertEqual(solicitud.solicitud["actor_id"], self.root.pk)
        self.titular.refresh_from_db()
        self.assertTrue(self.titular.check_password(CLAVE))

    @override_settings(INSTITUCIONAL_CORREO_MODO="", INSTITUCIONAL_URL_BASE="")
    def test_accion_sin_correo_configurado_no_acepta_solicitudes(self):
        self.client.force_login(self.root)
        respuesta = self.client.post("/admin/accounts/usuario/", {
            "action": "iniciar_recuperacion", "_selected_action": [str(self.titular.pk)],
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(CorreoInstitucionalOutbox.objects.exists())
        self.assertContains(respuesta, "no está disponible")

    def test_la_cookie_del_admin_no_autentica_en_la_api(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        self.assertEqual(self.client.get("/api/usuarios/me/").status_code, 401)
        self.assertEqual(self.client.get("/api/instituciones/").status_code, 401)


class AsignarPrivilegiosAuditoria172Tests(TestCase):
    def setUp(self):
        self.root = Usuario.objects.create_superuser("responsable@example.test", CLAVE, nombre="Responsable")
        self.titular = Usuario.objects.create_user("titular-priv@example.test", CLAVE, nombre="Titular")

    def asignar(self, **opciones):
        salida = StringIO()
        call_command("asignar_privilegios", stdout=salida, **opciones)
        return salida.getvalue()

    def test_otorga_superusuario_con_staff_y_deja_registro(self):
        self.asignar(email="TITULAR-PRIV@example.test", responsable=self.root.email,
                     motivo="Guardia de plataforma sintética", superusuario="si")
        self.titular.refresh_from_db()
        self.assertTrue(self.titular.is_superuser)
        self.assertTrue(self.titular.is_staff)
        self.assertTrue(self.titular.check_password(CLAVE))
        registro = LogEntry.objects.get(object_id=str(self.titular.pk))
        self.assertEqual(registro.user_id, self.root.pk)
        self.assertIn("is_superuser: False→True", registro.change_message)
        self.assertIn("Guardia de plataforma sintética", registro.change_message)

    def test_retira_privilegios_y_no_repite_registro_sin_cambios(self):
        self.titular.is_staff = True
        self.titular.save(update_fields=["is_staff"])
        self.asignar(email=self.titular.email, responsable=self.root.email, motivo="Baja", staff="no")
        self.titular.refresh_from_db()
        self.assertFalse(self.titular.is_staff)
        self.assertIn("Sin cambios", self.asignar(email=self.titular.email, responsable=self.root.email, motivo="Baja", staff="no"))
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_rechazos_no_modifican_ni_registran(self):
        comun = Usuario.objects.create_user("no-super@example.test", CLAVE, nombre="Común")
        referencia = Usuario.objects.create_user(f"medico@{DOMINIO}", None, nombre="Referencia")
        casos = [
            {"email": self.titular.email, "responsable": comun.email, "motivo": "x", "staff": "si"},
            {"email": self.titular.email, "responsable": self.root.email, "motivo": "  ", "staff": "si"},
            {"email": self.titular.email, "responsable": self.root.email, "motivo": "x"},
            {"email": "inexistente@example.test", "responsable": self.root.email, "motivo": "x", "staff": "si"},
            {"email": referencia.email, "responsable": self.root.email, "motivo": "x", "staff": "si"},
            {"email": self.root.email, "responsable": self.root.email, "motivo": "x", "superusuario": "no"},
        ]
        for opciones in casos:
            with self.subTest(opciones=opciones), self.assertRaises(CommandError):
                self.asignar(**opciones)
        self.titular.refresh_from_db()
        self.root.refresh_from_db()
        self.assertFalse(self.titular.is_staff)
        self.assertTrue(self.root.is_superuser)
        self.assertFalse(LogEntry.objects.exists())
