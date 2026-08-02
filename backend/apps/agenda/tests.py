"""
Agenda de turnos: disponibilidad, reserva, sobreturnos, ausentismo y llegada.

Lo que más se cuida acá es que un horario no se dé dos veces y que presentarse
al turno abra el caso: sin eso último el turno es una anotación en una grilla y
alguien tiene que cargar todo de nuevo a mano.
"""
from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from . import motor
from .models import Agenda, Bloqueo, Disponibilidad, Turno


def un_martes(semanas=1):
    """Un martes futuro, para no depender del día en que corran los tests."""
    d = timezone.localdate() + timedelta(days=7 * semanas)
    return d + timedelta(days=(1 - d.weekday()) % 7)


class AgendaTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_superuser("agenda@cauce.local", "x", nombre="Adm")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suárez",
            duracion_min=20, sobreturnos_max=2,
        )
        self.disp = Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=1, desde=time(8, 0), hasta=time(10, 0),
        )
        self.martes = un_martes()
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="30111222"
        )

    def _hora(self, h, m=0, fecha=None):
        return timezone.make_aware(
            datetime.combine(fecha or self.martes, time(h, m)), timezone.get_current_timezone()
        )


class DisponibilidadTests(AgendaTestCase):
    def test_la_franja_genera_los_horarios_del_dia(self):
        """8 a 10 cada 20 minutos son seis turnos, y el último empieza 9:40."""
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual(len(h), 6)
        self.assertEqual(timezone.localtime(h[0]["inicio"]).strftime("%H:%M"), "08:00")
        self.assertEqual(timezone.localtime(h[-1]["inicio"]).strftime("%H:%M"), "09:40")

    def test_no_genera_un_turno_que_no_entra(self):
        """
        Con franjas de 45 minutos entre 8 y 10 entran dos, no tres: el tercero
        terminaría 10:15, después de que la agenda cerró.
        """
        self.disp.duracion_min = 45
        self.disp.save()
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual([timezone.localtime(x["inicio"]).strftime("%H:%M") for x in h],
                         ["08:00", "08:45"])

    def test_otro_dia_de_la_semana_no_tiene_turnos(self):
        self.assertEqual(motor.horarios_del_dia(self.agenda, self.martes + timedelta(days=1)), [])

    def test_una_franja_fuera_de_vigencia_no_rige(self):
        """Permite cargar el horario nuevo sin borrar el viejo."""
        self.disp.vigente_desde = self.martes + timedelta(days=30)
        self.disp.save()
        self.assertEqual(motor.horarios_del_dia(self.agenda, self.martes), [])

    def test_un_bloqueo_saca_los_horarios_que_cubre(self):
        """Vacaciones o mantenimiento, sin perder el horario habitual."""
        Bloqueo.objects.create(
            agenda=self.agenda, desde=self._hora(8, 0), hasta=self._hora(9, 0), motivo="Congreso"
        )
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual([timezone.localtime(x["inicio"]).strftime("%H:%M") for x in h],
                         ["09:00", "09:20", "09:40"])
        self.assertTrue(Disponibilidad.objects.filter(pk=self.disp.pk).exists())


class ReservaTests(AgendaTestCase):
    def test_dar_un_turno(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.assertEqual(t.estado, Turno.Estado.RESERVADO)
        self.assertEqual(t.duracion_min, 20)

    def test_el_horario_dado_figura_ocupado_con_el_paciente(self):
        """
        La grilla muestra los ocupados, no sólo lo que queda: quien atiende el
        mostrador necesita poder decir «a las 8 está con otro paciente, ¿le
        sirve 8:20?».
        """
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertTrue(h[0]["ocupado"])
        self.assertEqual(h[0]["paciente"], "Ana Pérez")
        self.assertFalse(h[1]["ocupado"])

    def test_no_se_da_dos_veces_el_mismo_horario(self):
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, otro, self._hora(8, 0), autor=self.user)

    def test_no_se_da_un_horario_que_no_existe_en_la_agenda(self):
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(11, 0), autor=self.user)

    def test_no_se_da_un_horario_bloqueado(self):
        Bloqueo.objects.create(agenda=self.agenda, desde=self._hora(8, 0), hasta=self._hora(9, 0))
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)

    def test_la_misma_persona_no_saca_dos_turnos_el_mismo_dia(self):
        """Casi siempre es un doble clic, y ocupa un lugar que otro necesita."""
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 20), autor=self.user)

    def test_cancelar_libera_el_horario(self):
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.cancelar(t, autor=self.user, motivo="no puede venir")
        self.assertFalse(motor.horarios_del_dia(self.agenda, self.martes)[0]["ocupado"])
        motor.reservar(self.agenda, otro, self._hora(8, 0), autor=self.user)  # no levanta


