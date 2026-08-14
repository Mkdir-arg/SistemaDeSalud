"""
Motor de ejecución de casos.

Un `Caso` es una instancia de una `VersionFlujo`. El motor lo hace avanzar por
el grafo: ejecuta los nodos automáticos en cadena y se detiene cuando llega a un
nodo que requiere acción humana (formulario, atención), una espera (fila o
tiempo) o el fin del flujo.

Convención de `Nodo.config` por tipo:
  - estado   : {"estado": "<valor de Caso.Estado>"}  ej. "en_espera"
  - derivar  : {"area_destino_id": <id>, "flujo_destino_id": <id>}
  - tiempo   : {"duracion": "1 mes"}  (informativo; la reactivación es externa)
  - atencion : {"plantilla": "evaluación inicial"}

Convención de `Conexion.condicion` (nodos Decisión):

  hoja      {"campo": <id de Campo>, "operador": "=", "valor": "Alta"}
  compuesta {"op": "y" | "o", "reglas": [<hoja o compuesta>, ...]}

  Operadores: "=", "!=", ">", "<", ">=", "<=", "contiene", "no_contiene",
  "en", "no_en", "entre", "vacio", "no_vacio". Los de orden comparan como
  número y, si no se puede, como fecha ISO.

  Las compuestas anidan, así que se puede expresar «(A y B) o C». Una conexión
  sin condición es la rama por defecto (else).
"""
from __future__ import annotations

import contextvars
import json
import re
import unicodedata
from contextlib import contextmanager
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.flujos.models import Conexion, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, EstadiaCama
from apps.registros.models import EntradaHistoria, HistoriaClinica

from .models import Caso, EventoCaso, ItemFila, Notificacion, ValorCampo


class ErrorMotor(Exception):
    """Error de negocio del motor (estado inválido, datos faltantes, etc.)."""


# --------------------------------------------------------------------------- #
# Traza: por qué nodos pasó el motor
# --------------------------------------------------------------------------- #
# La usa el «Probar» del diseñador. Es la ÚNICA forma de que el botón diga la
# verdad: el motor cuenta él mismo por dónde pasó, en vez de que un simulador
# aparte adivine lo mismo con otro código.
#
# Va por `contextvars` y no por parámetro para no ensuciar la firma de media
# docena de funciones. Fuera de un bloque `trazar()` la variable es None y todo
# esto cuesta una comparación por nodo.
_traza = contextvars.ContextVar("motor_traza", default=None)


@contextmanager
def trazar():
    """Recolecta los nodos que atraviesa el motor dentro del bloque."""
    token = _traza.set([])
    try:
        yield _traza.get()
    finally:
        _traza.reset(token)


def _anotar(nodo: Nodo, motivo: str = ""):
    registro = _traza.get()
    if registro is None:
        return
    registro.append({
        "nodo": nodo.pk,
        "titulo": nodo.titulo,
        "tipo": nodo.tipo,
        "motivo": motivo,
    })


# --- Responsabilidad: quién puede ejecutar el paso actual de un caso ---------

def grupos_responsables_ids(caso):
    """IDs de los grupos responsables del paso actual. Vacío = abierto a todos."""
    if not caso.nodo_actual_id:
        return []
    return list(caso.nodo_actual.grupos.values_list("id", flat=True))


def areas_que_supervisa(usuario):
    """IDs de áreas donde `usuario` es jefe/supervisor (membresía activa)."""
    if not getattr(usuario, "is_authenticated", False):
        return set()
    from apps.accounts.models import Membresia
    return set(
        Area.objects.filter(
            miembros__usuario=usuario,
            miembros__rol=Membresia.Rol.JEFE_AREA,
            miembros__activo=True,
        ).values_list("id", flat=True)
    )


def usuario_supervisa(usuario, caso):
    """¿`usuario` es jefe del área del caso? (el super admin supervisa todo)."""
    if getattr(usuario, "is_superuser", False):
        return True
    area_id = caso.area_actual_id or (caso.version.flujo.area_id if caso.version_id else None)
    return area_id is not None and area_id in areas_que_supervisa(usuario)


def usuario_puede_tomar(usuario, caso):
    """
    ¿`usuario` puede tomar/ejecutar el paso actual del `caso`?

    True si el nodo no declara grupos responsables (paso abierto), si el usuario
    integra alguno de esos grupos, o si es super admin de plataforma.
    """
    if getattr(usuario, "is_superuser", False):
        return True
    gids = grupos_responsables_ids(caso)
    if not gids:
        return True
    return usuario.grupos.filter(id__in=gids).exists()


# Nodos que el motor atraviesa solos, sin intervención.
TIPOS_AUTOMATICOS = {
    Nodo.Tipo.INICIO,
    Nodo.Tipo.DECISION,
    Nodo.Tipo.ACCION,
    Nodo.Tipo.DERIVAR,
    Nodo.Tipo.ESTADO,
    Nodo.Tipo.NOTIFICAR,
    Nodo.Tipo.INTEGRACION,
}
# Nodos que detienen el avance hasta un disparador externo.
TIPOS_DETENCION = {
    Nodo.Tipo.FORMULARIO,
    Nodo.Tipo.ATENCION,
    Nodo.Tipo.ESPERA_FILA,
    Nodo.Tipo.ESPERA_TIEMPO,
    Nodo.Tipo.CAMA,
    Nodo.Tipo.FIN,
}


# --------------------------------------------------------------------------- #
# Evaluación de condiciones (decisiones)
# --------------------------------------------------------------------------- #
def _valor_de_campo(caso: Caso, campo_id) -> str | None:
    vc = caso.valores.filter(campo_id=campo_id).first()
    return vc.valor if vc else None


def _plano(texto) -> str:
    """
    Minúsculas y sin tildes, para comparar texto libre.

    En una admisión se escribe «dolor toracico» tanto como «Dolor Torácico», y
    una regla de triage que sólo matchea con la tilde puesta manda al paciente
    por el circuito equivocado sin que nadie se entere. La comparación exacta
    (`=`, `en`) NO pasa por acá: ahí los valores salen de una lista cerrada y
    tienen que coincidir tal cual.
    """
    crudo = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in crudo if unicodedata.category(c) != "Mn").lower()


def _lista(valor) -> list[str]:
    """Normaliza el `valor` de «entre» / «en lista»: acepta lista o texto con comas."""
    if isinstance(valor, (list, tuple)):
        return [str(v).strip() for v in valor]
    return [p.strip() for p in str(valor or "").split(",") if p.strip()]


def _comparables(a, b):
    """
    Devuelve `(a, b)` en un tipo que se pueda ordenar, o None si no se puede.

    Primero número, después fecha ISO. Las fechas hacen falta porque un flujo
    clínico compara fechas todo el tiempo (nacimiento, último control) y hasta
    ahora `>` sobre una fecha devolvía siempre False, en silencio.
    """
    try:
        return float(a), float(b)
    except (TypeError, ValueError):
        pass
    try:
        return date.fromisoformat(str(a)[:10]), date.fromisoformat(str(b)[:10])
    except ValueError:
        return None


def _cumple_simple(condicion: dict, caso: Caso) -> bool:
    """Evalúa UNA condición hoja `{campo, operador, valor}`."""
    operador = condicion.get("operador", "=")
    esperado = condicion.get("valor")
    actual = _valor_de_campo(caso, condicion.get("campo"))

    # Vacío se resuelve antes que nada: «sin cargar» es justamente lo que pregunta,
    # así que no puede caer en el descarte por `actual is None`.
    vacio = actual is None or str(actual).strip() == ""
    if operador == "vacio":
        return vacio
    if operador == "no_vacio":
        return not vacio
    if vacio:
        return False

    if operador == "=":
        return str(actual) == str(esperado)
    if operador == "!=":
        return str(actual) != str(esperado)
    if operador == "contiene":
        return _plano(esperado) in _plano(actual)
    if operador == "no_contiene":
        return _plano(esperado) not in _plano(actual)
    if operador == "en":
        return str(actual) in _lista(esperado)
    if operador == "no_en":
        return str(actual) not in _lista(esperado)
    if operador == "entre":
        limites = _lista(esperado)
        if len(limites) != 2:
            return False
        desde = _comparables(actual, limites[0])
        hasta = _comparables(actual, limites[1])
        if desde is None or hasta is None:
            return False
        return desde[0] >= desde[1] and hasta[0] <= hasta[1]
    if operador in (">", "<", ">=", "<="):
        par = _comparables(actual, esperado)
        if par is None:
            return False
        a, e = par
        if operador == ">":
            return a > e
        if operador == "<":
            return a < e
        if operador == ">=":
            return a >= e
        return a <= e
    return False


def campos_de_condicion(condicion: dict | None) -> set[int]:
    """
    Todos los campos que menciona una condición, recorriendo el árbol.

    La validación previa a publicar avisa cuando una rama usa un campo que
    ningún formulario del flujo carga. Mirando sólo `condicion["campo"]` una
    regla compuesta no tiene campo arriba de todo, así que se salteaba entera y
    el aviso no aparecía nunca: la validación decía «todo bien» sobre una regla
    que en producción no iba a poder evaluarse.
    """
    if not condicion:
        return set()
    if "reglas" in condicion:
        campos: set[int] = set()
        for r in condicion.get("reglas") or []:
            campos |= campos_de_condicion(r)
        return campos
    campo = condicion.get("campo")
    try:
        return {int(campo)} if campo else set()
    except (TypeError, ValueError):
        return set()


