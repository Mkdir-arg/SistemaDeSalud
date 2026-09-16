"""Seguimiento hospitalario: dinero por cuenta, origen y lectura restringida."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.dinero import (
    crear_obligacion_cobro, decidir_ajuste, decidir_movimiento,
    estado_obligacion, previsualizar_reintegro, reducir_obligacion,
    registrar_movimiento, reintegrar_movimiento,
)
from apps.finanzas.models import AccesoFinanciero, ObligacionFinanciera, Prestacion
from apps.finanzas.models_cobros import SnapshotCobroAtencion
from apps.finanzas.services import registrar_atencion_completada
from apps.flujos.models import Nodo
from apps.instituciones.models import Area, Institucion

from .cobertura import liberar, seleccionar_afiliacion
from .cobros import resolver_saldo
from .models import DistribucionCobro, Financiador, ReservaCobertura, VinculoPrestacion
from .test_cobertura import CoberturaSetup


CAMPOS_DINERO = (
    "importe_original", "ajustes_aprobados", "obligacion_actual",
    "registrado_neto", "pendiente", "saldo_a_devolver", "por_aprobar",
    "reintegros_por_aprobar", "ajustes_por_aprobar",
)


class SeguimientoSetup(CoberturaSetup):
    url = "/api/seguimiento-cobros/"

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def consultar(self, **filtros):
        response = self.client.get(self.url, {"institucion": self.institucion.pk, **filtros})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        return response.data

    def nuevo_caso(self, area=None):
        caso = Caso.objects.create(
            institucion=self.institucion, version=self.caso.version,
            ciudadano=self.paciente, area_actual=area or self.area,
        )
        seleccionar_afiliacion(
            caso=caso, usuario=self.admin, afiliado=self.afiliado,
            motivo="Afiliación verificada para la atención",
        )
        return caso

    def realizar(self, caso=None, prestacion=None, acepta=True):
        caso = caso or self.nuevo_caso()
        prestacion = prestacion or self.prestacion
        if acepta:
            self.reservar(caso=caso, prestacion=prestacion, acepta=True)
        evento = EventoCaso.objects.create(
            caso=caso, nodo=prestacion.nodo, autor=self.usuario,
            titulo="Atención completada",
        )
        hecho = registrar_atencion_completada(caso, prestacion.nodo, evento, self.usuario)
        return ReservaCobertura.objects.get(hecho=hecho, prestacion=prestacion)

    def movimiento(self, obligacion, importe, **datos):
        valores = dict(
            obligacion=obligacion, importe=Decimal(importe), fecha=self.hoy,
            usuario=self.admin, clave=uuid4(), aprobado=True,
        )
        valores.update(datos)
        return registrar_movimiento(**valores)

    def reduccion(self, obligacion, importe, **datos):
        valores = dict(
            obligacion=obligacion, importe=Decimal(importe), usuario=self.admin,
            motivo="Reducción documentada", clave=uuid4(), aprobado=True,
        )
        valores.update(datos)
        return reducir_obligacion(**valores)

    def reintegro(self, original, importe, **datos):
        valores = dict(
            original=original, importe=Decimal(importe), fecha=self.hoy,
            usuario=self.admin, motivo="Devolución documentada",
            efecto="mantener", aprobado=True,
        )
        valores.update(datos)
        previo = previsualizar_reintegro(**valores)
        return reintegrar_movimiento(
            **valores, clave=uuid4(), version_esperada=previo["version_esperada"],
        )


class SeguimientoCuentasTests(SeguimientoSetup, APITestCase):
    def test_separa_responsables_y_totales_incluyen_todas_las_paginas(self):
        reserva = self.realizar()
        distribucion = DistribucionCobro.objects.get(reserva=reserva)
        primera = self.consultar(page_size=1)
        segunda = self.consultar(page_size=1, page=2)
        self.assertEqual(primera["count"], 2)
        self.assertEqual(len(primera["results"]), 1)
        self.assertIsNotNone(primera["next"])
        self.assertEqual(primera["resumen"], segunda["resumen"])
        self.assertEqual(primera["resumen"]["registros"], 2)
        self.assertEqual(primera["resumen"]["importe_original"], "100.00")
        self.assertEqual(primera["resumen"]["pendiente"], "100.00")
        filas = {fila["responsable"]: fila for fila in primera["results"] + segunda["results"]}
        self.assertEqual(filas["financiador"]["id"], distribucion.obligacion_financiador_id)
        self.assertEqual(filas["paciente"]["id"], distribucion.obligacion_paciente_id)
        self.assertEqual(filas["financiador"]["importe_original"], "80.00")
        self.assertEqual(filas["paciente"]["importe_original"], "20.00")
        for fila in filas.values():
            self.assertEqual(set(fila), {
                "id", "caso", "fecha", "area", "sensible", "reserva", "prestacion",
                "financiador", "financiador_nombre", "responsable", "contraparte_nombre",
                *CAMPOS_DINERO,
            })
            self.assertEqual(fila["caso"], reserva.hecho.caso_origen_id)
            self.assertEqual(fila["reserva"], reserva.pk)
            self.assertEqual(fila["financiador"], self.financiador.pk)
            self.assertEqual(fila["area"], self.area.pk)
            for campo in CAMPOS_DINERO:
                self.assertIsInstance(fila[campo], str)

    def test_sumatorias_sin_producto_cartesiano_y_paridad_con_dinero(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        primero = self.movimiento(obligacion, "30")
        self.movimiento(obligacion, "10")
        self.reintegro(primero, "5")
        self.reduccion(obligacion, "3")
        self.reduccion(obligacion, "2")
        self.movimiento(obligacion, "7", aprobado=False)
        self.reintegro(primero, "4", aprobado=False)
        self.reduccion(obligacion, "6", aprobado=False)
        rechazado = self.movimiento(obligacion, "11", aprobado=False)
        decidir_movimiento(movimiento=rechazado, usuario=self.admin, aprobar=False, motivo="Comprobante duplicado")
        ajuste_rechazado = self.reduccion(obligacion, "1", aprobado=False)
        decidir_ajuste(ajuste=ajuste_rechazado, obligacion=obligacion, usuario=self.admin, aprobar=False, motivo="No corresponde")
        resultado = self.consultar(responsable="financiador")
        self.assertEqual(resultado["count"], 1)
        fila = resultado["results"][0]
        self.assertEqual(fila["ajustes_aprobados"], "-5.00")
        referencia = estado_obligacion(obligacion)
        for campo in CAMPOS_DINERO[2:]:
            self.assertEqual(Decimal(fila[campo]), referencia[campo], campo)
        self.assertEqual(fila["obligacion_actual"], "75.00")
        self.assertEqual(fila["registrado_neto"], "35.00")
        self.assertEqual(fila["pendiente"], "40.00")
        for campo in CAMPOS_DINERO:
            self.assertEqual(resultado["resumen"][campo], fila[campo], campo)

    def test_saldo_a_devolver_no_compensa_deuda_del_otro_responsable(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        self.movimiento(obligacion, "80")
        self.reduccion(obligacion, "10")
        resumen = self.consultar()["resumen"]
        self.assertEqual(resumen["obligacion_actual"], "90.00")
        self.assertEqual(resumen["registrado_neto"], "80.00")
        self.assertEqual(resumen["pendiente"], "20.00")
        self.assertEqual(resumen["saldo_a_devolver"], "10.00")
        devolucion = self.consultar(estado="a_devolver")
        self.assertEqual([fila["id"] for fila in devolucion["results"]], [obligacion.pk])
        self.assertEqual(devolucion["resumen"]["pendiente"], "0.00")

    def test_filtros_estado_no_tratan_como_cobrado_lo_pendiente_de_aprobacion(self):
        reserva = self.realizar()
        distribucion = DistribucionCobro.objects.get(reserva=reserva)
        self.movimiento(distribucion.obligacion_financiador, "80", aprobado=False)
        self.movimiento(distribucion.obligacion_paciente, "20")
        pendiente = self.consultar(estado="pendiente")
        self.assertEqual([fila["id"] for fila in pendiente["results"]], [distribucion.obligacion_financiador_id])
        self.assertEqual(pendiente["resumen"]["pendiente"], "80.00")
        self.assertEqual(pendiente["resumen"]["registrado_neto"], "0.00")
        self.assertEqual(self.consultar(estado="por_aprobar")["count"], 1)
        saldada = self.consultar(estado="saldada")
        self.assertEqual([fila["id"] for fila in saldada["results"]], [distribucion.obligacion_paciente_id])

    def test_cargos_de_acuerdos_se_vinculan_por_fk_sin_inferir_referencia(self):
        primera = self.realizar(acepta=False)
        segunda = self.realizar(acepta=False)
        acuerdos = []
        for reserva, decision in [(primera, "financiador"), (segunda, "paciente")]:
            acuerdos.append(resolver_saldo(
                reserva=reserva, usuario=self.admin, decision=decision, importe=Decimal("20"),
                motivo="Aceptación administrativa", evidencia="Documento firmado", clave=uuid4(),
            ))
        no_vinculada = crear_obligacion_cobro(
            hecho=primera.hecho, importe=Decimal("13"), contraparte_nombre=self.financiador.nombre,
            contraparte_referencia=f"financiador:{self.financiador.pk}", creado_por=self.admin, clave=uuid4(),
        )
        resultado = self.consultar()
        self.assertEqual(resultado["count"], 4)
        filas = {fila["id"]: fila for fila in resultado["results"]}
        self.assertNotIn(no_vinculada.pk, filas)
        self.assertEqual(filas[acuerdos[0].obligacion_id]["responsable"], "financiador")
        self.assertEqual(filas[acuerdos[1].obligacion_id]["responsable"], "paciente")
        self.assertEqual(self.consultar(financiador=self.financiador.pk, responsable="paciente")["resumen"]["importe_original"], "20.00")

    def test_devolucion_por_aprobar_impide_clasificar_cuenta_como_saldada(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        cobro = self.movimiento(obligacion, "80")
        self.reintegro(cobro, "5", aprobado=False)
        self.assertEqual(self.consultar(estado="saldada")["count"], 0)
        pendientes = self.consultar(estado="por_aprobar")
        self.assertEqual([fila["id"] for fila in pendientes["results"]], [obligacion.pk])
        self.assertEqual(pendientes["resumen"]["reintegros_por_aprobar"], "5.00")
        self.assertEqual(pendientes["resumen"]["registrado_neto"], "80.00")

    def test_fecha_filtra_prestacion_y_no_fecha_de_movimiento(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        # Una entrega previa registrada no cambia la cohorte de la prestación.
        ayer = self.hoy - timedelta(days=1)
        self.movimiento(obligacion, "10", fecha=ayer)
        actual = self.consultar(desde=str(self.hoy), hasta=str(self.hoy))
        self.assertEqual(actual["count"], 2)
        self.assertEqual(actual["resumen"]["registrado_neto"], "10.00")
        self.assertEqual(self.consultar(desde=str(ayer), hasta=str(ayer))["count"], 0)

    def test_filtros_busqueda_y_responsable_son_aplicados_antes_del_resumen(self):
        reserva = self.realizar()
        self.assertEqual(self.consultar(search=str(reserva.caso_id))["count"], 2)
        self.assertEqual(self.consultar(search=self.financiador.nombre)["count"], 1)
        self.assertEqual(self.consultar(search=self.prestacion.nombre)["count"], 2)
        self.assertEqual(self.consultar(responsable="paciente")["resumen"]["importe_original"], "20.00")
        vacia = self.consultar(search="No existe esta contraparte")
        self.assertEqual(vacia["count"], 0)
        self.assertEqual(vacia["resumen"]["registros"], 0)
        for campo in CAMPOS_DINERO:
            self.assertEqual(vacia["resumen"][campo], "0.00", campo)


class SeguimientoAlcanceTests(SeguimientoSetup, APITestCase):
    def test_clinico_financiador_y_resolver_no_sustituyen_ver_dinero(self):
        self.realizar()
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        for usuario in (self.usuario, self.operador):
            with self.subTest(usuario=usuario.pk):
                self.client.force_authenticate(usuario)
                self.assertEqual(self.client.get(self.url, {"institucion": self.institucion.pk}).status_code, 403)
        self.conceder("resolver_cobertura", sensible=True)
        self.client.force_authenticate(self.usuario)
        for vista in ("cuentas", "pendientes", "captura"):
            self.assertEqual(self.client.get(self.url, {"institucion": self.institucion.pk, "vista": vista}).status_code, 403)
        self.assertFalse(AccesoFinanciero.objects.filter(usuario=self.usuario).exists())

    def test_permiso_limitado_al_area_habilita_seguimiento_y_opciones(self):
        propia = self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Área reservada")
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        resultado = self.consultar()
        self.assertEqual(resultado["count"], 2)
        self.assertEqual({fila["reserva"] for fila in resultado["results"]}, {propia.pk})
        self.assertEqual(resultado["opciones"]["areas"], [{"id": self.area.pk, "nombre": self.area.nombre}])
        opciones = self.client.get("/api/coberturas/opciones/", {"institucion": self.institucion.pk})
        self.assertEqual(opciones.status_code, 200, opciones.data)
        self.assertTrue(opciones.data["permisos"]["seguimiento"])
        self.assertFalse(opciones.data["permisos"]["resolver"])

    def test_sensibles_requieren_concesion_explicita_sin_filtrarse_en_totales(self):
        publica = self.realizar()
        self.politica(sensible=True)
        self.realizar()
        concesion = self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        restringido = self.consultar()
        self.assertEqual(restringido["count"], 2)
        self.assertEqual({fila["reserva"] for fila in restringido["results"]}, {publica.pk})
        self.assertEqual(restringido["resumen"]["importe_original"], "100.00")
        concesion.permite_sensibles = True
        concesion.save(update_fields=["permite_sensibles"])
        self.assertEqual(self.consultar()["count"], 4)

    def test_institucion_ajena_no_es_accesible_por_membresia_de_otro_hospital(self):
        self.conceder("ver_dinero", sensible=True)
        caso, prestacion = self.otro_hospital()
        self.realizar(caso=caso, prestacion=prestacion)
        self.client.force_authenticate(self.usuario)
        response = self.client.get(self.url, {"institucion": caso.institucion_id})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.consultar()["count"], 0)

    def test_opciones_no_publican_financiadores_sin_actividad_autorizada(self):
        self.realizar()
        Financiador.objects.create(nombre="Organización sin relación", tipo="mutual")
        Area.objects.create(institucion=self.institucion, nombre="Sin actividad")
        resultado = self.consultar()
        self.assertEqual(resultado["opciones"]["financiadores"], [{"id": self.financiador.pk, "nombre": self.financiador.nombre}])
        self.assertEqual(resultado["opciones"]["areas"], [{"id": self.area.pk, "nombre": self.area.nombre}])

    def test_traslado_del_caso_no_reescribe_origen_ni_alcance(self):
        reserva = self.realizar()
        otro = Institucion.objects.create(nombre="Hospital de traslado")
        area = Area.objects.create(institucion=otro, nombre="Destino")
        Caso.objects.filter(pk=reserva.caso_id).update(institucion=otro, area_actual=area)
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        resultado = self.consultar()
        self.assertEqual(resultado["count"], 2)
        self.assertEqual({fila["area"] for fila in resultado["results"]}, {self.area.pk})
        self.assertEqual({fila["caso"] for fila in resultado["results"]}, {reserva.hecho.caso_origen_id})

    def test_sin_area_asignada_requiere_alcance_institucional(self):
        caso = self.nuevo_caso()
        caso.area_actual = None
        caso.save(update_fields=["area_actual"])
        sin_area = self.realizar(caso=caso)
        self.realizar()
        resultado = self.consultar(area_sin_asignar="true")
        self.assertEqual(resultado["count"], 2)
        self.assertEqual({fila["reserva"] for fila in resultado["results"]}, {sin_area.pk})
        self.assertTrue(all(fila["area"] is None for fila in resultado["results"]))
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.consultar(area_sin_asignar="true")["count"], 0)

    def test_sin_autenticacion_no_entrega_datos(self):
        self.realizar()
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url, {"institucion": self.institucion.pk}).status_code, 401)

    def test_seguimiento_no_habilita_edicion_ni_detalle_generico(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        response = self.client.post(self.url, {"institucion": self.institucion.pk}, format="json")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.get(f"{self.url}{obligacion.pk}/").status_code, 404)

    def test_parametros_invalidos_no_devuelven_falsos_vacios(self):
        for datos in (
            {}, {"institucion": "x"}, {"institucion": "-1"},
            {"desde": "31/01/2026"}, {"hasta": "2026-02-30"},
            {"desde": str(self.hoy), "hasta": str(self.hoy - timedelta(days=1))},
            {"area": "x"}, {"financiador": "0"}, {"responsable": "hospital"},
            {"vista": "otra"}, {"estado": "inventado"},
            {"vista": "captura", "financiador": self.financiador.pk},
            {"vista": "captura", "responsable": "paciente"},
            {"vista": "captura", "estado": "pendiente"},
            {"vista": "pendientes", "responsable": "paciente"},
            {"area_sin_asignar": "quizás"},
            {"area_sin_asignar": "true", "area": self.area.pk},
        ):
            with self.subTest(datos=datos):
                filtros = {} if not datos else {"institucion": self.institucion.pk, **datos}
                response = self.client.get(self.url, filtros)
                self.assertEqual(response.status_code, 400, response.data)


class SeguimientoPendientesTests(SeguimientoSetup, APITestCase):
    def test_pendiente_muestra_saldo_sin_crear_cargo_del_paciente(self):
        pendiente = self.realizar(acepta=False)
        self.realizar()
        reservada = self.reservar(caso=self.nuevo_caso())
        liberada = self.reservar(caso=self.nuevo_caso())
        liberar(reserva=liberada, usuario=self.admin, motivo="No se realizó", no_realizada=True)
        cargos = ObligacionFinanciera.objects.count()
        resultado = self.consultar(vista="pendientes")
        self.assertEqual(resultado["count"], 1)
        fila = resultado["results"][0]
        self.assertEqual(set(fila), {
            "id", "caso", "fecha", "area", "sensible", "reserva", "prestacion",
            "financiador", "financiador_nombre", "estado", "motivo", "importe_pendiente",
        })
        self.assertEqual(fila["reserva"], pendiente.pk)
        self.assertEqual(fila["estado"], "pendiente")
        self.assertEqual(fila["importe_pendiente"], "20.00")
        self.assertEqual(resultado["resumen"], {"registros": 1, "importes_desconocidos": 0, "importe_pendiente": "20.00"})
        self.assertEqual(ObligacionFinanciera.objects.count(), cargos)
        self.assertIsNone(DistribucionCobro.objects.get(reserva=pendiente).obligacion_paciente_id)
        self.assertNotIn(reservada.pk, [fila["reserva"] for fila in resultado["results"]])

    def test_arancel_y_evaluacion_desconocidos_no_se_presentan_como_cero(self):
        self.politica(importe=None)
        arancel = self.realizar(acepta=False)
        self.politica()
        caso = self.nuevo_caso()
        seleccionar_afiliacion(caso=caso, usuario=self.admin, declaracion="Afiliación a verificar", motivo="Pendiente documental")
        evaluacion = self.realizar(caso=caso, acepta=False)
        resultado = self.consultar(vista="pendientes", page_size=1)
        self.assertEqual(resultado["count"], 2)
        self.assertIsNone(resultado["results"][0]["importe_pendiente"])
        self.assertEqual(resultado["resumen"], {"registros": 2, "importes_desconocidos": 2, "importe_pendiente": "0.00"})
        self.assertEqual(self.consultar(vista="pendientes", estado="arancel_pendiente")["results"][0]["reserva"], arancel.pk)
        self.assertEqual(self.consultar(vista="pendientes", estado="evaluacion_pendiente")["results"][0]["reserva"], evaluacion.pk)

    def test_pendientes_conservan_area_y_sensibilidad_del_origen(self):
        publica = self.realizar(acepta=False)
        self.politica(sensible=True)
        self.realizar(acepta=False)
        destino = Area.objects.create(institucion=self.institucion, nombre="Otro sector")
        Caso.objects.filter(pk=publica.caso_id).update(area_actual=destino)
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        resultado = self.consultar(vista="pendientes")
        self.assertEqual(resultado["count"], 1)
        self.assertEqual(resultado["results"][0]["reserva"], publica.pk)
        self.assertEqual(resultado["results"][0]["area"], self.area.pk)

    def captura_fallida(self, sin_snapshot=False):
        contexto = patch("apps.finanzas.models_cobros.SnapshotCobroAtencion.objects.get_or_create", side_effect=RuntimeError("Ancla no disponible")) if sin_snapshot else patch("apps.finanzas.cobros.capturar_cobros_atencion", side_effect=RuntimeError("Captura no disponible"))
        caso = self.nuevo_caso()
        evento = EventoCaso.objects.create(caso=caso, nodo=self.nodo, autor=self.usuario, titulo="Atención completada")
        with contexto:
            hecho = registrar_atencion_completada(caso, self.nodo, evento, self.usuario)
        self.assertFalse(ReservaCobertura.objects.filter(hecho=hecho).exists())
        return hecho

    def test_captura_fallida_con_y_sin_snapshot_es_visible_sin_inventar_deuda(self):
        con_ancla = self.captura_fallida()
        sin_ancla = self.captura_fallida(sin_snapshot=True)
        self.realizar()
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=con_ancla).capturado)
        self.assertFalse(SnapshotCobroAtencion.objects.filter(hecho=sin_ancla).exists())
        cargos = ObligacionFinanciera.objects.count()
        resultado = self.consultar(vista="captura", page_size=1)
        self.assertEqual(resultado["count"], 2)
        self.assertEqual(resultado["resumen"], {"registros": 2})
        fila = resultado["results"][0]
        self.assertEqual(fila["estado"], "captura_pendiente")
        self.assertTrue(fila["sensible"])
        self.assertEqual(set(fila), {"id", "caso", "fecha", "area", "sensible", "estado", "motivo"})
        self.assertEqual(ObligacionFinanciera.objects.count(), cargos)

    def test_captura_sin_sensibilidad_verificable_requiere_permiso_sensible(self):
        hecho = self.captura_fallida()
        concesion = self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.consultar(vista="captura")["count"], 0)
        concesion.permite_sensibles = True
        concesion.save(update_fields=["permite_sensibles"])
        self.assertEqual(self.consultar(vista="captura")["results"][0]["id"], hecho.pk)

    def test_pendiente_sin_sensibilidad_evaluada_no_se_presume_publico(self):
        reserva = self.realizar(acepta=False)
        datos = dict(reserva.evaluacion)
        datos.pop("sensible")
        ReservaCobertura.objects.filter(pk=reserva.pk).update(evaluacion=datos)
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.consultar(vista="pendientes")["count"], 0)

    def test_politica_inexistente_no_convierte_sensibilidad_por_defecto_en_permiso(self):
        nodo = Nodo.objects.create(version=self.caso.version, tipo=Nodo.Tipo.ATENCION, titulo="Control")
        prestacion = Prestacion.objects.create(
            institucion=self.institucion, nodo=nodo, codigo="CONTROL", nombre="Control sin política",
        )
        VinculoPrestacion.objects.create(prestacion=prestacion, comun=self.comun)
        reserva = self.realizar(prestacion=prestacion, acepta=False)
        self.assertIsNone(reserva.evaluacion["politica"])
        self.assertFalse(reserva.evaluacion["sensible"])
        concesion = self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.consultar(vista="pendientes")["count"], 0)
        concesion.permite_sensibles = True
        concesion.save(update_fields=["permite_sensibles"])
        fila = self.consultar(vista="pendientes")["results"][0]
        self.assertEqual(fila["reserva"], reserva.pk)
        self.assertTrue(fila["sensible"])
        self.assertIsNone(fila["importe_pendiente"])


class SeguimientoAuditoriaTests(SeguimientoSetup, APITestCase):
    def test_audita_alcance_de_todos_los_totales_no_solo_la_pagina(self):
        self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.politica(sensible=True)
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        resultado = self.consultar(page_size=1)
        self.assertEqual(resultado["count"], 4)
        accesos = AccesoFinanciero.objects.filter(usuario=self.admin, recurso="seguimiento-cobros", accion="cuentas")
        self.assertEqual(set(accesos.values_list("institucion_id", "area_id", "sensible", "periodo_economico")), {
            (self.institucion.pk, self.area.pk, False, self.hoy.replace(day=1)),
            (self.institucion.pk, otra_area.pk, True, self.hoy.replace(day=1)),
        })
        self.assertEqual(sum(accesos.values_list("resultados", flat=True)), 4)

    def test_fallo_auditoria_no_entrega_resultados_ni_importes(self):
        self.realizar(acepta=False)
        for vista in ("cuentas", "pendientes"):
            with self.subTest(vista=vista), patch("apps.finanzas.models.AccesoFinanciero.objects.create", side_effect=RuntimeError("Registro no disponible")):
                response = self.client.get(self.url, {"institucion": self.institucion.pk, "vista": vista})
                self.assertEqual(response.status_code, 503, response.data)
                self.assertNotIn("results", response.data)
                self.assertNotIn("resumen", response.data)
                self.assertIn("no-store", response["Cache-Control"])

    def test_capturas_tambien_exigen_auditoria_antes_de_entregarse(self):
        with patch("apps.finanzas.cobros.capturar_cobros_atencion", side_effect=RuntimeError("Captura no disponible")):
            hecho = self.atencion()
        self.assertTrue(hecho.cobertura_contexto)
        with patch("apps.finanzas.models.AccesoFinanciero.objects.create", side_effect=RuntimeError("Registro no disponible")):
            response = self.client.get(self.url, {"institucion": self.institucion.pk, "vista": "captura"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("results", response.data)
        self.assertNotIn("resumen", response.data)

    def test_auditoria_distingue_faltantes_administrativos_de_cuentas(self):
        self.realizar(acepta=False)
        self.consultar(vista="pendientes")
        acceso = AccesoFinanciero.objects.get(usuario=self.admin, recurso="seguimiento-cobros", accion="pendientes")
        self.assertEqual(acceso.resultados, 1)
        self.assertEqual(acceso.periodo_economico, self.hoy.replace(day=1))

    def test_fallo_en_segundo_grupo_revierte_auditoria_parcial(self):
        self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        crear = AccesoFinanciero.objects.create
        llamadas = []

        def registrar(**datos):
            llamadas.append(datos)
            if len(llamadas) == 2:
                raise RuntimeError("Fallo al persistir el segundo grupo")
            return crear(**datos)

        with patch("apps.finanzas.models.AccesoFinanciero.objects.create", side_effect=registrar):
            response = self.client.get(self.url, {"institucion": self.institucion.pk})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(len(llamadas), 2)
        self.assertFalse(AccesoFinanciero.objects.exists())
