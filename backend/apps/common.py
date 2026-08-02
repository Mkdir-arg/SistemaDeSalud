"""Utilidades compartidas por la capa API."""
import re
import uuid

from django.core.files.storage import default_storage
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
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
    institución implicada. Por defecto la **lectura** queda abierta a cualquier
    miembro (el queryset ya está scopeado por institución); si el viewset declara
    `protege_lectura = True` (p. ej. datos clínicos), la lectura también exige la
    capacidad. El superusuario pasa siempre.

    Los viewsets declaran `capacidad_requerida`; sin ella, no se restringe."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        cap = getattr(view, "capacidad_requerida", None)
        es_lectura = request.method in SAFE_METHODS
        if es_lectura and not getattr(view, "protege_lectura", False):
            return True
        if not cap:
            return True
        # Alta (create): resolvemos la institución del objeto (o de su padre) desde
        # el cuerpo; si no se puede, se exige la capacidad en alguna membresía activa.
        if getattr(view, "action", None) == "create":
            return cap in capacidades_de(user, _institucion_de_payload(view, request.data))
        # Lectura protegida de lista: se exige la capacidad en alguna institución
        # del usuario (el queryset ya filtra por institución). El detalle se
        # re-valida contra el objeto en has_object_permission.
        if es_lectura:
            return cap in capacidades_de(user)
        # Detalle de escritura (update/delete/acciones): se valida con el objeto.
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        cap = getattr(view, "capacidad_requerida", None)
        if request.method in SAFE_METHODS and not getattr(view, "protege_lectura", False):
            return True
        if not cap:
            return True
        inst_id = _institucion_de_objeto(obj, getattr(view, "institucion_path", None))
        return cap in capacidades_de(user, inst_id)


class OrdenEstable(OrderingFilter):
    """`OrderingFilter` que agrega el id como último criterio de desempate.

    Un orden con empates hace que la paginación sea inestable: si dos casos
    comparten `creado`, la base puede devolverlos en distinto orden entre una
    consulta y la siguiente, y entonces un registro aparece en dos páginas o no
    aparece en ninguna. Agregar una columna única al final lo vuelve determinista
    sin cambiar el orden que pidió el usuario.
    """

    def get_ordering(self, request, queryset, view):
        orden = super().get_ordering(request, queryset, view)
        if not orden:
            return orden
        if any(c.lstrip("-") in ("pk", "id") for c in orden):
            return orden
        return list(orden) + ["-pk"]


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


class PuedeVerElEsquema(BasePermission):
    """Abierto en desarrollo, con sesión en producción.

    El esquema no tiene datos, pero sí el mapa completo de la API: qué endpoints
    existen, con qué campos y qué acciones acepta cada uno, incluidos los de
    historia clínica. Publicárselo a cualquiera que llegue al servidor le ahorra
    medio trabajo a quien busque por dónde entrar, y no le sirve a nadie más:
    quien tiene que integrar tiene credenciales.

    Se decide por pedido y no al cargar settings, para que valga lo que DEBUG
    diga en ese momento (y para poder probarlo).
    """

    def has_permission(self, request, view):
        from django.conf import settings

        if settings.DEBUG:
            return True
        return bool(request.user and request.user.is_authenticated)


@extend_schema(
    tags=["registros"],
    summary="Sube un archivo",
    description="Devuelve el nombre y la URL del archivo guardado, para referenciarlo desde un campo de formulario.",
    request={"multipart/form-data": {"type": "object", "properties": {"archivo": {"type": "string", "format": "binary"}}}},
    responses=OpenApiTypes.OBJECT,
)
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


