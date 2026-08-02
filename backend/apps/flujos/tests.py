from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario

from apps.instituciones.models import Area, Grupo, Institucion, Subarea

from .models import Flujo, Nodo, VersionFlujo
from .serializers import NodoSerializer


class FlujoAmbitoTests(TestCase):
    """Un flujo puede ser de la institución, de un área o de una sub-área."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.subarea = Subarea.objects.create(area=self.area, nombre="Hemodinamia")

    def test_flujo_de_institucion(self):
        f = Flujo.objects.create(institucion=self.inst, titulo="Ingreso general")
        self.assertEqual(f.ambito, "institucion")

    def test_flujo_de_area(self):
        f = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Proceso de área")
        self.assertEqual(f.ambito, "area")

    def test_flujo_de_subarea_deriva_area(self):
        # Fijar sólo la sub-área debe completar el área padre automáticamente.
        f = Flujo.objects.create(institucion=self.inst, subarea=self.subarea, titulo="Proceso específico")
        self.assertEqual(f.ambito, "subarea")
        self.assertEqual(f.area_id, self.area.id)


class NodoGruposTests(TestCase):
    """Un nodo puede declarar qué grupos son responsables de ejecutarlo."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Turno mañana")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Triage")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Evaluar")

    def test_asignar_grupo_y_serializar_detalle(self):
        s = NodoSerializer(self.nodo, data={"grupos": [self.grupo.id]}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        data = NodoSerializer(self.nodo).data
        self.assertEqual(data["grupos"], [self.grupo.id])
        self.assertEqual(data["grupos_detalle"][0]["nombre"], "Turno mañana")
        self.assertEqual(data["grupos_detalle"][0]["area_nombre"], "Guardia")


class FiltroEstadoVigenteTests(APITestCase):
    """`?estado=` filtra por la versión VIGENTE, que no es un campo del flujo.

    «Vigente» es la publicada si existe y, si no, la última por número. La regla
    es sutil —un flujo con v1 publicada y v2 borrador cuenta como PUBLICADO, no
    como borrador— y antes vivía sólo en el frontend, donde además se aplicaba
    sobre los 25 flujos de la primera página.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user(
            email="admin@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

    def _flujo(self, titulo, *estados):
        """Crea un flujo con una versión por estado (v1, v2, …)."""
        f = Flujo.objects.create(institucion=self.inst, titulo=titulo)
        for i, estado in enumerate(estados, start=1):
            VersionFlujo.objects.create(flujo=f, numero=i, estado=estado)
        return f

    def _titulos(self, estado):
        r = self.client.get(f"/api/flujos/?estado={estado}")
        self.assertEqual(r.status_code, 200)
        return {f["titulo"] for f in r.data["results"]}

    def test_publicada_gana_aunque_haya_un_borrador_mas_nuevo(self):
        self._flujo("Con publicada y borrador nuevo", "publicada", "borrador")
        self.assertIn("Con publicada y borrador nuevo", self._titulos("publicada"))
        self.assertNotIn("Con publicada y borrador nuevo", self._titulos("borrador"))

    def test_sin_publicada_manda_la_ultima(self):
        self._flujo("Sólo borradores", "borrador", "borrador")
        self._flujo("Terminó archivado", "borrador", "archivada")

        self.assertIn("Sólo borradores", self._titulos("borrador"))
        self.assertIn("Terminó archivado", self._titulos("archivada"))
        # La v1 borrador no lo hace aparecer como borrador: manda la última.
        self.assertNotIn("Terminó archivado", self._titulos("borrador"))

    def test_flujo_sin_versiones_no_aparece_en_ningun_estado(self):
        Flujo.objects.create(institucion=self.inst, titulo="Recién creado")
        for estado in ("publicada", "borrador", "archivada"):
            self.assertNotIn("Recién creado", self._titulos(estado))

    def test_sin_estado_devuelve_todos(self):
        self._flujo("Uno", "publicada")
        self._flujo("Dos", "borrador")
        r = self.client.get("/api/flujos/")
        self.assertEqual({f["titulo"] for f in r.data["results"]}, {"Uno", "Dos"})
