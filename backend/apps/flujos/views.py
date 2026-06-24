from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.casos import motor
from apps.common import BaseModelViewSet

from .models import Conexion, Flujo, Nodo, VersionFlujo
from .serializers import (
    ConexionSerializer,
    FlujoSerializer,
    NodoSerializer,
    VersionFlujoSerializer,
)


class FlujoViewSet(BaseModelViewSet):
    queryset = Flujo.objects.select_related("institucion", "area").prefetch_related("versiones")
    serializer_class = FlujoSerializer
    institucion_path = "institucion"
    filter_fields = ("institucion", "area")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titulo"]
    ordering_fields = ["titulo", "creado"]


class VersionFlujoViewSet(BaseModelViewSet):
    queryset = VersionFlujo.objects.select_related("flujo", "autor").prefetch_related(
        "nodos", "conexiones"
    )
    serializer_class = VersionFlujoSerializer
    institucion_path = "flujo__institucion"
    filter_fields = ("flujo", "estado")

    @action(detail=True, methods=["get"])
    def validar(self, request, pk=None):
        """Devuelve los problemas (errores/avisos) del grafo y si se puede publicar."""
        version = self.get_object()
        problemas = motor.validar_version(version)
        return Response({
            "problemas": problemas,
            "errores": sum(1 for p in problemas if p["sev"] == "error"),
            "avisos": sum(1 for p in problemas if p["sev"] == "aviso"),
            "puede_publicar": not any(p["sev"] == "error" for p in problemas),
        })

    @action(detail=True, methods=["post"])
    def publicar(self, request, pk=None):
        """Publica la versión si no tiene errores; marca las anteriores como reemplazadas."""
        version = self.get_object()
        problemas = motor.validar_version(version)
        if any(p["sev"] == "error" for p in problemas):
            return Response(
                {"detail": "La versión tiene errores y no puede publicarse.", "problemas": problemas},
                status=status.HTTP_400_BAD_REQUEST,
            )
        (VersionFlujo.objects
         .filter(flujo=version.flujo, estado=VersionFlujo.Estado.PUBLICADA)
         .exclude(pk=version.pk)
         .update(estado=VersionFlujo.Estado.REEMPLAZADA))
        version.estado = VersionFlujo.Estado.PUBLICADA
        version.save(update_fields=["estado"])
        return Response(self.get_serializer(version).data)


class NodoViewSet(BaseModelViewSet):
    queryset = Nodo.objects.select_related("version", "formulario")
    serializer_class = NodoSerializer
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version", "tipo")


class ConexionViewSet(BaseModelViewSet):
    queryset = Conexion.objects.select_related("version", "origen", "destino")
    serializer_class = ConexionSerializer
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version",)
