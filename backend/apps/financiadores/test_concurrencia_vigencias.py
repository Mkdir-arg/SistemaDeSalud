"""Cierres concurrentes con operaciones que ya habían leído la vigencia anterior."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase

from .cobertura import cotizacion, reservar
from .models import ReservaCobertura
from .services import registrar_afiliado
from .test_cobertura import CoberturaSetup
from .vigencias import cerrar_convenio, finalizar_afiliacion


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueos reales de PostgreSQL.")
class ConcurrenciaVigenciasTests(CoberturaSetup, TransactionTestCase):
    def mientras_cierra(self, cierre, operacion, tabla):
        intento = Event()

        def ejecutar():
            close_old_connections()

            def observar(execute, sql, params, many, context):
                if tabla in sql and "FOR UPDATE" in sql:
                    intento.set()
                return execute(sql, params, many, context)

            try:
                with connection.execute_wrapper(observar):
                    try:
                        operacion()
                    except ValidationError:
                        return "rechazada"
                    return "confirmada"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                cierre()
                futuro = pool.submit(ejecutar)
                self.assertTrue(intento.wait(timeout=10), "La operación no llegó al bloqueo esperado")
                self.assertFalse(futuro.done(), "La operación debe esperar la confirmación del cierre")
            return futuro.result(timeout=15)

    def test_cerrar_convenio_invalida_cotizacion_antes_de_confirmar_reserva(self):
        presentada = cotizacion(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        resultado = self.mientras_cierra(
            lambda: cerrar_convenio(usuario=self.admin, convenio=self.convenio, origen="hospital", motivo="Fin del acuerdo"),
            lambda: reservar(caso=self.caso, prestacion=self.prestacion, usuario=self.admin,
                             fecha=self.hoy, cantidad=1, clave=uuid4(), firma=presentada["firma"], acepta=True),
            "financiadores_convenio",
        )
        self.assertEqual(resultado, "rechazada")
        self.assertFalse(ReservaCobertura.objects.exists())

    def test_importacion_que_espera_una_baja_no_reactiva_afiliacion(self):
        resultado = self.mientras_cierra(
            lambda: finalizar_afiliacion(usuario=self.operador, afiliado=self.afiliado, motivo="Cambio de financiador"),
            lambda: registrar_afiliado(financiador=self.financiador, usuario=self.operador,
                                      numero="NUEVO", documento=self.afiliado.documento,
                                      nombre=self.afiliado.nombre, plan=self.plan, desde=self.hoy),
            "financiadores_afiliado",
        )
        self.assertEqual(resultado, "rechazada")
        self.afiliado.refresh_from_db()
        self.assertIsNotNone(self.afiliado.finalizado_en)
        self.assertEqual(self.afiliado.numero, "00001")
