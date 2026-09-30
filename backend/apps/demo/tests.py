"""Guarda de entorno, calendario relativo y carga completa del entorno de demo."""
import time
from datetime import date, datetime, timedelta
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command, get_commands
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso
from apps.finanzas.models import ConcesionFinanciera, Gasto, HechoAtencionCosteable, MovimientoDinero
from apps.financiadores.models import SolicitudAutorizacion
from apps.instituciones.models import Institucion
from apps.instituciones.puesta_en_marcha import pasos as pasos_de_puesta_en_marcha
from apps.registros import integridad
from apps.registros.models import HistoriaClinica

from .calendario import Calendario
from .claves import CLAVE_POR_DEFECTO
from .trabajo import INFORMATIVOS, trabajo_por_usuario

# Todos los comandos de carga ficticia, descubiertos y no listados a mano: uno
# nuevo que se olvide la guarda de entorno tiene que hacer fallar el test.
COMANDOS = sorted(nombre for nombre in get_commands() if nombre.startswith("seed_"))


def reloj(texto):
    return timezone.make_aware(datetime.fromisoformat(texto))


def reloj_corrido(texto):
    """El reloj en ese instante, pero que sigue corriendo, como el de la carga.

    Ver `seed_entorno_demo._reloj_en`: congelado o volviendo atrás, el sellado
    de la historia clínica —que encadena por hora de firma— se bifurca.
    """
    base, inicio = reloj(texto), time.monotonic()
    return patch("django.utils.timezone.now",
                 side_effect=lambda: base + timedelta(seconds=time.monotonic() - inicio))


class CalendarioTests(SimpleTestCase):
    def test_los_meses_terminan_en_el_actual_y_cruzan_el_anio(self):
        cal = Calendario(reloj("2027-02-10T12:00"))
        meses = cal.meses(12)
        self.assertEqual(meses[0], date(2026, 3, 1))
        self.assertEqual(meses[-1], date(2027, 2, 1))
        self.assertEqual(cal.mes(-2), date(2026, 12, 1))

    def test_los_meses_pasados_van_tal_cual(self):
        cal = Calendario(reloj("2026-10-01T09:00"))
        self.assertEqual(cal.instante(date(2026, 8, 25), 15), reloj("2026-08-25T15:00"))

    def test_el_dia_uno_todo_el_mes_nominal_cae_antes_de_ahora_y_en_orden(self):
        ahora = reloj("2026-10-01T09:00")
        cal = Calendario(ahora)
        # El componente del 13 a las 7 sigue siendo posterior a la atención del 5 a las 10.
        nominales = [(3, 12), (5, 10), (13, 7), (14, 16), (15, 8), (15, 10)]
        reales = [cal.instante(date(2026, 10, d), h) for d, h in nominales]
        self.assertEqual(reales, sorted(reales))
        self.assertEqual(len(set(reales)), len(reales))
        self.assertTrue(all(reloj("2026-10-01T00:00") <= r <= ahora for r in reales))

    def test_a_fin_de_mes_el_tramo_nominal_se_estira_hasta_ahora(self):
        ahora = reloj("2026-10-30T18:00")
        cal = Calendario(ahora)
        self.assertEqual(cal.instante(date(2026, 10, 15), 11), ahora)
        self.assertLess(cal.instante(date(2026, 10, 15), 9), ahora)
        self.assertGreater(cal.instante(date(2026, 10, 3), 12), reloj("2026-10-05T00:00"))

    def test_nunca_devuelve_el_futuro(self):
        ahora = reloj("2026-10-10T10:00")
        cal = Calendario(ahora)
        self.assertLessEqual(cal.instante(date(2026, 10, 15), 11), ahora)
        # Pasado el presente nominal no se colapsa en «ahora»: se rechaza.
        with self.assertRaises(ValueError):
            cal.instante(date(2026, 10, 28), 23)


class EntornoTests(TestCase):
    @override_settings(ENTORNO="produccion")
    def test_en_produccion_ningun_seed_escribe(self):
        self.assertIn("seed_entorno_demo", COMANDOS)
        self.assertGreaterEqual(len(COMANDOS), 10)
        for comando in COMANDOS:
            with self.subTest(comando=comando):
                parametros = {"interactive": False} if comando == "seed_entorno_demo" else {}
                with self.assertRaisesMessage(CommandError, "ENTORNO=produccion"):
                    call_command(comando, stdout=StringIO(), stderr=StringIO(), **parametros)
        self.assertFalse(Institucion.objects.exists())
        self.assertFalse(Usuario.objects.exists())

    def test_entorno_desconocido_no_arranca(self):
        from importlib import reload

        import config.settings as modulo
        with patch.dict("os.environ", {"ENTORNO": "produccíon"}):
            with self.assertRaisesMessage(RuntimeError, "ENTORNO"):
                reload(modulo)
        reload(modulo)


