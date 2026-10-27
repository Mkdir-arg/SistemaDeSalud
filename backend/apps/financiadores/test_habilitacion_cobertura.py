"""Separación administrativa: no concede cobertura y conserva compromisos previos."""
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.finanzas.models import ObligacionFinanciera
from apps.finanzas.cobros import capturar_cobros_atencion
from .administrativa import resumenes_administrativos
from .autorizaciones import solicitar_manual
from .cobertura import seleccionar_afiliacion
from .models import Afiliado, DistribucionCobro
from .test_cobertura import CoberturaSetup


class HabilitacionCoberturaTests(CoberturaSetup, TestCase):
    def deshabilitar(self):
        self.afiliado.cobertura_habilitada = False
        self.afiliado.save(update_fields=["cobertura_habilitada"])

    def test_default_preserva_alta_con_cobertura(self):
        self.assertTrue(self.afiliado.cobertura_habilitada)
        self.assertEqual(self.evaluar()["cubiertas"], 1)

    def test_solo_administrativo_rechaza_nueva_seleccion_y_cotizacion(self):
        self.deshabilitar()
        with self.assertRaisesMessage(ValidationError, "administrativo"):
            seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                                   afiliado=self.afiliado, motivo="Nueva selección")
        with self.assertRaisesMessage(ValidationError, "administrativo"):
            self.evaluar()
        with self.assertRaisesMessage(ValidationError, "administrativo"):
            self.reservar()

    def test_admision_no_permite_seleccionar_registro_administrativo(self):
        self.deshabilitar()
        resumen = resumenes_administrativos([self.paciente])[self.paciente.pk]
        self.assertFalse(any(a["seleccionable"] for a in resumen["afiliaciones"]))

    def test_atencion_sin_reserva_queda_pendiente_sin_deuda(self):
        self.deshabilitar()
        hecho = self.atencion()
        self.assertFalse(hecho.cobertura_contexto["cobertura_habilitada"])
        distribucion = DistribucionCobro.objects.get()
        self.assertEqual(distribucion.estado, "evaluacion_pendiente")
        self.assertEqual(distribucion.reserva.cubiertas, 0)
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_reserva_previa_conserva_compromiso_al_registrar_atencion(self):
        reserva = self.reservar(acepta=True)
        self.deshabilitar()
        self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.cubiertas, 1)
        self.assertIsNotNone(reserva.distribucion.obligacion_financiador_id)

    def test_recuperacion_no_concede_cobertura_por_habilitacion_posterior(self):
        self.deshabilitar()
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.afiliado.cobertura_habilitada = True
        self.afiliado.save(update_fields=["cobertura_habilitada"])
        capturar_cobros_atencion(hecho.pk)
        self.assertEqual(DistribucionCobro.objects.get().estado, "evaluacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_recuperacion_conserva_habilitacion_al_momento_del_hecho(self):
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.deshabilitar()
        capturar_cobros_atencion(hecho.pk)
        self.assertIsNotNone(DistribucionCobro.objects.get().obligacion_financiador_id)

    def test_autorizacion_manual_no_admite_solo_administrativo(self):
        self.deshabilitar()
        with self.assertRaisesMessage(ValidationError, "no está vigente"):
            solicitar_manual(financiador_id=self.financiador.pk, afiliado=self.afiliado,
                institucion=self.institucion, comun=self.comun, usuario=self.operador,
                cantidad=1, justificacion="Solicitud administrativa", clave=uuid4())

    def test_numero_interno_unico_no_vacio_por_financiador(self):
        self.afiliado.numero_interno = "OSTEL-1"
        self.afiliado.save(update_fields=["numero_interno"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Afiliado.objects.create(financiador=self.financiador, numero="Compartido",
                numero_interno="OSTEL-1", documento="999", nombre="Otra persona", desde=self.hoy)
        for documento in ("888", "777"):
            Afiliado.objects.create(financiador=self.financiador, numero="Compartido",
                documento=documento, nombre="Sin número interno", desde=self.hoy)
