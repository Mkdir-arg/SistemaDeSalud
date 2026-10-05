"""Invariantes de las escenas actuales; no imponen reglas al modelo productivo."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase
from django.utils import timezone

from apps.casos.models import ItemFila
from apps.flujos.models import VersionFlujo
from apps.instituciones.models import Cama
from apps.casos.management.commands.seed_volumen import Command as Volumen


def verificar_escenas(test):
    colas = ItemFila.objects.filter(atendido=False, caso__ciudadano__isnull=False)
    repetidos = colas.values("nodo", "caso__ciudadano").annotate(total=Count("pk")).filter(total__gt=1)
    test.assertFalse(repetidos.exists(), list(repetidos))
    camas = Cama.objects.filter(caso__isnull=False)
    dobles = camas.values("caso__ciudadano").annotate(total=Count("pk")).filter(total__gt=1)
    test.assertFalse(dobles.exists(), list(dobles))
    en_cama = camas.values_list("caso__ciudadano_id", flat=True)
    test.assertFalse(colas.filter(caso__ciudadano_id__in=en_cama, nodo__version__flujo__titulo="Ingreso a Guardia").exists())
    nombres = camas.values("area__institucion", "caso__ciudadano__nombre", "caso__ciudadano__apellido").annotate(total=Count("pk")).filter(total__gt=1)
    test.assertFalse(nombres.exists(), list(nombres))


class SeedVolumenRegresionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_guardia", stdout=StringIO())
        call_command("seed_volumen", casos=12, pacientes=6, activos=18, dias=7,
                     stdout=StringIO(), stderr=StringIO())

    def test_pacientes_no_ocupan_lugares_incompatibles(self):
        verificar_escenas(self)

    def test_pediatria_tiene_un_menor_internado(self):
        cama = Cama.objects.filter(subarea__nombre="Pediatría", caso__isnull=False).select_related("caso__ciudadano").first()
        self.assertIsNotNone(cama)
        self.assertGreater(cama.caso.ciudadano.fecha_nacimiento, timezone.localdate() - timedelta(days=18 * 366))

    def test_guardia_tiene_circuito_y_esperas_recientes(self):
        version = VersionFlujo.objects.get(flujo__titulo="Ingreso a Guardia")
        self.assertEqual(version.tipo_circuito, "guardia")
        self.assertFalse(ItemFila.objects.filter(atendido=False, ingreso__lt=timezone.now() - timedelta(hours=3)).exists())


class SeedVolumenHigieneTests(SeedVolumenRegresionTests):
    @classmethod
    def setUpTestData(cls):
        original = Volumen._asegurar_pediatria

        def preparar_con_camas_sucias(comando, pacientes, hechos, ahora):
            Cama.objects.filter(area__institucion=comando.inst, subarea__nombre="Clínica médica",
                estado=Cama.Estado.LIBRE).update(estado=Cama.Estado.HIGIENE, desde=ahora - timedelta(hours=2))
            original(comando, pacientes, hechos, ahora)

        with patch.object(Volumen, "_asegurar_pediatria", preparar_con_camas_sucias):
            super().setUpTestData()
