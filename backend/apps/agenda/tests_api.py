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

from .models import Agenda, Bloqueo, Disponibilidad, Turno


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

    def test_se_buscan_los_turnos_futuros_de_una_persona_en_todas_las_agendas(self):
        """
        Es la consulta que hace la pantalla cuando alguien llama para cancelar:
        no sabe el día ni si es Suárez o Gómez, así que se busca por documento
        sobre TODAS las agendas y de hoy en adelante.

        Si la búsqueda dejara de combinarse con el rango, la lista se llenaría de
        turnos viejos —que no se pueden cancelar— y el que la persona tiene en la
        mano quedaría abajo de todo; si dejara de cruzar agendas, se vuelve a
        tener que adivinar cuál era, que es de dónde salió este endpoint.
        """
        self._dar(8, 0)
        otra = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dr. Gómez", duracion_min=30
        )
        Disponibilidad.objects.create(
            agenda=otra, dia_semana=1, desde=time(11, 0), hasta=time(12, 0)
        )
        r = self.client.post("/api/turnos/", {
            "agenda": otra.id, "ciudadano": self.paciente.id, "inicio": self._iso(11, 0),
        })
        self.assertEqual(r.status_code, 201, r.data)

        # Un turno viejo de la misma persona: no se cancela ni se confirma.
        Turno.objects.create(
            agenda=self.agenda, ciudadano=self.paciente, duracion_min=20,
            inicio=timezone.now() - timedelta(days=30),
        )

        r = self.client.get(
            f"/api/turnos/?search=30111222&desde={timezone.localdate()}&ordering=inicio"
        )
        self.assertEqual(r.data["count"], 2, r.data)
        self.assertEqual(
            [t["agenda_nombre"] for t in r.data["results"]], ["Dra. Suárez", "Dr. Gómez"]
        )


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


