"""Pruebas sin configuración productiva, red ni conexión a una DB."""
import copy
import io
import json
import unittest
from unittest.mock import patch

from .contrato import clave_manual, id_valido, nombre_valido, validar_catalogo


def catalogo_ficticio():
    return {
        "provincia": [{"id": "01", "nombre": "Provincia de prueba"}, {"id": "02", "nombre": "Otra provincia"}],
        "partido": [{"id": "01001", "nombre": "Departamento de prueba", "provincia": {"id": "01"}}],
        "localidad": [{"id": "01001000001", "nombre": "Localidad de prueba", "provincia": {"id": "01"}, "departamento": {"id": "01001"}}],
    }


class ContratoTest(unittest.TestCase):
    def test_identificadores_conservan_ceros(self):
        filas = validar_catalogo(catalogo_ficticio())
        self.assertEqual(filas[-1]["codigo"], "01001000001")
        self.assertEqual(filas[-1]["partido"], "01001")

    def test_relacion_incompatible_no_se_publica(self):
        datos = catalogo_ficticio()
        datos["localidad"][0]["provincia"]["id"] = "02"
        with self.assertRaisesRegex(ValueError, "provincias distintas"):
            validar_catalogo(datos)

    def test_descarga_incompleta_no_es_catalogo(self):
        for nivel in catalogo_ficticio():
            datos = catalogo_ficticio()
            datos[nivel] = []
            with self.subTest(nivel=nivel), self.assertRaises(ValueError):
                validar_catalogo(datos)

    def test_ids_numericos_y_duplicados_se_rechazan(self):
        datos = catalogo_ficticio()
        datos["provincia"].append(copy.deepcopy(datos["provincia"][0]))
        with self.assertRaisesRegex(ValueError, "duplicados"):
            validar_catalogo(datos)
        datos = catalogo_ficticio()
        datos["provincia"][0]["id"] = 1
        with self.assertRaisesRegex(ValueError, "texto numérico"):
            validar_catalogo(datos)

    def test_clave_manual_aisla_organizacion_y_contexto(self):
        def clave(nombre, inst=1, prov=1):
            return clave_manual("localidad", nombre, inst, None, prov, None)
        self.assertEqual(clave("  Lugar   de Prueba "), clave("lugar de prueba"))
        self.assertNotEqual(clave("Lugar de prueba"), clave("Lugar de prueba", inst=2))
        self.assertNotEqual(clave("Lugar de prueba"), clave("Lugar de prueba", prov=2))
        self.assertNotEqual(clave("Peña"), clave("Pena"))
        self.assertNotEqual(clave("Lugar de prueba"), clave_manual("localidad", "Lugar de prueba", None, 1, 1, None))

    def test_manual_no_tiene_ambito_global(self):
        for inst, fin in ((None, None), (1, 1)):
            with self.subTest(inst=inst, fin=fin), self.assertRaises(ValueError):
                clave_manual("provincia", "Lugar", inst, fin, None, None)

    def test_nombres_admiten_toponimos_sin_fusion_aproximada(self):
        for nombre in ("28 de Noviembre", "O'Higgins", "Villa Ángela", "Test-lugar"):
            self.assertEqual(nombre_valido(nombre), nombre)
        for nombre in (None, "", "   ", "x" * 101, "Lugar\x00"):
            with self.subTest(nombre=nombre), self.assertRaises(ValueError):
                nombre_valido(nombre)
        self.assertFalse(id_valido(True))
        self.assertFalse(id_valido("01"))
        self.assertFalse(id_valido(2**63))
        self.assertTrue(id_valido(1))


class DescargaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Esta configuración usa backend dummy: una conexión sería un error.
        import os
        os.environ["DJANGO_SETTINGS_MODULE"] = "apps.geografia.issue136_settings"
        import django
        django.setup()

    def test_paginacion_completa_y_transporte_sin_credenciales(self):
        from .sincronizacion import descargar
        datos = catalogo_ficticio()
        llamadas = []
        def abrir(pedido, timeout):
            llamadas.append(pedido)
            recurso = pedido.full_url.split("/api/")[1].split("?")[0]
            tipo = {"provincias": "provincia", "departamentos": "partido", "localidades": "localidad"}[recurso]
            filas = datos[tipo]
            return io.BytesIO(json.dumps({recurso: filas, "total": len(filas), "cantidad": len(filas), "inicio": 0}).encode())
        self.assertEqual(len(descargar(abrir)), 4)
        self.assertEqual(len(llamadas), 3)
        self.assertTrue(all(p.full_url.startswith("https://apis.datos.gob.ar/georef/api/") for p in llamadas))
        self.assertTrue(all(not p.has_header("Authorization") and not p.has_header("Cookie") for p in llamadas))

    def test_pagina_parcial_y_payload_invalido_fallan(self):
        from .sincronizacion import descargar
        for datos in (b"not json", b"[]", b'{"provincias":[],"total":10,"cantidad":0,"inicio":0}'):
            with self.subTest(datos=datos), self.assertRaises(ValueError):
                descargar(lambda *a, **k: io.BytesIO(datos))

    def test_modo_seco_no_accede_a_db(self):
        from .sincronizacion import sincronizar
        with patch("apps.geografia.sincronizacion.Catalogo.objects") as objetos:
            self.assertEqual(sincronizar(seco=True, descargar_fn=lambda: validar_catalogo(catalogo_ficticio())), {"entidades": 4, "publicado": False})
            objetos.get_or_create.assert_not_called()

    def test_cadencia_semanal_y_reintento_diario(self):
        from datetime import timedelta
        from types import SimpleNamespace
        from django.utils import timezone
        from .sincronizacion import corresponde
        ahora = timezone.now()
        self.assertTrue(corresponde(None, ahora))
        self.assertFalse(corresponde(SimpleNamespace(actualizado=ahora - timedelta(days=6), intento=None), ahora))
        self.assertTrue(corresponde(SimpleNamespace(actualizado=ahora - timedelta(days=8), intento=None), ahora))
        self.assertFalse(corresponde(SimpleNamespace(actualizado=None, intento=ahora - timedelta(hours=23)), ahora))

    def test_edicion_sin_cambio_geografico_conserva_instantanea_sin_consultar_catalogo(self):
        from types import SimpleNamespace
        from .servicios import resolver
        anterior = SimpleNamespace(provincia=SimpleNamespace(pk=1), partido=None, localidad=None,
            textos={"provincia": "Nombre histórico"}, origenes={"provincia": "georef"})
        with patch("apps.geografia.servicios.Lugar.objects") as lugares:
            resultado = resolver.__wrapped__({"provincia": {"id": 1}, "partido": None, "localidad": None}, dueno={"institucion_id": 1, "financiador_id": None}, anterior=anterior)
            self.assertIs(resultado, anterior)
            lugares.filter.assert_not_called()

    def test_contrato_de_serializers_no_expone_ubicacion_en_listados_minimizados(self):
        from apps.instituciones.serializers import InstitucionSerializer
        from apps.registros.serializers import CiudadanoSerializer, CiudadanoListadoSerializer
        from apps.financiadores.serializers import AfiliadoSerializer
        self.assertIn("geografia", CiudadanoSerializer().fields)
        self.assertIn("geografia", InstitucionSerializer().fields)
        self.assertIn("geografia_laboral", AfiliadoSerializer().fields)
        self.assertNotIn("geografia", CiudadanoListadoSerializer().fields)
        self.assertFalse(CiudadanoSerializer().fields["geografia"].write_only)

    def test_ids_extremos_de_consulta_se_rechazan_antes_de_consultar_organizaciones(self):
        from types import SimpleNamespace
        from rest_framework.exceptions import ValidationError
        from .api import autorizar_ambito
        with self.assertRaises(ValidationError):
            autorizar_ambito(SimpleNamespace(), {"ambito": "institucion", "organizacion": "9" * 5000})


if __name__ == "__main__":
    unittest.main()
