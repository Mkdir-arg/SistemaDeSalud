"""La migración aditiva conserva versiones históricas sin asignarles un plazo."""
from datetime import date
from unittest import skipUnless
from django.db import connection, transaction, IntegrityError
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from apps.accounts.models import Usuario
from .models import Financiador, BorradorReglaDerechos
from .derechos_borrador import MAX_DIAS_CORRIDOS


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL ficticio dedicado.")
class MigracionPlazoTests(TransactionTestCase):
    def test_version_previa_permanece_sin_plazo_y_conserva_todos_sus_datos(self):
        org = Financiador.objects.create(nombre="Migración ficticia", tipo="otro")
        user = Usuario.objects.create_user("migracion-plazo@example.invalid")
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes("financiadores")
        previo = [("financiadores", "0018_borradorregladerechos")]
        executor.migrate(previo)
        try:
            apps = executor.loader.project_state(previo).apps
            anterior = apps.get_model("financiadores", "BorradorReglaDerechos")
            fila = anterior.objects.create(financiador_id=org.pk, codigo="ficticia", version=1,
                regimen="dependencia", fuente="Fuente histórica ficticia", desde=date(2029, 1, 1),
                creado_por_id=user.pk, motivo="Registro previo ficticio")
            antes = anterior.objects.values().get(pk=fila.pk)
            MigrationExecutor(connection).migrate(finales)
            despues = BorradorReglaDerechos.objects.values().get(pk=fila.pk)
            self.assertIsNone(despues.pop("plazo_dias_corridos"))
            self.assertEqual(despues, antes)
            datos = {k: v for k, v in antes.items() if k not in ("id", "creado")}
            datos["version"] = 2
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    BorradorReglaDerechos.objects.create(**datos, plazo_dias_corridos=MAX_DIAS_CORRIDOS + 1)
            nueva = BorradorReglaDerechos.objects.create(**datos, plazo_dias_corridos=0)
            self.assertEqual(nueva.plazo_dias_corridos, 0)
            self.assertIsNone(BorradorReglaDerechos.objects.get(pk=fila.pk).plazo_dias_corridos)
        finally:
            MigrationExecutor(connection).migrate(finales)
