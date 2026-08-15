"""
La otra mitad del conector: consultar un padrón FHIR ajeno.

La fachada (`views.py`) deja que otros lean lo de Cauce. Esto es al revés: un
paso del flujo consulta un servidor FHIR externo —el padrón provincial, SISA, la
obra social— y completa los datos del paciente que está siendo atendido.

Es el caso concreto de una guardia: la persona llega con el documento y nada
más. Cargar a mano nombre, fecha de nacimiento y cobertura es lo que hace que un
ingreso tarde tres minutos en vez de veinte segundos, y lo que produce los
registros duplicados con el apellido mal escrito.

Se monta sobre el nodo de integración que ya existe, no al lado: la lista blanca
de destinos, el timeout y el tope de lectura son los mismos. Un segundo camino
de salida a internet sería un segundo lugar donde olvidarse de restringirlo.
"""
import json
import logging
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

ACEPTA = "application/fhir+json, application/json"

# Por qué falló la consulta al padrón. Las cuatro primeras son problemas del
# servicio o de la red; sólo `ambiguo` y `sin_resultados` hablan del documento de
# esta persona. Sin esta distinción, la Trazabilidad del caso dice «no se
# encontró una persona única para ese documento» cuando el padrón estaba caído,
# y el administrativo del mostrador le pide el DNI otra vez a alguien que lo
# tenía bien: si el padrón provincial se cae un martes, quedan 80 ingresos
# diciendo, uno por uno, que el paciente estaba mal identificado.
MOTIVOS = {
    "sin_documento": "no hay documento con qué buscar en el padrón",
    "sin_conexion": "el padrón no respondió a tiempo",
    "no_autorizado": "el padrón rechazó la consulta (credenciales o permisos)",
    "respuesta_invalida": "el padrón contestó algo que no es una respuesta FHIR",
    "sin_resultados": "el padrón no tiene a nadie con ese documento",
    "ambiguo": "el padrón devolvió más de una persona con ese documento: no se completó nada a propósito",
}


def buscar_paciente(base, documento, sistema=None, timeout=6):
    """
    Busca una persona por documento en un servidor FHIR y devuelve su `Patient`.

    Devuelve `None` si no está, si hay más de uno o si el servidor no contesta.
    Para saber CUÁL de esas cosas pasó —que es lo que hay que mostrarle a quien
    está en el mostrador— está `buscar_paciente_con_motivo`.
    """
    return buscar_paciente_con_motivo(base, documento, sistema=sistema, timeout=timeout)[0]


