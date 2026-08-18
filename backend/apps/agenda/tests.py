"""
Agenda de turnos: disponibilidad, reserva, sobreturnos, ausentismo y llegada.

Lo que más se cuida acá es que un horario no se dé dos veces y que presentarse
al turno abra el caso: sin eso último el turno es una anotación en una grilla y
alguien tiene que cargar todo de nuevo a mano.
"""
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
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


class NingunTurnoSeVuelveInvisibleTests(AgendaTestCase):
    """
    Un turno vigente tiene que salir en la grilla del día SIEMPRE, aunque su
    horario esté bloqueado o ya no exista en la agenda.

    Es la lista con la que el mostrador llama a los pacientes para avisarles.
    Si el turno desaparece de la pantalla nadie tiene a quién llamar, la persona
    viaja al hospital para nada, y después el turno queda `reservado` para
    siempre o alguien le carga un ausentismo que fue del hospital.
    """

    def test_bloquear_el_dia_no_borra_de_la_grilla_los_turnos_ya_dados(self):
        """
        Es el escenario más común de la agenda: el profesional avisa a las 7 que
        no viene y el administrativo bloquea el día. Antes la pantalla pasaba a
        decir «La agenda no atiende este día» y los pacientes con turno
        desaparecían.
        """
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        Bloqueo.objects.create(
            agenda=self.agenda, desde=self._hora(0, 0), hasta=self._hora(23, 59),
            motivo="El profesional no viene",
        )
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual(len(h), 1, "el bloqueo tiene que dejar sólo el horario con turno")
        self.assertEqual(h[0]["paciente"], "Ana Pérez")
        self.assertTrue(h[0]["bloqueado"], "la grilla tiene que decir que está bloqueado")
        self.assertFalse(h[0]["admite_sobreturno"], "no se sobreturnea un horario bloqueado")

    def test_desactivar_la_franja_no_esconde_al_que_ya_tiene_el_papel(self):
        """
        Desactivar una disponibilidad es cotidiano. Los turnos ya dados dejaban
        de caer en la grilla y salían de la respuesta sin que nada avisara.
        """
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.disp.activa = False
        self.disp.save()
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual(len(h), 1)
        self.assertTrue(h[0]["fuera_de_grilla"])
        self.assertEqual(h[0]["paciente"], "Ana Pérez")

    def test_cambiarle_el_horario_a_la_franja_no_esconde_los_turnos_viejos(self):
        """
        Se corre la atención de la mañana a la tarde y los turnos de las 8 dejan
        de coincidir con ningún horario generado.
        """
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.disp.desde, self.disp.hasta = time(14, 0), time(16, 0)
        self.disp.save()
        h = motor.horarios_del_dia(self.agenda, self.martes)
        sueltos = [x for x in h if x["fuera_de_grilla"]]
        self.assertEqual([x["paciente"] for x in sueltos], ["Ana Pérez"])
        self.assertEqual(h[-1], sueltos[0], "los sueltos van al final, después de la grilla")

    def test_los_horarios_bloqueados_sin_turno_siguen_sin_ofrecerse(self):
        """La contracara: bloquear tiene que seguir cerrando la agenda."""
        Bloqueo.objects.create(agenda=self.agenda, desde=self._hora(8, 0), hasta=self._hora(9, 0))
        h = motor.horarios_del_dia(self.agenda, self.martes)
        self.assertEqual([timezone.localtime(x["inicio"]).strftime("%H:%M") for x in h],
                         ["09:00", "09:20", "09:40"])


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


