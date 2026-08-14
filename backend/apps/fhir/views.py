"""
Fachada FHIR R4 de sólo lectura.

**Sólo lectura, y es una decisión, no una etapa.** Aceptar escrituras por acá
significaría meter datos clínicos salteándose el motor: sin flujo, sin evento en
la línea de tiempo, sin el sellado de integridad que se le agregó a la historia
clínica. Un `POST /fhir/Observation` que escribe directo en la base convierte
todo eso en decorado. Cuando haga falta escribir desde afuera, el camino es un
nodo de integración del flujo —que ya existe— y no un endpoint que puentea las
reglas.

**Toda lectura de acá queda en el registro de accesos**, igual que desde la
pantalla. Es el punto que más fácil se pasa por alto: si la fachada FHIR no
auditara, sería un agujero prolijo a través de todo lo que se construyó para la
Ley 26.529 —bastaría con pedir los datos por la otra puerta—. Se usa la MISMA
función que los viewsets (`registrar_acceso`), no una copia.

**Alcance por institución.** Un cliente ve lo de las instituciones donde su
usuario tiene membresía activa, ni una más. El scope no lo decide el parámetro
de la consulta.
"""
from django.http import JsonResponse
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.auditoria.mixins import registrar_acceso
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

from . import recursos

# --------------------------------------------------------------------------- #
# Esta fachada NO se documenta en el OpenAPI, a propósito.
#
# FHIR trae su propio documento de contrato —el CapabilityStatement de
# `/fhir/metadata`—, que es lo que un cliente FHIR lee. Describirla además en
# OpenAPI no le sirve a nadie y sí rompe el esquema de `/api/`: los recursos se
# arman a mano (no hay serializer que drf-spectacular pueda inspeccionar) y las
# rutas del estándar colisionan de a pares (`/Patient` y `/Patient/{id}`).
#
# El guard del esquema lo detectó apenas se agregó esto: 47 errores y 3
# colisiones. Se excluye acá, explícito y con motivo, en vez de bajarle la vara
# al guard —que es lo que evita que el esquema de la API se degrade solo—.
fuera_del_openapi = extend_schema(exclude=True)

# FHIR define su propio content-type. Un cliente estricto que recibe
# `application/json` a secas puede rechazar la respuesta.
TIPO = "application/fhir+json"

# Tope de resultados de una búsqueda. Sin esto, `GET /fhir/Patient` sin filtros
# devuelve el padrón entero en una sola respuesta: mala idea para el servidor y
# peor para el registro de accesos, donde queda una línea que dice «miró todo».
TOPE = 100


def _fhir(datos, status=200):
    return JsonResponse(datos, status=status, content_type=TIPO, json_dumps_params={"ensure_ascii": False})


def _error(status, codigo, mensaje):
    severidad = "error" if status >= 500 else "warning" if status == 404 else "error"
    return _fhir(recursos.operation_outcome(severidad, codigo, mensaje), status=status)


def _instituciones(request):
    """Las instituciones que este usuario puede ver. El superusuario, todas."""
    if request.user.is_superuser:
        return Institucion.objects.all()
    ids = request.user.membresias.filter(activo=True).values_list("institucion_id", flat=True)
    return Institucion.objects.filter(id__in=list(ids))


# --------------------------------------------------------------------------- #
# CapabilityStatement
# --------------------------------------------------------------------------- #
@fuera_del_openapi
@api_view(["GET"])
@permission_classes([AllowAny])
def metadata(request):
    """
    `GET /fhir/metadata` — qué sabe hacer este servidor.

    Es lo PRIMERO que pide cualquier cliente FHIR, antes de intentar nada. Sin
    esto la integración no arranca aunque el resto funcione perfecto.

    Va sin autenticación a propósito: describe capacidades, no datos. Que el
    área de sistemas del otro lado pueda apuntar su cliente y ver qué hay antes
    de tramitar credenciales es la diferencia entre una prueba de media hora y
    una reunión.

    Declara exactamente lo que está implementado. Anunciar recursos que
    devuelven cáscaras vacías hace que el otro lado escriba código contra algo
    que no existe, y el problema aparece en producción, no en la prueba.
    """
    base = request.build_absolute_uri(reverse("fhir-metadata")).rsplit("/metadata", 1)[0]
    return _fhir({
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2026-08-14",
        "kind": "instance",
        "software": {"name": "Cauce"},
        "implementation": {"description": "Fachada FHIR de Cauce", "url": base},
        "fhirVersion": recursos.VERSION_FHIR,
        "format": ["json"],
        "rest": [{
            "mode": "server",
            "documentation": (
                "Sólo lectura. Escribir datos clínicos salteándose el motor de flujos "
                "dejaría el episodio sin línea de tiempo y sin sellado de integridad; "
                "para escribir desde afuera se usa un nodo de integración del flujo."
            ),
            "security": {"description": "Bearer JWT. Alcance limitado a las instituciones del usuario."},
            "resource": [
                {
                    "type": "Patient",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "identifier", "type": "token",
                         "documentation": f"Documento. Ej.: {recursos.SISTEMA_DNI}|30111222"},
                        {"name": "family", "type": "string"},
                    ],
                },
                {
                    "type": "Encounter",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "patient", "type": "reference"},
                        {"name": "status", "type": "token"},
                    ],
                },
                {
                    "type": "Organization",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                },
            ],
        }],
    })