def buscar_paciente_con_motivo(base, documento, sistema=None, timeout=6):
    """
    Igual que `buscar_paciente`, pero devuelve `(patient, motivo)`.

    `motivo` es una clave de `MOTIVOS` cuando no hubo resultado, y `None` cuando
    sí lo hubo. Existe porque las cuatro fallas posibles no se arreglan igual:
    «el padrón no respondió» es para sistemas y «el padrón devolvió dos personas
    con ese documento» es lo único que justifica que alguien mire el DNI del
    paciente. Un único texto para todas manda a revisar el documento de alguien
    cada vez que se cae un servidor.

    **Más de uno es `None`, a propósito.** Dos personas con el mismo documento en
    un padrón es un problema de ese padrón, y elegir la primera sería completar
    la historia de alguien con los datos de otro. Ante la duda no se completa
    nada: cargarlo a mano cuesta un minuto, descubrir dentro de un año que dos
    pacientes se mezclaron no se arregla.
    """
    documento = (documento or "").strip()
    if not documento:
        return None, "sin_documento"

    # El valor va codificado: un documento tipeado «30 111 222» en el mostrador
    # arma una URL con un espacio y `http.client` levanta InvalidURL, que NO es
    # OSError y por lo tanto se escapaba del except de abajo hasta el
    # `@transaction.atomic` del motor — el ingreso entero se caía con 500 y el
    # caso quedaba sin nodo y sin un solo evento que explicara por qué. Y un `#`
    # en el documento urllib lo trata como fragmento y lo descarta, o sea que se
    # consultaba por una persona distinta de la que se pidió.
    # `|`, `:` y `/` son legales dentro de un valor de query y son justamente los
    # que forman un `system` (`http://www.renaper.gob.ar/dni|30111222`): dejarlos
    # tal cual mantiene la URL legible en un log. Lo que se codifica es lo que
    # rompe —espacios, `#`, `&`, `=`—.
    crudo_id = f"{sistema}|{documento}" if sistema else documento
    url = f"{base.rstrip('/')}/Patient?identifier={quote(crudo_id, safe='|:/')}"

    try:
        pedido = Request(url, method="GET")
        pedido.add_header("Accept", ACEPTA)
        with urlopen(pedido, timeout=timeout) as r:
            # Mismo tope que el nodo de integración: una respuesta enorme no
            # puede comerse la memoria del proceso que atiende a un paciente.
            crudo = r.read(256_000).decode("utf-8", "replace")
        datos = json.loads(crudo) if crudo.strip() else {}
    except HTTPError as e:
        log.info("padrón FHIR rechazó la consulta (%s): %s", e.code, url)
        return None, "no_autorizado" if e.code in (401, 403) else "sin_conexion"
    except (URLError, TimeoutError, OSError, HTTPException) as e:
        log.info("padrón FHIR no respondió (%s): %s", type(e).__name__, url)
        return None, "sin_conexion"
    except ValueError as e:
        log.info("padrón FHIR contestó algo ilegible (%s): %s", type(e).__name__, url)
        return None, "respuesta_invalida"

    if not isinstance(datos, dict):
        return None, "respuesta_invalida"

    # Un servidor FHIR puede contestar el recurso pelado si hubo un solo
    # resultado, aunque el estándar pida un Bundle. Se aceptan los dos: fallar
    # ahí sería rechazar una respuesta correcta por una cuestión de forma.
    if datos.get("resourceType") == "Patient":
        return datos, None
    if datos.get("resourceType") != "Bundle":
        return None, "respuesta_invalida"

    encontrados = [
        e["resource"] for e in datos.get("entry") or []
        if isinstance(e, dict) and isinstance(e.get("resource"), dict)
        and e["resource"].get("resourceType") == "Patient"
    ]
    if len(encontrados) == 1:
        return encontrados[0], None
    return None, "ambiguo" if encontrados else "sin_resultados"


def _lista_de_textos(valor):
    """
    Un campo que FHIR define como lista de strings, venga como venga.

    Hay padrones reales que mandan `"given": "Juan"` en vez de `["Juan"]`.
    Iterar eso directo recorre CARACTERES y el paciente queda anotado como
    «J u a n» en su historia clínica; y como `completar` nunca pisa un campo que
    ya tiene algo —que está bien—, esa basura queda blindada para siempre: buscar
    «Juan» ya no lo encuentra, se lo carga de nuevo y quedan dos historias
    clínicas de la misma persona.
    """
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, list):
        return [v for v in valor if isinstance(v, str)]
    return []


def _nombre(patient):
    """Nombre y apellido de un `Patient`, tolerando lo que mande cada padrón."""
    nombres = [n for n in (patient.get("name") or []) if isinstance(n, dict)]
    # `use: official` es el que corresponde; si no viene, se toma el primero.
    elegido = next((n for n in nombres if n.get("use") == "official"), None) or (
        nombres[0] if nombres else {}
    )
    nombre = " ".join(_lista_de_textos(elegido.get("given"))).strip()
    # `family` es un string en el estándar, pero llega como lista lo bastante
    # seguido: sin esto es un AttributeError que sube hasta el motor y tumba el
    # ingreso entero, no un nombre que falta.
    familias = _lista_de_textos(elegido.get("family"))
    apellido = (familias[0] if familias else "").strip()

    # Algunos padrones sólo mandan `text`. Partirlo es adivinar, así que va
    # entero al nombre en vez de inventar dónde termina uno y empieza el otro:
    # un apellido mal cortado se propaga a la historia clínica.
    if not nombre and not apellido:
        texto = elegido.get("text")
        nombre = texto.strip() if isinstance(texto, str) else ""
    return nombre, apellido


