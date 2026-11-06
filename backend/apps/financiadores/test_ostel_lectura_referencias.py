"""Ida y vuelta generador -> lector OSTEL de identidad y referencias, sin Django/DB.

Rescata de #197 los casos sin equivalente en tests_ostel_scenarios y
test_ostel_prevalidacion. Sólo prueba conservación literal: no resuelve familias
ni interpreta NROREF, CODPAR o CUILTIT.
"""

from itertools import permutations
import unittest

from . import ostel_prevalidacion, ostel_synthetic as s

IDENTIFICADORES = ("NUMERO", "NROAFI", "NRODOC", "CUIL", "NROREF", "CODPAR", "TIPODOC", "CUILTIT")


def cambiar_columnas(fila, **cambios):
    if cambios.keys() - set(s.COLUMNAS):
        raise ValueError("Columna fuera del esquema OSTEL")
    valores = dict(zip(s.COLUMNAS, fila))
    valores.update(cambios)
    return tuple(valores[c] for c in s.COLUMNAS)


class LecturaReferenciasOSTELTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = {e.codigo: e for e in s.generar_escenarios()}

    def filas(self, codigo):
        return self.catalogo[codigo].lotes[0].filas

    def leer(self, filas, hoja):
        contenido = s.generar_xlsx(s.Lote("lectura", tuple(filas)), hoja=hoja)
        resultado = ostel_prevalidacion.prevalidar_ostel(contenido)
        return resultado, [dict(zip(s.COLUMNAS, f.celdas)) for f in resultado.filas[hoja]]

    def comprobar_identificadores(self, filas):
        for hoja in s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, leidas = self.leer(filas, hoja)
                self.assertEqual([f.numero for f in resultado.filas[hoja]], list(range(2, 2 + len(filas))))
                for original, leida in zip(filas, leidas):
                    original = dict(zip(s.COLUMNAS, original))
                    for campo in IDENTIFICADORES:
                        self.assertEqual(leida[campo].valor, original[campo], campo)
                self.assertFalse(resultado.anomalias)

    def test_escenarios_de_identidad_y_referencia_se_leen_literalmente(self):
        for codigo in (
            "texto_literal", "codigos_sin_homologar", "identidad_individual",
            "cuil_distinto_mismo_numero", "numero_distinto_mismo_cuil", "documento_discordante",
            "referencia_presente", "referencia_ausente", "referencia_no_aaa",
            "nroref_numero_coherente", "nroref_numero_ausente", "nroref_numero_ambiguo",
            "nroref_cuiltit_discordantes",
        ):
            with self.subTest(codigo=codigo):
                self.comprobar_identificadores(self.filas(codigo))

    def test_referencias_ambiguas_se_conservan_en_cualquier_orden(self):
        for codigo in ("referencia_ambigua", "nroref_numero_ambiguo"):
            for filas in permutations(self.filas(codigo)):
                with self.subTest(codigo=codigo, orden=tuple(f[s.COLUMNAS.index("NUMERO")] for f in filas)):
                    self.comprobar_identificadores(filas)

    def test_referencias_reciprocas_y_autorreferencia_se_conservan(self):
        a, b = self.filas("identidad_individual")
        numero_a = dict(zip(s.COLUMNAS, a))["NUMERO"]
        numero_b = dict(zip(s.COLUMNAS, b))["NUMERO"]
        casos = {
            "reciprocas": (cambiar_columnas(a, NROREF=numero_b), cambiar_columnas(b, NROREF=numero_a)),
            "autorreferencia": (cambiar_columnas(a, NROREF=numero_a),),
        }
        for caso, filas in casos.items():
            with self.subTest(caso=caso):
                self.comprobar_identificadores(filas)

    def test_numero_excel_no_recupera_ceros_perdidos(self):
        base, = self.filas("base")
        filas = (cambiar_columnas(base, NUMERO="000042"), cambiar_columnas(base, NUMERO=42))
        for hoja in s.HOJAS:
            with self.subTest(hoja=hoja):
                resultado, leidas = self.leer(filas, hoja)
                self.assertEqual([f["NUMERO"].valor for f in leidas], ["000042", "42"])
                self.assertIn(leidas[0]["NUMERO"].tipo, ("inlineStr", "s", "str"))
                self.assertEqual(leidas[1]["NUMERO"].tipo, "n")
                self.assertFalse(resultado.anomalias)


if __name__ == "__main__":
    unittest.main()
