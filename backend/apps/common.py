"""Utilidades compartidas por la capa API."""
from pathlib import PurePosixPath
import hashlib
import re
import uuid

from django.core.files.storage import default_storage
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView


# --- Autorización por rol --------------------------------------------------- #
# Fuente de verdad de las capacidades de cada rol. Un rol habilita un conjunto
# de capacidades; cada viewset declara la capacidad que requiere para escribir
# (`capacidad_requerida`) y la UI consume estas mismas capacidades desde
# `/usuarios/me/`.
#   config    → estructura organizativa, administración (usuarios/membresías)
#   diseno    → flujos, versiones, nodos, conexiones, formularios
#   trabajo   → casos y su operación (tomar/llamar/avanzar), filas
#   registros → historia clínica, estudios, recetas, ciudadanos
CAPACIDADES_LEGADAS = {"config", "diseno", "trabajo", "registros", "supervision"}
CAPACIDADES_DOMINIO = {
    "reportes",
    "padron_admision",
    "historia_clinica",
    "prescripcion",
    "solicitud_estudios",
    "turnos",
    "casos_operar",
    "filas",
    "internacion",
    "farmacia_stock",
    "traslados_red",
    "config_institucional",
    "diseno_flujos",
    "gobierno_plataforma",
}
CAPACIDADES_UI = {"auditoria"}
TODAS_LAS_CAPACIDADES = CAPACIDADES_LEGADAS | CAPACIDADES_DOMINIO | CAPACIDADES_UI
CAPACIDADES_GLOBALES = {"gobierno_plataforma"}
ROL_CAPACIDADES = {
    "plataforma": {"gobierno_plataforma", "reportes"},
    "auditor": set(),
    "reportes": {"reportes"},
    "admin": CAPACIDADES_LEGADAS | (CAPACIDADES_DOMINIO - {"gobierno_plataforma"}),
    "configurador": {"diseno", "diseno_flujos"},
    "jefe_area": {
        "trabajo", "registros", "supervision",
        "padron_admision", "historia_clinica", "prescripcion",
        "solicitud_estudios", "turnos", "casos_operar", "filas",
        "internacion", "farmacia_stock", "traslados_red",
    },
    "administrativo": {
        "trabajo", "registros",
        "padron_admision", "turnos", "casos_operar", "filas", "traslados_red",
    },
    "enfermeria": {
        "trabajo", "registros",
        "padron_admision", "historia_clinica", "solicitud_estudios",
        "turnos", "casos_operar", "filas", "internacion", "farmacia_stock",
        "traslados_red",
    },
    "medico": {
        "trabajo", "registros",
        "padron_admision", "historia_clinica", "prescripcion",
        "solicitud_estudios", "turnos", "casos_operar", "filas",
        "internacion", "traslados_red",
    },
}
ROL_CAPACIDADES_UI = {
    "plataforma": {"auditoria"},
    "auditor": {"auditoria"},
    "admin": {"auditoria"},
    "jefe_area": {"auditoria"},
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


def tiene_capacidad(user, capacidad, institucion_id=None):
    """Verdadero si la capacidad aplica en el alcance pedido.

    Las capacidades sanitarias son institucionales. `gobierno_plataforma`, en
    cambio, es deliberadamente global: crear una institucion o definir una red no
    pertenece a ningun hospital puntual.
    """
    if capacidad in CAPACIDADES_GLOBALES:
        return capacidad in capacidades_de(user)
    return capacidad in capacidades_de(user, institucion_id)


def tiene_alguna_capacidad(user, capacidades, institucion_id=None):
    """Verdadero si alguna capacidad alcanza para el mismo objeto/alcance."""
    return any(tiene_capacidad(user, capacidad, institucion_id) for capacidad in capacidades)


def capacidades_efectivas_de(user, institucion_id=None):
    """Capacidades para sesion/UI, incluyendo reglas especiales de menu."""
    if getattr(user, "is_superuser", False):
        return set(TODAS_LAS_CAPACIDADES)
    qs = user.membresias.filter(activo=True)
    if institucion_id is not None:
        qs = qs.filter(institucion_id=institucion_id)
    caps = set()
    for rol in qs.values_list("rol", flat=True):
        caps |= ROL_CAPACIDADES.get(rol, set())
        caps |= ROL_CAPACIDADES_UI.get(rol, set())
    return caps


def roles_por_institucion_de(user):
    """Roles activos agrupados por institucion."""
    if getattr(user, "is_superuser", False):
        return {}
    por_inst = {}
    for inst_id, rol in user.membresias.filter(activo=True).values_list("institucion_id", "rol"):
        por_inst.setdefault(str(inst_id), []).append(rol)
    return {inst: sorted(set(roles)) for inst, roles in por_inst.items()}


def capacidades_por_institucion_de(user):
    """Capacidades efectivas agrupadas por institucion."""
    if getattr(user, "is_superuser", False):
        return {}
    por_inst = {}
    for inst_id, rol in user.membresias.filter(activo=True).values_list("institucion_id", "rol"):
        caps = por_inst.setdefault(str(inst_id), set())
        caps |= ROL_CAPACIDADES.get(rol, set())
        caps |= ROL_CAPACIDADES_UI.get(rol, set())
    return {inst: sorted(caps) for inst, caps in por_inst.items()}


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

    Los viewsets declaran `capacidad_requerida`; sin ella, no se restringe.

    Un mismo recurso puede necesitar capacidades distintas según qué se le haga:
    crear una cama es configurar el hospital, pero marcarla higienizada lo hace
    enfermería todos los días. Para eso está `capacidad_por_accion`, que pisa a
    `capacidad_requerida` en las acciones que nombre."""

    @staticmethod
    def _capacidad(view):
        por_accion = getattr(view, "capacidad_por_accion", None) or {}
        return por_accion.get(getattr(view, "action", None)) or getattr(view, "capacidad_requerida", None)

    @classmethod
    def _capacidades(cls, view):
        capacidad = cls._capacidad(view)
        if not capacidad:
            return ()
        if isinstance(capacidad, str):
            return (capacidad,)
        return tuple(capacidad)

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        caps = self._capacidades(view)
        es_lectura = request.method in SAFE_METHODS
        if es_lectura and not getattr(view, "protege_lectura", False):
            return True
        if not caps:
            return True
        # Alta (create): resolvemos la institución del objeto (o de su padre) desde
        # el cuerpo; si no se puede, se exige la capacidad en alguna membresía activa.
        if getattr(view, "action", None) == "create":
            return tiene_alguna_capacidad(user, caps, _institucion_de_payload(view, request.data))
        # Lectura protegida de lista: se exige la capacidad en alguna institución
        # del usuario (el queryset ya filtra por institución). El detalle se
        # re-valida contra el objeto en has_object_permission.
        if es_lectura:
            return tiene_alguna_capacidad(user, caps)
        # Detalle de escritura (update/delete/acciones): se valida con el objeto.
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        caps = self._capacidades(view)
        if request.method in SAFE_METHODS and not getattr(view, "protege_lectura", False):
            return True
        if not caps:
            return True
        inst_id = _institucion_de_objeto(obj, getattr(view, "institucion_path", None))
        return tiene_alguna_capacidad(user, caps, inst_id)


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


ARCHIVO_CLINICO_TIPOS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "text/plain": {".txt"},
}
ARCHIVO_CLINICO_MAX_BYTES = 10 * 1024 * 1024


def _archivo_max_bytes():
    from django.conf import settings

    return int(getattr(settings, "ARCHIVO_CLINICO_MAX_BYTES", ARCHIVO_CLINICO_MAX_BYTES))


def _tipo_archivo(archivo):
    return (getattr(archivo, "content_type", "") or "").split(";")[0].strip().lower()


def _muestra_archivo(archivo, n=512):
    try:
        data = archivo.read(n)
        archivo.seek(0)
        return data or b""
    except Exception:
        return b""


def _firma_coherente(content_type, muestra):
    if content_type == "application/pdf":
        return muestra.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return muestra.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return muestra.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return muestra.startswith(b"RIFF") and muestra[8:12] == b"WEBP"
    if content_type == "text/plain":
        return b"\x00" not in muestra
    return False


def _validar_archivo_clinico(archivo, original):
    max_bytes = _archivo_max_bytes()
    tamano = int(getattr(archivo, "size", 0) or 0)
    if tamano <= 0:
        return Response({"detail": "El archivo esta vacio."}, status=status.HTTP_400_BAD_REQUEST)
    if tamano > max_bytes:
        mb = max_bytes // (1024 * 1024)
        return Response({"detail": f"El archivo supera el maximo permitido de {mb} MB."}, status=status.HTTP_400_BAD_REQUEST)

    content_type = _tipo_archivo(archivo)
    extensiones = ARCHIVO_CLINICO_TIPOS.get(content_type)
    if not extensiones:
        return Response({"detail": "Tipo de archivo no permitido para adjuntos clinicos."}, status=status.HTTP_400_BAD_REQUEST)

    ext = PurePosixPath(original).suffix.lower()
    if ext and ext not in extensiones:
        return Response({"detail": "La extension no coincide con el tipo de archivo declarado."}, status=status.HTTP_400_BAD_REQUEST)
    if not _firma_coherente(content_type, _muestra_archivo(archivo)):
        return Response({"detail": "El contenido del archivo no coincide con el tipo declarado."}, status=status.HTTP_400_BAD_REQUEST)
    return content_type, ext or sorted(extensiones)[0], tamano


def _sha256_archivo(archivo):
    digest = hashlib.sha256()
    for chunk in archivo.chunks():
        digest.update(chunk)
    try:
        archivo.seek(0)
    except Exception:
        pass
    return digest.hexdigest()


@extend_schema(
    tags=["registros"],
    summary="Sube un archivo",
    description="Devuelve el nombre, la ruta interna y la URL protegida del archivo guardado.",
    request={"multipart/form-data": {"type": "object", "properties": {"archivo": {"type": "string", "format": "binary"}, "institucion": {"type": "integer"}}}},
    responses=OpenApiTypes.OBJECT,
)
class SubirArchivoView(APIView):
    """
    Sube un archivo y devuelve su nombre y URL. Usado por los campos de tipo
    «Archivo adjunto» y por los estudios de la historia clínica.

    POST multipart/form-data con campos `archivo` e `institucion`. → {"nombre": ..., "ruta": ..., "url": ...}
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        archivo = request.FILES.get("archivo")
        if not archivo:
            return Response({"detail": "Falta el archivo."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            institucion_id = int(request.data.get("institucion") or 0)
        except (TypeError, ValueError):
            institucion_id = 0
        if not institucion_id:
            return Response({"detail": "Indica la institucion del archivo."}, status=status.HTTP_400_BAD_REQUEST)
        from apps.instituciones.models import Institucion

        if not Institucion.objects.filter(pk=institucion_id).exists():
            return Response({"detail": "La institucion indicada no existe."}, status=status.HTTP_400_BAD_REQUEST)
        if "historia_clinica" not in capacidades_de(request.user, institucion_id):
            return Response(
                {"detail": "No tenes permiso para subir archivos clinicos en esta institucion."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Nombre único conservando la extensión.
        original = PurePosixPath(archivo.name or "archivo").name
        validacion = _validar_archivo_clinico(archivo, original)
        if isinstance(validacion, Response):
            return validacion
        content_type, ext, tamano = validacion
        sha256 = _sha256_archivo(archivo)

        nombre = f"uploads/{institucion_id}/{uuid.uuid4().hex}{ext}"
        guardado = default_storage.save(nombre, archivo)
        from apps.registros.models import ArchivoClinico

        proposito = request.data.get("proposito") or ArchivoClinico.Proposito.ADJUNTO_CASO
        if proposito not in {v for v, _ in ArchivoClinico.Proposito.choices}:
            default_storage.delete(guardado)
            return Response({"detail": "Proposito de archivo invalido."}, status=status.HTTP_400_BAD_REQUEST)
        objeto_id = request.data.get("objeto_id") or None
        if objeto_id is not None:
            try:
                objeto_id = int(objeto_id)
            except (TypeError, ValueError):
                default_storage.delete(guardado)
                return Response({"detail": "objeto_id debe ser numerico."}, status=status.HTTP_400_BAD_REQUEST)

        meta = ArchivoClinico.objects.create(
            institucion_id=institucion_id,
            ruta=guardado,
            nombre_original=original,
            content_type=content_type,
            tamano=tamano,
            sha256=sha256,
            proposito=proposito,
            objeto_tipo=(request.data.get("objeto_tipo") or "")[:80],
            objeto_id=objeto_id,
            subido_por=request.user,
        )
        url = request.build_absolute_uri(f"/api/archivos/descargar/{guardado}")
        return Response(
            {
                "nombre": original,
                "ruta": guardado,
                "url": url,
                "content_type": meta.content_type,
                "tamano": meta.tamano,
                "sha256": meta.sha256,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["registros"],
    summary="Descarga un archivo clinico",
    description="Sirve un archivo subido solo si el usuario tiene historia_clinica en la institucion del archivo.",
    responses=OpenApiTypes.BINARY,
)
class DescargarArchivoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ruta):
        partes = PurePosixPath(ruta).parts
        if len(partes) < 3 or partes[0] != "uploads" or not partes[1].isdigit():
            return Response({"detail": "Archivo invalido."}, status=status.HTTP_404_NOT_FOUND)
        if any(p in ("", ".", "..") for p in partes):
            return Response({"detail": "Archivo invalido."}, status=status.HTTP_404_NOT_FOUND)

        from apps.registros.models import ArchivoClinico

        meta = ArchivoClinico.objects.filter(ruta=ruta).first()
        institucion_id = meta.institucion_id if meta else int(partes[1])
        if "historia_clinica" not in capacidades_de(request.user, institucion_id):
            return Response(
                {"detail": "No tenes permiso para descargar este archivo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not default_storage.exists(ruta):
            return Response({"detail": "Archivo no encontrado."}, status=status.HTTP_404_NOT_FOUND)
        respuesta = FileResponse(
            default_storage.open(ruta, "rb"),
            as_attachment=False,
            filename=meta.nombre_original if meta else partes[-1],
        )
        if meta and meta.content_type:
            respuesta["Content-Type"] = meta.content_type
        return respuesta


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

    def get_columnas_csv(self, request):
        return self.columnas_csv

    def list(self, request, *args, **kwargs):
        columnas = self.get_columnas_csv(request)
        if request.query_params.get("formato") != "csv" or not columnas:
            return super().list(request, *args, **kwargs)
        return self.exportar_csv(request)

    def exportar_csv(self, request):
        import csv
        from django.http import StreamingHttpResponse
        from django.utils import timezone

        qs = self.filter_queryset(self.get_queryset())
        columnas = self.get_columnas_csv(request)
        claves = [c for c, _ in columnas]
        sep = "," if request.query_params.get("sep") == "," else ";"

        class Buffer:
            """`csv.writer` escribe en un objeto con `write`; acá se devuelve."""
            def write(self, valor):
                return valor

        escritor = csv.writer(Buffer(), delimiter=sep, quoting=csv.QUOTE_MINIMAL)

        def filas():
            # El BOM va primero para que Excel reconozca UTF-8.
            yield "﻿"
            yield escritor.writerow([e for _, e in columnas])
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
