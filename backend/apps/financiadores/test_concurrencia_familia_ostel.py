"""Revalidación de evidencia familiar con locks reales de PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier
from time import monotonic, sleep
from unittest import skipUnless

from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from . import models as m
from .test_familia_ostel import FamiliaOstelFixture


@skipUnless(connection.vendor == "postgresql", "Requiere locks reales en PostgreSQL local dedicado.")
class ConcurrenciaFamiliaOstelTests(FamiliaOstelFixture, TransactionTestCase):
    client_class = APIClient

    def enviar(self, propuesta, pid=None, barrera=None):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '15s'")
                cursor.execute("SELECT pg_backend_pid()")
                if pid is not None:
                    pid.put(cursor.fetchone()[0])
            cliente = APIClient()
            cliente.force_authenticate(self.user)
            if barrera is not None:
                barrera.wait(timeout=10)
            return cliente.post(self.url, {**self.fuente, **propuesta}, format="json").status_code
        finally:
            connection.close()

    def esperar_bloqueo(self, pid):
        limite = monotonic() + 10
        while monotonic() < limite:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                if cursor.fetchone()[0]:
                    return
            sleep(0.02)
        self.fail("No se observó la espera del lock PostgreSQL.")

    def test_confirmaciones_concurrentes_tienen_un_solo_efecto(self):
        self.importar()
        propuesta = self.proponer().data
        barrera = Barrier(2)
        anteriores = m.HistorialAfiliacion.objects.count()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(self.enviar, propuesta, None, barrera) for _ in range(2)]
            self.assertCountEqual([f.result(timeout=25) for f in futuros], [200, 409])
        self.assertEqual(m.HistorialAfiliacion.objects.count(), anteriores + 1)
        self.familiar.refresh_from_db()
        self.assertEqual(self.familiar.titular_id, propuesta["titular"])

    def carrera_identidad(self, titular):
        self.importar()
        propuesta = self.proponer().data
        pid = Queue()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                pk = propuesta["titular"] if titular else self.familiar.pk
                obj = m.Afiliado.objects.select_for_update().get(pk=pk)
                obj.numero_interno = "CAMBIO-CONCURRENTE"
                obj.save(update_fields=["numero_interno"])
                futuro = pool.submit(self.enviar, propuesta, pid)
                self.esperar_bloqueo(pid.get(timeout=10))
            antes = self.huella()
            self.assertEqual(futuro.result(timeout=25), 400)
            self.assertEqual(self.huella(), antes)

    def test_identidad_titular_cambia_antes_del_lock(self):
        self.carrera_identidad(True)

    def test_identidad_integrante_cambia_antes_del_lock(self):
        self.carrera_identidad(False)

    def test_fuente_cambia_mientras_espera_el_lote(self):
        self.importar()
        propuesta = self.proponer().data
        pid = Queue()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                lote = m.Importacion.objects.select_for_update().get(pk=self.lote.pk)
                lote.filas[0]["original"]["CUILTIT"] = ""
                lote.save(update_fields=["filas"])
                futuro = pool.submit(self.enviar, propuesta, pid)
                self.esperar_bloqueo(pid.get(timeout=10))
            antes = self.huella()
            self.assertEqual(futuro.result(timeout=25), 400)
            self.assertEqual(self.huella(), antes)
