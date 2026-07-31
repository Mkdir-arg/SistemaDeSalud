"""Tests de la capa API: scope por institución y acciones del motor."""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, VersionFlujo
from apps.instituciones.models import Institucion
from apps.casos.models import Caso


class ScopeInstitucionTest(APITestCase):
    def setUp(self):
        self.inst_a = Institucion.objects.create(nombre="Hospital A")
        self.inst_b = Institucion.objects.create(nombre="Hospital B")

        def flujo_con_caso(inst):
            f = Flujo.objects.create(institucion=inst, titulo=f"Flujo {inst.nombre}")
            v = VersionFlujo.objects.create(flujo=f, numero=1)
            return Caso.objects.create(institucion=inst, version=v)

        self.caso_a = flujo_con_caso(self.inst_a)
        self.caso_b = flujo_con_caso(self.inst_b)

        # Usuario con membresía solo en A.
        self.user = Usuario.objects.create_user("u@a.com", "x", nombre="U")
        Membresia.objects.create(usuario=self.user, institucion=self.inst_a, rol=Membresia.Rol.ADMINISTRATIVO)

        self.admin = Usuario.objects.create_superuser("admin@x.com", "x", nombre="Admin")

    def test_usuario_solo_ve_su_institucion(self):
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/casos/")
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(self.caso_a.id, ids)
        self.assertNotIn(self.caso_b.id, ids, "no debe ver casos de otra institución")

    def test_usuario_no_accede_a_caso_de_otra_institucion(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f"/api/casos/{self.caso_b.id}/")
        self.assertEqual(r.status_code, 404)

    def test_superadmin_ve_todo(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/casos/")
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(self.caso_a.id, ids)
        self.assertIn(self.caso_b.id, ids)

    def test_instituciones_filtradas(self):
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/instituciones/")
        nombres = {i["nombre"] for i in r.data["results"]}
        self.assertEqual(nombres, {"Hospital A"})


class ListadoTest(APITestCase):
    """Paginación, orden y búsqueda: lo que necesita la tabla del frontend.

    Se testea porque es contrato con la UI, no adorno: la tabla pagina contra
    `count`, ordena por `?ordering=` y elige el tamaño con `?page_size=`. Si
    alguno deja de funcionar, la pantalla miente en silencio (mostraría los
    primeros 25 y nadie se enteraría).
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital A")
        self.flujo = Flujo.objects.create(institucion=self.inst, titulo="Ingreso")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

        from apps.registros.models import Ciudadano

        self.quiroga = Ciudadano.objects.create(
            institucion=self.inst, nombre="Rubén", apellido="Quiroga", documento="12345678"
        )
        otro = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="87654321"
        )
        # 30 casos: más de una página con el PAGE_SIZE de 25.
        for i in range(30):
            Caso.objects.create(
                institucion=self.inst, version=self.ver,
                ciudadano=self.quiroga if i == 0 else otro,
                prioridad=Caso.Prioridad.URGENTE if i == 0 else Caso.Prioridad.NORMAL,
            )
        self.admin = Usuario.objects.create_superuser("admin@x.com", "x", nombre="Admin")
        self.client.force_authenticate(self.admin)

    def test_pagina_con_total_y_siguiente(self):
        r = self.client.get("/api/casos/")
        self.assertEqual(r.data["count"], 30)
        self.assertEqual(len(r.data["results"]), 25)
        self.assertIsNotNone(r.data["next"], "debe haber segunda página")

    def test_segunda_pagina_trae_el_resto(self):
        r = self.client.get("/api/casos/?page=2")
        self.assertEqual(len(r.data["results"]), 5)

    def test_page_size_configurable(self):
        # Sin `page_size_query_param` en la clase de paginación, DRF ignora esto
        # y devuelve 25: el selector de «filas por página» no haría nada.
        r = self.client.get("/api/casos/?page_size=10")
        self.assertEqual(len(r.data["results"]), 10)
        self.assertEqual(r.data["count"], 30)

    def test_page_size_tiene_techo(self):
        r = self.client.get("/api/casos/?page_size=99999")
        self.assertLessEqual(len(r.data["results"]), 200)

    def test_ordering_ascendente_y_descendente(self):
        asc = self.client.get("/api/casos/?ordering=id").data["results"]
        desc = self.client.get("/api/casos/?ordering=-id").data["results"]
        self.assertLess(asc[0]["id"], desc[0]["id"])
        self.assertEqual(asc[0]["id"], min(c["id"] for c in asc))

    def test_ordering_invalido_se_ignora(self):
        r = self.client.get("/api/casos/?ordering=; DROP TABLE casos")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 30)

    def test_busqueda_por_apellido_del_paciente(self):
        r = self.client.get("/api/casos/?search=Quiroga")
        self.assertEqual(r.data["count"], 1)

    def test_busqueda_por_documento(self):
        r = self.client.get("/api/casos/?search=12345678")
        self.assertEqual(r.data["count"], 1)

    def test_busqueda_se_combina_con_el_filtro_exacto(self):
        r = self.client.get("/api/casos/?search=Quiroga&prioridad=normal")
        self.assertEqual(r.data["count"], 0, "el caso de Quiroga es urgente")


class SubirArchivoTest(APITestCase):
    def test_subir_archivo_devuelve_nombre_y_url(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        user = Usuario.objects.create_user("f@x.com", "x", nombre="F")
        self.client.force_authenticate(user)
        archivo = SimpleUploadedFile("estudio.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        r = self.client.post("/api/archivos/", {"archivo": archivo}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["nombre"], "estudio.pdf")
        self.assertIn("/media/uploads/", r.data["url"])

    def test_subir_sin_archivo_da_400(self):
        user = Usuario.objects.create_user("g@x.com", "x", nombre="G")
        self.client.force_authenticate(user)
        r = self.client.post("/api/archivos/", {}, format="multipart")
        self.assertEqual(r.status_code, 400)
