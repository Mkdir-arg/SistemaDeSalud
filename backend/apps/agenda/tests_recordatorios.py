"""
La lista de llamados del día siguiente.

Cauce no tiene canal al paciente. Un «recordatorio» acá es que alguien del
mostrador sepa a quién llamar, y lo que se cuida es que ese aviso llegue a
alguien de verdad: un turno marcado como recordado que nadie va a llamar es
peor que no tener el comando.
"""
from datetime import time, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Notificacion
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from . import motor
from .models import Agenda, Disponibilidad, Turno


class RecordatoriosTests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.adm = Usuario.objects.create_user("adm@test.local", "x", nombre="Diego")
        m = Membresia.objects.create(
            usuario=self.adm, institucion=self.inst, rol="administrativo", activo=True
        )
        m.areas.set([self.area])

        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suárez", duracion_min=20
        )
        # Mañana, sea el día que sea: el comando mira el día siguiente.
        self.manana = timezone.localdate() + timedelta(days=1)
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=self.manana.weekday(),
            desde=time(8, 0), hasta=time(10, 0),
        )
        self.turnos = []
        for i, nombre in enumerate(["Ana", "Beto", "Caro"]):
            c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
            self.turnos.append(
                motor.reservar(self.agenda, c, self._hora(8, 20 * i))
            )

    def _hora(self, h, m):
        from datetime import datetime

        return timezone.make_aware(
            datetime.combine(self.manana, time(h, m)), timezone.get_current_timezone()
        )

    def _correr(self, *args):
        salida, errores = StringIO(), StringIO()
        call_command("recordar_turnos", *args, stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()

    def test_avisa_al_mostrador_del_area(self):
        self._correr()
        n = Notificacion.objects.filter(usuario=self.adm)
        self.assertEqual(n.count(), 1)
        self.assertIn("3 turnos por confirmar", n.first().titulo)

    def test_un_solo_aviso_por_area_y_no_uno_por_turno(self):
        """Una notificación por turno sería una lluvia de avisos inservible."""
        self._correr()
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_deja_registrado_cuando_entro_en_la_lista(self):
        """Es con lo que después se mide si llamar baja el ausentismo."""
        self._correr()
        for t in self.turnos:
            t.refresh_from_db()
            self.assertIsNotNone(t.recordado_at)

    def test_no_da_por_confirmado_lo_que_solo_salio_en_una_lista(self):
        """Confirmar es cuando el paciente CONTESTA. Lo otro sería inventar."""
        self._correr()
        for t in self.turnos:
            t.refresh_from_db()
            self.assertEqual(t.estado, Turno.Estado.RESERVADO)

    def test_correrlo_dos_veces_no_duplica_el_aviso(self):
        self._correr()
        self._correr()
        self.assertEqual(Notificacion.objects.count(), 1)

    def test_no_llama_a_los_ya_confirmados_ni_a_los_cancelados(self):
        motor.confirmar(self.turnos[0])
        motor.cancelar(self.turnos[1])
        salida, _ = self._correr()
        self.assertIn("1 turno(s) por confirmar", salida)

    def test_en_seco_no_toca_nada(self):
        self._correr("--seco")
        self.assertEqual(Notificacion.objects.count(), 0)
        self.turnos[0].refresh_from_db()
        self.assertIsNone(self.turnos[0].recordado_at)

    # --- El agujero que este comando puede tapar o esconder ------------------ #

    def test_un_area_sin_mostrador_lo_dice_en_vez_de_callarlo(self):
        """
        Si el área no tiene a nadie que pueda llamar, la lista no le llega a
        nadie. Callarlo es peor que no tener el comando.
        """
        huerfana = Area.objects.create(institucion=self.inst, nombre="Imágenes")
        agenda2 = Agenda.objects.create(
            institucion=self.inst, area=huerfana, nombre="Tomógrafo", duracion_min=30
        )
        Disponibilidad.objects.create(
            agenda=agenda2, dia_semana=self.manana.weekday(), desde=time(8, 0), hasta=time(9, 0)
        )
        c = Ciudadano.objects.create(institucion=self.inst, nombre="Dani", apellido="T")
        motor.reservar(agenda2, c, self._hora(8, 0))

        salida, errores = self._correr()
        self.assertIn("SIN DESTINATARIO", errores)
        self.assertIn("Imágenes", errores)
        self.assertIn("1 sin destinatario", salida)

    def test_un_turno_sin_destinatario_no_queda_marcado_como_recordado(self):
        """
        Marcarlo daría por recordado algo que nadie va a llamar, y el dato con
        el que se mide el efecto del recordatorio quedaría mintiendo.
        """
        huerfana = Area.objects.create(institucion=self.inst, nombre="Imágenes")
        agenda2 = Agenda.objects.create(
            institucion=self.inst, area=huerfana, nombre="Tomógrafo", duracion_min=30
        )
        Disponibilidad.objects.create(
            agenda=agenda2, dia_semana=self.manana.weekday(), desde=time(8, 0), hasta=time(9, 0)
        )
        c = Ciudadano.objects.create(institucion=self.inst, nombre="Dani", apellido="T")
        t = motor.reservar(agenda2, c, self._hora(8, 0))

        self._correr()
        t.refresh_from_db()
        self.assertIsNone(t.recordado_at, "quedó recordado sin que nadie lo vaya a llamar")
        # Y los que sí tienen mostrador, sí.
        self.turnos[0].refresh_from_db()
        self.assertIsNotNone(self.turnos[0].recordado_at)

    def test_sin_turnos_no_avisa_nada(self):
        Turno.objects.all().delete()
        salida, _ = self._correr()
        self.assertIn("Sin turnos por confirmar", salida)
        self.assertEqual(Notificacion.objects.count(), 0)
