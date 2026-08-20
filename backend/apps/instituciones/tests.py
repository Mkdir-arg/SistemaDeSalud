from django.test import TestCase
from rest_framework.test import APITestCase

from apps.common import _coerce
from apps.accounts.models import Membresia, Usuario

from .models import Area, Grupo, Institucion


class CoerceQueryParamTest(TestCase):
    """El mixin de filtrado debe convertir strings de query param a su tipo."""

    def test_booleanos(self):
        self.assertIs(_coerce("true"), True)
        self.assertIs(_coerce("false"), False)
        self.assertIs(_coerce("TRUE"), True)

    def test_null(self):
        self.assertIsNone(_coerce("null"))
        self.assertIsNone(_coerce("none"))

    def test_strings_normales(self):
        self.assertEqual(_coerce("recibido"), "recibido")
        self.assertEqual(_coerce("5"), "5")


class GobiernoPlataformaInstitucionTests(APITestCase):
    def setUp(self):
        self.base = Institucion.objects.create(nombre="Direccion provincial")
        self.hospital = Institucion.objects.create(nombre="Hospital Central")
        self.clinica = Institucion.objects.create(nombre="Clinica Norte")
        self.admin = Usuario.objects.create_user("admin-inst@test.local", "x")
        Membresia.objects.create(
            usuario=self.admin, institucion=self.hospital, rol=Membresia.Rol.ADMIN_INSTITUCION, activo=True
        )
        self.plataforma = Usuario.objects.create_user("plataforma-inst@test.local", "x")
        Membresia.objects.create(
            usuario=self.plataforma, institucion=self.base, rol=Membresia.Rol.PLATAFORMA, activo=True
        )

    def test_admin_institucional_no_crea_otro_establecimiento(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post("/api/instituciones/", {
            "nombre": "Hospital Nuevo",
            "tipo": "Hospital",
        }, format="json")
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(Institucion.objects.filter(nombre="Hospital Nuevo").exists())

    def test_admin_institucional_no_edita_la_institucion(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(f"/api/instituciones/{self.hospital.id}/", {
            "nombre": "Hospital Renombrado",
        }, format="json")
        self.assertEqual(r.status_code, 403, r.data)
        self.hospital.refresh_from_db()
        self.assertEqual(self.hospital.nombre, "Hospital Central")

    def test_plataforma_crea_y_edita_establecimientos(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.post("/api/instituciones/", {
            "nombre": "Hospital Nuevo",
            "tipo": "Hospital",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r2 = self.client.patch(f"/api/instituciones/{r.data['id']}/", {
            "estado": "en_alta",
        }, format="json")
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data["estado"], "en_alta")

    def test_plataforma_ve_todas_las_instituciones(self):
        self.client.force_authenticate(self.plataforma)
        r = self.client.get("/api/instituciones/?page_size=100")
        self.assertEqual(r.status_code, 200, r.data)
        nombres = {i["nombre"] for i in r.data["results"]}
        self.assertIn("Hospital Central", nombres)
        self.assertIn("Clinica Norte", nombres)


class GruposOperativosTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.root = Usuario.objects.create_superuser("root-grupos@test.local", "x", nombre="Root")
        self.client.force_authenticate(self.root)
        self.activo = self._usuario("activo@test.local")
        self.inactivo_membresia = self._usuario("baja@test.local", membresia_activa=False)
        self.inactivo_usuario = self._usuario("inactivo@test.local", usuario_activo=False)

    def _usuario(self, email, membresia_activa=True, usuario_activo=True):
        usuario = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        usuario.is_active = usuario_activo
        usuario.save(update_fields=["is_active"])
        membresia = Membresia.objects.create(
            usuario=usuario,
            institucion=self.inst,
            rol=Membresia.Rol.MEDICO,
            activo=membresia_activa,
        )
        membresia.areas.add(self.area)
        return usuario

    def test_no_agrega_miembro_con_membresia_inactiva(self):
        r = self.client.post("/api/grupos/", {
            "area": self.area.id,
            "nombre": "Guardia",
            "miembros": [self.inactivo_membresia.id],
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Grupo.objects.filter(nombre="Guardia").exists())

    def test_no_agrega_usuario_inactivo(self):
        r = self.client.post("/api/grupos/", {
            "area": self.area.id,
            "nombre": "Guardia",
            "miembros": [self.inactivo_usuario.id],
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Grupo.objects.filter(nombre="Guardia").exists())

    def test_integrantes_muestra_solo_miembros_operativos(self):
        grupo = Grupo.objects.create(area=self.area, nombre="Guardia")
        grupo.miembros.set([self.activo, self.inactivo_membresia, self.inactivo_usuario])

        r = self.client.get(f"/api/grupos/{grupo.id}/")

        self.assertEqual(r.status_code, 200, r.data)
        emails = {u["email"] for u in r.data["integrantes"]}
        self.assertEqual(emails, {"activo@test.local"})

    def test_staff_cuenta_solo_personas_activas_con_membresia_activa(self):
        r_area = self.client.get(f"/api/areas/{self.area.id}/")
        r_inst = self.client.get(f"/api/instituciones/{self.inst.id}/")

        self.assertEqual(r_area.status_code, 200, r_area.data)
        self.assertEqual(r_inst.status_code, 200, r_inst.data)
        self.assertEqual(r_area.data["staff"], 1)
        self.assertEqual(r_inst.data["staff"], 1)


class ResetEscuelaTests(APITestCase):
    """`reset-escuela` vacía la institución de capacitación, y sólo esa.

    Existe porque el recorrido guiado dejó de sembrar por API: ahora completa los
    formularios de la app, y sin la red de `crear_si_falta` necesita arrancar
    de una institución limpia. Es un borrado en cascada, así que lo que estos
    tests cuidan es el candado, no el camino feliz.
    """

    def setUp(self):
        self.escuela = Institucion.objects.create(nombre="Hospital Escuela Cauce")
        self.real = Institucion.objects.create(nombre="Hospital Central")
        self.super = Usuario.objects.create_superuser("super-reset@test.local", "x")
        self.plataforma = Usuario.objects.create_user("plataforma-reset@test.local", "x")
        Membresia.objects.create(
            usuario=self.plataforma, institucion=self.escuela,
            rol=Membresia.Rol.PLATAFORMA, activo=True,
        )

    def test_super_admin_vacia_la_escuela_con_todo_lo_que_cuelga(self):
        Area.objects.create(institucion=self.escuela, nombre="Guardia escuela")
        self.client.force_authenticate(self.super)

        r = self.client.post(f"/api/instituciones/{self.escuela.id}/reset-escuela/")

        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(Institucion.objects.filter(nombre="Hospital Escuela Cauce").exists())
        self.assertFalse(Area.objects.filter(nombre="Guardia escuela").exists())

    def test_no_vacia_una_institucion_real(self):
        """El candado del nombre: apuntarlo a un hospital vaciaría el hospital."""
        Area.objects.create(institucion=self.real, nombre="Guardia")
        self.client.force_authenticate(self.super)

        r = self.client.post(f"/api/instituciones/{self.real.id}/reset-escuela/")

        self.assertEqual(r.status_code, 400, r.data)
        self.assertTrue(Institucion.objects.filter(pk=self.real.pk).exists())
        self.assertTrue(Area.objects.filter(nombre="Guardia").exists())

    def test_gobierno_de_plataforma_no_alcanza(self):
        """Escribir instituciones y vaciarlas en cascada no son el mismo permiso."""
        self.client.force_authenticate(self.plataforma)

        r = self.client.post(f"/api/instituciones/{self.escuela.id}/reset-escuela/")

        self.assertEqual(r.status_code, 403, r.data)
        self.assertTrue(Institucion.objects.filter(pk=self.escuela.pk).exists())

    def test_borra_los_accesos_clinicos_que_protegen_a_la_escuela(self):
        """`AccesoClinico` es PROTECT y no cuelga por cascada: sin borrarlo
        primero, el reset falla contra cualquier escuela que se haya operado."""
        from apps.auditoria.models import AccesoClinico
        from apps.registros.models import Ciudadano

        paciente = Ciudadano.objects.create(
            institucion=self.escuela, nombre="Ana", apellido="Escuela", documento="90000001",
        )
        AccesoClinico.objects.create(
            usuario=self.super, ciudadano=paciente, institucion=self.escuela,
        )
        self.client.force_authenticate(self.super)

        r = self.client.post(f"/api/instituciones/{self.escuela.id}/reset-escuela/")

        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(Institucion.objects.filter(pk=self.escuela.pk).exists())
        self.assertFalse(AccesoClinico.objects.exists())

    def test_borra_los_casos_que_protegen_la_version_del_flujo(self):
        """`Caso.version` es PROTECT, y PROTECT aborta el borrado incluso cuando
        el caso que protege también se está borrando —esa tolerancia es de
        RESTRICT—. Sin sacar los casos primero, el reset falla contra cualquier
        escuela que ya haya operado un paciente, que es toda escuela usada."""
        from apps.casos.models import Caso
        from apps.flujos.models import Flujo, VersionFlujo
        from apps.registros.models import Ciudadano

        area = Area.objects.create(institucion=self.escuela, nombre="Guardia escuela")
        flujo = Flujo.objects.create(institucion=self.escuela, area=area, titulo="Guardia escuela")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        paciente = Ciudadano.objects.create(
            institucion=self.escuela, nombre="Luis", apellido="Simulado", documento="90000002",
        )
        Caso.objects.create(
            institucion=self.escuela, version=version, ciudadano=paciente, area_actual=area,
        )
        self.client.force_authenticate(self.super)

        r = self.client.post(f"/api/instituciones/{self.escuela.id}/reset-escuela/")

        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(Institucion.objects.filter(pk=self.escuela.pk).exists())
        self.assertFalse(Caso.objects.exists())
        self.assertFalse(VersionFlujo.objects.exists())
