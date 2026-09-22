"""Dinero vinculado: casos de aceptación e invariantes de integridad."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from .dinero import (EstadoDineroCambio, crear_obligacion_cobro, crear_obligacion_pago,
                     disponible_reduccion, estado_obligacion, previsualizar_reintegro,
                     reducir_obligacion, registrar_movimiento, reintegrar_movimiento)
from .models import (AccesoFinanciero, AjusteGasto, AjusteObligacion, ConceptoGasto,
                     ConcesionFinanciera, Gasto, HechoAtencionCosteable,
                     MovimientoDinero, ObligacionFinanciera)
from .services import registrar_gasto


class DatosDinero:
    def preparar(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Dinero")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.usuario = Usuario.objects.create_superuser("dinero@test.local", "x")
        self.concepto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="SERVICIO", nombre="Servicio")
        self.gasto = registrar_gasto(concepto=self.concepto, institucion=self.institucion, area=self.area, importe="100.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario)
        self.obligacion = crear_obligacion_pago(gasto=self.gasto, contraparte_nombre="Proveedor", clave=uuid4(), usuario=self.usuario)
        self.fecha = date(2026, 9, 1)

    def movimiento(self, importe="100.00", **kwargs):
        return registrar_movimiento(obligacion=self.obligacion, importe=importe, fecha=self.fecha, clave=uuid4(), usuario=self.usuario, **kwargs)

    def devolver(self, original, importe="30.00", efecto="mantener", **kwargs):
        datos = dict(original=original, importe=importe, fecha=self.fecha, motivo="Devolución acordada", efecto=efecto, usuario=self.usuario, **kwargs)
        plan = previsualizar_reintegro(**datos)
        return reintegrar_movimiento(**datos, clave=uuid4(), version_esperada=plan["version_esperada"])


class DineroTests(DatosDinero, APITestCase):
    def setUp(self):
        self.preparar()
        self.client.force_authenticate(self.usuario)

    def test_tablas_ordenan_y_buscan_antes_de_paginar(self):
        menor = self.movimiento("9.99", referencia="Transferencia menor")
        mayor = self.movimiento("20.01", referencia="Transferencia mayor")
        respuesta = self.client.get("/api/movimientos-dinero/", {
            "search": "Transferencia", "ordering": "-importe", "page_size": 1,
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 2)
        self.assertEqual(len(respuesta.data["results"]), 1)
        self.assertEqual(respuesta.data["results"][0]["id"], mayor.pk)
        respuesta = self.client.get("/api/movimientos-dinero/", {"search": "menor"})
        self.assertEqual([r["id"] for r in respuesta.data["results"]], [menor.pk])
        for busqueda, cantidad in (("Proveedor", 1), ("Ausente", 0)):
            respuesta = self.client.get("/api/obligaciones-financieras/", {
                "search": busqueda, "ordering": "contraparte_nombre",
            })
            self.assertEqual(respuesta.data["count"], cantidad)

    def test_pago_parcial_limite_y_no_duplica_el_gasto(self):
        self.movimiento("30")
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], Decimal("70"))
        with self.assertRaises(ValidationError):
            self.movimiento("70.01")
        self.assertEqual(Gasto.objects.count(), 1)
        self.assertEqual(AjusteGasto.objects.count(), 0)

    def test_cobro_parcial_mas_completo_sin_copiar_costo(self):
        hecho = HechoAtencionCosteable.objects.create(institucion=self.institucion, area=self.area, area_origen_id=self.area.pk, evento_origen_id=999, caso_origen_id=999, ciudadano_origen_id=999, nodo_origen_id=999, ocurrida_en=timezone.now())
        self.obligacion = crear_obligacion_cobro(hecho=hecho, importe="100", contraparte_nombre="Financiador, no paciente", clave=uuid4())
        self.movimiento("40")
        self.movimiento("60")
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], 0)
        self.assertEqual(set(self.obligacion.movimientos.values_list("tipo", flat=True)), {"cobro"})

    def test_reintento_idempotente_y_payload_distinto_rechazado(self):
        datos = dict(obligacion=self.obligacion, importe="30", fecha=self.fecha, clave=uuid4(), usuario=self.usuario)
        primero = registrar_movimiento(**datos)
        self.assertEqual(registrar_movimiento(**datos).pk, primero.pk)
        with self.assertRaises(ValidationError):
            registrar_movimiento(**{**datos, "importe": "31"})
        self.movimiento("30")
        self.assertEqual(self.obligacion.movimientos.count(), 2)

    def test_obligacion_unica_por_gasto_y_reintento_no_recalcula_importe(self):
        with self.assertRaises(ValidationError):
            crear_obligacion_pago(gasto=self.gasto, contraparte_nombre="Otro", clave=uuid4(), usuario=self.usuario)
        datos = self.obligacion.solicitud
        misma = crear_obligacion_pago(gasto=self.gasto, contraparte_nombre=datos["nombre"], contraparte_referencia=datos["referencia"], clave=self.obligacion.clave, usuario=self.usuario)
        self.assertEqual(misma.pk, self.obligacion.pk)

    def test_reintegro_manteniendo_reabre_pendiente(self):
        self.devolver(self.movimiento(), efecto="mantener")
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["pendiente"]), (100, 30))
        self.assertFalse(AjusteObligacion.objects.exists())

    def test_reintegro_reduciendo_no_reabre_y_es_atomico(self):
        self.devolver(self.movimiento(), efecto="reducir")
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["pendiente"]), (70, 0))
        self.assertFalse(AjusteGasto.objects.exists())

    def test_reduccion_previa_no_se_aplica_dos_veces_y_conserva_deuda_no_relacionada(self):
        original = self.movimiento("60")
        ajuste = reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Descuento", clave=uuid4(), usuario=self.usuario)
        self.devolver(original, importe="20", efecto="reduccion_existente", ajuste=ajuste.pk)
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], 30)
        self.assertEqual(estado_obligacion(self.obligacion)["obligacion_actual"], 70)
        self.assertEqual(disponible_reduccion(ajuste), 10)
        with self.assertRaises(ValidationError):
            self.devolver(original, importe="20", efecto="reduccion_existente", ajuste=ajuste.pk)

    def test_reduccion_previa_de_otro_vinculo_rechazada(self):
        original = self.movimiento()
        with self.assertRaises(ValidationError):
            self.devolver(original, efecto="reduccion_existente", ajuste=999999)
        with self.assertRaises(ValidationError):
            self.devolver(original, efecto="mantener", ajuste=999999)

    def test_no_reintegra_mas_que_original_ni_reintegra_un_reintegro(self):
        original = self.movimiento("40")
        devolucion = self.devolver(original, "30")
        with self.assertRaises(ValidationError):
            self.devolver(original, "11")
        with self.assertRaises(ValidationError):
            self.devolver(devolucion, "1")

    def test_preview_no_escribe_y_confirma_version_no_solo_saldo(self):
        original = self.movimiento()
        datos = dict(original=original, importe="30", fecha=self.fecha, motivo="Prueba", efecto="reducir", usuario=self.usuario)
        plan = previsualizar_reintegro(**datos)
        self.assertEqual(MovimientoDinero.objects.count(), 1)
        self.assertEqual(AjusteObligacion.objects.count(), 0)
        reducir_obligacion(obligacion=self.obligacion, importe="10", motivo="Otro", clave=uuid4(), usuario=self.usuario)
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], plan["pendiente_anterior"])
        with self.assertRaises(EstadoDineroCambio):
            reintegrar_movimiento(**datos, clave=uuid4(), version_esperada=plan["version_esperada"])

    def test_reintento_reintegro_devuelve_registro_original_aunque_version_cambio(self):
        original = self.movimiento()
        datos = dict(original=original, importe="30", fecha=self.fecha, motivo="Prueba", efecto="reducir", usuario=self.usuario)
        plan = previsualizar_reintegro(**datos)
        datos.update(clave=uuid4(), version_esperada=plan["version_esperada"])
        primero = reintegrar_movimiento(**datos)
        self.assertEqual(reintegrar_movimiento(**datos).pk, primero.pk)
        self.assertEqual(AjusteObligacion.objects.count(), 1)

    def test_reintegro_no_reutiliza_clave_de_reduccion_independiente(self):
        original = self.movimiento()
        clave = uuid4()
        reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Prueba", clave=clave, usuario=self.usuario)
        datos = dict(original=original, importe="30", fecha=self.fecha, motivo="Prueba", efecto="reducir", usuario=self.usuario)
        version = previsualizar_reintegro(**datos)["version_esperada"]
        with self.assertRaises(ValidationError):
            reintegrar_movimiento(**datos, clave=clave, version_esperada=version)
        self.assertEqual(estado_obligacion(self.obligacion)["obligacion_actual"], 70)
        self.assertEqual(MovimientoDinero.objects.count(), 1)

    def test_importes_invalidos_y_fecha_futura_rechazados(self):
        for importe in ("0", "-1", "1.001", "NaN", "Infinity", "1000000000000"):
            with self.subTest(importe=importe), self.assertRaises(ValidationError):
                self.movimiento(importe)
        with self.assertRaises(ValidationError):
            registrar_movimiento(obligacion=self.obligacion, importe="1", fecha=timezone.localdate() + timedelta(days=1), clave=uuid4(), usuario=self.usuario)

    def test_historial_no_editable_y_delete_api_no_disponible(self):
        movimiento = self.movimiento("30")
        with self.assertRaises(ModelValidationError):
            movimiento.save()
        with self.assertRaises(ModelValidationError):
            self.obligacion.delete()
        self.assertEqual(self.client.delete(f"/api/movimientos-dinero/{movimiento.pk}/").status_code, 405)

    def test_admin_hereda_el_dinero_de_su_hospital_y_un_miembro_comun_no(self):
        """El admin de institución hereda las acciones financieras; nadie más.

        Decisión de `docs/plans/2026-09-18-finanzas-coberturas-usabilidad-diseno.md`:
        el rol hereda todas las acciones, para todas las áreas, sin crear
        concesiones duplicadas. Antes heredaba sólo `ver_costos` y `ver_gastos`
        y este caso afirmaba lo contrario. Lo que la herencia no toca —y sigue
        cerrado— es el miembro que no es admin y no tiene concesión.
        """
        admin = Usuario.objects.create_user("admin-con-dinero@test.local", "x")
        Membresia.objects.create(usuario=admin, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get("/api/obligaciones-financieras/").status_code, 200)
        registrar_movimiento(obligacion=self.obligacion, importe="30", fecha=self.fecha, clave=uuid4(), usuario=admin)

        comun = Usuario.objects.create_user("administrativo-sin-dinero@test.local", "x")
        Membresia.objects.create(usuario=comun, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        self.client.force_authenticate(comun)
        self.assertEqual(self.client.get("/api/obligaciones-financieras/").status_code, 403)
        with self.assertRaises(PermissionDenied):
            registrar_movimiento(obligacion=self.obligacion, importe="30", fecha=self.fecha, clave=uuid4(), usuario=comun)

    def test_api_lista_detalle_preview_auditan_y_fallan_cerrado(self):
        original = self.movimiento()
        respuesta = self.client.get(f"/api/obligaciones-financieras/{self.obligacion.pk}/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["pendiente"], "0.00")
        self.assertTrue(AccesoFinanciero.objects.filter(recurso="obligacionfinanciera").exists())
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            self.assertEqual(self.client.get("/api/obligaciones-financieras/").status_code, 503)
        respuesta = self.client.post(f"/api/movimientos-dinero/{original.pk}/previsualizar-reintegro/", {"importe": "30", "fecha": str(self.fecha), "motivo": "Devolución", "efecto": "mantener"}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["pendiente_resultante"], "30.00")

    def test_filtro_sin_area_y_fecha_del_movimiento_no_periodo_gasto(self):
        self.movimiento()
        self.assertEqual(self.client.get("/api/obligaciones-financieras/?area_sin_asignar=true").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/obligaciones-financieras/?area_sin_asignar=true&area={self.area.pk}").status_code, 400)
        self.assertEqual(self.client.get("/api/movimientos-dinero/?fecha_desde=2026-09-01&fecha_hasta=2026-09-30").data["count"], 1)
        self.assertEqual(self.client.get("/api/movimientos-dinero/?fecha_hasta=2026-08-31").data["count"], 0)

    def test_permiso_sensible_y_area_se_comprueban_en_servicio(self):
        usuario = Usuario.objects.create_user("alcance-dinero@test.local", "x")
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        permiso = ConcesionFinanciera.objects.create(membresia=membresia, accion="registrar_dinero")
        with self.assertRaises(PermissionDenied):
            registrar_movimiento(obligacion=self.obligacion, importe="1", fecha=self.fecha, clave=uuid4(), usuario=usuario)
        permiso.areas.add(self.area)
        registrar_movimiento(obligacion=self.obligacion, importe="1", fecha=self.fecha, clave=uuid4(), usuario=usuario)
        ObligacionFinanciera.objects.filter(pk=self.obligacion.pk).update(sensible=True)
        with self.assertRaises(PermissionDenied):
            registrar_movimiento(obligacion=self.obligacion, importe="1", fecha=self.fecha, clave=uuid4(), usuario=usuario)

    def test_no_crea_deuda_desde_gasto_pendiente(self):
        Gasto.objects.filter(pk=self.gasto.pk).update(estado=Gasto.Estado.PENDIENTE_APROBACION)
        with self.assertRaises(ValidationError):
            crear_obligacion_pago(gasto=self.gasto, contraparte_nombre="Proveedor", clave=uuid4(), usuario=self.usuario)

    def test_sin_permiso_de_escritura_no_registra_y_otro_hospital_no_ve(self):
        usuario = Usuario.objects.create_user("lectura-dinero@test.local", "x")
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        ConcesionFinanciera.objects.create(membresia=membresia, accion="ver_dinero", todas_las_areas=True)
        self.client.force_authenticate(usuario)
        respuesta = self.client.post(f"/api/obligaciones-financieras/{self.obligacion.pk}/movimientos/", {"importe": "1", "fecha": str(self.fecha), "clave": str(uuid4())}, format="json")
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertFalse(MovimientoDinero.objects.exists())
        otra = Institucion.objects.create(nombre="Otro hospital")
        membresia.institucion = otra
        membresia.save()
        self.assertEqual(self.client.get("/api/obligaciones-financieras/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/obligaciones-financieras/{self.obligacion.pk}/").status_code, 404)


class AuditoriaEscrituraDineroTests(DatosDinero, APITestCase):
    def setUp(self):
        self.preparar()
        self.client.force_authenticate(self.usuario)

    def test_pago_audita_cuenta_contexto_y_mes_economico(self):
        respuesta = self.client.post(f"/api/obligaciones-financieras/{self.obligacion.pk}/movimientos/", {
            "importe": "30", "fecha": str(self.fecha), "clave": str(uuid4()),
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        acceso = AccesoFinanciero.objects.get(accion="movimientos")
        self.assertEqual((acceso.recurso, acceso.objeto_id, acceso.institucion_id, acceso.area_id),
                         ("obligacionfinanciera", self.obligacion.pk, self.institucion.pk, self.area.pk))
        self.assertEqual(acceso.periodo_economico, self.obligacion.periodo_economico)

    def test_auditoria_caida_revierte_pago_y_reduccion(self):
        for accion, datos in (("movimientos", {"importe": "30", "fecha": str(self.fecha)}),
                              ("reducir", {"importe": "10", "motivo": "Descuento"})):
            with self.subTest(accion=accion), patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
                respuesta = self.client.post(f"/api/obligaciones-financieras/{self.obligacion.pk}/{accion}/", {**datos, "clave": str(uuid4())}, format="json")
            self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertFalse(MovimientoDinero.objects.exists())
        self.assertFalse(AjusteObligacion.objects.exists())

    def test_auditoria_caida_revierte_alta_de_cuenta(self):
        gasto = registrar_gasto(concepto=self.concepto, institucion=self.institucion, area=self.area,
                               importe="50", periodo_economico=self.obligacion.periodo_economico, registrado_por=self.usuario)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post("/api/obligaciones-financieras/", {
                "gasto": gasto.pk, "contraparte_nombre": "Proveedor", "clave": str(uuid4()),
            }, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertFalse(ObligacionFinanciera.objects.filter(gasto=gasto).exists())

    def test_reintento_de_aprobado_tambien_audita_y_falla_cerrado(self):
        movimiento = self.movimiento("30")
        url = f"/api/movimientos-dinero/{movimiento.pk}/aprobar/"
        for _ in range(2):
            self.assertEqual(self.client.post(url, {}, format="json").status_code, 200)
        self.assertEqual(AccesoFinanciero.objects.filter(recurso="movimientodinero", accion="aprobar", objeto_id=movimiento.pk).count(), 2)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post(url, {}, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertNotIn("movimientos", respuesta.data)
        self.assertEqual(MovimientoDinero.objects.count(), 1)

    def test_auditoria_caida_revierte_decisiones_pendientes(self):
        movimiento = self.movimiento("30", aprobado=False)
        ajuste = reducir_obligacion(obligacion=self.obligacion, importe="10", motivo="Descuento",
                                    clave=uuid4(), usuario=self.usuario, aprobado=False)
        for accion in ("aprobar", "rechazar"):
            for url, datos in ((f"/api/movimientos-dinero/{movimiento.pk}/{accion}/", {"motivo": "No corresponde"}),
                               (f"/api/obligaciones-financieras/{self.obligacion.pk}/{accion}-ajuste/", {"ajuste": ajuste.pk, "motivo": "No corresponde"})):
                with self.subTest(url=url), patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
                    respuesta = self.client.post(url, datos, format="json")
                self.assertEqual(respuesta.status_code, 503, respuesta.data)
                movimiento.refresh_from_db()
                ajuste.refresh_from_db()
                self.assertEqual((movimiento.estado, ajuste.estado), ("pendiente_aprobacion", "pendiente_aprobacion"))

    def test_auditoria_caida_revierte_devolucion_y_reduccion_conjuntas(self):
        original = self.movimiento()
        datos = dict(original=original, importe="10", fecha=self.fecha, motivo="Devolución", efecto="reducir", usuario=self.usuario)
        plan = previsualizar_reintegro(**datos)
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError("fallo")):
            respuesta = self.client.post(f"/api/movimientos-dinero/{original.pk}/reintegrar/", {
                "importe": "10", "fecha": str(self.fecha), "motivo": "Devolución", "efecto": "reducir",
                "clave": str(uuid4()), "version_esperada": plan["version_esperada"],
            }, format="json")
        self.assertEqual(respuesta.status_code, 503, respuesta.data)
        self.assertEqual(MovimientoDinero.objects.count(), 1)
        self.assertFalse(AjusteObligacion.objects.exists())
        self.assertEqual(estado_obligacion(self.obligacion)["registrado_neto"], 100)


@skipUnless(connection.vendor == "postgresql", "La garantía de bloqueo requiere PostgreSQL; SQLite no la demuestra.")
class DineroConcurrenciaTests(DatosDinero, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def test_dos_pagos_simultaneos_no_superan_pendiente(self):
        barrera = Barrier(2)

        def pagar():
            connections.close_all()
            try:
                barrera.wait(timeout=10)
                registrar_movimiento(obligacion=self.obligacion.pk, importe="70", fecha=self.fecha, clave=uuid4(), usuario=self.usuario)
                return "registrado"
            except ValidationError:
                return "rechazado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(lambda _: pagar(), range(2)))
        self.assertCountEqual(resultados, ["registrado", "rechazado"])
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], 30)

    def test_dos_reintegros_no_superan_original(self):
        original = self.movimiento()
        datos = dict(original=original.pk, importe="70", fecha=self.fecha, motivo="Prueba", efecto="mantener", usuario=self.usuario)
        version = previsualizar_reintegro(**datos)["version_esperada"]
        barrera = Barrier(2)

        def devolver():
            connections.close_all()
            try:
                barrera.wait(timeout=10)
                reintegrar_movimiento(**datos, clave=uuid4(), version_esperada=version)
                return "registrado"
            except (ValidationError, EstadoDineroCambio):
                return "rechazado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(lambda _: devolver(), range(2)))
        self.assertCountEqual(resultados, ["registrado", "rechazado"])
        self.assertEqual(estado_obligacion(self.obligacion)["registrado_neto"], 30)