def _cumple(condicion: dict, caso: Caso) -> bool:
    """
    Evalúa la condición de una rama contra los valores cargados del caso.

    Admite dos formas, y las dos conviven a propósito:

      hoja      {"campo": 3, "operador": ">", "valor": "65"}
      compuesta {"op": "y", "reglas": [<hoja o compuesta>, ...]}

    La compuesta anida, así que se puede expresar «(A y B) o C». Hacía falta
    porque una decisión clínica real casi nunca es una sola condición: «mayor de
    65 Y dolor torácico» es la regla, no la excepción.

    La forma hoja se conserva porque es la que tienen todas las conexiones ya
    guardadas. Migrarlas no aportaría nada: una hoja es exactamente una
    compuesta de un solo elemento, y sostener las dos cuesta tres líneas.
    """
    if not condicion:
        return True  # rama por defecto (else)
    if "reglas" in condicion:
        reglas = condicion.get("reglas") or []
        if not reglas:
            return True  # compuesta vacía = sin restricción
        combinar = all if condicion.get("op", "y") == "y" else any
        return combinar(_cumple(r, caso) for r in reglas)
    return _cumple_simple(condicion, caso)


def _siguiente_nodo(nodo: Nodo, caso: Caso) -> Nodo | None:
    """
    Devuelve el próximo nodo a partir de `nodo`.

    Para una Decisión, evalúa las condiciones de las conexiones salientes y elige
    la primera que se cumpla; las conexiones con condición tienen prioridad sobre
    la rama por defecto (sin condición).
    """
    salidas = list(
        Conexion.objects.filter(version=caso.version, origen=nodo).select_related("destino")
    )
    if not salidas:
        return None

    if nodo.tipo == Nodo.Tipo.DECISION:
        con_condicion = [c for c in salidas if c.condicion]
        por_defecto = [c for c in salidas if not c.condicion]
        for c in con_condicion:
            if _cumple(c.condicion, caso):
                return c.destino
        if por_defecto:
            return por_defecto[0].destino
        return None  # ninguna rama aplica y no hay default

    return salidas[0].destino


# --------------------------------------------------------------------------- #
# Efectos al entrar a un nodo
# --------------------------------------------------------------------------- #
def _registrar(caso: Caso, titulo: str, detalle: str = "", autor=None, nodo: Nodo | None = None):
    EventoCaso.objects.create(
        caso=caso, titulo=titulo, detalle=detalle, autor=autor, nodo=nodo
    )


def _notificar(usuario, titulo: str, detalle: str = "", caso: Caso | None = None):
    """Crea un aviso personal (si hay destinatario)."""
    if usuario is not None and getattr(usuario, "pk", None):
        Notificacion.objects.create(usuario=usuario, titulo=titulo, detalle=detalle[:255], caso=caso)


def _nombre_paciente(caso: Caso) -> str:
    return f"{caso.ciudadano.nombre} {caso.ciudadano.apellido}".strip() if caso.ciudadano_id else ""


def _notificar_grupo(nodo: Nodo | None, titulo: str, detalle: str = "", caso: Caso | None = None, excluir=None):
    """Avisa a todos los integrantes de los grupos responsables del nodo."""
    if nodo is None:
        return
    user_ids = set()
    for g in nodo.grupos.all():
        user_ids |= set(g.miembros.values_list("id", flat=True))
    user_ids.discard(getattr(excluir, "id", None))
    Notificacion.objects.bulk_create([
        Notificacion(usuario_id=uid, titulo=titulo, detalle=detalle[:255], caso=caso) for uid in user_ids
    ])


# --------------------------------------------------------------------------- #
# Tiempos: esperas programadas y SLA
# --------------------------------------------------------------------------- #
# Alias de unidad, ORDENADOS DE MÁS LARGO A MÁS CORTO.
#
# El orden es el punto: se compara con `startswith` para que «horas», «hora» y
# «hs» caigan juntas, y con los alias de una letra eso muerde — «mes» empieza
# con «m», así que «1 mes» se interpretaba como 1 MINUTO. Un caso que tenía que
# volver en un mes volvía en sesenta segundos.
_UNIDADES = sorted(
    [
        ("minuto", 1), ("min", 1), ("m", 1),
        ("hora", 60), ("hs", 60), ("hr", 60), ("h", 60),
        ("semana", 60 * 24 * 7), ("sem", 60 * 24 * 7),
        ("dia", 60 * 24), ("d", 60 * 24),
        ("mes", 60 * 24 * 30),
        ("anio", 60 * 24 * 365), ("ano", 60 * 24 * 365),
    ],
    key=lambda par: -len(par[0]),
)


def minutos_de_espera(config: dict) -> int | None:
    """
    Duración de una espera, en minutos.

    Acepta `{"minutos": 360}` y también el texto libre `{"duracion": "6 horas"}`,
    que es lo que ya está guardado en los flujos existentes: la duración nació
    como rótulo informativo y recién ahora se ejecuta. Migrar ese texto a un
    número sería tocar datos de producción para no ganar nada — interpretarlo
    alcanza, y el editor guarda los minutos de acá en adelante.

    Devuelve None si no se entiende: ahí el nodo queda como estaba (esperando
    una reactivación manual) en vez de inventar un plazo.
    """
    if not config:
        return None
    exacto = config.get("minutos")
    if isinstance(exacto, (int, float)) and exacto > 0:
        return int(exacto)

    texto = _plano(config.get("duracion", ""))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-z]+)", texto)
    if not m:
        return None
    cantidad = float(m.group(1).replace(",", "."))
    palabra = m.group(2)
    for alias, factor in _UNIDADES:
        if palabra.startswith(alias):
            return max(1, round(cantidad * factor))
    return None


def minutos_de_sla(nodo: Nodo) -> int | None:
    """Plazo declarado para el paso, en minutos. None = sin SLA."""
    cfg = nodo.config or {}
    valor = cfg.get("sla_minutos")
    if isinstance(valor, (int, float)) and valor > 0:
        return int(valor)
    return None


# --------------------------------------------------------------------------- #
# Integración con sistemas externos
# --------------------------------------------------------------------------- #
def _host_permitido(url: str) -> bool:
    """
    ¿La URL apunta a un host habilitado por la infraestructura?

    El nodo de integración deja que alguien con permiso de DISEÑO configure una
    URL que llama el servidor. Sin restricción eso es un SSRF con formulario:
    quien diseña un flujo podría hacer que el backend consulte un servicio
    interno que no está expuesto a internet y guardar la respuesta en un campo
    del caso, que después se lee desde la pantalla.

    Es lista blanca y no «bloquear rangos privados» porque el DNS puede cambiar
    de respuesta entre la validación y la petición. Y la lista vive en settings,
    no en el flujo: habilitar un destino es una decisión de infraestructura, no
    de quien dibuja el diagrama.
    """
    from django.conf import settings

    permitidos = getattr(settings, "INTEGRACIONES_PERMITIDAS", []) or []
    if not permitidos:
        return False
    partes = urlparse(url)
    if partes.scheme not in ("http", "https"):
        return False
    host = (partes.hostname or "").lower()
    return any(host == h.lower() or host.endswith("." + h.lower()) for h in permitidos)


def _extraer(datos, ruta: str):
    """Sigue una ruta tipo `paciente.cobertura.plan` dentro de la respuesta."""
    actual = datos
    for parte in (ruta or "").split("."):
        if not parte:
            continue
        if isinstance(actual, dict):
            actual = actual.get(parte)
        elif isinstance(actual, list) and parte.isdigit():
            actual = actual[int(parte)] if int(parte) < len(actual) else None
        else:
            return None
    return actual


def _llamar_externo(caso: Caso, nodo: Nodo, autor=None):
    """
    Llama a un sistema externo y, si se pidió, guarda un dato de la respuesta.

    Config: `{url, metodo, cuerpo, guardar_en: <id de Campo>, ruta, obligatorio}`.

    Ante una falla, por defecto se ANOTA y el caso sigue: un padrón que no
    responde no puede dejar a un paciente trabado en el circuito. Con
    `obligatorio: true` el flujo se detiene, para los pasos donde seguir sin el
    dato no tiene sentido.
    """
    from django.conf import settings

    cfg = nodo.config or {}
    url = (cfg.get("url") or "").strip()
    obligatorio = bool(cfg.get("obligatorio"))

    def fallar(motivo: str):
        _registrar(caso, f"Integración fallida: {nodo.titulo}", detalle=motivo, autor=autor, nodo=nodo)
        if obligatorio:
            raise ErrorMotor(f"«{nodo.titulo}» no pudo completarse: {motivo}")

    if not url:
        return fallar("el nodo no tiene URL configurada")
    if not _host_permitido(url):
        return fallar(
            "el destino no está habilitado. Un administrador tiene que agregarlo a "
            "CAUCE_INTEGRACIONES_PERMITIDAS."
        )

    metodo = (cfg.get("metodo") or "GET").upper()
    cuerpo = cfg.get("cuerpo")
    datos = json.dumps(cuerpo).encode() if (cuerpo and metodo != "GET") else None
    pedido = Request(url, data=datos, method=metodo)
    pedido.add_header("Content-Type", "application/json")
    pedido.add_header("Accept", "application/json")

    try:
        with urlopen(pedido, timeout=getattr(settings, "INTEGRACIONES_TIMEOUT", 6)) as r:
            # Tope de lectura: una respuesta enorme no puede comerse la memoria
            # del proceso que está atendiendo a un paciente.
            crudo = r.read(256_000).decode("utf-8", "replace")
        respuesta = json.loads(crudo) if crudo.strip() else {}
    except (URLError, HTTPError, TimeoutError, OSError) as e:
        return fallar(f"no respondió ({type(e).__name__})")
    except ValueError:
        return fallar("la respuesta no es JSON")

    campo_id = cfg.get("guardar_en")
    if campo_id:
        valor = _extraer(respuesta, cfg.get("ruta", ""))
        ValorCampo.objects.update_or_create(
            caso=caso, campo_id=campo_id,
            defaults={"nodo": nodo, "valor": "" if valor is None else str(valor)},
        )
        _registrar(caso, nodo.titulo or "Integración", detalle=f"dato recibido: {valor}", autor=autor, nodo=nodo)
    else:
        _registrar(caso, nodo.titulo or "Integración", detalle="consulta realizada", autor=autor, nodo=nodo)


