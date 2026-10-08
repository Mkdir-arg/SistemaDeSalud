"""
Portal del paciente (#121): sus datos en toda la red.

Fijan los criterios de aceptación del issue y las reglas que no se pueden
romper sin que nadie lo note: R1 (sólo los registros de esta persona), R3
(cancelar hasta 24 horas antes, lo decide el backend) y R4 (estudio ajeno: 404,
y cada descarga auditada).
"""
import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.agenda.models import Agenda, Turno
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, ItemFila, Notificacion
from apps.financiadores.models import Afiliado, Financiador, Plan, VinculoCiudadano
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Box, Institucion
from apps.registros.models import Ciudadano, Estudio, HistoriaClinica

from .models import EventoPortal
from .tests import CLAVE, Base

NACIMIENTO = date(1990, 5, 4)


class RedBase(Base):
    def setUp(self):
        super().setUp()
        self.central = Institucion.objects.create(nombre="Hospital Central")
        self.norte = Institucion.objects.create(nombre="Hospital Norte")
        self.cuenta_ = self.validada()
        self.cuenta_.fecha_nacimiento = NACIMIENTO
        self.cuenta_.save()
        self.api = self.cliente(self.cuenta_)
        # La misma persona en dos hospitales; en el Norte con ceros adelante.
        self.en_central = self.ciudadano(self.central, "34521521", NACIMIENTO)
        self.en_norte = self.ciudadano(self.norte, "034521521", None)
        self.otra = self.ciudadano(self.central, "30111222", date(1980, 1, 1))

    def ciudadano(self, inst, documento, nacimiento):
        return Ciudadano.objects.create(
            institucion=inst, nombre="Martina", apellido="Sosa",
            documento=documento, fecha_nacimiento=nacimiento,
        )

    def agenda(self, inst):
        area, _ = Area.objects.get_or_create(institucion=inst, nombre="Clínica")
        return Agenda.objects.get_or_create(institucion=inst, area=area, nombre="Dra. Suárez")[0]

    def turno(self, ciudadano, horas, estado=Turno.Estado.RESERVADO):
        return Turno.objects.create(
            agenda=self.agenda(ciudadano.institucion), ciudadano=ciudadano,
            inicio=timezone.now() + timedelta(hours=horas), estado=estado,
        )

    def get(self, ruta, cliente=None):
        return (cliente or self.api).get(f"/api/mi/{ruta}")


