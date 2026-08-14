"""
Que una falla silenciosa deje de ser silenciosa.

Los dos casos que se cubren acá son de los que nadie descubre mirando la
pantalla: la aplicación no llega a la base pero contesta HTTP igual, y el reloj
del motor se muere sin que nada cambie de aspecto.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria import latidos
from apps.auditoria.latidos import Latido
from apps.instituciones.models import Area, Institucion


class HealthTests(APITestCase):
    """
    El chequeo que mira la base.

    Antes devolvía `ok` sin comprobar nada: el balanceador veía verde mientras
    la aplicación no llegaba a Postgres, le seguía mandando gente, y nadie
    recibía una alarma porque la sonda estaba conforme.
    """

    def test_con_la_base_viva_responde_ok(self):
        r = self.client.get("/api/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_no_pide_credenciales(self):
        """Una sonda de infraestructura no tramita usuarios."""
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/health/").status_code, 200)

    def test_si_la_base_no_responde_devuelve_503(self):
        with patch("django.db.connection.cursor", side_effect=Exception("sin conexión")):
            r = self.client.get("/api/health/")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["status"], "error")

    def test_no_cuenta_qué_falló(self):
        """Se sirve sin sesión: el detalle iría a cualquiera que pase."""
        with patch("django.db.connection.cursor", side_effect=Exception("password authentication failed")):
            cuerpo = self.client.get("/api/health/").content.decode()
        self.assertNotIn("password", cuerpo)


class LatidoTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user("jefe@test.local", "x")
        Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol="admin", activo=True
        )
        self.client.force_authenticate(self.user)

    def _viejo(self, servicio, segundos):
        Latido.objects.filter(servicio=servicio).update(
            momento=timezone.now() - timedelta(seconds=segundos)
        )

    # --- el latido ------------------------------------------------------- #
    def test_el_reloj_deja_su_latido_al_terminar(self):
        call_command("correr_tiempos", stdout=StringIO())
        self.assertTrue(Latido.objects.filter(servicio="correr_tiempos").exists())

    def test_en_seco_no_late(self):
        """
        Una corrida en seco no hizo el trabajo. Dejar el latido diría que el
        reloj está al día cuando no reactivó nada.
        """
        call_command("correr_tiempos", "--seco", stdout=StringIO())
        self.assertFalse(Latido.objects.filter(servicio="correr_tiempos").exists())

    def test_el_latido_guarda_qué_hizo(self):
        call_command("correr_tiempos", stdout=StringIO())
        self.assertIn("espera", Latido.objects.get(servicio="correr_tiempos").detalle)

    def test_hay_una_sola_fila_por_servicio(self):
        """
        Lo que se pregunta es «¿sigue vivo?». Un histórico de cada pasada serían
        millones de filas para contestar algo que se lee de la última.
        """
        for _ in range(3):
            call_command("correr_tiempos", stdout=StringIO())
        self.assertEqual(Latido.objects.filter(servicio="correr_tiempos").count(), 1)

    def test_que_falle_el_latido_no_frena_al_reloj(self):
        """
        Al revés sería absurdo: el registro existe para que el reloj no muera en
        silencio, no para poder matarlo.
        """
        with patch("apps.auditoria.latidos.Latido.objects.update_or_create",
                   side_effect=Exception("tabla bloqueada")):
            call_command("correr_tiempos", stdout=StringIO())  # no explota

    # --- el estado ------------------------------------------------------- #
    def test_sin_haber_corrido_nunca_no_es_lo_mismo_que_atrasado(self):
        """
        Un sistema recién instalado todavía no corrió nada. Confundirlo con un
        proceso muerto haría que la primera alarma de su vida sea falsa.
        """
        d = latidos.estado()
        self.assertEqual(d["servicios"]["correr_tiempos"]["estado"], "nunca")
        self.assertEqual(d["atrasados"], [])

    def test_un_proceso_reciente_está_al_día(self):
        call_command("correr_tiempos", stdout=StringIO())
        self.assertEqual(latidos.estado()["servicios"]["correr_tiempos"]["estado"], "al día")

    def test_un_reloj_que_se_murió_aparece_atrasado(self):
        call_command("correr_tiempos", stdout=StringIO())
        self._viejo("correr_tiempos", latidos.ESPERADOS["correr_tiempos"] + 60)
        d = latidos.estado()
        self.assertEqual(d["servicios"]["correr_tiempos"]["estado"], "atrasado")
        self.assertIn("correr_tiempos", d["atrasados"])

    def test_el_margen_es_generoso(self):
        """
        Un monitor que grita porque una pasada se atrasó treinta segundos enseña
        a ignorar la alarma, y entonces no sirve el día que el proceso se muere.
        """
        call_command("correr_tiempos", stdout=StringIO())
        self._viejo("correr_tiempos", 5 * 60)  # el reloj corre cada 2 minutos
        self.assertEqual(latidos.estado()["atrasados"], [])

    def test_un_proceso_sin_nada_que_hacer_igual_late(self):
        """
        No tener trabajo es haber corrido bien. `recordar_turnos` salía temprano
        cuando no había turnos y no dejaba rastro: el monitor lo daba por muerto
        justo cuando estaba sano, que es la falsa alarma que enseña a ignorar
        las alarmas de verdad.
        """
        from apps.agenda.models import Turno

        self.assertFalse(Turno.objects.exists(), "el test necesita la agenda vacía")
        call_command("recordar_turnos", stdout=StringIO())
        self.assertTrue(Latido.objects.filter(servicio="recordar_turnos").exists())

    def test_todo_proceso_periódico_está_vigilado(self):
        """
        Un proceso que corre solo y no está en esta lista puede morirse sin que
        nadie lo note, que es exactamente lo que este archivo existe para
        evitar.
        """
        for servicio in ("correr_tiempos", "recordar_turnos", "alertar_saturacion", "respaldar"):
            with self.subTest(servicio=servicio):
                self.assertIn(servicio, latidos.ESPERADOS)

    # --- el endpoint ----------------------------------------------------- #
    def test_estado_pide_sesión(self):
        """Dice cómo anda el sistema por dentro: no va abierto como `health`."""
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/estado/").status_code, (401, 403))

    def test_estado_devuelve_200_cuando_todo_está_al_día(self):
        call_command("correr_tiempos", stdout=StringIO())
        self.assertEqual(self.client.get("/api/estado/").status_code, 200)

    def test_estado_devuelve_503_con_algo_atrasado(self):
        """
        Para que un monitor externo lo mire sin tener que interpretar el cuerpo.
        """
        call_command("correr_tiempos", stdout=StringIO())
        self._viejo("correr_tiempos", latidos.ESPERADOS["correr_tiempos"] + 60)
        r = self.client.get("/api/estado/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("correr_tiempos", r.data["atrasados"])
