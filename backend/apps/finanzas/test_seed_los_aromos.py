"""Guardas y conciliación del escenario ficticio de Los Aromos, con fechas relativas."""
import json
from datetime import datetime
from io import StringIO
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import F
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.casos.models import Caso
from apps.instituciones.models import Institucion
from .models import Gasto, HechoAtencionCosteable, MovimientoDinero, ObligacionFinanciera, PendienteCosteo
from .models_cobros import PendienteCobro


def reloj(texto):
    return timezone.make_aware(datetime.fromisoformat(texto))


@skipUnless(connection.vendor == "postgresql", "La semilla requiere PostgreSQL aislado.")
class SeedLosAromosTests(TestCase):
    def ejecutar(self, ahora=None, **opciones):
        salida = StringIO()
        if ahora is None:
            call_command("seed_los_aromos", stdout=salida, **opciones)
        else:
            with patch("django.utils.timezone.now", return_value=reloj(ahora)):
                call_command("seed_los_aromos", stdout=salida, **opciones)
        return json.loads(salida.getvalue())

    @override_settings(ENTORNO="produccion")
    def test_en_produccion_no_escribe(self):
        with self.assertRaisesMessage(CommandError, "ENTORNO=produccion"):
            self.ejecutar()
        self.assertFalse(Institucion.objects.exists())
        self.assertFalse(Usuario.objects.exists())

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

    def test_convive_con_otros_datos_y_no_se_duplica(self):
        # No depende de que la base esté vacía: sólo de que Los Aromos no esté.
        otra = Institucion.objects.create(nombre="Datos que se conservan")
        Usuario.objects.create_user("existente@example.test", "sin-importancia")
        self.ejecutar()
        self.assertTrue(Institucion.objects.filter(pk=otra.pk).exists())
        modelos = (Usuario, Institucion, Caso, Gasto, ObligacionFinanciera, MovimientoDinero)
        antes = [m.objects.count() for m in modelos]
        with self.assertRaisesMessage(CommandError, "ya está cargado"):
            self.ejecutar()
        self.assertEqual([m.objects.count() for m in modelos], antes)

    def test_usuarios_con_la_clave_de_la_demo(self):
        with patch.dict("os.environ", {"DEMO_PASSWORD": "otra-clave-de-prueba"}):
            self.ejecutar()
        usuario = Usuario.objects.get(email="elena.rivas@losaromos.test")
        self.assertTrue(usuario.check_password("otra-clave-de-prueba"))

    def test_mismas_cifras_en_septiembre_que_antes_de_las_fechas_relativas(self):
        # Con el mes en curso en septiembre, la serie es exactamente la que se
        # documentó cuando el escenario tenía fechas fijas.
        resumen = self.ejecutar("2026-09-24T12:00")
        self.assertEqual(resumen["periodos"][0], "2025-10-01")
        self.assertEqual(resumen["cantidades"]["HechoAtencionCosteable"], 170)
        self.assertEqual(resumen["cantidades"]["Gasto"], 110)
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

    # El 1° temprano, a fin de mes y en marzo cruzando el año: el mes en curso
    # tiene lo mismo y nada queda en el futuro.
    def test_concilia_el_primer_dia_del_mes(self):
        self._conciliar("2026-10-01T09:00")

    def test_concilia_a_fin_de_mes(self):
        self._conciliar("2026-10-28T18:00")

    def test_concilia_cruzando_el_anio(self):
        self._conciliar("2027-03-01T00:30")

    def _conciliar(self, ahora):
        resumen = self.ejecutar(ahora)
        mes = resumen["mes_en_curso"]
        self.assertEqual(mes["periodo"], ahora[:8] + "01")
        self.assertEqual(mes["gasto_aprobado"], "750000.00")
        self.assertEqual(mes["gasto_por_aprobar"], "45000.00")
        self.assertEqual(mes["pago_aprobado"], "610000.00")
        self.assertEqual(mes["cobro_aprobado"], "155000.00")
        self.assertEqual(mes["reintegro_aprobado"], "5000.00")
        self.assertEqual(mes["atenciones"], 7)
        instante = reloj(ahora)
        self.assertFalse(Caso.objects.filter(creado__gt=instante).exists())
        self.assertFalse(HechoAtencionCosteable.objects.filter(ocurrida_en__gt=instante).exists())
        self.assertFalse(MovimientoDinero.objects.filter(fecha__gt=instante.date()).exists())
        self.assertFalse(PendienteCobro.objects.filter(politica__registrado__gt=F("hecho__ocurrida_en")).exists())
        self.assertEqual(PendienteCobro.objects.filter(obligacion__isnull=True).count(), 1)
        self.assertEqual(PendienteCosteo.objects.filter(resuelto=False, motivo="sin_valor").count(), 1)