def _aplicar_efecto_entrada(caso: Caso, nodo: Nodo, autor=None):
    """Aplica el efecto de *entrar* a un nodo automático o de espera."""
    if nodo.tipo == Nodo.Tipo.NOTIFICAR:
        cfg = nodo.config or {}
        titulo = cfg.get("titulo") or nodo.titulo or "Aviso del flujo"
        # El detalle admite {paciente}: un aviso que dice a quién se refiere
        # sirve; uno que dice «revisá el sistema», no.
        detalle = (cfg.get("detalle") or "").replace("{paciente}", _nombre_paciente(caso))
        if cfg.get("a") == "asignado":
            _notificar(caso.asignado_a, titulo, detalle, caso=caso)
        else:
            _notificar_grupo(nodo, titulo, detalle, caso=caso, excluir=autor)
        _registrar(caso, f"Aviso enviado: {titulo}", detalle=detalle, autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.INTEGRACION:
        _llamar_externo(caso, nodo, autor=autor)

    elif nodo.tipo == Nodo.Tipo.ESTADO:
        nuevo = (nodo.config or {}).get("estado")
        valores_validos = {c for c, _ in Caso.Estado.choices}
        if nuevo in valores_validos:
            caso.estado = nuevo
        _registrar(caso, f"Estado → {nodo.titulo or nuevo}", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.DERIVAR:
        cfg = nodo.config or {}
        area_id = cfg.get("area_destino_id")
        if area_id:
            area = Area.objects.filter(pk=area_id).first()
            if area:
                caso.area_actual = area
        caso.estado = Caso.Estado.DERIVADO
        destino = caso.area_actual.nombre if caso.area_actual else nodo.titulo
        _registrar(caso, f"Derivado a {destino}", detalle="regla del flujo", autor=autor, nodo=nodo)

        # Derivación a otro flujo: instanciar y arrancar un caso nuevo allí,
        # vinculado al caso origen para poder trazar el recorrido completo.
        flujo_destino_id = cfg.get("flujo_destino_id")
        if flujo_destino_id:
            ver_destino = (
                VersionFlujo.objects
                .filter(flujo_id=flujo_destino_id, estado=VersionFlujo.Estado.PUBLICADA)
                .order_by("-numero")
                .first()
            )
            if ver_destino:
                nuevo = Caso.objects.create(
                    institucion=caso.institucion,
                    version=ver_destino,
                    ciudadano=caso.ciudadano,
                    prioridad=caso.prioridad,
                    origen=caso,
                    area_actual=ver_destino.flujo.area,
                )
                _registrar(caso, "Derivado a otro flujo",
                           detalle=f"Caso #{nuevo.pk} en «{ver_destino.flujo.titulo}»", autor=autor, nodo=nodo)
                _registrar(nuevo, "Originado por derivación",
                           detalle=f"Desde el caso #{caso.pk} · {caso.version.flujo.titulo}", autor=autor)
                iniciar(nuevo, autor=autor)

    elif nodo.tipo == Nodo.Tipo.ACCION:
        _registrar(caso, f"Acción: {nodo.titulo}", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ESPERA_FILA:
        # Encolar al final (urgentes primero los ordena el modelo).
        ya = caso.en_filas.filter(nodo=nodo, atendido=False).exists()
        if not ya:
            orden = _proximo_orden(nodo)
            ItemFila.objects.create(
                caso=caso,
                nodo=nodo,
                urgente=(caso.prioridad == Caso.Prioridad.URGENTE),
                orden=orden,
            )
        caso.estado = Caso.Estado.EN_ESPERA
        _registrar(caso, f"Ingresó a la fila «{nodo.titulo}»", detalle="orden FIFO", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ESPERA_TIEMPO:
        caso.estado = Caso.Estado.EN_ESPERA
        cfg = nodo.config or {}
        dur = cfg.get("duracion", "")
        minutos = minutos_de_espera(cfg)
        if minutos:
            # Acá se agenda el vencimiento. Hasta ahora la duración era sólo un
            # texto informativo y el caso se quedaba en el nodo PARA SIEMPRE: una
            # «observación 6 horas» no volvía nunca sola.
            caso.reactivar_en = timezone.now() + timedelta(minutes=minutos)
            _registrar(caso, f"Espera programada: {nodo.titulo}",
                       detalle=f"{dur or f'{minutos} min'} · vence {caso.reactivar_en:%d/%m %H:%M}",
                       autor=autor, nodo=nodo)
        else:
            caso.reactivar_en = None
            _registrar(caso, f"Espera programada: {nodo.titulo}",
                       detalle=(dur or "sin duración: hay que reactivarlo a mano"),
                       autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila"):
        # Atención con fila: el paciente espera encolado hasta que lo llaman de un box.
        ya = caso.en_filas.filter(nodo=nodo, atendido=False).exists()
        if not ya:
            orden = _proximo_orden(nodo)
            ItemFila.objects.create(
                caso=caso, nodo=nodo,
                urgente=(caso.prioridad == Caso.Prioridad.URGENTE), orden=orden,
            )
        caso.estado = Caso.Estado.EN_ESPERA
        _registrar(caso, f"En sala de espera: {nodo.titulo}", detalle="esperando ser llamado a un box", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.CAMA:
        # El caso queda esperando cama. No se le asigna una sola: elegirla es una
        # decisión de quien conoce el sector (aislamiento, sexo de la sala,
        # gravedad), y automatizarla sería adivinar algo que se paga caro.
        caso.estado = Caso.Estado.EN_ESPERA
        sector = _sector_del_nodo(nodo)
        _registrar(
            caso, f"Esperando cama: {nodo.titulo}",
            detalle=f"sector {sector.nombre}" if sector else "sin sector definido",
            autor=autor, nodo=nodo,
        )

    elif nodo.tipo == Nodo.Tipo.FIN:
        # Una cama ocupada por un caso cerrado no se libera nunca sola: el sector
        # se queda sin camas y nadie entiende por qué. Se libera acá.
        _liberar_camas_del_caso(caso, EstadiaCama.Egreso.ALTA, autor=autor)
        caso.estado = Caso.Estado.CERRADO
        _registrar(caso, f"Estado → Cerrado", detalle=nodo.titulo, autor=autor, nodo=nodo)
        if caso.bloquea_origen and caso.origen_id:
            _retornar_al_origen(caso, autor=autor)


# --------------------------------------------------------------------------- #
# Camas de internación
# --------------------------------------------------------------------------- #
def _sector_del_nodo(nodo):
    """Sub-área a la que el nodo restringe la búsqueda de cama, si declara una."""
    from apps.instituciones.models import Subarea

    sid = (nodo.config or {}).get("sector")
    return Subarea.objects.filter(pk=sid).first() if sid else None


def camas_disponibles(nodo):
    """Camas que se le pueden ofrecer a un caso parado en este nodo.

    Si el nodo declara sector, sólo las de ese sector; si no, las del área del
    flujo. Nunca las de otra institución: se filtra por el área, que ya cuelga
    de una sola.
    """
    sector = _sector_del_nodo(nodo)
    qs = Cama.objects.filter(activa=True, estado=Cama.Estado.LIBRE)
    if sector:
        return qs.filter(subarea=sector)
    area_id = nodo.version.flujo.area_id
    return qs.filter(area_id=area_id) if area_id else qs.none()


def _liberar_camas_del_caso(caso: Caso, motivo: str, autor=None, hasta=None) -> int:
    """Cierra las estadías abiertas del caso y deja las camas en higiene.

    Devuelve cuántas liberó. Se llama al cerrar y al cancelar un caso: una cama
    ocupada por un caso que ya terminó no se libera nunca sola, y el sector se
    queda sin camas sin que nadie entienda por qué.
    """
    ahora = hasta or timezone.now()
    n = 0
    for estadia in EstadiaCama.objects.select_related("cama").filter(caso=caso, hasta__isnull=True):
        estadia.hasta = ahora
        estadia.motivo_egreso = motivo
        estadia.save(update_fields=["hasta", "motivo_egreso"])
        cama = estadia.cama
        # A higiene, no a libre: entre un paciente y el siguiente la cama no
        # está disponible, y ofrecerla sin higienizar es el error que nadie
        # quiere cometer.
        cama.estado = Cama.Estado.HIGIENE
        cama.caso = None
        cama.desde = ahora
        cama.save(update_fields=["estado", "caso", "desde"])
        n += 1
    return n


@transaction.atomic
def asignar_cama(caso: Caso, cama_id, autor=None) -> Caso:
    """Interna al caso en una cama y lo hace avanzar.

    La cama la elige una persona: qué cama le toca a quién depende de
    aislamiento, del sexo de la sala y de la gravedad, y adivinarlo se paga
    caro. El motor se ocupa de que la cama esté realmente libre y de que el
    caso no ocupe dos.
    """
    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo.")
    if nodo.tipo != Nodo.Tipo.CAMA:
        raise ErrorMotor("Este paso no es de asignación de cama.")
    if EstadiaCama.objects.filter(caso=caso, hasta__isnull=True).exists():
        raise ErrorMotor("El caso ya está internado en una cama.")

    # `select_for_update` porque dos administrativos mirando el mismo tablero
    # pueden apretar la misma cama con segundos de diferencia.
    #
    # El `order_by()` vacío no es adorno: `Cama` ordena por `subarea__nombre` y
    # la sub-área es opcional, así que el orden por defecto arma un LEFT JOIN y
    # Postgres no deja bloquear filas sobre el lado nullable de un outer join.
    # Acá se busca por id y el orden no aporta nada.
    cama = Cama.objects.order_by().select_for_update().filter(pk=cama_id).first()
    if cama is None:
        raise ErrorMotor("La cama no existe.")
    if not cama.activa:
        raise ErrorMotor(f"La cama {cama.nombre} está dada de baja.")
    if cama.estado != Cama.Estado.LIBRE:
        raise ErrorMotor(
            f"La cama {cama.nombre} no está libre ({cama.get_estado_display().lower()})."
        )

    ahora = timezone.now()
    cama.estado = Cama.Estado.OCUPADA
    cama.caso = caso
    cama.desde = ahora
    cama.save(update_fields=["estado", "caso", "desde"])
    EstadiaCama.objects.create(cama=cama, caso=caso, desde=ahora, autor=autor)

    _registrar(caso, f"Internado en cama {cama.nombre}",
               detalle=cama.sector_nombre, autor=autor, nodo=nodo)
    siguiente = _siguiente_nodo(nodo, caso)
    if siguiente is None:
        _registrar(caso, "Caso sin salida", detalle=f"nodo «{nodo.titulo}» sin conexión",
                   autor=autor, nodo=nodo)
        caso.save()
        return caso
    caso.nodo_actual = siguiente
    return _correr_automaticos(caso, autor=autor)


@transaction.atomic
def pasar_de_sector(caso: Caso, cama_id, autor=None, motivo: str = "") -> Caso:
    """Mueve al paciente a otra cama (típicamente de otro sector).

    Es el pase de UTI a sala y viceversa. Cierra la estadía anterior y abre una
    nueva, así el recorrido del paciente queda completo sin ningún registro
    aparte. La cama que deja va a higiene como cualquier egreso.
    """
    actual = (
        EstadiaCama.objects.select_related("cama")
        .filter(caso=caso, hasta__isnull=True).first()
    )
    if actual is None:
        raise ErrorMotor("El caso no está internado en ninguna cama.")

    # `order_by()` vacío por lo mismo que en `asignar_cama`.
    destino = Cama.objects.order_by().select_for_update().filter(pk=cama_id).first()
    if destino is None:
        raise ErrorMotor("La cama de destino no existe.")
    if destino.id == actual.cama_id:
        raise ErrorMotor("El paciente ya está en esa cama.")
    if not destino.activa or destino.estado != Cama.Estado.LIBRE:
        raise ErrorMotor(f"La cama {destino.nombre} no está libre.")

    origen = actual.cama
    ahora = timezone.now()
    actual.hasta = ahora
    actual.motivo_egreso = EstadiaCama.Egreso.PASE
    actual.save(update_fields=["hasta", "motivo_egreso"])
    origen.estado = Cama.Estado.HIGIENE
    origen.caso = None
    origen.desde = ahora
    origen.save(update_fields=["estado", "caso", "desde"])

    destino.estado = Cama.Estado.OCUPADA
    destino.caso = caso
    destino.desde = ahora
    destino.save(update_fields=["estado", "caso", "desde"])
    EstadiaCama.objects.create(cama=destino, caso=caso, desde=ahora, autor=autor)

    cambia_sector = origen.subarea_id != destino.subarea_id
    _registrar(
        caso,
        f"Pase a {destino.sector_nombre}" if cambia_sector else f"Cambio de cama: {destino.nombre}",
        detalle=motivo or f"{origen.nombre} → {destino.nombre}",
        autor=autor, nodo=caso.nodo_actual,
    )
    caso.save()
    return caso


@transaction.atomic
def dar_de_alta_cama(caso: Caso, autor=None, motivo: str = "") -> Caso:
    """Libera la cama sin cerrar el caso.

    Se usa cuando el paciente egresa de internación pero el caso sigue —queda
    pendiente el resumen de epicrisis, o se lo deriva—. Sin esto, la única
    forma de liberar una cama era cerrar el caso.
    """
    egreso = motivo if motivo in EstadiaCama.Egreso.values else EstadiaCama.Egreso.ALTA
    if not _liberar_camas_del_caso(caso, egreso, autor=autor):
        raise ErrorMotor("El caso no está internado en ninguna cama.")
    _registrar(caso, "Egreso de internación",
               detalle=dict(EstadiaCama.Egreso.choices).get(egreso, ""),
               autor=autor, nodo=caso.nodo_actual)
    caso.save()
    return caso


@transaction.atomic
def cambiar_estado_cama(cama: Cama, estado: str, autor=None, motivo: str = "") -> Cama:
    """Higiene → libre, o poner/sacar una cama de servicio.

    No pasa por acá ocupar ni desocupar: eso lo hace el motor junto con la
    estadía del paciente, y dejar que alguien marque «libre» una cama ocupada
    dejaría a un paciente internado en ningún lado.
    """
    if estado not in (Cama.Estado.LIBRE, Cama.Estado.HIGIENE, Cama.Estado.BLOQUEADA):
        raise ErrorMotor("Ese estado se cambia internando o dando el alta, no a mano.")
    if cama.estado == Cama.Estado.OCUPADA:
        raise ErrorMotor(
            f"La cama {cama.nombre} está ocupada: primero hay que dar el egreso del paciente."
        )
    cama.estado = estado
    cama.motivo = motivo[:200] if estado == Cama.Estado.BLOQUEADA else ""
    cama.desde = timezone.now()
    cama.save(update_fields=["estado", "motivo", "desde"])
    return cama


# --------------------------------------------------------------------------- #
# Avance del caso
# --------------------------------------------------------------------------- #
def _correr_automaticos(caso: Caso, autor=None):
    """
    Desde el `nodo_actual`, aplica efectos y avanza mientras el nodo sea
    automático. Se detiene en un nodo de detención (form/atención/espera/fin) o
    en un callejón sin salida.
    """
    visitados = set()
    while caso.nodo_actual is not None:
        nodo = caso.nodo_actual
        # Único punto por donde pasa TODO nodo que el motor atraviesa: anotar acá
        # es lo que hace que la traza no pueda quedar desactualizada.
        _anotar(nodo)

        # Mismo argumento para el reloj del paso: se reinicia acá y en ningún otro
        # lado, así el SLA mide siempre desde que el caso ENTRÓ a este nodo.
        caso.paso_desde = timezone.now()
        caso.sla_avisado = False
        # Un vencimiento viejo no puede sobrevivir al cambio de paso.
        if nodo.tipo != Nodo.Tipo.ESPERA_TIEMPO:
            caso.reactivar_en = None

        if nodo.tipo in TIPOS_DETENCION:
            _aplicar_efecto_entrada(caso, nodo, autor=autor)
            # Un caso urgente que llega a un paso de trabajo avisa al equipo responsable.
            if caso.prioridad == Caso.Prioridad.URGENTE and nodo.tipo in (
                Nodo.Tipo.FORMULARIO, Nodo.Tipo.ATENCION, Nodo.Tipo.ESPERA_FILA
            ):
                _notificar_grupo(nodo, "Caso urgente", detalle=f"{nodo.titulo} · {_nombre_paciente(caso)}".strip(" ·"), caso=caso, excluir=autor)
            break

        # Nodo automático: aplicar efecto y saltar al siguiente.
        if nodo.pk in visitados:
            raise ErrorMotor(f"Ciclo automático detectado en el nodo «{nodo.titulo}».")
        visitados.add(nodo.pk)

        _aplicar_efecto_entrada(caso, nodo, autor=autor)
        siguiente = _siguiente_nodo(nodo, caso)
        if siguiente is None:
            _registrar(caso, "Caso sin salida", detalle=f"nodo «{nodo.titulo}» sin conexión", autor=autor, nodo=nodo)
            break
        caso.nodo_actual = siguiente

    caso.save()
    return caso


def asegurar_historia(caso: Caso):
    """Garantiza que el paciente del caso tenga su historia clínica (ingreso = HC)."""
    if caso.ciudadano_id:
        HistoriaClinica.objects.get_or_create(ciudadano=caso.ciudadano)


def _hc_del_caso(caso: Caso) -> HistoriaClinica:
    if not caso.ciudadano_id:
        raise ErrorMotor("El caso no tiene un paciente asociado.")
    asegurar_historia(caso)
    return caso.ciudadano.historia_clinica


def agregar_receta(caso: Caso, detalle: str, autor=None):
    """El médico o enfermería emite una receta que queda en la historia clínica."""
    from apps.registros.models import Receta

    _exigir_clinico(caso, autor)
    hc = _hc_del_caso(caso)
    r = Receta.objects.create(historia=hc, detalle=detalle, autor=autor if (autor and autor.is_authenticated) else None)
    _registrar(caso, "Receta emitida", detalle=detalle[:120], autor=autor, nodo=caso.nodo_actual)
    return r


def agregar_estudio(caso: Caso, tipo: str, autor=None):
    """El médico o enfermería solicita un estudio (queda pendiente en la HC)."""
    from apps.registros.models import Estudio

    _exigir_clinico(caso, autor)
    hc = _hc_del_caso(caso)
    e = Estudio.objects.create(
        historia=hc, tipo=tipo, fecha=timezone.now().date(),
        autor=(autor.nombre_completo if (autor and autor.is_authenticated) else ""),
    )
    _registrar(caso, "Estudio solicitado", detalle=tipo, autor=autor, nodo=caso.nodo_actual)
    return e


def _derivar_subproceso(caso: Caso, area_destino, autor=None, estudio=None,
                        etiqueta_origen="Derivado y en espera", etiqueta_sub="Sub-proceso",
                        detalle_sub="") -> Caso:
    """
    Mecanismo general de ida y vuelta: abre un sub-caso en el flujo del área destino,
    ligado al `caso` (que queda ESPERANDO), y al cerrarse el sub-caso reactiva al origen.
    Sirve para estudios derivados e interconsultas.
    """
    ver = (
        VersionFlujo.objects
        .filter(flujo__area=area_destino, estado=VersionFlujo.Estado.PUBLICADA)
        .order_by("-flujo_id", "-numero").first()
    )
    if ver is None:
        raise ErrorMotor(f"El área «{area_destino}» no tiene un flujo publicado para recibir el caso.")

    sub = Caso.objects.create(
        institucion=caso.institucion, version=ver, ciudadano=caso.ciudadano,
        prioridad=caso.prioridad, origen=caso, bloquea_origen=True,
        estudio=estudio, area_actual=area_destino,
    )
    caso.esperando = True
    caso.estado = Caso.Estado.EN_ESPERA
    caso.save(update_fields=["esperando", "estado", "actualizado"])
    _registrar(caso, etiqueta_origen, detalle=f"{area_destino.nombre} · caso #{sub.pk}", autor=autor, nodo=caso.nodo_actual)
    _registrar(sub, etiqueta_sub, detalle=detalle_sub or f"del caso #{caso.pk}", autor=autor)
    iniciar(sub, autor=autor)
    return sub


@transaction.atomic
def solicitar_estudio_derivado(caso: Caso, tipo: str, area_destino, autor=None) -> Caso:
    """Estudio que se realiza en OTRA área (ida y vuelta). Crea el estudio pendiente."""
    estudio = agregar_estudio(caso, tipo, autor=autor)
    return _derivar_subproceso(
        caso, area_destino, autor=autor, estudio=estudio,
        etiqueta_origen=f"Estudio derivado a {area_destino.nombre}",
        etiqueta_sub="Estudio a realizar", detalle_sub=f"{tipo} (del caso #{caso.pk})",
    )


@transaction.atomic
def solicitar_interconsulta(caso: Caso, area_destino, motivo: str, autor=None) -> Caso:
    """Interconsulta a otra área (ida y vuelta): el caso espera la opinión y vuelve."""
    _registrar(caso, "Interconsulta solicitada", detalle=(motivo or "")[:120], autor=autor, nodo=caso.nodo_actual)
    return _derivar_subproceso(
        caso, area_destino, autor=autor, estudio=None,
        etiqueta_origen=f"Interconsulta a {area_destino.nombre}",
        etiqueta_sub="Interconsulta recibida", detalle_sub=(motivo or f"del caso #{caso.pk}"),
    )


def _retornar_al_origen(sub: Caso, autor=None):
    """Al cerrarse un sub-caso bloqueante, marca su estudio como realizado y, si no
    quedan otros sub-procesos pendientes, reactiva al caso de origen."""
    parent = sub.origen
    if parent is None:
        return
    if sub.estudio_id:
        sub.estudio.realizado = True
        sub.estudio.save(update_fields=["realizado"])
    pendientes = (
        parent.derivados.filter(bloquea_origen=True)
        .exclude(pk=sub.pk).exclude(estado=Caso.Estado.CERRADO).exists()
    )
    if not pendientes and parent.esperando:
        parent.esperando = False
        parent.estado = Caso.Estado.EN_EVALUACION
        parent.save(update_fields=["esperando", "estado", "actualizado"])
        _registrar(parent, "Estudio recibido — retomar atención", detalle=f"desde el caso #{sub.pk}", autor=autor)
        _notificar(parent.asignado_a, "Resultado recibido",
                   detalle=f"Volvió «{sub.version.flujo.titulo}» — podés retomar la atención", caso=parent)


@transaction.atomic
def cancelar_caso(caso: Caso, autor=None, motivo: str = "") -> Caso:
    """Cancela un caso (acción del jefe/supervisor de área).

    Lo saca de cualquier fila, lo marca CANCELADO y, si bloqueaba a un caso de
    origen que estaba esperando, lo destraba para que pueda retomarse.
    """
    if caso.estado in (Caso.Estado.CERRADO, Caso.Estado.CANCELADO):
        raise ErrorMotor("El caso ya está finalizado.")
    caso.en_filas.filter(atendido=False).update(atendido=True)  # sale de las colas
    _liberar_camas_del_caso(caso, EstadiaCama.Egreso.ALTA, autor=autor)
    caso.estado = Caso.Estado.CANCELADO
    caso.esperando = False
    caso.save(update_fields=["estado", "esperando", "actualizado"])
    _registrar(caso, "Caso cancelado", detalle=motivo[:200], autor=autor, nodo=caso.nodo_actual)
    if caso.asignado_a_id and caso.asignado_a_id != getattr(autor, "id", None):
        _notificar(caso.asignado_a, "Caso cancelado",
                   detalle=f"{_nombre_paciente(caso)} · {motivo}".strip(" ·"), caso=caso)

    # Si bloqueaba a un caso de origen en espera y no quedan otros sub-procesos
    # pendientes, destrabamos el origen (sin marcar estudios como realizados).
    if caso.bloquea_origen and caso.origen_id:
        parent = caso.origen
        pendientes = (
            parent.derivados.filter(bloquea_origen=True)
            .exclude(pk=caso.pk)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .exists()
        )
        if not pendientes and parent.esperando:
            parent.esperando = False
            parent.estado = Caso.Estado.EN_EVALUACION
            parent.save(update_fields=["esperando", "estado", "actualizado"])
            _registrar(parent, "Sub-proceso cancelado — retomar atención",
                       detalle=f"caso #{caso.pk}", autor=autor)
    return caso


@transaction.atomic
def llamar(caso: Caso, box_id=None, autor=None) -> Caso:
    """
    Llama al caso desde un box. En una «Atención con fila» el caso queda asignado
    al box y pasa a ser atendido (sin avanzar de nodo). En una «Espera de fila»
    clásica, el llamado destraba la cola y avanza al siguiente nodo.
    """
    from apps.instituciones.models import Box

    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo.")
    item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
    if item is None:
        raise ErrorMotor("El caso no está en una fila de espera.")

    box = Box.objects.filter(pk=box_id).first() if box_id else None
    box_nombre = box.nombre if box else ""
    item.box = box
    if item.llamado_at is None:
        item.llamado_at = timezone.now()  # marca de "llamado desde la fila" (métricas)

    # El que llama se queda con el caso (queda asignado a quien atiende).
    if autor is not None and getattr(autor, "is_authenticated", False):
        caso.asignado_a = autor

    es_atencion_fila = nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila")
    if es_atencion_fila:
        # Queda en el mismo nodo, ahora en atención en el box.
        item.save(update_fields=["box", "llamado_at"])
        caso.estado = Caso.Estado.EN_EVALUACION
        _registrar(caso, f"Llamado a {box_nombre}" if box_nombre else "Llamado para atención",
                   detalle="pasa a atención", autor=autor, nodo=nodo)
        caso.save()
        return caso

    # Espera de fila clásica: marca atendido y avanza al siguiente nodo.
    item.atendido = True
    item.atendido_at = timezone.now()
    item.save(update_fields=["box", "atendido", "llamado_at", "atendido_at"])
    _registrar(caso, f"Llamado desde la fila{f' a {box_nombre}' if box_nombre else ''}",
               detalle=nodo.titulo, autor=autor, nodo=nodo)
    siguiente = _siguiente_nodo(nodo, caso)
    if siguiente is None:
        _registrar(caso, "Caso sin salida", detalle=f"nodo «{nodo.titulo}» sin conexión", autor=autor, nodo=nodo)
        caso.save()
        return caso
    caso.nodo_actual = siguiente
    return _correr_automaticos(caso, autor=autor)


def _proximo_orden(nodo) -> int:
    """Último lugar de la cola del nodo.

    Se usaba `count()` de los que esperan, pero eso no es una secuencia: si
    alguien sale de la cola el contador BAJA y el siguiente que llega repite un
    número ya usado. Con el orden solo como desempate no se notaba; desde que se
    puede reordenar a mano, dos personas en la misma posición sí se notan.
    """
    ultimo = ItemFila.objects.filter(nodo=nodo, atendido=False).aggregate(m=Max("orden"))["m"]
    return 0 if ultimo is None else ultimo + 1


@transaction.atomic
def devolver_a_la_cola(caso: Caso, autor=None, motivo: str = "") -> Caso:
    """Devuelve a la cola a alguien que ya había sido llamado a un box.

    Pasa cuando lo llamaron por error, cuando quien atiende se tuvo que ir a una
    urgencia, o cuando el paciente aparece después de haber sido dado por
    ausente. Sin esto, llamar es irreversible: el box queda ocupado por alguien
    que no está y la única salida es avanzar un caso que nadie atendió.

    Dónde vuelve depende de por qué vuelve, y no es un detalle: es el turno de
    una persona.
      - Lo llamaron y no lo atendieron → vuelve a SU lugar. La demora no fue
        suya y ya esperó una vez.
      - Estaba dado por ausente y reapareció → va al final. Perdió el turno.

    `llamado_at` se conserva en los dos casos: mide la espera hasta el primer
    llamado y esa espera ocurrió. Reiniciarlo dejaría el indicador de demora del
    servicio más bajo cuanto peor se opera la cola.
    """
    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo.")
    item = (
        caso.en_filas.filter(nodo=nodo, atendido=False, box__isnull=False).first()
        or caso.en_filas.filter(nodo=nodo, ausente=True).order_by("-ausente_at").first()
    )
    if item is None:
        raise ErrorMotor("El caso no está llamado ni fue dado por ausente en esta fila.")

    reaparecio = item.ausente
    if reaparecio:
        item.orden = _proximo_orden(nodo)
    item.ausente = False
    item.ausente_at = None
    item.atendido = False
    item.box = None
    item.save(update_fields=["ausente", "ausente_at", "atendido", "box", "orden"])

    caso.estado = Caso.Estado.EN_ESPERA
    caso.asignado_a = None  # el box queda libre para el siguiente
    _registrar(
        caso,
        "Vuelve a la cola" + (" (reapareció)" if reaparecio else ""),
        detalle=motivo or ("va al final: había sido dado por ausente" if reaparecio else "conserva su lugar"),
        autor=autor, nodo=nodo,
    )
    caso.save()
    return caso


@transaction.atomic
def marcar_ausente(caso: Caso, autor=None) -> Caso:
    """El paciente fue llamado y no se presentó.

    Es lo más común que pasa en una guardia después de llamar, y hasta ahora no
    se podía registrar: quedaba llamado para siempre, ocupando el box en la
    pantalla y contando como si lo estuvieran atendiendo.

    Sale de la cola con `atendido=True` —el predicado que todo el código ya usa
    para «no está más en la cola»— pero sin `atendido_at`, así el promedio de
    tiempo de atención no baja por gente que nunca se atendió. Si aparece
    después, `devolver_a_la_cola` lo reencola al final.
    """
    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo.")
    item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
    if item is None:
        raise ErrorMotor("El caso no está en una fila de espera.")
    if item.llamado_at is None:
        raise ErrorMotor("Todavía no se lo llamó: no se lo puede dar por ausente.")

    item.ausente = True
    item.ausente_at = timezone.now()
    item.atendido = True   # sale de la cola
    item.box = None        # libera el box
    item.save(update_fields=["ausente", "ausente_at", "atendido", "box"])

    caso.estado = Caso.Estado.EN_ESPERA
    caso.asignado_a = None
    _registrar(
        caso, "No se presentó",
        detalle=f"llamado {item.veces_llamado} {'vez' if item.veces_llamado == 1 else 'veces'}",
        autor=autor, nodo=nodo,
    )
    caso.save()
    return caso


@transaction.atomic
def mover_en_fila(item: ItemFila, posicion: int, autor=None) -> ItemFila:
    """Mueve un ítem a una posición de la cola y renumera el resto.

    Se usa cuando alguien empeora esperando y hay que adelantarlo sin llegar a
    marcarlo urgente (que lo saltea todo). La cola se ordena por
    `-urgente, orden, ingreso`: los urgentes van primero igual, así que la
    posición es dentro del grupo que corresponde.

    Se renumera 0..n para que quede una secuencia sin huecos ni repetidos.
    """
    # Solo los que ESPERAN: quien ya está en un box sigue con `atendido=False`
    # pero no está en la cola, y meterlo acá correría las posiciones respecto de
    # las que muestra la pantalla.
    cola = list(
        ItemFila.objects.select_for_update()
        .filter(nodo=item.nodo_id, atendido=False, box__isnull=True)
        .order_by("-urgente", "orden", "ingreso")
    )
    ids = [i.id for i in cola]
    if item.id not in ids:
        raise ErrorMotor("El ítem no está en la cola.")
    destino = max(0, min(int(posicion), len(cola) - 1))
    cola.insert(destino, cola.pop(ids.index(item.id)))
    for n, it in enumerate(cola):
        if it.orden != n:
            it.orden = n
            it.save(update_fields=["orden"])
    _registrar(
        item.caso, "Cambió de lugar en la cola",
        detalle=f"pasa al puesto {destino + 1} de {len(cola)}",
        autor=autor, nodo=item.nodo,
    )
    return ItemFila.objects.get(pk=item.pk)


@transaction.atomic
def rellamar(caso: Caso, autor=None) -> Caso:
    """Vuelve a llamar a un paciente que ya fue llamado a un box pero no se
    presentó (atención con fila). No cambia de nodo ni de estado: refresca el
    último llamado para que vuelva a destacarse en la pantalla de la sala."""
    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo.")
    es_atencion_fila = nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila")
    if not es_atencion_fila:
        raise ErrorMotor("Rellamar solo aplica a una atención con fila de espera.")
    item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
    if item is None or item.box_id is None:
        raise ErrorMotor("El paciente todavía no fue llamado a un box.")

    item.rellamado_at = timezone.now()
    item.veces_llamado = (item.veces_llamado or 1) + 1
    item.save(update_fields=["rellamado_at", "veces_llamado"])
    box_nombre = item.box.nombre if item.box_id else ""
    _registrar(
        caso, f"Rellamado{f' a {box_nombre}' if box_nombre else ''}",
        detalle=f"{item.veces_llamado}º llamado", autor=autor, nodo=nodo,
    )
    return caso


@transaction.atomic
def iniciar(caso: Caso, autor=None) -> Caso:
    """Coloca el caso en el nodo Inicio de su versión y corre hasta la 1ª parada."""
    asegurar_historia(caso)
    inicio = caso.version.nodos.filter(tipo=Nodo.Tipo.INICIO).first()
    if inicio is None:
        raise ErrorMotor("La versión del flujo no tiene un nodo Inicio.")
    caso.nodo_actual = inicio
    caso.estado = Caso.Estado.RECIBIDO
    caso.save(update_fields=["nodo_actual", "estado", "actualizado"])
    _registrar(caso, "Caso iniciado", detalle=f"Flujo: {caso.version.flujo.titulo} · {caso.version.etiqueta}", autor=autor, nodo=inicio)
    return _correr_automaticos(caso, autor=autor)


@transaction.atomic
def avanzar(caso: Caso, datos: dict | None = None, autor=None) -> Caso:
    """
    Completa el nodo de detención actual con `datos` y avanza al siguiente.

    Según el tipo de nodo actual:
      - form     : datos = {"valores": {<campo_id>: <valor>, ...}}
      - atencion : datos = {"titulo": str, "contenido": str, "firmada": bool}
      - espera   : datos = {} (representa «llamado desde la fila»)
      - tiempo   : datos = {} (representa la reactivación)
    """
    datos = datos or {}
    nodo = caso.nodo_actual
    if nodo is None:
        raise ErrorMotor("El caso no está posicionado en ningún nodo (¿falta iniciar?).")
    if caso.estado in (Caso.Estado.CERRADO, Caso.Estado.CANCELADO) or nodo.tipo == Nodo.Tipo.FIN:
        raise ErrorMotor("El caso ya está finalizado.")
    if caso.esperando:
        raise ErrorMotor("El caso está esperando el resultado de un estudio derivado.")
    if nodo.tipo not in TIPOS_DETENCION:
        raise ErrorMotor(f"El nodo actual («{nodo.titulo}») no espera una acción manual.")

    # Completar el nodo actual.
    if nodo.tipo == Nodo.Tipo.FORMULARIO:
        valores = datos.get("valores", {})
        _guardar_valores(caso, nodo, valores)
        _aplicar_prioridad_desde_form(caso, nodo, autor)
        _registrar(caso, f"Formulario «{nodo.titulo}» completado", detalle=f"{len(valores)} campos cargados", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ATENCION:
        if (nodo.config or {}).get("con_fila"):
            item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
            if item and item.box_id is None:
                raise ErrorMotor("Primero hay que llamar al paciente desde un box.")
            if item:
                item.atendido = True
                item.atendido_at = timezone.now()  # fin de atención (métricas)
                item.save(update_fields=["atendido", "atendido_at"])
        # La matrícula se exige solo si la atención se FIRMA (acto firmado).
        firmada = bool(datos.get("firmada", False))
        matricula = _exigir_firmante(caso, nodo, autor, requiere_matricula=firmada)
        _registrar_atencion(caso, nodo, datos, autor=autor, matricula=matricula)
        # Si este caso vino a realizar un estudio, cargar su resultado estructurado.
        if caso.estudio_id:
            est = caso.estudio
            resultado = datos.get("resultado", "")
            archivo = datos.get("archivo", "")
            if resultado:
                est.resultado = resultado
            if archivo:
                est.archivo = archivo
            est.realizado = True
            est.save(update_fields=["resultado", "archivo", "realizado"])

    elif nodo.tipo == Nodo.Tipo.ESPERA_FILA:
        box_id = datos.get("box_id")
        box_nombre = ""
        item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
        if item:
            ahora = timezone.now()
            item.atendido = True
            item.atendido_at = ahora
            if item.llamado_at is None:
                item.llamado_at = ahora  # llamado y atención coinciden en la fila clásica
            if box_id:
                item.box_id = box_id
            item.save(update_fields=["atendido", "box", "llamado_at", "atendido_at"])
        if box_id:
            from apps.instituciones.models import Box
            b = Box.objects.filter(pk=box_id).first()
            box_nombre = b.nombre if b else ""
        detalle = f"{nodo.titulo}" + (f" · {box_nombre}" if box_nombre else "")
        _registrar(caso, f"Llamado desde la fila{f' a {box_nombre}' if box_nombre else ''}", detalle=detalle, autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ESPERA_TIEMPO:
        _registrar(caso, "Espera finalizada", detalle=nodo.titulo, autor=autor, nodo=nodo)

    # Mover al siguiente y correr la cadena automática.
    siguiente = _siguiente_nodo(nodo, caso)
    if siguiente is None:
        _registrar(caso, "Caso sin salida", detalle=f"nodo «{nodo.titulo}» sin conexión", autor=autor, nodo=nodo)
        caso.save()
        return caso
    caso.nodo_actual = siguiente
    return _correr_automaticos(caso, autor=autor)


def quien_firma(nodo: Nodo | None) -> tuple[list[str], bool]:
    """
    Qué roles pueden registrar la atención de este nodo, y si hace falta matrícula.

    Antes estaba clavado: sólo `medico`, siempre con matrícula. Eso bloquea
    media docena de procesos reales de un hospital —una consulta de enfermería,
    una entrevista de trabajo social, una admisión administrativa— donde el acto
    lo firma otra persona. El rol pasa a declararlo el nodo.

    El default conserva el comportamiento anterior a propósito: los flujos ya
    publicados no tienen esta config y su semántica no puede cambiar sola.
    """
    cfg = (nodo.config or {}) if nodo else {}
    roles = cfg.get("firma_roles")
    if not isinstance(roles, list) or not roles:
        roles = ["medico"]
    # La matrícula es lo que convierte a la firma en un acto profesional
    # registrable. Se puede apagar donde el rol no la tiene (un administrativo),
    # pero por defecto se exige, que es la regla clínica.
    exige_matricula = cfg.get("firma_matricula", True) is not False
    return [str(r) for r in roles], bool(exige_matricula)


def _exigir_firmante(caso: Caso, nodo: Nodo | None, autor, requiere_matricula: bool = True) -> str:
    """
    Verifica que `autor` pueda registrar la atención de `nodo`.

    Los roles habilitados y si hace falta matrícula los declara el nodo (ver
    `quien_firma`). Si el caso está en un área, además hay que tener esa área
    asignada en la membresía. El super admin firma siempre.

    Devuelve la matrícula del profesional (snapshot para asentar en la firma);
    cadena vacía si firma el super admin o si el rol no la requiere.
    """
    from apps.accounts.models import Membresia

    if autor is None:
        raise ErrorMotor("Se requiere un profesional autenticado para registrar la atención.")
    if getattr(autor, "is_superuser", False):
        return ""

    roles, exige_matricula = quien_firma(nodo)
    membresias = Membresia.objects.filter(
        usuario=autor, institucion=caso.institucion, rol__in=roles, activo=True
    )
    if not membresias.exists():
        etiquetas = dict(Membresia.Rol.choices)
        nombres = " o ".join(etiquetas.get(r, r) for r in roles)
        raise ErrorMotor(f"Este paso lo puede registrar {nombres}.")
    if caso.area_actual_id and not membresias.filter(areas=caso.area_actual_id).exists():
        raise ErrorMotor(f"No estás asignado al área «{caso.area_actual}».")

    matricula = (getattr(getattr(autor, "legajo", None), "matricula", "") or "").strip()
    if requiere_matricula and exige_matricula and not matricula:
        raise ErrorMotor(
            "Para firmar necesitás tener tu matrícula cargada en el legajo profesional."
        )
    return matricula


def _exigir_clinico(caso: Caso, autor):
    """
    Recetas y solicitudes de estudio son actos clínicos: solo un médico o
    enfermería (con membresía activa en la institución del caso) pueden hacerlos.
    El super admin pasa siempre.
    """
    from apps.accounts.models import Membresia

    if autor is None:
        raise ErrorMotor("Se requiere un profesional autenticado.")
    if getattr(autor, "is_superuser", False):
        return
    permitido = Membresia.objects.filter(
        usuario=autor, institucion=caso.institucion, activo=True,
        rol__in=[Membresia.Rol.MEDICO, Membresia.Rol.ENFERMERIA],
    ).exists()
    if not permitido:
        raise ErrorMotor("Solo un médico o enfermería puede emitir recetas o solicitar estudios.")


def _guardar_valores(caso: Caso, nodo: Nodo, valores: dict):
    for campo_id, valor in valores.items():
        ValorCampo.objects.update_or_create(
            caso=caso,
            campo_id=campo_id,
            defaults={"nodo": nodo, "valor": "" if valor is None else str(valor)},
        )


def _aplicar_prioridad_desde_form(caso: Caso, nodo: Nodo, autor=None):
    """Si el nodo (p. ej. triage) declara que un campo define la prioridad del caso,
    la aplica según un mapa valor→prioridad. Config del nodo:
        {"prioridad_campo": <id>, "prioridad_mapa": {"Rojo - Emergencia": "urgente", ...}}
    """
    cfg = nodo.config or {}
    campo_id = cfg.get("prioridad_campo")
    if not campo_id:
        return
    nueva = (cfg.get("prioridad_mapa") or {}).get(_valor_de_campo(caso, campo_id))
    validas = {c for c, _ in Caso.Prioridad.choices}
    if nueva in validas and nueva != caso.prioridad:
        caso.prioridad = nueva
        caso.en_filas.filter(atendido=False).update(urgente=(nueva == Caso.Prioridad.URGENTE))
        _registrar(caso, f"Prioridad → {caso.get_prioridad_display()}", detalle="según triage", autor=autor, nodo=nodo)


def _registrar_atencion(caso: Caso, nodo: Nodo, datos: dict, autor=None, matricula: str = ""):
    """Crea una entrada en la historia clínica del ciudadano del caso."""
    titulo = datos.get("titulo") or nodo.titulo or "Atención"
    contenido = datos.get("contenido", "")
    firmada = bool(datos.get("firmada", False))
    if caso.ciudadano_id:
        historia, _ = HistoriaClinica.objects.get_or_create(ciudadano=caso.ciudadano)
        entrada = EntradaHistoria.objects.create(
            historia=historia,
            titulo=titulo,
            contenido=contenido,
            autor=autor,
            caso=caso,
            firmada=firmada,
            matricula=matricula if firmada else "",
        )
        # Se sella al firmar: es lo que después permite demostrar que la entrada
        # no se tocó. Una sin firmar es un borrador y no se sella.
        from apps.registros.integridad import sellar

        sellar(entrada)
        detalle = "asentada en la historia clínica" + (f" · firmada (Mat. {matricula})" if firmada and matricula else (" · firmada" if firmada else ""))
    else:
        detalle = "sin ciudadano asociado"
    caso.estado = Caso.Estado.ATENDIDO
    _registrar(caso, f"Atención «{titulo}» registrada", detalle=detalle, autor=autor, nodo=nodo)


# --------------------------------------------------------------------------- #
# Validación de una versión antes de publicar
# --------------------------------------------------------------------------- #
def _acciones_posibles(caso: Caso, nodo: Nodo | None) -> list[str]:
    """
    Qué puede hacer quien está parado en este nodo, según el estado real del caso.

    Un paciente encolado y todavía sin box hay que LLAMARLO; recién después se
    registra la atención. Es la misma secuencia que en la guardia de verdad.
    """
    if nodo is None or nodo.tipo == Nodo.Tipo.FIN:
        return []
    # Esperando cama: lo único que se puede hacer es internarlo. Avanzar sin
    # asignar cama dejaría a un paciente internado en ningún lado.
    if nodo.tipo == Nodo.Tipo.CAMA:
        return ["asignar_cama"]
    # La señal de «todavía no lo llamaron» es `llamado_at`, no el box: se puede
    # llamar sin box asignado y el paciente igual quedó llamado.
    esperando_llamado = caso.en_filas.filter(
        nodo=nodo, atendido=False, llamado_at__isnull=True
    ).exists()
    if esperando_llamado:
        return ["llamar"]
    # Ya llamado y en el box: además de registrar la atención, se puede
    # devolverlo a la cola o darlo por ausente. Sin estas dos, llamar es
    # irreversible y el único camino es avanzar un caso que nadie atendió.
    en_box = caso.en_filas.filter(nodo=nodo, atendido=False, box__isnull=False).exists()
    if en_box:
        return ["avanzar", "devolver", "ausente"]
    # Dado por ausente: lo único que queda es reencolarlo si aparece.
    if caso.en_filas.filter(nodo=nodo, ausente=True).exists():
        return ["devolver"]
    return ["avanzar"]


def _box_para_ensayo(caso: Caso):
    """
    Un box cualquiera del área, para que el ensayo pueda llamar al paciente.

    En el diseñador no importa a qué box se llama sino el recorrido, así que
    elegirlo a mano sería ruido. Si el área no tiene boxes se llama sin box y el
    motor lo dirá: un flujo con atención por fila necesita consultorios cargados,
    y enterarse al diseñarlo es mucho mejor que enterarse en la guardia.
    """
    from apps.instituciones.models import Box

    if not caso.area_actual_id:
        return None
    box = Box.objects.filter(area_id=caso.area_actual_id, activo=True).order_by("pk").first()
    return box.pk if box else None


def ensayar(version: VersionFlujo, pasos: list[dict] | None = None, autor=None) -> dict:
    """
    Corre un caso de prueba por `version` con el MOTOR REAL y deshace todo.

    Es lo que hay detrás del botón «Probar» del diseñador. Antes eso lo resolvía
    un simulador propio en el navegador (`lib/simular.js`, 83 líneas) que
    espejaba a este archivo (800+). Dos implementaciones de la misma semántica
    divergen siempre, y ésta ya había divergido: el simulador no sabía de grupos
    responsables, boxes, prioridad de triage, estudios de ida y vuelta ni de la
    regla de firma médica. O sea que el botón mentía, y en silencio: el
    configurador probaba el flujo, le daba bien, publicaba, y en producción
    pasaba otra cosa. Ese es el peor bug posible en un producto cuya promesa es
    «el proceso se configura, no se programa».

    Cómo funciona: se crea un caso de verdad, se lo hace avanzar con el mismo
    código que atiende a un paciente real, se anota por dónde pasó, y al final se
    deshace la transacción entera. No queda nada en la base.

    `pasos` es la lista de datos para cada parada, en orden — el mismo formato
    que recibe `avanzar`. Un paso `{"accion": "llamar"}` ejecuta `llamar` en vez
    de `avanzar`: hace falta porque una «Atención con fila» exige que primero
    llamen al paciente desde un box, y sin eso el ensayo no puede atravesar el
    nodo más común de una guardia. También ahí se usa el motor real, no un atajo.

    Corre **como quien lo pide**. Si el flujo llega a una Atención y quien prueba
    no es médico, el motor lo rechaza y eso aparece en el resultado, con el nodo
    donde pasó. Es a propósito: esa restricción es real y verla al diseñar es
    justamente el punto.
    """
    pasos = list(pasos or [])
    resultado: dict = {
        "camino": [],
        "parada": None,
        "estado": None,
        "prioridad": None,
        "pasos_consumidos": 0,
        "termino": False,
        "error": None,
    }

    with transaction.atomic():
        with trazar() as camino:
            caso = Caso.objects.create(
                institucion=version.flujo.institucion,
                version=version,
                area_actual=version.flujo.area,
            )
            try:
                iniciar(caso, autor=autor)
                for datos in pasos:
                    datos = datos or {}
                    nodo = caso.nodo_actual
                    if nodo is None or nodo.tipo == Nodo.Tipo.FIN:
                        break
                    if nodo.tipo == Nodo.Tipo.CAMA:
                        # Sin esto, un flujo con internación no se podía ensayar:
                        # el nodo detiene el avance esperando que alguien asigne
                        # una cama, y el ensayo se plantaba ahí. Cuál cama no
                        # importa para el recorrido; que NO HAYA sí importa, y
                        # el motor lo dice —enterarse al diseñar el flujo es
                        # mucho mejor que enterarse con un paciente esperando—.
                        libre = camas_disponibles(nodo).first()
                        if libre is None:
                            raise ErrorMotor(
                                f"No hay camas libres para «{nodo.titulo}»: "
                                "cargá camas en el sector antes de publicar."
                            )
                        asignar_cama(caso, libre.id, autor=autor)
                    elif datos.get("accion") == "llamar":
                        llamar(caso, box_id=datos.get("box_id") or _box_para_ensayo(caso), autor=autor)
                    else:
                        avanzar(caso, datos, autor=autor)
                    resultado["pasos_consumidos"] += 1
            except ErrorMotor as e:
                # El motor se plantó: es información, no una falla del ensayo.
                nodo = caso.nodo_actual
                resultado["error"] = {
                    "mensaje": str(e),
                    "nodo": nodo.pk if nodo else None,
                    "titulo": nodo.titulo if nodo else "",
                }

            actual = caso.nodo_actual
            resultado["camino"] = list(camino)
            resultado["parada"] = (
                {
                    "nodo": actual.pk,
                    "titulo": actual.titulo,
                    "tipo": actual.tipo,
                    # Qué acción admite esta parada. Lo decide el motor mirando el
                    # estado real del caso, para que el diseñador no tenga que
                    # deducirlo por su cuenta — deducirlo sería, otra vez, una
                    # segunda implementación de la misma regla.
                    "acciones": _acciones_posibles(caso, actual),
                }
                if actual else None
            )
            resultado["estado"] = caso.estado
            resultado["prioridad"] = caso.prioridad
            resultado["termino"] = bool(actual and actual.tipo == Nodo.Tipo.FIN)

        # Nada de esto queda: el ensayo no puede dejar casos, eventos, ítems de
        # fila ni entradas de historia clínica en la base.
        transaction.set_rollback(True)

    return resultado


def validar_version(version) -> list[dict]:
    """
    Revisa el grafo y devuelve una lista de problemas. Cada problema:
      {"sev": "error"|"aviso", "nodo_id": <id|None>, "titulo": str, "detalle": str}
    Replica los chequeos del prototipo.
    """
    problemas: list[dict] = []
    nodos = list(version.nodos.all())
    conexiones = list(version.conexiones.select_related("origen", "destino"))
    por_tipo = {}
    for n in nodos:
        por_tipo.setdefault(n.tipo, []).append(n)

    # 1) Debe existir exactamente un Inicio.
    inicios = por_tipo.get(Nodo.Tipo.INICIO, [])
    if not inicios:
        problemas.append({"sev": "error", "nodo_id": None,
                          "titulo": "El flujo no tiene un nodo Inicio",
                          "detalle": "Ningún caso podría arrancar."})
    elif len(inicios) > 1:
        problemas.append({"sev": "error", "nodo_id": None,
                          "titulo": "El flujo tiene más de un nodo Inicio",
                          "detalle": "Debe haber un único punto de entrada."})

    # 2) Debe existir al menos un Fin.
    if not por_tipo.get(Nodo.Tipo.FIN):
        problemas.append({"sev": "aviso", "nodo_id": None,
                          "titulo": "El flujo no tiene un nodo Fin",
                          "detalle": "Los casos quedarían sin un cierre explícito."})

    salidas_por_nodo = {}
    for c in conexiones:
        salidas_por_nodo.setdefault(c.origen_id, []).append(c)

    # Campos cargados por formularios "antes" de cada nodo (aproximación: cualquier
    # campo de cualquier formulario del flujo se considera disponible).
    campos_disponibles = set()
    for n in por_tipo.get(Nodo.Tipo.FORMULARIO, []):
        if n.formulario_id:
            campos_disponibles.update(n.formulario.campos.values_list("id", flat=True))

    for n in nodos:
        salidas = salidas_por_nodo.get(n.pk, [])

        # 3) Nodos que no son Fin deberían tener salida.
        if n.tipo != Nodo.Tipo.FIN and not salidas:
            problemas.append({"sev": "aviso", "nodo_id": n.pk,
                              "titulo": f"«{n.titulo}» no tiene salida",
                              "detalle": "El caso quedaría detenido en este nodo."})

        # 4) Derivar sin área de destino.
        if n.tipo == Nodo.Tipo.DERIVAR and not (n.config or {}).get("area_destino_id"):
            problemas.append({"sev": "error", "nodo_id": n.pk,
                              "titulo": "Derivación sin área de destino",
                              "detalle": f"El nodo «{n.titulo}» no tiene un área asignada."})

        # 5) Decisión con condición sobre un campo inexistente / no cargado.
        #    Se recorre el árbol: una regla compuesta no tiene campo arriba de todo.
        if n.tipo == Nodo.Tipo.DECISION:
            for c in salidas:
                if campos_de_condicion(c.condicion) - campos_disponibles:
                    problemas.append({"sev": "error", "nodo_id": n.pk,
                                      "titulo": "Regla con un campo inexistente",
                                      "detalle": f"«{n.titulo}» usa un campo que no se carga en ningún formulario del flujo."})
                    break

        # 6) Integración sin URL, o con un destino que la infraestructura no
        #    habilitó. Avisarlo al publicar es mucho mejor que descubrirlo con un
        #    paciente esperando: el flujo se dibuja hoy y se ejecuta mañana.
        if n.tipo == Nodo.Tipo.INTEGRACION:
            url = ((n.config or {}).get("url") or "").strip()
            if not url:
                problemas.append({"sev": "error", "nodo_id": n.pk,
                                  "titulo": f"«{n.titulo}» no tiene URL",
                                  "detalle": "El paso de integración no haría nada."})
            elif not _host_permitido(url):
                problemas.append({"sev": "error", "nodo_id": n.pk,
                                  "titulo": "Destino de integración no habilitado",
                                  "detalle": f"«{n.titulo}» apunta a un servicio que un administrador "
                                             "todavía no habilitó en el sistema."})

        # 7) Notificación sin nada que decir.
        if n.tipo == Nodo.Tipo.NOTIFICAR and not ((n.config or {}).get("titulo") or n.titulo):
            problemas.append({"sev": "aviso", "nodo_id": n.pk,
                              "titulo": "Aviso sin título",
                              "detalle": "Llegaría una notificación vacía."})

        # 8) Formulario sin formulario asignado.
        if n.tipo == Nodo.Tipo.FORMULARIO and not n.formulario_id:
            problemas.append({"sev": "aviso", "nodo_id": n.pk,
                              "titulo": f"«{n.titulo}» no tiene formulario asignado",
                              "detalle": "No habría datos para cargar en este paso."})

    return problemas


def puede_publicar(version) -> bool:
    return not any(p["sev"] == "error" for p in validar_version(version))