class DosTurnosAlaVezTests(AgendaTestCase):
    """
    Una llama por teléfono y otra está en el mostrador, al mismo tiempo y sobre
    el mismo horario libre.

    Si pasan las dos quedan dos titulares a las 8:00 y la grilla muestra uno
    solo: el segundo paciente tiene el turno impreso y para el sistema no
    existe. Llega, discute, y nadie puede explicarle nada.
    """

    def test_el_candado_de_reservar_agarra_una_fila_que_existe(self):
        """
        Con el horario libre no hay ninguna fila de turno para bloquear, y en
        Postgres un `SELECT ... FOR UPDATE` que no matchea nada no bloquea nada
        (no hay predicate locking): las dos transacciones leían la lista vacía y
        las dos insertaban. El candado tiene que ser sobre la agenda.
        """
        if connection.vendor != "postgresql":
            self.skipTest("el candado sólo se puede observar en Postgres")
        with CaptureQueriesContext(connection) as consultas:
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        candados = [c["sql"] for c in consultas.captured_queries if "FOR UPDATE" in c["sql"]]
        self.assertTrue(
            any(Agenda._meta.db_table in sql for sql in candados),
            "reservar no bloquea ninguna fila que exista: las reservas simultáneas no se serializan",
        )

    def test_la_base_no_deja_dos_titulares_en_el_mismo_horario(self):
        """
        Red de seguridad abajo del candado, para lo que entre por fuera del
        motor (el admin, una carga masiva, un PATCH nuevo).
        """
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turno.objects.create(
                agenda=self.agenda, ciudadano=otro, inicio=self._hora(8, 0), duracion_min=20
            )

    def test_un_turno_cancelado_no_traba_el_horario(self):
        """La restricción no puede volverse un candado permanente sobre la hora."""
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.cancelar(t, autor=self.user)
        motor.reservar(self.agenda, otro, self._hora(8, 0), autor=self.user)  # no levanta

    def test_los_sobreturnos_siguen_pudiendo_repetir_horario(self):
        """El sobreturno es la excepción que la agenda tiene que admitir."""
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        tercero = Ciudadano.objects.create(institucion=self.inst, nombre="Caro", apellido="T")
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.reservar(self.agenda, otro, self._hora(8, 0), autor=self.user, sobreturno=True)
        motor.reservar(self.agenda, tercero, self._hora(8, 0), autor=self.user, sobreturno=True)
        self.assertEqual(Turno.objects.filter(sobreturno=True).count(), 2)