def _fecha(valor):
    """
    La `birthDate` que mandó el padrón, sólo si Cauce puede sostenerla.

    FHIR R4 admite fechas parciales —`1985` y `1985-03` son válidas y frecuentes
    en padrones— y el `DateField` de Cauce no. Guardarlas tal cual levanta
    ValidationError dentro del `@transaction.atomic` del motor: el ingreso
    contesta 500 y el caso queda sin nodo, sin eventos y sin explicación, con el
    checkbox «detener si falla» destildado. Una fecha parcial es un dato que
    Cauce no puede representar; vacío se nota, inventado no.
    """
    from django.utils.dateparse import parse_date

    if not isinstance(valor, str):
        return None
    try:
        return parse_date(valor.strip())
    except ValueError:  # bien formada pero imposible: «1985-02-30»
        return None


def _recortado(campo, texto):
    """
    El texto, cortado al largo de la columna.

    Un `family` de 300 caracteres da `DataError: value too long` y aborta la
    transacción de Postgres, o sea que se lleva puesto el ingreso entero por un
    dato ajeno mal cargado. El largo sale del modelo y no de un número escrito
    acá: si mañana la columna se agranda, esto la sigue.
    """
    from apps.registros.models import Ciudadano

    tope = Ciudadano._meta.get_field(campo).max_length
    return texto[:tope] if tope else texto


def a_ciudadano(patient) -> dict:
    """
    Traduce un `Patient` a los campos de Cauce. Sólo lo que se puede sostener.

    Acá entra el dato ajeno, así que acá se sanea: lo que sale de esta función
    tiene que poder guardarse sin que el padrón pueda tumbar un ingreso.
    """
    if not isinstance(patient, dict):
        return {}
    nombre, apellido = _nombre(patient)
    datos = {"nombre": _recortado("nombre", nombre), "apellido": _recortado("apellido", apellido)}

    fecha = _fecha(patient.get("birthDate"))
    if fecha:
        datos["fecha_nacimiento"] = fecha.isoformat()

    direcciones = [d for d in (patient.get("address") or []) if isinstance(d, dict)]
    if direcciones:
        d = direcciones[0]
        texto = d.get("text") if isinstance(d.get("text"), str) else None
        texto = texto or ", ".join(
            str(x) for x in (_lista_de_textos(d.get("line")) + [d.get("city"), d.get("state")])
            if isinstance(x, str) and x
        )
        if texto:
            datos["domicilio"] = _recortado("domicilio", texto)

    return {k: v for k, v in datos.items() if v}


# Campos que se pueden completar desde un padrón. `documento` NO está: es lo que
# se usó para buscar, y pisarlo con lo que devolvió la búsqueda es circular.
COMPLETABLES = ("nombre", "apellido", "fecha_nacimiento", "domicilio")


def completar(ciudadano, patient) -> list:
    """
    Rellena los campos VACÍOS del paciente. Devuelve cuáles se completaron.

    **Nunca pisa un dato cargado.** Lo que una persona dijo en el mostrador vale
    más que lo que dice un padrón: los padrones tienen domicilios de hace quince
    años y nombres sin actualizar después de un casamiento o un cambio registral.
    Y sobre todo: cambiar en silencio el nombre o la fecha de nacimiento de
    alguien que ya fue identificado en persona es como un paciente termina con
    los datos de otro, sin que nadie vea el momento en que pasó.

    Si el padrón contradice lo cargado, eso se mira y se decide; no se aplica
    solo.
    """
    nuevos = a_ciudadano(patient)
    completados = []
    for campo in COMPLETABLES:
        if campo not in nuevos:
            continue
        actual = getattr(ciudadano, campo, None)
        if actual:  # ya tiene algo: se respeta
            continue
        setattr(ciudadano, campo, nuevos[campo])
        completados.append(campo)

    if completados:
        ciudadano.save(update_fields=completados)
    return completados
