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


class IndicadorAusentismoTests(TestCase):
    """
    El ausentismo es el número con el que se decide si hay que sobreturnear o
    llamar más. Que esté mal no se nota —siempre da algo verosímil— así que las
    dos formas de estropearlo tienen su test.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        self.user = Usuario.objects.create_user(
            "jefe@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suárez", duracion_min=20
        )
        self.ayer = timezone.localdate() - timedelta(days=1)
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=self.ayer.weekday(),
            desde=time(8, 0), hasta=time(16, 0),
        )

    def _turno(self, minuto, estado):
        from datetime import datetime

        c = Ciudadano.objects.create(institucion=self.inst, nombre=f"P{minuto}", apellido="T")
        inicio = timezone.make_aware(
            datetime.combine(self.ayer, time(8, 0)), timezone.get_current_timezone()
        ) + timedelta(minutes=minuto)
        t = motor.reservar(self.agenda, c, inicio)
        if estado != Turno.Estado.RESERVADO:
            t.estado = estado
            t.save(update_fields=["estado"])
        return t

    def _resumen(self):
        r = self.client.get(f"/api/instituciones/{self.inst.id}/tablero/?dias=7")
        return r.data["resumen"]

    def test_el_ausentismo_sale_sobre_los_turnos_con_desenlace(self):
        for i in range(8):
            self._turno(i * 20, Turno.Estado.PRESENTE)
        for i in range(8, 10):
            self._turno(i * 20, Turno.Estado.AUSENTE)
        self.assertEqual(self._resumen()["ausentismo"], 20)

    def test_los_cancelados_no_cuentan_como_ausentes(self):
        """
        El que avisó con tiempo liberó el horario y se pudo reasignar. Contarlo
        como ausente diría que el servicio pierde horas que en realidad usó.
        """
        for i in range(8):
            self._turno(i * 20, Turno.Estado.PRESENTE)
        for i in range(8, 10):
            self._turno(i * 20, Turno.Estado.AUSENTE)
        for i in range(10, 12):
            self._turno(i * 20, Turno.Estado.CANCELADO)
        r = self._resumen()
        self.assertEqual(r["ausentismo"], 20, "los cancelados entraron en la cuenta")
        self.assertEqual(r["turnos_cancelados"], 2)

    def test_los_sin_registrar_se_cuentan_aparte_y_no_inflan_el_ausentismo(self):
        """
        Un turno que pasó y nadie resolvió puede ser alguien que vino y nadie
        registró. Meterlo en ausentes haría que el número suba con el desorden
        administrativo en vez de con la gente que faltó.
        """
        for i in range(8):
            self._turno(i * 20, Turno.Estado.PRESENTE)
        for i in range(8, 10):
            self._turno(i * 20, Turno.Estado.AUSENTE)
        for i in range(10, 14):
            self._turno(i * 20, Turno.Estado.RESERVADO)  # nadie los cerró
        r = self._resumen()
        self.assertEqual(r["ausentismo"], 20, "los sin registrar inflaron el ausentismo")
        self.assertEqual(r["turnos_sin_registrar"], 4, "y tienen que verse, para que alguien los cierre")

    def test_los_turnos_futuros_no_entran_en_el_ausentismo(self):
        """Todavía no faltó nadie: sólo tiene sentido sobre lo que ya pasó."""
        manana = timezone.localdate() + timedelta(days=1)
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=manana.weekday(), desde=time(8, 0), hasta=time(16, 0)
        )
        from datetime import datetime

        for i in range(6):
            c = Ciudadano.objects.create(institucion=self.inst, nombre=f"F{i}", apellido="T")
            motor.reservar(self.agenda, c, timezone.make_aware(
                datetime.combine(manana, time(8, 0)), timezone.get_current_timezone()
            ) + timedelta(minutes=i * 20))
        self._turno(0, Turno.Estado.AUSENTE)
        r = self._resumen()
        self.assertEqual(r["ausentismo"], 100, "un ausente sobre un resuelto")
        self.assertEqual(r["turnos_sin_registrar"], 0, "los futuros no son «sin registrar»")

    def test_sin_turnos_no_divide_por_cero(self):
        self.assertEqual(self._resumen()["ausentismo"], 0)
