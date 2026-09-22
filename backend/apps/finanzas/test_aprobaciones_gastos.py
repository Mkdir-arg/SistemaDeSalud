"""Aprobaciones de cargas manuales: pendientes no afectan importes efectivos."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area
from .models import AjusteCosto, AjusteGasto, ConceptoGasto, ConcesionFinanciera, DefinicionComponente, EstadoAprobacion, ExpectativaGasto, Gasto, ImputacionCosto, ValorComponente
from .serializers import GastoSerializer, HechoAtencionCosteableSerializer
from .services import aprobar_gasto, decidir_ajuste, procesar_hecho_atencion, procesar_reparto_gasto, rechazar_gasto, registrar_ajuste_costo, registrar_ajuste_gasto, registrar_gasto
from .test_cobros import CobrosSetup


class AprobacionesGastosTests(CobrosSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="LUZ", nombre="Electricidad")
        self.mes = timezone.localdate().replace(day=1)
        self.client.force_authenticate(self.admin)

    def gasto(self, usuario=None, **datos):
        return registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), self.mes, usuario or self.admin, **datos)

    def imputacion(self):
        componente = DefinicionComponente.objects.create(prestacion=self.prestacion, codigo="BASE", nombre="Costo base")
        ValorComponente.objects.create(componente=componente, importe=Decimal("100"), vigente_desde=timezone.now() - timedelta(days=1))
        hecho = self.atencion()
        procesar_hecho_atencion(hecho.pk)
        return ImputacionCosto.objects.get(hecho=hecho)

    def test_registrador_sin_permiso_de_aprobacion_crea_pendiente(self):
        """Quien registra sin facultad de aprobar deja el gasto pendiente.

        El origen es de área y ya no central: `origen` se marca central cuando la
        concesión cuelga de una membresía con rol admin, y ese rol hereda hoy
        `aprobar_gastos`, así que «central y pendiente» dejó de ser alcanzable.
        El origen central se cubre en `tests.ConceptoGastoApiTests`.
        """
        self.conceder("registrar_gastos")
        gasto = self.gasto(self.usuario)
        self.assertEqual(gasto.origen, Gasto.Origen.AREA)
        self.assertEqual(gasto.estado, EstadoAprobacion.PENDIENTE)
        self.assertIsNone(gasto.aprobado_por)
        self.assertIsNone(gasto.aprobado_en)
        with self.assertRaises(PermissionDenied):
            self.gasto(self.usuario, aprobado=True)

    def test_aprobacion_por_permiso_del_area_no_por_rol(self):
        registro = self.conceder("registrar_gastos", area=self.area)
        self.conceder("aprobar_gastos", area=self.area)
        Membresia.objects.filter(pk=registro.membresia_id).update(rol=Membresia.Rol.ADMINISTRATIVO)
        gasto = self.gasto(self.usuario)
        self.assertEqual(gasto.origen, Gasto.Origen.AREA)
        self.assertTrue(gasto.aprobado)
        self.assertEqual(gasto.aprobado_por_id, self.usuario.pk)

    def test_permiso_aprobacion_otra_area_no_aprueba(self):
        self.conceder("registrar_gastos", area=self.area)
        otra = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        self.conceder("aprobar_gastos", area=otra)
        self.assertFalse(self.gasto(self.usuario).aprobado)
        with self.assertRaises(PermissionDenied):
            self.gasto(self.usuario, aprobado=True)

    def test_desmarcar_aprobado_deja_gasto_pendiente_incluso_superusuario(self):
        gasto = self.gasto(aprobado=False)
        self.assertFalse(gasto.aprobado)
        aprobado = aprobar_gasto(gasto.pk, self.admin)
        self.assertTrue(aprobado.aprobado)
        self.assertEqual(aprobar_gasto(gasto.pk, self.admin).aprobado_en, aprobado.aprobado_en)

    def test_central_pendiente_puede_rechazarse_sin_perder_importe(self):
        gasto = rechazar_gasto(self.gasto(aprobado=False).pk, "Comprobante incorrecto", self.admin)
        self.assertEqual(gasto.estado, EstadoAprobacion.RECHAZADO)
        self.assertEqual(gasto.importe, Decimal("100"))
        self.assertIsNone(gasto.aprobado_en)

    def test_ajuste_gasto_pendiente_no_cambia_total_huella_o_cola(self):
        gasto = self.gasto()
        reparto = procesar_reparto_gasto(gasto.pk)
        with patch("apps.finanzas.services.solicitar_reparto") as solicitar:
            ajuste = registrar_ajuste_gasto(gasto.pk, Decimal("-40"), "Revisión", self.admin, aprobado=False)
        solicitar.assert_not_called()
        self.assertEqual(GastoSerializer(gasto).data["importe_resultante"], "100.00")
        self.assertEqual(GastoSerializer(gasto).data["ajustes"][0]["estado"], EstadoAprobacion.PENDIENTE)
        self.assertEqual(procesar_reparto_gasto(gasto.pk).pk, reparto.pk)
        with patch("apps.finanzas.services.solicitar_reparto") as solicitar:
            decidido = decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=self.admin, aprobar=True)
            repetido = decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=self.admin, aprobar=True)
        solicitar.assert_called_once_with(gasto.pk)
        self.assertEqual(decidido.aprobado_en, repetido.aprobado_en)
        self.assertEqual(GastoSerializer(gasto).data["importe_resultante"], "60.00")
        nuevo = procesar_reparto_gasto(gasto.pk)
        self.assertNotEqual(nuevo.pk, reparto.pk)
        self.assertEqual(nuevo.importe_ajustes_centavos, -4000)

    def test_ajuste_rechazado_no_aplica_y_decision_no_se_sobrescribe(self):
        gasto = self.gasto()
        ajuste = registrar_ajuste_gasto(gasto.pk, Decimal("-40"), "Revisión", self.admin, aprobado=False)
        with patch("apps.finanzas.services.solicitar_reparto") as solicitar:
            rechazado = decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=self.admin, aprobar=False, motivo="No corresponde")
        solicitar.assert_not_called()
        self.assertEqual(decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=self.admin, aprobar=False, motivo="No corresponde").rechazado_en, rechazado.rechazado_en)
        for datos in ({"aprobar": True}, {"aprobar": False, "motivo": "Otro motivo"}):
            with self.assertRaises(ValidationError):
                decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=self.admin, **datos)
        self.assertEqual(GastoSerializer(gasto).data["importe_resultante"], "100.00")
        rechazado.importe = Decimal("-99")
        with self.assertRaises(ValidationError):
            rechazado.save()

    def test_ajustes_historicos_creados_sin_nuevo_estado_siguen_aprobados(self):
        gasto = self.gasto()
        ajuste = AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-10"), motivo="Histórico")
        self.assertTrue(ajuste.aprobado)
        self.assertEqual(GastoSerializer(gasto).data["importe_resultante"], "90.00")

    def test_ajuste_costo_pendiente_no_aplica_hasta_decision(self):
        imputacion = self.imputacion()
        ajuste = registrar_ajuste_costo(imputacion, Decimal("-25"), "Revisión", self.admin, aprobado=False)
        self.assertEqual(Decimal(HechoAtencionCosteableSerializer(imputacion.hecho).data["total_conocido"]), Decimal("100"))
        detalle = HechoAtencionCosteableSerializer(imputacion.hecho).data["imputaciones"][0]["ajustes"][0]
        self.assertEqual(detalle["area"], self.area.pk)
        self.assertFalse(detalle["sensible"])
        self.assertEqual(detalle["registrado_por"], self.admin.pk)
        decidir_ajuste(ajuste.pk, modelo=AjusteCosto, usuario=self.admin, aprobar=True)
        self.assertEqual(Decimal(HechoAtencionCosteableSerializer(imputacion.hecho).data["total_conocido"]), Decimal("75"))
        self.assertEqual(ImputacionCosto.objects.get(pk=imputacion.pk).importe, Decimal("100"))

    def test_corregir_costos_no_concede_aprobar_costos(self):
        imputacion = self.imputacion()
        self.conceder("corregir_costos", sensible=True, area=self.area)
        ajuste = registrar_ajuste_costo(imputacion, Decimal("10"), "Revisión", self.usuario)
        self.assertFalse(ajuste.aprobado)
        with self.assertRaises(PermissionDenied):
            registrar_ajuste_costo(imputacion, Decimal("10"), "Revisión", self.usuario, aprobado=True)
        with self.assertRaises(PermissionDenied):
            decidir_ajuste(ajuste.pk, modelo=AjusteCosto, usuario=self.usuario, aprobar=True)

    def test_api_gasto_y_ajuste_respetan_checkbox_y_exponen_estado(self):
        respuesta = self.client.post("/api/gastos/", {"concepto": self.concepto.pk, "institucion": self.institucion.pk, "area": self.area.pk, "importe": "100", "periodo_economico": str(self.mes), "aprobado": False}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertFalse(respuesta.data["aprobado"])
        self.assertIsNone(respuesta.data["aprobado_por"])
        gasto = self.gasto()
        respuesta = self.client.post("/api/ajustes-gasto/", {"gasto": gasto.pk, "importe": "-20", "motivo": "Revisión", "aprobado": False}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["estado"], EstadoAprobacion.PENDIENTE)
        url = f"/api/ajustes-gasto/{respuesta.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        decision = self.client.post(url + "aprobar/", {}, format="json")
        self.assertEqual(decision.status_code, 200, decision.data)
        self.assertTrue(decision.data["aprobado"])
        self.assertEqual(self.client.patch(url, {"importe": "1"}).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_api_costo_rechazo_y_auditoria_lectura_cerrada(self):
        imputacion = self.imputacion()
        respuesta = self.client.post("/api/ajustes-costo/", {"imputacion": imputacion.pk, "importe": "-20", "motivo": "Revisión", "aprobado": False}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        url = f"/api/ajustes-costo/{respuesta.data['id']}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        respuesta = self.client.post(url + "rechazar/", {"motivo": "No corresponde"}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], EstadoAprobacion.RECHAZADO)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("Fallo")):
            self.assertEqual(self.client.get(url).status_code, 503)

    def test_pendiente_no_modifica_listado_ni_reporte(self):
        gasto = self.gasto()
        registrar_ajuste_gasto(gasto.pk, Decimal("-50"), "Revisión", self.admin, aprobado=False)
        listado = self.client.get("/api/gastos/", {"id": gasto.pk})
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado.data["results"][0]["importe_resultante"], "100.00")
        reporte = self.client.get("/api/reportes-finanzas/", {"institucion": self.institucion.pk, "periodo_economico": str(self.mes)})
        self.assertEqual(reporte.status_code, 200, reporte.data)
        self.assertEqual(reporte.data["aprobados"], "100.00")
        ExpectativaGasto.objects.create(concepto=self.concepto, institucion=self.institucion, area=self.area, vigente_desde=self.mes)
        calendario = self.client.get("/api/expectativas-gasto/calendario/", {"institucion": self.institucion.pk, "periodo_economico": str(self.mes)})
        self.assertEqual(calendario.status_code, 200, calendario.data)
        filas = calendario.data["results"] if isinstance(calendario.data, dict) else calendario.data
        self.assertEqual(filas[0]["importe_aprobado"], "100.00")
