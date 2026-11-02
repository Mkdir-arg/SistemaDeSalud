"""Contrato puro de borradores; fechas y fuentes ficticias, no normativa."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
import unittest

from .derechos_borrador import BorradorDerechos, previsualizar_borradores


class BorradoresTests(unittest.TestCase):
    def borrador(self, **cambios):
        datos = dict(codigo="ejemplo", version=1, fuente="Fuente ficticia",
                     financiador_id=10, regimen="dependencia", plan_id=None,
                     desde=date(2030, 1, 1), hasta=date(2030, 2, 1))
        return BorradorDerechos(**(datos | cambios))

    def test_version_con_fuente_y_ambito_inmutables(self):
        original = self.borrador()
        nueva = replace(original, version=2, fuente="Otra fuente ficticia")
        self.assertEqual((original.version, original.fuente), (1, "Fuente ficticia"))
        self.assertEqual(nueva.version, 2)
        with self.assertRaises(FrozenInstanceError):
            original.version = 3

    def test_rechaza_descriptores_incompletos_o_invalidos(self):
        for cambio in ({"version": 0}, {"version": True}, {"financiador_id": -1},
                       {"plan_id": False}, {"codigo": " "}, {"fuente": ""},
                       {"regimen": ""}, {"desde": "2030-01-01"},
                       {"hasta": date(2030, 1, 1)}):
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                self.borrador(**cambio)

    def vista(self, borradores, **cambios):
        datos = dict(financiador_id=10, regimen="dependencia", plan_id=20,
                     fecha=date(2030, 1, 15))
        return previsualizar_borradores(borradores, **(datos | cambios))

    def test_previsualiza_solo_ambito_y_limites_de_version_sin_decidir_derechos(self):
        anterior = self.borrador()
        nueva = self.borrador(version=2, desde=date(2030, 2, 1), hasta=None)
        ajeno = self.borrador(financiador_id=11)
        otro_regimen = self.borrador(regimen="pasivo")
        otro_plan = self.borrador(plan_id=21)
        reglas = (nueva, ajeno, otro_regimen, otro_plan, anterior)
        for fecha, esperado in ((date(2029, 12, 31), ()),
                                (date(2030, 1, 1), (anterior,)),
                                (date(2030, 1, 31), (anterior,)),
                                (date(2030, 2, 1), (nueva,)),
                                (date(2031, 1, 1), (nueva,))):
            with self.subTest(fecha=fecha):
                vista = self.vista(reglas, fecha=fecha)
                self.assertEqual(vista.coincidencias, esperado)
                self.assertFalse(vista.conflicto)
        self.assertEqual(reglas, (nueva, ajeno, otro_regimen, otro_plan, anterior))
        self.assertEqual(self.vista((otro_plan,), plan_id=None).coincidencias, ())

    def test_conflictos_no_eligen_precedencia_ni_ultima_version(self):
        general = self.borrador()
        especifico = self.borrador(version=2, plan_id=20)
        vista = self.vista((especifico, general))
        self.assertTrue(vista.conflicto)
        self.assertEqual(vista.coincidencias, (general, especifico))
        self.assertEqual(vista, self.vista((general, especifico)))
        with self.assertRaises(FrozenInstanceError):
            vista.coincidencias = ()
        self.assertTrue(self.vista((general, general)).conflicto)

    def test_consulta_invalida_no_se_interpreta_como_sin_impacto(self):
        for cambio in ({"financiador_id": True}, {"regimen": " "},
                       {"plan_id": 0}, {"fecha": "2030-01-15"}):
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                self.vista((), **cambio)
        with self.assertRaises(ValueError):
            self.vista(({},))
        with self.assertRaises(TypeError):
            self.borrador(activar=True)


if __name__ == "__main__":
    unittest.main()
