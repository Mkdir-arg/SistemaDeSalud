"""
El padrón de personas es por institución, no de la plataforma.

`Usuario` no tiene FK a institución —la pertenencia vive en `Membresia`—, así
que el aislamiento entre instituciones no lo da el mixin genérico sino
`UsuarioViewSet.get_queryset`. Estos tests fijan ese límite: es la diferencia
entre «el admin del Hospital A ve a su gente» y «el admin del Hospital A ve el
padrón completo de la plataforma, con nombre y email».
"""
from rest_framework.test import APITestCase

from apps.instituciones.models import Area, Institucion

from .models import LegajoProfesional, Membresia, Usuario


class PadronPorInstitucionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hospital = Institucion.objects.create(nombre="Hospital Central")
        cls.clinica = Institucion.objects.create(nombre="Clínica del Sur")

        cls.admin_hosp = cls._persona("admin@hospital.local", cls.hospital, "admin")
        cls.medico_hosp = cls._persona("medico@hospital.local", cls.hospital, "medico")
        cls.medico_clin = cls._persona("medico@clinica.local", cls.clinica, "medico")
        cls.huerfano = Usuario.objects.create_user("suelto@nadie.local", "x", nombre="Suelto")
        cls.root = Usuario.objects.create_superuser("root@cauce.local", "x", nombre="Root")

    @staticmethod
    def _persona(email, institucion, rol):
        u = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        Membresia.objects.create(usuario=u, institucion=institucion, rol=rol, activo=True)
        return u

    def _emails(self, params=""):
        self.client.force_authenticate(self.admin_hosp)
        r = self.client.get(f"/api/usuarios/{params}")
        self.assertEqual(r.status_code, 200)
        return {u["email"] for u in r.data["results"]}

    def test_el_admin_no_ve_el_padron_de_otra_institucion(self):
        emails = self._emails()
        self.assertIn(self.medico_hosp.email, emails)
        self.assertNotIn(self.medico_clin.email, emails)
        self.assertNotIn(self.huerfano.email, emails)

    def test_filtrar_por_institucion_devuelve_su_padron(self):
        self.assertEqual(
            self._emails(f"?institucion={self.hospital.id}"),
            {self.admin_hosp.email, self.medico_hosp.email},
        )

    def test_filtrar_por_una_institucion_ajena_no_filtra_nada_hacia_afuera(self):
        """El filtro no es una puerta: se cruza con el scope, no lo reemplaza."""
        self.assertEqual(self._emails(f"?institucion={self.clinica.id}"), set())

    def test_uno_mismo_siempre_se_ve(self):
        """Sin esto, quien se queda sin membresía activa no puede leer su ficha."""
        self.client.force_authenticate(self.huerfano)
        r = self.client.get(f"/api/usuarios/{self.huerfano.id}/")
        self.assertEqual(r.status_code, 200)


    def test_no_se_puede_leer_ni_editar_la_ficha_de_otra_institucion(self):
        self.client.force_authenticate(self.admin_hosp)
        self.assertEqual(self.client.get(f"/api/usuarios/{self.medico_clin.id}/").status_code, 404)
        r = self.client.patch(f"/api/usuarios/{self.medico_clin.id}/", {"nombre": "Pisado"}, format="json")
        self.assertEqual(r.status_code, 404)
        self.medico_clin.refresh_from_db()
        self.assertNotEqual(self.medico_clin.nombre, "Pisado")

    def test_el_super_admin_sigue_viendo_toda_la_plataforma(self):
        self.client.force_authenticate(self.root)
        r = self.client.get("/api/usuarios/?page_size=100")
        emails = {u["email"] for u in r.data["results"]}
        self.assertIn(self.medico_clin.email, emails)
        self.assertIn(self.huerfano.email, emails)

    def test_dos_roles_no_duplican_a_la_persona_en_la_lista(self):
        Membresia.objects.create(
            usuario=self.medico_hosp, institucion=self.hospital, rol="jefe_area", activo=True
        )
        self.client.force_authenticate(self.admin_hosp)
        r = self.client.get("/api/usuarios/?page_size=100")
        ids = [u["id"] for u in r.data["results"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(r.data["count"], len(ids))


class PerfilConCapacidadesTests(APITestCase):
    def setUp(self):
        self.hospital = Institucion.objects.create(nombre="Hospital Central")
        self.clinica = Institucion.objects.create(nombre="Clinica Sur")
        self.user = Usuario.objects.create_user("multi@cauce.local", "x", nombre="Multi")
        Membresia.objects.create(
            usuario=self.user, institucion=self.hospital,
            rol=Membresia.Rol.ADMINISTRATIVO, activo=True,
        )
        Membresia.objects.create(
            usuario=self.user, institucion=self.clinica,
            rol=Membresia.Rol.JEFE_AREA, activo=True,
        )

    def test_me_devuelve_roles_y_capacidades_por_institucion(self):
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/usuarios/me/")
        self.assertEqual(r.status_code, 200)

        hosp = str(self.hospital.id)
        clin = str(self.clinica.id)
        self.assertEqual(r.data["roles_por_institucion"][hosp], ["administrativo"])
        self.assertEqual(r.data["roles_por_institucion"][clin], ["jefe_area"])
        self.assertIn("turnos", r.data["capacidades_por_institucion"][hosp])
        self.assertIn("casos_operar", r.data["capacidades_por_institucion"][hosp])
        self.assertNotIn("historia_clinica", r.data["capacidades_por_institucion"][hosp])
        self.assertIn("historia_clinica", r.data["capacidades_por_institucion"][clin])
        self.assertIn("auditoria", r.data["capacidades_por_institucion"][clin])
        self.assertNotIn("auditoria", r.data["capacidades_por_institucion"][hosp])


class LegajoAjenoTests(APITestCase):
    """El legajo va con la persona: especialidad y matrícula no cruzan de centro."""

    @classmethod
    def setUpTestData(cls):
        cls.hospital = Institucion.objects.create(nombre="Hospital Central")
        cls.clinica = Institucion.objects.create(nombre="Clínica del Sur")
        cls.admin = Usuario.objects.create_user("admin@hospital.local", "x", nombre="Admin")
        Membresia.objects.create(usuario=cls.admin, institucion=cls.hospital, rol="admin", activo=True)
        cls.ajeno = Usuario.objects.create_user("medico@clinica.local", "x", nombre="Ajeno")
        Membresia.objects.create(usuario=cls.ajeno, institucion=cls.clinica, rol="medico", activo=True)
        cls.legajo_ajeno = LegajoProfesional.objects.create(
            usuario=cls.ajeno, especialidad="Cardiología", matricula="MN-1234"
        )

    def setUp(self):
        self.client.force_authenticate(self.admin)

    def test_no_se_lista_el_legajo_de_otra_institucion(self):
        r = self.client.get("/api/legajos/?page_size=100")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(self.legajo_ajeno.id, [x["id"] for x in r.data["results"]])

    def test_no_se_puede_pisar_la_matricula_de_un_medico_ajeno(self):
        r = self.client.patch(
            f"/api/legajos/{self.legajo_ajeno.id}/", {"matricula": "FALSA"}, format="json"
        )
        self.assertEqual(r.status_code, 404)
        self.legajo_ajeno.refresh_from_db()
        self.assertEqual(self.legajo_ajeno.matricula, "MN-1234")

    def test_no_se_puede_crear_un_legajo_a_una_persona_ajena(self):
        LegajoProfesional.objects.all().delete()
        r = self.client.post(
            "/api/legajos/", {"usuario": self.ajeno.id, "matricula": "MN-9"}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(LegajoProfesional.objects.exists())


class AltaDePersonaTests(APITestCase):
    """
    El alta crea la membresía junto con la persona.

    Con el padrón acotado, una persona sin membresía no la ve nadie: ni quien la
    creó, para darle acceso. Quedaba en la base y desaparecía de la pantalla.
    """

    @classmethod
    def setUpTestData(cls):
        cls.hospital = Institucion.objects.create(nombre="Hospital Central")
        cls.clinica = Institucion.objects.create(nombre="Clínica del Sur")
        cls.admin = Usuario.objects.create_user("admin@hospital.local", "x", nombre="Admin")
        Membresia.objects.create(usuario=cls.admin, institucion=cls.hospital, rol="admin", activo=True)
        cls.root = Usuario.objects.create_superuser("root@cauce.local", "x", nombre="Root")

    def _alta(self, **extra):
        return self.client.post(
            "/api/usuarios/",
            {"email": "nueva@hospital.local", "nombre": "Nueva", **extra},
            format="json",
        )

    def test_el_alta_deja_a_la_persona_con_membresia_y_visible(self):
        self.client.force_authenticate(self.admin)
        r = self._alta(institucion=self.hospital.id, rol="medico")
        self.assertEqual(r.status_code, 201, r.data)
        m = Membresia.objects.get(usuario_id=r.data["id"])
        self.assertEqual((m.institucion_id, m.rol, m.activo), (self.hospital.id, "medico", True))

        lista = self.client.get("/api/usuarios/?page_size=100")
        self.assertIn("nueva@hospital.local", {u["email"] for u in lista.data["results"]})

    def test_sin_institucion_entra_en_la_del_admin(self):
        """Un admin de una sola institución no tiene nada que elegir."""
        self.client.force_authenticate(self.admin)
        r = self._alta(rol="enfermeria")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Membresia.objects.get(usuario_id=r.data["id"]).institucion_id, self.hospital.id)

    def test_no_se_puede_dar_de_alta_en_una_institucion_ajena(self):
        self.client.force_authenticate(self.admin)
        r = self._alta(institucion=self.clinica.id)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Usuario.objects.filter(email="nueva@hospital.local").exists())

    def test_un_rol_inventado_no_crea_la_persona(self):
        """El rol define las capacidades: si no es válido, no hay alta a medias."""
        self.client.force_authenticate(self.admin)
        r = self._alta(rol="director_general")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Usuario.objects.filter(email="nueva@hospital.local").exists())

    def test_la_plataforma_puede_crear_sin_membresia(self):
        """El super admin da de alta al futuro admin antes de que exista su centro."""
        self.client.force_authenticate(self.root)
        r = self._alta()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(Membresia.objects.filter(usuario_id=r.data["id"]).exists())


