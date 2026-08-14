"""
Traducción de los datos de Cauce a recursos FHIR R4.

**Por qué existe esto.** «¿Se integra con nuestro sistema?» es la primera
pregunta del área de sistemas de cualquier organismo, y hasta acá la respuesta
era «hay una API REST». Es cierto y no alcanza: una API propia obliga al otro
lado a escribir un adaptador para Cauce. FHIR es el idioma que ya hablan, y
hablarlo convierte semanas de integración en configurar una URL.

**Qué NO hace esto, dicho antes de que alguien lo suponga.**

  · No inventa códigos. Donde Cauce guarda texto libre —«obra social: OSDE»,
    «condiciones: hipertensión»— se emite texto libre. Poner eso bajo un
    `system` de SNOMED o de la nomenclatura nacional daría un dato que parece
    codificado y no lo está, y del otro lado alguien lo va a procesar como si
    lo estuviera. Un campo vacío se nota; uno mal codificado, no.

  · No cubre FHIR entero. Se mapea lo que Cauce realmente tiene: quién es la
    persona (Patient), dónde se la atendió (Organization) y qué episodio de
    atención hubo (Encounter). Anunciar recursos que devuelven cáscaras vacías
    es peor que declarar tres y que funcionen.

  · No es escritura. Ver el módulo de vistas.

Perfil: FHIR R4 (4.0.1).
"""

# Sistema de identificación del documento argentino. Es el `system` que
# corresponde a un DNI y no uno inventado: si el otro lado busca por documento
# tiene que poder decir en qué padrón está ese número.
SISTEMA_DNI = "http://www.renaper.gob.ar/dni"

# Los identificadores propios de Cauce van bajo una URN de la institución que
# corre el sistema. No se usa una URL http: sugeriría que hay algo publicado ahí.
SISTEMA_LOCAL = "urn:cauce:id"

VERSION_FHIR = "4.0.1"


def _instante(dt):
    """FHIR pide ISO 8601 con zona; sin zona el otro lado adivina, y adivina mal."""
    return dt.isoformat() if dt else None


# --------------------------------------------------------------------------- #
# Patient
# --------------------------------------------------------------------------- #
def patient(c) -> dict:
    """
    Un `Ciudadano` como `Patient`.

    `name` va como lista porque FHIR contempla que una persona tenga varios
    nombres (de nacimiento, de casada, el que usa). Cauce guarda uno solo: se
    emite uno solo, con `use: official`, en vez de fingir que hay más.
    """
    identificadores = []
    if c.documento:
        identificadores.append({
            "use": "official",
            "system": SISTEMA_DNI,
            "value": c.documento,
        })
    if c.codigo:
        identificadores.append({"system": f"{SISTEMA_LOCAL}:ciu", "value": c.codigo})
    # El id interno va SIEMPRE: sin él, un paciente sin documento ni código no
    # tendría con qué ser referenciado desde su propio Encounter.
    identificadores.append({"system": f"{SISTEMA_LOCAL}:ciudadano", "value": str(c.id)})

    recurso = {
        "resourceType": "Patient",
        "id": str(c.id),
        "identifier": identificadores,
        "active": True,
        "name": [{
            "use": "official",
            "family": c.apellido or "",
            "given": [c.nombre] if c.nombre else [],
            "text": f"{c.nombre} {c.apellido}".strip(),
        }],
        "managingOrganization": {
            "reference": f"Organization/{c.institucion_id}",
            "display": c.institucion.nombre if c.institucion_id else None,
        },
    }
    if c.fecha_nacimiento:
        recurso["birthDate"] = c.fecha_nacimiento.isoformat()
    if c.domicilio:
        recurso["address"] = [{"use": "home", "text": c.domicilio}]

    # La cobertura NO va como `Coverage`: ese recurso pide plan, período y
    # pagador, y Cauce tiene el nombre de la obra social escrito a mano. Se
    # emite como una extensión con el texto tal cual está, que es lo que hay.
    if c.obra_social:
        recurso["extension"] = [{
            "url": f"{SISTEMA_LOCAL}:obra-social",
            "valueString": c.obra_social,
        }]

    # `gender` no se emite: Cauce no lo guarda. Mandar "unknown" sería afirmar
    # que se preguntó y no se sabe, cuando en realidad nunca se preguntó.
    return recurso


# --------------------------------------------------------------------------- #
# Organization
# --------------------------------------------------------------------------- #
def organization(i) -> dict:
    recurso = {
        "resourceType": "Organization",
        "id": str(i.id),
        "active": i.activa,
        "name": i.nombre,
        "identifier": [{"system": f"{SISTEMA_LOCAL}:institucion", "value": str(i.id)}],
    }
    if i.cuit:
        recurso["identifier"].append({
            "system": "http://www.afip.gob.ar/cuit", "value": i.cuit,
        })
    if i.tipo:
        # Sin `system`: el tipo de establecimiento es texto libre en Cauce y no
        # hay forma honesta de mapearlo a la tabla de FHIR sin adivinar.
        recurso["type"] = [{"text": i.tipo}]
    if i.direccion:
        recurso["address"] = [{"text": i.direccion}]
    return recurso


