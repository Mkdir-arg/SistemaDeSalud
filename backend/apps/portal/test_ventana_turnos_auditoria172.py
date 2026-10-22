"""AUD-049: política del paciente aplicada a la fila y al reloj bajo lock."""
from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Event, current_thread, main_thread
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.agenda import motor
from apps.agenda.models import Agenda, Disponibilidad, Turno
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import CuentaPaciente
from .tests_red import RedBase
from .tokens import abrir_sesion


class VentanaPortalTests(RedBase):
    def test_cancelar_exactamente_24_horas_se_lista_y_se_permite(self):
        with patch("django.utils.timezone.now", return_value=timezone.now()):
            api = self.cliente(self.cuenta_)
            turno = self.turno(self.en_central, 24)
            listado = api.get("/api/mi/turnos/")
            self.assertTrue(listado.data["turnos"][0]["puede_cancelar"])
            respuesta = api.post(f"/api/mi/turnos/{turno.pk}/cancelar/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Turno.Estado.CANCELADO)

    def test_cancelar_un_microsegundo_antes_del_limite_se_rechaza(self):
        ahora = timezone.now()
        with patch("django.utils.timezone.now", return_value=ahora):
            api = self.cliente(self.cuenta_)
            turno = self.turno(self.en_central, 24)
            turno.inicio -= timedelta(microseconds=1)
            turno.save(update_fields=["inicio"])
            respuesta = api.post(f"/api/mi/turnos/{turno.pk}/cancelar/")
        self.assertEqual((respuesta.status_code, respuesta.data["codigo"]), (409, "no_cancelable"))
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Turno.Estado.RESERVADO)

    def test_motor_portal_no_confirma_al_llegar_la_hora(self):
        turno = self.turno(self.en_central, 1)
        with patch("django.utils.timezone.now", return_value=turno.inicio):
            with self.assertRaises(motor.ErrorAgenda):
                motor.confirmar(turno, via=Turno.Via.PORTAL)
        turno.refresh_from_db()
        self.assertEqual(turno.estado, Turno.Estado.RESERVADO)

    def test_mostrador_conserva_cancelacion_cercana_y_confirmacion_pasada(self):
        cercano = self.turno(self.en_central, 1)
        pasado = self.turno(self.en_norte, -1)
        self.assertEqual(motor.cancelar(cercano).estado, Turno.Estado.CANCELADO)
        self.assertEqual(motor.confirmar(pasado).estado, Turno.Estado.CONFIRMADO)


@skipUnless(connection.vendor == "postgresql", "La carrera requiere locks PostgreSQL reales.")
class VentanaPortalConcurrenteTests(TransactionTestCase):
    def setUp(self):
        self.ahora = timezone.now().replace(minute=0, second=0, microsecond=0)
        inst = Institucion.objects.create(nombre="AUD172 ventana ficticia")
        area = Area.objects.create(institucion=inst, nombre="Clínica ficticia")
        self.agenda = Agenda.objects.create(institucion=inst, area=area, nombre="Agenda ficticia")
        ciudadano = Ciudadano.objects.create(
            institucion=inst, documento="34343434", nombre="Persona", apellido="Ficticia",
        )
        cuenta = CuentaPaciente.objects.create(
            email="ventana-aud172@example.test", documento=ciudadano.documento,
            sexo="F", identidad="validada", identidad_via="renaper",
            identidad_validada_at=self.ahora, email_verificado_at=self.ahora,
        )
        with patch("django.utils.timezone.now", return_value=self.ahora):
            _, self.acceso, _ = abrir_sesion(cuenta)
        self.turno = Turno.objects.create(
            agenda=self.agenda, ciudadano=ciudadano, inicio=self.ahora + timedelta(hours=48),
        )

    def _carrera(self, accion, horas, adelantar_reloj=0):
        nuevo_inicio = self.ahora + timedelta(hours=horas)
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=timezone.localtime(nuevo_inicio).weekday(),
            desde=time(0), hasta=time(23, 59), duracion_min=20,
        )
        llego_al_lock = Event()
        original = motor._bajo_candado
        reloj = [self.ahora]

        def bajo_candado(turno):
            if current_thread() is not main_thread():
                llego_al_lock.set()
            return original(turno)

        def peticion():
            connections.close_all()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                api = APIClient()
                api.credentials(HTTP_AUTHORIZATION=f"Bearer {self.acceso}")
                return api.post(f"/api/mi/turnos/{self.turno.pk}/{accion}/")
            finally:
                connections.close_all()

        with patch("django.utils.timezone.now", side_effect=lambda: reloj[0]), patch.object(
            motor, "_bajo_candado", side_effect=bajo_candado,
        ), ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                # La API ve el horario anterior ya persistido; espera el lock que
                # conserva esta reprogramación real todavía sin commit.
                motor.reprogramar(self.turno, nuevo_inicio)
                futuro = pool.submit(peticion)
                self.assertTrue(llego_al_lock.wait(5), "La petición no llegó al lock del turno.")
                reloj[0] += timedelta(hours=adelantar_reloj)
            respuesta = futuro.result(timeout=10)
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        codigo = "no_cancelable" if accion == "cancelar" else "no_confirmable"
        self.assertEqual(respuesta.data.get("codigo"), codigo)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.inicio, nuevo_inicio)
        self.assertEqual(self.turno.estado, Turno.Estado.RESERVADO)
        self.assertIsNone(self.turno.cancelado_at)
        self.assertIsNone(self.turno.recordado_at)

    def test_reprogramacion_a_23_horas_impide_cancelacion_portal(self):
        self._carrera("cancelar", 23)

    def test_reloj_tras_esperar_reprogramacion_impide_confirmar_turno_pasado(self):
        self._carrera("confirmar", 1, adelantar_reloj=2)
