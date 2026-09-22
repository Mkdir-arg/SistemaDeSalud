"""Confirmado y reservado son distintos; aprobar nunca duplica dinero."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from .dinero import (decidir_ajuste, decidir_movimiento, disponible_reduccion,
                     disponible_reintegro, estado_obligacion, previsualizar_reintegro,
                     reducir_obligacion, registrar_movimiento, reintegrar_movimiento)
from .models import AjusteObligacion, ConcesionFinanciera, MovimientoDinero
from .test_dinero import DatosDinero


class AprobacionesDineroTests(DatosDinero, APITestCase):
    def setUp(self):
        self.preparar()
        self.operador = Usuario.objects.create_user("registro-sin-aprobar@test.local", "x")
        # Rol sin herencia financiera a propósito: todo este archivo comprueba que
        # la facultad de aprobar viene de la concesión y no del rol. El admin de
        # institución hereda las dieciocho acciones, así que usarlo acá haría que
        # el operador se autoaprobara y las afirmaciones negativas pasaran solas.
        self.membresia = Membresia.objects.create(usuario=self.operador, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        for accion in ("ver_dinero", "registrar_dinero", "corregir_dinero"):
            ConcesionFinanciera.objects.create(membresia=self.membresia, accion=accion, todas_las_areas=True)
        self.client.force_authenticate(self.usuario)

    def registrar(self, importe="30", **kwargs):
        return registrar_movimiento(obligacion=self.obligacion, importe=importe, fecha=self.fecha, clave=uuid4(), usuario=self.operador, **kwargs)

    def reintegro(self, original, importe="30", efecto="reducir", **kwargs):
        datos = dict(original=original, importe=importe, fecha=self.fecha, motivo="Devolución", efecto=efecto, usuario=self.operador, **kwargs)
        preview = previsualizar_reintegro(**datos)
        return reintegrar_movimiento(**datos, clave=uuid4(), version_esperada=preview["version_esperada"])

    def test_registrador_sin_aprobar_reserva_sin_confirmar(self):
        movimiento = self.registrar()
        self.assertEqual(movimiento.estado, "pendiente_aprobacion")
        self.assertIsNone(movimiento.aprobado_por_id)
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["registrado_neto"], estado["pendiente"], estado["por_aprobar"], estado["disponible_registro"]), (0, 100, 30, 70))
        with self.assertRaises(ValidationError):
            self.registrar("80")
        with self.assertRaises(PermissionDenied):
            self.registrar("1", aprobado=True)

    def test_el_admin_de_institucion_tampoco_aprueba_lo_que_registra(self):
        """Cuatro ojos: el rol hereda registrar dinero, no aprobarlo.

        Es la garantía concreta detrás de `ACCIONES_SIN_HERENCIA`. Mientras el
        admin heredó las dieciocho acciones, firmaba su propio movimiento en un
        solo paso y el control no existía para ese rol. Acá el movimiento entra
        y queda esperando a otra persona.
        """
        admin = Usuario.objects.create_user("admin-firma-sola@test.local", "x")
        Membresia.objects.create(
            usuario=admin, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        movimiento = registrar_movimiento(
            obligacion=self.obligacion, importe="30", fecha=self.fecha, clave=uuid4(), usuario=admin,
        )
        self.assertEqual(movimiento.estado, "pendiente_aprobacion")
        self.assertIsNone(movimiento.aprobado_por_id)
        with self.assertRaises(PermissionDenied):
            registrar_movimiento(
                obligacion=self.obligacion, importe="1", fecha=self.fecha, clave=uuid4(),
                usuario=admin, aprobado=True,
            )

    def test_aprobador_default_true_y_false_explicitamente_pendiente(self):
        confirmado = self.movimiento("20")
        pendiente = self.movimiento("30", aprobado=False)
        self.assertTrue(confirmado.aprobado)
        self.assertEqual(confirmado.aprobado_por_id, self.usuario.pk)
        self.assertIsNotNone(confirmado.aprobado_en)
        self.assertFalse(pendiente.aprobado)
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], 80)

    def test_aprobar_confirma_una_vez_y_rechazar_libera_reserva(self):
        pendiente = self.registrar()
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True)
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True)
        self.assertEqual(estado_obligacion(self.obligacion)["registrado_neto"], 30)
        otro = self.registrar("20")
        decidir_movimiento(movimiento=otro, usuario=self.usuario, aprobar=False, motivo="No corresponde")
        otro.refresh_from_db()
        self.assertEqual(otro.estado, "rechazado")
        self.assertEqual(otro.rechazado_por_id, self.usuario.pk)
        self.assertIsNotNone(otro.rechazado_en)
        self.assertEqual(otro.motivo_rechazo, "No corresponde")
        self.assertEqual(estado_obligacion(self.obligacion)["disponible_registro"], 70)
        with self.assertRaises(ValidationError):
            decidir_movimiento(movimiento=otro, usuario=self.usuario, aprobar=True)

    def test_sin_permiso_de_aprobar_no_resuelve_y_motivo_es_obligatorio(self):
        pendiente = self.registrar()
        with self.assertRaises(PermissionDenied):
            decidir_movimiento(movimiento=pendiente, usuario=self.operador, aprobar=True)
        with self.assertRaises(ValidationError):
            decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=False)

    def test_idempotencia_incluye_opcion_aprobado(self):
        datos = dict(obligacion=self.obligacion, importe="30", fecha=self.fecha, clave=uuid4(), usuario=self.usuario, aprobado=False)
        primero = registrar_movimiento(**datos)
        self.assertEqual(registrar_movimiento(**datos).pk, primero.pk)
        with self.assertRaises(ValidationError):
            registrar_movimiento(**{**datos, "aprobado": True})
        decidir_movimiento(movimiento=primero, usuario=self.usuario, aprobar=True)
        self.assertEqual(registrar_movimiento(**datos).pk, primero.pk)

    def test_reintegro_solo_desde_original_aprobado(self):
        pendiente = self.registrar()
        with self.assertRaises(ValidationError):
            self.reintegro(pendiente, importe="10")
        self.assertEqual(disponible_reintegro(pendiente), 0)

    def test_reintegro_y_reduccion_pendientes_son_una_operacion(self):
        original = self.movimiento()
        datos = dict(original=original, importe="30", fecha=self.fecha, motivo="Devolución", efecto="reducir", usuario=self.operador)
        preview = previsualizar_reintegro(**datos)
        self.assertFalse(preview["aprobado"])
        self.assertEqual((preview["obligacion_resultante"], preview["registrado_neto_resultante"], preview["importe_reservado"]), (100, 100, 30))
        pendiente = self.reintegro(original)
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["registrado_neto"], estado["reintegros_por_aprobar"], estado["ajustes_por_aprobar"]), (100, 100, 30, 30))
        self.assertEqual(disponible_reintegro(original), 70)
        with self.assertRaises(ValidationError):
            decidir_ajuste(ajuste=pendiente.ajuste_id, obligacion=self.obligacion, usuario=self.usuario, aprobar=True)
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "aprobado")
        self.assertEqual(pendiente.ajuste.estado, "aprobado")
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["registrado_neto"], estado["pendiente"]), (70, 70, 0))

    def test_rechazar_devolucion_rechaza_su_reduccion_y_libera_ambas_reservas(self):
        original = self.movimiento()
        pendiente = self.reintegro(original)
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=False, motivo="Duplicado")
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.ajuste.estado, "rechazado")
        self.assertEqual(estado_obligacion(self.obligacion)["ajustes_por_aprobar"], 0)
        self.assertEqual(disponible_reintegro(original), 100)

    def test_fallo_de_segunda_decision_revierte_tambien_la_reduccion(self):
        original = self.movimiento()
        pendiente = self.reintegro(original)
        with patch.object(MovimientoDinero, "full_clean", side_effect=RuntimeError("fallo controlado")):
            with self.assertRaises(RuntimeError):
                decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "pendiente_aprobacion")
        self.assertEqual(pendiente.ajuste.estado, "pendiente_aprobacion")
        self.assertEqual(estado_obligacion(self.obligacion)["registrado_neto"], 100)

    def test_reduccion_existente_debe_estar_aprobada_y_reserva_uso(self):
        original = self.movimiento()
        ajuste = reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Descuento", clave=uuid4(), usuario=self.operador)
        with self.assertRaises(ValidationError):
            self.reintegro(original, efecto="reduccion_existente", ajuste=ajuste.pk)
        decidir_ajuste(ajuste=ajuste, obligacion=self.obligacion, usuario=self.usuario, aprobar=True)
        ajuste.refresh_from_db()
        pendiente = self.reintegro(original, efecto="reduccion_existente", ajuste=ajuste.pk)
        self.assertEqual(disponible_reduccion(ajuste), 0)
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=False, motivo="No realizar")
        self.assertEqual(disponible_reduccion(ajuste), 30)
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.estado, "aprobado")

    def test_reduccion_independiente_no_invalida_pago_reservado(self):
        self.registrar("70")
        with self.assertRaises(ValidationError):
            reducir_obligacion(obligacion=self.obligacion, importe="40", motivo="Descuento", clave=uuid4(), usuario=self.usuario)
        ajuste = reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Descuento", clave=uuid4(), usuario=self.operador)
        self.assertEqual(estado_obligacion(self.obligacion)["disponible_registro"], 0)
        decidir_ajuste(ajuste=ajuste, obligacion=self.obligacion, usuario=self.usuario, aprobar=True)
        pago = self.obligacion.movimientos.get()
        decidir_movimiento(movimiento=pago, usuario=self.usuario, aprobar=True)
        self.assertEqual(estado_obligacion(self.obligacion)["pendiente"], 0)

    def test_reducciones_pendientes_no_superan_obligacion(self):
        reducir_obligacion(obligacion=self.obligacion, importe="80", motivo="Descuento", clave=uuid4(), usuario=self.operador)
        with self.assertRaises(ValidationError):
            reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Otro", clave=uuid4(), usuario=self.operador)

    def test_reducir_no_roba_reserva_de_devolucion_conjunta(self):
        original = self.movimiento()
        pendiente = self.reintegro(original, importe="80")
        with self.assertRaises(ValidationError):
            reducir_obligacion(obligacion=self.obligacion, importe="30", motivo="Otro", clave=uuid4(), usuario=self.usuario)
        reducir_obligacion(obligacion=self.obligacion, importe="20", motivo="Otro", clave=uuid4(), usuario=self.usuario)
        decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True)
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["registrado_neto"], estado["saldo_a_devolver"]), (0, 20, 20))

    def test_conjunto_no_bloquea_el_pago_del_pendiente_no_relacionado(self):
        original = self.movimiento("40")
        devolucion = self.reintegro(original, importe="20")
        self.assertEqual(estado_obligacion(self.obligacion)["disponible_registro"], 60)
        pago = self.registrar("60")
        decidir_movimiento(movimiento=devolucion, usuario=self.usuario, aprobar=True)
        decidir_movimiento(movimiento=pago, usuario=self.usuario, aprobar=True)
        estado = estado_obligacion(self.obligacion)
        self.assertEqual((estado["obligacion_actual"], estado["registrado_neto"], estado["pendiente"]), (80, 80, 0))

    def test_api_estados_auditoria_y_resolucion(self):
        pendiente = self.registrar()
        respuesta = self.client.get("/api/movimientos-dinero/?estado=pendiente_aprobacion")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 1)
        self.assertFalse(respuesta.data["results"][0]["aprobado"])
        respuesta = self.client.post(f"/api/movimientos-dinero/{pendiente.pk}/aprobar/", {}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["registrado_neto"], "30.00")
        self.assertEqual(respuesta.data["movimientos"][0]["aprobado_por"], self.usuario.pk)
        self.assertEqual(self.client.get("/api/movimientos-dinero/?estado=incorrecto").status_code, 400)


@skipUnless(connection.vendor == "postgresql", "Las reservas concurrentes requieren PostgreSQL.")
class ReservasDineroConcurrenciaTests(DatosDinero, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def paralelo(self, primera, segunda):
        barrera = Barrier(2)

        def ejecutar(funcion):
            connections.close_all()
            try:
                barrera.wait(timeout=10)
                funcion()
                return "ok"
            except ValidationError:
                return "rechazado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(ejecutar, [primera, segunda]))

    def test_dos_reservas_simultaneas_no_superan_saldo(self):
        operacion = lambda: self.movimiento("70", aprobado=False)
        self.assertCountEqual(self.paralelo(operacion, operacion), ["ok", "rechazado"])
        self.assertEqual(estado_obligacion(self.obligacion)["por_aprobar"], 70)

    def test_aprobar_y_registrar_simultaneamente_respetan_reserva(self):
        pendiente = self.movimiento("30", aprobado=False)
        resultados = self.paralelo(lambda: decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True), lambda: self.movimiento("80"))
        self.assertCountEqual(resultados, ["ok", "rechazado"])
        self.assertEqual(estado_obligacion(self.obligacion)["registrado_neto"], 30)

    def test_rechazar_y_registrar_solo_consumen_capacidad_liberada(self):
        pendiente = self.movimiento("30", aprobado=False)
        self.paralelo(lambda: decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=False, motivo="No realizar"), lambda: self.movimiento("80"))
        estado = estado_obligacion(self.obligacion)
        self.assertEqual(estado["por_aprobar"], 0)
        self.assertIn(estado["registrado_neto"], (0, 80))
        self.assertGreaterEqual(estado["pendiente"], 0)

    def test_aprobar_y_rechazar_una_misma_operacion_tienen_un_solo_ganador(self):
        pendiente = self.movimiento("30", aprobado=False)
        resultados = self.paralelo(lambda: decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=True), lambda: decidir_movimiento(movimiento=pendiente, usuario=self.usuario, aprobar=False, motivo="No realizar"))
        self.assertCountEqual(resultados, ["ok", "rechazado"])
        pendiente.refresh_from_db()
        self.assertIn(pendiente.estado, ("aprobado", "rechazado"))
        self.assertEqual(MovimientoDinero.objects.count(), 1)
