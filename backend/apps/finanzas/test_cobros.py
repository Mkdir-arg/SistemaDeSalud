"""Contrato cobros: regla explícita, origen durable, sin inventar deuda clínica."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .cobros import capturar_cobros_atencion, registrar_politica_cobro, resolver_pendiente_cobro, recuperar_cobros_atencion
from .models import AccesoFinanciero, ConcesionFinanciera, Gasto, HechoAtencionCosteable, ImputacionCosto, ObligacionFinanciera, Prestacion
from .models_cobros import PendienteCobro, PoliticaCobro, SnapshotCobroAtencion
from .services import registrar_atencion_completada


class CobrosSetup:
    def setUp(self):
        self.admin = Usuario.objects.create_superuser("cobros@hospital.local", "x")
        self.usuario = Usuario.objects.create_user("operador@hospital.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        self.paciente = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Paz")
        self.caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=self.paciente, area_actual=self.area)
        self.prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")

    def politica(self, **datos):
        valores = dict(cobrar=True, importe=Decimal("100.00"), contraparte_nombre="Responsable explícito")
        valores.update(datos)
        return registrar_politica_cobro(prestacion=self.prestacion, registrado_por=self.admin, **valores)

    def atencion(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        return registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)

    def conceder(self, accion, sensible=False, area=None):
        membresia, _ = Membresia.objects.get_or_create(usuario=self.usuario, institucion=self.institucion, defaults={"rol": Membresia.Rol.ADMIN_INSTITUCION})
        concesion = ConcesionFinanciera.objects.create(membresia=membresia, accion=accion, todas_las_areas=area is None, permite_sensibles=sensible)
        if area:
            concesion.areas.add(area)
        return concesion


class CobrosAtencionTests(CobrosSetup, TestCase):
    def test_sin_politica_no_crea_deuda_ni_pendiente(self):
        hecho = self.atencion()
        self.assertTrue(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.assertFalse(PendienteCobro.objects.exists())

    def test_arancel_sin_decision_cobrar_no_genera_cargo(self):
        self.politica(cobrar=False)
        self.atencion()
        self.assertFalse(PendienteCobro.objects.exists())

    def test_regla_completa_genera_un_cargo_y_no_infiere_pagador(self):
        self.politica()
        hecho = self.atencion()
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertIsNotNone(pendiente.obligacion_id)
        self.assertEqual(pendiente.obligacion.contraparte_nombre, "Responsable explícito")
        self.assertEqual(pendiente.obligacion.importe_original, Decimal("100.00"))
        self.assertEqual(pendiente.obligacion.hecho_id, hecho.pk)
        capturar_cobros_atencion(hecho.pk)
        self.assertEqual(PendienteCobro.objects.filter(hecho=hecho).count(), 1)

    def test_faltantes_administrativos_se_completan_sin_tocar_costo(self):
        self.politica(importe=None, contraparte_nombre="")
        hecho = self.atencion()
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertIsNone(pendiente.obligacion_id)
        resuelto = resolver_pendiente_cobro(pendiente.pk, usuario=self.admin, importe=Decimal("70"), contraparte_nombre="Tercero autorizado")
        self.assertEqual(resuelto.obligacion.importe_original, Decimal("70"))
        repetido = resolver_pendiente_cobro(pendiente.pk, usuario=self.admin, importe=Decimal("70"), contraparte_nombre="Tercero autorizado")
        self.assertEqual(repetido.obligacion_id, resuelto.obligacion_id)
        with self.assertRaises(ValidationError):
            resolver_pendiente_cobro(pendiente.pk, usuario=self.admin, importe=Decimal("90"))

    def test_atencion_sin_paciente_conserva_origen_y_responsable_explicito(self):
        self.caso.ciudadano = None
        self.caso.save(update_fields=["ciudadano"])
        self.politica()
        hecho = self.atencion()
        obligacion = PendienteCobro.objects.get(hecho=hecho).obligacion
        self.assertIsNotNone(obligacion)
        self.assertIsNone(hecho.ciudadano_origen_id)
        self.assertEqual(obligacion.hecho_id, hecho.pk)
        self.assertEqual(obligacion.contraparte_nombre, "Responsable explícito")

    def test_version_nueva_no_modifica_cargo_ni_pendientes_anteriores(self):
        self.politica(contraparte_nombre="")
        hecho = self.atencion()
        self.politica(importe=Decimal("250"), contraparte_nombre="Otro")
        capturar_cobros_atencion(hecho.pk)
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertEqual(pendiente.importe, Decimal("100"))
        self.assertEqual(pendiente.contraparte_nombre, "")
        self.assertIsNone(pendiente.obligacion_id)

    def test_suspender_cobro_solo_afecta_futuras_atenciones(self):
        self.politica()
        primero = self.atencion()
        self.politica(cobrar=False)
        segundo = self.atencion()
        self.assertTrue(PendienteCobro.objects.filter(hecho=primero).exists())
        self.assertFalse(PendienteCobro.objects.filter(hecho=segundo).exists())

    def test_fallo_cobro_no_revierte_atencion_y_recupera_regla_original(self):
        original = self.politica()
        with patch("apps.finanzas.cobros._crear_cargo", side_effect=RuntimeError("fallo")):
            hecho = self.atencion()
        self.assertTrue(HechoAtencionCosteable.objects.filter(pk=hecho.pk).exists())
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.politica(importe=Decimal("250"))
        recuperar_cobros_atencion(hecho.pk, usuario=self.admin)
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertEqual(pendiente.politica_id, original.pk)
        self.assertEqual(pendiente.obligacion.importe_original, Decimal("100"))

    def test_recuperar_sin_ancla_no_aplica_politica_creada_despues_de_atencion(self):
        hecho = self.atencion()
        SnapshotCobroAtencion.objects.filter(hecho=hecho).delete()
        self.politica()
        snapshot = recuperar_cobros_atencion(hecho.pk, usuario=self.admin)
        self.assertTrue(snapshot.capturado)
        self.assertFalse(PendienteCobro.objects.exists())

    def test_politica_retroactiva_y_edicion_historica_rechazadas(self):
        with self.assertRaises(ValidationError):
            self.politica(vigente_desde=timezone.now() - timedelta(days=1))
        politica = self.politica()
        politica.importe = Decimal("200")
        with self.assertRaises(ValidationError):
            politica.save()

    def test_una_version_futura_no_se_aplica_hoy(self):
        self.politica(vigente_desde=timezone.now() + timedelta(days=1))
        self.atencion()
        self.assertFalse(PendienteCobro.objects.exists())

    def test_mover_prestacion_no_resucita_regla_del_nodo_anterior(self):
        self.politica()
        otro_nodo = Nodo.objects.create(version=self.nodo.version, tipo=Nodo.Tipo.ATENCION, titulo="Otra consulta")
        self.prestacion.nodo = otro_nodo
        self.prestacion.save()
        self.politica()
        self.atencion()
        self.assertFalse(PendienteCobro.objects.exists())

    def test_resolver_exige_permiso_explicito_incluso_admin_institucion(self):
        self.politica(contraparte_nombre="")
        pendiente = PendienteCobro.objects.get(hecho=self.atencion())
        with self.assertRaises(PermissionDenied):
            resolver_pendiente_cobro(pendiente.pk, usuario=self.usuario, contraparte_nombre="Tercero")
        self.conceder("registrar_dinero", area=self.area)
        self.assertIsNotNone(resolver_pendiente_cobro(pendiente.pk, usuario=self.usuario, contraparte_nombre="Tercero").obligacion_id)

    def test_configuracion_por_area_no_alcanza_politica_institucional(self):
        self.conceder("configurar_cobros", area=self.area)
        with self.assertRaises(PermissionDenied):
            registrar_politica_cobro(prestacion=self.prestacion, registrado_por=self.usuario, cobrar=True)


class CobrosApiTests(CobrosSetup, APITestCase):
    def test_pendientes_busqueda_y_orden_antes_de_paginar(self):
        self.client.force_authenticate(self.admin)
        self.politica(importe=None)
        primero, segundo = self.atencion(), self.atencion()
        respuesta = self.client.get("/api/pendientes-cobro/", {
            "search": "Consulta", "ordering": "-hecho_id", "page_size": 1,
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 2)
        self.assertEqual(len(respuesta.data["results"]), 1)
        self.assertEqual(respuesta.data["results"][0]["hecho"], segundo.pk)
        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(self.client.get("/api/pendientes-cobro/", {"search": "ausente"}).data["count"], 0)

    def test_circuito_api_politica_atencion_cobros_reintegro_y_reporte_sin_duplicar(self):
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post("/api/politicas-cobro/", {
            "prestacion": self.prestacion.pk, "cobrar": True,
            "importe": "100.00", "contraparte_nombre": "Responsable administrativo",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        hecho = self.atencion()
        obligacion = PendienteCobro.objects.get(hecho=hecho).obligacion
        url = f"/api/obligaciones-financieras/{obligacion.pk}/"
        self.assertEqual(self.client.get(url).data["pendiente"], "100.00")
        fecha = timezone.localdate().isoformat()
        for importe, pendiente in (("40.00", "60.00"), ("60.00", "0.00")):
            respuesta = self.client.post(url + "movimientos/", {
                "importe": importe, "fecha": fecha, "clave": str(uuid4()),
            }, format="json")
            self.assertEqual(respuesta.status_code, 201, respuesta.data)
            self.assertEqual(respuesta.data["pendiente"], pendiente)
        original = next(m for m in respuesta.data["movimientos"] if m["importe"] == "40.00")
        datos = {"importe": "30.00", "fecha": fecha, "motivo": "Reducción acordada", "efecto": "reducir"}
        movimiento_url = f"/api/movimientos-dinero/{original['id']}/"
        preview = self.client.post(movimiento_url + "previsualizar-reintegro/", datos, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["pendiente_resultante"], "0.00")
        respuesta = self.client.post(movimiento_url + "reintegrar/", {
            **datos, "clave": str(uuid4()), "version_esperada": preview.data["version_esperada"],
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["obligacion_actual"], "70.00")
        self.assertEqual(respuesta.data["registrado_neto"], "70.00")
        self.assertEqual(respuesta.data["pendiente"], "0.00")
        reporte = self.client.get("/api/reportes-dinero/", {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "fecha_desde": fecha, "fecha_hasta": fecha,
        })
        self.assertEqual(reporte.status_code, 200, reporte.data)
        self.assertEqual(reporte.data["cobros_brutos"], "100.00")
        self.assertEqual(reporte.data["reintegros_cobros"], "30.00")
        self.assertEqual(reporte.data["cobros_netos"], "70.00")
        self.assertEqual(reporte.data["cantidad_movimientos"], 3)
        self.assertEqual(Gasto.objects.count(), 0)
        self.assertEqual(ImputacionCosto.objects.count(), 0)
        self.assertEqual(PendienteCobro.objects.filter(hecho=hecho).count(), 1)

    def test_lectura_no_expone_paciente_y_audita(self):
        self.politica(contraparte_nombre="")
        self.atencion()
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.get("/api/pendientes-cobro/")
        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.data.get("results", []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual(len(filas), 1)
        self.assertNotIn("ciudadano", filas[0])
        self.assertNotIn("paciente", filas[0])
        self.assertNotIn("Ana", str(filas[0]))
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            self.assertEqual(self.client.get("/api/pendientes-cobro/").status_code, 503)

    def test_sensible_no_visible_y_resolver_fuera_alcance_404(self):
        self.politica(sensible=True, contraparte_nombre="")
        pendiente = PendienteCobro.objects.get(hecho=self.atencion())
        self.conceder("ver_dinero", area=self.area)
        self.conceder("registrar_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.get("/api/pendientes-cobro/")
        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.data.get("results", []) if isinstance(respuesta.data, dict) else respuesta.data
        self.assertEqual(filas, [])
        respuesta = self.client.post(f"/api/pendientes-cobro/{pendiente.pk}/resolver/", {"contraparte_nombre": "Tercero"})
        self.assertEqual(respuesta.status_code, 404)

    def test_configuracion_no_concede_costos_ni_grants(self):
        self.conceder("configurar_cobros")
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post("/api/politicas-cobro/", {"prestacion": self.prestacion.pk, "cobrar": True, "importe": "100", "contraparte_nombre": "Tercero"})
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(self.client.get("/api/politicas-cobro/").status_code, 200)
        self.assertEqual(ConcesionFinanciera.objects.filter(membresia__usuario=self.usuario).count(), 1)

    def test_resolver_por_api_no_revela_fila_a_permiso_solo_escritura(self):
        self.politica(contraparte_nombre="")
        pendiente = PendienteCobro.objects.get(hecho=self.atencion())
        self.conceder("registrar_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post(f"/api/pendientes-cobro/{pendiente.pk}/resolver/", {"contraparte_nombre": "Tercero"})
        self.assertEqual(respuesta.status_code, 404)
        pendiente.refresh_from_db()
        self.assertIsNone(pendiente.obligacion_id)


class CorreccionesCobrosApiTests(CobrosSetup, APITestCase):
    def test_fallo_inicial_de_captura_es_visible_y_recuperable_sin_duplicar(self):
        original = self.politica()
        with patch("apps.finanzas.models_cobros.SnapshotCobroAtencion.objects.get_or_create", side_effect=RuntimeError("captura no disponible")):
            hecho = self.atencion()
        self.assertTrue(HechoAtencionCosteable.objects.filter(pk=hecho.pk).exists())
        self.assertTrue(EventoCaso.objects.filter(pk=hecho.evento_origen_id).exists())
        self.assertFalse(SnapshotCobroAtencion.objects.filter(hecho=hecho).exists())
        self.politica(importe=Decimal("250"))
        self.client.force_authenticate(self.admin)
        listado = self.client.get("/api/pendientes-cobro/recuperables/", {"institucion": self.institucion.pk, "area": self.area.pk})
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual([fila["hecho"] for fila in listado.data["results"]], [hecho.pk])
        url = "/api/pendientes-cobro/recuperar/"
        for _ in range(2):
            respuesta = self.client.post(url, {"hecho": hecho.pk}, format="json")
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertTrue(respuesta.data["capturado"])
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertEqual(pendiente.politica_id, original.pk)
        self.assertEqual(pendiente.obligacion.importe_original, Decimal("100"))
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)
        self.assertEqual(self.client.get("/api/pendientes-cobro/recuperables/").data["count"], 0)

    def test_recuperacion_sin_ancla_revierte_si_falla_auditoria(self):
        self.politica()
        with patch("apps.finanzas.models_cobros.SnapshotCobroAtencion.objects.get_or_create", side_effect=RuntimeError("captura no disponible")):
            hecho = self.atencion()
        self.client.force_authenticate(self.admin)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("auditoría no disponible")):
            self.assertEqual(self.client.get("/api/pendientes-cobro/recuperables/").status_code, 503)
            respuesta = self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertFalse(SnapshotCobroAtencion.objects.filter(hecho=hecho).exists())
        self.assertFalse(PendienteCobro.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertEqual(self.client.get("/api/pendientes-cobro/recuperables/").data["count"], 1)
        self.assertEqual(self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json").status_code, 200)

    def test_recuperacion_sin_ancla_respeta_institucion_area_y_sensibilidad(self):
        self.politica()
        with patch("apps.finanzas.models_cobros.SnapshotCobroAtencion.objects.get_or_create", side_effect=RuntimeError("captura no disponible")):
            hecho = self.atencion()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        otra_institucion = Institucion.objects.create(nombre="Otro hospital")
        membresia, _ = Membresia.objects.get_or_create(usuario=self.usuario, institucion=self.institucion, defaults={"rol": Membresia.Rol.ADMIN_INSTITUCION})
        externa = Membresia.objects.create(usuario=self.usuario, institucion=otra_institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        self.client.force_authenticate(self.usuario)
        for nombre, origen, area, sensible, lectura in (
            ("sin sensibles", membresia, self.area, False, True),
            ("otra área", membresia, otra_area, True, True),
            ("otra institución", externa, None, True, True),
            ("sólo escritura", membresia, self.area, True, False),
        ):
            with self.subTest(alcance=nombre):
                ConcesionFinanciera.objects.filter(membresia__usuario=self.usuario).delete()
                for accion in (["ver_dinero", "registrar_dinero"] if lectura else ["registrar_dinero"]):
                    concesion = ConcesionFinanciera.objects.create(membresia=origen, accion=accion, todas_las_areas=area is None, permite_sensibles=sensible)
                    if area:
                        concesion.areas.add(area)
                listado = self.client.get("/api/pendientes-cobro/recuperables/", {"institucion": self.institucion.pk})
                if lectura:
                    self.assertEqual(listado.status_code, 200, listado.data)
                    self.assertEqual(listado.data["count"], 0)
                else:
                    self.assertEqual(listado.status_code, 403)
                respuesta = self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json")
                self.assertEqual(respuesta.status_code, 404, respuesta.data)
                self.assertFalse(SnapshotCobroAtencion.objects.filter(hecho=hecho).exists())
        ConcesionFinanciera.objects.filter(membresia__usuario=self.usuario).delete()
        self.conceder("ver_dinero", sensible=True, area=self.area)
        self.conceder("registrar_dinero", sensible=True, area=self.area)
        # El alcance sigue al área original aunque ya no esté la FK mutable.
        HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(area=None)
        listado = self.client.get("/api/pendientes-cobro/recuperables/", {"area": self.area.pk})
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado.data["count"], 1)
        self.assertEqual(listado.data["results"][0]["area"], self.area.pk)
        self.assertEqual(self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json").status_code, 200)

    def test_suspende_prestacion_inactiva_sin_reescribir_cargo_anterior(self):
        politica = self.politica()
        anterior = PendienteCobro.objects.get(hecho=self.atencion())
        self.prestacion.activo = False
        self.prestacion.save(update_fields=["activo"])
        self.conceder("configurar_cobros")
        self.client.force_authenticate(self.usuario)
        respuesta = self.client.post("/api/politicas-cobro/", {"prestacion": self.prestacion.pk, "cobrar": False}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertFalse(PendienteCobro.objects.filter(hecho=self.atencion()).exists())
        anterior.refresh_from_db()
        self.assertEqual(anterior.politica_id, politica.pk)
        self.assertEqual(anterior.obligacion.importe_original, Decimal("100"))
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)
        self.prestacion.refresh_from_db()
        self.assertFalse(self.prestacion.activo)
        self.assertEqual(self.client.post("/api/politicas-cobro/", {"prestacion": self.prestacion.pk, "cobrar": True}, format="json").status_code, 400)

    def test_desactivar_catalogo_no_modifica_captura_historica(self):
        politica = self.politica()
        with patch("apps.finanzas.cobros._crear_cargo", side_effect=RuntimeError("fallo")):
            hecho = self.atencion()
        self.prestacion.activo = False
        self.prestacion.save(update_fields=["activo"])
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post("/api/politicas-cobro/", {"prestacion": self.prestacion.pk, "cobrar": False}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        recuperar_cobros_atencion(hecho.pk, usuario=self.admin)
        pendiente = PendienteCobro.objects.get(hecho=hecho)
        self.assertEqual(pendiente.politica_id, politica.pk)
        self.assertEqual(pendiente.obligacion.importe_original, Decimal("100"))

    def test_alta_politica_audita_y_error_revierte_version(self):
        self.client.force_authenticate(self.admin)
        datos = {"prestacion": self.prestacion.pk, "cobrar": True, "importe": "100", "contraparte_nombre": "Tercero"}
        respuesta = self.client.post("/api/politicas-cobro/", datos, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(AccesoFinanciero.objects.filter(recurso="politicacobro", accion="create", objeto_id=respuesta.data["id"], institucion=self.institucion, area__isnull=True).exists())
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post("/api/politicas-cobro/", {**datos, "importe": "200"}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertEqual(PoliticaCobro.objects.count(), 1)

    def test_resolver_audita_y_error_revierte_datos_y_cargo(self):
        self.politica(contraparte_nombre="")
        pendiente = PendienteCobro.objects.get(hecho=self.atencion())
        self.client.force_authenticate(self.admin)
        url = f"/api/pendientes-cobro/{pendiente.pk}/resolver/"
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post(url, {"contraparte_nombre": "Tercero"}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.contraparte_nombre, "")
        self.assertIsNone(pendiente.obligacion_id)
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertEqual(self.client.post(url, {"contraparte_nombre": "Tercero"}, format="json").status_code, 200)
        self.assertTrue(AccesoFinanciero.objects.filter(recurso="pendientecobro", accion="resolver", objeto_id=pendiente.pk, institucion=self.institucion, area=self.area).exists())

    def test_recuperacion_auditada_y_error_no_oculta_cargo_creado(self):
        self.politica()
        with patch("apps.finanzas.cobros._crear_cargo", side_effect=RuntimeError("fallo")):
            hecho = self.atencion()
        self.client.force_authenticate(self.admin)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.assertEqual(self.client.post("/api/pendientes-cobro/recuperar/", {"hecho": hecho.pk}, format="json").status_code, 200)
        self.assertTrue(AccesoFinanciero.objects.filter(accion="recuperar", institucion=self.institucion, area=self.area, sensible=True).exists())


@skipUnless(connection.vendor == "postgresql", "Los bloqueos se validan en PostgreSQL.")
class CobrosConcurrenciaTests(CobrosSetup, TransactionTestCase):
    def _paralelo(self, ejecutar):
        barrera = Barrier(2)

        def operacion():
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return ejecutar()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(operacion) for _ in range(2)]
            return [futuro.result(timeout=20) for futuro in futuros]

    def test_resolucion_simultanea_crea_un_solo_cargo(self):
        self.politica(contraparte_nombre="")
        pendiente = PendienteCobro.objects.get(hecho=self.atencion())
        ids = self._paralelo(lambda: resolver_pendiente_cobro(pendiente.pk, usuario=self.admin, contraparte_nombre="Tercero").obligacion_id)
        self.assertEqual(ids[0], ids[1])

    def test_recuperacion_simultanea_conserva_unica_captura(self):
        self.politica()
        with patch("apps.finanzas.cobros._crear_cargo", side_effect=RuntimeError("fallo")):
            hecho = self.atencion()
        self._paralelo(lambda: recuperar_cobros_atencion(hecho.pk, usuario=self.admin).pk)
        self.assertEqual(PendienteCobro.objects.filter(hecho=hecho).count(), 1)
        self.assertIsNotNone(PendienteCobro.objects.get(hecho=hecho).obligacion_id)

    def test_recuperacion_simultanea_sin_ancla_crea_un_solo_cargo(self):
        self.politica()
        with patch("apps.finanzas.models_cobros.SnapshotCobroAtencion.objects.get_or_create", side_effect=RuntimeError("captura no disponible")):
            hecho = self.atencion()
        ids = self._paralelo(lambda: recuperar_cobros_atencion(hecho.pk, usuario=self.admin).pk)
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PendienteCobro.objects.filter(hecho=hecho).count(), 1)
        self.assertEqual(ObligacionFinanciera.objects.filter(hecho=hecho).count(), 1)