class SobreturnoTests(AgendaTestCase):
    """
    Existe en todas las agendas reales. Si el sistema no lo admite se anota en
    un papel, y ahí se pierde: no aparece en la grilla del día ni en ningún
    indicador.
    """

    def setUp(self):
        super().setUp()
        self.otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        self.tercero = Ciudadano.objects.create(institucion=self.inst, nombre="Caro", apellido="T")
        self.cuarto = Ciudadano.objects.create(institucion=self.inst, nombre="Dani", apellido="T")
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)

    def test_se_puede_sobreturnear_un_horario_tomado(self):
        t = motor.reservar(self.agenda, self.otro, self._hora(8, 0), autor=self.user, sobreturno=True)
        self.assertTrue(t.sobreturno)

    def test_el_sobreturno_no_desplaza_al_que_tenia_el_turno(self):
        motor.reservar(self.agenda, self.otro, self._hora(8, 0), autor=self.user, sobreturno=True)
        h = motor.horarios_del_dia(self.agenda, self.martes)[0]
        self.assertEqual(h["paciente"], "Ana Pérez")
        self.assertEqual(h["sobreturnos"], 1)

    def test_hay_un_maximo_por_horario(self):
        motor.reservar(self.agenda, self.otro, self._hora(8, 0), autor=self.user, sobreturno=True)
        motor.reservar(self.agenda, self.tercero, self._hora(8, 0), autor=self.user, sobreturno=True)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.cuarto, self._hora(8, 0), autor=self.user, sobreturno=True)

    def test_no_se_sobreturnea_un_horario_libre(self):
        """Pedirlo sobre un horario vacío es un error de quien opera."""
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.otro, self._hora(9, 0), autor=self.user, sobreturno=True)

    def test_el_error_de_horario_tomado_dice_que_hay_sobreturno(self):
        """Que la salida exista y no se sepa es lo mismo que no tenerla."""
        with self.assertRaises(motor.ErrorAgenda) as e:
            motor.reservar(self.agenda, self.otro, self._hora(8, 0), autor=self.user)
        self.assertIn("sobreturno", str(e.exception))