class TurnosTests(RedBase):
    def test_ve_los_turnos_de_las_dos_instituciones_y_ninguno_ajeno(self):
        a = self.turno(self.en_central, 48)
        b = self.turno(self.en_norte, 72)
        self.turno(self.otra, 48)
        r = self.get("turnos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([t["id"] for t in r.data["turnos"]], [a.id, b.id])
        self.assertEqual(
            {t["institucion"]["nombre"] for t in r.data["turnos"]}, {"Hospital Central", "Hospital Norte"},
        )

    def test_nunca_entran_los_nn_ni_los_documentos_vacios(self):
        sin_doc = self.turno(self.ciudadano(self.central, "", None), 48)
        cuenta_nn = self.validada("nn@correo.test", documento="NN")
        r = self.get("turnos/", self.cliente(cuenta_nn))
        self.assertEqual(r.data["turnos"], [])
        self.assertNotIn(sin_doc.id, [t["id"] for t in self.get("turnos/").data["turnos"]])

    def test_confirmar_por_el_portal(self):
        t = self.turno(self.en_norte, 48)
        r = self.api.post(f"/api/mi/turnos/{t.id}/confirmar/")
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual((t.estado, t.confirmado_via), (Turno.Estado.CONFIRMADO, "portal"))
        self.assertIsNone(t.resuelto_por)
        self.assertEqual(r.data["estado"], "confirmado")

    def test_el_hospital_ve_confirmado_por_el_paciente(self):
        t = self.turno(self.en_central, 48)
        self.api.post(f"/api/mi/turnos/{t.id}/confirmar/")
        admin = Usuario.objects.create_superuser("root@salud.test", CLAVE, nombre="Root")
        hospital = APIClient()
        hospital.force_authenticate(admin)
        r = hospital.get(f"/api/turnos/{t.id}/")
        self.assertEqual((r.data["estado"], r.data["confirmado_via"]), ("confirmado", "portal"))

    def test_recordar_turnos_ya_no_lista_el_confirmado(self):
        t = self.turno(self.en_central, 48)
        adm = Usuario.objects.create_user("adm@test.local", "x", nombre="Diego")
        m = Membresia.objects.create(usuario=adm, institucion=self.central, rol="administrativo", activo=True)
        m.areas.set([t.agenda.area])
        self.api.post(f"/api/mi/turnos/{t.id}/confirmar/")
        dias = (timezone.localtime(t.inicio).date() - timezone.localdate()).days
        call_command("recordar_turnos", "--dias", str(dias), stdout=StringIO(), stderr=StringIO())
        self.assertFalse(Notificacion.objects.filter(usuario=adm).exists())

    def test_confirmar_exige_un_turno_reservado(self):
        t = self.turno(self.en_central, 48, Turno.Estado.CONFIRMADO)
        r = self.api.post(f"/api/mi/turnos/{t.id}/confirmar/")
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "no_confirmable"))

    def test_cancelar_a_30_horas(self):
        t = self.turno(self.en_central, 30, Turno.Estado.CONFIRMADO)
        r = self.api.post(f"/api/mi/turnos/{t.id}/cancelar/")
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual((t.estado, t.cancelado_via), (Turno.Estado.CANCELADO, "portal"))
        self.assertIn("cancelado por el paciente", t.observaciones)

    def test_cancelar_a_10_horas_se_rechaza_con_motivo(self):
        t = self.turno(self.en_central, 10)
        listado = self.get("turnos/").data["turnos"][0]
        self.assertFalse(listado["puede_cancelar"])
        self.assertIn("24 horas", listado["motivo_no_cancelable"])
        r = self.api.post(f"/api/mi/turnos/{t.id}/cancelar/")
        self.assertEqual((r.status_code, r.data["codigo"]), (409, "no_cancelable"))
        self.assertIn("24 horas", r.data["detail"])
        t.refresh_from_db()
        self.assertEqual(t.estado, Turno.Estado.RESERVADO)

    def test_un_turno_ajeno_da_404(self):
        t = self.turno(self.otra, 48)
        for accion in ("confirmar", "cancelar"):
            with self.subTest(accion=accion):
                self.assertEqual(self.api.post(f"/api/mi/turnos/{t.id}/{accion}/").status_code, 404)
        t.refresh_from_db()
        self.assertEqual(t.estado, Turno.Estado.RESERVADO)


class CruceDeDocumentoTests(RedBase):
    def test_otra_fecha_de_nacimiento_no_se_ve_y_queda_auditado(self):
        otro_norte = Institucion.objects.create(nombre="Hospital Sur")
        cruzado = self.ciudadano(otro_norte, "34521521", date(1950, 1, 1))
        self.turno(cruzado, 48)
        self.assertEqual(self.get("turnos/").data["turnos"], [])
        self.get("turnos/")
        self.get("llamado/")
        eventos = EventoPortal.objects.filter(tipo=EventoPortal.Tipo.DESCARTE_POR_NACIMIENTO)
        # Una vez por registro, aunque la app consulte muchas veces.
        self.assertEqual(eventos.count(), 1)
        self.assertEqual(eventos.get().detalle, {"ciudadano": cruzado.id, "institucion": otro_norte.id})


