"""La migración 0003 pasa las cuentas de referencia al dominio nuevo y sólo a ellas."""
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from apps.accounts.models import Usuario

migracion = import_module("apps.simulacion.migrations.0003_dominio_referencia_plexo")


class MigracionDominioReferenciaTests(TestCase):
    def test_cambia_el_dominio_de_las_cuentas_de_referencia_y_vuelve_atras(self):
        ref = Usuario.objects.create_user("medico.i3@referencia.hen.invalid", None)
        otra = Usuario.objects.create_user("persona@hen.invalid.ejemplo.org", "x")

        migracion.cambiar(migracion.ANTERIOR, migracion.NUEVO)(apps, None)
        ref.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(ref.email, "medico.i3@referencia.plexo.invalid")
        self.assertEqual(otra.email, "persona@hen.invalid.ejemplo.org")

        migracion.cambiar(migracion.NUEVO, migracion.ANTERIOR)(apps, None)
        ref.refresh_from_db()
        self.assertEqual(ref.email, "medico.i3@referencia.hen.invalid")
