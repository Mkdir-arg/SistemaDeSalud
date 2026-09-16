"""Autorización, cupo y dinero: ninguna decisión reemplaza una prestación real."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.finanzas.cobros import capturar_cobros_atencion
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera
from . import autorizaciones as a, models as m
from .actividad import con_importes, fila_actividad
from .acceso import actividad_visible
from .cobertura import liberar, periodo, cantidades_periodo
from .cobros import completar_pendiente, resolver_saldo
from .test_autorizaciones import AutorizacionSetup
from .uso_autorizaciones import aplicar_resolucion


class UsoAutorizacionTests(AutorizacionSetup, TestCase):
    def aprobar(self, obj=None, **cambios):
        obj = obj or self.solicitud()
        return a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion(**cambios))

    def test_aprobacion_no_gasta_cupo_ni_crea_hecho_y_uso_tiene_traza_por_reserva(self):
        sol = self.aprobar()
        self.assertFalse(m.UsoAutorizacion.objects.exists())
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        reserva = self.reservar(acepta=True)
        uso = m.UsoAutorizacion.objects.get(reserva=reserva)
        self.assertEqual(uso.estado, "comprometido")
        self.assertEqual(a.cantidades_autorizacion(sol), {"comprometida": 1, "consumida": 0, "disponible": 2})
        hecho = self.atencion()
        uso.refresh_from_db()
        self.assertEqual((uso.estado, uso.hecho_id), ("consumido", hecho.pk))
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)
        inicio, fin = periodo(self.hoy, "anio")
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, inicio, fin), 1)
        capturar_cobros_atencion(hecho.pk)
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)

    def test_realizar_sin_aprobar_conserva_copago_aceptado_y_pendiente_del_pagador(self):
        sol = self.solicitud()
        reserva = self.reservar(acepta=True)
        hecho = self.atencion()
        distribucion = m.DistribucionCobro.objects.get(reserva=reserva)
        self.assertEqual(distribucion.estado, "autorizacion_pendiente")
        self.assertIsNone(distribucion.obligacion_financiador_id)
        self.assertEqual(distribucion.obligacion_paciente.importe_original, Decimal("20.00"))
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)
        fila = fila_actividad(con_importes(actividad_visible(self.financiador)).get(pk=reserva.pk))
        self.assertIsNone(fila["importe_asignado"])
        self.aprobar(sol)
        sol.refresh_from_db()
        for _ in range(2):
            aplicar_resolucion(sol, self.operador)
            capturar_cobros_atencion(hecho.pk)
        distribucion.refresh_from_db()
        self.assertEqual(distribucion.estado, "resuelta")
        self.assertEqual(distribucion.obligacion_financiador.importe_original, Decimal("80.00"))
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)

    def test_aprobar_tarde_sin_reserva_previa_usa_hecho_existente(self):
        sol = self.solicitud()
        hecho = self.atencion()
        reserva = m.ReservaCobertura.objects.get(hecho=hecho)
        self.assertEqual(reserva.distribucion.estado, "autorizacion_pendiente")
        self.aprobar(sol)
        self.assertEqual(HechoAtencionCosteable.objects.count(), 1)
        self.assertEqual(m.UsoAutorizacion.objects.get(reserva=reserva).hecho_id, hecho.pk)
        self.assertEqual(m.DistribucionCobro.objects.get(reserva=reserva).estado, "pendiente")

    def test_rechazo_conserva_importes_y_no_transfiere_deuda_al_paciente(self):
        sol = self.solicitud()
        reserva = self.reservar()
        self.atencion()
        reserva.refresh_from_db()
        a.resolver(solicitud=sol, usuario=self.operador, revision=1, decision="rechazar",
                   motivo="Documentación insuficiente", clave=uuid4())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        distribucion = m.DistribucionCobro.objects.get(reserva=reserva)
        self.assertEqual((distribucion.estado, distribucion.importe_financiador, distribucion.importe_paciente),
                         ("autorizacion_pendiente", Decimal("80.00"), Decimal("20.00")))
        with self.assertRaises(ValidationError):
            resolver_saldo(reserva=reserva, usuario=self.admin, parte="financiador", decision="paciente",
                           importe=Decimal("80"), motivo="Decisión", clave=uuid4())
        resolver_saldo(reserva=reserva, usuario=self.admin, parte="financiador", decision="asumir",
                       importe=Decimal("80"), motivo="El hospital asume esta prestación", clave=uuid4())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        distribucion.refresh_from_db()
        self.assertEqual(distribucion.estado, "pendiente")
        fila = fila_actividad(con_importes(actividad_visible(self.financiador)).get(pk=reserva.pk))
        self.assertEqual(fila["importe_asignado"], "0.00")

    def test_resolucion_explicita_previene_cargo_duplicado_por_aprobacion_posterior(self):
        sol = self.solicitud()
        reserva = self.reservar(acepta=True)
        self.atencion()
        reserva.refresh_from_db()
        resolver_saldo(reserva=reserva, usuario=self.admin, parte="financiador", decision="financiador",
                       importe=Decimal("80"), motivo="Acuerdo escrito", evidencia="Aceptación por esta prestación e importe", clave=uuid4())
        self.aprobar(sol)
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)
        fila = fila_actividad(con_importes(actividad_visible(self.financiador)).get(pk=reserva.pk))
        self.assertEqual(fila["importe_asignado"], "80.00")
        self.assertEqual(fila["importe_acuerdos"], "0.00")

    def test_liberar_requiere_no_realizada_y_restituye_solo_cantidad_autorizada(self):
        sol = self.aprobar(cantidad_aprobada=1)
        reserva = self.reservar()
        with self.assertRaises(ValidationError):
            liberar(reserva=reserva, usuario=self.admin, motivo="No se realizó", no_realizada=False)
        liberar(reserva=reserva, usuario=self.admin, motivo="Confirmado no realizada", no_realizada=True)
        self.assertEqual(a.cantidades_autorizacion(sol)["disponible"], 1)
        self.assertEqual(m.UsoAutorizacion.objects.get(reserva=reserva).estado, "liberado")

    def test_aprobacion_no_amplia_plan_ni_se_traslada_a_otro_convenio(self):
        self.aprobar()
        otro, prestacion = self.otro_hospital()
        ajena = self.evaluar(caso=otro, prestacion=prestacion)
        self.assertTrue(ajena["requiere_autorizacion"])
        self.assertIsNone(ajena["autorizacion"])
        self.externo(6)
        self.assertEqual(self.evaluar()["estado"], "no_cubierta")
        self.assertFalse(self.evaluar()["requiere_autorizacion"])

    def test_consumo_externo_tardio_preserva_cupo_comprometido_y_exige_autorizacion(self):
        sol = self.solicitud()
        reserva = self.reservar(acepta=True)
        self.externo(6)
        self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.cubiertas, 1)
        self.assertTrue(reserva.evaluacion["requiere_autorizacion"])
        self.assertEqual(reserva.distribucion.estado, "autorizacion_pendiente")
        self.aprobar(sol)
        self.assertEqual(m.DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador.importe_original, Decimal("80"))

    def test_vigencia_al_realizar_y_nuevo_arancel_no_reusan_aceptacion(self):
        sol = self.aprobar(vigencia_hasta=self.hoy)
        reserva = self.reservar(acepta=True)
        m.SolicitudAutorizacion.objects.filter(pk=sol.pk).update(vigencia_hasta=self.hoy-timedelta(days=1), vigencia_desde=self.hoy-timedelta(days=2))
        self.politica(importe=Decimal("200"))
        self.atencion()
        reserva.refresh_from_db()
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(reserva.aceptacion, {})
        self.assertEqual(reserva.distribucion.estado, "autorizacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_completar_arancel_con_consumo_tardio_conserva_exigencia_de_autorizacion(self):
        sol = self.solicitud()
        self.politica(importe=None)
        hecho = self.atencion()
        reserva = m.ReservaCobertura.objects.get(hecho=hecho)
        self.externo(6)
        distribucion = completar_pendiente(reserva=reserva, usuario=self.admin,
            motivo="Arancel de la prestación comprobado", arancel=Decimal("100"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.cubiertas, 1)
        self.assertTrue(reserva.evaluacion["requiere_autorizacion"])
        self.assertEqual(distribucion.estado, "autorizacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.aprobar(sol)
        self.assertEqual(m.DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador.importe_original, Decimal("80"))

    def test_completar_evaluacion_historica_registra_uso_aprobado(self):
        from .cobertura import seleccionar_afiliacion
        self.aprobar()
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
            declaracion="Credencial pendiente de revisar", motivo="Corrección al ingreso")
        hecho = self.atencion()
        reserva = m.ReservaCobertura.objects.get(hecho=hecho)
        self.assertEqual(reserva.distribucion.estado, "evaluacion_pendiente")
        distribucion = completar_pendiente(reserva=reserva, usuario=self.admin,
            motivo="Credencial de esta prestación comprobada", afiliado=self.afiliado)
        self.assertIsNotNone(distribucion.obligacion_financiador_id)
        uso = m.UsoAutorizacion.objects.get(reserva=reserva)
        self.assertEqual((uso.estado, uso.hecho_id), ("consumido", hecho.pk))

    def test_regla_nueva_sin_autorizacion_libera_compromiso_con_traza_del_hecho(self):
        sol = self.aprobar()
        reserva = self.reservar(acepta=True)
        self.nueva_regla(requiere_autorizacion=False)
        hecho = self.atencion()
        reserva.refresh_from_db()
        self.assertFalse(reserva.evaluacion["requiere_autorizacion"])
        uso = m.UsoAutorizacion.objects.get(reserva=reserva)
        self.assertEqual((uso.estado, uso.hecho_id), ("liberado", hecho.pk))
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(a.cantidades_autorizacion(sol)["disponible"], 3)

    def test_baja_y_convenio_cerrado_no_impiden_resolver_hecho_original(self):
        sol = self.solicitud()
        reserva = self.reservar(acepta=True)
        self.atencion()
        m.Afiliado.objects.filter(pk=self.afiliado.pk).update(finalizado_en=timezone.now())
        m.Convenio.objects.filter(pk=self.convenio.pk).update(estado="finalizado", cerrado_en=timezone.now())
        self.aprobar(sol)
        self.assertIsNotNone(m.DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador_id)
        self.assertEqual(m.Afiliado.objects.get(pk=self.afiliado.pk).finalizado_en is not None, True)


@skipUnless(connection.vendor == "postgresql", "La exclusión concurrente requiere PostgreSQL.")
class UsoAutorizacionConcurrenteTests(AutorizacionSetup, TransactionTestCase):
    def test_realizacion_y_liberacion_no_duplican_uso_ni_cargo(self):
        from django.db import transaction
        from apps.casos.models import Caso
        sol = self.solicitud(cantidad=1)
        a.resolver(solicitud=sol, usuario=self.operador, **self.aprobacion(cantidad_aprobada=1))
        reserva = self.reservar(acepta=True)
        barrera = Barrier(2)

        def ejecutar(accion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                try:
                    if accion == "liberar":
                        liberar(reserva=reserva, usuario=self.admin, motivo="No realizada al verificar", no_realizada=True)
                    else:
                        # El motor ya bloquea el caso antes de registrar el hecho.
                        with transaction.atomic():
                            Caso.objects.select_for_update().get(pk=self.caso.pk)
                            self.atencion()
                except ValidationError:
                    if accion != "liberar":
                        raise
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(ejecutar, ["liberar", "realizar"]))
        self.assertEqual(HechoAtencionCosteable.objects.count(), 1)
        self.assertEqual(m.UsoAutorizacion.objects.filter(solicitud=sol, estado="consumido").count(), 1)
        self.assertEqual(m.UsoAutorizacion.objects.filter(solicitud=sol, estado="comprometido").count(), 0)
        self.assertEqual(ObligacionFinanciera.objects.filter(contraparte_referencia=f"financiador:{self.financiador.pk}").count(), 1)

    def test_ultimo_uso_disputado_no_se_compromete_dos_veces(self):
        from apps.casos.models import Caso
        from .cobertura import cotizacion, reservar
        sol = self.solicitud(cantidad=1)
        a.resolver(solicitud=sol, usuario=self.operador, **self.aprobacion(cantidad_aprobada=1))
        otro = Caso.objects.create(institucion=self.institucion, version=self.caso.version,
                                   ciudadano=self.paciente, area_actual=self.area, nodo_actual=self.nodo)
        m.AfiliacionCaso.objects.create(caso=otro, afiliado=self.afiliado, plan=self.plan,
                                       estado="verificada", motivo="Nueva sesión", registrado_por=self.admin)
        barrera = Barrier(2)

        def ejecutar(caso_id):
            close_old_connections()
            try:
                caso = Caso.objects.get(pk=caso_id)
                datos = dict(caso=caso, prestacion=self.prestacion, fecha=self.hoy, cantidad=1)
                cotizada = cotizacion(**datos)
                barrera.wait(timeout=10)
                try:
                    return reservar(**datos, usuario=self.admin, clave=uuid4(), firma=cotizada["firma"]).pk
                except ValidationError:
                    return None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(ejecutar, [self.caso.pk, otro.pk]))
        self.assertEqual(m.UsoAutorizacion.objects.filter(solicitud=sol, estado="comprometido").count(), 1)
        self.assertEqual(a.cantidades_autorizacion(sol)["disponible"], 0)
