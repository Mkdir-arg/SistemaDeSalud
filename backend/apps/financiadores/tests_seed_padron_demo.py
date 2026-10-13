"""Pruebas focales en la BD de tests aislada; nunca ejecutar contra datos reales."""
import json
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano
from . import models as m
from .management.commands import seed_padron_demo as seed
from .padron import estado_administrativo, validar_cbu, validar_cuit
from .permisos import puede_padron_protegido, requerir_financiador, requerir_padron_protegido


MODULO = "apps.financiadores.management.commands.seed_padron_demo."
CLAVE_TEST = "externa-solo-para-prueba-130"


class GuardasSeedPadronDemoTests(SimpleTestCase):
    def test_exige_demo_incluso_si_desarrollo_o_base_correcta(self):
        for entorno in ("produccion", "desarrollo"):
            with self.subTest(entorno=entorno), override_settings(ENTORNO=entorno):
                with self.assertRaisesMessage(CommandError, "ENTORNO=demo"):
                    seed.exigir_destino()

    @override_settings(ENTORNO="demo")
    def test_nombre_exacto_y_postgresql(self):
        for vendor, nombre in (("postgresql", "salud"), ("postgresql", "test_padron130"),
                               ("postgresql", "padron130_demo"), ("sqlite", "padron130")):
            with self.subTest(vendor=vendor, nombre=nombre), patch(MODULO + "connection") as db:
                db.vendor, db.settings_dict = vendor, {"NAME": nombre}
                with self.assertRaisesMessage(CommandError, "NAME exacto padron130"):
                    seed.exigir_destino()
        with patch(MODULO + "connection") as db:
            db.vendor, db.settings_dict = "postgresql", {"NAME": "padron130"}
            seed.exigir_destino()

    def test_clave_externa_obligatoria_y_default_prohibido_sin_imprimir(self):
        for clave in ("", "  ", "demo1234", " DEMO1234 "):
            with self.subTest(clave=clave), patch.dict("os.environ", {"DEMO_PASSWORD": clave}):
                with self.assertRaisesMessage(CommandError, "Provisioná DEMO_PASSWORD"):
                    seed.clave_externa()
        with patch.dict("os.environ", {"DEMO_PASSWORD": CLAVE_TEST}):
            self.assertEqual(seed.clave_externa(), CLAVE_TEST)

    def test_identificadores_sinteticos_validan_algoritmos_reales(self):
        for indice in range(1, 14):
            cuil = seed.identificador_fiscal(99013000 + indice)
            validar_cuit(cuil)
            self.assertEqual(cuil[2:10], str(99013000 + indice))
            validar_cbu(seed.cbu_ficticio(indice))
        validar_cuit(seed.identificador_fiscal(99001300, (30, 33, 34)), "cuit_titular")

    def test_ruta_fuera_repo_y_sin_sobrescritura(self):
        with self.assertRaisesMessage(CommandError, "fuera del repositorio"):
            seed.ruta_manifiesto(str(Path(seed.__file__).parent / "manifiesto.json"))
        with tempfile.TemporaryDirectory() as temporal:
            existente = Path(temporal) / "existente.json"
            existente.write_text("conservar", encoding="utf-8")
            with self.assertRaisesMessage(CommandError, "archivo de manifiesto nuevo"):
                seed.ruta_manifiesto(str(existente))
            self.assertEqual(existente.read_text(encoding="utf-8"), "conservar")


