"""Utilidades compartidas por la capa API."""
import uuid

from django.core.files.storage import default_storage
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


# --- Autorización por rol --------------------------------------------------- #
# Fuente de verdad de las capacidades de cada rol (espeja CAPS_POR_ROL del
# frontend). Un rol habilita un conjunto de capacidades; cada viewset declara la
# capacidad que requiere para escribir (`capacidad_requerida`).
#   config    → estructura organizativa, administración (usuarios/membresías)
#   diseno    → flujos, versiones, nodos, conexiones, formularios
#   trabajo   → casos y su operación (tomar/llamar/avanzar), filas
#   registros → historia clínica, estudios, recetas, ciudadanos
TODAS_LAS_CAPACIDADES = {"config", "diseno", "trabajo", "registros", "supervision"}
ROL_CAPACIDADES = {
    "admin": TODAS_LAS_CAPACIDADES,
    "configurador": {"diseno"},
    "jefe_area": {"trabajo", "registros", "supervision"},  # supervisa su área
    "administrativo": {"trabajo", "registros"},
    "enfermeria": {"trabajo", "registros"},      # opera, pero no firma atención (regla del motor)
    "medico": {"trabajo", "registros"},
}


def capacidades_de(user, institucion_id=None):
    """Capacidades del usuario, opcionalmente acotadas a una institución.

    El superusuario de plataforma tiene todas. El resto, la unión de las
    capacidades de sus roles en las membresías activas (de esa institución, si se
    indica una)."""
    if getattr(user, "is_superuser", False):
        return set(TODAS_LAS_CAPACIDADES)
    qs = user.membresias.filter(activo=True)
    if institucion_id is not None:
        qs = qs.filter(institucion_id=institucion_id)
    caps = set()
    for rol in qs.values_list("rol", flat=True):
        caps |= ROL_CAPACIDADES.get(rol, set())
    return caps


def _institucion_de_objeto(obj, path):
    """Sigue una ruta ORM (p. ej. "version__flujo__institucion") hasta el id de
    la institución del objeto. `path="id"` devuelve el id del propio objeto."""
    if not path:
        return None
    cur = obj
    for part in path.split("__"):
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return getattr(cur, "id", cur)


def _institucion_de_payload(view, data):
    """Resuelve la institución implicada en un `create`, usando el mismo
    `institucion_path` del viewset. Si el path apunta a un padre (p. ej.
    "version__flujo__institucion"), trae el padre por su id del cuerpo y sigue la
    cadena; así un usuario no puede crear hijos en instituciones donde no actúa.
    Devuelve None si no se puede resolver (cae al chequeo por cualquier membresía)."""
    path = getattr(view, "institucion_path", None)
    if not path:
        return None
    parts = path.split("__")
    if parts == ["id"]:
        return None  # crear la institución misma: no hay padre que resolver
    if parts == ["institucion"]:
        v = data.get("institucion")
        return _coerce(str(v)) if v else None
    # parts[0] es una FK; traemos el padre y seguimos la cadena hasta la institución.
    val = data.get(parts[0])
    if not val:
        return None
    try:
        rel_model = view.queryset.model._meta.get_field(parts[0]).related_model
    except Exception:
        return None
    cur = rel_model.objects.filter(pk=val).first()
    for part in parts[1:]:
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return getattr(cur, "id", cur)


class CapacidadPermission(BasePermission):
    """Autoriza la **escritura** según la capacidad del rol del usuario en la
    institución implicada; la **lectura** queda abierta a cualquier miembro (el
    queryset ya está scopeado por institución). El superusuario pasa siempre.

    Los viewsets declaran `capacidad_requerida`; sin ella, no se restringe."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or request.method in SAFE_METHODS:
            return True
        cap = getattr(view, "capacidad_requerida", None)
        if not cap:
            return True
        # Alta (create): resolvemos la institución del objeto (o de su padre) desde
        # el cuerpo; si no se puede, se exige la capacidad en alguna membresía activa.
        if getattr(view, "action", None) == "create":
            return cap in capacidades_de(user, _institucion_de_payload(view, request.data))
        # Detalle (update/delete/acciones): se valida con el objeto.
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser or request.method in SAFE_METHODS:
            return True
        cap = getattr(view, "capacidad_requerida", None)
        if not cap:
            return True
        inst_id = _institucion_de_objeto(obj, getattr(view, "institucion_path", None))
        return cap in capacidades_de(user, inst_id)


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
    """ViewSet estándar: CRUD + filtrado por query params + scope por institución
    + autorización por rol (lectura abierta a miembros, escritura por capacidad)."""

    permission_classes = [IsAuthenticated, CapacidadPermission]
    # Capacidad requerida para escribir; None = sin restricción de rol.
    capacidad_requerida = None
