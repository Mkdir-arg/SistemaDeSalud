"""Comparación de propuestas ficticias, sin persistencia ni derechos."""
from dataclasses import FrozenInstanceError, replace
from datetime import date
import unittest

from .derechos_borrador import BorradorDerechos
from .propuesta_derechos import comparar_borradores


class PropuestaTests(unittest.TestCase):
    def borrador(self, version=1, **cambios):
        datos = dict(codigo="ejemplo", version=version, fuente="Fuente ficticia",
                     financiador_id=10, regimen="dependencia", plan_id=20,
                     desde=date(2030, 1, 1), hasta=date(2030, 2, 1))
        return BorradorDerechos(**(datos | cambios))

    def comparar(self, historial, propuesta, **cambios):
        contexto = dict(financiador_id=10, regimen="dependencia", plan_id=20,
                        fecha=date(2030, 2, 1))
        return comparar_borradores(historial, propuesta, **(contexto | cambios))

    def test_incorpora_version_sin_modificar_anterior_y_muestra_antes_despues(self):
        anterior = self.borrador()
        nueva = self.borrador(2, desde=date(2030, 2, 1), hasta=None)
        historial, propuesta = [anterior], [nueva, anterior]
        vista = self.comparar(historial, propuesta)
        self.assertEqual(vista.nuevas, (nueva,))
        self.assertEqual(vista.antes.coincidencias, ())
        self.assertEqual(vista.despues.coincidencias, (nueva,))
        self.assertFalse(vista.despues.conflicto)
        self.assertEqual(historial, [anterior])
        self.assertEqual(propuesta, [nueva, anterior])
        self.assertEqual(vista, self.comparar(historial, list(reversed(propuesta))))

    def test_rechaza_borrado_o_reescritura_de_version_historica(self):
        anterior = self.borrador()
        nueva = self.borrador(2)
        for propuesta in ((), (nueva,), (replace(anterior, fuente="Cambio"),),
                          (replace(anterior, hasta=None),),
                          (replace(anterior, plan_id=21),)):
            with self.subTest(propuesta=propuesta), self.assertRaises(ValueError):
                self.comparar((anterior,), propuesta)
        self.assertEqual(anterior.fuente, "Fuente ficticia")
        self.assertEqual(anterior.hasta, date(2030, 2, 1))
        sin_cambio = self.comparar((anterior,), (anterior,))
        self.assertEqual(sin_cambio.nuevas, ())
        self.assertEqual(sin_cambio.antes, sin_cambio.despues)

    def test_identidad_unica_y_versiones_nuevas_crecientes_por_ambito(self):
        anterior = self.borrador(3)
        for historia, propuesta in (((anterior, anterior), (anterior,)),
                                   ((anterior,), (anterior, anterior)),
                                   ((anterior,), (anterior, self.borrador(2)))):
            with self.subTest(historia=historia, propuesta=propuesta), self.assertRaises(ValueError):
                self.comparar(historia, propuesta)
        otro_plan = self.borrador(1, plan_id=21)
        nuevo_codigo = self.borrador(1, codigo="otra")
        nuevas = self.comparar((anterior,), (anterior, otro_plan, nuevo_codigo)).nuevas
        self.assertEqual(nuevas, (nuevo_codigo, otro_plan))

    def test_rechaza_mezclar_financiadores_y_entradas_no_controladas(self):
        propio, ajeno = self.borrador(), self.borrador(financiador_id=11)
        for historial, propuesta in (((ajeno,), (ajeno,)),
                                     ((propio,), (propio, ajeno)),
                                     (({},), ()), ((), ({},))):
            with self.subTest(historial=historial, propuesta=propuesta), self.assertRaises(ValueError):
                self.comparar(historial, propuesta)
        for contexto in ({"financiador_id": True}, {"fecha": "2030-01-01"}):
            with self.subTest(contexto=contexto), self.assertRaises(ValueError):
                self.comparar((), (), **contexto)

    def test_superposicion_se_muestra_sin_elegir_ganador_ni_recortar_historia(self):
        anterior = self.borrador(hasta=None)
        nueva = self.borrador(2, desde=date(2030, 2, 1), hasta=None)
        vista = self.comparar((anterior,), (nueva, anterior))
        self.assertEqual(vista.antes.coincidencias, (anterior,))
        self.assertEqual(vista.despues.coincidencias, (anterior, nueva))
        self.assertTrue(vista.despues.conflicto)
        self.assertIsNone(anterior.hasta)
        with self.assertRaises(FrozenInstanceError):
            vista.nuevas = ()
        vacia = self.comparar((), ())
        self.assertEqual(vacia.nuevas, ())
        self.assertEqual(vacia.antes.coincidencias, ())
        self.assertFalse(vacia.despues.conflicto)


if __name__ == "__main__":
    unittest.main()