# --------------------------------------------------------------------------- #
# Patient
# --------------------------------------------------------------------------- #
@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_read(request, pk):
    c = (
        Ciudadano.objects.select_related("institucion")
        .filter(pk=pk, institucion__in=_instituciones(request))
        .first()
    )
    if c is None:
        # Mismo 404 exista o no fuera del alcance: contestar «existe pero no
        # podés verlo» confirma que esa persona está registrada en el sistema,
        # que ya es información sobre ella.
        return _error(404, "not-found", "No hay un Patient con ese id.")

    registrar_acceso(
        request, AccesoClinico.Tipo.DETALLE, "ciudadano",
        ciudadano=c, objeto_id=c.id, detalle="fhir Patient/read",
    )
    return _fhir(recursos.patient(c))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_search(request):
    """
    `GET /fhir/Patient?identifier=<sistema>|<documento>&family=<apellido>`

    El `identifier` de FHIR viene como `sistema|valor`, y el sistema es
    opcional. Se acepta con y sin: exigirlo haría fallar consultas correctas por
    una cuestión de forma.
    """
    qs = Ciudadano.objects.select_related("institucion").filter(
        institucion__in=_instituciones(request)
    )

    identificador = request.query_params.get("identifier", "")
    if identificador:
        valor = identificador.split("|")[-1].strip()
        qs = qs.filter(documento=valor) if valor else qs.none()
    familia = request.query_params.get("family", "").strip()
    if familia:
        qs = qs.filter(apellido__icontains=familia)

    filas = list(qs[:TOPE])
    total = qs.count()

    # Buscar por documento y encontrar UNA persona es leer los datos de esa
    # persona: se anota a su nombre. Si no, consultar por documento sería la
    # forma de mirar a alguien sin dejar rastro suyo.
    unico = filas[0] if (identificador and len(filas) == 1) else None
    registrar_acceso(
        request,
        AccesoClinico.Tipo.DETALLE if unico else AccesoClinico.Tipo.LISTADO,
        "ciudadano",
        ciudadano=unico,
        objeto_id=unico.id if unico else "",
        detalle="fhir Patient/search "
                + " ".join(f"{k}={v}" for k, v in sorted(request.query_params.items())),
        resultados=total,
    )
    return _fhir(recursos.bundle([recursos.patient(c) for c in filas], total=total))


# --------------------------------------------------------------------------- #
# Encounter
# --------------------------------------------------------------------------- #
def _casos(request):
    return Caso.objects.select_related(
        "institucion", "area_actual", "version__flujo", "ciudadano"
    ).filter(institucion__in=_instituciones(request))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encounter_read(request, pk):
    caso = _casos(request).filter(pk=pk).first()
    if caso is None:
        return _error(404, "not-found", "No hay un Encounter con ese id.")

    registrar_acceso(
        request, AccesoClinico.Tipo.DETALLE, "caso",
        ciudadano=caso.ciudadano, objeto_id=caso.id, detalle="fhir Encounter/read",
    )
    return _fhir(recursos.encounter(caso))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encounter_search(request):
    """`GET /fhir/Encounter?patient=<id>&status=<estado FHIR>`"""
    qs = _casos(request)

    paciente = request.query_params.get("patient", "")
    if paciente:
        # FHIR admite `Patient/12` además del id pelado.
        qs = qs.filter(ciudadano_id=paciente.split("/")[-1])

    estado = request.query_params.get("status", "").strip()
    if estado:
        # Se traduce al revés desde el estado FHIR: varios estados de Cauce caen
        # en `in-progress`, así que filtrar por el texto crudo no encontraría
        # nada aunque haya casos que corresponden.
        propios = [c for c, f in recursos.ESTADO_ENCOUNTER.items() if f == estado]
        qs = qs.filter(estado__in=propios) if propios else qs.none()

    filas = list(qs[:TOPE])
    total = qs.count()

    ciudadano = filas[0].ciudadano if (paciente and filas) else None
    registrar_acceso(
        request, AccesoClinico.Tipo.LISTADO, "caso",
        ciudadano=ciudadano,
        detalle="fhir Encounter/search "
                + " ".join(f"{k}={v}" for k, v in sorted(request.query_params.items())),
        resultados=total,
    )
    return _fhir(recursos.bundle([recursos.encounter(c) for c in filas], total=total))


# --------------------------------------------------------------------------- #
# Organization
# --------------------------------------------------------------------------- #
#
# No se audita: una institución no es dato clínico de nadie. Meterla en el
# registro de accesos lo llenaría de ruido y taparía justamente las lecturas que
# hay que poder encontrar.
@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def organization_read(request, pk):
    i = _instituciones(request).filter(pk=pk).first()
    if i is None:
        return _error(404, "not-found", "No hay una Organization con ese id.")
    return _fhir(recursos.organization(i))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def organization_search(request):
    qs = _instituciones(request)
    return _fhir(recursos.bundle([recursos.organization(i) for i in qs[:TOPE]], total=qs.count()))


# --------------------------------------------------------------------------- #
# Lo que no está
# --------------------------------------------------------------------------- #
@fuera_del_openapi
@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def no_soportado(request, tipo=None, pk=None):
    """
    Cualquier otro recurso o cualquier escritura.

    Contesta en FHIR y dice qué SÍ hay. Un 404 de Django acá manda a alguien a
    revisar su cliente durante media hora buscando un error que no es suyo.
    """
    if request.method != "GET":
        return _error(
            405, "not-supported",
            "Esta fachada es de sólo lectura. Escribir datos clínicos por fuera del "
            "motor dejaría el episodio sin línea de tiempo ni sellado de integridad; "
            "para escribir desde afuera se usa un nodo de integración del flujo.",
        )
    return _error(
        404, "not-supported",
        f"«{tipo}» no está implementado. Este servidor expone Patient, Encounter y "
        f"Organization; el detalle está en /fhir/metadata.",
    )
