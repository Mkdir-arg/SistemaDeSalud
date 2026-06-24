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
