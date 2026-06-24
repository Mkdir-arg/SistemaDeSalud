from django.test import TestCase

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
