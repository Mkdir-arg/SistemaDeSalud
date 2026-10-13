"""Escritores anteriores al padrón ampliado contra el esquema expandido."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.utils import timezone
from uuid import uuid4

from apps.accounts.models import Usuario
from . import models as m


class EscritoresLegadosPadronTests(TestCase):
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="Compatibilidad", tipo="obra_social")
        self.user = Usuario.objects.create_user("legacy131@test.local", "clave")
        self.a = m.Afiliado.objects.create(financiador=self.org, numero="001",
            documento="12345678", nombre="Legado", desde=timezone.localdate())
        # Renderizar los modelos reales previos a esta entrega: sus INSERT no
        # conocen las columnas nuevas. No cambia ni retrocede la base de tests.
        self.legacy = MigrationExecutor(connection).loader.project_state(
            [("financiadores", "0009_registrofactura")]
        ).apps

    def test_alta_legada_recibe_defaults_no_obligatorios(self):
        model = self.legacy.get_model("financiadores", "Afiliado")
        anterior = model.objects.create(financiador_id=self.org.pk, numero="002",
            documento="22333444", nombre="Alta anterior", desde=timezone.localdate())
        actual = m.Afiliado.objects.get(pk=anterior.pk)
        self.assertEqual((actual.revision, actual.cuil, actual.estado_tramite), (1, "", "pendiente"))

    def test_plan_legado_no_inventa_tipo(self):
        model = self.legacy.get_model("financiadores", "Plan")
        anterior = model.objects.create(financiador_id=self.org.pk, codigo="ANT", nombre="Anterior")
        self.assertEqual(m.Plan.objects.get(pk=anterior.pk).tipo, "")

    def test_membresia_legada_no_recibe_permisos_protegidos(self):
        model = self.legacy.get_model("financiadores", "MembresiaFinanciador")
        anterior = model.objects.create(financiador_id=self.org.pk, usuario_id=self.user.pk, rol="admin")
        actual = m.MembresiaFinanciador.objects.get(pk=anterior.pk)
        self.assertFalse(actual.acceso_padron_salud)
        self.assertFalse(actual.acceso_padron_cobranza)

    def test_historial_legado_conserva_valores_y_origen(self):
        model = self.legacy.get_model("financiadores", "HistorialAfiliacion")
        anterior = model.objects.create(afiliado_id=self.a.pk, numero=self.a.numero,
            desde=self.a.desde, registrado_por_id=self.user.pk)
        actual = m.HistorialAfiliacion.objects.get(pk=anterior.pk)
        self.assertEqual((actual.cambios, actual.origen), ({}, "manual"))

    def test_lote_legado_sigue_siendo_version_uno(self):
        model = self.legacy.get_model("financiadores", "Importacion")
        anterior = model.objects.create(financiador_id=self.org.pk, creado_por_id=self.user.pk,
            tipo="padron", clave=uuid4())
        self.assertEqual(m.Importacion.objects.get(pk=anterior.pk).version, 1)
