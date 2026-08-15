"""
Volumen de la red.

La propiedad que se cuida es la misma que en `apps/casos/tests_volumen.py`: **las
consultas no pueden depender de cuántas filas hay.** Acá las filas son
establecimientos.

El desplegable de «derivar a otro establecimiento» recalculaba la saturación de
la red entera por cada destino posible —cuatro count() por efector, por
efector—: 63 consultas con 4 hospitales, 255 con 8, 1023 con 16. Es el endpoint
que se abre con un paciente esperando adelante y con el médico decidiendo a
dónde manda una ambulancia. Y no degrada suave: cada establecimiento que se suma
a la red multiplica el costo para todos los demás, así que la pantalla que
andaba «se pone lenta» el día que la región crece, sin que nadie haya tocado un
traslado.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Cama, Institucion, Subarea

from .models import Red


class VolumenRedTests(TestCase):
    def setUp(self):
        self.red = Red.objects.create(nombre="Región Sanitaria VI")
        self.mia = Institucion.objects.create(nombre="Hospital de Lomas")
        self.red.instituciones.add(self.mia)
        self.usuario = Usuario.objects.create_user("jefe@lomas.gob.ar", "x")
        Membresia.objects.create(
            usuario=self.usuario, institucion=self.mia, rol="jefe_area", activo=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)
        self._sumados = 0

    def _sumar_efectores(self, cuantos):
        for _ in range(cuantos):
            self._sumados += 1
            inst = Institucion.objects.create(
                nombre=f"Efector {self._sumados:02d}", latitud=-34.7, longitud=-58.3
            )
            area = Area.objects.create(institucion=inst, nombre="Internación")
            sala = Subarea.objects.create(area=area, nombre="Sala")
            for j in range(3):
                Cama.objects.create(area=area, subarea=sala, nombre=f"{self._sumados}-{j}")
            self.red.instituciones.add(inst)

    def _consultas(self, url):
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, r.data)
        return len(ctx)

    def test_el_desplegable_de_destinos_no_consulta_mas_por_tener_mas_efectores(self):
        """
        Si esto se rompe, elegir a dónde derivar tarda segundos con un paciente
        esperando, y empeora solo por cada hospital que se suma a la red.
        """
        url = f"/api/traslados/destinos/?institucion={self.mia.id}"
        self._sumar_efectores(3)
        chica = self._consultas(url)
        self._sumar_efectores(27)
        grande = self._consultas(url)
        self.assertEqual(
            grande, chica,
            f"con 30 efectores hace {grande} consultas y con 3 hace {chica}",
        )

    def test_el_tablero_de_la_red_no_consulta_mas_por_tener_mas_efectores(self):
        """
        Es la pantalla que abre dirección para decidir a dónde mandar recursos, y
        corre contra la misma base que en ese momento está atendiendo la guardia.
        Contando de a un establecimiento por vez eran ocho consultas por efector
        —32 con 3, 248 con 30— más todos los traslados resueltos traídos a
        memoria: el día que la región crece, la pantalla se pone lenta para todos
        sin que nadie haya tocado un traslado.
        """
        url = f"/api/redes/{self.red.id}/tablero/"
        self._sumar_efectores(3)
        chica = self._consultas(url)
        self._sumar_efectores(27)
        grande = self._consultas(url)
        self.assertEqual(
            grande, chica,
            f"con 30 efectores hace {grande} consultas y con 3 hace {chica}",
        )

    def test_el_panorama_de_camas_no_consulta_mas_por_tener_mas_efectores(self):
        """
        `camas_en_red` es lo que llama el desplegable de derivación por cada
        red: si vuelve a contar de a un establecimiento por vez, el endpoint de
        destinos se vuelve cuadrático otra vez aunque el bucle esté arreglado.
        """
        url = f"/api/redes/{self.red.id}/camas/"
        self._sumar_efectores(3)
        chica = self._consultas(url)
        self._sumar_efectores(27)
        grande = self._consultas(url)
        self.assertEqual(
            grande, chica,
            f"con 30 efectores hace {grande} consultas y con 3 hace {chica}",
        )
