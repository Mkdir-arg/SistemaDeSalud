"""Conciliación del informe ejecutivo con sus fuentes y permisos existentes."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.financiadores.models import DistribucionCobro, ResolucionSaldo
from apps.financiadores.test_cobertura import CoberturaSetup
from .comparativas import comparar
from .dinero import crear_obligacion_cobro, registrar_movimiento
from .models import AccesoFinanciero, AjusteGasto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto, MovimientoDinero
from .procesamiento import solicitar_reparto
from . import test_reportes, test_reportes_dinero


class VariacionesTests(SimpleTestCase):
    def test_base_cero_negativa_y_ausente_no_inventan_porcentaje(self):
        for base in ("0.00", "-1.00"):
            self.assertIsNone(comparar("10.00", base)["porcentaje"])
        self.assertIsNone(comparar(None, "10.00")["importe"])
        self.assertEqual(comparar("110.01", "100.00"), {"importe": "10.01", "porcentaje": "10.01", "motivo": None})


class ComparativaGastosTests(APITestCase):
    setUp = test_reportes.ReportesFinanzasTests.setUp
    gasto = test_reportes.ReportesFinanzasTests.gasto

    def consultar(self, **filtros):
        return self.client.get("/api/reportes-finanzas/comparativa/", {**self.parametros, **filtros})

    def test_mismos_importes_que_resumen_ajustes_y_ambos_meses_auditados(self):
        self.mes = date(2026, 8, 1)
        self.gasto("80.00")
        self.mes = date(2026, 9, 1)
        self.parametros["periodo_economico"] = str(self.mes)
        gasto = self.gasto("100.01")
        AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-0.01"), motivo="Ajuste", registrado_por=self.usuario)
        AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-30.00"), motivo="Pendiente", estado="pendiente_aprobacion")
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        d = respuesta.data
        self.assertEqual(d["variaciones"]["aprobados"], {"importe": "20.00", "porcentaje": "25.00", "motivo": None})
        original = self.client.get("/api/reportes-finanzas/", self.parametros).data
        for campo in ("aprobados", "pendientes_aprobacion", "distribuido", "sin_distribuir", "ajustes_pendientes"):
            self.assertEqual(d["actual"][campo], original[campo])
        self.assertEqual(d["agrupaciones"][0]["variacion"]["importe"], "20.00")
        self.assertEqual(len(d["serie"]), 6)
        self.assertEqual(set(AccesoFinanciero.objects.filter(accion="comparativa", resultados__gt=0).values_list("periodo_economico", flat=True)), {date(2026, 8, 1), date(2026, 9, 1)})

    def test_ausencia_y_reparto_pendiente_no_son_cero_comparable(self):
        gasto = self.gasto()
        solicitar_reparto(gasto.pk)
        d = self.consultar().data
        self.assertIsNone(d["variaciones"]["aprobados"]["importe"])
        self.assertIsNone(d["actual"]["distribuido"])
        self.assertIsNone(d["variaciones"]["distribuido"]["importe"])
        self.assertIsNone(d["agrupaciones"][0]["anterior"])

    def test_permiso_limitado_no_incluye_otras_areas_ni_sensibles(self):
        self.gasto()
        self.gasto("900.00", self.otra)
        secreto = self.gasto("999.00")
        Gasto.objects.filter(pk=secreto.pk).update(sensible=True)
        self.membresia.rol = Membresia.Rol.ADMINISTRATIVO
        self.membresia.save()
        concesion = ConcesionFinanciera.objects.create(membresia=self.membresia, accion="ver_gastos")
        concesion.areas.add(self.area)
        d = self.consultar().data
        self.assertEqual(d["actual"]["aprobados"], "100.01")
        self.assertEqual(len(d["agrupaciones"]), 1)
        self.assertEqual(self.consultar(area=self.otra.pk).status_code, 403)
        self.assertEqual(self.consultar(area_sin_asignar="true").status_code, 403)

    def test_anio_anterior_y_validacion_de_fechas(self):
        self.mes = date(2025, 9, 1)
        self.gasto("50.00")
        self.mes = date(2026, 9, 1)
        self.gasto("100.00")
        d = self.consultar(periodo_economico="2026-09-01", comparar="anio_anterior", meses=12).data
        self.assertEqual(d["anterior"]["aprobados"], "50.00")
        self.assertEqual(d["variaciones"]["aprobados"]["porcentaje"], "100.00")
        self.assertEqual(len(d["serie"]), 12)
        for filtros in ({"meses": 120}, {"comparar": "libre"}, {"periodo_economico": "0001-01-01"}, {"periodo_economico": "2026-09-02"}):
            self.assertEqual(self.consultar(**filtros).status_code, 400)

    def test_auditoria_falla_cerrada(self):
        self.gasto()
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("simulado")):
            r = self.consultar()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("actual", r.data)

    def test_concepto_renombrado_conserva_un_solo_grupo_y_detalle_conciliable(self):
        self.gasto("100.00")
        self.concepto.nombre = "Energía eléctrica"
        self.concepto.save()
        self.gasto("50.00")
        r = self.consultar()
        self.assertEqual(len(r.data["agrupaciones"]), 1)
        grupo = r.data["agrupaciones"][0]
        self.assertEqual(grupo["actual"]["aprobados"], "150.00")
        self.assertEqual(grupo["concepto_nombre"], "Energía eléctrica")
        detalle = self.client.get("/api/gastos/", {**self.parametros, "area": self.area.pk, "concepto": self.concepto.pk, "estado_operativo": "aprobado"})
        self.assertEqual(detalle.data["count"], 2)

    def test_faltantes_conocidos_por_mes_respetan_vigencia_y_permisos(self):
        control = ExpectativaGasto.objects.create(institucion=self.institucion, area=self.area, concepto=self.concepto, vigente_desde="2026-08-01")
        ExpectativaGasto.objects.create(institucion=self.institucion, area=self.otra, concepto=self.concepto, vigente_desde="2026-08-01")
        IndicacionCargaGasto.objects.create(expectativa=control, periodo_economico="2026-09-01", estado="carga_completa", registrado_por=self.usuario)
        self.membresia.rol = Membresia.Rol.ADMINISTRATIVO
        self.membresia.save()
        permiso = ConcesionFinanciera.objects.create(membresia=self.membresia, accion="ver_gastos")
        permiso.areas.add(self.area)
        d = self.consultar(periodo_economico="2026-09-01").data
        self.assertEqual((d["actual"]["controles"], d["actual"]["controles_sin_completar"]), (1, 0))
        self.assertEqual((d["anterior"]["controles"], d["anterior"]["controles_sin_completar"]), (1, 1))
        self.assertTrue(d["anterior"]["provisional"])
        self.assertEqual(d["serie"][0]["controles"], 0)
        self.assertTrue(AccesoFinanciero.objects.filter(accion="comparativa", area=self.area, periodo_economico="2026-08-01", resultados=1).exists())
        self.assertFalse(AccesoFinanciero.objects.filter(accion="comparativa", area=self.otra).exists())


class ComparativaDineroTests(APITestCase):
    setUp = test_reportes_dinero.ReportesDineroTests.setUp
    cuenta = test_reportes_dinero.ReportesDineroTests.cuenta
    pago = test_reportes_dinero.ReportesDineroTests.pago

    def consultar(self, **filtros):
        return self.client.get("/api/reportes-dinero/comparativa/", {"institucion": self.institucion.pk, "periodo_economico": "2026-09-01", **filtros})

    def test_neto_negativo_reintegros_pendientes_y_detalle_exactamente_conciliable(self):
        cuenta = self.cuenta()
        original = self.pago(cuenta, "80.00", date(2026, 8, 31))
        for importe in ("10.01", "19.99"):
            MovimientoDinero.objects.create(obligacion=cuenta, institucion=self.institucion, tipo="reintegro", original=original, importe=Decimal(importe), fecha=date(2026, 9, 2), motivo="Reintegro", clave=uuid4(), solicitud={"fixture": True}, autor=self.usuario)
        pendiente = self.pago(cuenta, "5.00")
        MovimientoDinero.objects.filter(pk=pendiente.pk).update(estado="pendiente_aprobacion")
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        d = r.data
        self.assertEqual(d["actual"]["pagos_netos"], "-30.00")
        self.assertEqual(d["actual"]["por_aprobar"]["pagos"], "5.00")
        self.assertEqual(d["anterior"]["pagos_netos"], "80.00")
        self.assertEqual(d["agrupaciones"][0]["pagos_netos"], "-30.00")
        filtros = {**self.parametros, **d["agrupaciones"][0]["filtros"], "estado": "aprobado"}
        listado = self.client.get("/api/movimientos-dinero/", filtros)
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado.data["count"], 2)
        self.assertEqual(sum(Decimal(f["importe"]) for f in listado.data["results"]), Decimal("30.00"))
        filtros["estado"] = "pendiente_aprobacion"
        self.assertEqual(self.client.get("/api/movimientos-dinero/", filtros).data["count"], 1)

    def test_permisos_y_filtros_no_pueden_ensanchar_detalle(self):
        self.pago(self.cuenta())
        self.pago(self.cuenta(area=self.otra_area))
        self.pago(self.cuenta(sensible=True))
        usuario = Usuario.objects.create_user("reporte-limitado@test.local", "x")
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol="administrativo")
        permiso = ConcesionFinanciera.objects.create(membresia=membresia, accion="ver_dinero")
        permiso.areas.add(self.area)
        self.client.force_authenticate(usuario)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["actual"]["pagos_netos"], "30.00")
        self.assertEqual(len(r.data["agrupaciones"]), 1)
        filtros = {**self.parametros, **r.data["agrupaciones"][0]["filtros"], "estado": "aprobado"}
        self.assertEqual(self.client.get("/api/movimientos-dinero/", filtros).data["count"], 1)
        filtros["area"] = self.otra_area.pk
        self.assertEqual(self.client.get("/api/movimientos-dinero/", filtros).data["count"], 0)
        self.assertEqual(self.consultar(area=self.otra_area.pk).status_code, 403)
        for campo, valor in (("reporte_financiador", "abc"), ("reporte_prestacion", "-1"), ("reporte_concepto", "0"), ("reporte_pagador", "otro"), ("tipo_cuenta", "libre")):
            self.assertEqual(self.client.get("/api/movimientos-dinero/", {**self.parametros, campo: valor}).status_code, 400)

    def test_auditoria_falla_cerrada_y_sin_permiso_no_devuelve_cero(self):
        self.pago(self.cuenta())
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("simulado")):
            self.assertEqual(self.consultar().status_code, 503)
        usuario = Usuario.objects.create_user("sin-dinero@test.local", "x")
        self.client.force_authenticate(usuario)
        self.assertEqual(self.consultar().status_code, 403)


class FinanciadoresReporteTests(CoberturaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def test_financiador_copago_y_resolucion_no_duplican_ni_adivinan_el_pagador(self):
        self.reservar(acepta=True)
        hecho = self.atencion()
        reparto = DistribucionCobro.objects.get(reserva__hecho=hecho)
        self.assertIsNotNone(reparto.obligacion_financiador)
        self.assertIsNotNone(reparto.obligacion_paciente)
        for cuenta, importe in ((reparto.obligacion_financiador, "40.00"), (reparto.obligacion_paciente, "10.00")):
            registrar_movimiento(obligacion=cuenta, importe=importe, fecha=self.hoy, clave=uuid4(), usuario=self.admin)
        # El nombre coincide a propósito: la obligación sin relación no debe
        # heredar la identidad ni la prestación de otra cuenta del mismo hecho.
        legado = crear_obligacion_cobro(hecho=hecho, importe="10.00", contraparte_nombre=self.financiador.nombre, clave=uuid4())
        registrar_movimiento(obligacion=legado, importe="5.00", fecha=self.hoy, clave=uuid4(), usuario=self.admin)
        params = {"institucion": self.institucion.pk, "periodo_economico": self.hoy.replace(day=1).isoformat()}
        r = self.client.get("/api/reportes-dinero/comparativa/", params)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["actual"]["cobros_netos"], "55.00")
        grupos = {g["filtros"]["reporte_pagador"]: g for g in r.data["agrupaciones"]}
        self.assertEqual(set(grupos), {"financiador", "paciente", "sin_identificar"})
        self.assertEqual(grupos["financiador"]["filtros"]["reporte_financiador"], str(self.financiador.pk))
        self.assertEqual(grupos["paciente"]["filtros"]["reporte_financiador"], "null")
        self.assertEqual(grupos["sin_identificar"]["filtros"]["reporte_prestacion"], "null")
        for g in grupos.values():
            respuesta = self.client.get("/api/movimientos-dinero/", {"institucion": self.institucion.pk, "fecha_desde": self.hoy, "fecha_hasta": self.hoy, "estado": "aprobado", **g["filtros"]})
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(respuesta.data["count"], 1)
            self.assertEqual(respuesta.data["results"][0]["importe"], g["cobros_netos"])

    def test_resolucion_vinculada_a_distribucion_y_a_cuenta_cuenta_una_sola_vez(self):
        self.atencion()
        reparto = DistribucionCobro.objects.get()
        cuenta = reparto.obligacion_financiador
        ResolucionSaldo.objects.create(distribucion=reparto, parte="financiador", decision="financiador", importe="80.00", motivo="Fixture de autorización posterior", evidencia="Constancia", obligacion=cuenta, registrado_por=self.admin, clave=uuid4())
        registrar_movimiento(obligacion=cuenta, importe="10.00", fecha=self.hoy, clave=uuid4(), usuario=self.admin)
        r = self.client.get("/api/reportes-dinero/comparativa/", {"institucion": self.institucion.pk, "periodo_economico": self.hoy.replace(day=1).isoformat()})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["actual"]["cobros_netos"], "10.00")
        self.assertEqual(len(r.data["agrupaciones"]), 1)
