"""Umbrales técnicos con fechas/plazos ficticios; no decisiones asistenciales."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime
import unittest
from .derechos_borrador import BorradorDerechos
from .simulacion_plazo import simular_plazo


class SimulacionPlazoTests(unittest.TestCase):
    def setUp(self):
        self.regla = BorradorDerechos("ficticia", 3, "Fuente ficticia", 10,
                                     "dependencia", None, date(2029, 1, 1))

    def simular(self, **cambios):
        datos = dict(dias_corridos=7, financiador_id=10, regimen="dependencia", plan_id=20,
                     fecha=date(2030, 1, 8), referencia=date(2030, 1, 1), evidencia="REF-FICTICIA")
        return simular_plazo(self.regla, **(datos | cambios))

    def test_antes_en_y_despues_sin_imponer_efecto_asistencial(self):
        for fecha, relacion in ((date(2030, 1, 7), "antes"),
                                (date(2030, 1, 8), "en"),
                                (date(2030, 1, 9), "despues")):
            with self.subTest(fecha=fecha):
                resultado = self.simular(fecha=fecha)
                self.assertEqual(resultado.estado, "calculado")
                self.assertEqual(resultado.limite, date(2030, 1, 8))
                self.assertEqual(resultado.relacion, relacion)
                self.assertEqual(resultado.regla, self.regla)
                self.assertEqual((resultado.dias_corridos, resultado.referencia, resultado.evidencia),
                                 (7, date(2030, 1, 1), "REF-FICTICIA"))

    def test_evidencia_incompleta_no_infiere_fecha_ni_calcula_limite(self):
        for cambios in (dict(referencia=None), dict(evidencia=None),
                        dict(referencia=None, evidencia=None)):
            with self.subTest(cambios=cambios):
                resultado = self.simular(**cambios)
                self.assertEqual(resultado.estado, "requiere_evidencia")
                self.assertIsNone(resultado.limite)
                self.assertIsNone(resultado.relacion)

    def test_ambito_y_vigencia_no_coincidentes_no_calculan(self):
        for cambios in (dict(financiador_id=11), dict(regimen="pasivo"),
                        dict(fecha=date(2028, 12, 31))):
            with self.subTest(cambios=cambios):
                resultado = self.simular(**cambios)
                self.assertEqual(resultado.estado, "sin_coincidencia")
                self.assertIsNone(resultado.limite)
                self.assertIsNone(resultado.relacion)

    def test_cero_y_calendario_real_no_convierten_meses_en_dias(self):
        ejemplos = ((date(2030, 1, 1), 0, date(2030, 1, 1)),
                    (date(2030, 1, 31), 1, date(2030, 2, 1)),
                    (date(2032, 2, 28), 1, date(2032, 2, 29)),
                    (date(2032, 2, 29), 1, date(2032, 3, 1)),
                    (date(2030, 12, 31), 1, date(2031, 1, 1)))
        for referencia, dias, limite in ejemplos:
            with self.subTest(referencia=referencia, dias=dias):
                resultado = self.simular(referencia=referencia, dias_corridos=dias, fecha=limite)
                self.assertEqual(resultado.limite, limite)
                self.assertEqual(resultado.relacion, "en")

    def test_tipos_y_rangos_invalidos_se_rechazan_sin_ocultar_errores(self):
        for cambio in (dict(dias_corridos=True), dict(dias_corridos=-1), dict(dias_corridos=1.5),
                       dict(referencia="2030-01-01"), dict(referencia=datetime(2030, 1, 1)),
                       dict(evidencia=""), dict(evidencia=" "), dict(evidencia=False)):
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                self.simular(**cambio)
        with self.assertRaises(ValueError):
            self.simular(referencia=date.max, dias_corridos=1)
        with self.assertRaises(ValueError):
            self.simular(dias_corridos=10**20)

    def test_salida_inmutable_reproducible_con_insumos_y_version_exactos(self):
        resultado = self.simular()
        self.assertEqual(resultado, self.simular())
        self.assertEqual((resultado.financiador_id, resultado.regimen, resultado.plan_id, resultado.fecha),
                         (10, "dependencia", 20, date(2030, 1, 8)))
        with self.assertRaises(FrozenInstanceError):
            resultado.relacion = "despues"
        self.assertEqual(self.regla.version, 3)
        otra = self.simular(dias_corridos=9)
        self.assertEqual(otra.limite, date(2030, 1, 10))
        self.assertEqual(resultado.limite, date(2030, 1, 8))
        self.assertEqual(otra.regla, resultado.regla)

    def test_plan_especifico_y_fin_exclusivo_reutilizan_seleccion_existente(self):
        self.regla = replace(self.regla, plan_id=21, hasta=date(2030, 1, 9))
        self.assertEqual(self.simular().estado, "sin_coincidencia")
        self.assertEqual(self.simular(plan_id=21).estado, "calculado")
        self.assertEqual(self.simular(plan_id=21, fecha=date(2030, 1, 9)).estado, "sin_coincidencia")
        with self.assertRaises(ValueError):
            self.simular(referencia=None, dias_corridos=-1)
        with self.assertRaises(TypeError):
            self.simular(expresion="activar()")

    def test_fecha_documentada_futura_solo_se_compara_no_afirma_que_ocurrio_evento(self):
        resultado = self.simular(referencia=date(2030, 2, 1))
        self.assertEqual(resultado.limite, date(2030, 2, 8))
        self.assertEqual(resultado.relacion, "antes")
        self.assertEqual(resultado.fecha, date(2030, 1, 8))
