"""Identidad durable de operaciones de stock (#172, AUD-053).

Clave obligatoria (decisión del dueño): misma clave y mismo contenido mueven
stock una sola vez aunque se pierda la respuesta; otro contenido con la misma
clave da 409; una clave nueva es una operación nueva. Datos sintéticos.
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from uuid import uuid4

from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion

from . import motor
from .models import Deposito, Existencia, Insumo, LineaPedido, Movimiento, OperacionStock, Pedido


class EscenarioOperaciones:
    def preparar(self):
        self.usuario = Usuario.objects.create_user("farma-clave@example.test", "x", is_superuser=True, is_staff=True)
        self.inst = Institucion.objects.create(nombre="Hospital sintético de claves")
        self.central = Deposito.objects.create(institucion=self.inst, nombre="Central", central=True)
        self.botiquin = Deposito.objects.create(institucion=self.inst, nombre="Botiquín")
        self.insumo = Insumo.objects.create(institucion=self.inst, nombre="Insumo sintético", requiere_lote=False)

    def cliente(self):
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        return cliente

    def ingreso(self, clave, cantidad=10, cliente=None):
        return (cliente or self.cliente()).post("/api/movimientos-stock/ingreso/", {
            "deposito": self.central.pk, "insumo": self.insumo.pk, "cantidad": cantidad, "clave": clave,
        }, format="json")

    def stock(self, deposito=None):
        return sum(Existencia.objects.filter(deposito=deposito or self.central, insumo=self.insumo)
                   .values_list("cantidad", flat=True))


class OperacionesStockAuditoria172Tests(EscenarioOperaciones, APITestCase):
    def setUp(self):
        self.preparar()

    def test_repetir_la_misma_operacion_no_vuelve_a_mover_stock(self):
        clave = str(uuid4())
        primera = self.ingreso(clave)
        self.assertEqual(primera.status_code, 201)
        segunda = self.ingreso(clave)
        self.assertEqual(segunda.status_code, 201)
        self.assertEqual(segunda["X-Operacion-Repetida"], "1")
        self.assertEqual(segunda.data["id"], primera.data["id"])
        self.assertEqual((Movimiento.objects.count(), self.stock()), (1, 10))

    def test_misma_clave_con_otro_contenido_se_rechaza_sin_cambios(self):
        clave = str(uuid4())
        self.ingreso(clave)
        respuesta = self.ingreso(clave, cantidad=11)
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual((Movimiento.objects.count(), self.stock()), (1, 10))

    def test_clave_nueva_es_una_operacion_nueva_y_sin_clave_no_se_mueve(self):
        self.ingreso(str(uuid4()))
        self.assertEqual(self.ingreso(str(uuid4())).status_code, 201)
        for clave in (None, "", "no-es-uuid"):
            with self.subTest(clave=clave):
                datos = {"deposito": self.central.pk, "insumo": self.insumo.pk, "cantidad": 10}
                if clave is not None:
                    datos["clave"] = clave
                self.assertEqual(self.cliente().post("/api/movimientos-stock/ingreso/", datos, format="json").status_code, 400)
        self.assertEqual((Movimiento.objects.count(), self.stock()), (2, 20))

    def test_operacion_fallida_no_reserva_la_clave(self):
        clave = str(uuid4())
        consumo = {"deposito": self.central.pk, "insumo": self.insumo.pk, "cantidad": 5, "clave": clave}
        self.assertEqual(self.cliente().post("/api/movimientos-stock/consumo/", consumo, format="json").status_code, 400)
        self.assertFalse(OperacionStock.objects.exists())
        self.ingreso(str(uuid4()))
        self.assertEqual(self.cliente().post("/api/movimientos-stock/consumo/", consumo, format="json").status_code, 201)
        self.assertEqual(self.stock(), 5)

    def test_entrega_parcial_repetida_no_duplica_y_una_nueva_si_avanza(self):
        motor.ingresar(self.central, self.insumo, 100, autor=self.usuario)
        pedido = Pedido.objects.create(origen=self.botiquin, destino=self.central, creado_por=self.usuario)
        linea = LineaPedido.objects.create(pedido=pedido, insumo=self.insumo, pedido_cant=100)
        url = f"/api/pedidos-stock/{pedido.pk}/entregar/"
        clave = str(uuid4())
        cuerpo = {"entregas": {str(linea.pk): 10}, "clave": clave}
        self.assertEqual(self.cliente().post(url, cuerpo, format="json").status_code, 200)
        repetida = self.cliente().post(url, cuerpo, format="json")
        self.assertEqual((repetida.status_code, repetida["X-Operacion-Repetida"]), (200, "1"))
        linea.refresh_from_db()
        self.assertEqual(linea.entregado, 10)
        otro = self.cliente().post(url, {"entregas": {str(linea.pk): 20}, "clave": clave}, format="json")
        self.assertEqual(otro.status_code, 409)
        self.assertEqual(self.cliente().post(url, {"entregas": {str(linea.pk): 10}, "clave": str(uuid4())},
                                             format="json").status_code, 200)
        linea.refresh_from_db()
        self.assertEqual((linea.entregado, self.stock(self.botiquin)), (20, 20))

    def test_la_clave_es_por_institucion(self):
        clave = str(uuid4())
        self.ingreso(clave)
        otra = Institucion.objects.create(nombre="Otra institución sintética")
        deposito = Deposito.objects.create(institucion=otra, nombre="Central B", central=True)
        insumo = Insumo.objects.create(institucion=otra, nombre="Insumo B", requiere_lote=False)
        respuesta = self.cliente().post("/api/movimientos-stock/ingreso/", {
            "deposito": deposito.pk, "insumo": insumo.pk, "cantidad": 10, "clave": clave,
        }, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(OperacionStock.objects.filter(clave=clave).count(), 2)


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL")
class OperacionesStockConcurrentesAuditoria172Tests(EscenarioOperaciones, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def test_dos_reintentos_simultaneos_con_la_misma_clave_mueven_una_vez(self):
        clave = str(uuid4())
        adentro, seguir = threading.Event(), threading.Event()
        original = motor.ingresar

        def lento(*args, **kwargs):
            # La primera solicitud ya reservó la clave; espera a que la segunda
            # quede bloqueada en la unicidad antes de confirmar.
            adentro.set()
            seguir.wait(10)
            return original(*args, **kwargs)

        def pedir(espera):
            try:
                if espera:
                    adentro.wait(10)
                respuesta = self.ingreso(clave)
                return respuesta.status_code, respuesta.get("X-Operacion-Repetida")
            finally:
                connections.close_all()

        motor.ingresar = lento
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                uno = pool.submit(pedir, False)
                dos = pool.submit(pedir, True)
                limite = time.monotonic() + 10
                while time.monotonic() < limite:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid)) > 0")
                        if cursor.fetchone()[0]:
                            break
                    time.sleep(0.05)
                motor.ingresar = original
                seguir.set()
                resultados = sorted([uno.result(timeout=20), dos.result(timeout=20)], key=str)
        finally:
            motor.ingresar = original
            seguir.set()
        self.assertEqual(resultados, [(201, "1"), (201, None)])
        self.assertEqual((Movimiento.objects.count(), self.stock()), (1, 10))
