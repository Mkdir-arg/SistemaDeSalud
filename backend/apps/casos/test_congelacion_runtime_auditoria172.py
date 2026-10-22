"""AUD-012: avanzar no toma locks cruzados sobre definiciones indelebles."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import MagicMock, patch

from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import Usuario

from apps.formularios.models import Campo, Formulario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Institucion
from . import motor
from .models import Caso, ValorCampo


@skipUnless(connection.vendor == "postgresql", "El cruce requiere dos conexiones PostgreSQL reales")
@override_settings(INTEGRACIONES_PERMITIDAS=["integracion.example.test"])
class CongelacionRuntimeAuditoria172Tests(TransactionTestCase):
    def setUp(self):
        institucion = Institucion.objects.create(nombre="Institución sintética runtime")
        flujo = Flujo.objects.create(institucion=institucion, titulo="Flujo cruzado sintético")
        self.version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.forms = [Formulario.objects.create(institucion=institucion, titulo=nombre) for nombre in ("A", "B")]
        self.campos = [Campo.objects.create(formulario=form, label="Respuesta", tipo="texto_corto") for form in self.forms]
        self.nodos = [Nodo.objects.create(version=self.version, tipo="form", formulario=form, titulo=form.titulo) for form in self.forms]
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        for indice, nodo in enumerate(self.nodos):
            integracion = Nodo.objects.create(version=self.version, tipo="integracion", titulo="Consulta sintética",
                config={"url": "https://integracion.example.test/resultado", "guardar_en": self.campos[1-indice].pk,
                        "ruta": "resultado"})
            Conexion.objects.create(version=self.version, origen=nodo, destino=integracion)
            Conexion.objects.create(version=self.version, origen=integracion, destino=fin)
        inicio = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        Conexion.objects.create(version=self.version, origen=inicio, destino=self.nodos[0])
        actor = Usuario.objects.create_superuser("runtime-publicador@example.test", "x")
        cliente = APIClient()
        cliente.force_authenticate(actor)
        publicada = cliente.post(f"/api/versiones-flujo/{self.version.pk}/publicar/", {}, format="json")
        self.assertEqual(publicada.status_code, 200, publicada.data)
        self.assertEqual(Formulario.objects.filter(pk__in=[f.pk for f in self.forms], congelado_at__isnull=False).count(), 2)
        self.version.refresh_from_db()
        self.casos = [Caso.objects.create(institucion=institucion, version=self.version, nodo_actual=nodo) for nodo in self.nodos]

    def test_dos_casos_formularios_e_integraciones_cruzadas_sin_deadlock(self):
        ambos_guardados = Barrier(2, timeout=5)
        guardar_original = motor._guardar_valores

        def guardar(*args, **kwargs):
            resultado = guardar_original(*args, **kwargs)
            # Sólo sincronización después del servicio REAL: ambos casos ya
            # guardaron su respuesta y todavía no entraron en la integración.
            ambos_guardados.wait()
            return resultado

        def avanzar(indice):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                caso = Caso.objects.get(pk=self.casos[indice].pk)
                motor.avanzar(caso, {"valores": {str(self.campos[indice].pk): "Respuesta sintética"}})
                return None
            except Exception as error:
                causa = error.__cause__
                return type(error).__name__, getattr(causa, "sqlstate", None) or getattr(causa, "pgcode", None)
            finally:
                connections.close_all()

        respuesta = MagicMock()
        respuesta.__enter__.return_value.read.return_value = b'{"resultado":"Resultado sintetico"}'
        with patch.object(motor, "_guardar_valores", side_effect=guardar), patch.object(motor, "urlopen", return_value=respuesta):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futuros = [pool.submit(avanzar, indice) for indice in (0, 1)]
                errores = [futuro.result(timeout=12) for futuro in futuros]
        self.assertEqual(errores, [None, None])
        for caso in self.casos:
            caso.refresh_from_db()
            self.assertEqual(caso.estado, Caso.Estado.CERRADO)
            self.assertEqual(ValorCampo.objects.filter(caso=caso).count(), 2)
        self.assertEqual(respuesta.__enter__.call_count, 2)

    def test_marca_durable_fresh_evade_locks_runtime_y_mantiene_guard_fuerte(self):
        from apps.formularios.integridad import asegurar_congelados, congelar_formularios

        ids = [form.pk for form in self.forms]
        with CaptureQueriesContext(connection) as consultas:
            with transaction.atomic():
                asegurar_congelados(ids)
        self.assertFalse(any("FOR UPDATE" in consulta["sql"] for consulta in consultas))
        with CaptureQueriesContext(connection) as consultas:
            with transaction.atomic():
                congelar_formularios(ids)
        self.assertTrue(any("FOR UPDATE" in consulta["sql"] for consulta in consultas))

    def test_preparacion_null_congela_conjunto_y_es_idempotente(self):
        from apps.formularios.integridad import asegurar_congelados

        nuevos = [Formulario.objects.create(institucion=self.forms[0].institucion, titulo=titulo)
                  for titulo in ("Pendiente uno", "Pendiente dos")]
        with transaction.atomic():
            asegurar_congelados([form.pk for form in reversed(nuevos)])
        marcas = list(Formulario.objects.filter(pk__in=[f.pk for f in nuevos]).order_by("pk").values_list("congelado_at", flat=True))
        self.assertTrue(all(marcas))
        with transaction.atomic():
            asegurar_congelados([form.pk for form in nuevos])
        self.assertEqual(list(Formulario.objects.filter(pk__in=[f.pk for f in nuevos]).order_by("pk").values_list("congelado_at", flat=True)), marcas)

    def test_preparacion_missing_no_congela_parcialmente(self):
        from rest_framework.exceptions import NotFound
        from apps.formularios.integridad import asegurar_congelados

        nuevo = Formulario.objects.create(institucion=self.forms[0].institucion, titulo="No congelar parcialmente")
        with self.assertRaises(NotFound):
            with transaction.atomic():
                asegurar_congelados([nuevo.pk, nuevo.pk + 100000])
        nuevo.refresh_from_db()
        self.assertIsNone(nuevo.congelado_at)

    def test_ensayo_borrador_revierte_marca_y_respuestas(self):
        version = VersionFlujo.objects.create(flujo=self.version.flujo, numero=2)
        formulario = Formulario.objects.create(institucion=self.forms[0].institucion, titulo="Ensayo sin persistencia")
        campo = Campo.objects.create(formulario=formulario, label="Dato de ensayo", tipo="texto_corto")
        inicio = Nodo.objects.create(version=version, tipo="inicio", titulo="Inicio")
        formulario_nodo = Nodo.objects.create(version=version, tipo="form", titulo="Formulario", formulario=formulario)
        fin = Nodo.objects.create(version=version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=version, origen=inicio, destino=formulario_nodo)
        Conexion.objects.create(version=version, origen=formulario_nodo, destino=fin)
        resultado = motor.ensayar(version, pasos=[{"valores": {str(campo.pk): "Respuesta de ensayo"}}])
        self.assertIsNone(resultado["error"])
        self.assertTrue(resultado["termino"])
        formulario.refresh_from_db()
        self.assertIsNone(formulario.congelado_at)
        self.assertFalse(Caso.objects.filter(version=version).exists())
        self.assertFalse(ValorCampo.objects.filter(campo=campo).exists())
