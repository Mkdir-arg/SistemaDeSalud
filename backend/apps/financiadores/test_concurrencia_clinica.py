"""La confirmación y la atención serializan el mismo caso en PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from unittest import skipUnless
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase

from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Nodo

from .clinica import confirmar_en_paso, contexto_actual, cotizar_en_paso
from .cobertura import cantidades_periodo, periodo
from .models import ReservaCobertura
from .test_cobertura import CoberturaSetup


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueos reales de PostgreSQL.")
class ConcurrenciaClinicaTests(CoberturaSetup, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.caso.refresh_from_db()
        self.caso.nodo_actual = self.nodo
        self.caso.estado = Caso.Estado.EN_EVALUACION
        self.caso.save()
        fin = Nodo.objects.create(version=self.nodo.version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.nodo.version, origen=self.nodo, destino=fin)

    def solicitud(self, **cambios):
        contexto = contexto_actual(self.caso)
        evaluacion = cotizar_en_paso(caso=self.caso, usuario=self.admin,
            contexto=contexto, prestacion=self.prestacion)
        return {"caso": self.caso, "usuario": self.admin, "contexto": contexto,
            "prestacion": self.prestacion, "firma": evaluacion["firma"], "clave": uuid4(),
            "acepta": True, **cambios}

    def mientras_otra_transaccion(self, primera, segunda):
        intento = Event()

        def ejecutar():
            close_old_connections()

            def observar(execute, sql, params, many, context):
                if "casos_caso" in sql and "FOR UPDATE" in sql:
                    intento.set()
                return execute(sql, params, many, context)

            try:
                with connection.execute_wrapper(observar):
                    try:
                        segunda()
                    except ValidationError:
                        return "rechazada"
                    return "confirmada"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                primera()
                futuro = pool.submit(ejecutar)
                self.assertTrue(intento.wait(timeout=10), "La segunda operación no intentó bloquear el caso")
                self.assertFalse(futuro.done(), "La segunda operación debe esperar el commit del caso")
            return futuro.result(timeout=15)

    def test_atencion_que_gana_el_bloqueo_rechaza_confirmacion_tardia_sin_reserva_huerfana(self):
        solicitud = self.solicitud()
        resultado = self.mientras_otra_transaccion(
            lambda: motor.avanzar(self.caso, autor=self.admin,
                datos={"titulo": "Consulta realizada", "contenido": "Atención registrada", "firmada": False}),
            lambda: confirmar_en_paso(**solicitud),
        )
        self.assertEqual(resultado, "rechazada")
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.CERRADO)
        self.assertFalse(ReservaCobertura.objects.filter(estado="reservada").exists())
        realizada = ReservaCobertura.objects.get(estado="realizada")
        self.assertIsNotNone(realizada.hecho_id)
        self.assertEqual(realizada.aceptacion, {})
        self.assertIsNone(realizada.distribucion.obligacion_paciente_id)

    def test_dos_renovaciones_de_la_misma_reserva_no_duplican_cupo_ni_aceptaciones(self):
        self.externo(5)
        original = confirmar_en_paso(**self.solicitud())
        solicitud = self.solicitud(no_realizada=True)
        segunda = {**solicitud, "clave": uuid4()}
        resultado = self.mientras_otra_transaccion(
            lambda: confirmar_en_paso(**solicitud),
            lambda: confirmar_en_paso(**segunda),
        )
        self.assertEqual(resultado, "rechazada")
        original.refresh_from_db()
        self.assertEqual(original.estado, "liberada")
        self.assertEqual(original.aceptacion["importe"], "20.00")
        self.assertEqual(ReservaCobertura.objects.count(), 2)
        vigente = ReservaCobertura.objects.get(estado="reservada")
        self.assertEqual(vigente.cubiertas, 1)
        self.assertEqual(vigente.aceptacion["importe"], "20.00")
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, *periodo(self.hoy, "anio")), 6)

    def test_confirmacion_que_gana_el_bloqueo_se_captura_al_avanzar_con_instancia_vieja(self):
        solicitud = self.solicitud()
        caso_viejo = Caso.objects.get(pk=self.caso.pk)

        def confirmar_y_actualizar():
            confirmar_en_paso(**solicitud)
            # El paso no cambia, pero una instancia leída antes del bloqueo no
            # debe sobrescribir una actualización concurrente al completar.
            Caso.objects.filter(pk=self.caso.pk).update(prioridad=Caso.Prioridad.ALTA)

        resultado = self.mientras_otra_transaccion(
            confirmar_y_actualizar,
            lambda: motor.avanzar(caso_viejo, autor=self.admin,
                datos={"titulo": "Consulta realizada", "contenido": "Atención registrada", "firmada": False}),
        )
        self.assertEqual(resultado, "confirmada")
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.CERRADO)
        self.assertEqual(self.caso.prioridad, Caso.Prioridad.ALTA)
        self.assertEqual(ReservaCobertura.objects.count(), 1)
        realizada = ReservaCobertura.objects.get(clave=solicitud["clave"])
        self.assertEqual(realizada.estado, "realizada")
        self.assertIsNotNone(realizada.hecho_id)
        self.assertEqual(realizada.aceptacion["importe"], "20.00")
        self.assertEqual(realizada.aceptacion["usuario"], self.admin.pk)
        self.assertEqual(realizada.distribucion.estado, "resuelta")
        self.assertEqual(realizada.distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertEqual(realizada.distribucion.obligacion_financiador.importe_original, Decimal("80"))
        self.assertFalse(ReservaCobertura.objects.filter(estado="reservada").exists())