class ConfiguracionDeAccesosTests(APITestCase):
    def setUp(self):
        self.hospital = Institucion.objects.create(nombre="Hospital Central")
        self.clinica = Institucion.objects.create(nombre="Clinica Norte")
        self.area = Area.objects.create(institucion=self.hospital, nombre="Guardia")
        self.area_ajena = Area.objects.create(institucion=self.clinica, nombre="Guardia")
        self.root = Usuario.objects.create_user(
            "root@test.local", "x", is_superuser=True, is_staff=True
        )
        self.usuario = Usuario.objects.create_user("persona@test.local", "x")
        self.client.force_authenticate(self.root)

    def test_la_membresia_no_toma_areas_de_otra_institucion(self):
        r = self.client.post("/api/membresias/", {
            "usuario": self.usuario.pk,
            "institucion": self.hospital.pk,
            "rol": Membresia.Rol.JEFE_AREA,
            "areas": [self.area_ajena.pk],
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Membresia.objects.filter(usuario=self.usuario).exists())

    def test_patch_no_mueve_membresia_de_persona_ni_institucion(self):
        m = Membresia.objects.create(
            usuario=self.usuario, institucion=self.hospital, rol=Membresia.Rol.ADMINISTRATIVO
        )
        otro = Usuario.objects.create_user("otra@test.local", "x")
        r = self.client.patch(f"/api/membresias/{m.pk}/", {
            "usuario": otro.pk, "institucion": self.clinica.pk,
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        m.refresh_from_db()
        self.assertEqual((m.usuario_id, m.institucion_id), (self.usuario.pk, self.hospital.pk))

    def test_no_se_escala_a_staff_desde_la_api_de_usuarios(self):
        r = self.client.patch(f"/api/usuarios/{self.usuario.pk}/", {"is_staff": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_staff)


class GobiernoPlataformaTests(APITestCase):
    def setUp(self):
        self.base = Institucion.objects.create(nombre="Direccion provincial")
        self.hospital = Institucion.objects.create(nombre="Hospital Central")
        self.clinica = Institucion.objects.create(nombre="Clinica Norte")
        self.plataforma = Usuario.objects.create_user("plataforma@test.local", "x", nombre="Plataforma")
        Membresia.objects.create(
            usuario=self.plataforma, institucion=self.base, rol=Membresia.Rol.PLATAFORMA, activo=True
        )
        self.admin = Usuario.objects.create_user("admin@test.local", "x", nombre="Admin")
        Membresia.objects.create(
            usuario=self.admin, institucion=self.hospital, rol=Membresia.Rol.ADMIN_INSTITUCION, activo=True
        )
        self.ajeno = Usuario.objects.create_user("ajeno@test.local", "x", nombre="Ajeno")
        Membresia.objects.create(
            usuario=self.ajeno, institucion=self.clinica, rol=Membresia.Rol.MEDICO, activo=True
        )

    def test_plataforma_ve_el_directorio_de_usuarios_completo(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.get("/api/usuarios/?page_size=100")
        self.assertEqual(r.status_code, 200, r.data)
        emails = {u["email"] for u in r.data["results"]}
        self.assertIn("ajeno@test.local", emails)

    def test_plataforma_crea_usuario_sin_membresia_institucional(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.post("/api/usuarios/", {
            "email": "nuevo@test.local", "nombre": "Nuevo",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(
            Membresia.objects.filter(usuario_id=r.data["id"]).exists(),
            "el alta de plataforma no debe enganchar al usuario a la institucion base",
        )

    def test_admin_institucional_no_asigna_roles_estatales(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/membresias/", {
            "usuario": self.ajeno.id,
            "institucion": self.hospital.id,
            "rol": Membresia.Rol.PLATAFORMA,
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(
            Membresia.objects.filter(usuario=self.ajeno, rol=Membresia.Rol.PLATAFORMA).exists()
        )

    def test_plataforma_asigna_roles_estatales(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.post("/api/membresias/", {
            "usuario": self.ajeno.id,
            "institucion": self.base.id,
            "rol": Membresia.Rol.AUDITOR,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(
            Membresia.objects.filter(usuario=self.ajeno, rol=Membresia.Rol.AUDITOR).exists()
        )

    def test_admin_institucional_no_crea_usuario_con_rol_estatal(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/usuarios/", {
            "email": "escalado@test.local",
            "nombre": "Escalado",
            "institucion": self.hospital.id,
            "rol": Membresia.Rol.PLATAFORMA,
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Usuario.objects.filter(email="escalado@test.local").exists())

    def test_me_expone_las_capacidades_de_gobierno(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.get("/api/usuarios/me/")
        self.assertEqual(r.status_code, 200, r.data)
        caps = r.data["capacidades_por_institucion"][str(self.base.id)]
        self.assertIn("gobierno_plataforma", caps)
        self.assertIn("auditoria", caps)
        self.assertIn("reportes", caps)
