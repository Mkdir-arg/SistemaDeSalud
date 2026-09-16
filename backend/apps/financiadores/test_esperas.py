"""Esperas programadas, salidas explícitas y vencimientos sin realización ficticia."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso, EventoCaso, Notificacion
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera, Prestacion
from apps.flujos.models import Conexion, Nodo, VersionFlujo
from apps.flujos.serializers import NodoSerializer, VersionFlujoSerializer
from apps.instituciones.models import Area
from . import autorizaciones as a, models as m
from .esperas import continuar, registrar_espera, validar_avance, vencer_autorizaciones
from .test_autorizaciones import AutorizacionSetup


class EsperaSetup(AutorizacionSetup):
    def setUp(self):
        super().setUp()
        self.caso.version.tipo_circuito = "programado"
        self.caso.version.save(update_fields=["tipo_circuito"])
        self.nodo.config = {"esperar_autorizacion": True}
        self.nodo.save(update_fields=["config"])
        self.supervisor = Usuario.objects.create_user("supervisor@espera.local", "x")
        membresia = Membresia.objects.create(usuario=self.supervisor, institucion=self.institucion, rol="jefe_area")
        membresia.areas.add(self.area)

    def aprobar(self, obj, **datos):
        return a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion(**datos))

    def estado_espera(self):
        self.caso.refresh_from_db()
        return self.caso.espera_autorizacion.get("estado")

    def vencer_plazo(self, obj):
        m.SolicitudAutorizacion.objects.filter(pk=obj.pk).update(plazo_respuesta=timezone.now() - timedelta(seconds=1))


class EsperasAutorizacionTests(EsperaSetup, APITestCase):
    def test_programado_solicita_y_aprueba_sin_realizar_ni_mover_nodo(self):
        paso = self.caso.paso_desde
        obj = self.solicitud()
        self.assertEqual(self.estado_espera(), "esperando")
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(self.caso, {}, autor=self.admin)
        self.aprobar(obj)
        self.assertEqual(self.estado_espera(), "liberada")
        self.assertEqual(self.caso.nodo_actual_id, self.nodo.pk)
        self.assertEqual(self.caso.paso_desde, paso)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        validar_avance(self.caso)

    def test_guardia_no_definido_y_urgente_original_no_esperan(self):
        for tipo, prioridad in (("guardia", "normal"), ("no_definido", "normal"), ("programado", "urgente")):
            self.caso.version.tipo_circuito = tipo
            self.caso.version.save(update_fields=["tipo_circuito"])
            self.caso.prioridad = prioridad
            self.caso.paso_desde = timezone.now()
            self.caso.espera_autorizacion = {}
            self.caso.save(update_fields=["prioridad", "paso_desde", "espera_autorizacion"])
            self.solicitud()
            self.assertIsNone(self.estado_espera())
            validar_avance(self.caso)

    def test_sin_solicitud_no_permite_saltar_requisito_programado(self):
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(self.caso, {"contenido": "No debe registrarse"}, autor=self.admin)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(m.SolicitudAutorizacion.objects.exists())

    def test_reserva_y_consumo_externo_tardio_no_saltan_autorizacion(self):
        reserva = self.reservar()
        self.externo(6)
        reserva.refresh_from_db()
        self.assertEqual(reserva.cubiertas, 1)
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(self.caso.espera_autorizacion, {})
        with self.assertRaises(ValidationError):
            validar_avance(self.caso)

    def test_datos_incompletos_del_programado_requieren_revision_no_aprobacion_implicita(self):
        self.seleccion.delete()
        with self.assertRaises(ValidationError):
            validar_avance(self.caso)
        self.caso.version.tipo_circuito = "guardia"
        self.caso.version.save(update_fields=["tipo_circuito"])
        validar_avance(self.caso)

    def test_observada_rechazada_y_vencida_conservan_espera(self):
        obj = self.solicitud()
        a.resolver(solicitud=obj, usuario=self.operador, revision=1, decision="observar", motivo="Falta respaldo", clave=uuid4())
        self.assertEqual(self.estado_espera(), "esperando")
        obj.refresh_from_db()
        a.resolver(solicitud=obj, usuario=self.operador, revision=2, decision="rechazar", motivo="No corresponde", clave=uuid4())
        self.assertEqual(self.estado_espera(), "esperando")
        nuevo = self.solicitud()
        self.vencer_plazo(nuevo)
        vencer_autorizaciones()
        self.assertEqual(self.estado_espera(), "esperando")
        self.assertEqual(self.caso.espera_autorizacion["solicitudes"], [nuevo.pk])

    def test_multiples_prestaciones_y_requisito_aun_no_solicitado(self):
        otra = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="OTRA", nombre="Otra")
        comun = m.PrestacionComun.objects.create(codigo="OTR", nombre="Otra", categoria="otras")
        m.VinculoPrestacion.objects.create(prestacion=otra, comun=comun)
        from apps.finanzas.cobros import registrar_politica_cobro
        registrar_politica_cobro(prestacion=otra, registrado_por=self.admin, cobrar=True, importe=100)
        self.nueva_regla(prestacion=comun, requiere_autorizacion=True)
        primera = self.solicitud()
        self.aprobar(primera)
        self.assertEqual(self.estado_espera(), "esperando")
        segunda = self.solicitud(prestacion=otra)
        self.aprobar(segunda)
        self.assertEqual(self.estado_espera(), "liberada")
        self.assertEqual(self.caso.espera_autorizacion["solicitudes"], [primera.pk, segunda.pk])

    def test_supervisor_continua_con_motivo_sin_aceptar_pago(self):
        self.solicitud()
        self.client.force_authenticate(self.usuario)
        url = f"/api/casos/{self.caso.pk}/continuar-autorizacion/"
        datos = {"intento": str(a.intento_actual(self.caso)), "motivo": "Evaluación del supervisor"}
        self.assertEqual(self.client.post(url, datos, format="json").status_code, 403)
        self.client.force_authenticate(self.supervisor)
        self.assertEqual(self.client.post(url, {**datos, "motivo": ""}, format="json").status_code, 400)
        respuesta = self.client.post(url, datos, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "supervisada")
        self.assertEqual(respuesta.data["usuario"], self.supervisor.pk)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertFalse(m.ReservaCobertura.objects.exists())
        self.caso.refresh_from_db()
        validar_avance(self.caso)

    def test_supervisor_otra_area_no_continua_y_contexto_viejo_se_rechaza(self):
        self.solicitud()
        miembro = Membresia.objects.get(usuario=self.supervisor)
        miembro.areas.set([Area.objects.create(institucion=self.institucion, nombre="Otra área")])
        self.client.force_authenticate(self.supervisor)
        url = f"/api/casos/{self.caso.pk}/continuar-autorizacion/"
        datos = {"intento": str(a.intento_actual(self.caso)), "motivo": "Revisión"}
        self.assertIn(self.client.post(url, datos, format="json").status_code, (403, 404))
        miembro.areas.set([self.area])
        self.assertEqual(self.client.post(url, {**datos, "intento": str(uuid4())}, format="json").status_code, 400)

    def test_subir_a_urgente_no_completa_ni_salta_salida_con_motivo(self):
        self.solicitud()
        self.assertEqual(self.estado_espera(), "esperando")
        self.caso.prioridad = "urgente"
        self.caso.save(update_fields=["prioridad"])
        with self.assertRaises(ValidationError):
            validar_avance(self.caso)
        resultado = continuar(caso=self.caso, usuario=self.usuario, intento=a.intento_actual(self.caso), motivo="La atención no admite demora")
        self.assertEqual(resultado["estado"], "urgencia")
        self.caso.refresh_from_db()
        validar_avance(self.caso)
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_respuesta_de_intento_viejo_no_libera_nueva_espera_mismo_nodo(self):
        vieja = self.solicitud()
        continuar(caso=self.caso, usuario=self.supervisor, intento=a.intento_actual(self.caso), motivo="Continuación supervisada")
        Conexion.objects.create(version=self.caso.version, origen=self.nodo, destino=self.nodo)
        motor.avanzar(self.caso, {"contenido": "Atención realizada", "firmada": False}, autor=self.admin)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.espera_autorizacion, {})
        nueva = self.solicitud()
        self.aprobar(vieja)
        self.assertEqual(self.estado_espera(), "esperando")
        self.assertEqual(self.caso.espera_autorizacion["solicitudes"], [nueva.pk])

    def test_no_toca_espera_por_estudio_ni_temporizador(self):
        self.caso.esperando = True
        self.caso.reactivar_en = timezone.now() + timedelta(hours=2)
        self.caso.save(update_fields=["esperando", "reactivar_en"])
        temporizador = self.caso.reactivar_en
        obj = self.solicitud()
        self.aprobar(obj)
        self.caso.refresh_from_db()
        self.assertTrue(self.caso.esperando)
        self.assertEqual(self.caso.reactivar_en, temporizador)

    def test_aprobacion_con_vigencia_futura_no_habilita_antes_de_tiempo(self):
        obj = self.solicitud()
        self.aprobar(obj, vigencia_desde=self.hoy+timedelta(days=1), vigencia_hasta=self.hoy+timedelta(days=5))
        self.assertEqual(self.estado_espera(), "esperando")
        with self.assertRaises(ValidationError):
            validar_avance(self.caso)
        manana = timezone.now() + timedelta(days=1)
        with patch("apps.financiadores.esperas.timezone.now", return_value=manana):
            validar_avance(self.caso)
        self.assertEqual(self.estado_espera(), "liberada")
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_vencer_aprobacion_previa_reabre_la_espera_si_no_se_realizo(self):
        obj = self.solicitud()
        self.aprobar(obj, vigencia_hasta=self.hoy)
        self.assertEqual(self.estado_espera(), "liberada")
        vencer_autorizaciones(ahora=timezone.now() + timedelta(days=1))
        self.assertEqual(self.estado_espera(), "esperando")
        with self.assertRaises(ValidationError):
            validar_avance(self.caso)
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_cancelar_anula_solicitudes_y_preserva_reservas_sin_confirmacion(self):
        obj = self.solicitud()
        reserva = self.reservar(acepta=True)
        motor.cancelar_caso(self.caso, autor=self.admin, motivo="Cancelación administrativa")
        obj.refresh_from_db()
        reserva.refresh_from_db()
        self.assertEqual(obj.estado, "anulada")
        self.assertEqual(reserva.estado, "reservada")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_cancelar_solo_libera_reservas_confirmadas_como_no_realizadas(self):
        self.solicitud()
        reserva = self.reservar()
        motor.cancelar_caso(self.caso, autor=self.admin, motivo="No se realizó la prestación", reservas_no_realizadas=[reserva.pk])
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "liberada")

    def test_cancelar_no_libera_reserva_que_tiene_realizacion_registrada(self):
        self.solicitud()
        reserva = self.reservar()
        self.atencion()
        with self.assertRaises(motor.ErrorMotor):
            motor.cancelar_caso(self.caso, autor=self.admin, motivo="Revisión administrativa", reservas_no_realizadas=[reserva.pk])
        self.caso.refresh_from_db()
        reserva.refresh_from_db()
        self.assertNotEqual(self.caso.estado, "cancelado")
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(m.SolicitudAutorizacion.objects.get().estado, "pendiente")

    def test_vencimiento_sin_sla_no_ocurre_y_modo_seco_no_muta(self):
        obj = self.solicitud()
        self.assertEqual(vencer_autorizaciones(ahora=timezone.now() + timedelta(days=365)), 0)
        self.vencer_plazo(obj)
        self.assertEqual(vencer_autorizaciones(seco=True), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "pendiente")
        salida = StringIO()
        call_command("correr_tiempos", seco=True, stdout=salida)
        self.assertIn("1 autorización(es)", salida.getvalue())
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "pendiente")

    def test_clock_idempotente_notifica_despues_commit_y_no_avanza(self):
        self.caso.asignado_a = self.usuario
        self.caso.save(update_fields=["asignado_a"])
        obj = self.solicitud()
        self.vencer_plazo(obj)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(vencer_autorizaciones(), 1)
            self.assertFalse(Notificacion.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(vencer_autorizaciones(), 0)
        self.assertEqual(Notificacion.objects.filter(usuario=self.usuario).count(), 1)
        self.assertEqual(m.EventoAutorizacion.objects.filter(solicitud=obj, accion="vencer").count(), 1)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertEqual(self.estado_espera(), "esperando")

    def test_fallo_notificacion_no_revierte_decision_y_aprobada_vencida_no_se_usa(self):
        obj = self.solicitud()
        self.aprobar(obj, vigencia_desde=self.hoy-timedelta(days=2), vigencia_hasta=self.hoy-timedelta(days=1))
        with self.assertLogs("apps.financiadores.esperas", level="WARNING"), patch("apps.financiadores.esperas.Notificacion.objects.bulk_create", side_effect=RuntimeError("Entrega fallida")), self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(vencer_autorizaciones(), 1)
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "vencida")
        self.assertEqual(self.estado_espera(), "esperando")
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_disenador_valida_modalidad_booleano_y_clona_clasificacion(self):
        self.client.force_authenticate(self.admin)
        version = self.caso.version
        for config in ({"esperar_autorizacion": "true"}, {"esperar_autorizacion": 1}):
            serializer = NodoSerializer(self.nodo, data={"config": config}, partial=True)
            self.assertFalse(serializer.is_valid())
        version.tipo_circuito = "guardia"
        version.save(update_fields=["tipo_circuito"])
        self.assertTrue(any(p["titulo"] == "Espera de autorización inválida" for p in motor.validar_version(version)))
        serializer = NodoSerializer(self.nodo, data={"config": {"esperar_autorizacion": True}}, partial=True)
        self.nodo.version = version
        self.assertFalse(serializer.is_valid())
        version.tipo_circuito, version.estado = "programado", "publicada"
        version.save(update_fields=["tipo_circuito", "estado"])
        serializer = VersionFlujoSerializer(version, data={"tipo_circuito": "guardia"}, partial=True)
        self.assertFalse(serializer.is_valid())
        respuesta = self.client.post(f"/api/versiones-flujo/{version.pk}/nueva-version/", {}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["tipo_circuito"], "programado")


@skipUnless(connection.vendor == "postgresql", "La exclusión concurrente requiere PostgreSQL")
class ConcurrenciaEsperasTests(EsperaSetup, TransactionTestCase):
    def test_clock_y_aprobacion_revalidan_bajo_el_mismo_bloqueo(self):
        obj = self.solicitud()
        ahora = timezone.now()
        m.SolicitudAutorizacion.objects.filter(pk=obj.pk).update(plazo_respuesta=ahora + timedelta(hours=1))
        barrera = Barrier(2)

        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                if accion == "clock":
                    return vencer_autorizaciones(ahora=ahora + timedelta(hours=2))
                try:
                    self.aprobar(m.SolicitudAutorizacion.objects.get(pk=obj.pk))
                    return "aprobada"
                except ValidationError:
                    return "resolucion_rechazada"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(ejecutar, ("clock", "aprobar")))
        obj.refresh_from_db()
        self.assertIn(obj.estado, ("aprobada", "vencida"), resultados)
        self.assertEqual(m.EventoAutorizacion.objects.filter(solicitud=obj, accion__in=["aprobar", "vencer"]).count(), 1)
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_dos_clocks_no_duplican_evento_terminal(self):
        obj = self.solicitud()
        self.vencer_plazo(obj)
        barrera = Barrier(2)

        def ejecutar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return vencer_autorizaciones()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(ejecutar, range(2)))
        self.assertEqual(sum(resultados), 1)
        self.assertEqual(m.EventoAutorizacion.objects.filter(solicitud=obj, accion="vencer").count(), 1)
