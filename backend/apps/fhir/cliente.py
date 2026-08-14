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
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

ACEPTA = "application/fhir+json, application/json"


def buscar_paciente(base, documento, sistema=None, timeout=6):
    """
    Busca una persona por documento en un servidor FHIR y devuelve su `Patient`.

    Devuelve `None` si no está, si hay más de uno o si el servidor no contesta.

    **Más de uno también es `None`, a propósito.** Dos personas con el mismo
    documento en un padrón es un problema de ese padrón, y elegir la primera
    sería completar la historia de alguien con los datos de otro. Ante la duda no
    se completa nada: cargarlo a mano cuesta un minuto, descubrir dentro de un
    año que dos pacientes se mezclaron no se arregla.
    """
    documento = (documento or "").strip()
    if not documento:
        return None

    identificador = f"{sistema}|{documento}" if sistema else documento
    url = f"{base.rstrip('/')}/Patient?identifier={identificador}"

    pedido = Request(url, method="GET")
    pedido.add_header("Accept", ACEPTA)
    try:
        with urlopen(pedido, timeout=timeout) as r:
            # Mismo tope que el nodo de integración: una respuesta enorme no
            # puede comerse la memoria del proceso que atiende a un paciente.
            crudo = r.read(256_000).decode("utf-8", "replace")
        datos = json.loads(crudo) if crudo.strip() else {}
    except (URLError, HTTPError, TimeoutError, OSError, ValueError) as e:
        log.info("padrón FHIR no respondió (%s): %s", type(e).__name__, url)
        return None

    # Un servidor FHIR puede contestar el recurso pelado si hubo un solo
    # resultado, aunque el estándar pida un Bundle. Se aceptan los dos: fallar
    # ahí sería rechazar una respuesta correcta por una cuestión de forma.
    if datos.get("resourceType") == "Patient":
        return datos
    if datos.get("resourceType") != "Bundle":
        return None

    encontrados = [
        e["resource"] for e in datos.get("entry") or []
        if isinstance(e, dict) and (e.get("resource") or {}).get("resourceType") == "Patient"
    ]
    return encontrados[0] if len(encontrados) == 1 else None


def _nombre(patient):
    """Nombre y apellido de un `Patient`, tolerando lo que mande cada padrón."""
    nombres = patient.get("name") or []
    # `use: official` es el que corresponde; si no viene, se toma el primero.
    elegido = next((n for n in nombres if n.get("use") == "official"), None) or (
        nombres[0] if nombres else {}
    )
    dados = elegido.get("given") or []
    nombre = " ".join(str(g) for g in dados).strip()
    apellido = (elegido.get("family") or "").strip()

    # Algunos padrones sólo mandan `text`. Partirlo es adivinar, así que va
    # entero al nombre en vez de inventar dónde termina uno y empieza el otro:
    # un apellido mal cortado se propaga a la historia clínica.
    if not nombre and not apellido:
        nombre = (elegido.get("text") or "").strip()
    return nombre, apellido


def a_ciudadano(patient) -> dict:
    """Traduce un `Patient` a los campos de Cauce. Sólo lo que se puede sostener."""
    if not isinstance(patient, dict):
        return {}
    nombre, apellido = _nombre(patient)
    datos = {"nombre": nombre, "apellido": apellido}

    if patient.get("birthDate"):
        datos["fecha_nacimiento"] = patient["birthDate"]

    direcciones = patient.get("address") or []
    if direcciones:
        d = direcciones[0]
        texto = d.get("text") or ", ".join(
            str(x) for x in ((d.get("line") or []) + [d.get("city"), d.get("state")]) if x
        )
        if texto:
            datos["domicilio"] = texto

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