# --------------------------------------------------------------------------- #
# Encounter
# --------------------------------------------------------------------------- #
#
# El estado del caso en Cauce y el de un Encounter no son la misma escala, y
# forzarlos uno a uno perdería lo que importa. Lo que un sistema externo
# necesita saber es si el episodio está abierto, terminado o anulado.
#
# `derivado` mapea a `in-progress` y no a `finished`: para el paciente el
# episodio sigue abierto, sólo que en otra área. Marcarlo terminado haría que el
# otro lado cerrara el registro de alguien que todavía está siendo atendido.
ESTADO_ENCOUNTER = {
    "recibido": "arrived",
    "en_evaluacion": "in-progress",
    "en_espera": "in-progress",
    "derivado": "in-progress",
    "atendido": "in-progress",
    "cerrado": "finished",
    "cancelado": "cancelled",
}

# La prioridad sí tiene tabla estándar y vale usarla: es de las pocas cosas que
# un sistema externo puede accionar sin conocer nada de Cauce.
PRIORIDAD = {
    "normal": ("R", "routine"),
    "alta": ("UR", "urgent"),
    "urgente": ("EM", "emergency"),
}


def encounter(caso) -> dict:
    recurso = {
        "resourceType": "Encounter",
        "id": str(caso.id),
        "identifier": [{"system": f"{SISTEMA_LOCAL}:caso", "value": str(caso.id)}],
        "status": ESTADO_ENCOUNTER.get(caso.estado, "unknown"),
        # `class` es obligatorio en R4. Cauce no distingue ambulatorio de
        # internación a nivel del caso —lo dice la cama, si la hay—, así que se
        # emite lo que se puede sostener.
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "IMP" if _tiene_cama(caso) else "AMB",
            "display": "inpatient encounter" if _tiene_cama(caso) else "ambulatory",
        },
        "subject": (
            {"reference": f"Patient/{caso.ciudadano_id}"} if caso.ciudadano_id else None
        ),
        "serviceProvider": {"reference": f"Organization/{caso.institucion_id}"},
        "period": {"start": _instante(caso.creado)},
    }

    codigo, display = PRIORIDAD.get(caso.prioridad, PRIORIDAD["normal"])
    recurso["priority"] = {
        "coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActPriority",
            "code": codigo,
            "display": display,
        }],
    }

    # El fin del período sólo se declara si el episodio terminó de verdad. Un
    # `end` puesto «por las dudas» con la fecha de última modificación haría que
    # el otro lado creyera cerrado un caso abierto.
    if caso.estado in ("cerrado", "cancelado"):
        recurso["period"]["end"] = _instante(caso.actualizado)

    if caso.area_actual_id:
        recurso["location"] = [{
            "location": {"display": caso.area_actual.nombre},
            "status": "active",
        }]

    # De qué se trata: el flujo que se está corriendo. Sin `system`, por lo
    # mismo de siempre — es el título que escribió quien diseñó el circuito.
    titulo = getattr(getattr(caso.version, "flujo", None), "titulo", "")
    if titulo:
        recurso["serviceType"] = {"text": titulo}

    return {k: v for k, v in recurso.items() if v is not None}


def _tiene_cama(caso) -> bool:
    """
    ¿El caso tiene una cama abierta?

    Usa la anotación `_internado` cuando viene del listado, que la trae para
    todos de una sola consulta. La consulta suelta queda como respaldo para
    cuando se serializa un caso que no salió de ese queryset.
    """
    anotado = getattr(caso, "_internado", None)
    if anotado is not None:
        return bool(anotado)
    return caso.estadias.filter(hasta__isnull=True).exists()


# --------------------------------------------------------------------------- #
# Sobres
# --------------------------------------------------------------------------- #
def bundle(recursos, total=None, tipo="searchset") -> dict:
    """
    El sobre de una búsqueda.

    Un cliente FHIR espera SIEMPRE un Bundle en una búsqueda, aunque no haya
    resultados. Devolver una lista pelada, o un 404 cuando no hay nada, rompe
    clientes que por lo demás funcionarían: «ninguno» es un resultado válido.
    """
    lista = list(recursos)
    return {
        "resourceType": "Bundle",
        "type": tipo,
        "total": len(lista) if total is None else total,
        "entry": [{"resource": r} for r in lista],
    }


def operation_outcome(severidad, codigo, mensaje) -> dict:
    """
    El error, en el formato en que un cliente FHIR sabe leerlo.

    Un 404 con el JSON de error de Django obliga al otro lado a escribir un caso
    especial para Cauce, que es justamente lo que esta fachada existe para
    evitar.
    """
    return {
        "resourceType": "OperationOutcome",
        "issue": [{
            "severity": severidad,
            "code": codigo,
            "diagnostics": mensaje,
        }],
    }
