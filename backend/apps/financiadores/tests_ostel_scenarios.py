"""Pruebas del generador, sin Django/DB y sin importar la prevalidación #180."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from io import BytesIO
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from openpyxl import load_workbook

from .ostel_synthetic import (
    COLUMNAS, HOJAS, Lote, exportar_temporales, generar_escenarios, generar_xlsx,
)


def campos(fila):
    return dict(zip(COLUMNAS, fila))


def checksum_valido(cuil):
    # Comprobación independiente: suma ponderada incluyendo el verificador.
    return sum(int(n) * p for n, p in zip(cuil, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2, 1))) % 11 == 0


class EscenariosOSTELTests(unittest.TestCase):
    def setUp(self):
        self.catalogo = {e.codigo: e for e in generar_escenarios()}

    def filas(self, codigo, lote=0):
        return [campos(f) for f in self.catalogo[codigo].lotes[lote].filas]

    def test_esquema_exacto_y_cobertura(self):
        esperado = (
            "TIPO,NROAFI,CODEMP,CODPAR,APENOM,TIPODOC,NRODOC,CUIL,SEXO,COD_PLAN,"
            "FEC_NAC,FECING,FECBAJ,FECVTO,MOTIVO,NROBENE,NROPENS,CARNET,NIV,INCAPA,"
            "FACTURA,TABVAL,NUMERO,NROREF,A_CALLE,A_NRO,A_PISO,A_DPTO,A_TEL1,CELU1,"
            "EMAIL1,CODPOS,DESLOCA,CODPROV,CODZON,CODLOCA,CODEST,CODNAC,ESTADO"
        )
        self.assertEqual(COLUMNAS, tuple(esperado.split(",")))
        self.assertEqual(len(COLUMNAS), 39)
        self.assertEqual(set(self.catalogo), {
            "base", "numero_compartido", "referencia_presente", "referencia_ausente",
            "referencia_no_aaa", "cuil_invalido", "documento_discordante",
            "filas_vacias", "tipos_mixtos", "baja_repetida", "posible_reingreso",
            "vencimiento_lejano", "baja_anterior_ingreso", "lote_parcial",
        })
        self.assertEqual(len(generar_escenarios()), len(self.catalogo))
        for escenario in self.catalogo.values():
            for lote in escenario.lotes:
                for fila in lote.filas:
                    self.assertEqual(len(fila), 39)

    def test_determinismo_e_inmutabilidad(self):
        self.assertEqual(generar_escenarios(), generar_escenarios())
        with self.assertRaises(FrozenInstanceError):
            self.catalogo["base"].codigo = "cambio"
        with self.assertRaises(TypeError):
            self.catalogo["base"].lotes[0].filas[0][0] = "cambio"

    def test_identidades_marcadas_y_sin_contactos_operativos(self):
        for escenario in self.catalogo.values():
            for lote in escenario.lotes:
                for fila in lote.filas:
                    if all(v is None for v in fila):
                        continue
                    datos = campos(fila)
                    self.assertTrue(datos["APENOM"].startswith("PERSONA FICTICIA OSTEL "))
                    self.assertTrue(datos["EMAIL1"].endswith("@example.invalid"))
                    self.assertIsNone(datos["A_TEL1"])
                    self.assertIsNone(datos["CELU1"])

    def test_numero_compartido_con_personas_distintas(self):
        a, b = self.filas("numero_compartido")
        self.assertEqual(a["NROAFI"], b["NROAFI"])
        for columna in ("APENOM", "NRODOC", "CUIL"):
            self.assertNotEqual(a[columna], b[columna])

    def test_referencias(self):
        for codigo in ("referencia_presente", "referencia_no_aaa"):
            a, b = self.filas(codigo)
            self.assertEqual(b["NROREF"], a["NROAFI"])
        self.assertTrue(self.filas("referencia_presente")[0]["NROAFI"].endswith("AAA"))
        self.assertFalse(self.filas("referencia_no_aaa")[0]["NROAFI"].endswith("AAA"))
        ausentes = self.filas("referencia_ausente")
        self.assertNotIn(ausentes[0]["NROREF"], {f["NROAFI"] for f in ausentes})

    def test_checksum_y_discrepancia_son_estimulos_distintos(self):
        base = self.filas("base")[0]
        self.assertTrue(checksum_valido(base["CUIL"]))
        self.assertEqual(base["CUIL"][2:10], base["NRODOC"])
        invalido = self.filas("cuil_invalido")[0]
        self.assertFalse(checksum_valido(invalido["CUIL"]))
        self.assertEqual(invalido["CUIL"][2:10], invalido["NRODOC"])
        discordante = self.filas("documento_discordante")[0]
        self.assertTrue(checksum_valido(discordante["CUIL"]))
        self.assertNotEqual(discordante["CUIL"][2:10], discordante["NRODOC"])

    def test_vacias_y_tipos_sin_normalizacion(self):
        filas = self.catalogo["filas_vacias"].lotes[0].filas
        self.assertEqual([i for i, f in enumerate(filas) if all(v is None for v in f)], [0, 2, 4])
        a, b, c = self.filas("tipos_mixtos")
        self.assertEqual(a["NROAFI"], "000185")
        self.assertEqual([type(f["NROAFI"]) for f in (a, b, c)], [str, int, float])
        self.assertIs(type(c["NRODOC"]), bool)
        self.assertIsInstance(a["FECING"], date)
        self.assertEqual(b["FECING"], "2026-01-01")
        self.assertEqual(c["FECING"], "no-es-fecha")

    def test_secuencias_entre_archivos(self):
        baja, repetida = self.catalogo["baja_repetida"].lotes
        self.assertNotEqual(baja.nombre, repetida.nombre)
        self.assertEqual(baja.filas, repetida.filas)
        antes, despues = (self.filas("posible_reingreso", i)[0] for i in (0, 1))
        for columna in ("NROAFI", "NRODOC", "CUIL"):
            self.assertEqual(antes[columna], despues[columna])
        self.assertLess(antes["FECBAJ"], despues["FECING"])
        self.assertIsNone(despues["FECBAJ"])

    def test_fechas_y_lote_parcial(self):
        self.assertEqual(self.filas("vencimiento_lejano")[0]["FECVTO"], date(2099, 12, 31))
        conflicto = self.filas("baja_anterior_ingreso")[0]
        self.assertLess(conflicto["FECBAJ"], conflicto["FECING"])
        a, b, c = self.filas("lote_parcial")
        self.assertTrue(checksum_valido(a["CUIL"]))
        self.assertFalse(checksum_valido(b["CUIL"]))
        self.assertEqual(b["CUIL"][2:10], b["NRODOC"])
        self.assertLess(c["FECBAJ"], c["FECING"])
        self.assertEqual(len({f["NROAFI"] for f in (a, b, c)}), 3)

    def test_xlsx_ambas_hojas_todos_los_casos(self):
        for escenario in self.catalogo.values():
            for lote in escenario.lotes:
                for hoja in HOJAS:
                    with self.subTest(caso=escenario.codigo, lote=lote.nombre, hoja=hoja):
                        libro = load_workbook(BytesIO(generar_xlsx(lote, hoja=hoja)))
                        try:
                            self.assertEqual(libro.sheetnames, [hoja])
                            filas = list(libro[hoja].values)
                            self.assertEqual(filas[0], COLUMNAS)
                            esperado = [
                                tuple(datetime.combine(v, datetime.min.time()) if type(v) is date else v
                                      for v in fila) for fila in lote.filas
                            ]
                            self.assertEqual(filas[1:], esperado)
                            for original, leida in zip(esperado, filas[1:]):
                                self.assertEqual(tuple(map(type, original)), tuple(map(type, leida)))
                        finally:
                            libro.close()

    def test_exportador_rechaza_hoja_y_ancho_incorrectos(self):
        with self.assertRaises(ValueError):
            generar_xlsx(self.catalogo["base"].lotes[0], hoja="Carga")
        for ancho in (0, 38, 40):
            with self.subTest(ancho=ancho), self.assertRaises(ValueError):
                generar_xlsx(Lote("malformado", ((None,) * ancho,)))

    def test_xlsx_solo_filas_vacias_y_lote_sin_filas(self):
        for cantidad in (0, 1, 3):
            with self.subTest(cantidad=cantidad):
                filas = ((None,) * len(COLUMNAS),) * cantidad
                libro = load_workbook(BytesIO(generar_xlsx(Lote("vacias", filas))))
                try:
                    self.assertEqual(list(libro.active.values), [COLUMNAS, *filas])
                finally:
                    libro.close()

    def test_exportacion_temporal_completa_sin_sobrescritura(self):
        with TemporaryDirectory() as temporal:
            with patch("tempfile.mkdtemp", return_value=temporal):
                destino = exportar_temporales()
                self.assertEqual(destino, Path(temporal))
                rutas = {
                    Path(hoja) / escenario.codigo / f"{lote.nombre}.xlsx"
                    for hoja in HOJAS for escenario in generar_escenarios()
                    for lote in escenario.lotes
                }
                self.assertEqual({p.relative_to(destino) for p in destino.rglob("*.xlsx")}, rutas)
                for ruta in rutas:
                    libro = load_workbook(destino / ruta)
                    try:
                        self.assertEqual(libro.sheetnames, [ruta.parts[0]])
                        self.assertEqual(next(libro.active.values), COLUMNAS)
                    finally:
                        libro.close()
                original = {ruta: (destino / ruta).read_bytes() for ruta in rutas}
                with self.assertRaises(FileExistsError):
                    exportar_temporales()
                self.assertEqual(original, {ruta: (destino / ruta).read_bytes() for ruta in rutas})

    def test_texto_literal_no_formula(self):
        fila = list(self.catalogo["base"].lotes[0].filas[0])
        fila[COLUMNAS.index("APENOM")] = "=1+1"
        libro = load_workbook(BytesIO(generar_xlsx(Lote("literal", (tuple(fila),)))))
        try:
            self.assertEqual(libro.active["E2"].value, "=1+1")
            self.assertEqual(libro.active["E2"].data_type, "s")
        finally:
            libro.close()