class LlamadoTests(RedBase):
    def setUp(self):
        super().setUp()
        area = Area.objects.create(institucion=self.norte, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.norte, area=area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ESPERA_FILA, titulo="Espera")
        caso = Caso.objects.create(institucion=self.norte, version=version, ciudadano=self.en_norte, area_actual=area)
        self.item = ItemFila.objects.create(caso=caso, nodo=self.nodo)
        self.box = Box.objects.create(area=area, nombre="Consultorio 2")

    def test_sin_fila(self):
        self.item.delete()
        self.assertEqual(self.get("llamado/").data, {"estado": "sin_fila"})

    def test_en_espera(self):
        r = self.get("llamado/")
        self.assertEqual(r.data["estado"], "en_espera")
        self.assertEqual(r.data["institucion"]["nombre"], "Hospital Norte")

    def test_te_estan_llamando_a_consultorio_2(self):
        self.item.box = self.box
        self.item.llamado_at = timezone.now()
        self.item.save()
        r = self.get("llamado/")
        self.assertEqual((r.data["estado"], r.data["box"]), ("llamado", "Consultorio 2"))
        self.assertEqual(r.data["institucion"]["nombre"], "Hospital Norte")

    def test_un_llamado_vencido_no_se_anuncia(self):
        self.item.box = self.box
        self.item.llamado_at = timezone.now() - timedelta(hours=9)
        self.item.save()
        self.assertNotEqual(self.get("llamado/").data["estado"], "llamado")


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ResultadosTests(RedBase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.ruta = default_storage.save(f"uploads/{self.central.id}/eco.pdf", ContentFile(b"%PDF-eco"))
        self.estudio = self.estudio_de(self.en_central, realizado=True, archivo=self.ruta, resultado="alterado")

    def estudio_de(self, ciudadano, **campos):
        hc, _ = HistoriaClinica.objects.get_or_create(ciudadano=ciudadano)
        return Estudio.objects.create(historia=hc, tipo="Ecografía", fecha=date(2026, 10, 1), **campos)

    def test_lista_realizados_y_pendientes(self):
        pendiente = self.estudio_de(self.en_norte, realizado=False)
        r = self.get("resultados/")
        por_id = {e["id"]: e for e in r.data["resultados"]}
        self.assertEqual(set(por_id), {self.estudio.id, pendiente.id})
        self.assertEqual(por_id[self.estudio.id]["resultado"], "alterado")
        self.assertTrue(por_id[self.estudio.id]["descargable"])
        self.assertEqual((por_id[pendiente.id]["realizado"], por_id[pendiente.id]["descargable"]), (False, False))

    def test_descarga_auditada_con_tipo_paciente(self):
        r = self.get(f"resultados/{self.estudio.id}/archivo/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-eco")
        acceso = AccesoClinico.objects.get()
        self.assertEqual(
            (acceso.tipo, acceso.cuenta_paciente_id, acceso.usuario_id, acceso.ciudadano_id, acceso.institucion_id),
            ("paciente", self.cuenta_.id, None, self.en_central.id, self.central.id),
        )

    def test_estudio_de_otra_persona_da_404_sin_descarga(self):
        ajeno = self.estudio_de(self.otra, realizado=True, archivo=self.ruta)
        r = self.get(f"resultados/{ajeno.id}/archivo/")
        self.assertEqual(r.status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())

    def test_un_archivo_de_otra_institucion_no_se_sirve(self):
        estudio = self.estudio_de(self.en_norte, realizado=True, archivo=self.ruta)
        self.assertEqual(self.get(f"resultados/{estudio.id}/archivo/").status_code, 404)

    def test_el_hospital_ve_la_descarga_en_la_auditoria(self):
        self.get(f"resultados/{self.estudio.id}/archivo/")
        admin = Usuario.objects.create_superuser("root@salud.test", CLAVE, nombre="Root")
        hospital = APIClient()
        hospital.force_authenticate(admin)
        r = hospital.get(f"/api/accesos-clinicos/de-paciente/?ciudadano={self.en_central.id}")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["results"][0]["usuario_nombre"], "El paciente, desde el portal")
        self.assertEqual(r.data["personas"][0]["email"], self.cuenta_.email)


