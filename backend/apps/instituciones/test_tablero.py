"""El tablero le cuenta la producción del período al área que procesó el caso.

`area_actual` es un puntero MÓVIL: el nodo `derivar` lo pisa con el área destino
mientras el caso sigue corriendo el flujo del área de origen. Si las métricas de
período cuelgan de ahí, Guardia informa menos ingresos de los que corrió, el área
que recibió la derivación informa de más, y la atribución cambia HACIA ATRÁS: el
ingreso contado ayer a las 10:00 se muda de gráfico a las 11:00. El jefe no puede
reconciliar el tablero con su turno y termina llevando su propia planilla.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano


class TableroAtribucionPorAreaTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inst = Institucion.objects.create(nombre="Hospital Test", tipo="Hospital")
        cls.guardia = Area.objects.create(institucion=cls.inst, nombre="Guardia")
        cls.internacion = Area.objects.create(institucion=cls.inst, nombre="Internación")

        cls.flujo = Flujo.objects.create(institucion=cls.inst, area=cls.guardia, titulo="Atención de guardia")
        cls.ver = VersionFlujo.objects.create(
            flujo=cls.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        cls.nodo = Nodo.objects.create(version=cls.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención")

        cls.usuario = Usuario.objects.create_user(email="jefe@test.local", password="x", nombre="Jefa")
        m = Membresia.objects.create(usuario=cls.usuario, institucion=cls.inst, rol=Membresia.Rol.JEFE_AREA)
        m.areas.add(cls.guardia, cls.internacion)

        cls.ciudadano = Ciudadano.objects.create(institucion=cls.inst, nombre="P", apellido="Q", documento="1")

    def setUp(self):
        self.client.force_authenticate(self.usuario)

    def _caso_derivado(self, estado=Caso.Estado.CERRADO, horas=5):
        """Un caso que corrió el flujo de Guardia y quedó apuntando a Internación.

        Es exactamente lo que deja el nodo `derivar`: `area_actual` cambia, el
        flujo que lo procesó no.
        """
        caso = Caso.objects.create(
            institucion=self.inst, version=self.ver, ciudadano=self.ciudadano,
            nodo_actual=self.nodo, area_actual=self.internacion, estado=estado,
        )
        # `creado`/`actualizado` son auto_now: sólo un UPDATE crudo los fija, y
        # sin fijarlos la resolución promedio da cero y el test no distingue nada.
        ahora = timezone.now()
        Caso.objects.filter(pk=caso.pk).update(creado=ahora - timedelta(hours=horas), actualizado=ahora)
        return caso

    def _tablero_area(self, area):
        r = self.client.get(f"/api/areas/{area.id}/tablero/")
        self.assertEqual(r.status_code, 200)
        return r.data

    # --- Tablero de área ---------------------------------------------------
    def test_los_ingresos_del_periodo_los_cuenta_el_area_que_corrio_el_flujo(self):
        """Si falla, el área informa ingresos que no atendió y la que sí lo hizo
        aparece con menos trabajo del que tuvo: es el número con el que se decide
        a qué servicio se le manda gente."""
        self._caso_derivado()

        self.assertEqual(self._tablero_area(self.guardia)["resumen"]["ingresos"], 1)
        self.assertEqual(self._tablero_area(self.internacion)["resumen"]["ingresos"], 0)

    def test_los_cerrados_y_la_resolucion_no_se_mudan_cuando_el_caso_se_deriva(self):
        """Si falla, el área que resolvió el caso muestra cero cerrados y cero
        horas de resolución, y el jefe lee que su servicio no resuelve nada."""
        self._caso_derivado(horas=5)

        guardia = self._tablero_area(self.guardia)["resumen"]
        internacion = self._tablero_area(self.internacion)["resumen"]
        self.assertEqual(guardia["cerrados"], 1)
        self.assertEqual(guardia["resolucion_prom_h"], 5.0)
        self.assertEqual(internacion["cerrados"], 0)
        self.assertEqual(internacion["resolucion_prom_h"], 0)

    def test_la_serie_de_ingresos_del_area_no_cambia_hacia_atras(self):
        """Si falla, el punto que el gráfico dibujó ayer desaparece hoy: la serie
        de ayer no es la misma hoy y el tablero deja de ser reconciliable."""
        self._caso_derivado()

        serie = self._tablero_area(self.guardia)["serie_ingresos"]
        self.assertEqual(sum(p["casos"] for p in serie), 1)
        self.assertEqual(sum(p["casos"] for p in self._tablero_area(self.internacion)["serie_ingresos"]), 0)

    def test_los_activos_se_cuentan_donde_esta_el_caso_ahora(self):
        """La contracara: la carga VIVA sí se responde con `area_actual`. Si esto
        falla, el área que tiene al paciente adentro figura vacía y la que lo
        derivó parece seguir ocupándose de él."""
        self._caso_derivado(estado=Caso.Estado.EN_ESPERA)

        self.assertEqual(self._tablero_area(self.internacion)["resumen"]["activos"], 1)
        self.assertEqual(self._tablero_area(self.guardia)["resumen"]["activos"], 0)

    # --- Tablero general ---------------------------------------------------
    def test_la_fila_del_tablero_general_no_mezcla_dos_definiciones_de_area(self):
        """La misma fila de «Carga y tiempos por área» tenía la espera y la
        atención colgadas del flujo y la resolución colgada de `area_actual`. Si
        falla, dentro de un mismo renglón conviven dos áreas distintas."""
        self._caso_derivado(horas=5)

        r = self.client.get(f"/api/instituciones/{self.inst.id}/tablero/")
        self.assertEqual(r.status_code, 200)
        por_area = {a["nombre"]: a for a in r.data["por_area"]}
        self.assertEqual(por_area["Guardia"]["resolucion_prom_h"], 5.0)
        self.assertEqual(por_area["Internación"]["resolucion_prom_h"], 0)
