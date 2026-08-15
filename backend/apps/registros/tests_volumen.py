"""
Que abrir una historia clínica no se degrade con los años.

Mismo criterio que `apps/casos/tests_volumen.py`: no se mide un tope de
consultas —un «no más de 12» es arbitrario y termina subiéndose hasta que no
significa nada— sino que la cantidad de consultas NO dependa de cuántas filas
hay. Ésa es exactamente la propiedad que rompe un N+1.

Va acá y no allá porque el eje que importa en esta pantalla es distinto: no son
más pacientes en la lista sino más ATENCIONES del mismo paciente. El costo crece
con los años de historia, así que el paciente crónico —el que más veces se abre y
el que más urgente es leer— es el que más tarda en cargar. Y la historia se
conserva diez años.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica, Receta


class HistoriaClinicaVolumenTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.med = Usuario.objects.create_user("med@test.local", "x", nombre="Ana", apellido="Ruiz")
        m = Membresia.objects.create(
            usuario=self.med, institucion=self.inst, rol="medico", activo=True
        )
        m.areas.set([self.area])
        LegajoProfesional.objects.create(usuario=self.med, matricula="MP 12345")
        self.client.force_authenticate(self.med)

    def _paciente_con(self, atenciones):
        """
        Un paciente con `atenciones` entradas, cada una de un profesional
        distinto: si todas fueran del mismo autor un N+1 quedaría escondido
        detrás de la caché de instancias.
        """
        c = Ciudadano.objects.create(
            institucion=self.inst, nombre=f"P{atenciones}", apellido="Test",
            documento=f"40{atenciones:06d}",
        )
        hc = HistoriaClinica.objects.create(ciudadano=c)
        for i in range(atenciones):
            autor = Usuario.objects.create_user(f"a{atenciones}-{i}@test.local", "x", nombre=f"Prof {i}")
            EntradaHistoria.objects.create(historia=hc, titulo=f"Consulta {i}", autor=autor)
            Receta.objects.create(historia=hc, detalle=f"Medicación {i}", autor=autor)
        return c

    def _consultas(self, atenciones):
        c = self._paciente_con(atenciones)
        url = f"/api/historias-clinicas/?ciudadano={c.id}"
        # La primera llamada calienta lo que se cachea por proceso (permisos,
        # content types): sin esto la diferencia mide el calentamiento.
        self.client.get(url)
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        return len(ctx.captured_queries)

    def test_abrir_la_historia_no_escala_con_los_anos_de_evolucion(self):
        """
        Es la llamada que hace la pantalla de historia clínica. Con 19 entradas
        eran 27 consultas —19 a `accounts_usuario`, una por autor de entrada—, y
        eso no lo rompe ningún test funcional: la respuesta es idéntica, sólo
        cambia el tiempo.
        """
        pocas = self._consultas(3)
        muchas = self._consultas(30)
        self.assertEqual(
            pocas, muchas,
            f"/api/historias-clinicas/ hace {pocas} consultas con 3 atenciones y "
            f"{muchas} con 30: hay un N+1. Falta un Prefetch con select_related "
            f"del autor en el queryset.",
        )
