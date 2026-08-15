"""
Camas de internación: asignación, pases entre sectores y liberación.

Una cama mal contabilizada no es un error de software, es un paciente sin lugar
o una cama vacía que el sistema dice ocupada. Estos tests cuidan sobre todo eso:
que la cama vuelva a estar disponible siempre que el paciente ya no esté.
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, EstadiaCama, Institucion, Subarea
from apps.registros.models import Ciudadano

from . import motor
from .models import Caso


class CamasTests(TestCase):
    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("jefe@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.uti = Subarea.objects.create(area=self.area, nombre="UTI")
        self.sala = Subarea.objects.create(area=self.area, nombre="Clínica médica")

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.cama_nodo = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.CAMA, titulo="Asignar cama",
            config={"sector": self.sala.id},
        )
        self.evol = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Evolución")
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Alta")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.cama_nodo)
        Conexion.objects.create(version=self.ver, origen=self.cama_nodo, destino=self.evol)
        Conexion.objects.create(version=self.ver, origen=self.evol, destino=fin)

        self.c101 = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        self.c102 = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-B")
        self.uti1 = Cama.objects.create(area=self.area, subarea=self.uti, nombre="UTI 1")

    def _internar(self, nombre="Ana"):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.jefe)
        caso.refresh_from_db()
        return caso

    # --- Asignar ------------------------------------------------------------ #

    def test_el_caso_espera_cama_y_no_avanza_solo(self):
        """Elegir cama es una decisión de quien conoce el sector."""
        caso = self._internar()
        self.assertEqual(caso.nodo_actual_id, self.cama_nodo.id)
        self.assertEqual(caso.estado, Caso.Estado.EN_ESPERA)

    def test_asignar_ocupa_la_cama_y_hace_avanzar_al_caso(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        self.c101.refresh_from_db()
        self.assertEqual(self.c101.estado, Cama.Estado.OCUPADA)
        self.assertEqual(self.c101.caso_id, caso.id)
        self.assertEqual(caso.nodo_actual_id, self.evol.id)

    def test_no_se_puede_internar_en_una_cama_ocupada(self):
        """Dos administrativos pueden estar mirando el mismo tablero."""
        a = self._internar("Ana")
        motor.asignar_cama(a, self.c101.id, autor=self.jefe)
        b = self._internar("Beto")
        with self.assertRaises(motor.ErrorMotor):
            motor.asignar_cama(b, self.c101.id, autor=self.jefe)

    def test_no_se_puede_internar_en_una_cama_sin_higienizar(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        motor.dar_de_alta_cama(caso, autor=self.jefe)
        otro = self._internar("Beto")
        with self.assertRaises(motor.ErrorMotor):
            motor.asignar_cama(otro, self.c101.id, autor=self.jefe)

    def test_un_caso_no_puede_ocupar_dos_camas(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        caso.nodo_actual = self.cama_nodo  # como si volviera al paso
        caso.save()
        with self.assertRaises(motor.ErrorMotor):
            motor.asignar_cama(caso, self.c102.id, autor=self.jefe)

    def test_solo_se_ofrecen_las_camas_del_sector_del_paso(self):
        """El nodo declara «Clínica médica»: no se ofrece una cama de UTI."""
        nombres = set(motor.camas_disponibles(self.cama_nodo).values_list("nombre", flat=True))
        self.assertEqual(nombres, {"101-A", "101-B"})

    # --- Liberar ------------------------------------------------------------ #

    def test_cerrar_el_caso_libera_la_cama(self):
        """
        Lo más importante del módulo: una cama ocupada por un caso que ya
        terminó no se libera nunca sola, y el sector se queda sin camas sin que
        nadie entienda por qué.
        """
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.avanzar(caso, {"titulo": "Alta", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.c101.refresh_from_db()
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.CERRADO)
        self.assertIsNone(self.c101.caso_id)
        self.assertNotEqual(self.c101.estado, Cama.Estado.OCUPADA)

    def test_cancelar_el_caso_libera_la_cama(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.cancelar_caso(caso, autor=self.jefe, motivo="se fue por sus medios")
        self.c101.refresh_from_db()
        self.assertIsNone(self.c101.caso_id)

    def test_la_cama_liberada_queda_en_higiene_y_no_libre(self):
        """Ofrecer una cama sin higienizar es el error que nadie quiere cometer."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        motor.dar_de_alta_cama(caso, autor=self.jefe)
        self.c101.refresh_from_db()
        self.assertEqual(self.c101.estado, Cama.Estado.HIGIENE)

    def test_marcar_lista_la_deja_disponible(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        motor.dar_de_alta_cama(caso, autor=self.jefe)
        self.c101.refresh_from_db()
        motor.cambiar_estado_cama(self.c101, Cama.Estado.LIBRE, autor=self.jefe)
        self.c101.refresh_from_db()
        self.assertTrue(self.c101.disponible)

    def test_no_se_puede_marcar_libre_una_cama_ocupada(self):
        """Dejaría a un paciente internado en ningún lado."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        self.c101.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor):
            motor.cambiar_estado_cama(self.c101, Cama.Estado.LIBRE, autor=self.jefe)

    def test_dar_de_alta_sin_estar_internado_lo_dice(self):
        caso = self._internar()
        with self.assertRaises(motor.ErrorMotor):
            motor.dar_de_alta_cama(caso, autor=self.jefe)

    # --- Pases -------------------------------------------------------------- #

    def test_pase_de_sector_mueve_al_paciente_y_libera_la_cama_anterior(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe, motivo="descompensó")
        self.c101.refresh_from_db()
        self.uti1.refresh_from_db()
        self.assertEqual(self.c101.estado, Cama.Estado.HIGIENE)
        self.assertEqual(self.uti1.estado, Cama.Estado.OCUPADA)
        self.assertEqual(self.uti1.caso_id, caso.id)

    def test_el_pase_deja_el_recorrido_completo(self):
        """«¿Dónde estuvo este paciente?» es una pregunta clínica real."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe)
        recorrido = list(
            EstadiaCama.objects.filter(caso=caso).order_by("desde")
            .values_list("cama__nombre", "motivo_egreso")
        )
        self.assertEqual(recorrido, [("101-A", EstadiaCama.Egreso.PASE), ("UTI 1", "")])

    def test_no_se_pasa_a_una_cama_ocupada(self):
        a = self._internar("Ana")
        motor.asignar_cama(a, self.c101.id, autor=self.jefe)
        b = self._internar("Beto")
        motor.asignar_cama(b, self.c102.id, autor=self.jefe)
        a.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor):
            motor.pasar_de_sector(a, self.c102.id, autor=self.jefe)

    def test_el_pase_a_una_cama_de_baja_dice_que_esta_de_baja_y_no_que_esta_ocupada(self):
        """
        Dar de baja una cama es un PATCH sobre `activa` y no le toca el `estado`:
        la cama sigue figurando «libre» y el panel de pase se la ofrece. Si el
        motor contesta «no está libre», le está diciendo a enfermería algo que
        contradice lo que la pantalla acaba de mostrar; deja de confiar en la
        lista de camas libres, que es lo único que este módulo tiene para dar.
        """
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        self.uti1.activa = False
        self.uti1.save(update_fields=["activa"])
        self.assertEqual(self.uti1.estado, Cama.Estado.LIBRE)

        with self.assertRaises(motor.ErrorMotor) as e:
            motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe)
        self.assertIn("dada de baja", str(e.exception))
        self.assertNotIn("no está libre", str(e.exception))

    def test_el_pase_a_una_cama_ocupada_dice_en_que_estado_esta(self):
        """
        El otro lado de lo mismo: si el rechazo no nombra el estado, quien mira
        una ficha vieja del tablero no sabe si la cama se ocupó o quedó en
        higiene, y vuelve a intentar sobre la misma.
        """
        a = self._internar("Ana")
        motor.asignar_cama(a, self.c101.id, autor=self.jefe)
        b = self._internar("Beto")
        motor.asignar_cama(b, self.c102.id, autor=self.jefe)
        a.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.pasar_de_sector(a, self.c102.id, autor=self.jefe)
        self.assertIn("no está libre", str(e.exception))
        self.assertIn("ocupada", str(e.exception))

    def test_no_se_pasa_a_alguien_que_no_esta_internado(self):
        caso = self._internar()
        with self.assertRaises(motor.ErrorMotor):
            motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe)

    # --- Invariante --------------------------------------------------------- #

    def test_ocupada_y_con_paciente_son_siempre_lo_mismo(self):
        """
        `estado == OCUPADA` si y solo si hay un caso, y si y solo si hay una
        estadía abierta. Son tres formas de decir lo mismo y el módulo entero se
        apoya en que no se separen: el tablero mira `estado`, el historial mira
        las estadías y la pantalla del paciente mira `caso`.
        """
        # Las dos internaciones entran por camas de «Clínica médica», que es el
        # sector que declara el nodo de este flujo. Antes `b` entraba directo a
        # UTI: dejó de andar cuando el motor pasó a exigir que la cama sea del
        # sector del paso —una regla nueva y correcta, porque internar en un
        # sector ajeno deja la cama ocupada en un tablero que no la puede
        # liberar—. Lo que este test cuida es el invariante, no por dónde entra.
        a, b = self._internar("Ana"), self._internar("Beto")
        motor.asignar_cama(a, self.c101.id, autor=self.jefe)
        motor.asignar_cama(b, self.c102.id, autor=self.jefe)
        a.refresh_from_db()
        # El pase SÍ cruza de sector: es su función, y así el invariante se
        # comprueba también sobre una cama de UTI.
        motor.pasar_de_sector(a, self.uti1.id, autor=self.jefe)
        b.refresh_from_db()
        motor.cancelar_caso(b, autor=self.jefe, motivo="x")

        abiertas = set(
            EstadiaCama.objects.filter(hasta__isnull=True).values_list("cama_id", flat=True)
        )
        for cama in Cama.objects.all():
            with self.subTest(cama=cama.nombre):
                ocupada = cama.estado == Cama.Estado.OCUPADA
                self.assertEqual(ocupada, cama.caso_id is not None, "estado vs ocupante")
                self.assertEqual(ocupada, cama.id in abiertas, "estado vs estadía abierta")

    def test_la_estadia_registra_cuanto_duro(self):
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        antes = timezone.now()
        motor.dar_de_alta_cama(caso, autor=self.jefe)
        e = EstadiaCama.objects.get(caso=caso)
        self.assertIsNotNone(e.hasta)
        self.assertGreaterEqual(e.hasta, antes)
        self.assertEqual(e.motivo_egreso, EstadiaCama.Egreso.ALTA)


