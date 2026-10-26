"""Retención técnica (#172): sesiones cerradas y contenido de correos terminales.

`purgar_datos` sigue en seco por defecto. Las sesiones revocadas o vencidas hace
más de 90 días se borran; de los correos terminales de hace más de 30 días se
vacía el contenido y se conserva la fila. Los plazos se configuran en settings.
"""
import uuid
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import BajaMembresia, CorreoInstitucionalOutbox, SesionInstitucional, Usuario
from apps.auditoria import retencion
from apps.auditoria.models import FalloAuditoria
from apps.farmacia.models import OperacionStock
from apps.instituciones.models import Institucion

Estado = CorreoInstitucionalOutbox.Estado
PAYLOAD = {"tipo": "recuperacion", "email": "titular@example.test"}


def hace(dias):
    return timezone.now() - timedelta(days=dias)


class RetencionTecnicaTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("retencion@example.test", "x")

    def correr(self, *args):
        salida = StringIO()
        call_command("purgar_datos", *args, stdout=salida)
        return salida.getvalue()

    def sesion(self, *, revocada=None, vence=None):
        return SesionInstitucional.objects.create(
            usuario=self.usuario, refresh_jti_hash="0" * 64,
            revocada_at=hace(revocada) if revocada is not None else None,
            refresh_vence=hace(vence) if vence is not None else timezone.now() + timedelta(days=7),
        )

    def correo(self, estado, terminado=None):
        return CorreoInstitucionalOutbox.objects.create(
            solicitud=dict(PAYLOAD), estado=estado, vence=hace(200), disponible_en=hace(200),
            terminado_en=hace(terminado) if terminado is not None else None,
        )

    def existe(self, sesion):
        return SesionInstitucional.objects.filter(pk=sesion.pk).exists()

    # --- Sesiones ------------------------------------------------------------ #

    def test_sesion_revocada_se_borra_a_los_91_dias_y_no_a_los_89(self):
        vieja, reciente = self.sesion(revocada=91), self.sesion(revocada=89)
        self.correr("--aplicar")
        self.assertFalse(self.existe(vieja))
        self.assertTrue(self.existe(reciente))

    def test_sesion_vencida_se_borra_a_los_91_dias_y_no_a_los_89(self):
        vieja, reciente = self.sesion(vence=91), self.sesion(vence=89)
        self.correr("--aplicar")
        self.assertFalse(self.existe(vieja))
        self.assertTrue(self.existe(reciente))

    def test_sesion_vigente_antigua_no_se_borra(self):
        vigente = self.sesion()
        SesionInstitucional.objects.filter(pk=vigente.pk).update(creada=hace(400))
        self.correr("--aplicar")
        self.assertTrue(self.existe(vigente))

    # --- Correos ------------------------------------------------------------- #

    def test_correo_terminal_vacia_contenido_a_los_31_dias_y_no_a_los_29(self):
        for estado in (Estado.ENVIADO, Estado.DESCARTADO, Estado.ERROR):
            with self.subTest(estado=estado):
                viejo, reciente = self.correo(estado, 31), self.correo(estado, 29)
                self.correr("--aplicar")
                viejo.refresh_from_db(); reciente.refresh_from_db()
                self.assertEqual(viejo.solicitud, {})
                self.assertEqual(viejo.estado, estado)
                self.assertEqual(reciente.solicitud, PAYLOAD)

    def test_correo_no_terminal_queda_intacto_aunque_sea_viejo(self):
        for estado in (Estado.PENDIENTE, Estado.PROCESANDO):
            with self.subTest(estado=estado):
                correo = self.correo(estado, terminado=200)
                self.correr("--aplicar")
                correo.refresh_from_db()
                self.assertEqual(correo.solicitud, PAYLOAD)

    def test_correo_vaciado_no_se_borra(self):
        correo = self.correo(Estado.ENVIADO, 31)
        self.correr("--aplicar")
        correo.refresh_from_db()
        self.assertEqual((correo.estado, correo.solicitud), (Estado.ENVIADO, {}))
        self.assertIsNotNone(correo.terminado_en)

    # --- En seco, plazos y lo que se conserva -------------------------------- #

    def test_en_seco_no_borra_ni_vacia(self):
        sesion, correo = self.sesion(revocada=91), self.correo(Estado.ENVIADO, 31)
        salida = self.correr()
        self.assertTrue(self.existe(sesion))
        correo.refresh_from_db()
        self.assertEqual(correo.solicitud, PAYLOAD)
        self.assertIn("sesiones cerradas", salida)
        self.assertIn("contenido de correos", salida)
        self.assertIn("no se borró nada", salida.lower())

    @override_settings(RETENCION_SESIONES_DIAS=10, RETENCION_CORREOS_DIAS=5)
    def test_plazos_configurables(self):
        sesion, correo = self.sesion(revocada=11), self.correo(Estado.ENVIADO, 6)
        self.correr("--aplicar")
        self.assertFalse(self.existe(sesion))
        correo.refresh_from_db()
        self.assertEqual(correo.solicitud, {})

    def test_plazos_por_defecto(self):
        plazos = {r["regla"]: r["dias"] for r in retencion.informe()}
        self.assertEqual(plazos["sesiones cerradas"], 90)
        self.assertEqual(plazos["contenido de correos"], 30)

    @override_settings(RETENCION_SESIONES_DIAS=0)
    def test_plazo_invalido_se_rechaza(self):
        with self.assertRaises(ValueError):
            retencion.reglas()

    def test_conserva_bajas_operaciones_de_stock_y_fallos_de_auditoria(self):
        inst = Institucion.objects.create(nombre="Hospital Retencion")
        baja = BajaMembresia.objects.create(usuario=self.usuario, institucion=inst)
        operacion = OperacionStock.objects.create(
            institucion=inst, clave=uuid.uuid4(), tipo="ingreso", solicitud={}, autor=self.usuario,
        )
        fallo = FalloAuditoria.objects.create(tipo="detalle", recurso="historia", error="OperationalError")
        BajaMembresia.objects.filter(pk=baja.pk).update(momento=hace(4000))
        OperacionStock.objects.filter(pk=operacion.pk).update(creado=hace(4000))
        FalloAuditoria.objects.filter(pk=fallo.pk).update(momento=hace(4000))
        self.correr("--aplicar")
        self.assertTrue(BajaMembresia.objects.filter(pk=baja.pk).exists())
        self.assertTrue(OperacionStock.objects.filter(pk=operacion.pk).exists())
        self.assertTrue(FalloAuditoria.objects.filter(pk=fallo.pk).exists())
