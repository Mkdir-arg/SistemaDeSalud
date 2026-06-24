"""Utilidades compartidas por la capa API."""
import uuid

from django.core.files.storage import default_storage
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView


class QueryParamFilterMixin:
    """
    Permite filtrar un ViewSet por campos exactos vía query params.

    Definir `filter_fields = ("institucion", "area")` y luego llamar, p. ej.,
    `GET /api/areas/?institucion=1`.
    """

    filter_fields: tuple = ()

    def get_queryset(self):
        qs = super().get_queryset()
        for field in self.filter_fields:
            value = self.request.query_params.get(field)
            if value not in (None, ""):
                qs = qs.filter(**{field: _coerce(value)})
        return qs


class InstitucionScopedMixin:
    """
    Limita el queryset a las instituciones del usuario autenticado.

    El super admin de plataforma (is_superuser) ve todo. El resto solo ve los
    objetos de las instituciones donde tiene una membresía activa. Definir
    `institucion_path` con la ruta ORM hacia la institución (p. ej. "institucion",
    "area__institucion", "caso__institucion").
    """

    institucion_path: str | None = None

    def instituciones_del_usuario(self):
        user = self.request.user
        return list(
            user.membresias.filter(activo=True).values_list("institucion_id", flat=True)
        )

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if self.institucion_path and user.is_authenticated and not user.is_superuser:
            ids = self.instituciones_del_usuario()
            qs = qs.filter(**{f"{self.institucion_path}__in": ids})
        return qs


def _coerce(value):
    """Convierte strings de query param a su tipo: booleanos y 'null'."""
    low = value.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none"):
        return None
    return value


class SubirArchivoView(APIView):
    """
    Sube un archivo y devuelve su nombre y URL. Usado por los campos de tipo
    «Archivo adjunto» y por los estudios de la historia clínica.

    POST multipart/form-data con campo `archivo`. → {"nombre": ..., "url": ...}
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get("archivo")
        if not archivo:
            return Response({"detail": "Falta el archivo."}, status=status.HTTP_400_BAD_REQUEST)
        # Nombre único conservando la extensión.
        ext = archivo.name.rsplit(".", 1)[-1] if "." in archivo.name else ""
        nombre = f"uploads/{uuid.uuid4().hex}{('.' + ext) if ext else ''}"
        guardado = default_storage.save(nombre, archivo)
        return Response(
            {"nombre": archivo.name, "url": request.build_absolute_uri(default_storage.url(guardado))},
            status=status.HTTP_201_CREATED,
        )


class BaseModelViewSet(QueryParamFilterMixin, InstitucionScopedMixin, viewsets.ModelViewSet):
    """ViewSet estándar: CRUD + filtrado por query params + scope por institución."""

    pass
