"""AUD-013/014: unicidad y transferencias opuestas con PostgreSQL real."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier, BrokenBarrierError, get_ident
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.db import IntegrityError, connection, connections, transaction
from django.db.models.query import QuerySet
from django.test import TransactionTestCase
from django.utils import timezone

from apps.instituciones.models import Institucion

from . import motor
from .models import Deposito, Existencia, Insumo, LineaPedido, Lote, Movimiento, Pedido


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL")
class StockConcurrenteAuditoria172Tests(TransactionTestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Stock concurrente sintético")
        self.a = Deposito.objects.create(institucion=self.institucion, nombre="A")
        self.b = Deposito.objects.create(institucion=self.institucion, nombre="B")
        self.insumo = Insumo.objects.create(institucion=self.institucion, nombre="Insumo sintético", requiere_lote=False)

    def ejecutar_dos(self, primera, segunda):
        inicio = Barrier(2, timeout=5)

        def ejecutar(operacion):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '6s'")
                    cursor.execute("SET statement_timeout = '9s'")
                inicio.wait()
                operacion()
                return None
            except Exception as error:
                # Los errores SQL pueden incluir datos: sólo tipo y SQLSTATE.
                causa = error.__cause__
                sqlstate = (getattr(causa, "sqlstate", None) or getattr(causa, "pgcode", None)
                            or getattr(error, "sqlstate", None) or getattr(error, "pgcode", None))
                return type(error).__name__, sqlstate
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            uno = pool.submit(ejecutar, primera)
            dos = pool.submit(ejecutar, segunda)
            errores = [uno.result(timeout=15), dos.result(timeout=15)]
        self.assertEqual(errores, [None, None])

    def sincronizar_primeras_filas(self):
        original, vistos = motor._existencia, set()
        ambos = Barrier(2, timeout=2)

        def bloquear(*args, **kwargs):
            existencia = original(*args, **kwargs)
            hilo = get_ident()
            if hilo not in vistos:
                vistos.add(hilo)
                try:
                    ambos.wait()
                except BrokenBarrierError:
                    # Con el protocolo correcto la segunda operación espera
                    # antes de tomar ninguna fila: la primera debe continuar.
                    pass
            return existencia

        return patch.object(motor, "_existencia", bloquear)

    def test_base_rechaza_segunda_existencia_sin_lote(self):
        Existencia.objects.create(deposito=self.a, insumo=self.insumo, cantidad=4)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Existencia.objects.create(deposito=self.a, insumo=self.insumo, cantidad=7)
        self.assertEqual(list(Existencia.objects.values_list("cantidad", flat=True)), [4])

    def test_ingresos_simultaneos_crean_una_existencia_sin_lote(self):
        original = QuerySet.create
        ambos = Barrier(2, timeout=2)

        def crear(queryset, **kwargs):
            if queryset.model is Existencia:
                try:
                    ambos.wait()
                except BrokenBarrierError:
                    pass
            return original(queryset, **kwargs)

        with patch.object(QuerySet, "create", crear):
            self.ejecutar_dos(lambda: motor.ingresar(self.a, self.insumo, 7),
                              lambda: motor.ingresar(self.a, self.insumo, 11))
        self.assertEqual(Existencia.objects.filter(deposito=self.a, insumo=self.insumo, lote=None).count(), 1)
        self.assertEqual(motor.disponible(self.a, self.insumo), 18)
        self.assertEqual(Movimiento.objects.filter(tipo=Movimiento.Tipo.INGRESO).count(), 2)

    def test_transferencias_opuestas_sin_lote_no_entran_en_deadlock(self):
        motor.ingresar(self.a, self.insumo, 20)
        motor.ingresar(self.b, self.insumo, 20)
        with self.sincronizar_primeras_filas():
            self.ejecutar_dos(lambda: motor.transferir(self.a, self.b, self.insumo, 5),
                              lambda: motor.transferir(self.b, self.a, self.insumo, 7))
        self.assertEqual(motor.disponible(self.a, self.insumo), 22)
        self.assertEqual(motor.disponible(self.b, self.insumo), 18)
        self.assertEqual(Movimiento.objects.filter(tipo=Movimiento.Tipo.TRANSFERENCIA).count(), 2)

    def test_transferencias_opuestas_preservan_fefo_y_movimientos_por_lote(self):
        temprano = Lote.objects.create(insumo=self.insumo, numero="Temprano",
                                      vencimiento=timezone.localdate() + timedelta(days=10))
        tarde = Lote.objects.create(insumo=self.insumo, numero="Tarde",
                                   vencimiento=timezone.localdate() + timedelta(days=30))
        for deposito in (self.a, self.b):
            motor.ingresar(deposito, self.insumo, 3, lote=temprano)
            motor.ingresar(deposito, self.insumo, 20, lote=tarde)
        with self.sincronizar_primeras_filas():
            self.ejecutar_dos(lambda: motor.transferir(self.a, self.b, self.insumo, 5),
                              lambda: motor.transferir(self.b, self.a, self.insumo, 7))
        self.assertEqual(motor.disponible(self.a, self.insumo), 25)
        self.assertEqual(motor.disponible(self.b, self.insumo), 21)
        movimientos = list(Movimiento.objects.filter(tipo=Movimiento.Tipo.TRANSFERENCIA).order_by("pk"))
        self.assertEqual(sum(m.cantidad for m in movimientos), 12)
        # Cada despacho usa primero lo temprano disponible tras el anterior.
        por_origen = {}
        for movimiento in movimientos:
            por_origen.setdefault(movimiento.origen_id, []).append(movimiento)
        for despacho in por_origen.values():
            self.assertEqual(despacho[0].lote_id, temprano.pk)
        self.assertEqual(sum(Existencia.objects.filter(lote=temprano).values_list("cantidad", flat=True)), 6)
        self.assertEqual(sum(Existencia.objects.filter(lote=tarde).values_list("cantidad", flat=True)), 40)

    def test_pedidos_opuestos_multiinsumo_comparten_orden_de_depositos(self):
        segundo = Insumo.objects.create(institucion=self.institucion, nombre="Segundo sintético", requiere_lote=False)
        for deposito in (self.a, self.b):
            for insumo in (self.insumo, segundo):
                motor.ingresar(deposito, insumo, 20)
        pedidos = [Pedido.objects.create(origen=self.b, destino=self.a),
                   Pedido.objects.create(origen=self.a, destino=self.b)]
        entregas = []
        for pedido in pedidos:
            lineas = [LineaPedido.objects.create(pedido=pedido, insumo=insumo, pedido_cant=5)
                      for insumo in (self.insumo, segundo)]
            entregas.append({linea.pk: 5 for linea in lineas})
        with self.sincronizar_primeras_filas():
            self.ejecutar_dos(lambda: motor.entregar_pedido(pedidos[0], entregas[0]),
                              lambda: motor.entregar_pedido(pedidos[1], entregas[1]))
        for pedido in pedidos:
            pedido.refresh_from_db()
            self.assertEqual(pedido.estado, Pedido.Estado.ENTREGADO)
        for deposito in (self.a, self.b):
            for insumo in (self.insumo, segundo):
                self.assertEqual(motor.disponible(deposito, insumo), 20)
        self.assertEqual(Movimiento.objects.filter(tipo=Movimiento.Tipo.TRANSFERENCIA).count(), 4)


@skipUnless(connection.vendor == "postgresql", "Prueba migraciones y DDL PostgreSQL")
class MigracionExistenciasAuditoria172Tests(TransactionTestCase):
    anterior = ("farmacia", "0003_proteger_depositos_de_pedidos")
    nueva = ("farmacia", "0004_existencia_unica_sin_lote")

    def setUp(self):
        institucion = Institucion.objects.create(nombre="Migración sintética privada")
        self.deposito = Deposito.objects.create(institucion=institucion, nombre="Depósito sintético privado")
        self.insumo = Insumo.objects.create(institucion=institucion, nombre="Insumo sintético privado", requiere_lote=False)
        self.lote = Lote.objects.create(insumo=self.insumo, numero="Lote sintético privado")

    def preparar_estado_anterior(self):
        executor = MigrationExecutor(connection)
        executor.migrate([self.anterior])
        return executor.loader.project_state([self.anterior]).apps.get_model("farmacia", "Existencia")

    def restaurar_estado_final(self, existencia):
        # Sólo filas sintéticas de esta prueba; jamás resolver datos reales.
        existencia.objects.filter(deposito_id=self.deposito.pk).delete()
        MigrationExecutor(connection).migrate([self.nueva])

    def constraints(self, existencia):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, existencia._meta.db_table)

    def test_migracion_valida_conserva_stock_y_garantiza_unicidad_null_y_lote(self):
        existencia = self.preparar_estado_anterior()
        try:
            existencia.objects.create(deposito_id=self.deposito.pk, insumo_id=self.insumo.pk, cantidad=4)
            existencia.objects.create(deposito_id=self.deposito.pk, insumo_id=self.insumo.pk,
                                      lote_id=self.lote.pk, cantidad=9)
            antes = list(existencia.objects.order_by("pk").values())
            MigrationExecutor(connection).migrate([self.nueva])
            self.assertEqual(list(existencia.objects.order_by("pk").values()), antes)
            self.assertIn("farmacia_existencia_unica_sin_lote", self.constraints(existencia))
            for lote_id in (None, self.lote.pk):
                with self.subTest(lote=lote_id):
                    with self.assertRaises(IntegrityError):
                        with transaction.atomic():
                            existencia.objects.create(deposito_id=self.deposito.pk, insumo_id=self.insumo.pk,
                                                      lote_id=lote_id, cantidad=1)
        finally:
            self.restaurar_estado_final(existencia)

    def test_preflight_duplicado_aborta_sin_modificar_datos_ni_constraints(self):
        existencia = self.preparar_estado_anterior()
        try:
            for cantidad in (4, 9):
                existencia.objects.create(deposito_id=self.deposito.pk, insumo_id=self.insumo.pk, cantidad=cantidad)
            antes = list(existencia.objects.order_by("pk").values())
            constraints = self.constraints(existencia)
            with self.assertRaises(RuntimeError) as error:
                MigrationExecutor(connection).migrate([self.nueva])
            texto = str(error.exception)
            self.assertIn("AUD-013", texto)
            for privado in (self.deposito.nombre, self.insumo.nombre, self.lote.numero):
                self.assertNotIn(privado, texto)
            self.assertEqual(list(existencia.objects.order_by("pk").values()), antes)
            self.assertEqual(self.constraints(existencia), constraints)
            self.assertFalse(MigrationRecorder(connection).migration_qs.filter(
                app=self.nueva[0], name=self.nueva[1],
            ).exists())
            salida = StringIO()
            with self.assertRaises(CommandError):
                call_command("diagnosticar_existencias", stdout=salida)
            self.assertIn(f"deposito_id={self.deposito.pk}", salida.getvalue())
            self.assertIn("lote_id=NULL filas=2", salida.getvalue())
            self.assertNotIn(self.deposito.nombre, salida.getvalue())
            self.assertNotIn(self.insumo.nombre, salida.getvalue())
            self.assertEqual(list(existencia.objects.order_by("pk").values()), antes)
        finally:
            self.restaurar_estado_final(existencia)
