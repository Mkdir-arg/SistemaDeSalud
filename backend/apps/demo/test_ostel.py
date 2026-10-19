"""Contratos del escenario OSTEL: aislamiento, repetición y cobertura entre prestadores."""
import json
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections
from django.db.models import Count
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.agenda.models import Turno
from apps.casos.models import Caso
from apps.demo.management.commands.seed_ostel_demo import Command, DOMINIO, ESCENARIO, ORGANIZACION
from apps.financiadores import models as m
from apps.financiadores.cobertura import evaluar, seleccionar_afiliacion
from apps.finanzas.models import Prestacion
from apps.instituciones.models import Cama, EstadiaCama, Institucion
from apps.registros.models import Ciudadano, HistoriaClinica


class OstelGuardasTests(SimpleTestCase):
    def test_rechaza_produccion_y_desarrollo_antes_de_consultar(self):
        for entorno in ("produccion", "desarrollo"):
            with self.subTest(entorno=entorno), override_settings(ENTORNO=entorno):
                with self.assertRaisesMessage(CommandError, f"ENTORNO={entorno}"):
                    call_command("seed_ostel_demo", stdout=StringIO())

    @override_settings(ENTORNO="demo")
    def test_rechaza_motor_sin_bloqueo_postgresql_antes_de_consultar(self):
        with patch.object(connection, "vendor", "sqlite"):
            with self.assertRaisesMessage(CommandError, "exige PostgreSQL"):
                call_command("seed_ostel_demo", stdout=StringIO())


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL aislado; SQLite no demuestra la carga.")
@override_settings(ENTORNO="demo")
class OstelCargaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.previa = Institucion.objects.create(nombre="Institución ajena a OSTEL")
        cls.usuario_previo = Usuario.objects.create_user("previo@example.test", "test-only", nombre="Previo")
        cls.financiador_previo = m.Financiador.objects.create(nombre="Financiador previo", tipo="mutual")
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-solo-prueba-aislada"}):
            salida = StringIO()
            call_command("seed_ostel_demo", stdout=salida)
            cls.manifiesto = json.loads(salida.getvalue())

    def test_conserva_los_datos_anteriores_y_no_otorga_acceso_a_ellos(self):
        self.previa.refresh_from_db()
        self.assertEqual(self.previa.nombre, "Institución ajena a OSTEL")
        self.assertTrue(self.usuario_previo.check_password("test-only"))
        self.assertTrue(m.Financiador.objects.filter(pk=self.financiador_previo.pk).exists())
        evaluador = Usuario.objects.get(email=f"consultora@{DOMINIO}")
        self.assertEqual(evaluador.membresias.values("institucion").distinct().count(), 3)
        self.assertFalse(evaluador.membresias.filter(institucion=self.previa).exists())
        self.assertFalse(evaluador.membresias.filter(institucion=None).exists())
        self.assertFalse(evaluador.is_superuser)
        from apps.auditoria.views import _instituciones_que_audita
        auditables = set(_instituciones_que_audita(evaluador))
        propias = set(evaluador.membresias.values_list("institucion_id", flat=True))
        self.assertEqual(auditables, propias)
        self.assertNotIn(self.previa.pk, auditables)

    def test_tres_convenios_un_padron_y_tarifas_diferentes(self):
        org = m.Financiador.objects.get(nombre=ORGANIZACION)
        self.assertEqual(m.Convenio.objects.filter(financiador=org, estado="activo").count(), 3)
        self.assertEqual(m.Afiliado.objects.filter(financiador=org).count(), 24)
        self.assertEqual(m.Afiliado.objects.filter(financiador=org, titular__isnull=False).count(), 18)
        self.assertEqual(set(m.ArancelConvenio.objects.filter(convenio__financiador=org, prestacion__codigo="OSTEL-CONS").values_list("importe", flat=True)), {22000, 28000})

    def test_cupo_compartido_sin_compartir_fichas_clinicas(self):
        org = m.Financiador.objects.get(nombre=ORGANIZACION)
        afiliado = m.Afiliado.objects.get(financiador=org, numero="OSTEL-D001-00")
        ciudadanos = Ciudadano.objects.filter(documento=afiliado.documento)
        self.assertEqual(ciudadanos.count(), 3)
        historias = HistoriaClinica.objects.filter(ciudadano__in=ciudadanos)
        self.assertEqual(historias.count(), 2)
        self.assertEqual(historias.values("ciudadano__institucion").distinct().count(), 2)
        admin = Usuario.objects.get(email=f"consultora@{DOMINIO}")
        for prestacion in Prestacion.objects.filter(codigo="OSTEL-CONS"):
            caso = Caso.objects.create(institucion=prestacion.institucion, version=prestacion.nodo.version,
                area_actual=prestacion.nodo.version.flujo.area,
                ciudadano=ciudadanos.get(institucion=prestacion.institucion))
            seleccionar_afiliacion(caso=caso, usuario=admin, afiliado=afiliado, motivo="Prueba de cupo compartido")
            resultado = evaluar(caso=caso, prestacion=prestacion, fecha=timezone.localdate())
            self.assertEqual(resultado["disponibles"], 4)
            self.assertEqual(resultado["porcentaje"], "80.00")
            self.assertEqual(resultado["origen_arancel"], "acordado_financiador")

    def test_repeticion_no_restaura_claves_roles_ni_casos_modificados(self):
        evaluador = Usuario.objects.get(email=f"consultora@{DOMINIO}")
        evaluador.set_password("modificada-en-ensayo")
        evaluador.save()
        membresia = evaluador.membresias.get(rol="medico", institucion__nombre__startswith="Sanatorio")
        membresia.activo = False
        membresia.save()
        caso = Caso.objects.filter(institucion__nombre__contains="Demo OSTEL").first()
        caso.prioridad = "urgente"
        caso.save()
        cantidades = (Usuario.objects.count(), Caso.objects.count(), m.Afiliado.objects.count())
        with patch.dict("os.environ", {"DEMO_PASSWORD": "otra-clave-no-aplicar"}):
            call_command("seed_ostel_demo", stdout=StringIO())
        self.assertEqual((Usuario.objects.count(), Caso.objects.count(), m.Afiliado.objects.count()), cantidades)
        evaluador.refresh_from_db()
        membresia.refresh_from_db()
        caso.refresh_from_db()
        self.assertTrue(evaluador.check_password("modificada-en-ensayo"))
        self.assertFalse(membresia.activo)
        self.assertEqual(caso.prioridad, "urgente")

    def test_camas_y_estadias_son_coherentes(self):
        ocupadas = Cama.objects.filter(area__institucion__nombre__contains="Demo OSTEL", estado="ocupada")
        self.assertEqual(ocupadas.count(), 1)
        self.assertEqual(EstadiaCama.objects.filter(cama__in=ocupadas, hasta=None).count(), 1)

    def test_el_afiliado_no_tiene_turnos_simultaneos_entre_prestadores(self):
        simultaneos = Turno.objects.filter(agenda__institucion__nombre__contains="Demo OSTEL").values(
            "ciudadano__documento", "inicio",
        ).annotate(total=Count("pk")).filter(total__gt=1)
        self.assertFalse(simultaneos.exists(), "La precarga no debe citar a una persona en dos lugares al mismo tiempo.")

    def test_ingreso_real_y_convenios_desde_la_api(self):
        cliente = APIClient()
        respuesta = cliente.post("/api/auth/token/", {
            "email": f"consultora@{DOMINIO}", "password": "clave-solo-prueba-aislada",
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}")
        org = m.Financiador.objects.get(nombre=ORGANIZACION)
        respuesta = cliente.get(f"/api/financiadores/{org.pk}/convenios/")
        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.data.get("results", []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual(len(filas), 3)
        # Una membresía propia no permite consultar el padrón de otro financiador.
        respuesta = cliente.get(f"/api/financiadores/{self.financiador_previo.pk}/padron/")
        self.assertIn(respuesta.status_code, (403, 404))

    def test_perfiles_protegidos_por_api_y_auditor_sin_escritura(self):
        org = m.Financiador.objects.get(nombre=ORGANIZACION)
        afiliado = m.Afiliado.objects.filter(financiador=org).first()
        cliente = APIClient()
        for perfil, salud, cobranza in (("autorizaciones", 403, 403), ("salud", 200, 403), ("cobranza", 403, 200)):
            cliente.force_authenticate(Usuario.objects.get(email=f"{perfil}@{DOMINIO}"))
            for recurso, esperado in (("salud", salud), ("cobranza", cobranza)):
                with self.subTest(perfil=perfil, recurso=recurso):
                    respuesta = cliente.get(f"/api/financiadores/{org.pk}/padron/{afiliado.pk}/{recurso}/")
                    self.assertEqual(respuesta.status_code, esperado)
        cliente.force_authenticate(Usuario.objects.get(email=f"auditor@{DOMINIO}"))
        respuesta = cliente.patch(f"/api/financiadores/{org.pk}/padron/{afiliado.pk}/", {"nombre": "Cambio no autorizado"}, format="json")
        self.assertEqual(respuesta.status_code, 403)

    def test_portal_paciente_en_dos_instituciones_y_token_separado(self):
        cliente = APIClient()
        respuesta = cliente.post("/api/mi/cuenta/ingresar/", {
            "email": f"paciente@{DOMINIO}", "password": "clave-solo-prueba-aislada",
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        cliente.credentials(HTTP_AUTHORIZATION=f"Bearer {respuesta.data['access']}")
        respuesta = cliente.get("/api/mi/turnos/")
        self.assertEqual(respuesta.status_code, 200)
        respuesta = cliente.get("/api/mi/resultados/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.data["resultados"]), 2)
        self.assertEqual(len({e["institucion"]["id"] for e in respuesta.data["resultados"]}), 2)
        respuesta = cliente.get("/api/financiadores/")
        self.assertEqual(respuesta.status_code, 401)


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL aislado.")
@override_settings(ENTORNO="demo")
class OstelAtomicidadTests(TestCase):
    def test_colision_no_se_apropia_de_datos(self):
        org = m.Financiador.objects.create(nombre=ORGANIZACION, tipo="obra_social")
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-solo-prueba-aislada"}):
            with self.assertRaisesMessage(CommandError, "identificadores reservados"):
                call_command("seed_ostel_demo", stdout=StringIO())
        self.assertEqual(m.Financiador.objects.get().pk, org.pk)
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(Group.objects.filter(name=ESCENARIO).exists())

    def test_fallo_intermedio_revierte_toda_la_carga(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-solo-prueba-aislada"}):
            with patch.object(Command, "_padron", side_effect=CommandError("Fallo inyectado de prueba")):
                with self.assertRaisesMessage(CommandError, "Fallo inyectado"):
                    call_command("seed_ostel_demo", stdout=StringIO())
        self.assertFalse(Institucion.objects.exists())
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(m.Financiador.objects.exists())
        self.assertFalse(Group.objects.filter(name=ESCENARIO).exists())

    def test_clave_publica_se_rechaza(self):
        for password in ("", "demo1234"):
            with self.subTest(password=bool(password)), patch.dict("os.environ", {"DEMO_PASSWORD": password}):
                with self.assertRaisesMessage(CommandError, "DEMO_PASSWORD externa"):
                    call_command("seed_ostel_demo", stdout=StringIO())
        self.assertFalse(Institucion.objects.exists())


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL reales.")
@override_settings(ENTORNO="demo")
class OstelConcurrenciaTests(TransactionTestCase):
    def test_dos_cargas_simultaneas_crean_un_solo_escenario(self):
        barrera = Barrier(2)

        def cargar():
            close_old_connections()
            try:
                barrera.wait(timeout=20)
                salida = StringIO()
                call_command("seed_ostel_demo", stdout=salida)
                return json.loads(salida.getvalue())["existente"]
            finally:
                connections.close_all()

        with patch.dict("os.environ", {"DEMO_PASSWORD": "clave-solo-prueba-aislada"}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futuros = [pool.submit(cargar) for _ in range(2)]
                resultados = [f.result(timeout=60) for f in futuros]
        self.assertEqual(sorted(resultados), [False, True])
        self.assertEqual(Institucion.objects.count(), 3)
        self.assertEqual(m.Financiador.objects.count(), 1)
        self.assertEqual(m.Afiliado.objects.count(), 24)
        self.assertEqual(Usuario.objects.count(), len(Command._emails()))
