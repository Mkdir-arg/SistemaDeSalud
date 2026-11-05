"""Copia protegida de CODPAR desde lotes completamente ficticios."""
from hashlib import sha256
import json
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Usuario
from . import models as m
from .ostel_synthetic import Lote, generar_xlsx, _persona


class CodparImportacionFixture:
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="OSTEL ficticia", tipo="obra_social")
        self.user = Usuario.objects.create_user("copia@example.invalid")
        self.member = m.MembresiaFinanciador.objects.create(
            financiador=self.org, usuario=self.user, rol="operador",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.base = f"/api/financiadores/{self.org.pk}/"
        archivo = generar_xlsx(Lote("entrada", (_persona(1, NUMERO="000001", CODPAR=" 00-XD1 "),)))
        preview = self.client.post(self.base + "previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("ficticio.xlsx", archivo), "clave": str(uuid4()),
            "fuente": "base", "cobertura_habilitada": False,
        }, format="multipart")
        self.assertEqual(preview.status_code, 200)
        aplicada = self.client.post(self.base + "confirmar-importacion/", {
            "importacion": preview.data["id"],
        }, format="json")
        self.assertEqual(aplicada.status_code, 200)
        self.lote = m.Importacion.objects.get(pk=preview.data["id"])
        self.fila = self.lote.filas[0]
        self.assertEqual(self.fila["estado"], "aplicada")
        self.afiliado = m.Afiliado.objects.get(pk=self.fila["afiliado"])
        self.url = self.base + f"padron/{self.afiliado.pk}/salud/"
        self.assertFalse(m.SaludPadron.objects.exists())

    def designar(self):
        self.member.acceso_padron_salud = True
        self.member.save()

    def copiar(self, **extra):
        return self.client.post(self.url + "codpar-ostel/", {
            "importacion": self.lote.pk, "fila": self.fila["fila"], "revision": 1, **extra,
        }, format="json")

    def huella(self):
        tablas = (m.Afiliado, m.SaludPadron, m.HistorialAfiliacion,
                  m.HistorialPadronProtegido, m.Importacion, m.EventoCobertura)
        datos = [list(tabla.objects.order_by("pk").values()) for tabla in tablas]
        return sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()


