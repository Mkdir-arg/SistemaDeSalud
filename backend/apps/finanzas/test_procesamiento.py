from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.instituciones.models import Area, Institucion
from .models import ConceptoGasto, Gasto, RepartoGasto, TrabajoReparto
from .procesamiento import solicitar_reparto, procesar_siguiente, tomar_trabajo


class TrabajoRepartoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.institucion = Institucion.objects.create(nombre="Hospital procesamiento")
        cls.area = Area.objects.create(institucion=cls.institucion, nombre="Consultorios")
        cls.autor = Usuario.objects.create_user("worker@demo.local", "x")
        cls.concepto = ConceptoGasto.objects.create(institucion=cls.institucion, codigo="LUZ", nombre="Electricidad")

    def gasto(self):
        return Gasto.objects.create(
            institucion=self.institucion, area=self.area, concepto=self.concepto,
            importe=Decimal("100.01"), periodo_economico=timezone.localdate().replace(day=1),
            registrado_por=self.autor, estado=Gasto.Estado.APROBADO, origen=Gasto.Origen.CENTRAL,
            aprobado_por=self.autor, aprobado_en=timezone.now(),
        )

    def test_solicitudes_se_acumulan_sin_duplicar_trabajos(self):
        gasto = self.gasto()
        solicitar_reparto(gasto.pk)
        solicitar_reparto(gasto.pk)
        self.assertEqual(TrabajoReparto.objects.count(), 1)
        self.assertEqual(TrabajoReparto.objects.get().revision, 2)
        self.assertTrue(procesar_siguiente())
        trabajo = TrabajoReparto.objects.get()
        self.assertEqual(trabajo.revision_procesada, 2)
        self.assertEqual(trabajo.estado, "actualizado")
        self.assertFalse(procesar_siguiente())
        self.assertEqual(RepartoGasto.objects.count(), 1)

    def test_solicitud_y_notificacion_se_revierten_con_la_transaccion(self):
        gasto = self.gasto()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                solicitar_reparto(gasto.pk)
                raise RuntimeError("cancelar")
        self.assertFalse(TrabajoReparto.objects.exists())

    def test_falla_conserva_pendiente_y_reintenta_sin_copiar_error_privado(self):
        gasto = self.gasto()
        solicitar_reparto(gasto.pk)
        with patch("apps.finanzas.services.procesar_reparto_gasto", side_effect=RuntimeError("dato privado")):
            self.assertTrue(procesar_siguiente())
        trabajo = TrabajoReparto.objects.get()
        self.assertEqual(trabajo.estado, "error")
        self.assertNotIn("dato privado", trabajo.ultimo_error)
        self.assertEqual(trabajo.revision_procesada, 0)
        self.assertFalse(procesar_siguiente())
        TrabajoReparto.objects.update(reintentar_en=timezone.now())
        self.assertTrue(procesar_siguiente())
        self.assertEqual(TrabajoReparto.objects.get().estado, "actualizado")


class EntregaRepartosPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("La notificación y los bloqueos se prueban en PostgreSQL real")
        self.institucion = Institucion.objects.create(nombre="Notificaciones")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.autor = Usuario.objects.create_user("notificaciones@demo.local", "x")
        concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="LUZ", nombre="Luz")
        self.gasto = Gasto.objects.create(
            institucion=self.institucion, area=self.area, concepto=concepto,
            importe=Decimal("100.00"), periodo_economico=timezone.localdate().replace(day=1),
            origen=Gasto.Origen.CENTRAL, estado=Gasto.Estado.APROBADO,
            registrado_por=self.autor, aprobado_por=self.autor, aprobado_en=timezone.now(),
        )

    def test_postgres_despierta_tras_commit_y_no_tras_rollback(self):
        import psycopg
        from .procesamiento import CANAL
        parametros = connection.get_connection_params()
        parametros.pop("cursor_factory", None)
        with psycopg.connect(**parametros, autocommit=True) as escucha:
            escucha.execute(f"LISTEN {CANAL}")
            with transaction.atomic():
                solicitar_reparto(self.gasto.pk)
                self.assertEqual(list(escucha.notifies(timeout=0.05, stop_after=1)), [])
            self.assertEqual(len(list(escucha.notifies(timeout=1, stop_after=1))), 1)
            with self.assertRaises(RuntimeError):
                with transaction.atomic():
                    solicitar_reparto(self.gasto.pk)
                    raise RuntimeError("cancelar")
            self.assertEqual(list(escucha.notifies(timeout=0.05, stop_after=1)), [])

    def test_dos_workers_no_reservan_el_mismo_trabajo(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        solicitar_reparto(self.gasto.pk)
        barrera = Barrier(2)
        def reservar(_):
            try:
                barrera.wait(timeout=5)
                return tomar_trabajo()
            finally:
                connections["default"].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(reservar, (1, 2)))
        self.assertEqual(sum(r is not None for r in resultados), 1)

    def test_otro_cambio_durante_el_calculo_no_se_pierde(self):
        gasto = self.gasto
        solicitar_reparto(gasto.pk)
        from .services import procesar_reparto_gasto
        def con_cambio(gasto_id):
            resultado = procesar_reparto_gasto(gasto_id)
            solicitar_reparto(gasto_id)
            return resultado
        with patch("apps.finanzas.services.procesar_reparto_gasto", side_effect=con_cambio):
            self.assertTrue(procesar_siguiente())
        trabajo = TrabajoReparto.objects.get()
        self.assertEqual((trabajo.revision, trabajo.revision_procesada), (2, 1))
        self.assertTrue(procesar_siguiente())
        self.assertEqual(TrabajoReparto.objects.get().revision_procesada, 2)
        self.assertEqual(RepartoGasto.objects.count(), 1)

    def test_trabajo_abandonado_se_recupera_tras_vencer_reserva(self):
        gasto = self.gasto
        solicitar_reparto(gasto.pk)
        primero = tomar_trabajo()
        self.assertIsNotNone(primero)
        self.assertIsNone(tomar_trabajo())
        TrabajoReparto.objects.update(reintentar_en=timezone.now() - timedelta(seconds=1))
        self.assertTrue(procesar_siguiente())
        self.assertEqual(TrabajoReparto.objects.get().estado, "actualizado")