class ModalidadAPITests(APITestCase):
    """
    La modalidad por HTTP: al dar el turno, y al pasarlo a video despues.

    Con setUp propio y no heredando de `AgendaAPITests`: subclasificarla vuelve a
    correr sus treinta y dos tests, y la suite de agenda ya tarda dos minutos.
    """

    def setUp(self):
        self.user = Usuario.objects.create_user(
            "modalidad@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiologia")
        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Dra. Suarez",
            duracion_min=20, sobreturnos_max=2,
        )
        Disponibilidad.objects.create(
            agenda=self.agenda, dia_semana=1, desde=time(8, 0), hasta=time(10, 0)
        )
        self.martes = un_martes()
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Perez", documento="30111222"
        )

    def _dar(self, **extra):
        inicio = timezone.make_aware(
            datetime.combine(self.martes, time(8, 0)), timezone.get_current_timezone()
        )
        return self.client.post("/api/turnos/", {
            "agenda": self.agenda.id, "ciudadano": self.paciente.id,
            "inicio": inicio.isoformat(), **extra,
        })

    def test_da_un_turno_virtual_en_una_agenda_mixta(self):
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.enlace_virtual = "https://sala.example.com/suarez"
        self.agenda.save()
        r = self._dar(modalidad="virtual")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["modalidad"], "virtual")
        self.assertEqual(r.data["enlace"], "https://sala.example.com/suarez")

    def test_un_turno_virtual_en_una_agenda_presencial_es_400(self):
        r = self._dar(modalidad="virtual")
        self.assertEqual(r.status_code, 400, r.data)

    def test_la_accion_pasa_el_turno_a_virtual_con_su_propia_sala(self):
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.save()
        turno_id = self._dar().data["id"]
        r = self.client.post("/api/turnos/%s/modalidad/" % turno_id, {
            "modalidad": "virtual", "enlace": "https://sala.example.com/ana",
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["modalidad"], "virtual")
        self.assertEqual(r.data["enlace"], "https://sala.example.com/ana")

    def test_una_modalidad_inventada_es_400_y_no_toca_el_turno(self):
        turno_id = self._dar().data["id"]
        r = self.client.post("/api/turnos/%s/modalidad/" % turno_id, {"modalidad": "telepatia"})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Turno.objects.get(pk=turno_id).modalidad, "presencial")

    def test_por_patch_no_se_cambia_la_modalidad(self):
        """
        Por PATCH quedaba un turno «virtual» sin enlace en una agenda que solo
        atiende en el consultorio: el paciente no viene y espera una llamada que
        nadie va a hacer.
        """
        turno_id = self._dar().data["id"]
        r = self.client.patch("/api/turnos/%s/" % turno_id,
                              {"modalidad": "virtual", "enlace": "https://x.example.com/"})
        self.assertEqual(r.status_code, 200, r.data)
        t = Turno.objects.get(pk=turno_id)
        self.assertEqual(t.modalidad, "presencial")
        self.assertEqual(t.enlace, "")

    def test_pasar_la_agenda_a_presencial_le_saca_la_sala(self):
        """Si no, el dia que vuelva a virtual hereda un link que nadie eligio."""
        self.agenda.modalidad = Agenda.Modalidad.VIRTUAL
        self.agenda.enlace_virtual = "https://sala.example.com/suarez"
        self.agenda.save()
        r = self.client.patch("/api/agendas/%s/" % self.agenda.id, {"modalidad": "presencial"})
        self.assertEqual(r.status_code, 200, r.data)
        self.agenda.refresh_from_db()
        self.assertEqual(self.agenda.enlace_virtual, "")

    def test_el_turno_informa_la_modalidad_de_su_agenda(self):
        """La pantalla que atiende el telefono decide con esto si ofrece el pase."""
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.save()
        turno_id = self._dar().data["id"]
        r = self.client.get("/api/turnos/%s/" % turno_id)
        self.assertEqual(r.data["agenda_modalidad"], "mixta")

    def test_la_grilla_del_dia_informa_la_modalidad(self):
        self.agenda.modalidad = Agenda.Modalidad.MIXTA
        self.agenda.save()
        r = self.client.get(
            "/api/agendas/%s/dia/?fecha=%s" % (self.agenda.id, self.martes.isoformat())
        )
        self.assertEqual(r.data["agenda"]["modalidad"], "mixta")


