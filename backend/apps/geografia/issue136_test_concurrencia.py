"""Requiere PostgreSQL exclusivo autorizado. Sin red externa ni datos reales."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.instituciones.models import Institucion
from .contrato import validar_catalogo
from .issue136_test_puros import catalogo_ficticio
from .models import Catalogo, Lugar
from .servicios import ambito, resolver
from .sincronizacion import sincronizar


@skipUnless(connection.vendor == "postgresql", "Este contrato de concurrencia requiere PostgreSQL.")
class ConcurrenciaGeografiaTest(TransactionTestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Institución concurrente ficticia")
        sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()))

    def test_dos_cargas_del_mismo_manual_generan_un_solo_lugar(self):
        barrera = Barrier(2)
        def cargar(_):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return resolver({"localidad": {"manual": "Localidad simultánea ficticia"}}, dueno=ambito(institucion_id=self.inst.pk)).localidad_id
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(cargar, range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(Lugar.objects.filter(origen="manual").count(), 1)

    def test_sincronizaciones_superpuestas_publican_una_sola_version(self):
        barrera = Barrier(2)
        anterior = Catalogo.objects.get(pk=1).version
        def descargar():
            barrera.wait(timeout=10)
            return validar_catalogo(catalogo_ficticio())
        def cargar(_):
            close_old_connections()
            try:
                return sincronizar(descargar_fn=descargar)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(cargar, range(2)))
        self.assertEqual(sum(r["publicado"] for r in resultados), 1)
        self.assertEqual(Catalogo.objects.get(pk=1).version, anterior + 1)