@skipUnless(connection.vendor == "postgresql", "La carga completa requiere PostgreSQL.")
class CargaCompletaTests(TransactionTestCase):
    """Una carga chica anclada en el peor día: el 1° del mes, temprano.

    Es el caso real de la demo: se carga días antes con `--ancla` a las 8 y se
    mira a las 9, que es cuando empieza.
    """

    ANCLA = "2026-10-01T08:00"
    AHORA = "2026-10-01T09:00"

    def cargar(self, **opciones):
        call_command("seed_entorno_demo", interactive=False, casos=40, dias=30, ancla=self.ANCLA,
                     stdout=StringIO(), **opciones)

    def cantidades(self):
        modelos = (Usuario, Institucion, Caso, Gasto, HechoAtencionCosteable, MovimientoDinero,
                   SolicitudAutorizacion, AccesoClinico)
        return {m.__name__: m.objects.count() for m in modelos}

    def test_carga_completa(self):
        with reloj_corrido(self.AHORA):
            self._verificar_carga_completa()

    def _verificar_carga_completa(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-de-prueba-65"}):
            self.cargar()
        ahora = timezone.now()
        mes = timezone.localdate().replace(day=1)
        self.assertEqual(mes, reloj(self.AHORA).date().replace(day=1))
        # La carga quedó en el ancla, no en la fecha real de la corrida.
        ultimo = Caso.objects.order_by("-creado").values_list("creado", flat=True).first()
        self.assertLess(abs(ultimo - reloj(self.ANCLA)), timedelta(minutes=30))

        # Nada queda en el futuro.
        futuros = list(Caso.objects.filter(creado__gt=ahora).values_list("pk", "institucion__nombre", "creado"))
        self.assertEqual(futuros, [])
        self.assertFalse(HechoAtencionCosteable.objects.filter(ocurrida_en__gt=ahora).exists())
        self.assertFalse(MovimientoDinero.objects.filter(fecha__gt=ahora.date()).exists())
        self.assertFalse(AccesoClinico.objects.filter(momento__gt=ahora).exists())

        # El mes en curso, que es el que abren las pantallas, tiene movimiento.
        self.assertTrue(Gasto.objects.filter(periodo_economico=mes, estado="aprobado").exists())
        self.assertTrue(Gasto.objects.filter(periodo_economico=mes, estado="pendiente_aprobacion").exists())
        self.assertTrue(HechoAtencionCosteable.objects.filter(ocurrida_en__date__gte=mes).exists())
        self.assertTrue(MovimientoDinero.objects.filter(fecha__gte=mes, tipo="cobro").exists())
        estados = set(SolicitudAutorizacion.objects.values_list("estado", flat=True))
        self.assertTrue({"pendiente", "observada", "aprobada", "rechazada"} <= estados)

        # Cada rol tiene al menos un usuario, y cada usuario algo que hacer o que ver.
        filas = trabajo_por_usuario()
        perfiles = {f["perfil"] for f in filas}
        for rol in Membresia.Rol.values:
            self.assertIn(rol, perfiles)
        for rol in ("admin", "operador", "auditor"):
            self.assertIn(f"financiador · {rol}", perfiles)
        # Los de consulta tienen algo que ver; los que operan, algo que HACER:
        # un conteo informativo no alcanza para decir que un rol tiene trabajo.
        sin_datos = [(f["email"], f["perfil"]) for f in filas if f["consulta"] and not f["trabajo"]]
        sin_trabajo = [(f["email"], f["perfil"]) for f in filas
                       if not f["consulta"] and not set(f["trabajo"]) - INFORMATIVOS]
        self.assertEqual(sin_datos, [])
        self.assertEqual(sin_trabajo, [])

        self._verificar_tablero_de_plataforma()
        self._verificar_comprador()
        self._verificar_central_completo()

        # Todos con la clave de DEMO_PASSWORD, también el superusuario.
        for usuario in Usuario.objects.all():
            self.assertTrue(usuario.check_password("clave-de-prueba-65"), usuario.email)

        # Una segunda carga deja exactamente lo mismo.
        antes = self.cantidades()
        with patch.dict("os.environ", {"DEMO_PASSWORD": ""}):
            self.cargar()
        self.assertEqual(self.cantidades(), antes)
        self.assertTrue(Usuario.objects.get(email="admin@salud.local").check_password(CLAVE_POR_DEFECTO))

    def _verificar_tablero_de_plataforma(self):
        """La primera pantalla de la plataforma muestra una red y no un hospital solo."""
        cliente = APIClient()
        cliente.force_authenticate(Usuario.objects.get(email="plataforma@salud.local"))
        tablero = cliente.get("/api/instituciones/tablero-plataforma/").json()
        self.assertEqual({a["tipo"] for a in tablero["alertas"]}, {"ocupacion", "puesta_en_marcha"})
        self.assertGreaterEqual(tablero["en_alta"], 2)
        nombres = dict(Institucion.objects.values_list("id", "nombre"))
        con_fila_hoy = {nombres[i["institucion"]] for i in tablero["indicadores"]
                        if i["atendidos_hoy"] and i["espera_minutos"] is not None}
        self.assertTrue({"Hospital Zonal Sur", "Clínica San Martín", "Centro de Salud Barrio Norte",
                         "Hospital Municipal de Villa Real"} <= con_fila_hoy, con_fila_hoy)
        # Las atenciones de los efectores se firman: la cadena de sellos tiene que verificar.
        rotas = [hc.pk for hc in HistoriaClinica.objects.filter(ciudadano__institucion__nombre="Hospital Zonal Sur")
                 if not integridad.verificar_historia(hc)["ok"]]
        self.assertEqual(rotas, [])

    def _verificar_central_completo(self):
        """Hospital Central tiene todo: finanzas del mes y el circuito de financiadores."""
        mes = timezone.localdate().replace(day=1)
        for nombre in ("Hospital Central", "Hospital General Los Aromos"):
            gastos = Gasto.objects.filter(institucion__nombre=nombre)
            self.assertTrue(gastos.filter(periodo_economico=mes, estado="aprobado").exists(), nombre)
            self.assertTrue(gastos.filter(estado="pendiente_aprobacion").exists(), nombre)
            self.assertTrue(MovimientoDinero.objects.filter(institucion__nombre=nombre, tipo="cobro").exists(), nombre)
        estados = set(SolicitudAutorizacion.objects.filter(institucion__nombre="Hospital Central")
                      .values_list("estado", flat=True))
        self.assertTrue({"pendiente", "observada", "aprobada", "rechazada"} <= estados)

    def _verificar_comprador(self):
        """Quien recibe la demo entra a todo y tiene su propia institución por configurar."""
        comprador = Usuario.objects.get(email="test@salud.local")
        roles = set(Membresia.objects.filter(usuario=comprador, institucion__nombre="Hospital Central")
                    .values_list("rol", flat=True))
        self.assertEqual(roles, set(Membresia.Rol.values))
        aromos = Membresia.objects.get(usuario=comprador, institucion__nombre="Hospital General Los Aromos")
        self.assertEqual(aromos.concesiones_financieras.count(), len(ConcesionFinanciera.Accion.values))
        self.assertTrue(comprador.notificaciones.filter(leida=False).exists())
        piloto = Institucion.objects.get(nombre="Hospital Piloto")
        self.assertEqual(piloto.estado, Institucion.Estado.EN_ALTA)
        pendientes = {paso for paso, hecho in pasos_de_puesta_en_marcha(piloto).items() if not hecho}
        self.assertEqual(pendientes, {"agenda_profesional", "agenda_recurso", "flujo_operativo"})

    def test_un_paso_que_falla_no_deja_la_base_a_medias(self):
        Institucion.objects.create(nombre="Datos previos")
        with patch("apps.casos.management.commands.seed_red.Command.handle", side_effect=RuntimeError("falla de prueba")):
            with self.assertRaisesMessage(CommandError, "seed_red falló"):
                self.cargar()
        self.assertEqual(list(Institucion.objects.values_list("nombre", flat=True)), ["Datos previos"])

    def test_ancla_invalida_no_toca_la_base(self):
        Institucion.objects.create(nombre="Datos previos")
        with self.assertRaisesMessage(CommandError, "no es una fecha"):
            call_command("seed_entorno_demo", interactive=False, ancla="el lunes", stdout=StringIO())
        self.assertEqual(Institucion.objects.count(), 1)