@override_settings(ENTORNO="demo")
class SeedPadronDemoTests(TestCase):
    def setUp(self):
        # Sólo la guarda de destino se sustituye: el ORM usa la BD de tests.
        # No cambiar NAME de connection ni apuntar el test al destino padron130.
        guarda = patch(MODULO + "exigir_destino")
        guarda.start()
        self.addCleanup(guarda.stop)
        claves = patch.dict("os.environ", {"DEMO_PASSWORD": CLAVE_TEST})
        claves.start()
        self.addCleanup(claves.stop)

    @staticmethod
    def ejecutar(**opciones):
        salida = StringIO()
        call_command("seed_padron_demo", stdout=salida, **opciones)
        return json.loads(salida.getvalue())

    def test_primera_carga_rechaza_financiadores_o_personas(self):
        for modelo, datos in ((m.Financiador, {"nombre": "Ajeno", "tipo": "otro"}),
                              (Usuario, {"email": "ajeno@example.test", "nombre": "Ajeno"})):
            with self.subTest(modelo=modelo.__name__):
                # Un savepoint por caso; no borrar información para probar la guarda.
                with transaction.atomic():
                    modelo.objects.create(**datos)
                    with self.assertRaisesMessage(CommandError, "deben estar vacíos"):
                        self.ejecutar()
                    self.assertFalse(Group.objects.filter(name=seed.ESCENARIO).exists())
                    transaction.set_rollback(True)

    def test_primera_carga_rechaza_paciente_aunque_no_haya_financiadores(self):
        institucion = Institucion.objects.create(nombre="Aislada")
        Ciudadano.objects.create(institucion=institucion, nombre="Ficticio", documento="99099999")
        with self.assertRaisesMessage(CommandError, "deben estar vacíos"):
            self.ejecutar()
        self.assertEqual(Ciudadano.objects.count(), 1)
        self.assertFalse(m.Financiador.objects.exists())

    def test_sin_clave_externa_no_crea_nada(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": ""}):
            with self.assertRaisesMessage(CommandError, "Provisioná DEMO_PASSWORD"):
                self.ejecutar()
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(Group.objects.exists())
        self.assertFalse(m.Financiador.objects.exists())

    def test_error_intermedio_revierte_todos_los_modelos_y_marcador(self):
        with patch(MODULO + "editar_protegido", side_effect=CommandError("Fallo focal")):
            with self.assertRaisesMessage(CommandError, "Fallo focal"):
                self.ejecutar()
        for modelo in (Usuario, m.Financiador, m.MembresiaFinanciador, m.Plan, m.Afiliado,
                       m.DocumentoLegajo, m.HistorialAfiliacion, m.EventoCobertura, Group):
            self.assertFalse(modelo.objects.exists(), modelo.__name__)

    def test_casos_orgs_familia_y_derechos_sin_crear_pacientes(self):
        manifiesto = self.ejecutar()
        self.assertFalse(manifiesto["existente"])
        a, b = [manifiesto["financiadores"][letra]["id"] for letra in ("A", "B")]
        self.assertEqual(m.Afiliado.objects.filter(financiador_id=a).count(), 12)
        self.assertEqual(m.Afiliado.objects.filter(financiador_id=b).count(), 1)
        self.assertFalse(Ciudadano.objects.exists())
        self.assertFalse(Institucion.objects.exists())
        afiliados = {caso: m.Afiliado.objects.get(pk=d["id"]) for caso, d in manifiesto["afiliados"].items()}
        titular = afiliados["titular"]
        self.assertEqual(titular.familiares.count(), 4)
        self.assertEqual(afiliados["orgB"].documento, titular.documento)
        self.assertNotEqual(afiliados["orgB"].pk, titular.pk)
        self.assertFalse(m.Afiliado.objects.exclude(titular=None).exclude(financiador_id=a).exists())
        self.assertEqual(set(m.Afiliado.objects.exclude(regimen="").values_list("regimen", flat=True)),
                         {"dependencia", "monotributo", "pasivo", "desempleo", "adherente"})
        self.assertEqual(estado_administrativo(afiliados["continuidad"]), "baja_administrativa")
        self.assertIsNone(afiliados["continuidad"].finalizado_en)
        self.assertEqual(estado_administrativo(afiliados["desempleo"]), "baja_programada")
        self.assertIsNotNone(afiliados["finalizado"].finalizado_en)
        self.assertGreater(afiliados["futuro"].desde, timezone.localdate())
        self.assertEqual(afiliados["legado"].cuil, "")
        self.assertFalse(afiliados["legado"].legajo.exists())
        self.assertEqual(afiliados["estudiante"].estado_tramite, "en_revision")
        self.assertLess(afiliados["estudiante"].legajo.get().vence_en, timezone.localdate())
        mora = afiliados["monotributo"]
        self.assertEqual(mora.cobranza_padron.situacion, "deuda")
        self.assertIsNone(mora.finalizado_en)
        self.assertLessEqual(mora.desde, timezone.localdate())
        self.assertEqual(m.SaludPadron.objects.get().afiliado_id, afiliados["integrante_5"].pk)

    def test_roles_designaciones_independientes_y_auditor_solo_lectura(self):
        manifiesto = self.ejecutar()
        for cuenta, (letra, rol, salud, cobranza) in seed.CUENTAS.items():
            user = Usuario.objects.get(pk=manifiesto["usuarios"][cuenta]["id"])
            org = manifiesto["financiadores"][letra]["id"]
            self.assertEqual(requerir_financiador(user, org), rol)
            self.assertEqual(puede_padron_protegido(user, org, "salud"), salud)
            self.assertEqual(puede_padron_protegido(user, org, "cobranza"), cobranza)
            self.assertFalse(user.is_superuser)
            self.assertFalse(user.is_staff)
            otra = manifiesto["financiadores"]["B" if letra == "A" else "A"]["id"]
            with self.assertRaises(PermissionDenied):
                requerir_financiador(user, otra)
            if rol == "auditor":
                with self.assertRaises(PermissionDenied):
                    requerir_financiador(user, org, escritura=True)
                for bloque in ("salud", "cobranza"):
                    with self.assertRaises(PermissionDenied):
                        requerir_padron_protegido(user, org, bloque, escritura=True)
        self.assertEqual(m.EventoCobertura.objects.filter(accion__startswith="designar_padron_").count(), 6)

    def test_repetir_preserva_ediciones_claves_roles_y_no_requiere_clave(self):
        inicial = self.ejecutar()
        titular = m.Afiliado.objects.get(pk=inicial["afiliados"]["titular"]["id"])
        titular.numero, titular.nombre, titular.email = "Editado en ensayo", "Nombre editado", "editado@example.test"
        titular.save(update_fields=["numero", "nombre", "email"])
        user = Usuario.objects.get(pk=inicial["usuarios"]["admin"]["id"])
        user.set_password("cambiada-durante-ensayo")
        user.save(update_fields=["password"])
        membresia = m.MembresiaFinanciador.objects.get(usuario=user)
        membresia.acceso_padron_salud = False
        membresia.save(update_fields=["acceso_padron_salud"])
        modelos = (Usuario, m.Financiador, m.Afiliado, m.DocumentoLegajo, m.HistorialAfiliacion,
                   m.SaludPadron, m.CobranzaPadron, m.HistorialPadronProtegido, m.EventoCobertura, Group)
        antes = [modelo.objects.count() for modelo in modelos]
        with patch.dict("os.environ", {"DEMO_PASSWORD": ""}):
            repetido = self.ejecutar()
        self.assertTrue(repetido["existente"])
        self.assertEqual([modelo.objects.count() for modelo in modelos], antes)
        self.assertEqual(repetido["afiliados"]["titular"]["id"], titular.pk)
        self.assertEqual(repetido["afiliados"]["titular"]["numero"], "Editado en ensayo")
        user.refresh_from_db()
        membresia.refresh_from_db()
        titular.refresh_from_db()
        self.assertTrue(user.check_password("cambiada-durante-ensayo"))
        self.assertFalse(membresia.acceso_padron_salud)
        self.assertEqual(titular.email, "editado@example.test")

    def test_repetir_admite_afiliados_importados_solo_en_orgs_del_ensayo(self):
        manifiesto = self.ejecutar()
        m.Afiliado.objects.create(financiador_id=manifiesto["financiadores"]["A"]["id"],
                                 numero="Importado ensayo", documento="99013999", nombre="Ficticio importado", desde=timezone.localdate())
        self.assertTrue(self.ejecutar()["existente"])
        self.assertEqual(m.Afiliado.objects.count(), 14)

    def test_marcador_no_habilita_mezclar_personas_o_organizaciones_ajenas(self):
        self.ejecutar()
        Usuario.objects.create_user("ajeno@example.test", "prueba", nombre="Ajeno")
        with self.assertRaisesMessage(CommandError, "ajenos al escenario"):
            self.ejecutar()
        self.assertEqual(Usuario.objects.count(), 7)
        self.assertEqual(m.Afiliado.objects.count(), 13)

    def test_repetir_rechaza_otra_organizacion_y_conserva_sus_datos(self):
        self.ejecutar()
        ajena = m.Financiador.objects.create(nombre="Organización ajena", tipo="otro")
        with self.assertRaisesMessage(CommandError, "ajenos al escenario"):
            self.ejecutar()
        self.assertTrue(m.Financiador.objects.filter(pk=ajena.pk).exists())
        self.assertEqual(m.Afiliado.objects.count(), 13)

    def test_marcador_incompleto_no_se_repara(self):
        Group.objects.create(name=seed.ESCENARIO)
        with self.assertRaisesMessage(CommandError, "marcador del escenario está incompleto"):
            self.ejecutar()
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(m.Financiador.objects.exists())

    def test_manifiesto_json_no_contiene_salud_bancos_documentos_ni_claves(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "manifiesto.json"
            salida = self.ejecutar(manifiesto=str(ruta))
            guardado = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(guardado["afiliados"], salida["afiliados"])
            texto = ruta.read_text(encoding="utf-8")
            for dato in (CLAVE_TEST, "password", "cud", "cronicas", "discapacidad", "99013001", "cuit_titular", "cbu"):
                self.assertNotIn(dato, texto)
            self.assertEqual(guardado["usuarios"]["auditor"]["rol"], "auditor")
            self.assertEqual(guardado["fecha_carga"], timezone.localdate().isoformat())

    def test_fallo_archivo_no_resembrara_la_base_ya_confirmada(self):
        with tempfile.TemporaryDirectory() as temporal:
            with patch.object(Path, "open", side_effect=OSError("Error de prueba")):
                with self.assertRaisesMessage(CommandError, "carga está completa en la base"):
                    self.ejecutar(manifiesto=str(Path(temporal) / "manifiesto.json"))
        self.assertEqual(m.Afiliado.objects.count(), 13)
        self.assertTrue(self.ejecutar()["existente"])

    def test_muestra_runtime_firmada_preview_sin_altas_y_confirmacion_idempotente(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from openpyxl import load_workbook
        from .importaciones import aplicar_importacion, previsualizar_importacion

        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "muestra.xlsx"
            manifiesto = self.ejecutar(muestra_xlsx=str(ruta))
            contenido = ruta.read_bytes()
        libro = load_workbook(BytesIO(contenido))
        self.assertEqual(libro["_contexto"].sheet_state, "hidden")
        columnas = [c.value for c in libro["Carga"][1]]
        self.assertNotIn("cbu", columnas)
        self.assertNotIn("cud", columnas)
        org = m.Financiador.objects.get(pk=manifiesto["financiadores"]["A"]["id"])
        admin = Usuario.objects.get(pk=manifiesto["usuarios"]["admin"]["id"])
        lote = previsualizar_importacion(financiador=org, usuario=admin, tipo="padron",
                                         archivo=SimpleUploadedFile("muestra.xlsx", contenido), clave=uuid4())
        self.assertEqual(m.Afiliado.objects.count(), 13)
        self.assertEqual(lote.resumen["valida"], 2)
        self.assertEqual(lote.resumen["rechazada"], 4)
        aplicar_importacion(importacion=lote, usuario=admin)
        self.assertEqual(m.Afiliado.objects.count(), 15)
        historias = m.HistorialAfiliacion.objects.count()
        aplicar_importacion(importacion=lote, usuario=admin)
        self.assertEqual(m.Afiliado.objects.count(), 15)
        self.assertEqual(m.HistorialAfiliacion.objects.count(), historias)
