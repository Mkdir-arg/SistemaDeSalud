"""Señales del respaldo continuo en `/api/estado/` (#172, AUD-017).

- Apagado (sin `RESPALDO_CONTINUO=1`) no se informa nada nuevo: dev, demo y CI
  no pasan a 503 por un respaldo que no tienen.
- Encendido, el archivado de WAL se lee de `pg_stat_archiver`: atrasado si el
  último archivado es más viejo que `archive_timeout` más el margen, si el
  último intento falló después del último éxito o si PostgreSQL arrancó sin
  `archive_mode`.
- La copia base y la de archivos son latidos que dejan los servicios del
  perfil `respaldo-continuo` (`docker/postgres/respaldo-continuo.sh`).
"""
import os
from datetime import timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from . import latidos
from .latidos import Latido

NUEVOS = ("wal_archivado", "respaldo_base", "respaldo_archivos")
ENCENDIDO = {"RESPALDO_CONTINUO": "1"}
SCRIPT = Path(__file__).resolve().parents[3] / "docker" / "postgres" / "respaldo-continuo.sh"


def archivador(**cambios):
    """Una fila de `pg_stat_archiver` sana, con los cambios pedidos."""
    ahora = timezone.now()
    fila = {
        "archive_mode": "on", "archive_timeout": 300,
        "last_archived_wal": "000000010000000000000003", "last_archived_time": ahora - timedelta(seconds=60),
        "failed_count": 0, "last_failed_time": None, "arranque": ahora - timedelta(days=1),
    }
    fila.update(cambios)
    return fila


class RespaldoContinuoApagadoTests(TestCase):
    def test_apagado_no_agrega_servicios_ni_atrasados(self):
        with patch.dict(os.environ, {"RESPALDO_CONTINUO": ""}):
            datos = latidos.estado()
        for nombre in NUEVOS:
            self.assertNotIn(nombre, datos["servicios"])
            self.assertNotIn(nombre, datos["atrasados"])


@patch.dict(os.environ, ENCENDIDO)
class RespaldoContinuoEncendidoTests(TestCase):
    def estado_con(self, fila):
        with patch.object(latidos, "_leer_archivador", return_value=fila):
            return latidos.estado()

    def test_archivado_reciente_esta_al_dia(self):
        datos = self.estado_con(archivador())
        self.assertEqual(datos["servicios"]["wal_archivado"]["estado"], "al día")
        self.assertNotIn("wal_archivado", datos["atrasados"])

    def test_archivado_viejo_pasa_a_atrasado(self):
        viejo = timezone.now() - timedelta(seconds=300 + latidos.MARGEN_ARCHIVADO + 60)
        datos = self.estado_con(archivador(last_archived_time=viejo))
        self.assertEqual(datos["servicios"]["wal_archivado"]["estado"], "atrasado")
        self.assertIn("wal_archivado", datos["atrasados"])

    def test_fallo_posterior_al_ultimo_exito_pasa_a_atrasado(self):
        ahora = timezone.now()
        fila = archivador(last_archived_time=ahora - timedelta(seconds=90),
                          last_failed_time=ahora - timedelta(seconds=10), failed_count=4)
        datos = self.estado_con(fila)
        self.assertIn("wal_archivado", datos["atrasados"])
        self.assertIn("falló", datos["servicios"]["wal_archivado"]["detalle"])

    def test_fallo_anterior_al_ultimo_exito_no_alarma(self):
        ahora = timezone.now()
        fila = archivador(last_archived_time=ahora - timedelta(seconds=10),
                          last_failed_time=ahora - timedelta(seconds=90), failed_count=1)
        self.assertNotIn("wal_archivado", self.estado_con(fila)["atrasados"])

    def test_sin_archive_mode_pasa_a_atrasado(self):
        datos = self.estado_con(archivador(archive_mode="off"))
        self.assertIn("wal_archivado", datos["atrasados"])
        self.assertIn("archive_mode", datos["servicios"]["wal_archivado"]["detalle"])

    def test_nunca_archivo_tras_arranque_reciente_es_nunca_y_despues_atrasado(self):
        ahora = timezone.now()
        datos = self.estado_con(archivador(last_archived_time=None, last_archived_wal=None,
                                           arranque=ahora - timedelta(seconds=30)))
        self.assertEqual(datos["servicios"]["wal_archivado"]["estado"], "nunca")
        self.assertNotIn("wal_archivado", datos["atrasados"])
        datos = self.estado_con(archivador(last_archived_time=None, last_archived_wal=None))
        self.assertIn("wal_archivado", datos["atrasados"])

    def test_consulta_imposible_es_atrasado_y_no_rompe(self):
        datos = self.estado_con({"error": "No se pudo consultar pg_stat_archiver."})
        self.assertIn("wal_archivado", datos["atrasados"])

    def test_copias_base_y_de_archivos_son_latidos_con_su_plazo(self):
        Latido.objects.create(servicio="respaldo_base")
        Latido.objects.create(servicio="respaldo_archivos")
        datos = self.estado_con(archivador())
        self.assertEqual(datos["servicios"]["respaldo_base"]["estado"], "al día")
        self.assertEqual(datos["servicios"]["respaldo_archivos"]["estado"], "al día")
        hace = timezone.now() - timedelta(seconds=latidos.RESPALDO_CONTINUO_ESPERADOS["respaldo_archivos"] + 60)
        Latido.objects.filter(servicio="respaldo_archivos").update(momento=hace)
        datos = self.estado_con(archivador())
        self.assertIn("respaldo_archivos", datos["atrasados"])
        self.assertNotIn("respaldo_base", datos["atrasados"])

    @skipUnless(connection.vendor != "postgresql", "En PostgreSQL la consulta es real")
    def test_en_sqlite_no_rompe_y_avisa(self):
        datos = latidos.estado()
        self.assertIn("wal_archivado", datos["atrasados"])
        self.assertIn("PostgreSQL", datos["servicios"]["wal_archivado"]["detalle"])


@skipUnless(connection.vendor == "postgresql", "Requiere pg_stat_archiver de PostgreSQL")
@patch.dict(os.environ, ENCENDIDO)
class ArchivadorPostgresTests(TestCase):
    def test_la_consulta_real_devuelve_la_fila(self):
        fila = latidos._leer_archivador()
        self.assertNotIn("error", fila)
        self.assertIn(fila["archive_mode"], {"on", "off", "always"})
        self.assertIsInstance(fila["archive_timeout"], int)
        # La base de pruebas no archiva: el estado tiene que decirlo, no romper.
        if fila["archive_mode"] == "off":
            self.assertIn("wal_archivado", latidos.estado()["atrasados"])


@skipUnless(SCRIPT.exists(), "El script vive fuera de la imagen del backend")
class ContratoDelScriptTests(TestCase):
    """El script escribe el latido con SQL: si cambia la tabla o un nombre, falla acá."""

    def test_el_script_usa_la_tabla_y_los_nombres_del_modelo(self):
        texto = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(Latido._meta.db_table, texto)
        for campo in ("servicio", "momento", "detalle"):
            Latido._meta.get_field(campo)
            self.assertIn(campo, texto)
        for nombre in latidos.RESPALDO_CONTINUO_ESPERADOS:
            self.assertIn(nombre, texto)
