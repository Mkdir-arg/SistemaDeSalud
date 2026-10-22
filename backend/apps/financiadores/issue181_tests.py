"""Evidencia pura #181 sobre #186 por SHA: lectura, no aplicación ni familia.

Desde la raíz: python -B -m unittest backend.apps.financiadores.issue181_tests -v
No requiere settings, Django, DB, red ni escribir XLSX. No reemplaza los tests
de API/familia existentes ni acredita controles de persistencia.
"""

from itertools import permutations
import unittest

from .issue181_fixtures import (
    cargar_referencia, cambiar_columnas, referencias_crudas,
)


class IdentidadLecturaIssue181Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = cargar_referencia("ostel_synthetic")
        cls.lector = cargar_referencia("ostel_prevalidacion")
        cls.catalogo = {e.codigo: e for e in cls.s.generar_escenarios()}

    def filas(self, codigo):
        return self.catalogo[codigo].lotes[0].filas

    def leer(self, filas, hoja):
        contenido = self.s.generar_xlsx(self.s.Lote("issue181", tuple(filas)), hoja=hoja)
        resultado = self.lector.prevalidar_ostel(contenido)
        return resultado, [dict(zip(self.s.COLUMNAS, f.celdas)) for f in resultado.filas[hoja]]

    def comprobar_identificadores(self, filas):
        campos = ("NUMERO", "NROAFI", "NRODOC", "CUIL", "NROREF", "CODPAR", "TIPODOC")
        for hoja in self.s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, leidas = self.leer(filas, hoja)
                self.assertEqual(len(leidas), len(filas))
                self.assertEqual([f.numero for f in resultado.filas[hoja]], list(range(2, 2 + len(filas))))
                for original, leida in zip(filas, leidas):
                    original = dict(zip(self.s.COLUMNAS, original))
                    for campo in campos:
                        self.assertEqual(leida[campo].valor, original[campo], campo)
                self.assertFalse(resultado.anomalias)

    def test_ceros_y_texto_literal_en_identificadores(self):
        self.comprobar_identificadores(self.filas("texto_literal"))
        self.comprobar_identificadores(self.filas("codigos_sin_homologar"))

    def test_nroafi_compartido_no_colapsa_identidades_individuales(self):
        filas = self.filas("identidad_individual")
        self.comprobar_identificadores(filas)
        for hoja in self.s.HOJAS:
            _, leidas = self.leer(filas, hoja)
            self.assertEqual(len({f["NROAFI"].valor for f in leidas}), 1)
            for campo in ("NUMERO", "NRODOC", "CUIL"):
                self.assertEqual(len({f[campo].valor for f in leidas}), 2)

    def test_colisiones_de_identidad_se_conservan_no_son_duplicados_exactos(self):
        for caso in ("cuil_distinto_mismo_numero", "numero_distinto_mismo_cuil"):
            with self.subTest(caso=caso):
                self.comprobar_identificadores(self.filas(caso))

    def test_documento_cuil_discordante_no_es_error_estructural_xlsx(self):
        # El guard semántico está en padron/_validar; este lector no lo sustituye.
        fila, = self.filas("documento_discordante")
        campos = dict(zip(self.s.COLUMNAS, fila))
        self.assertNotEqual(campos["CUIL"][2:10], campos["NRODOC"])
        self.comprobar_identificadores((fila,))

    def test_referencia_ausente_se_conserva_sin_inventar_titular(self):
        self.comprobar_identificadores(self.filas("referencia_ausente"))
        self.assertNotIn("CUILTIT", self.lector.COLUMNAS)

    def test_referencia_ambigua_conserva_todos_los_candidatos_en_cualquier_orden(self):
        for filas in permutations(self.filas("referencia_ambigua")):
            with self.subTest(orden=tuple(f[self.s.COLUMNAS.index("NRODOC")] for f in filas)):
                self.comprobar_identificadores(filas)

    def test_referencias_reciprocas_y_autorreferencia_no_son_familias_resueltas(self):
        for caso, filas in referencias_crudas(self.s).items():
            with self.subTest(caso=caso):
                self.comprobar_identificadores(filas)

    def test_orden_de_referencia_presente_no_cambia_conservacion(self):
        filas = self.filas("referencia_presente")
        self.comprobar_identificadores(filas)
        self.comprobar_identificadores(tuple(reversed(filas)))

    def test_referencia_no_aaa_no_se_homologa(self):
        self.comprobar_identificadores(self.filas("referencia_no_aaa"))

    def test_fila_exactamente_repetida_se_senala_sin_eliminar_evidencia(self):
        for hoja in self.s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, filas = self.leer(self.filas("fila_repetida"), hoja)
                self.assertEqual(len(filas), 2)
                self.assertEqual(resultado.resumen["duplicados_exactos"], 1)
                anomalia, = resultado.anomalias
                self.assertEqual((anomalia.codigo, anomalia.fila, anomalia.fila_original),
                                 ("fila_duplicada", 3, 2))

    def test_numero_excel_no_recupera_ceros_perdidos_ni_homologa_tipo(self):
        base, = self.filas("base")
        filas = (cambiar_columnas(self.s, base, NUMERO="000042"),
                 cambiar_columnas(self.s, base, NUMERO=42))
        for hoja in self.s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, leidas = self.leer(filas, hoja)
                self.assertEqual([f["NUMERO"].valor for f in leidas], ["000042", "42"])
                self.assertIn(leidas[0]["NUMERO"].tipo, ("inlineStr", "s", "str"))
                self.assertEqual(leidas[1]["NUMERO"].tipo, "n")
                self.assertFalse(resultado.anomalias)

    def test_resumen_y_repr_no_exponen_identificadores_o_referencias(self):
        for hoja in self.s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, _ = self.leer(self.filas("texto_literal"), hoja)
                publico = repr(resultado) + repr(resultado.resumen)
                for campo in ("NUMERO", "NROAFI", "NRODOC", "CUIL", "NROREF", "APENOM"):
                    valor = dict(zip(self.s.COLUMNAS, self.filas("texto_literal")[0]))[campo]
                    self.assertNotIn(valor, publico)


if __name__ == "__main__":
    unittest.main()