class CoberturaTests(RedBase):
    def setUp(self):
        super().setUp()
        self.verificador = Usuario.objects.create_user("adm@test.local", "x", nombre="Diego")

    def afiliado(self, nombre, documento="34521521"):
        fin = Financiador.objects.create(nombre=nombre, tipo="mutual")
        plan = Plan.objects.create(financiador=fin, codigo="P1", nombre="Plan 210")
        return Afiliado.objects.create(
            financiador=fin, numero="A-77", documento=documento, nombre="Sosa Martina",
            plan=plan, desde=date(2025, 1, 1),
        )

    def test_debil_y_confirmada(self):
        debil = self.afiliado("Mutual Sur")
        fuerte = self.afiliado("Mutual Norte")
        VinculoCiudadano.objects.create(afiliado=fuerte, ciudadano=self.en_norte, verificado_por=self.verificador)
        self.afiliado("Otra Obra", documento="30111222")
        r = self.get("cobertura/")
        por_id = {c["id"]: c for c in r.data["coberturas"]}
        self.assertEqual(set(por_id), {debil.id, fuerte.id})
        self.assertFalse(por_id[debil.id]["confirmada"])
        self.assertTrue(por_id[fuerte.id]["confirmada"])
        self.assertEqual(
            (por_id[fuerte.id]["financiador"], por_id[fuerte.id]["plan"], por_id[fuerte.id]["numero"], por_id[fuerte.id]["desde"]),
            ("Mutual Norte", "Plan 210", "A-77", date(2025, 1, 1)),
        )

    def test_vinculada_a_un_registro_descartado_no_se_muestra(self):
        sur = Institucion.objects.create(nombre="Hospital Sur")
        cruzado = self.ciudadano(sur, "34521521", date(1950, 1, 1))
        a = self.afiliado("Mutual Sur")
        VinculoCiudadano.objects.create(afiliado=a, ciudadano=cruzado, verificado_por=self.verificador)
        self.assertEqual(self.get("cobertura/").data["coberturas"], [])

    def test_finalizada_no_se_muestra(self):
        a = self.afiliado("Mutual Sur")
        a.finalizado_en = timezone.now()
        a.save()
        self.assertEqual(self.get("cobertura/").data["coberturas"], [])


RUTAS_DE_DATOS = [
    ("get", "turnos/"), ("post", "turnos/1/confirmar/"), ("post", "turnos/1/cancelar/"),
    ("get", "llamado/"), ("get", "resultados/"), ("get", "resultados/1/archivo/"), ("get", "cobertura/"),
]


class TodasLasRutasDelPortalTests(Base):
    """Ninguna ruta de `/api/mi/` puede usar la cadena de autenticación global.

    Una vista que hereda de `APIView` y no de `_ConCuenta` acepta el JWT de un
    médico: con `IsAuthenticated` por defecto, entra como `Usuario` a una vista
    escrita para un paciente. Las listas de rutas de las otras pruebas se pueden
    olvidar al sumar una ruta; ésta recorre las rutas que existen.
    """

    def test_cada_vista_autentica_solo_con_el_portal_o_con_nada(self):
        from . import urls
        from .autenticacion import PortalAuthentication

        for patron in urls.urlpatterns:
            vista = patron.callback.view_class
            with self.subTest(ruta=str(patron.pattern)):
                self.assertIn(list(vista.authentication_classes), [[], [PortalAuthentication]])


class AccesoALosDatosTests(Base):
    def test_sin_identidad_validada_da_403(self):
        api = self.cliente(self.cuenta())
        for metodo, ruta in RUTAS_DE_DATOS:
            with self.subTest(ruta=ruta):
                r = getattr(api, metodo)(f"/api/mi/{ruta}")
                self.assertEqual((r.status_code, r.data["codigo"]), (403, "identidad_sin_validar"))

    def test_el_jwt_del_sistema_da_401(self):
        Usuario.objects.create_superuser("root@salud.test", CLAVE, nombre="Root")
        r = self.client.post("/api/auth/token/", {"email": "root@salud.test", "password": CLAVE}, format="json")
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        for metodo, ruta in RUTAS_DE_DATOS:
            with self.subTest(ruta=ruta):
                self.assertEqual(getattr(api, metodo)(f"/api/mi/{ruta}").status_code, 401)
