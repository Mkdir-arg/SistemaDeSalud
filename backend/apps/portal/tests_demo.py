"""
La paciente del portal en la demo (#122).

`seed_portal_demo` sobre una Andrea Paniagua como la deja `seed_financiadores`:
lo que importa es que la cuenta entre al portal y vea, por la API real, el turno,
los dos estudios y la cobertura confirmada. Repetirlo no duplica nada.
"""
import shutil
import tempfile
from datetime import date, time, timedelta
from io import StringIO

from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.agenda.models import Agenda, Disponibilidad, Turno
from apps.casos.models import Caso, ItemFila
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.financiadores.models import Afiliado, Financiador, Plan, VinculoCiudadano
from apps.instituciones.models import Area, Institucion
from apps.registros.models import ArchivoClinico, Ciudadano, Estudio

from .demo import en_sala_de_espera, informe_pdf
from .management.commands.seed_portal_demo import DOCUMENTO, EMAIL
from .models import CuentaPaciente
from .tests import Base


class SeedPortalDemoTests(Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)

        central = Institucion.objects.create(nombre="Hospital Central")
        area = Area.objects.create(institucion=central, nombre="Cardiología")
        agenda = Agenda.objects.create(institucion=central, area=area, nombre="Dra. Méndez", duracion_min=20)
        Disponibilidad.objects.bulk_create(
            Disponibilidad(agenda=agenda, dia_semana=d, desde=time(8), hasta=time(12)) for d in range(7)
        )
        self.andrea = Ciudadano.objects.create(
            institucion=central, nombre="Andrea", apellido="Paniagua", documento=DOCUMENTO,
            fecha_nacimiento=date(1983, 11, 12),
        )
        mutual = Financiador.objects.create(nombre="Mutual del Valle", tipo="mutual")
        plan = Plan.objects.create(financiador=mutual, codigo="MV-INT", nombre="Plan Integral")
        afiliado = Afiliado.objects.create(
            financiador=mutual, documento=DOCUMENTO, numero="MV00011", nombre="Andrea Paniagua",
            plan=plan, desde=timezone.localdate() - timedelta(days=300),
        )
        admin = Usuario.objects.create_user("admin@salud.local", "x")
        VinculoCiudadano.objects.create(afiliado=afiliado, ciudadano=self.andrea, verificado_por=admin)

    def sembrar(self):
        call_command("seed_portal_demo", stdout=StringIO())
        return CuentaPaciente.objects.get(email=EMAIL)

    def test_la_cuenta_entra_y_ve_lo_mismo_que_el_hospital_y_el_financiador(self):
        cuenta = self.sembrar()
        self.assertTrue(cuenta.validada)
        self.assertEqual(cuenta.identidad_via, "")  # no pasó por RENAPER
        api = self.cliente(cuenta)

        turnos = api.get("/api/mi/turnos/").data["turnos"]
        self.assertEqual(len(turnos), 1)
        self.assertTrue(turnos[0]["puede_confirmar"] and turnos[0]["puede_cancelar"])
        self.assertGreater(Turno.objects.get().inicio - timezone.now(), timedelta(hours=24))

        resultados = api.get("/api/mi/resultados/").data["resultados"]
        self.assertEqual(
            sorted((r["tipo"], r["realizado"], r["descargable"]) for r in resultados),
            [("Hemograma completo", True, True), ("Radiografía de tórax", False, False)],
        )
        hecho = next(r for r in resultados if r["realizado"])
        archivo = api.get(f"/api/mi/resultados/{hecho['id']}/archivo/")
        self.assertEqual(archivo.status_code, 200)
        self.assertTrue(b"".join(archivo.streaming_content).startswith(b"%PDF-"))

        coberturas = api.get("/api/mi/cobertura/").data["coberturas"]
        self.assertEqual(
            [(c["financiador"], c["plan"], c["numero"], c["confirmada"]) for c in coberturas],
            [("Mutual del Valle", "Plan Integral", "MV00011", True)],
        )

    def test_repetirlo_no_duplica_nada(self):
        self.sembrar()
        self.sembrar()
        self.assertEqual(CuentaPaciente.objects.count(), 1)
        self.assertEqual(Turno.objects.count(), 1)
        self.assertEqual(Estudio.objects.count(), 2)

    def test_despues_de_un_ensayo_le_da_otro_turno_otro_dia(self):
        # En el ensayo confirmaron el turno: repetir la carga le da uno reservado
        # nuevo, aunque los primeros horarios libres caigan el mismo día.
        self.sembrar()
        Turno.objects.update(estado=Turno.Estado.CONFIRMADO)
        self.sembrar()
        nuevo = Turno.objects.get(estado=Turno.Estado.RESERVADO)
        viejo = Turno.objects.get(estado=Turno.Estado.CONFIRMADO)
        self.assertNotEqual(timezone.localtime(nuevo.inicio).date(), timezone.localtime(viejo.inicio).date())

    def test_rehacer_la_carga_al_otro_dia_renueva_la_espera(self):
        # La fila la arma el motor con `seed_guardia` (lo cubre el e2e); acá, el
        # caso ya esperando desde ayer.
        area = Area.objects.get(nombre="Cardiología")
        flujo = Flujo.objects.create(institucion=area.institucion, area=area, titulo="Atención cardiológica")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1, estado="publicada")
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Atención del especialista")
        caso = Caso.objects.create(institucion=area.institucion, version=version, ciudadano=self.andrea, area_actual=area)
        item = ItemFila.objects.create(caso=caso, nodo=nodo)
        ItemFila.objects.filter(pk=item.pk).update(ingreso=timezone.now() - timedelta(hours=30))

        self.assertEqual(en_sala_de_espera(self.andrea, flujo), caso)
        item.refresh_from_db()
        self.assertGreater(item.ingreso, timezone.now() - timedelta(minutes=1))
        api = self.cliente(self.sembrar())
        self.assertEqual(api.get("/api/mi/llamado/").data["estado"], "en_espera")

    def test_si_se_perdio_el_archivo_lo_vuelve_a_generar(self):
        # Una base restaurada sin el volumen de media: el estudio apunta a un
        # archivo que no está. Rehacer la carga no puede chocar con la ruta única.
        self.sembrar()
        estudio = Estudio.objects.get(realizado=True)
        default_storage.delete(estudio.archivo)
        cuenta = self.sembrar()
        estudio.refresh_from_db()
        self.assertTrue(default_storage.exists(estudio.archivo))
        self.assertEqual(ArchivoClinico.objects.filter(objeto_tipo="Estudio", objeto_id=estudio.pk).count(), 1)
        self.assertEqual(self.cliente(cuenta).get(f"/api/mi/resultados/{estudio.pk}/archivo/").status_code, 200)

    def test_sin_la_carga_del_hospital_avisa_y_no_crea_nada(self):
        Ciudadano.objects.filter(pk=self.andrea.pk).update(nombre="Otra")
        with self.assertRaisesMessage(CommandError, "seed_financiadores"):
            call_command("seed_portal_demo", stdout=StringIO())
        self.assertFalse(CuentaPaciente.objects.exists())

    @override_settings(ENTORNO="produccion")
    def test_no_corre_en_produccion(self):
        with self.assertRaises(CommandError):
            call_command("seed_portal_demo", stdout=StringIO())
        self.assertFalse(CuentaPaciente.objects.exists())

    def test_el_informe_es_un_pdf_que_dice_que_es_ficticio(self):
        pdf = informe_pdf(self.andrea, "Hemograma completo", date(2026, 9, 26))
        self.assertTrue(pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn("FICTICIO".encode(), pdf)
