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
  {"campo": <id de Campo>, "operador": "=", "valor": "Alta"}
  Operadores: "=", "!=", ">", "<", "contiene". Una conexión sin condición es la
  rama por defecto (else).
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.flujos.models import Conexion, Nodo, VersionFlujo
from apps.instituciones.models import Area
from apps.registros.models import EntradaHistoria, HistoriaClinica

from .models import Caso, EventoCaso, ItemFila, ValorCampo


class ErrorMotor(Exception):
    """Error de negocio del motor (estado inválido, datos faltantes, etc.)."""


# --- Responsabilidad: quién puede ejecutar el paso actual de un caso ---------

def grupos_responsables_ids(caso):
    """IDs de los grupos responsables del paso actual. Vacío = abierto a todos."""
    if not caso.nodo_actual_id:
        return []
    return list(caso.nodo_actual.grupos.values_list("id", flat=True))


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
}
# Nodos que detienen el avance hasta un disparador externo.
TIPOS_DETENCION = {
    Nodo.Tipo.FORMULARIO,
    Nodo.Tipo.ATENCION,
    Nodo.Tipo.ESPERA_FILA,
    Nodo.Tipo.ESPERA_TIEMPO,
    Nodo.Tipo.FIN,
}


# --------------------------------------------------------------------------- #
# Evaluación de condiciones (decisiones)
# --------------------------------------------------------------------------- #
def _valor_de_campo(caso: Caso, campo_id) -> str | None:
    vc = caso.valores.filter(campo_id=campo_id).first()
    return vc.valor if vc else None


def _cumple(condicion: dict, caso: Caso) -> bool:
    """Evalúa una condición de rama contra los valores cargados del caso."""
    if not condicion:
        return True  # rama por defecto (else)
    campo_id = condicion.get("campo")
    operador = condicion.get("operador", "=")
    esperado = condicion.get("valor")
    actual = _valor_de_campo(caso, campo_id)
    if actual is None:
        return False

    if operador == "=":
        return str(actual) == str(esperado)
    if operador == "!=":
        return str(actual) != str(esperado)
    if operador == "contiene":
        return str(esperado).lower() in str(actual).lower()
    if operador in (">", "<"):
        try:
            a, e = float(actual), float(esperado)
        except (TypeError, ValueError):
            return False
        return a > e if operador == ">" else a < e
    return False


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


