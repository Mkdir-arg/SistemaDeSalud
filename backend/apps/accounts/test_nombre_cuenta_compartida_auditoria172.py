"""Nombre y apellido de una cuenta compartida entre instituciones (#172).

Si la cuenta tiene una pertenencia activa en una institución que el actor no
administra, un admin institucional no cambia su nombre ni su apellido. Sí el
titular, el superusuario y el gobierno de plataforma.
"""
from rest_framework.test import APITestCase

from apps.instituciones.models import Institucion

from .models import Membresia, Usuario

Rol = Membresia.Rol


class NombreCuentaCompartidaTests(APITestCase):
    def setUp(self):
        self.a = Institucion.objects.create(nombre="Hospital A")
        self.b = Institucion.objects.create(nombre="Clinica B")
        self.base = Institucion.objects.create(nombre="Direccion provincial")
        self.admin_a = self.persona("admin-a@test.local", (self.a, Rol.ADMIN_INSTITUCION))
        self.solo_a = self.persona("solo-a@test.local", (self.a, Rol.MEDICO))
        self.compartida = self.persona("compartida@test.local", (self.a, Rol.MEDICO), (self.b, Rol.MEDICO))

    def persona(self, email, *pertenencias, **extra):
        usuario = Usuario.objects.create_user(email, "x", nombre="Nombre", apellido="Apellido", **extra)
        for institucion, rol in pertenencias:
            Membresia.objects.create(usuario=usuario, institucion=institucion, rol=rol, activo=True)
        return usuario

    def editar(self, actor, objetivo, **datos):
        self.client.force_authenticate(actor)
        return self.client.patch(f"/api/usuarios/{objetivo.pk}/", datos, format="json")

    def assertSinCambios(self, usuario):
        usuario.refresh_from_db()
        self.assertEqual((usuario.nombre, usuario.apellido), ("Nombre", "Apellido"))

    # --- Cuenta no compartida (A) ------------------------------------------
    def test_admin_cambia_nombre_de_cuenta_solo_de_su_institucion(self):
        r = self.editar(self.admin_a, self.solo_a, nombre="Nuevo", apellido="Otro")
        self.assertEqual(r.status_code, 200, r.data)
        self.solo_a.refresh_from_db()
        self.assertEqual((self.solo_a.nombre, self.solo_a.apellido), ("Nuevo", "Otro"))

    def test_pertenencia_inactiva_en_otra_institucion_no_la_vuelve_compartida(self):
        Membresia.objects.filter(usuario=self.compartida, institucion=self.b).update(activo=False)
        r = self.editar(self.admin_a, self.compartida, apellido="Otro")
        self.assertEqual(r.status_code, 200, r.data)

    # --- Cuenta compartida (B) ---------------------------------------------
    def test_admin_no_cambia_nombre_ni_apellido_de_cuenta_compartida(self):
        for datos in ({"nombre": "Pisado"}, {"apellido": "Pisado"}):
            with self.subTest(**datos):
                r = self.editar(self.admin_a, self.compartida, **datos)
                self.assertEqual(r.status_code, 403)
                self.assertIn("otra institución", str(r.data["detail"]))
                self.assertSinCambios(self.compartida)

    def test_rechazo_no_aplica_cambio_parcial(self):
        r = self.editar(self.admin_a, self.compartida, nombre="Nombre", apellido="Pisado")
        self.assertEqual(r.status_code, 403)
        self.assertSinCambios(self.compartida)

    def test_mismos_valores_no_cuentan_como_cambio(self):
        # La pantalla de Directorio manda nombre y apellido siempre.
        r = self.editar(self.admin_a, self.compartida, nombre="Nombre", apellido="Apellido")
        self.assertEqual(r.status_code, 200, r.data)

    def test_pertenencia_global_tambien_vuelve_compartida_la_cuenta(self):
        Membresia.objects.create(usuario=self.solo_a, institucion=None, rol=Rol.AUDITOR, activo=True)
        r = self.editar(self.admin_a, self.solo_a, nombre="Pisado")
        self.assertEqual(r.status_code, 403)
        self.assertSinCambios(self.solo_a)

    def test_admin_de_ambas_instituciones_si_puede(self):
        Membresia.objects.create(usuario=self.admin_a, institucion=self.b, rol=Rol.ADMIN_INSTITUCION)
        r = self.editar(self.admin_a, self.compartida, nombre="Nuevo")
        self.assertEqual(r.status_code, 200, r.data)

    def test_gobierno_de_plataforma_y_superusuario_si_pueden(self):
        plataforma = self.persona("plataforma@test.local", (self.base, Rol.PLATAFORMA))
        superusuario = Usuario.objects.create_superuser("super@test.local", "x")
        for actor, nombre in ((plataforma, "Por plataforma"), (superusuario, "Por superusuario")):
            with self.subTest(actor=actor.email):
                r = self.editar(actor, self.compartida, nombre=nombre)
                self.assertEqual(r.status_code, 200, r.data)
                self.compartida.refresh_from_db()
                self.assertEqual(self.compartida.nombre, nombre)

    def test_titular_admin_cambia_su_propio_nombre_aunque_tenga_otra_pertenencia(self):
        Membresia.objects.create(usuario=self.admin_a, institucion=self.b, rol=Rol.MEDICO)
        r = self.editar(self.admin_a, self.admin_a, nombre="Propio")
        self.assertEqual(r.status_code, 200, r.data)