class CodparImportacionTests(CodparImportacionFixture, APITestCase):
    def test_importacion_administrativa_y_copia_designada_con_procedencia(self):
        self.designar()
        general = self.client.get(self.base + f"padron/{self.afiliado.pk}/").data
        lote_antes = m.Importacion.objects.values().get(pk=self.lote.pk)
        respuesta = self.copiar()
        self.assertEqual(respuesta.status_code, 200, getattr(respuesta, "data", None))
        self.assertEqual(respuesta.data["codpar_ostel"], " 00-XD1 ")
        self.assertEqual(respuesta.data["revision"], 2)
        self.assertEqual(self.client.get(self.url).data, respuesta.data)
        historial = self.client.get(self.url + "historial/").data["results"]
        self.assertEqual(historial[0]["motivo"],
                         f"Copia CODPAR OSTEL: lote {self.lote.pk}, hoja {self.fila['hoja']}, fila Excel {self.fila['fila_excel']}.")
        self.assertEqual(historial[0]["cambios"], {"codpar_ostel": {"anterior": "", "nuevo": " 00-XD1 "}})
        self.assertEqual(self.client.get(self.base + f"padron/{self.afiliado.pk}/").data, general)
        self.assertEqual(m.Importacion.objects.values().get(pk=self.lote.pk), lote_antes)
        self.assertNotIn("00-XD1", str(list(m.EventoCobertura.objects.values())))
        self.assertEqual(self.copiar(revision=2).data, respuesta.data)
        self.assertEqual(self.client.get(self.url + "historial/").data["count"], 1)

    def rechaza_sin_cambios(self, estado, **entrada):
        antes = self.huella()
        respuesta = self.copiar(**entrada)
        self.assertEqual(respuesta.status_code, estado, getattr(respuesta, "data", None))
        self.assertEqual(self.huella(), antes)

    def test_exige_designacion_activa_y_rol_editor(self):
        self.rechaza_sin_cambios(403)
        self.designar()
        self.member.rol = "auditor"
        self.member.save()
        self.rechaza_sin_cambios(403)
        self.member.rol = "operador"
        self.member.activo = False
        self.member.save()
        self.rechaza_sin_cambios(404)

    def test_revision_y_contrato_explicito_sin_reescribir_fuente(self):
        self.designar()
        self.assertEqual(self.copiar().status_code, 200)
        self.rechaza_sin_cambios(409)
        for entrada in ({"revision": None}, {"revision": True}, {"fila": 0},
                        {"importacion": None}, {"codpar_ostel": "OT1"},
                        {"afiliado": self.afiliado.pk}, {"motivo": "Sustituir procedencia"}):
            with self.subTest(entrada=entrada):
                self.rechaza_sin_cambios(400, **entrada)

    def test_fuente_invalida_no_borra_codigo_previo(self):
        self.designar()
        self.assertEqual(self.copiar().status_code, 200)
        for codigo in (None, "", "   ", 1, True, "X" * 41):
            with self.subTest(tipo=type(codigo).__name__):
                self.lote.filas[0]["original"]["CODPAR"] = codigo
                self.lote.save(update_fields=["filas"])
                self.rechaza_sin_cambios(400, revision=2)

    def test_solo_fila_aplicada_unica_y_formato_ostel(self):
        self.designar()
        self.rechaza_sin_cambios(400, fila=999)
        for estado in ("valida", "revision", "omitida"):
            self.lote.filas[0]["estado"] = estado
            self.lote.save(update_fields=["filas"])
            self.rechaza_sin_cambios(400)
        self.lote.filas[0]["estado"] = "aplicada"
        self.lote.filas.append(dict(self.lote.filas[0]))
        self.lote.save(update_fields=["filas"])
        self.rechaza_sin_cambios(400)
        self.lote.filas.pop()
        for version, tipo in ((1, "padron"), (2, "padron"), (3, "catalogo")):
            self.lote.version, self.lote.tipo = version, tipo
            self.lote.save()
            self.rechaza_sin_cambios(400)

    def test_destino_persistido_y_aislamiento_sin_resolver_identificadores(self):
        self.designar()
        # Aunque el número visible coincida, la fila no puede vincularse a otra persona.
        otro = m.Afiliado.objects.create(
            financiador=self.org, numero=self.afiliado.numero, documento="FICTICIO-OTRO",
            nombre="Otra persona ficticia", desde=self.afiliado.desde,
        )
        self.lote.filas[0]["afiliado"] = otro.pk
        self.lote.save(update_fields=["filas"])
        self.rechaza_sin_cambios(400)
        self.lote.filas[0].pop("afiliado")
        self.lote.save(update_fields=["filas"])
        self.rechaza_sin_cambios(400)
        otra_org = m.Financiador.objects.create(nombre="Otra ficticia", tipo="obra_social")
        self.lote.financiador = otra_org
        self.lote.save(update_fields=["financiador"])
        self.rechaza_sin_cambios(404)
        self.rechaza_sin_cambios(404, importacion=self.lote.pk + 999)

    def test_afiliado_ajeno_no_es_destino(self):
        self.designar()
        otra = m.Financiador.objects.create(nombre="Otra ficticia", tipo="obra_social")
        ajeno = m.Afiliado.objects.create(
            financiador=otra, numero="FICTICIO-AJENO", documento="FICTICIO-AJENO",
            nombre="Persona ficticia ajena", desde=self.afiliado.desde,
        )
        self.url = self.base + f"padron/{ajeno.pk}/salud/"
        self.rechaza_sin_cambios(404)


class CodparImportacionConcurrenciaTests(CodparImportacionFixture, TransactionTestCase):
    def copia_con_conexion_propia(self, *, pid_queue=None, barrera=None):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout='10s'")
                if pid_queue is not None:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid_queue.put(cursor.fetchone()[0])
            if barrera is not None:
                barrera.wait(timeout=5)
            client = APIClient()
            client.force_authenticate(self.user)
            return client.post(self.url + "codpar-ostel/", {
                "importacion": self.lote.pk, "fila": self.fila["fila"], "revision": 1,
            }, format="json").status_code
        finally:
            connection.close()

    def test_revocacion_mientras_copia_espera_lote(self):
        self.designar()
        antes = self.huella()
        pid_queue = Queue()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                m.Importacion.objects.select_for_update().get(pk=self.lote.pk)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    propietario = cursor.fetchone()[0]
                futuro = pool.submit(self.copia_con_conexion_propia, pid_queue=pid_queue)
                pid = pid_queue.get(timeout=5)
                limite = monotonic() + 8
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid])
                        bloqueantes = cursor.fetchone()[0]
                    if propietario in bloqueantes:
                        break
                    if monotonic() > limite:
                        self.fail("La copia no esperó el lock del lote.")
                    sleep(0.02)
                self.member.acceso_padron_salud = False
                self.member.save(update_fields=["acceso_padron_salud"])
            self.assertEqual(futuro.result(timeout=12), 403)
        self.assertEqual(self.huella(), antes)

    def test_copias_concurrentes_con_revision_unica(self):
        self.designar()
        barrera = Barrier(2)
        fuente = m.Importacion.objects.values().get(pk=self.lote.pk)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(self.copia_con_conexion_propia, barrera=barrera) for _ in range(2)]
            estados = [f.result(timeout=15) for f in futuros]
        self.assertCountEqual(estados, [200, 409])
        self.assertEqual(m.HistorialPadronProtegido.objects.count(), 1)
        self.assertEqual(m.SaludPadron.objects.get(afiliado=self.afiliado).revision, 2)
        self.assertEqual(m.Importacion.objects.values().get(pk=self.lote.pk), fuente)
