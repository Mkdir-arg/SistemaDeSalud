"""Pruebas que requieren PostgreSQL dedicado; SQLite no acredita locks reales."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from queue import Queue
from time import monotonic, sleep
from unittest import skipUnless
from unittest.mock import patch
from io import BytesIO
from uuid import uuid4

from openpyxl import load_workbook

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from .models import Afiliado, Financiador, MembresiaFinanciador, Plan
from . import padron
from .services import registrar_afiliado
from .padron import ConflictoPadron, editar_ficha
from .importaciones import aplicar_importacion, generar_plantilla, previsualizar_importacion


@skipUnless(connection.vendor == "postgresql", "Requiere locks reales en PostgreSQL local dedicado; no ejecutado en SQLite.")
class ConcurrenciaPadron130Tests(TransactionTestCase):
    def setUp(self):
        self.org = Financiador.objects.create(nombre="A", tipo="obra_social")
        self.usuario = Usuario.objects.create_user("concurrencia130@test.local", "clave")
        MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.usuario, rol="operador")
        self.a = Afiliado.objects.create(financiador=self.org, numero="A", documento="10000001", nombre="A", desde=timezone.localdate())
        self.b = Afiliado.objects.create(financiador=self.org, numero="B", documento="10000002", nombre="B", desde=timezone.localdate())

    def test_vinculos_inversos_simultaneos_no_crean_ciclo(self):
        barrera = Barrier(2)
        def vincular(afiliado, titular):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    editar_ficha(afiliado=afiliado, usuario=self.usuario, entrada={"revision": 1, "motivo": "Familia", "titular": titular.pk, "parentesco": "hijo"})
                    return "aceptado"
                except (ValidationError, ConflictoPadron):
                    return "rechazado"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(vincular, self.a, self.b)
            segundo = pool.submit(vincular, self.b, self.a)
            resultados = [primero.result(timeout=20), segundo.result(timeout=20)]
        self.assertCountEqual(resultados, ["aceptado", "rechazado"])
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertFalse(self.a.titular_id and self.b.titular_id)

    def test_plan_desactivado_mientras_se_asigna_se_revalida_bajo_lock(self):
        plan = Plan.objects.create(financiador=self.org, codigo="BASE", nombre="Base")
        validando, continuar = Event(), Event()
        pid_editor = Queue(maxsize=1)
        validar_original = padron.validar_generales

        def validar_pausado(obj):
            validando.set()
            if not continuar.wait(timeout=15):
                raise RuntimeError("No se liberó la edición de la prueba.")
            return validar_original(obj)

        def asignar():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_editor.put(cursor.fetchone()[0])
                try:
                    editar_ficha(afiliado=self.a, usuario=self.usuario, entrada={
                        "revision": 1, "motivo": "Asignación concurrente", "plan": plan.pk,
                    })
                    return "aceptado"
                except ValidationError:
                    return "rechazado"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(padron, "validar_generales", side_effect=validar_pausado):
            try:
                with transaction.atomic():
                    bloqueado = Plan.objects.select_for_update().get(pk=plan.pk)
                    bloqueado.activo = False
                    bloqueado.save(update_fields=["activo"])
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        pid_desactivador = cursor.fetchone()[0]
                    futuro = pool.submit(asignar)
                    pid = pid_editor.get(timeout=10)
                    limite = monotonic() + 10
                    while True:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                            bloqueadores = cursor.fetchone()[0]
                        # Con el fix espera el lock; sin él llega a validar con
                        # activo=True antes del commit. Ambos órdenes se prueban.
                        if pid_desactivador in bloqueadores or validando.is_set():
                            break
                        if monotonic() >= limite:
                            self.fail("La asignación no alcanzó el punto de sincronización.")
                        sleep(0.02)
                # Confirmar la desactivación antes de permitir guardar al editor.
            finally:
                continuar.set()
            self.assertEqual(futuro.result(timeout=20), "rechazado")
        self.a.refresh_from_db()
        self.assertIsNone(self.a.plan_id)
        self.assertEqual(self.a.revision, 1)
        self.assertFalse(self.a.historial.exists())

    def test_altas_exclusivas_simultaneas_no_sobrescriben_ganador(self):
        barrera = Barrier(2)
        crear_original = Afiliado.objects.get_or_create

        def crear_sincronizado(*args, **kwargs):
            barrera.wait(timeout=10)
            return crear_original(*args, **kwargs)

        def registrar(nombre):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                try:
                    registrar_afiliado(financiador=self.org, usuario=self.usuario,
                        numero=nombre, documento="10000003", nombre=nombre,
                        plan=None, desde=timezone.localdate(), motivo="Alta exclusiva",
                        solo_crear=True)
                    return nombre
                except ValidationError:
                    return None
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(Afiliado.objects, "get_or_create", side_effect=crear_sincronizado):
            futuros = [pool.submit(registrar, nombre) for nombre in ("Uno", "Dos")]
            resultados = [futuro.result(timeout=20) for futuro in futuros]
        ganadores = [nombre for nombre in resultados if nombre is not None]
        self.assertEqual(len(ganadores), 1)
        afiliado = Afiliado.objects.get(financiador=self.org, documento="10000003")
        self.assertEqual((afiliado.nombre, afiliado.numero), (ganadores[0], ganadores[0]))
        self.assertEqual(afiliado.revision, 1)
        self.assertEqual(afiliado.historial.count(), 1)
        self.assertEqual(afiliado.historial.get().motivo, "Alta exclusiva")

    def test_ediciones_misma_revision_solo_una_confirma(self):
        barrera = Barrier(2)
        def editar(telefono):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    editar_ficha(afiliado=self.a, usuario=self.usuario, entrada={"revision": 1, "motivo": "Contacto", "telefono": telefono})
                    return "aceptado"
                except ConflictoPadron:
                    return "conflicto"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(editar, "111")
            segundo = pool.submit(editar, "222")
            resultados = [primero.result(timeout=20), segundo.result(timeout=20)]
        self.assertCountEqual(resultados, ["aceptado", "conflicto"])
        self.a.refresh_from_db()
        self.assertEqual(self.a.revision, 2)

    def test_importacion_existente_y_vinculo_inverso_no_invierten_locks(self):
        libro = load_workbook(BytesIO(generar_plantilla(financiador=self.org, usuario=self.usuario, tipo="padron", version=2)))
        hoja = libro["Carga"]
        fila = {"N.º de afiliado": self.a.numero, "Documento": self.a.documento,
                "Nombre y apellido": self.a.nombre, "Vigente desde": self.a.desde.isoformat(),
                "titular_documento": self.b.documento, "parentesco": "hijo"}
        for columna, celda in enumerate(hoja[1], 1):
            if celda.value in fila:
                hoja.cell(2, columna, fila[celda.value])
        salida = BytesIO()
        libro.save(salida)
        lote = previsualizar_importacion(financiador=self.org, usuario=self.usuario, tipo="padron", archivo=salida.getvalue(), clave=uuid4())
        self.assertEqual(lote.resumen["valida"], 1)
        barrera = Barrier(2)
        def importar():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                aplicar_importacion(importacion=lote, usuario=self.usuario)
                return lote.filas[0]["estado"]
            finally:
                close_old_connections()
        def vincular():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    editar_ficha(afiliado=self.b, usuario=self.usuario, entrada={"revision": 1, "motivo": "Vínculo inverso", "titular": self.a.pk, "parentesco": "hijo"})
                    return "aplicada"
                except (ValidationError, ConflictoPadron):
                    return "rechazada"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            primero = pool.submit(importar)
            segundo = pool.submit(vincular)
            resultados = [primero.result(timeout=20), segundo.result(timeout=20)]
        self.assertCountEqual(resultados, ["aplicada", "rechazada"])
        self.a.refresh_from_db()
        self.b.refresh_from_db()
        self.assertFalse(self.a.titular_id and self.b.titular_id)
