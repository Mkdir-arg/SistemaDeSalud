from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia
from .models import AccesoFinanciero, AjusteGasto, ConceptoGasto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto
from . import test_reportes


class EvolucionMensualTests(APITestCase):
    setUp = test_reportes.ReportesFinanzasTests.setUp
    gasto = test_reportes.ReportesFinanzasTests.gasto

    def control(self, area, desde=date(2026, 4, 1), **datos):
        return ExpectativaGasto.objects.create(institucion=self.institucion, concepto=self.concepto, area=area, vigente_desde=desde, **datos)

    def consultar(self, **datos):
        return self.client.get("/api/reportes-finanzas/evolucion/", {
            "institucion": self.institucion.pk, "periodo_economico": "2026-09-01", "meses": 6, **datos,
        })

    def cerrar(self, control, mes="2026-08-01"):
        return IndicacionCargaGasto.objects.create(expectativa=control, periodo_economico=mes, estado="carga_completa", registrado_por=self.usuario)

    def test_vigencia_historica_referencia_ajustes_y_drilldown_exacto(self):
        previo = self.control(self.area, monto_referencia="120.00")
        self.control(self.area, date(2026, 9, 1), monto_referencia="150.00", reemplaza=previo)
        self.mes = date(2026, 8, 1)
        fuente = self.gasto()
        AjusteGasto.objects.create(gasto=fuente, importe=Decimal("-0.01"), motivo="Ajuste", registrado_por=self.usuario)
        AjusteGasto.objects.create(gasto=fuente, importe=Decimal("1.01"), motivo="Otro ajuste", registrado_por=self.usuario)
        self.gasto("999.00", area=self.otra)  # Mismo concepto, pero sin control.
        self.cerrar(previo)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        agosto, septiembre = r.data["meses"][-2:]
        self.assertEqual((agosto["importe_aprobado"], agosto["monto_referencia"], agosto["estado"]), ("101.01", "120.00", "completo"))
        self.assertEqual(septiembre["monto_referencia"], "150.00")
        detalle = self.client.get("/api/gastos/", {"institucion": self.institucion.pk, "concepto": self.concepto.pk, "periodo_economico": "2026-08-01", "control_mensual": "true", "estado_operativo": "aprobado"})
        self.assertEqual(detalle.status_code, 200, detalle.data)
        self.assertEqual(detalle.data["count"], 1)
        self.assertEqual(detalle.data["results"][0]["importe_resultante"], agosto["importe_aprobado"])

    def test_sin_control_sin_carga_y_cero_confirmado_no_se_confunden(self):
        c = self.control(self.area, date(2026, 7, 1))
        self.cerrar(c)
        r = self.consultar()
        junio, julio, agosto = r.data["meses"][2:5]
        self.assertEqual((junio["estado"], junio["importe_aprobado"]), ("sin_control", None))
        self.assertEqual((julio["estado"], julio["importe_aprobado"]), ("sin_carga", "0.00"))
        self.assertEqual((agosto["estado"], agosto["importe_aprobado"], agosto["monto_referencia"]), ("completo", "0.00", None))

    def test_carga_completa_con_aprobacion_pendiente_es_provisional(self):
        c = self.control(self.area)
        self.mes = date(2026, 8, 1)
        self.gasto()
        pendiente = self.gasto("3.00")
        Gasto.objects.filter(pk=pendiente.pk).update(estado="pendiente_aprobacion")
        self.cerrar(c)
        agosto = self.consultar().data["meses"][-2]
        self.assertEqual((agosto["estado"], agosto["gastos_pendientes"], agosto["importe_aprobado"]), ("incompleto", 1, "100.01"))

    def test_mes_actual_es_abierto_aunque_se_declare_completo(self):
        c = self.control(self.area)
        self.cerrar(c, "2026-09-01")
        with patch("apps.finanzas.api_reportes.timezone.localdate", return_value=date(2026, 9, 14)):
            self.assertEqual(self.consultar().data["meses"][-1]["estado"], "mes_abierto")

    def test_area_nula_no_multiplica_gastos_y_referencia_incompleta_es_nula(self):
        self.control(self.area, monto_referencia="100.00")
        self.control(None)
        self.mes = date(2026, 8, 1)
        self.gasto("10.00")
        fuente = self.gasto("20.00")
        Gasto.objects.filter(pk=fuente.pk).update(area=None)
        r = self.consultar()
        self.assertEqual(r.data["meses"][-2]["importe_aprobado"], "30.00")
        self.assertIsNone(r.data["meses"][-2]["monto_referencia"])
        self.assertEqual(self.consultar(area_sin_asignar="true").data["meses"][-2]["importe_aprobado"], "20.00")
        detalle = self.client.get("/api/gastos/", {"control_mensual": "true", "area": "null", "periodo_economico": "2026-08-01"})
        self.assertEqual(detalle.data["count"], 1)

    def test_conceptos_y_referencias_respetan_sensibilidad_area_y_auditoria(self):
        self.control(self.area, monto_referencia="100.00")
        self.control(self.otra, monto_referencia="999.00")
        secreto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="SECRET", nombre="Concepto reservado", sensible=True)
        ExpectativaGasto.objects.create(institucion=self.institucion, concepto=secreto, area=self.area, vigente_desde=date(2026, 4, 1), monto_referencia="9999.00")
        self.membresia.rol = Membresia.Rol.ADMINISTRATIVO
        self.membresia.save()
        permiso = ConcesionFinanciera.objects.create(membresia=self.membresia, accion="ver_gastos")
        permiso.areas.add(self.area)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["conceptos"], [{"id": self.concepto.pk, "nombre": "Electricidad"}])
        self.assertEqual(r.data["meses"][-2]["monto_referencia"], "100.00")
        self.assertEqual([s["id"] for s in r.data["series"]], [self.concepto.pk])
        self.assertEqual(r.data["series"][0]["meses"], r.data["meses"])
        self.assertEqual(self.consultar(area=self.otra.pk).status_code, 403)
        self.assertEqual(self.consultar(concepto=secreto.pk).status_code, 400)
        lecturas = AccesoFinanciero.objects.filter(accion="evolucion")
        self.assertEqual(lecturas.count(), 6)
        self.assertEqual(set(lecturas.values_list("area_id", flat=True)), {self.area.pk})
        self.assertEqual(set(lecturas.values_list("periodo_economico", flat=True)), {date(2026, m, 1) for m in range(4, 10)})

    def test_rechaza_parametros_invalidos_no_autorizados_y_auditoria_caida(self):
        for cambios in ({"meses": 120}, {"meses": "x"}, {"concepto": 0}, {"periodo_economico": "2026-09-02"}, {"periodo_economico": "0001-01-01"}, {"area": self.area.pk, "area_sin_asignar": "true"}):
            self.assertEqual(self.consultar(**cambios).status_code, 400)
        self.control(self.area)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("auditoria")):
            r = self.consultar()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("meses", r.data)
        self.assertNotIn("series", r.data)
        self.membresia.activo = False
        self.membresia.save()
        self.assertEqual(self.consultar().status_code, 403)

    def test_12_meses_cruzan_el_anio_y_no_inventan_controles(self):
        r = self.consultar(meses=12)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["meses"]), 12)
        self.assertEqual(r.data["meses"][0]["periodo_economico"], "2025-10-01")
        self.assertEqual(r.data["conceptos"], [])
        self.assertIsNone(r.data["concepto"])
        self.assertEqual(r.data["series"], [])

    def test_series_separadas_exactas_y_consultas_no_crecen_por_concepto(self):
        control = self.control(self.area, monto_referencia="120.00")
        self.mes = date(2026, 8, 1)
        fuente = self.gasto()
        AjusteGasto.objects.create(gasto=fuente, importe=Decimal("-0.01"), motivo="Ajuste", registrado_por=self.usuario)
        AjusteGasto.objects.create(gasto=fuente, importe=Decimal("1.01"), motivo="Otro", registrado_por=self.usuario)
        self.cerrar(control)
        self.consultar()  # Calienta sólo metadatos del framework.
        with CaptureQueriesContext(connection) as una:
            self.assertEqual(self.consultar().status_code, 200)
        limpieza = ConceptoGasto.objects.create(institucion=self.institucion, codigo="LIMP", nombre="Limpieza")
        otro = ExpectativaGasto.objects.create(institucion=self.institucion, concepto=limpieza, area=self.area, vigente_desde=date(2026, 4, 1))
        self.gasto("20.02", concepto=limpieza)
        pendiente = self.gasto("3.00", concepto=limpieza)
        Gasto.objects.filter(pk=pendiente.pk).update(estado="pendiente_aprobacion")
        self.cerrar(otro)
        self.gasto("999.00", area=self.otra, concepto=limpieza)  # Fuera del control.
        with CaptureQueriesContext(connection) as varias:
            r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(una), len(varias))
        series = {s["id"]: s for s in r.data["series"]}
        self.assertEqual(set(series), {self.concepto.pk, limpieza.pk})
        luz, aseo = [series[pk]["meses"][-2] for pk in (self.concepto.pk, limpieza.pk)]
        self.assertEqual((luz["importe_aprobado"], luz["monto_referencia"], luz["estado"]), ("101.01", "120.00", "completo"))
        self.assertEqual((aseo["importe_aprobado"], aseo["monto_referencia"], aseo["estado"]), ("20.02", None, "incompleto"))
        self.assertEqual(self.consultar(concepto=limpieza.pk).data["meses"], series[limpieza.pk]["meses"])
