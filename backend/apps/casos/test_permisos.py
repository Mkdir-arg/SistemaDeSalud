"""Autorización por rol en la API (Capa 1 de docs/ROLES-Y-PERMISOS.md).

Verifica que la escritura se gatee por la capacidad del rol y que la lectura
quede abierta a cualquier miembro de la institución.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion


class PermisosPorRolTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inst = Institucion.objects.create(nombre="Hospital Test", tipo="Hospital")
        cls.area = Area.objects.create(institucion=cls.inst, nombre="Guardia")
        R = Membresia.Rol
        cls.admin = cls._miembro("admin@test.local", R.ADMIN_INSTITUCION)
        cls.conf = cls._miembro("conf@test.local", R.CONFIGURADOR)
        cls.adm = cls._miembro("adm@test.local", R.ADMINISTRATIVO)
        cls.med = cls._miembro("med@test.local", R.MEDICO)
        cls.root = Usuario.objects.create_superuser(email="root@test.local", password="x", nombre="Root")

    @classmethod
    def _miembro(cls, email, rol):
        u = Usuario.objects.create_user(email=email, password="x", nombre="N")
        m = Membresia.objects.create(usuario=u, institucion=cls.inst, rol=rol)
        m.areas.add(cls.area)
        return u

    def _post(self, user, url, data):
        self.client.force_authenticate(user)
        return self.client.post(url, data).status_code

    # --- Diseño (flujos) ---------------------------------------------------
    def test_configurador_puede_crear_flujo(self):
        self.assertEqual(self._post(self.conf, "/api/flujos/", {"institucion": self.inst.id, "titulo": "F", "area": self.area.id}), 201)

    def test_administrativo_no_puede_crear_flujo(self):
        self.assertEqual(self._post(self.adm, "/api/flujos/", {"institucion": self.inst.id, "titulo": "F"}), 403)

    def test_medico_no_puede_crear_flujo(self):
        self.assertEqual(self._post(self.med, "/api/flujos/", {"institucion": self.inst.id, "titulo": "F"}), 403)

    # --- Estructura (áreas, config) ---------------------------------------
    def test_medico_no_puede_crear_area(self):
        self.assertEqual(self._post(self.med, "/api/areas/", {"institucion": self.inst.id, "nombre": "Z"}), 403)

    def test_admin_puede_crear_area(self):
        self.assertEqual(self._post(self.admin, "/api/areas/", {"institucion": self.inst.id, "nombre": "Z"}), 201)

    def test_configurador_no_puede_crear_area(self):
        self.assertEqual(self._post(self.conf, "/api/areas/", {"institucion": self.inst.id, "nombre": "Z"}), 403)

    # --- Registros (ciudadanos) -------------------------------------------
    def test_administrativo_puede_crear_ciudadano(self):
        self.assertEqual(self._post(self.adm, "/api/ciudadanos/", {"institucion": self.inst.id, "nombre": "Juan", "documento": "111"}), 201)

    def test_configurador_no_puede_crear_ciudadano(self):
        self.assertEqual(self._post(self.conf, "/api/ciudadanos/", {"institucion": self.inst.id, "nombre": "Juan", "documento": "222"}), 403)

    # --- Lectura abierta a miembros ---------------------------------------
    def test_medico_puede_leer_flujos(self):
        self.client.force_authenticate(self.med)
        self.assertEqual(self.client.get("/api/flujos/").status_code, 200)

    # --- Superusuario pasa siempre ----------------------------------------
    def test_superuser_puede_crear_area(self):
        self.assertEqual(self._post(self.root, "/api/areas/", {"institucion": self.inst.id, "nombre": "ZZ"}), 201)