def _aplicar_efecto_entrada(caso: Caso, nodo: Nodo, autor=None):
    """Aplica el efecto de *entrar* a un nodo automático o de espera."""
    if nodo.tipo == Nodo.Tipo.ESTADO:
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
            orden = ItemFila.objects.filter(nodo=nodo, atendido=False).count()
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
        dur = (nodo.config or {}).get("duracion", "")
        _registrar(caso, f"Espera programada: {nodo.titulo}", detalle=dur, autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila"):
        # Atención con fila: el paciente espera encolado hasta que lo llaman de un box.
        ya = caso.en_filas.filter(nodo=nodo, atendido=False).exists()
        if not ya:
            orden = ItemFila.objects.filter(nodo=nodo, atendido=False).count()
            ItemFila.objects.create(
                caso=caso, nodo=nodo,
                urgente=(caso.prioridad == Caso.Prioridad.URGENTE), orden=orden,
            )
        caso.estado = Caso.Estado.EN_ESPERA
        _registrar(caso, f"En sala de espera: {nodo.titulo}", detalle="esperando ser llamado a un box", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.FIN:
        caso.estado = Caso.Estado.CERRADO
        _registrar(caso, f"Estado → Cerrado", detalle=nodo.titulo, autor=autor, nodo=nodo)
        if caso.bloquea_origen and caso.origen_id:
            _retornar_al_origen(caso, autor=autor)


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

        if nodo.tipo in TIPOS_DETENCION:
            _aplicar_efecto_entrada(caso, nodo, autor=autor)
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
    """El médico emite una receta que queda en la historia clínica del paciente."""
    from apps.registros.models import Receta

    hc = _hc_del_caso(caso)
    r = Receta.objects.create(historia=hc, detalle=detalle, autor=autor if (autor and autor.is_authenticated) else None)
    _registrar(caso, "Receta emitida", detalle=detalle[:120], autor=autor, nodo=caso.nodo_actual)
    return r


def agregar_estudio(caso: Caso, tipo: str, autor=None):
    """El médico solicita un estudio (queda pendiente en la historia clínica)."""
    from apps.registros.models import Estudio

    hc = _hc_del_caso(caso)
    e = Estudio.objects.create(
        historia=hc, tipo=tipo, fecha=timezone.now().date(),
        autor=(autor.nombre_completo if (autor and autor.is_authenticated) else ""),
    )
    _registrar(caso, "Estudio solicitado", detalle=tipo, autor=autor, nodo=caso.nodo_actual)
    return e


@transaction.atomic
def solicitar_estudio_derivado(caso: Caso, tipo: str, area_destino, autor=None) -> Caso:
    """
    Solicita un estudio que se realiza en OTRA área (ida y vuelta): crea el estudio
    (pendiente), abre un sub-caso en el flujo de esa área y deja el caso actual
    ESPERANDO hasta que el sub-caso termine y lo reactive.
    """
    estudio = agregar_estudio(caso, tipo, autor=autor)
    ver = (
        VersionFlujo.objects
        .filter(flujo__area=area_destino, estado=VersionFlujo.Estado.PUBLICADA)
        .order_by("-flujo_id", "-numero").first()
    )
    if ver is None:
        raise ErrorMotor(f"El área «{area_destino}» no tiene un flujo de estudios publicado.")

    sub = Caso.objects.create(
        institucion=caso.institucion, version=ver, ciudadano=caso.ciudadano,
        prioridad=caso.prioridad, origen=caso, bloquea_origen=True,
        estudio=estudio, area_actual=area_destino,
    )
    caso.esperando = True
    caso.estado = Caso.Estado.EN_ESPERA
    caso.save(update_fields=["esperando", "estado", "actualizado"])
    _registrar(caso, f"Estudio derivado a {area_destino.nombre}",
               detalle=f"{tipo} · caso #{sub.pk}", autor=autor, nodo=caso.nodo_actual)
    _registrar(sub, "Estudio a realizar", detalle=f"{tipo} (del caso #{caso.pk})", autor=autor)
    iniciar(sub, autor=autor)
    return sub


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

    # El que llama se queda con el caso (queda asignado a quien atiende).
    if autor is not None and getattr(autor, "is_authenticated", False):
        caso.asignado_a = autor

    es_atencion_fila = nodo.tipo == Nodo.Tipo.ATENCION and (nodo.config or {}).get("con_fila")
    if es_atencion_fila:
        # Queda en el mismo nodo, ahora en atención en el box.
        item.save(update_fields=["box"])
        caso.estado = Caso.Estado.EN_EVALUACION
        _registrar(caso, f"Llamado a {box_nombre}" if box_nombre else "Llamado para atención",
                   detalle="pasa a atención", autor=autor, nodo=nodo)
        caso.save()
        return caso

    # Espera de fila clásica: marca atendido y avanza al siguiente nodo.
    item.atendido = True
    item.save(update_fields=["box", "atendido"])
    _registrar(caso, f"Llamado desde la fila{f' a {box_nombre}' if box_nombre else ''}",
               detalle=nodo.titulo, autor=autor, nodo=nodo)
    siguiente = _siguiente_nodo(nodo, caso)
    if siguiente is None:
        _registrar(caso, "Caso sin salida", detalle=f"nodo «{nodo.titulo}» sin conexión", autor=autor, nodo=nodo)
        caso.save()
        return caso
    caso.nodo_actual = siguiente
    return _correr_automaticos(caso, autor=autor)


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
    if caso.estado == Caso.Estado.CERRADO or nodo.tipo == Nodo.Tipo.FIN:
        raise ErrorMotor("El caso ya está cerrado.")
    if caso.esperando:
        raise ErrorMotor("El caso está esperando el resultado de un estudio derivado.")
    if nodo.tipo not in TIPOS_DETENCION:
        raise ErrorMotor(f"El nodo actual («{nodo.titulo}») no espera una acción manual.")

    # Completar el nodo actual.
    if nodo.tipo == Nodo.Tipo.FORMULARIO:
        valores = datos.get("valores", {})
        _guardar_valores(caso, nodo, valores)
        _registrar(caso, f"Formulario «{nodo.titulo}» completado", detalle=f"{len(valores)} campos cargados", autor=autor, nodo=nodo)

    elif nodo.tipo == Nodo.Tipo.ATENCION:
        if (nodo.config or {}).get("con_fila"):
            item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
            if item and item.box_id is None:
                raise ErrorMotor("Primero hay que llamar al paciente desde un box.")
            if item:
                item.atendido = True
                item.save(update_fields=["atendido"])
        _exigir_medico(caso, autor)
        _registrar_atencion(caso, nodo, datos, autor=autor)

    elif nodo.tipo == Nodo.Tipo.ESPERA_FILA:
        box_id = datos.get("box_id")
        box_nombre = ""
        item = caso.en_filas.filter(nodo=nodo, atendido=False).first()
        if item:
            item.atendido = True
            if box_id:
                item.box_id = box_id
            item.save(update_fields=["atendido", "box"])
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


def _exigir_medico(caso: Caso, autor):
    """
    Solo un médico (rol `medico`) puede registrar una atención. Si el caso está en
    un área, el médico debe tener esa área asignada en su membresía. El super admin
    puede firmar siempre.
    """
    from apps.accounts.models import Membresia

    if autor is None:
        raise ErrorMotor("Se requiere un profesional autenticado para registrar la atención.")
    if getattr(autor, "is_superuser", False):
        return
    medicas = Membresia.objects.filter(
        usuario=autor, institucion=caso.institucion, rol=Membresia.Rol.MEDICO, activo=True
    )
    if not medicas.exists():
        raise ErrorMotor("Solo un médico puede registrar una atención.")
    if caso.area_actual_id and not medicas.filter(areas=caso.area_actual_id).exists():
        raise ErrorMotor(f"El médico no está asignado al área «{caso.area_actual}».")


def _guardar_valores(caso: Caso, nodo: Nodo, valores: dict):
    for campo_id, valor in valores.items():
        ValorCampo.objects.update_or_create(
            caso=caso,
            campo_id=campo_id,
            defaults={"nodo": nodo, "valor": "" if valor is None else str(valor)},
        )


def _registrar_atencion(caso: Caso, nodo: Nodo, datos: dict, autor=None):
    """Crea una entrada en la historia clínica del ciudadano del caso."""
    titulo = datos.get("titulo") or nodo.titulo or "Atención"
    contenido = datos.get("contenido", "")
    firmada = bool(datos.get("firmada", False))
    if caso.ciudadano_id:
        historia, _ = HistoriaClinica.objects.get_or_create(ciudadano=caso.ciudadano)
        EntradaHistoria.objects.create(
            historia=historia,
            titulo=titulo,
            contenido=contenido,
            autor=autor,
            caso=caso,
            firmada=firmada,
        )
        detalle = "asentada en la historia clínica" + (" · firmada" if firmada else "")
    else:
        detalle = "sin ciudadano asociado"
    caso.estado = Caso.Estado.ATENDIDO
    _registrar(caso, f"Atención «{titulo}» registrada", detalle=detalle, autor=autor, nodo=nodo)


# --------------------------------------------------------------------------- #
# Validación de una versión antes de publicar
# --------------------------------------------------------------------------- #
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
        if n.tipo == Nodo.Tipo.DECISION:
            for c in salidas:
                campo_id = (c.condicion or {}).get("campo")
                if campo_id and int(campo_id) not in campos_disponibles:
                    problemas.append({"sev": "error", "nodo_id": n.pk,
                                      "titulo": "Regla con un campo inexistente",
                                      "detalle": f"«{n.titulo}» usa un campo que no se carga en ningún formulario del flujo."})
                    break

        # 6) Formulario sin formulario asignado.
        if n.tipo == Nodo.Tipo.FORMULARIO and not n.formulario_id:
            problemas.append({"sev": "aviso", "nodo_id": n.pk,
                              "titulo": f"«{n.titulo}» no tiene formulario asignado",
                              "detalle": "No habría datos para cargar en este paso."})

    return problemas


def puede_publicar(version) -> bool:
    return not any(p["sev"] == "error" for p in validar_version(version))
