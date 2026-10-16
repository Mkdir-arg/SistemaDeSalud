"""Retiro institucional durable A/B (#172, decisión D-c).

Una baja en A cierra A para las sesiones abiertas antes de la baja, aunque
después se reactive; B y otros usuarios no cambian. Se usa login JWT real:
`force_authenticate` no pasa por el autenticador que fija el corte.
"""
from django.core.cache import caches
from rest_framework.test import APIClient, APITestCase

from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

from .models import BajaMembresia, Membresia, Usuario

CLAVE = "Clave-sintetica-retiro-172!"


class RetiroInstitucionalAuditoria172Tests(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.a = Institucion.objects.create(nombre="Institución A sintética")
        self.b = Institucion.objects.create(nombre="Institución B sintética")
        self.usuario = Usuario.objects.create_user("retiro@example.test", CLAVE, nombre="Persona")
        self.en_a = Membresia.objects.create(usuario=self.usuario, institucion=self.a, rol=Membresia.Rol.ADMINISTRATIVO)
        Membresia.objects.create(usuario=self.usuario, institucion=self.b, rol=Membresia.Rol.ADMINISTRATIVO)
        self.admin_a = Usuario.objects.create_user("admin-a-retiro@example.test", CLAVE, nombre="Admin A")
        Membresia.objects.create(usuario=self.admin_a, institucion=self.a, rol=Membresia.Rol.ADMIN_INSTITUCION)
        Ciudadano.objects.create(institucion=self.a, nombre="Paciente A sintético")
        Ciudadano.objects.create(institucion=self.b, nombre="Paciente B sintético")
        self.client = APIClient()

    def login(self, usuario=None):
        respuesta = self.client.post("/api/auth/token/", {
            "email": (usuario or self.usuario).email, "password": CLAVE,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        return dict(respuesta.data)

    def get(self, par, ruta):
        return self.client.get(ruta, HTTP_AUTHORIZATION=f"Bearer {par['access']}")

    def instituciones(self, par):
        respuesta = self.get(par, "/api/usuarios/me/")
        self.assertEqual(respuesta.status_code, 200)
        return set(respuesta.data["roles_por_institucion"])

    def pacientes(self, par):
        respuesta = self.get(par, "/api/ciudadanos/")
        self.assertEqual(respuesta.status_code, 200)
        return {fila["nombre"] for fila in respuesta.data["results"]}

    def patch_membresia(self, par, membresia, datos):
        return self.client.patch(f"/api/membresias/{membresia.pk}/", datos, format="json",
                                 HTTP_AUTHORIZATION=f"Bearer {par['access']}")

    def test_reactivar_a_no_rehabilita_la_sesion_anterior_y_b_sigue_disponible(self):
        sesion = self.login()
        admin = self.login(self.admin_a)
        ambas = {str(self.a.pk), str(self.b.pk)}
        self.assertEqual(self.instituciones(sesion), ambas)
        self.assertEqual(self.pacientes(sesion), {"Paciente A sintético", "Paciente B sintético"})

        self.assertEqual(self.patch_membresia(admin, self.en_a, {"activo": False}).status_code, 200)
        self.assertEqual(BajaMembresia.objects.filter(usuario=self.usuario, institucion=self.a).count(), 1)
        self.assertEqual(self.instituciones(sesion), {str(self.b.pk)})

        self.assertEqual(self.patch_membresia(admin, self.en_a, {"activo": True}).status_code, 200)
        self.assertEqual(self.instituciones(sesion), {str(self.b.pk)})
        self.assertEqual(self.pacientes(sesion), {"Paciente B sintético"})

        # Renovar conserva la misma sesión: no recupera A.
        renovada = self.client.post("/api/auth/token/refresh/", {"refresh": sesion["refresh"]}, format="json")
        self.assertEqual(renovada.status_code, 200)
        self.assertEqual(self.instituciones(dict(renovada.data)), {str(self.b.pk)})

        # Un login nuevo vuelve a ver A; el admin de A nunca perdió su acceso.
        nueva = self.login()
        self.assertEqual(self.instituciones(nueva), ambas)
        self.assertEqual(self.pacientes(nueva), {"Paciente A sintético", "Paciente B sintético"})
        self.assertEqual(self.instituciones(admin), {str(self.a.pk)})

    def test_borrar_y_recrear_o_cambiar_rol_tambien_cortan_a(self):
        sesion = self.login()
        self.en_a.delete()
        Membresia.objects.create(usuario=self.usuario, institucion=self.a, rol=Membresia.Rol.ADMINISTRATIVO)
        self.assertEqual(self.instituciones(sesion), {str(self.b.pk)})

        otra = self.login()
        membresia = Membresia.objects.get(usuario=self.usuario, institucion=self.a)
        membresia.rol = Membresia.Rol.ENFERMERIA
        membresia.save()
        self.assertEqual(self.instituciones(otra), {str(self.b.pk)})
        self.assertEqual(self.instituciones(self.login()), {str(self.a.pk), str(self.b.pk)})

    def test_baja_de_rol_global_corta_el_alcance_global(self):
        plataforma = Membresia.objects.create(usuario=self.usuario, institucion=None, rol=Membresia.Rol.PLATAFORMA)
        sesion = self.login()
        self.assertIn("global", self.instituciones(sesion))
        plataforma.activo = False
        plataforma.save()
        plataforma.activo = True
        plataforma.save()
        self.assertNotIn("global", self.instituciones(sesion))
        self.assertEqual(self.instituciones(sesion), {str(self.a.pk), str(self.b.pk)})
        self.assertIn("global", self.instituciones(self.login()))

    def test_baja_anterior_al_login_no_corta_y_el_corte_no_sale_de_la_solicitud(self):
        self.en_a.activo = False
        self.en_a.save()
        self.en_a.activo = True
        self.en_a.save()
        sesion = self.login()
        self.assertEqual(self.instituciones(sesion), {str(self.a.pk), str(self.b.pk)})

        self.en_a.activo = False
        self.en_a.save()
        self.en_a.activo = True
        self.en_a.save()
        self.assertEqual(self.instituciones(sesion), {str(self.b.pk)})
        # Fuera de una solicitud (worker, comando) no queda corte aplicado.
        self.assertEqual(Membresia.objects.filter(usuario=self.usuario, activo=True).count(), 2)

    def test_borrar_la_identidad_no_registra_bajas_huerfanas(self):
        self.login()
        self.usuario.delete()
        self.assertFalse(BajaMembresia.objects.exists())
        self.assertFalse(Membresia.objects.filter(institucion=self.a, rol=Membresia.Rol.ADMINISTRATIVO).exists())
