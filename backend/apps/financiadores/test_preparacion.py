"""Configuración observable y ensayo de operación/restauración con datos ficticios."""
from copy import deepcopy
from contextlib import closing
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections, router
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia
from apps.finanzas.cobros import capturar_cobros_atencion
from apps.finanzas.dinero import registrar_movimiento
from apps.finanzas.models import ConcesionFinanciera, MovimientoDinero, ObligacionFinanciera
from apps.finanzas.models_cobros import PendienteCobro, SnapshotCobroAtencion
from apps.instituciones.models import Area
from .cobertura import liberar
from .models import ArancelConvenio, ConfiguracionHospital, Convenio, ReglaCobertura, VinculoPrestacion
from .preparacion import ACCIONES_OPERATIVAS, verificar_preparacion
from .test_cobertura import CoberturaSetup


class PreparacionFinanciadoresTests(CoberturaSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.membresia.rol = "admin"
        self.membresia.save(update_fields=["rol"])
        for accion in ("configurar_cobros", *ACCIONES_OPERATIVAS):
            self.conceder(accion)

    def informe(self, **datos):
        return verificar_preparacion(institucion_id=self.institucion.pk, **datos)

    def codigos(self, **datos):
        return {h["codigo"] for h in self.informe(**datos)["hallazgos"]}

    def test_configuracion_completa_desactivada_no_habilita_y_solo_select(self):
        ConfiguracionHospital.objects.filter(institucion=self.institucion).update(activo=False)
        with CaptureQueriesContext(connection) as consultas:
            reporte = self.informe(usuarios=[self.usuario.pk])
        self.assertTrue(reporte["configuracion_completa"], reporte)
        self.assertFalse(reporte["circuito_activo"])
        self.assertTrue(reporte["requiere_revision_operativa"])
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in consultas))
        self.assertFalse(ConfiguracionHospital.objects.get(institucion=self.institucion).activo)

    def test_detecta_equivalencia_inactiva_y_sin_regla_no_inventa_cobertura(self):
        self.comun.activo = False
        self.comun.save(update_fields=["activo"])
        self.assertIn("equivalencia_ausente_o_inactiva", self.codigos())
        self.comun.activo = True
        self.comun.save(update_fields=["activo"])
        ReglaCobertura.objects.all().delete()
        self.assertIn("sin_regla_aplicable", self.codigos())
        self.assertTrue(self.informe()["configuracion_completa"])
        Convenio.objects.filter(pk=self.convenio.pk).update(porcentaje_default=Decimal("0"))
        self.assertNotIn("sin_regla_aplicable", self.codigos())

    def test_usa_arancel_general_y_excepcion_sin_requerir_otra_tabla(self):
        self.assertNotIn("arancel_pendiente", self.codigos())
        self.politica(importe=None)
        self.assertIn("arancel_pendiente", self.codigos())
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion,
                                      importe=Decimal("80"), vigente_desde=self.hoy, creado_por=self.admin)
        self.assertNotIn("arancel_pendiente", self.codigos())
        self.assertIn("arancel_general_pendiente", self.codigos())
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion,
                                      importe=None, vigente_desde=self.hoy, creado_por=self.admin)
        self.assertIn("arancel_pendiente", self.codigos())

    def test_no_cobrar_no_se_reporta_como_arancel_faltante(self):
        self.politica(cobrar=False, importe=None)
        self.assertIn("prestacion_sin_cobro", self.codigos())
        self.assertNotIn("arancel_pendiente", self.codigos())
        self.assertTrue(self.informe()["configuracion_completa"])

    def test_politica_futura_no_oculta_arancel_pendiente_actual(self):
        self.politica(importe=None)
        self.politica(importe=Decimal("200"), vigente_desde=timezone.now() + timedelta(days=1))
        self.assertIn("arancel_pendiente", self.codigos())

    def test_convenio_cerrado_y_padron_finalizado_se_detectan(self):
        Convenio.objects.filter(pk=self.convenio.pk).update(estado="finalizado", cerrado_en=timezone.now())
        self.afiliado.finalizado_en = timezone.now()
        self.afiliado.save(update_fields=["finalizado_en"])
        codigos = self.codigos(financiadores=[self.financiador.pk])
        self.assertIn("convenio_no_vigente", codigos)
        self.assertIn("padron_sin_vigentes", codigos)

    def test_plan_inactivo_no_se_pasa_por_padron_valido(self):
        self.plan.activo = False
        self.plan.save(update_fields=["activo"])
        self.assertIn("padron_plan_invalido", self.codigos())

    def test_modalidad_autorizacion_exige_designacion_y_auditor_no_resuelve(self):
        ReglaCobertura.objects.filter(pk=self.regla.pk).update(requiere_autorizacion=True)
        self.assertIn("sin_resolutor_autorizaciones", self.codigos())
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.assertNotIn("sin_resolutor_autorizaciones", self.codigos())
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertIn("sin_resolutor_autorizaciones", self.codigos())

    def test_usuarios_inactivos_superadmin_y_rol_sin_concesion_no_sustituyen_designacion(self):
        self.assertFalse(self.informe(usuarios=[self.admin.pk])["configuracion_completa"])
        ConcesionFinanciera.objects.all().delete()
        # El rol admin se fija acá y no se hereda del ayudante `conceder`, que usa
        # a propósito un rol sin herencia financiera. Lo que este caso comprueba
        # es que ni siquiera el rol que sí hereda las dieciocho acciones sustituye
        # a la designación explícita de responsable.
        Membresia.objects.filter(usuario=self.usuario, institucion=self.institucion).update(
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        self.assertTrue(Membresia.objects.filter(usuario=self.usuario, rol=Membresia.Rol.ADMIN_INSTITUCION).exists())
        self.assertIn("sin_responsable_configuracion", self.codigos())
        for accion in ("configurar_cobros", *ACCIONES_OPERATIVAS):
            self.conceder(accion)
        self.usuario.is_active = False
        self.usuario.save(update_fields=["is_active"])
        self.assertIn("sin_responsable_operativo", self.codigos())

    def test_area_ajena_y_sensibilidad_no_se_combinan(self):
        self.politica(sensible=True)
        self.assertIn("sin_responsable_operativo", self.codigos())
        ConcesionFinanciera.objects.update(permite_sensibles=True)
        self.assertTrue(self.informe()["configuracion_completa"])
        permiso = ConcesionFinanciera.objects.get(accion="registrar_aceptacion")
        permiso.todas_las_areas = False
        permiso.save(update_fields=["todas_las_areas"])
        permiso.areas.add(Area.objects.create(institucion=self.institucion, nombre="Otra área"))
        self.assertIn("sin_responsable_operativo", self.codigos())
        permiso.areas.add(self.area)
        self.assertTrue(self.informe()["configuracion_completa"])

    def test_otro_hospital_no_completa_equivalencias_ni_concesiones(self):
        caso, _ = self.otro_hospital()
        VinculoPrestacion.objects.filter(prestacion=self.prestacion).delete()
        reporte = self.informe()
        self.assertEqual(reporte["totales"]["prestaciones"], 1)
        self.assertIn("equivalencia_ausente_o_inactiva", self.codigos())
        otro = verificar_preparacion(institucion_id=caso.institucion_id)
        self.assertIn("sin_responsable_operativo", {h["codigo"] for h in otro["hallazgos"]})

    def test_comando_no_imprime_pii_ni_activa_y_exigir_completa_falla(self):
        stdout = StringIO()
        call_command("verificar_preparacion_financiadores", institucion=self.institucion.pk, stdout=stdout)
        salida = stdout.getvalue()
        self.assertTrue(json.loads(salida)["solo_lectura"])
        for privado in (self.paciente.documento, self.paciente.nombre, self.financiador.nombre, self.usuario.email):
            self.assertNotIn(privado, salida)
        ConcesionFinanciera.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command("verificar_preparacion_financiadores", institucion=self.institucion.pk,
                         exigir_completa=True, stdout=StringIO(), stderr=StringIO())
        with self.assertRaises(CommandError):
            call_command("verificar_preparacion_financiadores", stdout=StringIO(), stderr=StringIO())
        with self.assertRaises(ValidationError):
            verificar_preparacion(institucion_id=999999)


class SuspensionOperativaTests(CoberturaSetup, APITestCase):
    def suspender(self):
        self.conceder("configurar_cobros")
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post("/api/coberturas/configurar/", {
            "institucion": self.institucion.pk, "activo": False, "dias_reserva_antigua": 7,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_suspendida_reserva_abierta_se_realiza_y_recupera_dos_veces_sin_deuda_duplicada(self):
        reserva = self.reservar(acepta=True)
        self.suspender()
        with self.assertRaises(ValidationError):
            self.reservar()
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("Fallo de prueba")):
            hecho = self.atencion()
        self.assertIn(reserva.pk, hecho.cobertura_contexto["reservas"])
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.politica(importe=Decimal("900"))
        capturar_cobros_atencion(hecho.pk)
        reserva.refresh_from_db()
        obligacion = reserva.distribucion.obligacion_financiador
        movimiento = registrar_movimiento(obligacion=obligacion, importe=Decimal("30"), fecha=self.hoy,
                                          clave=uuid4(), usuario=self.admin)
        original = list(ObligacionFinanciera.objects.order_by("pk").values_list("pk", "importe_original"))
        capturar_cobros_atencion(hecho.pk)
        capturar_cobros_atencion(hecho.pk)
        self.assertEqual(list(ObligacionFinanciera.objects.order_by("pk").values_list("pk", "importe_original")), original)
        self.assertEqual([importe for _, importe in original], [Decimal("80"), Decimal("20")])
        self.assertEqual(MovimientoDinero.objects.get(pk=movimiento.pk).importe, Decimal("30"))
        self.assertFalse(PendienteCobro.objects.exists())
        self.conceder("ver_dinero")
        respuesta = self.client.get(f"/api/seguimiento-cobros/?institucion={self.institucion.pk}")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 2)

    def test_suspendida_no_libera_automatica_reserva_y_confirmacion_sigue_siendo_explicita(self):
        reserva = self.reservar()
        self.suspender()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "reservada")
        with self.assertRaises(ValidationError):
            liberar(reserva=reserva, usuario=self.admin, motivo="Comprobación", no_realizada=False)
        liberar(reserva=reserva, usuario=self.admin, motivo="El personal confirmó que no se realizó", no_realizada=True)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "liberada")
        self.assertFalse(ObligacionFinanciera.objects.exists())


