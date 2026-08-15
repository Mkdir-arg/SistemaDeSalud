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
from urllib.parse import urlencode

from django.http import JsonResponse
from django.urls import reverse
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.auditoria.mixins import registrar_acceso
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso
from apps.common import capacidades_de
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano, normalizar_documento

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

# Los recursos que esta fachada expone de verdad. Se usa para no contestarle a un
# cliente que Patient no existe cuando lo que pasó es que el id no tiene forma.
IMPLEMENTADOS = ("Patient", "Encounter", "Organization")

# Hasta cuántas filas de una búsqueda por identificador se anotan como lectura
# de ESAS personas. Una persona registrada en varias instituciones de la red
# devuelve una fila por institución: siguen siendo pocas y siguen siendo ella.
# Más que un puñado ya no es leer a alguien, es listar.
POCAS = 10


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


def _id_sin_forma(tipo, pk):
    """
    404 para un id que no puede existir, sin negar que el recurso exista.

    En FHIR el `id` es una cadena, así que `Patient/abc` y `Patient/12/_history`
    son pedidos bien formados que un cliente arma solo. Contestar «Patient no
    está implementado» contradice el CapabilityStatement que ese mismo cliente
    leyó treinta segundos antes, y el integrador —que es quien decide si la
    prueba sigue— no tiene motivo para dudar: da la integración por descartada.
    """
    ruta = f"{tipo}/{pk}" if pk else f"{tipo}/"
    return _error(
        404, "not-found",
        f"«{tipo}» sí está implementado, pero «{ruta}» no es una ruta de este "
        f"servidor. Los id de Cauce son numéricos ({tipo}/12), la búsqueda va sin "
        f"barra final ({tipo}?…) y no hay operaciones ni sufijos del estándar "
        f"(_history, _search); lo que sí hay está en /fhir/metadata.",
    )


def _falta_capacidad(request, capacidad):
    """
    El OTRO eje del permiso: no dónde, sino qué rol.

    El alcance por institución no alcanza. `CiudadanoViewSet` exige la capacidad
    `registros` incluso para LEER (`protege_lectura`), así que sin esto un
    usuario con rol `configurador` —que existe justamente para dibujar flujos sin
    tocar datos clínicos— recibe 403 en `/api/ciudadanos/` y se baja el padrón
    entero por `/fhir/Patient` con su propio token. Se consulta la MISMA fuente
    de verdad que los viewsets (`capacidades_de`), no una copia: una segunda
    tabla de roles es un segundo lugar donde olvidarse de actualizarla.
    """
    if capacidad in capacidades_de(request.user):
        return None
    return _error(
        403, "forbidden",
        f"Tu rol no tiene la capacidad «{capacidad}», que es la que habilita estos datos "
        f"en Cauce. Es el mismo permiso que pide la API interna: la fachada FHIR no es "
        f"una puerta con otras reglas.",
    )


# Parámetros que toda búsqueda acepta además de los suyos. `_format` lo manda
# cualquier cliente FHIR y no cambia nada acá: siempre se contesta JSON.
COMUNES = {"_count", "_offset", "_format", "_pretty"}


def _paginacion(request):
    """
    `(offset, count)` de esta búsqueda, dentro del tope.

    Sin esto, `_offset` se ignoraba y la segunda página era idéntica a la
    primera: el cliente que sincroniza de a cien se lleva los mismos cien
    registros dos veces y cree que terminó, porque el `total` que declara el
    Bundle sí es el real.
    """
    def entero(nombre, defecto):
        crudo = (request.query_params.get(nombre) or "").strip()
        return int(crudo) if crudo.isdigit() else defecto

    return max(entero("_offset", 0), 0), min(entero("_count", TOPE), TOPE)


def _enlaces(request, offset, count, devueltas, total):
    """
    `self` y `next` del Bundle.

    El tope está bien puesto; lo que lo convierte en truncamiento silencioso es
    no decir que hay más. Sin `next`, un hospital de 250 pacientes sincroniza 100
    y del otro lado nadie se entera.
    """
    base = request.build_absolute_uri(request.path)
    parametros = {k: v for k, v in request.query_params.items() if k not in ("_count", "_offset")}
    enlaces = [{"relation": "self", "url": f"{base}?{urlencode({**parametros, '_count': count, '_offset': offset})}"}]
    if offset + devueltas < total and devueltas:
        enlaces.append({
            "relation": "next",
            "url": f"{base}?{urlencode({**parametros, '_count': count, '_offset': offset + devueltas})}",
        })
    return enlaces