class ExportaCSV:
    """
    Agrega `?formato=csv` a cualquier listado.

    Tres decisiones que hacen la diferencia entre «anda» y «el cliente dice que
    está roto»:

    1. **Respeta los filtros de la pantalla.** Se exporta exactamente lo que la
       persona está viendo (búsqueda, filtros, orden), sin la paginación. Un
       archivo que no coincide con lo que había en pantalla no sirve para rendir
       cuentas, que es justamente para lo que se exporta.

    2. **Se transmite fila por fila** (`StreamingHttpResponse`). Un servicio con
       cien mil casos no puede armar el archivo entero en memoria mientras
       alguien más está atendiendo pacientes.

    3. **BOM y punto y coma.** Excel en configuración regional española abre un
       CSV separado por comas metiendo todo en una sola columna, y sin BOM
       rompe los acentos. Como quien exporta abre el archivo en Excel, ése es el
       formato por defecto; `?sep=,` devuelve el CSV estándar para quien lo va a
       leer con pandas.

    Cada viewset declara `columnas_csv = [("clave", "Encabezado"), …]`. Las
    claves se resuelven sobre lo que devuelve el serializer, así que la
    exportación no puede mostrar un campo que la API no expone.
    """

    columnas_csv: list[tuple[str, str]] = []
    # Nombre del archivo. Por defecto DRF deriva `basename` del modelo y sale
    # en singular («caso-2026-08-02.csv»), que queda raro para un listado.
    nombre_csv: str = ""

    def list(self, request, *args, **kwargs):
        if request.query_params.get("formato") != "csv" or not self.columnas_csv:
            return super().list(request, *args, **kwargs)
        return self.exportar_csv(request)

    def exportar_csv(self, request):
        import csv
        from django.http import StreamingHttpResponse
        from django.utils import timezone

        qs = self.filter_queryset(self.get_queryset())
        claves = [c for c, _ in self.columnas_csv]
        sep = "," if request.query_params.get("sep") == "," else ";"

        class Buffer:
            """`csv.writer` escribe en un objeto con `write`; acá se devuelve."""
            def write(self, valor):
                return valor

        escritor = csv.writer(Buffer(), delimiter=sep, quoting=csv.QUOTE_MINIMAL)

        def filas():
            # El BOM va primero para que Excel reconozca UTF-8.
            yield "﻿"
            yield escritor.writerow([e for _, e in self.columnas_csv])
            serializer = self.get_serializer_class()
            contexto = self.get_serializer_context()
            # `iterator()` no arma la lista completa en memoria.
            for obj in qs.iterator(chunk_size=500):
                datos = serializer(obj, context=contexto).data
                yield escritor.writerow([_texto_csv(datos.get(k)) for k in claves])

        nombre = f"{self.nombre_csv or self.basename}-{timezone.localdate():%Y-%m-%d}.csv"
        r = StreamingHttpResponse(filas(), content_type="text/csv; charset=utf-8")
        r["Content-Disposition"] = f'attachment; filename="{nombre}"'
        return r


# Las fechas del serializer vienen en ISO con zona («2026-08-02T10:14:30-03:00»).
# Excel no lo reconoce como fecha: lo deja como texto y no se puede ordenar ni
# filtrar por él, que es la mitad de para qué se exporta.
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?")


def _texto_csv(valor):
    """Aplana un valor del serializer a algo que tenga sentido en una celda."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        m = _ISO.match(valor)
        if m:
            a, me, d, h, mi = m.groups()
            return f"{d}/{me}/{a}" + (f" {h}:{mi}" if h else "")
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (list, tuple)):
        return " · ".join(_texto_csv(v) for v in valor)
    if isinstance(valor, dict):
        # Los anidados suelen traer un nombre legible; si no, se descarta en vez
        # de volcar un JSON crudo en una celda.
        return str(valor.get("nombre") or valor.get("titulo") or valor.get("label") or "")
    return str(valor)


class BaseModelViewSet(ExportaCSV, QueryParamFilterMixin, InstitucionScopedMixin, viewsets.ModelViewSet):
    """ViewSet estándar: CRUD + filtrado por query params + scope por institución
    + autorización por rol (lectura abierta a miembros, escritura por capacidad)
    + orden y búsqueda por query param.

    `?ordering=` y `?search=` quedan disponibles en todos los listados. Cada
    viewset acota qué campos admite con `ordering_fields` y `search_fields`; sin
    declararlos, `ordering` no acepta nada y `search` se ignora (comportamiento de
    DRF), así que no hay riesgo de exponer campos por accidente.
    """

    permission_classes = [IsAuthenticated, CapacidadPermission]
    filter_backends = [OrdenEstable, SearchFilter]
    # Capacidad requerida para escribir; None = sin restricción de rol.
    capacidad_requerida = None
    # Si True, la LECTURA también exige `capacidad_requerida` (datos sensibles).
    protege_lectura = False
