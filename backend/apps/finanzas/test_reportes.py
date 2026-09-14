from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from .models import AccesoFinanciero, AjusteGasto, ConceptoGasto, ConcesionFinanciera, Gasto
from .procesamiento import solicitar_reparto, procesar_siguiente


class ReportesFinanzasTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital reportes")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.otra = Area.objects.create(institucion=self.institucion, nombre="Diagnóstico")
        self.usuario = Usuario.objects.create_user("reportes@demo.local", "x")
        self.membresia = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        self.concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="LUZ", nombre="Electricidad")
        self.mes = timezone.localdate().replace(day=1)
        self.parametros = {"institucion": self.institucion.pk, "periodo_economico": str(self.mes)}
        self.client.force_authenticate(self.usuario)

    def gasto(self, importe="100.01", area=None, concepto=None):
        return Gasto.objects.create(
            institucion=self.institucion, area=area or self.area, concepto=concepto or self.concepto,
            importe=Decimal(importe), periodo_economico=self.mes, origen=Gasto.Origen.CENTRAL,
            registrado_por=self.usuario, estado=Gasto.Estado.APROBADO,
            aprobado_por=self.usuario, aprobado_en=timezone.now(),
        )

    def consultar(self, **filtros):
        return self.client.get("/api/reportes-finanzas/", {**self.parametros, **filtros})

    def test_totales_neto_ajustes_por_area_y_auditoria(self):
        gasto = self.gasto()
        AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-0.01"), motivo="Bonificación", registrado_por=self.usuario)
        self.gasto("20.00", self.otra)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["aprobados"], r.data["distribuido"], r.data["sin_distribuir"]), ("120.00", "0.00", "120.00"))
        self.assertEqual(len(r.data["agrupaciones"]), 2)
        self.assertEqual(self.consultar(area=self.area.pk).data["aprobados"], "100.00")
        self.assertTrue(AccesoFinanciero.objects.filter(usuario=self.usuario).exists())

    def test_marca_actualizacion_no_publica_importes_viejos_y_recupera_estado(self):
        gasto = self.gasto()
        solicitar_reparto(gasto.pk)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["actualizando"])
        self.assertIsNone(r.data["distribuido"])
        self.assertIsNone(r.data["sin_distribuir"])
        self.assertIsNone(r.data["agrupaciones"][0]["distribuido"])
        estado = self.client.get("/api/procesamiento-finanzas/", self.parametros)
        self.assertEqual(estado.data["estado"], "pendiente")
        self.assertFalse(estado.data["worker_activo"])
        procesar_siguiente()
        self.assertFalse(self.consultar().data["actualizando"])
        self.assertEqual(self.consultar().data["sin_distribuir"], "100.01")

    def test_solo_permisos_del_area_y_sensibilidad(self):
        self.gasto()
        self.gasto("40.00", self.otra)
        sensible = ConceptoGasto.objects.create(institucion=self.institucion, codigo="SUE", nombre="Remuneración", sensible=True)
        self.gasto("999.00", concepto=sensible)
        self.membresia.rol = Membresia.Rol.ADMINISTRATIVO
        self.membresia.save()
        c = ConcesionFinanciera.objects.create(membresia=self.membresia, accion=ConcesionFinanciera.Accion.VER_GASTOS)
        c.areas.add(self.area)
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["aprobados"], "100.01")
        self.assertFalse(r.data["incluye_sensibles"])
        self.assertEqual(self.consultar(area=self.otra.pk).status_code, 403)
        self.assertEqual(self.consultar(area_sin_asignar="true").status_code, 403)

    def test_consulta_sin_filtro_de_area_es_auditable_en_el_area_visible(self):
        self.gasto()
        self.gasto("40.00", self.otra)
        self.membresia.rol = Membresia.Rol.ADMINISTRATIVO
        self.membresia.save()
        for accion in (ConcesionFinanciera.Accion.VER_GASTOS, ConcesionFinanciera.Accion.AUDITAR_FINANZAS):
            permiso = ConcesionFinanciera.objects.create(membresia=self.membresia, accion=accion)
            permiso.areas.add(self.area)
        self.assertEqual(self.consultar().status_code, 200)
        self.assertEqual(self.client.get("/api/procesamiento-finanzas/", self.parametros).status_code, 200)
        auditoria = self.client.get("/api/accesos-financieros/")
        self.assertEqual(auditoria.status_code, 200, auditoria.data)
        self.assertEqual(auditoria.data["count"], 2)
        self.assertEqual({fila["area"] for fila in auditoria.data["results"]}, {self.area.pk})

    def test_no_combina_instituciones_y_no_autorizado_no_es_cero(self):
        ajena = Institucion.objects.create(nombre="Ajena")
        r = self.client.get("/api/reportes-finanzas/", {**self.parametros, "institucion": ajena.pk})
        self.assertEqual(r.status_code, 403)
        self.membresia.activo = False
        self.membresia.save()
        self.assertEqual(self.consultar().status_code, 403)

    def test_auditoria_falla_cerrada_sin_totales(self):
        self.gasto()
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("auditoria")):
            r = self.consultar()
        self.assertEqual(r.status_code, 503)
        self.assertNotIn("aprobados", r.data)

    def test_valida_mes_y_ambito_sin_descartar_filtros(self):
        self.assertEqual(self.consultar(periodo_economico="2026-09-02").status_code, 400)
        self.assertEqual(self.consultar(area=self.area.pk, area_sin_asignar="true").status_code, 400)

    def test_reporte_vacio_tiene_importes_exactos_y_alcance_explicito(self):
        r = self.consultar()
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["aprobados"], "0.00")
        self.assertEqual(r.data["agrupaciones"], [])
        self.assertIn("no equivale", r.data["alcance"])
