"""AUD-011: un escritor ya validado no puede cambiar el grafo publicado."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion

from .models import Conexion, Flujo, Nodo, VersionFlujo
from .views import ConexionViewSet, NodoViewSet, VersionFlujoViewSet


@skipUnless(connection.vendor == "postgresql", "Requiere conexiones y locks PostgreSQL")
class PublicacionConcurrenteAuditoria172Tests(TransactionTestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_superuser("publicacion172@test.local", "x")
        institucion = Institucion.objects.create(nombre="Hospital sintético")
        self.flujo = Flujo.objects.create(institucion=institucion, titulo="Grafo sintético")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.inicio = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        self.fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        self.conexion = Conexion.objects.create(
            version=self.version, origen=self.inicio, destino=self.fin,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)

    def _grafo(self):
        return (
            list(Nodo.objects.filter(version=self.version).order_by("pk").values()),
            list(Conexion.objects.filter(version=self.version).order_by("pk").values()),
        )

    def _publicar_antes_de_escritura_validada(self, viewset, metodo, url, datos=None, esperado=409):
        validado = Barrier(2, timeout=10)
        publicado = Barrier(2, timeout=10)
        nombre_hook = {"post": "perform_create", "patch": "perform_update", "delete": "perform_destroy"}[metodo]
        original = getattr(viewset, nombre_hook)

        def pausar_escritor(view, objeto):
            # get_object/is_valid ya leyeron BORRADOR en la conexión escritora.
            validado.wait()
            publicado.wait()
            return original(view, objeto)

        def escribir():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.usuario.pk))
                funcion = getattr(cliente, metodo)
                respuesta = funcion(url, datos or {}, format="json")
                return respuesta.status_code, getattr(respuesta, "data", None)
            finally:
                connections.close_all()

        antes = self._grafo()
        with patch.object(viewset, nombre_hook, pausar_escritor):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(escribir)
                try:
                    validado.wait()
                    respuesta = self.client.post(
                        f"/api/versiones-flujo/{self.version.pk}/publicar/", {}, format="json",
                    )
                    self.assertEqual(respuesta.status_code, 200, respuesta.data)
                    self.version.refresh_from_db()
                    self.assertEqual(self.version.estado, VersionFlujo.Estado.PUBLICADA)
                    publicado.wait()
                    codigo, detalle = futuro.result(timeout=12)
                finally:
                    validado.abort()
                    publicado.abort()
        self.assertEqual(codigo, esperado, detalle)
        self.version.refresh_from_db()
        self.assertEqual(self.version.estado, VersionFlujo.Estado.PUBLICADA)
        self.assertEqual(self._grafo(), antes)

    def test_publicar_contra_crear_nodo(self):
        self._publicar_antes_de_escritura_validada(
            NodoViewSet, "post", "/api/nodos/",
            {"version": self.version.pk, "tipo": "fin", "titulo": "Otro fin"},
        )

    def test_publicar_contra_editar_nodo(self):
        self._publicar_antes_de_escritura_validada(
            NodoViewSet, "patch", f"/api/nodos/{self.inicio.pk}/", {"titulo": "Cambio tardío"},
        )

    def test_publicar_contra_borrar_nodo(self):
        self._publicar_antes_de_escritura_validada(
            NodoViewSet, "delete", f"/api/nodos/{self.inicio.pk}/",
        )

    def test_publicar_contra_crear_conexion(self):
        self._publicar_antes_de_escritura_validada(
            ConexionViewSet, "post", "/api/conexiones/",
            {"version": self.version.pk, "origen": self.inicio.pk, "destino": self.fin.pk},
        )

    def test_publicar_contra_editar_conexion(self):
        self._publicar_antes_de_escritura_validada(
            ConexionViewSet, "patch", f"/api/conexiones/{self.conexion.pk}/", {"etiqueta": "Cambio tardío"},
        )

    def test_publicar_contra_borrar_conexion(self):
        self._publicar_antes_de_escritura_validada(
            ConexionViewSet, "delete", f"/api/conexiones/{self.conexion.pk}/",
        )

    def test_nota_validada_antes_de_publicar_no_revierte_estado(self):
        clasificacion_original = self.version.tipo_circuito
        self._publicar_antes_de_escritura_validada(
            VersionFlujoViewSet, "patch", f"/api/versiones-flujo/{self.version.pk}/",
            {"nota": "Nota posterior a publicación"}, esperado=200,
        )
        self.assertEqual(self.version.nota, "Nota posterior a publicación")
        self.assertEqual(self.version.tipo_circuito, clasificacion_original)

    def test_clasificacion_validada_antes_de_publicar_no_cambia_publicada(self):
        clasificacion_original = self.version.tipo_circuito
        self._publicar_antes_de_escritura_validada(
            VersionFlujoViewSet, "patch", f"/api/versiones-flujo/{self.version.pk}/",
            {"tipo_circuito": VersionFlujo.TipoCircuito.PROGRAMADO},
        )
        self.assertEqual(self.version.tipo_circuito, clasificacion_original)
        self.assertEqual(self.version.nota, "")

    def test_patch_no_mueve_entidad_a_otra_version(self):
        otra = VersionFlujo.objects.create(flujo=self.flujo, numero=2)
        for ruta, instancia in (("nodos", self.inicio), ("conexiones", self.conexion)):
            with self.subTest(ruta=ruta):
                respuesta = self.client.patch(
                    f"/api/{ruta}/{instancia.pk}/", {"version": otra.pk}, format="json",
                )
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                instancia.refresh_from_db()
                self.assertEqual(instancia.version_id, self.version.pk)
