"""Relectura de versión borrada tras validar una escritura del grafo."""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion
from .models import Conexion, Flujo, Nodo, VersionFlujo
from .views import ConexionViewSet, NodoViewSet


class VersionEliminadaAuditoria172Tests(TestCase):
    def setUp(self):
        usuario = Usuario.objects.create_superuser("version-eliminada@example.test", "x")
        institucion = Institucion.objects.create(nombre="Institución sintética")
        self.flujo = Flujo.objects.create(institucion=institucion, titulo="Flujo sintético")
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)
        self.otro = APIClient()
        self.otro.force_authenticate(usuario)

    def intercalar(self, metodo):
        for numero, (viewset, ruta) in enumerate(((NodoViewSet, "nodos"), (ConexionViewSet, "conexiones")), 1):
            with self.subTest(ruta=ruta, metodo=metodo):
                version = VersionFlujo.objects.create(flujo=self.flujo, numero=numero)
                inicio = Nodo.objects.create(version=version, tipo="inicio", titulo="Inicio")
                fin = Nodo.objects.create(version=version, tipo="fin", titulo="Fin")
                conexion = Conexion.objects.create(version=version, origen=inicio, destino=fin)
                objeto = inicio if ruta == "nodos" else conexion
                hook = {"post": "perform_create", "patch": "perform_update", "delete": "perform_destroy"}[metodo]
                original = getattr(viewset, hook)

                def borrar_tras_validar(view, validado):
                    # Se intercalan requests reales una vez leído/validado el
                    # objeto, sin reemplazar el lock ni el guard de producción.
                    respuesta = self.otro.delete(f"/api/versiones-flujo/{version.pk}/")
                    self.assertEqual(respuesta.status_code, 204, getattr(respuesta, "data", None))
                    return original(view, validado)

                datos = ({"version": version.pk, "tipo": "fin", "titulo": "Nuevo"}
                         if ruta == "nodos" else {"version": version.pk, "origen": inicio.pk, "destino": fin.pk})
                url = f"/api/{ruta}/" if metodo == "post" else f"/api/{ruta}/{objeto.pk}/"
                if metodo == "patch":
                    datos = {"titulo": "Cambio"} if ruta == "nodos" else {"etiqueta": "Cambio"}
                with patch.object(viewset, hook, borrar_tras_validar):
                    respuesta = getattr(self.cliente, metodo)(url, datos, format="json")
                self.assertEqual(respuesta.status_code, 404, getattr(respuesta, "data", None))
                self.assertFalse(VersionFlujo.objects.filter(pk=version.pk).exists())
                self.assertFalse(Nodo.objects.filter(version_id=version.pk).exists())
                self.assertFalse(Conexion.objects.filter(version_id=version.pk).exists())

    def test_alta_sobre_version_eliminada_responde_404(self):
        self.intercalar("post")

    def test_edicion_sobre_version_eliminada_responde_404(self):
        self.intercalar("patch")

    def test_borrado_sobre_version_eliminada_responde_404(self):
        self.intercalar("delete")
