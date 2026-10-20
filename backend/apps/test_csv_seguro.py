"""AUD-004: texto de usuarios no se interpreta como fórmula en CSV común."""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.common import _texto_csv


class TextoCSVSeguroTests(SimpleTestCase):
    def test_neutraliza_formulas_con_espacios_y_controles_iniciales(self):
        for texto in (
            '=HYPERLINK("https://example.test")', "+SUM(1;2)", "-2+3", "@SUM(A1:A2)",
            "  =1+1", "\t@SUM(1;2)", "\r-2+3", "\n+1", "\x00=1+1", "\u200b=1+1",
        ):
            with self.subTest(texto=repr(texto)):
                self.assertEqual(_texto_csv(texto), "'" + texto)

    def test_protege_etiquetas_anidadas_y_celdas_de_lista(self):
        for valor in ({"nombre": "=1+1"}, {"titulo": " +1"}, {"label": "@SUM(A1:A2)"}, ["=1+1", "normal"], [-2, "normal"]):
            with self.subTest(valor=valor):
                self.assertTrue(_texto_csv(valor).startswith("'"))

    def test_conserva_numeros_fechas_booleanos_y_textos_normales(self):
        for valor, esperado in (
            (-12, "-12"), (Decimal("-12.50"), "-12.50"), (3, "3"),
            ("2026-10-15T10:30:00-03:00", "15/10/2026 10:30"),
            (True, "Sí"), (False, "No"), (None, ""), ("", ""),
            ('Ana; "Marta"\nPaz', 'Ana; "Marta"\nPaz'), ("00123", "00123"),
            (["Ana", "Marta"], "Ana · Marta"), ({"nombre": "Ana"}, "Ana"),
        ):
            with self.subTest(valor=valor):
                self.assertEqual(_texto_csv(valor), esperado)

    def test_no_duplica_proteccion_de_texto_ya_literal(self):
        self.assertEqual(_texto_csv("'=1+1"), "'=1+1")
