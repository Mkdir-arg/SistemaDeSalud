"""Guardas destructivas y conciliación del escenario ficticio de presentación."""
import json
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import F
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.casos.models import Caso
from apps.instituciones.models import Institucion
from .management.commands.seed_los_aromos import CONFIRMACION
from .models import Gasto, HechoAtencionCosteable, MovimientoDinero, ObligacionFinanciera, PendienteCosteo
from .models_cobros import PendienteCobro


@skipUnless(connection.vendor == "postgresql", "La semilla requiere PostgreSQL aislado.")
class SeedLosAromosTests(TestCase):
    def ejecutar(self, **opciones):
        salida = StringIO()
        parametros = {"confirmar": CONFIRMACION, "stdout": salida, **opciones}
        with patch.dict("os.environ", {"DEMO_LOS_AROMOS_PASSWORD": "clave-exclusiva-de-pruebas"}):
            call_command("seed_los_aromos", **parametros)
        return json.loads(salida.getvalue())

    def test_confirmacion_incorrecta_no_escribe(self):
        with self.assertRaisesMessage(CommandError, "Confirmación incorrecta"):
            self.ejecutar(confirmar="APLICAR")
        self.assertFalse(Institucion.objects.exists())
        self.assertFalse(Usuario.objects.exists())

    def test_sin_password_no_escribe(self):
        with patch.dict("os.environ", {"DEMO_LOS_AROMOS_PASSWORD": ""}):
            with self.assertRaisesMessage(CommandError, "DEMO_LOS_AROMOS_PASSWORD"):
                call_command("seed_los_aromos", confirmar=CONFIRMACION, stdout=StringIO())
        self.assertFalse(Institucion.objects.exists())

    def test_institucion_existente_no_se_mezcla_ni_borra(self):
        original = Institucion.objects.create(nombre="Datos que se conservan")
        with self.assertRaisesMessage(CommandError, "La base contiene datos"):
            self.ejecutar()
        self.assertEqual(Institucion.objects.get().pk, original.pk)
        self.assertFalse(Usuario.objects.exists())

    def test_usuario_existente_sin_institucion_tambien_bloquea(self):
        original = Usuario.objects.create_user("existente@example.test", "sin-importancia")
        with self.assertRaisesMessage(CommandError, "La base contiene datos"):
            self.ejecutar()
        self.assertEqual(Usuario.objects.get().pk, original.pk)
        self.assertFalse(Institucion.objects.exists())

    def test_no_sobrescribe_manifiesto(self):
        with patch("apps.finanzas.management.commands.seed_los_aromos.Path.exists", return_value=True):
            with self.assertRaisesMessage(CommandError, "archivo nuevo"):
                self.ejecutar(salida="/tmp/escenario-existente.json")
        self.assertFalse(Institucion.objects.exists())

    def test_error_intermedio_revierte_toda_la_carga(self):
        with patch("apps.finanzas.management.commands.seed_los_aromos.Command._historia", side_effect=CommandError("fallo de prueba")):
            with self.assertRaisesMessage(CommandError, "fallo de prueba"):
                self.ejecutar()
        self.assertFalse(Institucion.objects.exists())
        self.assertFalse(Usuario.objects.exists())
        self.assertFalse(Gasto.objects.exists())

    def test_escenario_concilia_con_cronologia_y_no_se_duplica(self):
        resumen = self.ejecutar()
        self.assertEqual(resumen["cantidades"]["HechoAtencionCosteable"], 170)
        self.assertEqual(resumen["cantidades"]["Gasto"], 110)
        self.assertEqual(resumen["septiembre"]["gasto_aprobado"], "750000.00")
        self.assertEqual(resumen["septiembre"]["pago_aprobado"], "610000.00")
        self.assertEqual(resumen["septiembre"]["cobro_aprobado"], "155000.00")
        self.assertEqual(resumen["septiembre"]["reintegro_aprobado"], "5000.00")
        # Estacionalidad y contratos del escenario, sin línea artificialmente
        # creciente ni cambios en los importes canónicos de presentación.
        esperados = (
            ("Clínica médica", "ELEC", "2026-01-01", "104000.00"),
            ("Clínica médica", "ELEC", "2026-03-01", "88000.00"),
            ("Clínica médica", "ELEC", "2026-07-01", "112000.00"),
            ("Clínica médica", "ELEC", "2026-08-01", "110000.00"),
            ("Clínica médica", "LIMP", "2025-11-01", "80000.00"),
            ("Clínica médica", "LIMP", "2026-01-01", "86400.00"),
            ("Clínica médica", "LIMP", "2026-04-01", "92800.00"),
            ("Cardiología", "MANT", "2025-11-01", "18750.00"),
            ("Cardiología", "MANT", "2026-03-01", "38750.00"),
            ("Cardiología", "MANT", "2026-04-01", "20000.00"),
        )
        for area, concepto, mes, importe in esperados:
            gasto = Gasto.objects.get(area__nombre=area, concepto__codigo=concepto, periodo_economico=mes)
            self.assertEqual(str(gasto.importe), importe)
        self.assertFalse(Usuario.objects.filter(is_superuser=True).exists())
        self.assertFalse(Caso.objects.filter(creado__gt=timezone.now()).exists())
        self.assertFalse(HechoAtencionCosteable.objects.filter(ocurrida_en__gt=timezone.now()).exists())
        self.assertFalse(PendienteCobro.objects.filter(politica__registrado__gt=F("hecho__ocurrida_en")).exists())
        self.assertEqual(PendienteCobro.objects.filter(obligacion__isnull=True).count(), 1)
        self.assertEqual(PendienteCosteo.objects.filter(resuelto=False, motivo="sin_valor").count(), 1)
        modelos = (Usuario, Institucion, Caso, Gasto, ObligacionFinanciera, MovimientoDinero)
        antes = [m.objects.count() for m in modelos]
        with self.assertRaisesMessage(CommandError, "La base contiene datos"):
            self.ejecutar()
        self.assertEqual([m.objects.count() for m in modelos], antes)