class AccionesSolapadasTests(AgendaTestCase):
    """
    El turno llega a las acciones leído fuera de toda transacción. Sin releerlo
    bajo candado, dos ejecuciones solapadas deciden las dos sobre datos viejos.
    """

    def setUp(self):
        super().setUp()
        self.flujo = Flujo.objects.create(
            institucion=self.inst, area=self.area, titulo="Consulta cardiológica"
        )
        ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1, estado="publicada")
        ini = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        aten = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        fin = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=ver, origen=ini, destino=aten)
        Conexion.objects.create(version=ver, origen=aten, destino=fin)
        self.agenda.flujo = self.flujo
        self.agenda.save()
        self.turno = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)

    def test_la_llegada_no_decide_con_una_copia_vieja_del_turno(self):
        """
        Es apretar «Llegó» de nuevo porque no respondió, o dos administrativos
        registrando la misma llegada. Con la copia vieja se abre un SEGUNDO caso
        y el primero queda huérfano, ya iniciado y circulando por el flujo: lo
        llaman por altavoz y no aparece nadie.
        """
        copia_vieja = Turno.objects.get(pk=self.turno.pk)
        motor.registrar_llegada(self.turno, autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.registrar_llegada(copia_vieja, autor=self.user)
        self.assertEqual(Caso.objects.count(), 1)

    def test_no_queda_un_turno_cancelado_con_un_caso_abierto_adentro(self):
        """
        Cancelar y registrar la llegada guardan campos distintos, así que
        ninguno pisa el estado del otro: quedaba un turno `cancelado` con un
        caso en atención, un estado que no debería poder existir.
        """
        copia_vieja = Turno.objects.get(pk=self.turno.pk)
        motor.cancelar(self.turno, autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.registrar_llegada(copia_vieja, autor=self.user)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, Turno.Estado.CANCELADO)
        self.assertIsNone(self.turno.caso_id)
        self.assertEqual(Caso.objects.count(), 0)

    def test_no_se_marca_ausente_con_una_copia_vieja(self):
        """Le carga al paciente un ausentismo cuando ya se había presentado."""
        copia_vieja = Turno.objects.get(pk=self.turno.pk)
        motor.registrar_llegada(self.turno, autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.marcar_ausente(copia_vieja, autor=self.user)


class TrazabilidadTests(AgendaTestCase):
    """
    «Me cancelaron el turno y nadie me avisó» es el reclamo típico del
    mostrador, y «no vino» es el estado que perjudica al paciente. Las tres
    funciones recibían `autor` y lo tiraban a la basura: no había a quién
    preguntarle.
    """

    def test_cancelar_deja_anotado_quien_lo_hizo(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.cancelar(t, autor=self.user, motivo="llamó para avisar")
        t.refresh_from_db()
        self.assertEqual(t.resuelto_por_id, self.user.id)
        self.assertIsNotNone(t.resuelto_at)

    def test_marcar_ausente_deja_anotado_quien_lo_hizo(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.marcar_ausente(t, autor=self.user)
        t.refresh_from_db()
        self.assertEqual(t.resuelto_por_id, self.user.id)

    def test_confirmar_deja_anotado_quien_atendio_el_telefono(self):
        """`recordado_at` sólo dice «entró en una lista», no quién llamó."""
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.confirmar(t, autor=self.user)
        t.refresh_from_db()
        self.assertEqual(t.resuelto_por_id, self.user.id)


class ReprogramarTests(AgendaTestCase):
    """
    Reprogramar es lo que más se pide después de dar el turno. Hacerlo con un
    PATCH a `inicio` no pasaba por ninguna regla.
    """

    def setUp(self):
        super().setUp()
        self.turno = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)

    def test_mover_el_turno_a_otro_horario_de_la_agenda(self):
        t = motor.reprogramar(self.turno, self._hora(9, 0), autor=self.user)
        self.assertEqual(t.inicio, self._hora(9, 0))
        self.assertFalse(motor.horarios_del_dia(self.agenda, self.martes)[0]["ocupado"])

    def test_no_se_reprograma_encima_de_un_horario_tomado(self):
        """Apilaría dos titulares en la misma hora, invisibles en la grilla."""
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        motor.reservar(self.agenda, otro, self._hora(9, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reprogramar(self.turno, self._hora(9, 0), autor=self.user)

    def test_no_se_reprograma_a_un_horario_que_no_existe(self):
        with self.assertRaises(motor.ErrorAgenda):
            motor.reprogramar(self.turno, self._hora(3, 0), autor=self.user)

    def test_no_se_reprograma_adentro_de_un_bloqueo(self):
        Bloqueo.objects.create(agenda=self.agenda, desde=self._hora(9, 0), hasta=self._hora(10, 0))
        with self.assertRaises(motor.ErrorAgenda):
            motor.reprogramar(self.turno, self._hora(9, 0), autor=self.user)

    def test_queda_escrito_de_donde_venia(self):
        """Si el paciente llega con el papel viejo, el mostrador tiene qué decirle."""
        t = motor.reprogramar(self.turno, self._hora(9, 0), autor=self.user)
        self.assertIn("08:00", t.observaciones)

    def test_un_turno_ya_resuelto_no_se_reprograma(self):
        motor.marcar_ausente(self.turno, autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reprogramar(self.turno, self._hora(9, 0), autor=self.user)


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

    def test_no_consulta_de_mas_por_cada_dia_que_mira(self):
        """
        Miraba 30 días con tres consultas por día: ~90 idas y vueltas a la base
        por request, contra un Postgres administrado con latencia de red, y del
        otro lado hay alguien esperando en el teléfono. Ninguna de las tres
        depende del día.
        """
        with self.assertNumQueries(3):
            motor.proximos_libres(self.agenda, dias=30, cuantos=50)

    def test_no_ofrece_un_horario_bloqueado(self):
        """Ofrecerlo termina en un turno que la agenda va a rechazar al darlo."""
        Bloqueo.objects.create(
            agenda=self.agenda, desde=self._hora(0, 0), hasta=self._hora(23, 59)
        )
        libres = motor.proximos_libres(self.agenda, desde=self._hora(0, 1), cuantos=3)
        self.assertTrue(all(timezone.localdate(h["inicio"]) != self.martes for h in libres))


class ModalidadTests(AgendaTestCase):
    """
    Presencial o virtual.

    Lo que se cuida acá es que la modalidad del turno no pueda contradecir a la
    de la agenda, y que un turno virtual salga con la sala puesta: las dos cosas
    terminan en un paciente esperando en el lugar equivocado.
    """

    def test_por_defecto_el_turno_es_presencial(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.assertEqual(t.modalidad, Turno.Modalidad.PRESENCIAL)
        self.assertEqual(t.enlace, "")

    def test_una_agenda_virtual_da_turnos_virtuales_sin_que_nadie_lo_pida(self):
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.enlace_virtual = "https://sala.example.com/suarez"
        self.agenda.save()
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.assertEqual(t.modalidad, Turno.Modalidad.VIRTUAL)
        # La sala se COPIA al reservar: si mañana cambia la de la agenda, el link
        # que se le dio a esta persona tiene que seguir siendo el que funcionaba.
        self.assertEqual(t.enlace, "https://sala.example.com/suarez")

    def test_la_agenda_presencial_no_admite_un_turno_virtual(self):
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           modalidad=Turno.Modalidad.VIRTUAL)

    def test_la_agenda_virtual_no_admite_un_turno_presencial(self):
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.save()
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           modalidad=Turno.Modalidad.PRESENCIAL)

    def test_la_agenda_mixta_da_las_dos_y_por_defecto_presencial(self):
        """
        Equivocarse hacia presencial deja al paciente viniendo al hospital; hacia
        virtual lo deja esperando frente a una pantalla a alguien que lo espera
        en el consultorio.
        """
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.save()
        otro = Ciudadano.objects.create(
            institucion=self.inst, nombre="Luis", apellido="Gomez", documento="30999888"
        )
        a = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        b = motor.reservar(self.agenda, otro, self._hora(8, 20), autor=self.user,
                           modalidad=Turno.Modalidad.VIRTUAL, enlace="https://sala.example.com/l")
        self.assertEqual(a.modalidad, Turno.Modalidad.PRESENCIAL)
        self.assertEqual(b.modalidad, Turno.Modalidad.VIRTUAL)
        self.assertEqual(b.enlace, "https://sala.example.com/l")

    def test_un_turno_presencial_no_se_queda_con_un_enlace(self):
        """Alguien lo lee y se conecta en vez de venir."""
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           enlace="https://sala.example.com/pegado")
        self.assertEqual(t.enlace, "")

    def test_pasar_el_turno_a_virtual_no_libera_el_horario(self):
        """
        Es el pedido de todos los dias —«no puedo ir, ¿lo hacemos por video?»— y
        la alternativa era cancelar y volver a dar el turno: en el medio se lo
        lleva otro paciente.
        """
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.enlace_virtual = "https://sala.example.com/suarez"
        self.agenda.save()
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        t = motor.cambiar_modalidad(t, modalidad=Turno.Modalidad.VIRTUAL, autor=self.user)
        self.assertEqual(t.modalidad, Turno.Modalidad.VIRTUAL)
        self.assertEqual(t.enlace, "https://sala.example.com/suarez")
        self.assertEqual(t.inicio, self._hora(8, 0))
        self.assertEqual(t.estado, Turno.Estado.RESERVADO)
        self.assertIn("Modalidad", t.observaciones)

    def test_volver_a_presencial_borra_el_enlace(self):
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.enlace_virtual = "https://sala.example.com/suarez"
        self.agenda.save()
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           modalidad=Turno.Modalidad.VIRTUAL)
        t = motor.cambiar_modalidad(t, modalidad=Turno.Modalidad.PRESENCIAL, autor=self.user)
        self.assertEqual(t.modalidad, Turno.Modalidad.PRESENCIAL)
        self.assertEqual(t.enlace, "")

    def test_no_se_cambia_la_modalidad_de_un_turno_ya_resuelto(self):
        """Reescribiria lo que paso, y con eso no se puede medir nada."""
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.save()
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        motor.marcar_ausente(t, autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.cambiar_modalidad(t, modalidad=Turno.Modalidad.VIRTUAL, autor=self.user)

    def test_no_se_pasa_a_virtual_un_turno_de_agenda_presencial(self):
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.cambiar_modalidad(t, modalidad=Turno.Modalidad.VIRTUAL, autor=self.user)

    def test_cambiar_la_sala_de_la_agenda_no_toca_los_turnos_dados(self):
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.enlace_virtual = "https://sala.example.com/vieja"
        self.agenda.save()
        t = motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        self.agenda.enlace_virtual = "https://sala.example.com/nueva"
        self.agenda.save()
        t.refresh_from_db()
        self.assertEqual(t.enlace, "https://sala.example.com/vieja")

    def test_un_enlace_que_no_es_una_direccion_web_se_rechaza(self):
        """
        Guardado, el boton «Abrir sala» no abre nada y nadie se entera hasta el
        dia del turno.
        """
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.save()
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           enlace="sala de la doctora")

    def test_un_enlace_larguisimo_es_un_error_de_agenda_y_no_un_500(self):
        """La columna guarda 200 caracteres: sin esto, la base cortaba con un 500."""
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.save()
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user,
                           enlace="https://sala.example.com/" + ("x" * 200))


class CuposTests(AgendaTestCase):
    """
    Varias personas por horario.

    Uno es el consultorio; mas de uno es el vacunatorio o la sala de enfermeria,
    donde tres puestos atienden a las 10 en paralelo. Lo que se cuida es que el
    cupo no se de dos veces y que el sobreturno siga siendo para el horario lleno.
    """

    def setUp(self):
        super().setUp()
        self.disp.cupos = 3
        self.disp.save()
        self.otros = [
            Ciudadano.objects.create(
                institucion=self.inst, nombre=f"P{i}", apellido="X", documento=f"4000000{i}"
            )
            for i in range(4)
        ]

    def test_tres_personas_en_el_mismo_horario(self):
        for i in range(3):
            motor.reservar(self.agenda, self.otros[i], self._hora(8, 0), autor=self.user)
        turnos = Turno.objects.filter(agenda=self.agenda, inicio=self._hora(8, 0), sobreturno=False)
        self.assertEqual(turnos.count(), 3)
        # Cada una en un cupo distinto: es lo que la base garantiza.
        self.assertEqual(sorted(t.posicion for t in turnos), [0, 1, 2])

    def test_la_cuarta_persona_ya_no_entra(self):
        for i in range(3):
            motor.reservar(self.agenda, self.otros[i], self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda) as e:
            motor.reservar(self.agenda, self.otros[3], self._hora(8, 0), autor=self.user)
        # El mensaje dice cuantos lugares hay y ofrece el sobreturno: sin eso, la
        # respuesta al mostrador sale a tanteo.
        self.assertIn("3 de 3", str(e.exception))
        self.assertIn("sobreturno", str(e.exception))

    def test_el_cupo_que_se_libera_se_vuelve_a_usar(self):
        """
        Cancelar el turno del primer puesto y dar otro tiene que reusar ESE lugar.
        Tomando `len(titulares)` como posicion, el nuevo caia en el 2 —donde ya
        habia alguien— y la base lo rechazaba con un error que en la pantalla no
        queria decir nada.
        """
        a = motor.reservar(self.agenda, self.otros[0], self._hora(8, 0), autor=self.user)
        motor.reservar(self.agenda, self.otros[1], self._hora(8, 0), autor=self.user)
        motor.reservar(self.agenda, self.otros[2], self._hora(8, 0), autor=self.user)
        motor.cancelar(a, autor=self.user)
        nuevo = motor.reservar(self.agenda, self.otros[3], self._hora(8, 0), autor=self.user)
        self.assertEqual(nuevo.posicion, 0)

    def test_el_sobreturno_recien_va_cuando_no_queda_lugar(self):
        motor.reservar(self.agenda, self.otros[0], self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda) as e:
            motor.reservar(self.agenda, self.otros[1], self._hora(8, 0), autor=self.user,
                           sobreturno=True)
        self.assertIn("lugar", str(e.exception))

    def test_la_grilla_informa_los_lugares_del_horario(self):
        motor.reservar(self.agenda, self.otros[0], self._hora(8, 0), autor=self.user)
        h = next(x for x in motor.horarios_del_dia(self.agenda, self.martes)
                 if x["inicio"] == self._hora(8, 0))
        self.assertEqual(h["cupos"], 3)
        self.assertEqual(h["libres"], 2)
        self.assertEqual(h["titulares"], 1)
        # Con lugar todavia no esta ocupado, y por eso no admite sobreturno.
        self.assertFalse(h["ocupado"])
        self.assertFalse(h["admite_sobreturno"])

    def test_un_horario_con_lugar_sigue_apareciendo_en_los_proximos_libres(self):
        """Si no, la agenda del vacunatorio se ve llena con un solo paciente."""
        motor.reservar(self.agenda, self.otros[0], self._hora(8, 0), autor=self.user)
        libres = motor.proximos_libres(self.agenda, desde=self._hora(0, 1), cuantos=3)
        self.assertEqual(timezone.localtime(libres[0]["inicio"]).strftime("%H:%M"), "08:00")

    def test_los_sobreturnos_de_la_franja_pisan_a_los_de_la_agenda(self):
        """La franja de la tarde puede no aceptar ninguno: es la que cierra."""
        self.disp.cupos = 1
        self.disp.sobreturnos_max = 0
        self.disp.save()
        motor.reservar(self.agenda, self.otros[0], self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reservar(self.agenda, self.otros[1], self._hora(8, 0), autor=self.user,
                           sobreturno=True)
        h = next(x for x in motor.horarios_del_dia(self.agenda, self.martes)
                 if x["inicio"] == self._hora(8, 0))
        self.assertEqual(h["sobreturnos_max"], 0)
        self.assertFalse(h["admite_sobreturno"])

    def test_reprogramar_a_un_horario_con_lugar_toma_el_cupo_libre(self):
        ocupa = motor.reservar(self.agenda, self.otros[0], self._hora(8, 20), autor=self.user)
        self.assertEqual(ocupa.posicion, 0)
        mover = motor.reservar(self.agenda, self.otros[1], self._hora(8, 0), autor=self.user)
        movido = motor.reprogramar(mover, self._hora(8, 20), autor=self.user)
        self.assertEqual(movido.inicio, self._hora(8, 20))
        self.assertEqual(movido.posicion, 1)

    def test_no_se_reprograma_a_un_horario_completo(self):
        for i in range(3):
            motor.reservar(self.agenda, self.otros[i], self._hora(8, 20), autor=self.user)
        mover = motor.reservar(self.agenda, self.otros[3], self._hora(8, 0), autor=self.user)
        with self.assertRaises(motor.ErrorAgenda):
            motor.reprogramar(mover, self._hora(8, 20), autor=self.user)

    def test_la_franja_dice_cuantos_turnos_ofrece(self):
        """El numero que quiere ver quien la carga, antes de guardarla."""
        # 8 a 10 cada 20 minutos son 6 horarios; con 3 puestos, 18 turnos.
        self.assertEqual(self.disp.cuantos_turnos, 18)


class SemanaTests(AgendaTestCase):
    def test_devuelve_los_siete_dias_con_su_grilla(self):
        lunes = self.martes - timedelta(days=1)
        dias = motor.grilla_de_dias(self.agenda, lunes, dias=7)
        self.assertEqual(len(dias), 7)
        self.assertEqual([d["fecha"] for d in dias][1], self.martes)
        # La agenda solo atiende los martes: el resto de los dias viene vacio.
        self.assertEqual(len(dias[1]["horarios"]), 6)
        self.assertEqual(len(dias[0]["horarios"]), 0)

    def test_no_consulta_de_mas_por_cada_dia_de_la_semana(self):
        """
        Siete dias son tres consultas, no veintiuna: es la misma razon por la que
        `proximos_libres` no las hace por dia, y ahora las dos comparten el
        armado del rango.
        """
        with self.assertNumQueries(3):
            motor.grilla_de_dias(self.agenda, self.martes, dias=7)

    def test_un_turno_dado_aparece_en_el_dia_que_le_toca(self):
        motor.reservar(self.agenda, self.paciente, self._hora(8, 0), autor=self.user)
        dias = motor.grilla_de_dias(self.agenda, self.martes - timedelta(days=1), dias=7)
        martes = dias[1]["horarios"]
        self.assertEqual(martes[0]["titulares"], 1)
        self.assertEqual(martes[0]["libres"], 0)