class FranjasAPITests(APITestCase):
    """
    Las franjas por HTTP: es lo que manda el editor grafico del horario semanal.

    setUp propio y no herencia de `AgendaAPITests`: subclasificarla vuelve a
    correr sus treinta y dos tests.
    """

    def setUp(self):
        self.user = Usuario.objects.create_user(
            "franjas@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Vacunatorio")
        self.agenda = Agenda.objects.create(
            institucion=self.inst, area=self.area, nombre="Vacunatorio",
            duracion_min=20, sobreturnos_max=2,
        )
        self.martes = un_martes()

    def _franja(self, **extra):
        cuerpo = {"agenda": self.agenda.id, "dia_semana": 1, "desde": "10:00", "hasta": "12:00"}
        cuerpo.update(extra)
        # JSON, como manda la pantalla. Con el formulario multipart del cliente de
        # pruebas, DRF trata el `activa` ausente como el checkbox desmarcado de un
        # form HTML y la franja nace inactiva: el test pasaba a verde por un
        # camino que el frontend no usa.
        return self.client.post("/api/disponibilidades/", cuerpo, format="json")

    def test_dos_franjas_del_mismo_dia_con_duraciones_distintas(self):
        """
        Lunes de 10 a 12 con turnos de 30 y de 13 a 17 con turnos de 20: es la
        agenda real de un profesional, y es lo que el formulario viejo no dejaba
        cargar.
        """
        a = self._franja(dia_semana=0, desde="10:00", hasta="12:00", duracion_min=30)
        b = self._franja(dia_semana=0, desde="13:00", hasta="17:00", duracion_min=20)
        self.assertEqual(a.status_code, 201, a.data)
        self.assertEqual(b.status_code, 201, b.data)
        self.assertEqual(a.data["cuantos_turnos"], 4)
        self.assertEqual(b.data["cuantos_turnos"], 12)

    def test_una_franja_que_se_pisa_con_otra_es_400(self):
        """
        Donde dos franjas se solapan, la grilla usa una sola y la otra no da
        ningun turno: la agenda ofrece algo distinto de lo que la pantalla de
        configuracion muestra.
        """
        self._franja(desde="10:00", hasta="12:00")
        r = self._franja(desde="11:00", hasta="13:00")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("10:00", str(r.data))

    def test_pegadas_no_se_pisan(self):
        """De 10 a 12 y de 12 a 14 es lo normal, no un choque."""
        self._franja(desde="10:00", hasta="12:00")
        r = self._franja(desde="12:00", hasta="14:00")
        self.assertEqual(r.status_code, 201, r.data)

    def test_el_mismo_horario_en_otro_dia_no_se_pisa(self):
        self._franja(dia_semana=1)
        r = self._franja(dia_semana=2)
        self.assertEqual(r.status_code, 201, r.data)

    def test_el_horario_nuevo_puede_convivir_con_el_viejo_por_vigencia(self):
        """
        Es para lo que existe la vigencia: cargar el horario que rige desde marzo
        sin borrar el que rige hasta febrero, que es el que sostiene los turnos ya
        dados.
        """
        self._franja(desde="10:00", hasta="12:00", vigente_hasta="2026-02-28")
        r = self._franja(desde="09:00", hasta="13:00", vigente_desde="2026-03-01")
        self.assertEqual(r.status_code, 201, r.data)

    def test_cero_cupos_se_rechaza(self):
        """Una franja que se dibuja y no da ningun turno: para eso esta «inactiva»."""
        r = self._franja(cupos=0)
        self.assertEqual(r.status_code, 400, r.data)

    def test_la_franja_editada_no_choca_consigo_misma(self):
        f = self._franja(desde="10:00", hasta="12:00").data
        r = self.client.patch(f"/api/disponibilidades/{f['id']}/", {"hasta": "13:00"},
                              format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["cuantos_turnos"], 9)

    def test_la_grilla_de_la_semana_arranca_siempre_en_lunes(self):
        """Una semana que empieza un miercoles no se puede comparar con la de al lado."""
        self._franja(dia_semana=1, cupos=3)
        r = self.client.get(f"/api/agendas/{self.agenda.id}/semana/?desde={self.martes}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["dias"]), 7)
        self.assertEqual(str(r.data["desde"]), str(self.martes - timedelta(days=1)))
        martes = r.data["dias"][1]
        self.assertEqual(martes["horarios"][0]["cupos"], 3)
        self.assertEqual(martes["horarios"][0]["libres"], 3)

    def test_los_bloqueos_se_filtran_por_rango(self):
        """
        La pantalla de la semana los dibuja encima de la grilla: sin el filtro
        tendria que traerse todas las vacaciones de la historia de la agenda.
        Cuenta el bloqueo que TOCA la semana, no solo el que empieza adentro.
        """
        inicio = timezone.make_aware(
            datetime.combine(self.martes - timedelta(days=4), time(8, 0)),
            timezone.get_current_timezone(),
        )
        Bloqueo.objects.create(
            agenda=self.agenda, desde=inicio, hasta=inicio + timedelta(days=6), motivo="Congreso"
        )
        lunes = self.martes - timedelta(days=1)
        r = self.client.get(
            f"/api/bloqueos-agenda/?agenda={self.agenda.id}&desde={lunes}"
            f"&hasta={lunes + timedelta(days=6)}"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["count"], 1)

        # Una semana posterior al bloqueo no lo trae.
        lejos = lunes + timedelta(days=28)
        r2 = self.client.get(
            f"/api/bloqueos-agenda/?agenda={self.agenda.id}&desde={lejos}"
            f"&hasta={lejos + timedelta(days=6)}"
        )
        self.assertEqual(r2.data["count"], 0)