class _SoloBaseEnsayo:
    def __init__(self, alias):
        self.alias = alias

    def db_for_read(self, model, **hints):
        return self.alias

    db_for_write = db_for_read


def _prohibir_consulta_default(execute, sql, params, many, context):
    raise AssertionError("El ensayo intentó consultar una conexión ajena a su base aislada.")


class EnsayoMigracionRestauracionTests(unittest.TestCase):
    """SQLite en archivo temporal exclusivo: no modifica ninguna conexión existente."""

    def test_desde_esquema_pre_financiadores_preserva_dinero_y_restaura_respaldo(self):
        alias = "ensayo_financiadores_" + uuid4().hex
        # Hay migraciones antiguas con ORM sin .using(alias). Se enrutan al
        # ensayo y además se prohíbe consultar default, incluso por SQL directo.
        with (tempfile.TemporaryDirectory(prefix="salud-ensayo-migracion-") as directorio,
              patch.object(router, "routers", [_SoloBaseEnsayo(alias)]),
              connection.execute_wrapper(_prohibir_consulta_default)):
            ruta = Path(directorio)
            config = deepcopy(connection.settings_dict)
            config.update(ENGINE="django.db.backends.sqlite3", NAME=str(ruta / "ensayo.sqlite3"), OPTIONS={})
            connections.databases[alias] = config
            bd = connections[alias]
            try:
                executor = MigrationExecutor(bd)
                actuales = executor.loader.graph.leaf_nodes()
                # Excluir también dependientes posteriores (p. ej. una espera de
                # Casos con FK a autorización), sin omitir sus dependencias viejas.
                posteriores = set(executor.loader.graph.backwards_plan(
                    ("finanzas", "0025_hechoatencioncosteable_cobertura_contexto_and_more"),
                ))
                anteriores = sorted(
                    clave for clave, nodo in executor.loader.graph.node_map.items()
                    if clave not in posteriores and not any(hijo.key not in posteriores for hijo in nodo.children)
                )
                executor.migrate(anteriores)
                apps = executor.loader.project_state(anteriores).apps
                hospital = apps.get_model("instituciones", "Institucion").objects.using(alias).create(nombre="Ensayo ficticio")
                usuario = apps.get_model("accounts", "Usuario").objects.using(alias).create(email="ensayo@prueba.local", password="!")
                hecho = apps.get_model("finanzas", "HechoAtencionCosteable").objects.using(alias).create(
                    institucion_id=hospital.pk, evento_origen_id=101, caso_origen_id=202,
                    nodo_origen_id=303, ocurrida_en=timezone.now(),
                )
                obligacion = apps.get_model("finanzas", "ObligacionFinanciera").objects.using(alias).create(
                    institucion_id=hospital.pk, hecho_id=hecho.pk, tipo="cobrar", importe_original=Decimal("125.50"),
                    periodo_economico=timezone.localdate().replace(day=1), contraparte_nombre="Ficticio", clave=uuid4(),
                )
                apps.get_model("finanzas", "MovimientoDinero").objects.using(alias).create(
                    institucion_id=hospital.pk, obligacion_id=obligacion.pk, tipo="cobro", importe=Decimal("25.25"),
                    fecha=timezone.localdate(), autor_id=usuario.pk, clave=uuid4(),
                )

                def invariantes(conexion):
                    with conexion.cursor() as cursor:
                        cursor.execute("SELECT id, hecho_id, importe_original, moneda FROM finanzas_obligacionfinanciera ORDER BY id")
                        obligaciones = cursor.fetchall()
                        cursor.execute("SELECT id, obligacion_id, importe, tipo FROM finanzas_movimientodinero ORDER BY id")
                        return obligaciones, cursor.fetchall()

                original = invariantes(bd)
                with closing(sqlite3.connect(ruta / "respaldo.sqlite3")) as respaldo:
                    bd.connection.backup(respaldo)
                executor = MigrationExecutor(bd)
                executor.migrate(actuales)
                self.assertEqual(invariantes(bd), original)
                self.assertIn("financiadores_afiliado", bd.introspection.table_names())
                with bd.cursor() as cursor:
                    cursor.execute("SELECT cobertura_contexto FROM finanzas_hechoatencioncosteable WHERE id = %s", [hecho.pk])
                    self.assertEqual(json.loads(cursor.fetchone()[0]), {})
                # Restauración real del respaldo en OTRA base, nunca migración inversa.
                with closing(sqlite3.connect(ruta / "respaldo.sqlite3")) as respaldo, closing(sqlite3.connect(ruta / "restaurado.sqlite3")) as restaurado:
                    respaldo.backup(restaurado)
                    self.assertEqual(restaurado.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
                    self.assertEqual(restaurado.execute("PRAGMA foreign_key_check").fetchall(), [])
                    self.assertEqual(restaurado.execute("SELECT id, hecho_id, importe_original, moneda FROM finanzas_obligacionfinanciera ORDER BY id").fetchall(), original[0])
                    self.assertEqual(restaurado.execute("SELECT id, obligacion_id, importe, tipo FROM finanzas_movimientodinero ORDER BY id").fetchall(), original[1])
                    self.assertIsNone(restaurado.execute("SELECT name FROM sqlite_master WHERE name = 'financiadores_afiliado'").fetchone())
            finally:
                bd.close()
                del connections[alias]
                del connections.databases[alias]