class LlegadaTests(AgendaTestCase):
    """Presentarse al turno abre el caso: es lo que hace que el turno valga algo."""

    def setUp(self):
        super().setUp()
        self.flujo = Flujo.objects.create(
            institucion=self.inst, area=self.area, titulo="Consulta cardiológica"
        )
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1, estado="publicada")
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        aten = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.ver, origen=ini, destino=aten)
        Conexion.objects.create(version=self.ver, origen=aten, destino=fin)
        self.agenda.flujo = self.flujo
        self.agenda.profesional = self.user
        self.agenda.save()
        self.turno = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)

    def test_presentarse_abre_el_caso_con_los_datos_del_turno(self):
        motor.registrar_llegada(self.turno, autor=self.user)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, Turno.Estado.PRESENTE)
        self.assertIsNotNone(self.turno.caso_id)
        caso = self.turno.caso
        self.assertEqual(caso.ciudadano_id, self.paciente.id)
        self.assertEqual(caso.area_actual_id, self.area.id)
        self.assertIsNotNone(caso.nodo_actual_id, "el caso tiene que quedar posicionado")

    def test_el_caso_nace_con_dueno_si_la_agenda_es_de_un_profesional(self):
        motor.registrar_llegada(self.turno, autor=self.user)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.caso.asignado_a_id, self.user.id)

    def test_sin_version_publicada_lo_dice_en_vez_de_abrir_cualquier_cosa(self):
        self.ver.estado = "borrador"
        self.ver.save()
        with self.assertRaises(motor.ErrorAgenda) as e:
            motor.registrar_llegada(self.turno, autor=self.user)
        self.assertIn("publicada", str(e.exception))

    def test_sin_flujo_igual_registra_que_vino(self):
        """
        El ausentismo se mide con esto. Negarse a registrar la llegada porque
        falta una configuración perdería el dato y no arregla nada.
        """
        self.agenda.flujo = None
        self.agenda.save()
        self.turno.refresh_from_db()
        motor.registrar_llegada(self.turno, autor=self.user)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, Turno.Estado.PRESENTE)
        self.assertIsNone(self.turno.caso_id)

    def test_no_se_registra_dos_veces_la_llegada(self):
        """Abriría un segundo caso para la misma consulta."""
        motor.registrar_llegada(self.turno, autor=self.user)
        self.turno.refresh_from_db()
        with self.assertRaises(motor.ErrorAgenda):
            motor.registrar_llegada(self.turno, autor=self.user)
        self.assertEqual(Caso.objects.count(), 1)

    def test_no_se_registra_la_llegada_de_un_turno_cancelado(self):
        motor.cancelar(self.turno, autor=self.user)
        self.turno.refresh_from_db()
        with self.assertRaises(motor.ErrorAgenda):
            motor.registrar_llegada(self.turno, autor=self.user)


class AusentismoTests(AgendaTestCase):
    def test_ausente_y_cancelado_se_cuentan_por_separado(self):
        """
        Son dos problemas distintos: el turno cancelado con tiempo se puede
        reasignar, el ausente ya se perdió. Mezclarlos hace que el indicador no
        sirva para decidir nada.
        """
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        a = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        b = motor.reservar(self.agenda, otro, self._hora(8, 20), autor=self.user)
        motor.marcar_ausente(a, autor=self.user)
        motor.cancelar(b, autor=self.user)
        self.assertEqual(Turno.objects.filter(estado=Turno.Estado.AUSENTE).count(), 1)
        self.assertEqual(Turno.objects.filter(estado=Turno.Estado.CANCELADO).count(), 1)

    def test_el_ausente_no_libera_el_horario(self):
        """La hora del profesional se perdió igual: la grilla tiene que decirlo."""
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        t = Turno.objects.get()
        motor.marcar_ausente(t, autor=self.user)
        self.assertTrue(motor.horarios_del_dia(self.agenda, self.martes)[0]["ocupado"])

    def test_no_se_marca_ausente_a_quien_ya_se_presento(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.registrar_llegada(t, autor=self.user)
        t.refresh_from_db()
        with self.assertRaises(motor.ErrorAgenda):
            motor.marcar_ausente(t, autor=self.user)

    def test_confirmar_deja_registrado_cuando_se_avisó(self):
        """Es el dato con el que se mide si el recordatorio baja el ausentismo."""
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.confirmar(t, autor=self.user)
        t.refresh_from_db()
        self.assertEqual(t.estado, Turno.Estado.CONFIRMADO)
        self.assertIsNotNone(t.recordado_at)


class ProximosLibresTests(AgendaTestCase):
    def test_devuelve_los_proximos_horarios_libres(self):
        """Para dar un turno por teléfono sin ir mirando día por día."""
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        # Se busca desde ese mismo martes: entre hoy y él puede haber otro
        # martes con la agenda entera libre, y el primer libre sería el de ahí.
        libres = motor.proximos_libres(self.agenda, desde=self._hora(0, 1), cuantos=3)
        self.assertEqual(len(libres), 3)
        self.assertEqual(timezone.localtime(libres[0]["inicio"]).strftime("%H:%M"), "08:20")

    def test_no_ofrece_horarios_ya_pasados(self):
        libres = motor.proximos_libres(self.agenda, cuantos=5)
        self.assertTrue(all(h["inicio"] > timezone.now() for h in libres))
