"""Convergencia de las dos ramas publicadas sin renombrar migraciones."""
from unittest import skipUnless

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from .models import Afiliado, BajaMembresiaFinanciador, Financiador


@skipUnless(connection.vendor == "postgresql", "Prueba DDL y restricciones PostgreSQL.")
class IntegracionMigraciones186Tests(TransactionTestCase):
    comun = ("financiadores", "0010_padron_expansion_compatible")
    administrativa = ("financiadores", "0013_administrativa_cobertura")
    membresia = ("financiadores", "0013_baja_membresia_financiador")
    integrada = ("financiadores", "0014_merge_cobertura_baja_membresia")

    def comprobar_desde(self, anterior):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        # Una sola hoja que desciende de la convergencia; migraciones posteriores
        # (por ejemplo 0015) no reabren la bifurcación.
        hojas = executor.loader.graph.leaf_nodes("financiadores")
        self.assertEqual(len(hojas), 1)
        self.assertIn(self.integrada, executor.loader.graph.forwards_plan(hojas[0]))
        try:
            executor.migrate([self.comun])
            executor = MigrationExecutor(connection)
            executor.migrate([anterior])
            historicos = executor.loader.project_state([anterior]).apps
            org = Financiador.objects.create(nombre="Migración ficticia", tipo="obra_social")
            usuario = Usuario.objects.create_user("migracion186@example.invalid", nombre="Ficticio")
            datos = {"financiador_id": org.pk, "numero": "000099", "documento": "99018599",
                     "nombre": "PERSONA FICTICIA", "desde": timezone.localdate()}
            if anterior == self.administrativa:
                datos.update(cobertura_habilitada=False, numero_interno="000007")
            previo = historicos.get_model("financiadores", "Afiliado").objects.create(**datos)
            if anterior == self.membresia:
                historicos.get_model("financiadores", "BajaMembresiaFinanciador").objects.create(
                    financiador_id=org.pk, usuario_id=usuario.pk)

            executor = MigrationExecutor(connection)
            executor.migrate(finales)
            executor.loader.check_consistent_history(connection)
            actual = Afiliado.objects.get(pk=previo.pk)
            self.assertEqual(actual.numero, "000099")
            self.assertEqual(actual.documento, "99018599")
            self.assertEqual(actual.cobertura_habilitada, anterior != self.administrativa)
            self.assertEqual(actual.numero_interno, "000007" if anterior == self.administrativa else "")
            self.assertEqual(BajaMembresiaFinanciador.objects.filter(
                financiador=org, usuario=usuario).exists(), anterior == self.membresia)
            # La rama de membresías sigue disponible, también viniendo de cobertura.
            if anterior != self.membresia:
                BajaMembresiaFinanciador.objects.create(financiador=org, usuario=usuario)
            actual.numero_interno = "000007"
            actual.save(update_fields=["numero_interno"])
            with self.assertRaises(IntegrityError), transaction.atomic():
                Afiliado.objects.create(financiador=org, numero="COMPARTIDO", numero_interno="000007",
                    documento="99018598", nombre="OTRA PERSONA FICTICIA", desde=timezone.localdate())
            self.assertEqual(MigrationExecutor(connection).migration_plan(finales), [])
        finally:
            # Restaurar el esquema para el flush y para las demás pruebas.
            MigrationExecutor(connection).migrate(finales)

    def test_desde_base_comun_conserva_afiliados_y_defaults(self):
        self.comprobar_desde(self.comun)

    def test_desde_cobertura_conserva_administrativos(self):
        self.comprobar_desde(self.administrativa)

    def test_desde_membresia_conserva_bajas(self):
        self.comprobar_desde(self.membresia)