def _ignorados(request, soportados):
    """
    Los parámetros que esta búsqueda NO sabe aplicar.

    Se devuelven como aviso dentro del Bundle (`handling=lenient` del estándar)
    en vez de descartarlos callado: `?date=ge2099-01-01` contestando 200 con
    todos los episodios del hospital es indistinguible de una respuesta buena, y
    la sincronización nocturna del ministerio carga la historia entera como si
    fuera de ayer. Nadie lo descubre hasta comparar números meses después.
    """
    return sorted(k for k in request.query_params if k not in soportados and k not in COMUNES)


def _aviso_ignorados(nombres):
    if not nombres:
        return []
    return [recursos.operation_outcome(
        "warning", "not-supported",
        "Esta búsqueda no aplicó " + ", ".join(nombres) + ": este servidor no los implementa, "
        "así que el resultado NO está filtrado por esos parámetros. Los que sí acepta cada "
        "recurso están en /fhir/metadata.",
    )]


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
                "para escribir desde afuera se usa un nodo de integración del flujo. "
                f"Las búsquedas devuelven como máximo {TOPE} recursos por página: se "
                "paginan con _count y _offset y se sigue el link 'next' del Bundle "
                "hasta que no venga. Un parámetro de búsqueda que este servidor no "
                "implemente NO se aplica en silencio: vuelve como OperationOutcome de "
                "severidad warning dentro del Bundle."
            ),
            "security": {"description": "Bearer JWT. Alcance limitado a las instituciones del usuario."},
            "resource": [
                {
                    "type": "Patient",
                    "interaction": [{"code": "read"}, {"code": "search-type"}],
                    "searchParam": [
                        {"name": "identifier", "type": "token",
                         "documentation": (
                             f"Documento. Ej.: {recursos.SISTEMA_DNI}|30111222, o el número "
                             f"solo. También se buscan los identificadores que emite Cauce: "
                             f"{recursos.SISTEMA_LOCAL}:ciu y {recursos.SISTEMA_LOCAL}:ciudadano. "
                             f"Con cualquier otro sistema la respuesta es un Bundle vacío: "
                             f"contestar la persona con ese documento sería devolver a otra."
                         )},
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
def _por_identificador(qs, identificador):
    """
    Filtra por `identifier`, respetando el `system` cuando viene.

    Cada sistema apunta a una columna distinta. Un sistema que no es ninguno de
    estos NO se busca por documento «total el número está»: el sistema del
    organismo pregunta por número de afiliado o por su propia historia clínica,
    recibiría 200 con la persona cuyo DNI coincide y la asociaría al episodio
    equivocado. Del otro lado no hay nadie mirando.
    """
    sistema, marca, valor = identificador.rpartition("|")
    valor = valor.strip()
    if not valor:
        return qs.none()
    if not marca or sistema == recursos.SISTEMA_DNI:
        # Sin sistema es el caso que el estándar contempla y el más común.
        # `normalizar_documento` es la misma función con la que se guarda: sin
        # ella, un documento escrito «7.775.258» del otro lado no encuentra nada.
        return qs.filter(documento=normalizar_documento(valor))
    if sistema == f"{recursos.SISTEMA_LOCAL}:ciu":
        return qs.filter(codigo=valor)
    if sistema == f"{recursos.SISTEMA_LOCAL}:ciudadano":
        # Los identificadores que Cauce mismo emite tienen que poder volver a
        # buscarse; hasta acá `urn:cauce:id:ciudadano|28` devolvía a la persona
        # con documento 28.
        return qs.filter(pk=valor) if valor.isdigit() else qs.none()
    return qs.none()


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_read(request, pk):
    if (negado := _falta_capacidad(request, "registros")) is not None:
        return negado
    if not str(pk).isdigit():
        return _id_sin_forma("Patient", pk)
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
    `GET /fhir/Patient?identifier=[<sistema>|]<documento>&family=<apellido>`

    El `identifier` de FHIR viene como `sistema|valor`, y el sistema es
    opcional. Se acepta SIN sistema: exigirlo haría fallar consultas correctas
    por una cuestión de forma.

    Ahora bien, si el sistema VIENE, se respeta. Ignorarlo y buscar siempre por
    documento es lo que hacía que pedir por número de afiliado, por pasaporte o
    por la historia clínica del otro organismo devolviera 200 y la persona cuyo
    DNI coincide con ese número: otra persona, presentada como coincidencia. Un
    Bundle vacío el otro lado lo sabe manejar; una identidad equivocada, no.
    """
    if (negado := _falta_capacidad(request, "registros")) is not None:
        return negado

    # Desempate por id: `Ciudadano` ordena por apellido y nombre, que no son
    # únicos. Paginar sobre un orden con empates hace que una fila aparezca en
    # dos páginas o en ninguna.
    qs = Ciudadano.objects.select_related("institucion").filter(
        institucion__in=_instituciones(request)
    ).order_by("apellido", "nombre", "id")

    identificador = request.query_params.get("identifier", "")
    if identificador:
        qs = _por_identificador(qs, identificador)
    familia = request.query_params.get("family", "").strip()
    if familia:
        qs = qs.filter(apellido__icontains=familia)

    offset, count = _paginacion(request)
    filas = list(qs[offset:offset + count])
    total = qs.count()
    ignorados = _ignorados(request, {"identifier", "family"})

    detalle = ("fhir Patient/search "
               + " ".join(f"{k}={v}" for k, v in sorted(request.query_params.items())))
    # Buscar por identificador y encontrar a UNA persona es leer los datos de esa
    # persona: se anota a su nombre, una línea por cada una. Si no, consultar por
    # documento sería la forma de mirar a alguien sin dejar rastro suyo — y con
    # una sola línea de LISTADO anónima pasaba igual en el escenario de red,
    # donde la misma persona está registrada en dos instituciones (el unique de
    # Ciudadano es institucion+documento) y la búsqueda devuelve dos filas. Esa
    # lectura no aparecía en la lista que la Ley 26.529 le da derecho a pedir al
    # paciente, que se arma filtrando por `ciudadano_id`.
    identificadas = filas if (identificador and 0 < len(filas) <= POCAS) else []
    if identificadas:
        for c in identificadas:
            registrar_acceso(
                request, AccesoClinico.Tipo.DETALLE, "ciudadano",
                ciudadano=c, objeto_id=c.id, detalle=detalle, resultados=total,
            )
    else:
        registrar_acceso(
            request, AccesoClinico.Tipo.LISTADO, "ciudadano",
            detalle=detalle, resultados=total,
        )
    return _fhir(recursos.bundle(
        [recursos.patient(c) for c in filas], total=total,
        enlaces=_enlaces(request, offset, count, len(filas), total),
        avisos=_aviso_ignorados(ignorados),
    ))


# --------------------------------------------------------------------------- #
# Encounter
# --------------------------------------------------------------------------- #
def _casos(request):
    # `_internado` se anota acá y no se consulta por caso: saber si hay cama es
    # una consulta más por fila, y del otro lado de esta fachada hay un sistema
    # que pide de a cien sin mirar. Un N+1 acá no lo sufre una pantalla, lo sufre
    # la base mientras alguien atiende pacientes.
    from django.db.models import Exists, OuterRef

    from apps.instituciones.models import EstadiaCama

    return (
        Caso.objects
        .select_related("institucion", "area_actual", "version__flujo", "ciudadano")
        .annotate(_internado=Exists(
            EstadiaCama.objects.filter(caso=OuterRef("pk"), hasta__isnull=True)
        ))
        .filter(institucion__in=_instituciones(request))
    )


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def encounter_read(request, pk):
    if (negado := _falta_capacidad(request, "trabajo")) is not None:
        return negado
    if not str(pk).isdigit():
        return _id_sin_forma("Encounter", pk)
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
    """`GET /fhir/Encounter?patient=<id>&status=<estado FHIR>[,<otro>]`"""
    if (negado := _falta_capacidad(request, "trabajo")) is not None:
        return negado

    # `Caso` ordena por `-creado`, que no es único: hace falta el desempate para
    # que paginar no repitiera ni salteara episodios.
    qs = _casos(request).order_by("-creado", "-id")

    paciente = request.query_params.get("patient", "")
    if paciente:
        # FHIR admite `Patient/12` además del id pelado.
        ref = paciente.split("/")[-1].strip()
        if not ref.isdigit():
            # El mismo ValueError que ya se arregló en auditoria/mixins.py y
            # volvió a entrar por acá: `?patient=urn:uuid:9` levantaba un 500 de
            # Django, y el integrador del otro lado escala «Cauce se cayó» por un
            # parámetro que la fachada puede rechazar explicando qué mandar.
            return _error(
                400, "value",
                "El parámetro patient tiene que ser el id numérico del Patient, "
                "solo o como Patient/<id>. Este servidor no resuelve identificadores "
                "lógicos ni UUID.",
            )
        qs = qs.filter(ciudadano_id=ref)

    estado = request.query_params.get("status", "").strip()
    if estado:
        # La coma es la sintaxis estándar de FHIR para «o» en un parámetro de
        # tipo token, y `status` está declarado como token en /fhir/metadata.
        # Sin partirla, `status=in-progress,finished` daba total 0: un hospital
        # sin actividad, que es un dato falso y no una carencia.
        pedidos = {e.strip() for e in estado.split(",") if e.strip()}
        # Se traduce al revés desde el estado FHIR: varios estados de Cauce caen
        # en `in-progress`, así que filtrar por el texto crudo no encontraría
        # nada aunque haya casos que corresponden.
        propios = [c for c, f in recursos.ESTADO_ENCOUNTER.items() if f in pedidos]
        qs = qs.filter(estado__in=propios) if propios else qs.none()

    offset, count = _paginacion(request)
    filas = list(qs[offset:offset + count])
    total = qs.count()
    ignorados = _ignorados(request, {"patient", "status"})

    ciudadano = filas[0].ciudadano if (paciente and filas) else None
    registrar_acceso(
        request, AccesoClinico.Tipo.LISTADO, "caso",
        ciudadano=ciudadano,
        detalle="fhir Encounter/search "
                + " ".join(f"{k}={v}" for k, v in sorted(request.query_params.items())),
        resultados=total,
    )
    return _fhir(recursos.bundle(
        [recursos.encounter(c) for c in filas], total=total,
        enlaces=_enlaces(request, offset, count, len(filas), total),
        avisos=_aviso_ignorados(ignorados),
    ))


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
    if not str(pk).isdigit():
        return _id_sin_forma("Organization", pk)
    i = _instituciones(request).filter(pk=pk).first()
    if i is None:
        return _error(404, "not-found", "No hay una Organization con ese id.")
    return _fhir(recursos.organization(i))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def organization_search(request):
    qs = _instituciones(request).order_by("nombre", "id")
    offset, count = _paginacion(request)
    filas = list(qs[offset:offset + count])
    total = qs.count()
    return _fhir(recursos.bundle(
        [recursos.organization(i) for i in filas], total=total,
        enlaces=_enlaces(request, offset, count, len(filas), total),
        avisos=_aviso_ignorados(_ignorados(request, set())),
    ))


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
    # Un recurso que SÍ está implementado no puede salir por acá diciendo lo
    # contrario. Acá caen `Patient/abc`, `Patient/12/_history` y `Patient/_search`
    # —formas que un cliente FHIR arma sin pensarlo, porque el `id` del estándar
    # es una cadena—, y el integrador que treinta segundos antes leyó el
    # CapabilityStatement no tiene motivo para dudar del mensaje: da la
    # integración por descartada.
    if tipo in IMPLEMENTADOS:
        return _id_sin_forma(tipo, pk)
    return _error(
        404, "not-supported",
        f"«{tipo}» no está implementado. Este servidor expone Patient, Encounter y "
        f"Organization; el detalle está en /fhir/metadata.",
    )
