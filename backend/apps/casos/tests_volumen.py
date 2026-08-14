"""
Que las listas no se degraden con el volumen.

**Qué se mide y por qué así.** No un número máximo de consultas —un tope de «no
más de 12» es arbitrario, se rompe con cualquier cambio inocente y termina
subiéndose hasta que no significa nada—. Lo que se mide es que la cantidad de
consultas **no dependa de cuántas filas hay**: mismas consultas con 3 casos que
con 30.

Ésa es exactamente la propiedad que rompe un N+1, y es la que importa. Con 25
filas por página un N+1 pasa desapercibido en desarrollo; en una guardia con
seiscientos casos es la pantalla que tarda ocho segundos en abrir, y nadie sabe
por qué porque «antes andaba bien».

Un `select_related` que alguien saca al refactorizar no rompe ningún test
funcional: la respuesta es idéntica. Sólo cambia el tiempo. Por eso hace falta
un test que mire las consultas y no el resultado.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.agenda.models import Agenda, Turno
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, ItemFila
from apps.farmacia.models import Deposito, Existencia, Insumo, Lote
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica


class VolumenTestCase(APITestCase):
    """
    Arma el mundo dos veces —pocas filas y muchas— y compara.

    Cada prueba corre sobre una base limpia, así que el mundo se construye por
    completo dentro de la medición del caso chico y del grande.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.admin = Usuario.objects.create_superuser("admin@test.local", "x")
        self.user = Usuario.objects.create_user("jefe@test.local", "x", nombre="Ana")
        m = Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol="admin", activo=True
        )
        m.areas.set([self.area])

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.nodo = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.nodo)

        self.client.force_authenticate(self.user)

    # --- el mundo -------------------------------------------------------- #
    def _poblar(self, n):
        """Crea n de cada cosa, todas relacionadas entre sí como en la realidad."""
        ahora = timezone.now()
        # `get_or_create` porque se puebla dos veces sobre la misma base (3 y
        # después 27 más).
        agenda, _ = Agenda.objects.get_or_create(
            institucion=self.inst, nombre="Consultorio", defaults={"area": self.area}
        )
        deposito, _ = Deposito.objects.get_or_create(institucion=self.inst, nombre="Central")

        desde = Ciudadano.objects.filter(institucion=self.inst).count()
        for i in range(desde, desde + n):
            c = Ciudadano.objects.create(
                institucion=self.inst, nombre=f"Paciente{i}", apellido=f"Ape{i}",
                documento=f"3000{i:04d}",
            )
            hc = HistoriaClinica.objects.create(ciudadano=c)
            EntradaHistoria.objects.create(historia=hc, titulo=f"Consulta {i}", autor=self.user)

            caso = Caso.objects.create(
                institucion=self.inst, version=self.ver, ciudadano=c,
                area_actual=self.area, nodo_actual=self.nodo, asignado_a=self.user,
            )
            ItemFila.objects.create(caso=caso, nodo=self.nodo, orden=i)
            Cama.objects.create(area=self.area, nombre=f"C-{i}")
            Turno.objects.create(
                agenda=agenda, ciudadano=c, inicio=ahora + timedelta(hours=i), duracion_min=30,
            )
            AccesoClinico.objects.create(
                usuario=self.user, ciudadano=c, institucion=self.inst,
                tipo=AccesoClinico.Tipo.DETALLE, recurso="historiaclinica",
            )
            insumo = Insumo.objects.create(institucion=self.inst, nombre=f"Insumo {i}", unidad="u")
            lote = Lote.objects.create(insumo=insumo, numero=f"L{i}")
            Existencia.objects.create(deposito=deposito, insumo=insumo, lote=lote, cantidad=10)

    # --- la medición ----------------------------------------------------- #
    def _consultas(self, url, n):
        """Consultas que hace `url` con el mundo poblado a `n`."""
        self._poblar(n)
        # La primera llamada calienta lo que se cachea por proceso (permisos,
        # content types): sin esto la diferencia mide el calentamiento y no el
        # N+1, y da un rojo distinto en cada corrida.
        self.client.get(url)
        with _Contador(self) as contador:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200, f"{url} devolvió {r.status_code}")
        return contador.cuantas

    def assertNoEscalaConElVolumen(self, url):
        pocas = self._consultas(url, 3)
        # Se sigue poblando sobre lo mismo: 3 + 27 = 30.
        muchas = self._consultas(url, 27)
        self.assertEqual(
            pocas, muchas,
            f"{url} hace {pocas} consultas con 3 filas y {muchas} con 30: "
            f"hay un N+1. Falta un select_related/prefetch_related en el queryset.",
        )


class _Contador:
    """Cuenta las consultas de un bloque, sin exigir un número de antemano."""

    def __init__(self, caso):
        self.caso = caso
        self.cuantas = 0

    def __enter__(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._ctx = CaptureQueriesContext(connection)
        self._ctx.__enter__()
        return self

    def __exit__(self, *a):
        self._ctx.__exit__(*a)
        self.cuantas = len(self._ctx.captured_queries)
        return False


class ListasTests(VolumenTestCase):
    """
    Las listas que un hospital abre todo el día.

    Si una de éstas escala con las filas, la pantalla se degrada sola a medida
    que la institución usa el sistema, que es el peor momento para descubrirlo.
    """

    def test_casos(self):
        self.assertNoEscalaConElVolumen("/api/casos/")

    def test_ciudadanos(self):
        self.assertNoEscalaConElVolumen("/api/ciudadanos/")

    def test_items_de_fila(self):
        self.assertNoEscalaConElVolumen("/api/items-fila/")

    def test_camas(self):
        self.assertNoEscalaConElVolumen("/api/camas/")

    def test_turnos(self):
        self.assertNoEscalaConElVolumen("/api/turnos/")

    def test_stock(self):
        self.assertNoEscalaConElVolumen("/api/stock/")

    def test_entradas_de_historia(self):
        self.assertNoEscalaConElVolumen("/api/entradas-historia/")

    def test_registro_de_accesos(self):
        self.assertNoEscalaConElVolumen("/api/accesos-clinicos/")

    def test_mis_tareas(self):
        """Es la pantalla de inicio de todo el personal operativo."""
        self.assertNoEscalaConElVolumen("/api/mis-tareas/")


class FachadaFhirTests(VolumenTestCase):
    """
    La fachada la consume un sistema externo, que pide de a cien y sin mirar.

    Un N+1 acá no lo sufre una pantalla: lo sufre la base mientras alguien
    atiende pacientes.
    """

    def test_patient(self):
        self.assertNoEscalaConElVolumen("/fhir/Patient")

    def test_encounter(self):
        self.assertNoEscalaConElVolumen("/fhir/Encounter")
