"""
Agenda por HTTP.

Los tests del motor llaman a las funciones. Estos pegan a las rutas tal como las
arma la pantalla: en la fase anterior una acción quedó declarada dentro del
viewset equivocado y los tests del motor no lo vieron —existía la ruta en otro
recurso y la que usaba el frontend daba 404—.
"""
from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import Agenda, Disponibilidad, Turno


def un_martes(semanas=1):
    d = timezone.localdate() + timedelta(days=7 * semanas)
    return d + timedelta(days=(1 - d.weekday()) % 7)


class AgendaAPITests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            "adm@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Consulta")
        ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1, estado="publicada")
        ini = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        aten = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        fin = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=ver, origen=ini, destino=aten)
        Conexion.objects.create(version=ver, origen=aten, destino=fin)

        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suárez",
            duracion_min=20, sobreturnos_max=2, flujo=self.flujo, profesional=self.user,
        )
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=1, desde=time(8, 0), hasta=time(10, 0)
        )
        self.martes = un_martes()
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="30111222"
        )

    def _iso(self, h, m=0):
        return timezone.make_aware(
            datetime.combine(self.martes, time(h, m)), timezone.get_current_timezone()
        ).isoformat()

    def _dar(self, h=8, m=0, **extra):
        return self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": self.paciente.id,
            "inicio": self._iso(h, m), **extra,
        })

    # --- Grilla -------------------------------------------------------------- #

    def test_la_grilla_del_dia(self):
        r = self.client.get(f"/api/agendas/{self.agenda.id}/dia/?fecha={self.martes}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["horarios"]), 6)
        self.assertFalse(r.data["horarios"][0]["ocupado"])

    def test_la_grilla_muestra_quien_ocupa_cada_horario(self):
        self._dar()
        r = self.client.get(f"/api/agendas/{self.agenda.id}/dia/?fecha={self.martes}")
        self.assertTrue(r.data["horarios"][0]["ocupado"])
        self.assertEqual(r.data["horarios"][0]["paciente"], "Ana Pérez")

    def test_los_proximos_libres(self):
        r = self.client.get(f"/api/agendas/{self.agenda.id}/proximos-libres/?cuantos=3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["horarios"]), 3)

    # --- Reserva -------------------------------------------------------------- #

    def test_dar_un_turno(self):
        r = self._dar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "reservado")
        self.assertEqual(r.data["paciente"], "Ana Pérez")

    def test_un_horario_tomado_lo_dice_y_ofrece_el_sobreturno(self):
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        self._dar()
        r = self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": otro.id, "inicio": self._iso(8, 0),
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("sobreturno", r.data["detail"])

    def test_dar_un_sobreturno(self):
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Beto", apellido="T")
        self._dar()
        r = self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": otro.id,
            "inicio": self._iso(8, 0), "sobreturno": True,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["sobreturno"])

    def test_sin_horario_lo_dice(self):
        r = self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": self.paciente.id,
        })
        self.assertEqual(r.status_code, 400)

    # --- Acciones ------------------------------------------------------------- #

    def test_las_acciones_existen_donde_las_pide_la_pantalla(self):
        """
        Guarda contra el error que ya pasó una vez: una acción declarada dentro
        del viewset equivocado. Existía la ruta en otro recurso y la que usaba
        el frontend daba 404.
        """
        t = self._dar().data["id"]
        for ruta in ["confirmar", "llegada", "cancelar", "ausente"]:
            with self.subTest(accion=ruta):
                r = self.client.post(f"/api/turnos/{t}/{ruta}/")
                self.assertNotEqual(r.status_code, 404, f"/api/turnos/{{id}}/{ruta}/ no existe")

    def test_registrar_la_llegada_abre_el_caso(self):
        t = self._dar().data["id"]
        r = self.client.post(f"/api/turnos/{t}/llegada/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["estado"], "presente")
        self.assertIsNotNone(r.data["caso"])

    def test_cancelar_libera_el_horario(self):
        t = self._dar().data["id"]
        self.client.post(f"/api/turnos/{t}/cancelar/", {"motivo": "no puede"})
        r = self.client.get(f"/api/agendas/{self.agenda.id}/dia/?fecha={self.martes}")
        self.assertFalse(r.data["horarios"][0]["ocupado"])

    def test_el_ausente_no_libera_el_horario(self):
        t = self._dar().data["id"]
        self.client.post(f"/api/turnos/{t}/ausente/")
        r = self.client.get(f"/api/agendas/{self.agenda.id}/dia/?fecha={self.martes}")
        self.assertTrue(r.data["horarios"][0]["ocupado"])

    def test_el_estado_no_se_cambia_por_patch(self):
        """
        Se mueve con las acciones, que además abren el caso o liberan el
        horario. Por PATCH se marcaría «presente» sin que exista el caso.
        """
        t = self._dar().data["id"]
        self.client.patch(f"/api/turnos/{t}/", {"estado": "presente"})
        self.assertEqual(Turno.objects.get(pk=t).estado, Turno.Estado.RESERVADO)

    def test_el_horario_no_se_mueve_por_patch(self):
        """
        Reprogramar es lo que más se pide después de dar el turno, y la primera
        implementación obvia —PATCH a `inicio`— salteaba la grilla, los
        bloqueos, el chequeo de ocupado y el candado: dejaba el turno a las 3 de
        la mañana de un día en que la agenda no atiende.
        """
        t = self._dar().data["id"]
        self.client.patch(f"/api/turnos/{t}/", {"inicio": self._iso(3, 0)})
        self.assertEqual(timezone.localtime(Turno.objects.get(pk=t).inicio).isoformat(), self._iso(8, 0))

    def test_el_turno_no_se_reasigna_a_otro_paciente_por_patch(self):
        """
        `ciudadano` no venía acotado a la institución: desde el Hospital A se
        podía apuntar el turno a un ciudadano del Hospital B, y la respuesta
        devolvía su nombre y su documento. Es justo lo que el scope por
        institución del resto de la API evita.
        """
        otra_inst = Institucion.objects.create(nombre="Hospital de otro lado")
        ajeno = Ciudadano.objects.create(
            institucion=otra_inst, nombre="Zoe", apellido="Ajena", documento="99888777"
        )
        t = self._dar().data["id"]
        r = self.client.patch(f"/api/turnos/{t}/", {"ciudadano": ajeno.id})
        self.assertEqual(Turno.objects.get(pk=t).ciudadano_id, self.paciente.id)
        self.assertNotEqual(r.data.get("documento"), "99888777")

    def test_un_turno_no_se_borra(self):
        """
        Borrarlo saca de la base la evidencia de un turno que se perdió, que es
        el dato con el que se calcula el ausentismo del servicio. El turno que
        no va se cancela.
        """
        t = self._dar().data["id"]
        r = self.client.delete(f"/api/turnos/{t}/")
        self.assertEqual(r.status_code, 405)
        self.assertTrue(Turno.objects.filter(pk=t).exists())

    def test_reprogramar_pasa_por_las_reglas_de_la_agenda(self):
        t = self._dar().data["id"]
        malo = self.client.post(f"/api/turnos/{t}/reprogramar/", {"inicio": self._iso(3, 0)})
        self.assertEqual(malo.status_code, 400, malo.data)
        bueno = self.client.post(f"/api/turnos/{t}/reprogramar/", {"inicio": self._iso(9, 0)})
        self.assertEqual(bueno.status_code, 200, bueno.data)
        self.assertEqual(timezone.localtime(Turno.objects.get(pk=t).inicio).isoformat(), self._iso(9, 0))

    def test_bloquear_devuelve_los_turnos_que_pisa(self):
        """
        Bloquear no cancela nada: los turnos siguen dados. Sin esta lista nadie
        se entera de que el bloqueo del día pisó doce turnos, y esos doce
        pacientes viajan al hospital para nada.
        """
        self._dar(8, 0)
        r = self.client.post("/api/bloqueos-agenda/", {
            "agenda": self.agenda.id, "desde": self._iso(8, 0), "hasta": self._iso(10, 0),
            "motivo": "El profesional no viene",
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data["turnos_afectados"]), 1)
        self.assertEqual(r.data["turnos_afectados"][0]["paciente"], "Ana Pérez")

    def test_la_grilla_de_un_dia_bloqueado_sigue_mostrando_los_turnos(self):
        """La pantalla decía «La agenda no atiende este día» con doce personas citadas."""
        self._dar(8, 0)
        self.client.post("/api/bloqueos-agenda/", {
            "agenda": self.agenda.id, "desde": self._iso(8, 0), "hasta": self._iso(10, 0),
        })
        r = self.client.get(f"/api/agendas/{self.agenda.id}/dia/?fecha={self.martes}")
        conturno = [h for h in r.data["horarios"] if h["ocupado"]]
        self.assertEqual(len(conturno), 1)
        self.assertTrue(conturno[0]["bloqueado"])

    def test_los_proximos_libres_arrancan_donde_se_pide(self):
        """
        Quien está mirando el 20 y necesita el siguiente hueco no quiere que le
        ofrezcan el de mañana.
        """
        desde = self.martes + timedelta(days=7)
        r = self.client.get(
            f"/api/agendas/{self.agenda.id}/proximos-libres/?cuantos=3&desde={desde}"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(all(timezone.localdate(h["inicio"]) >= desde for h in r.data["horarios"]))

    # --- Listados -------------------------------------------------------------- #

    def test_se_filtra_por_rango_de_fechas(self):
        """Así se mira una agenda: «la semana que viene», no todo el histórico."""
        self._dar()
        dentro = self.client.get(f"/api/turnos/?desde={self.martes}&hasta={self.martes}")
        fuera = self.client.get(
            f"/api/turnos/?desde={self.martes + timedelta(days=1)}"
        )
        self.assertEqual(dentro.data["count"], 1)
        self.assertEqual(fuera.data["count"], 0)

    def test_se_busca_por_documento(self):
        self._dar()
        r = self.client.get("/api/turnos/?search=30111222")
        self.assertEqual(r.data["count"], 1)


class AgendaPermisosTests(APITestCase):
    """Configurar la agenda y operarla son cosas distintas."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suárez"
        )
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=1, desde=time(8, 0), hasta=time(10, 0)
        )
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="T"
        )
        self.usuarios = {}
        for rol in ("admin", "administrativo", "configurador"):
            u = Usuario.objects.create_user(f"{rol}@test.local", "x")
            Membresia.objects.create(usuario=u, institucion=self.inst, rol=rol, activo=True)
            self.usuarios[rol] = u

    def _como(self, rol):
        self.client.force_authenticate(self.usuarios[rol])

    def test_el_administrativo_da_turnos(self):
        self._como("administrativo")
        martes = un_martes()
        inicio = timezone.make_aware(
            datetime.combine(martes, time(8, 0)), timezone.get_current_timezone()
        )
        r = self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": self.paciente.id, "inicio": inicio.isoformat(),
        })
        self.assertEqual(r.status_code, 201, r.data)

    def test_el_administrativo_no_crea_agendas(self):
        """Eso es configurar la institución, no operarla."""
        self._como("administrativo")
        r = self.client.post("/api/agendas/", {
            "institucion": self.inst.id, "area": self.area.id, "nombre": "Nueva",
        })
        self.assertEqual(r.status_code, 403)

    def test_el_admin_crea_agendas(self):
        self._como("admin")
        r = self.client.post("/api/agendas/", {
            "institucion": self.inst.id, "area": self.area.id, "nombre": "Nueva",
        })
        self.assertEqual(r.status_code, 201, r.data)

    def test_una_agenda_de_recurso_no_lleva_profesional(self):
        """Un caso abierto desde ahí no sabría a quién asignarse."""
        self._como("admin")
        r = self.client.post("/api/agendas/", {
            "institucion": self.inst.id, "area": self.area.id, "nombre": "Tomógrafo",
            "tipo": "recurso", "profesional": self.usuarios["admin"].id,
        })
        self.assertEqual(r.status_code, 400)
