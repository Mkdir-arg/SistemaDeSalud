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
    queryset = Flujo.objects.select_related("institucion", "area", "subarea").prefetch_related("versiones")
    serializer_class = FlujoSerializer
    capacidad_requerida = "diseno"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "subarea")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titulo"]
    ordering_fields = ["titulo", "creado"]

    @action(detail=False, methods=["get"])
    def mapa(self, request):
        """Grafo de derivaciones entre flujos (para el Mapa de flujos).

        Devuelve `nodos` (un flujo por bloque, con su estado vigente) y `aristas`
        (cada nodo de tipo «derivar» con `flujo_destino_id` es una flecha
        origen → destino). Una arista a un flujo fuera del conjunto se marca como
        externa para poder dibujarla distinto.
        """
        flujos = list(self.get_queryset())
        ids = {f.id for f in flujos}
        nodos, aristas = [], []
        for f in flujos:
            vigente = f.version_publicada or f.versiones.order_by("-numero").first()
            nodos.append({
                "id": f.id,
                "titulo": f.titulo,
                "area_nombre": f.area.nombre if f.area_id else "Institución",
                "ambito": f.ambito,
                "estado": vigente.estado if vigente else "borrador",
                "versiones": f.versiones.count(),
            })
            if not vigente:
                continue
            for nodo in vigente.nodos.filter(tipo=Nodo.Tipo.DERIVAR):
                destino = (nodo.config or {}).get("flujo_destino_id")
                if destino:
                    aristas.append({
                        "origen": f.id,
                        "destino": destino,
                        "etiqueta": nodo.titulo or "Derivar",
                        "externo": destino not in ids,
                    })
        return Response({"nodos": nodos, "aristas": aristas})


class VersionFlujoViewSet(BaseModelViewSet):
    queryset = VersionFlujo.objects.select_related("flujo", "autor").prefetch_related(
        "nodos", "conexiones"
    )
    serializer_class = VersionFlujoSerializer
    capacidad_requerida = "diseno"
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
    queryset = Nodo.objects.select_related("version", "formulario").prefetch_related("grupos__area")
    serializer_class = NodoSerializer
    capacidad_requerida = "diseno"
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version", "tipo")

    @action(detail=True, methods=["post"])
    def pantalla(self, request, pk=None):
        """Genera (si falta) y devuelve el token de la pantalla de llamados del nodo.

        La pantalla pública vive en `/pantalla/<token>` (sin login). Con `?rotar=1`
        en el cuerpo se reemplaza el token actual (invalida la URL anterior)."""
        import secrets

        nodo = self.get_object()
        if not nodo.pantalla_token or request.data.get("rotar"):
            nodo.pantalla_token = secrets.token_urlsafe(12)
            nodo.save(update_fields=["pantalla_token"])
        return Response({"token": nodo.pantalla_token, "ruta": f"/pantalla/{nodo.pantalla_token}"})


class ConexionViewSet(BaseModelViewSet):
    queryset = Conexion.objects.select_related("version", "origen", "destino")
    serializer_class = ConexionSerializer
    capacidad_requerida = "diseno"
    institucion_path = "version__flujo__institucion"
    filter_fields = ("version",)
