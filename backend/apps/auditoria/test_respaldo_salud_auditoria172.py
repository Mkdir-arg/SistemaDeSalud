"""Respaldo verificable y salud funcional (#172, AUD-015/016/018).

- Los conteos de referencia salen del mismo snapshot que se vuelca: una
  escritura posterior no invalida un respaldo válido.
- Un conteo que falla nunca da «verificado».
- La base de verificación tiene nombre único y marca propia: nunca se borra una
  base ajena.
- Un servicio que nunca corrió pasa a atrasado tras su intervalo, y la cola de
  repartos vieja se ve en `/api/estado/`.
"""
import subprocess
import threading
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import patch

from django.core.management.base import CommandError
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.instituciones.models import Institucion

from . import latidos
from .management.commands.respaldar import TABLAS, Command
from .latidos import Latido


def ok(salida=""):
    return subprocess.CompletedProcess([], 0, salida, "")


def mal(error="falla sintética"):
    return subprocess.CompletedProcess([], 1, "", error)


CRED = {"host": "db", "port": "5432", "user": "u", "password": "", "name": "salud"}


class VerificacionRespaldoAuditoria172Tests(TestCase):
    def comando(self):
        comando = Command()
        comando.stdout, comando.stderr = StringIO(), StringIO()
        return comando

    def preparar(self, comando, respuestas):
        """Simula psql: devuelve respuestas según el SQL y registra las sentencias."""
        sentencias = []

        def psql(cred, base, sql):
            sentencias.append(sql)
            for clave, respuesta in respuestas.items():
                if clave in sql:
                    return respuesta(sql) if callable(respuesta) else respuesta
            return ok()

        comando._psql = psql
        return sentencias

    def verificar(self, comando, conteos):
        with TemporaryDirectory() as tmp, patch("subprocess.run", return_value=ok()):
            archivo = Path(tmp) / "salud.sql.gz"
            archivo.write_bytes(b"x" * 2048)
            comando._verificar(CRED, archivo, conteos)

    def marca_de(self, sentencias):
        comentario = next(s for s in sentencias if s.startswith("COMMENT ON DATABASE"))
        return comentario.split("'")[1]

    def test_conteos_iguales_al_snapshot_verifican_y_borran_solo_su_base(self):
        comando = self.comando()
        conteos = {t: 3 for t in TABLAS}
        estado = {}

        def contar(sql):
            return ok("\n".join(f"{t}|3" for t in conteos))

        def descripcion(sql):
            return ok(estado["marca"])

        sentencias = self.preparar(comando, {"UNION ALL": contar, "shobj_description": descripcion})
        original = comando._crear_verificacion

        def crear(cred, nombre, marca):
            estado["marca"] = marca
            original(cred, nombre, marca)

        comando._crear_verificacion = crear
        self.verificar(comando, conteos)
        creada = next(s for s in sentencias if s.startswith("CREATE DATABASE"))
        nombre = creada.split('"')[1]
        self.assertRegex(nombre, r"^salud_verif_\d{14}_[0-9a-f]{12}$")
        self.assertIn(f'DROP DATABASE "{nombre}";', sentencias)
        self.assertFalse(any("IF EXISTS" in s for s in sentencias))

    def test_diferencia_o_conteo_fallido_nunca_verifica(self):
        conteos = {t: 3 for t in TABLAS}
        casos = {
            "distinto": lambda sql: ok("\n".join(f"{t}|{2 if t == TABLAS[0] else 3}" for t in conteos)),
            "falta_tabla": lambda sql: ok("\n".join(f"{t}|3" for t in list(conteos)[1:])),
            "conteo_falla": lambda sql: mal(),
        }
        for nombre, contar in casos.items():
            with self.subTest(caso=nombre):
                comando = self.comando()
                self.preparar(comando, {"UNION ALL": contar, "shobj_description": ok("otra")})
                with self.assertRaises(CommandError):
                    self.verificar(comando, conteos)

    def test_no_borra_una_base_que_no_lleva_su_marca(self):
        comando = self.comando()
        sentencias = self.preparar(comando, {"shobj_description": ok("base-ajena")})
        comando._borrar_verificacion(CRED, "salud_verif_x", "salud-verificacion-respaldo:abc")
        self.assertFalse(any(s.startswith("DROP DATABASE") for s in sentencias))

    def test_si_la_base_ya_existe_no_la_toca(self):
        comando = self.comando()
        sentencias = self.preparar(comando, {"CREATE DATABASE": mal("already exists")})
        with self.assertRaises(CommandError):
            comando._crear_verificacion(CRED, "salud_verif_x", "marca")
        self.assertFalse(any(s.startswith("DROP DATABASE") for s in sentencias))


@skipUnless(connection.vendor == "postgresql", "Requiere snapshots exportados de PostgreSQL")
class SnapshotRespaldoAuditoria172Tests(TransactionTestCase):
    def test_escritura_posterior_al_snapshot_no_entra_en_los_conteos(self):
        Institucion.objects.create(nombre="Antes del snapshot")
        comando = Command()
        comando.stdout = StringIO()
        snapshots = []

        def volcar(cred, archivo, snapshot):
            snapshots.append(snapshot)

            def escribir():
                try:
                    Institucion.objects.create(nombre="Después del snapshot")
                finally:
                    connections.close_all()

            hilo = threading.Thread(target=escribir)
            hilo.start()
            hilo.join(10)

        comando._volcar = volcar
        conteos = comando._volcar_y_contar(CRED, Path("no-se-usa.sql.gz"))
        self.assertTrue(snapshots and snapshots[0])
        self.assertEqual(conteos["instituciones_institucion"], 1)
        self.assertEqual(Institucion.objects.count(), 2)
        for tabla in TABLAS:
            self.assertIn(tabla, conteos)


class SaludFuncionalAuditoria172Tests(TestCase):
    def test_nunca_vencido_pasa_a_atrasado_y_dentro_de_la_gracia_no(self):
        Latido.objects.create(servicio="correr_tiempos")
        datos = latidos.estado()
        self.assertEqual(datos["servicios"]["respaldar"]["estado"], "nunca")
        self.assertNotIn("respaldar", datos["atrasados"])
        hace = timezone.now() - timedelta(seconds=latidos.ESPERADOS["revisar_boxes"] + 60)
        Latido.objects.filter(servicio="correr_tiempos").update(momento=hace)
        datos = latidos.estado()
        self.assertEqual(datos["servicios"]["revisar_boxes"]["estado"], "atrasado")
        self.assertIn("revisar_boxes", datos["atrasados"])
        self.assertNotIn("respaldar", datos["atrasados"])

    def test_cola_de_repartos_vieja_se_informa(self):
        from apps.finanzas.models import TrabajoReparto

        with patch.object(TrabajoReparto.objects, "filter") as filtro:
            filtro.return_value.order_by.return_value.values_list.return_value.first.return_value = (
                timezone.now() - timedelta(seconds=latidos.ESPERA_MAXIMA_REPARTOS + 60)
            )
            datos = latidos.estado()
        self.assertIn("cola_repartos", datos["atrasados"])
        self.assertEqual(latidos.estado()["servicios"]["cola_repartos"]["estado"], "al día")
