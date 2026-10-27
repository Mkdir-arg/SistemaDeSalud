"""Identidad e idempotencia OSTEL con conexiones PostgreSQL independientes."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.accounts.models import Usuario
from . import ostel_importacion
from .models import Afiliado, Financiador, Importacion, MembresiaFinanciador
from .ostel_synthetic import Lote, _persona, generar_xlsx


@skipUnless(connection.vendor == "postgresql", "El bloqueo de filas exige PostgreSQL.")
class OstelConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        self.financiador = Financiador.objects.create(
            nombre="Concurrencia OSTEL ficticia", tipo="obra_social",
        )
        self.usuario = Usuario.objects.create_user(
            "concurrencia-ostel@example.invalid", nombre="Operador ficticio",
        )
        MembresiaFinanciador.objects.create(
            financiador=self.financiador, usuario=self.usuario, rol="operador",
        )

    def preview(self, indice, cobertura_habilitada=True):
        contenido = generar_xlsx(Lote(
            "ficticio", (_persona(indice, NUMERO=f"PG-{indice}"),),
        ))
        return ostel_importacion.previsualizar(
            financiador=self.financiador, usuario=self.usuario,
            archivo=BytesIO(contenido), clave=uuid4(),
            cobertura_habilitada=cobertura_habilitada,
        )

    def confirmar_simultaneamente(self, lotes):
        barrera = Barrier(2)

        def confirmar(pk):
            close_old_connections()
            try:
                lote = Importacion.objects.get(pk=pk)
                usuario = Usuario.objects.get(pk=self.usuario.pk)
                barrera.wait(timeout=10)
                return ostel_importacion.aplicar(
                    importacion=lote, usuario=usuario,
                ).resumen
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as procesos:
            tareas = [procesos.submit(confirmar, lote.pk) for lote in lotes]
            return [tarea.result(timeout=30) for tarea in tareas]

    def test_dos_confirmaciones_del_mismo_lote_crean_una_persona(self):
        lote = self.preview(1)

        resultados = self.confirmar_simultaneamente([lote, lote])

        self.assertEqual([r["aplicada"] for r in resultados], [1, 1])
        self.assertEqual(Afiliado.objects.filter(financiador=self.financiador).count(), 1)

    def test_dos_lotes_misma_identidad_conservan_cobertura_del_primero(self):
        habilitada = self.preview(2, cobertura_habilitada=True)
        administrativa = self.preview(2, cobertura_habilitada=False)

        resultados = self.confirmar_simultaneamente([habilitada, administrativa])

        self.assertEqual(sum(r["aplicada"] for r in resultados), 1)
        self.assertEqual(sum(r["revision"] for r in resultados), 1)
        self.assertEqual(Afiliado.objects.filter(financiador=self.financiador).count(), 1)
        habilitada.refresh_from_db()
        administrativa.refresh_from_db()
        # Cualquiera puede adquirir primero el bloqueo; el otro requiere revisión.
        ganador = habilitada if habilitada.resumen["aplicada"] == 1 else administrativa
        afiliado = Afiliado.objects.get(financiador=self.financiador)
        self.assertEqual(
            afiliado.cobertura_habilitada, ganador.resumen["cobertura_habilitada"],
        )