class EnsayoConCamaTests(TestCase):
    """
    El ensayo del diseñador tiene que poder atravesar un paso de cama.

    Sin esto un flujo con internación no se podía probar antes de publicarlo:
    el nodo detiene el avance esperando que alguien asigne una cama y el ensayo
    se plantaba ahí. Es justo el flujo donde más caro sale un error.
    """

    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("jefe2@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.sala = Subarea.objects.create(area=self.area, nombre="Clínica médica")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.cama_nodo = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.CAMA, titulo="Asignar cama",
            config={"sector": self.sala.id},
        )
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Alta")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.cama_nodo)
        Conexion.objects.create(version=self.ver, origen=self.cama_nodo, destino=fin)

    def test_el_ensayo_atraviesa_el_paso_de_cama(self):
        Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        r = motor.ensayar(self.ver, [{}, {}], autor=self.jefe)
        self.assertTrue(r["termino"], r)

    def test_sin_camas_el_ensayo_lo_dice_antes_de_publicar(self):
        """Enterarse al diseñar es mucho mejor que enterarse con un paciente esperando."""
        r = motor.ensayar(self.ver, [{}, {}], autor=self.jefe)
        self.assertFalse(r["termino"])
        self.assertIn("camas libres", str(r))

    def test_el_ensayo_no_deja_la_cama_ocupada(self):
        """Es un ensayo: si ocupara camas de verdad, probar un flujo llenaría el sector."""
        cama = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        motor.ensayar(self.ver, [{}, {}], autor=self.jefe)
        cama.refresh_from_db()
        self.assertEqual(cama.estado, Cama.Estado.LIBRE)
        self.assertEqual(EstadiaCama.objects.count(), 0)
