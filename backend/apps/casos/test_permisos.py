"""Autorización por rol en la API (Capa 1 de docs/ROLES-Y-PERMISOS.md).

Verifica que la escritura se gatee por la capacidad del rol y que la lectura
quede abierta a cualquier miembro de la institución.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, VersionFlujo
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


class CreateHijoScopeTests(APITestCase):
    """El create de objetos hijos resuelve la institución del PADRE (no cae a
    'capacidad en cualquier membresía'): un configurador de A no puede crear un
    Nodo en una versión de B."""

    @classmethod
    def setUpTestData(cls):
        R = Membresia.Rol
        cls.A = Institucion.objects.create(nombre="Inst A", tipo="Hospital")
        cls.B = Institucion.objects.create(nombre="Inst B", tipo="Hospital")
        cls.flujoB = Flujo.objects.create(institucion=cls.B, titulo="F-B")
        cls.verB = VersionFlujo.objects.create(flujo=cls.flujoB, numero=1)
        cls.conf_A = cls._conf("confa@test.local", cls.A)
        cls.conf_B = cls._conf("confb@test.local", cls.B)

    @classmethod
    def _conf(cls, email, inst):
        u = Usuario.objects.create_user(email=email, password="x", nombre="N")
        Membresia.objects.create(usuario=u, institucion=inst, rol=Membresia.Rol.CONFIGURADOR)
        return u

    def _crear_nodo(self, user):
        self.client.force_authenticate(user)
        return self.client.post("/api/nodos/", {"version": self.verB.id, "tipo": "form", "titulo": "N"}).status_code

    def test_configurador_de_otra_institucion_no_puede_crear_nodo(self):
        self.assertEqual(self._crear_nodo(self.conf_A), 403)

    def test_configurador_de_la_institucion_si_puede(self):
        self.assertEqual(self._crear_nodo(self.conf_B), 201)
