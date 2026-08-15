"""
Traslados entre establecimientos.

El ciclo completo: se solicita, el destino acepta o rechaza, sale la ambulancia,
llega. Cada paso deja su marca de tiempo, que es de lo que salen los indicadores
que una región le pide a su red.
"""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.casos import motor as motor_casos
from apps.casos.models import Caso
from apps.flujos.models import VersionFlujo

from .models import Red, Traslado


class ErrorTraslado(Exception):
    """Regla de traslado incumplida. La API la traduce a un 400 con el texto."""


def _bloquear(t: Traslado) -> Traslado:
    """
    Relee la fila con candado, ya adentro de la transacción.

    La vista carga el traslado ANTES de abrir la transacción, así que chequear
    `t.estado` sobre esa instancia es chequear una foto vieja. Dos personas del
    destino con la pantalla abierta —jefe de área y administrativo tienen las
    dos el botón «Responder»— pasan las dos validaciones y queda un estado que
    no se puede reparar desde la app: dos casos abiertos por el mismo paciente,
    o un traslado «rechazado» con un caso ya abierto del otro lado, con el
    origen buscando otro efector y el destino esperando una ambulancia.
    """
    return Traslado.objects.select_for_update().get(pk=t.pk)


def _paciente_en(institucion, base):
    """
    El mismo paciente, en el padrón de `institucion`.

    `Ciudadano` tiene FK a institución y el scoping de la API va por ahí: un
    caso del destino colgado del ciudadano del origen le devuelve 404 al pedir
    la ficha y cero historias clínicas —la UTI que acepta un paciente crítico no
    ve alergias, antecedentes ni estudios—, y las evoluciones que firma su
    médico se asientan en el legajo del hospital que derivó.

    Se busca por documento, que es lo que identifica a una persona en la red. Si
    no tiene documento NO se busca: un get_or_create con documento='' fusionaría
    a todos los NN de guardia en una sola persona.
    """
    from apps.registros.models import Ciudadano

    if base.documento:
        existente = Ciudadano.objects.filter(
            institucion=institucion, documento=base.documento
        ).order_by("id").first()
        if existente is not None:
            return existente
    return Ciudadano.objects.create(
        institucion=institucion,
        nombre=base.nombre,
        apellido=base.apellido,
        documento=base.documento,
        fecha_nacimiento=base.fecha_nacimiento,
        obra_social=base.obra_social,
        domicilio=base.domicilio,
    )


def distancia_km(a, b):
    """
    Distancia en línea recta entre dos establecimientos, en kilómetros.

    En línea recta y no por ruta: calcular el trayecto real necesitaría un
    servicio de mapas externo, y para elegir entre dos hospitales el orden de
    magnitud alcanza. Devuelve None si a alguno le falta la ubicación —es mejor
    no mostrar distancia que mostrar una inventada—.
    """
    from math import asin, cos, radians, sin, sqrt

    if None in (a.latitud, a.longitud, b.latitud, b.longitud):
        return None
    lat1, lon1, lat2, lon2 = map(radians, [a.latitud, a.longitud, b.latitud, b.longitud])
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return round(2 * 6371 * asin(sqrt(h)), 1)


def destinos_posibles(institucion):
    """
    A qué establecimientos puede derivar esta institución.

    Sólo los de sus redes. Sin esa restricción, «derivar» sería una lista con
    todas las instituciones del sistema, incluidas las que no tienen ninguna
    relación con ésta.
    """
    from apps.instituciones.models import Institucion

    return (
        Institucion.objects.filter(redes__in=institucion.redes.filter(activa=True), activa=True)
        .exclude(pk=institucion.pk)
        .distinct()
    )


def visibles_para(user):
    """
    Traslados que puede ver esta persona: los de sus instituciones, esté de un
    lado o del otro.

    Es el único punto del sistema donde alguien ve un objeto ligado a otra
    institución, y por eso el traslado no lleva datos clínicos más allá del
    resumen que el origen decidió escribir.
    """
    if getattr(user, "is_superuser", False):
        return Traslado.objects.all()
    ids = list(user.membresias.filter(activo=True).values_list("institucion_id", flat=True))
    return Traslado.objects.filter(Q(origen_id__in=ids) | Q(destino_id__in=ids))


@transaction.atomic
def solicitar(caso: Caso, destino, motivo, detalle="", area_destino=None, autor=None,
              urgente=False) -> Traslado:
    """
    Pide trasladar un paciente a otro establecimiento.

    El caso de origen queda ESPERANDO —no cerrado—: si el destino rechaza, el
    paciente sigue siendo responsabilidad de quien lo tiene. Cerrarlo al pedir
    dejaría a alguien sin dueño en el momento más delicado.
    """
    # Con candado: sin él, dos pedidos simultáneos sobre el mismo caso pasan
    # los dos el chequeo de «ya tiene un traslado en curso» y el paciente
    # aparece pedido en dos hospitales a la vez.
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    if caso.institucion_id == getattr(destino, "id", destino):
        raise ErrorTraslado("El destino es la misma institución: usá una derivación interna.")
    if caso.estado in (Caso.Estado.CERRADO, Caso.Estado.CANCELADO):
        raise ErrorTraslado("El caso ya está finalizado.")
    if Traslado.objects.filter(
        caso_origen=caso,
        estado__in=[Traslado.Estado.SOLICITADO, Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO],
    ).exists():
        raise ErrorTraslado("Ese caso ya tiene un traslado en curso.")
    if destino not in destinos_posibles(caso.institucion):
        raise ErrorTraslado(
            f"«{destino}» no está en ninguna red compartida con {caso.institucion}."
        )
    if area_destino is not None and area_destino.institucion_id != destino.id:
        raise ErrorTraslado("El área elegida no pertenece al establecimiento de destino.")

    red = caso.institucion.redes.filter(activa=True, instituciones=destino).first()
    t = Traslado.objects.create(
        red=red, origen=caso.institucion, destino=destino, caso_origen=caso,
        ciudadano=caso.ciudadano, area_destino=area_destino, motivo=motivo,
        detalle=detalle[:4000], urgente=urgente or caso.prioridad == Caso.Prioridad.URGENTE,
        solicitado_por=autor,
    )
    caso.esperando = True
    caso.estado = Caso.Estado.EN_ESPERA
    caso.save(update_fields=["esperando", "estado", "actualizado"])
    motor_casos._registrar(
        caso, f"Traslado solicitado a {destino}",
        detalle=t.get_motivo_display(), autor=autor, nodo=caso.nodo_actual,
    )
    _avisar_destino(t)
    return t


def _avisar_destino(t: Traslado, titulo=None, detalle=None):
    """
    Avisa a quien puede resolverlo en el establecimiento de destino.

    Un traslado que nadie mira es un paciente esperando. Se avisa a todos los
    roles con capacidad «trabajo» —que es la que la pantalla de traslados exige
    para aceptar o rechazar— del área destino, o de toda la institución si no se
    indicó área.

    Sirve para todo el ciclo y no sólo para el pedido: el destino se enteró por
    esta vía, y si después el móvil sale, el origen cancela o el paciente no
    llega, tiene que enterarse por el mismo canal. Si no, el equipo que reservó
    la cama sólo lo sabe si se le ocurre mirar la pantalla.
    """
    from apps.accounts.models import Membresia
    from apps.casos.models import Notificacion

    # Médico y enfermería van en la lista: a las tres de la mañana en el hospital
    # de referencia no hay administrativo ni jefe de área, hay guardia, y es la
    # guardia la que decide si se recibe. Dejándolos afuera, un destino cuyos
    # usuarios activos son sólo médicos y enfermería no recibe NINGÚN aviso —no
    # hay otro canal: los traslados no aparecen en Inicio ni en Supervisión— y
    # el pedido queda en «Esperando respuesta» hasta que alguien se acuerde de
    # abrir la pantalla, con un paciente esperando del otro lado.
    qs = Membresia.objects.filter(
        activo=True, institucion=t.destino,
        rol__in=["administrativo", "jefe_area", "admin", "medico", "enfermeria"],
    )
    if t.area_destino_id:
        qs = qs.filter(Q(areas=t.area_destino_id) | Q(rol="admin"))
    destinatarios = {m.usuario for m in qs.select_related("usuario").distinct()}
    # Quien aceptó el traslado es el que reservó la cama: tiene que enterarse de
    # que el móvil salió, de que el origen canceló o de que el paciente no llega,
    # aunque el filtro por área no lo alcance —la membresía de un jefe puede no
    # tener áreas cargadas y ahí no se enteraría nadie—.
    if t.resuelto_por_id:
        destinatarios.add(t.resuelto_por)

    titulo = titulo or f"Traslado {'URGENTE ' if t.urgente else ''}desde {t.origen}"
    detalle = detalle or f"{t.ciudadano} · {t.get_motivo_display()}"
    for u in destinatarios:
        Notificacion.objects.create(usuario=u, titulo=titulo, detalle=detalle[:255])


@transaction.atomic
def aceptar(t: Traslado, autor=None, area_destino=None) -> Traslado:
    """
    El destino acepta y abre el caso de su lado.

    El caso nuevo es del destino: su institución, su flujo, su gente. Lo único
    que viaja es el paciente y el resumen que escribió el origen.
    """
    t = _bloquear(t)
    if t.estado != Traslado.Estado.SOLICITADO:
        raise ErrorTraslado(f"El traslado ya está {t.get_estado_display().lower()}.")
    area = area_destino or t.area_destino
    if area is None:
        raise ErrorTraslado("Hay que indicar a qué área ingresa el paciente.")
    if area.institucion_id != t.destino_id:
        raise ErrorTraslado("El área no pertenece a este establecimiento.")

    ver = (
        VersionFlujo.objects
        .filter(flujo__area=area, estado=VersionFlujo.Estado.PUBLICADA)
        .order_by("-flujo_id", "-numero").first()
    )
    if ver is None:
        raise ErrorTraslado(
            f"El área «{area.nombre}» no tiene un flujo publicado para recibir el caso."
        )

    # El paciente se resuelve del lado del destino ANTES de crear el caso: el
    # ciudadano del origen es un registro de otra institución y dejaría la ficha
    # vacía para quien lo recibe (ver `_paciente_en`).
    paciente = t.ciudadano_destino or _paciente_en(t.destino, t.ciudadano)

    caso = Caso.objects.create(
        institucion=t.destino, version=ver, ciudadano=paciente, area_actual=area,
        prioridad=Caso.Prioridad.URGENTE if t.urgente else t.caso_origen.prioridad,
    )
    motor_casos._registrar(
        caso, f"Recibido por traslado desde {t.origen}",
        detalle=t.detalle[:200] or t.get_motivo_display(), autor=autor,
    )
    motor_casos.iniciar(caso, autor=autor)

    t.caso_destino = caso
    t.ciudadano_destino = paciente
    t.area_destino = area
    t.estado = Traslado.Estado.ACEPTADO
    t.resuelto_por = autor
    t.resuelto_at = timezone.now()
    t.save(update_fields=["caso_destino", "ciudadano_destino", "area_destino", "estado",
                          "resuelto_por", "resuelto_at"])

    motor_casos._registrar(
        t.caso_origen, f"Traslado aceptado por {t.destino}",
        detalle=area.nombre, autor=autor, nodo=t.caso_origen.nodo_actual,
    )
    _avisar_origen(t, "Traslado aceptado", f"{t.destino} recibe a {t.ciudadano}")
    return t


@transaction.atomic
def rechazar(t: Traslado, motivo: str, autor=None) -> Traslado:
    """
    El destino no puede recibirlo, y dice por qué.

    El motivo no es cortesía: sin él, quien deriva no sabe si insistir, buscar
    otro establecimiento o esperar. Y el caso de origen se destraba, porque el
    paciente vuelve a ser responsabilidad de quien lo tiene.
    """
    t = _bloquear(t)
    if t.estado != Traslado.Estado.SOLICITADO:
        raise ErrorTraslado(f"El traslado ya está {t.get_estado_display().lower()}.")
    if not motivo.strip():
        raise ErrorTraslado("Un rechazo necesita un motivo.")

    t.estado = Traslado.Estado.RECHAZADO
    t.respuesta = motivo[:4000]
    t.resuelto_por = autor
    t.resuelto_at = timezone.now()
    t.save(update_fields=["estado", "respuesta", "resuelto_por", "resuelto_at"])
    _destrabar_origen(t, f"Traslado rechazado por {t.destino}", motivo, autor)
    _avisar_origen(t, f"Traslado rechazado por {t.destino}", motivo)
    return t


@transaction.atomic
def cancelar(t: Traslado, autor=None, motivo="") -> Traslado:
    """El origen se arrepiente: el paciente mejoró, o se consiguió otro lugar."""
    t = _bloquear(t)
    if not t.abierto:
        raise ErrorTraslado("El traslado ya está cerrado.")
    if t.caso_destino_id:
        raise ErrorTraslado(
            "El destino ya abrió el caso: hay que resolverlo allá, no cancelarlo desde acá."
        )
    t.estado = Traslado.Estado.CANCELADO
    t.respuesta = motivo[:4000]
    t.resuelto_at = timezone.now()
    t.resuelto_por = autor
    t.save(update_fields=["estado", "respuesta", "resuelto_at", "resuelto_por"])
    _destrabar_origen(t, "Traslado cancelado", motivo, autor)
    # Del otro lado ya reservaron una cama y avisaron al área por la
    # notificación del pedido: sin ésta, la cama queda bloqueada esperando una
    # ambulancia que no sale y nadie sabe por qué.
    _avisar_destino(
        t, f"Traslado cancelado por {t.origen}",
        f"{t.ciudadano} · {motivo}".strip(" ·") or str(t.ciudadano),
    )
    return t


@transaction.atomic
def no_llego(t: Traslado, motivo: str, autor=None) -> Traslado:
    """
    El traslado se aceptó pero el paciente no llegó.

    Los tres desenlaces habituales del traslado que sale mal —se descompensó y
    falleció en la ambulancia, la familia se lo llevó, el móvil lo desvió a un
    efector más cercano— no tenían dónde registrarse: después de ACEPTADO no
    quedaba más transición que «llegó». El caso de origen se congelaba EN_ESPERA
    sin poder avanzar ni cerrar, con el paciente muchas veces todavía ahí, y en
    el destino quedaba un caso abierto por alguien que no iba a aparecer.

    Lo puede registrar cualquiera de los dos lados: el que se enteró primero.
    El motivo es obligatorio porque «falleció en el traslado» y «lo retiró la
    familia» no son lo mismo para la región.
    """
    t = _bloquear(t)
    if t.estado not in (Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO):
        raise ErrorTraslado("Sólo un traslado en curso puede darse por no llegado.")
    if not motivo.strip():
        raise ErrorTraslado("Un traslado que no llegó necesita un motivo.")

    t.estado = Traslado.Estado.FALLIDO
    t.respuesta = motivo[:4000]
    # `resuelto_at` / `resuelto_por` NO se pisan: son de cuándo y quién contestó
    # el pedido, y de ahí sale «cuánto tarda este hospital en responder», el
    # indicador que más le importa a quien deriva. Pisarlos acá lo haría medir
    # otra cosa, y perdería a quien reservó la cama.
    t.save(update_fields=["estado", "respuesta"])

    # El caso que abrió el destino se cancela: es trabajo en su bandeja y una
    # cama comprometida por un paciente que no va a llegar.
    if t.caso_destino_id and t.caso_destino.estado not in (
        Caso.Estado.CERRADO, Caso.Estado.CANCELADO
    ):
        motor_casos.cancelar_caso(
            t.caso_destino, autor=autor, motivo=f"Traslado no concretado: {motivo}"[:200]
        )

    _destrabar_origen(t, "El traslado no se concretó", motivo, autor)
    _avisar_origen(t, "El traslado no se concretó", motivo)
    _avisar_destino(t, f"Traslado no concretado desde {t.origen}", f"{t.ciudadano} · {motivo}")
    return t


@transaction.atomic
def marcar_en_camino(t: Traslado, movil="", autor=None) -> Traslado:
    """Salió la ambulancia."""
    t = _bloquear(t)
    if t.estado != Traslado.Estado.ACEPTADO:
        raise ErrorTraslado("Sólo un traslado aceptado puede salir.")
    t.estado = Traslado.Estado.EN_CAMINO
    t.salida_at = timezone.now()
    t.movil = movil[:80]
    t.save(update_fields=["estado", "salida_at", "movil"])
    motor_casos._registrar(
        t.caso_origen, "Paciente en camino", detalle=movil or t.destino.nombre,
        autor=autor, nodo=t.caso_origen.nodo_actual,
    )
    # El que reservó la cama necesita saber que salió y en qué móvil viene. La
    # marca sólo se asienta en el caso de ORIGEN, que el destino no puede leer:
    # sin este aviso, la única forma de enterarse es el teléfono, que es lo que
    # este módulo vino a reemplazar.
    hora = timezone.localtime(t.salida_at).strftime("%H:%M")
    _avisar_destino(
        t, f"Paciente en camino desde {t.origen}",
        f"{t.ciudadano} · salió {hora}" + (f" · {t.movil}" if t.movil else ""),
    )
    return t


@transaction.atomic
def marcar_recibido(t: Traslado, autor=None) -> Traslado:
    """
    Llegó. Recién acá se cierra el caso de origen.

    Antes no: mientras el paciente está en la ambulancia sigue siendo
    responsabilidad de quien lo mandó, y un caso cerrado desaparece de su
    bandeja.
    """
    from apps.instituciones.models import EstadiaCama

    t = _bloquear(t)
    if t.estado not in (Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO):
        raise ErrorTraslado("El traslado no está en curso.")
    t.estado = Traslado.Estado.RECIBIDO
    t.llegada_at = timezone.now()
    t.save(update_fields=["estado", "llegada_at"])

    caso = t.caso_origen
    # El paciente se fue en la ambulancia: sus recursos se cierran acá, como en
    # los otros dos finales del sistema (el nodo FIN y `cancelar_caso`). Sin
    # esto la cama del origen queda OCUPADA con su nombre y la estadía abierta
    # para siempre —nada la libera sola—, y acá es peor que en un hospital solo:
    # esa ocupación falsa es la que alimentan `camas_en_red()`, `saturadas()` y
    # el desplegable de destinos, así que el efector que deriva se muestra más
    # lleno de lo que está, se marca SATURADO y la red le deja de mandar
    # pacientes. Cada traslado que sale bien empeoraba, en silencio, la
    # información con la que se decide a dónde va la próxima ambulancia.
    motor_casos._liberar_camas_del_caso(caso, EstadiaCama.Egreso.DERIVACION, autor=autor)
    # Y sale de las colas: un paciente que ya está internado en otro hospital no
    # puede seguir esperando a que lo llamen de un box de éste.
    caso.en_filas.filter(atendido=False).update(atendido=True)
    caso.esperando = False
    caso.estado = Caso.Estado.DERIVADO
    caso.save(update_fields=["esperando", "estado", "actualizado"])
    motor_casos._registrar(
        caso, f"Paciente recibido en {t.destino}",
        detalle=f"traslado #{t.pk}", autor=autor, nodo=caso.nodo_actual,
    )
    _avisar_origen(t, f"Paciente recibido en {t.destino}", str(t.ciudadano))
    return t


def _destrabar_origen(t: Traslado, titulo, detalle, autor):
    caso = t.caso_origen
    caso.esperando = False
    if caso.estado == Caso.Estado.EN_ESPERA:
        caso.estado = Caso.Estado.EN_EVALUACION
    caso.save(update_fields=["esperando", "estado", "actualizado"])
    motor_casos._registrar(caso, titulo, detalle=detalle[:200], autor=autor, nodo=caso.nodo_actual)


def _avisar_origen(t: Traslado, titulo, detalle):
    from apps.casos.models import Notificacion

    destinatarios = {t.solicitado_por} | (
        {t.caso_origen.asignado_a} if t.caso_origen.asignado_a_id else set()
    )
    for u in destinatarios:
        if u is not None:
            Notificacion.objects.create(
                usuario=u, titulo=titulo, detalle=detalle[:255], caso=t.caso_origen
            )


# --------------------------------------------------------------------------- #
# Panorama de la red
# --------------------------------------------------------------------------- #
def camas_en_red(red: Red):
    """
    Disponibilidad de camas de toda la red, por establecimiento.

    Es lo que hace posible derivar con criterio: sin esto, quien deriva llama
    por teléfono a preguntar si hay lugar, y muchas veces manda la ambulancia a
    un hospital que ya está lleno.
    """
    from django.db.models import Count

    from apps.instituciones.models import Cama

    instituciones = list(red.instituciones.filter(activa=True).order_by("nombre"))
    # Una sola agregación para toda la red, y no cuatro count() por
    # establecimiento: esto lo llama `saturadas()`, que a su vez se llama por
    # cada destino posible del desplegable de derivación. Con cuatro consultas
    # por efector, una red de 16 hospitales hacía más de mil consultas mientras
    # hay un paciente esperando adelante.
    por_inst = {
        c["area__institucion"]: c
        for c in Cama.objects.filter(
            area__institucion__in=[i.id for i in instituciones], activa=True
        ).values("area__institucion").annotate(
            total=Count("id"),
            fuera=Count("id", filter=Q(estado=Cama.Estado.BLOQUEADA)),
            ocupadas=Count("id", filter=Q(estado=Cama.Estado.OCUPADA)),
            libres=Count("id", filter=Q(estado=Cama.Estado.LIBRE)),
            higiene=Count("id", filter=Q(estado=Cama.Estado.HIGIENE)),
        )
    }

    salida = []
    for inst in instituciones:
        c = por_inst.get(inst.id) or {}
        total = c.get("total", 0)
        ocupadas = c.get("ocupadas", 0)
        operativas = total - c.get("fuera", 0)
        salida.append({
            "institucion": inst,
            "total": total,
            "operativas": operativas,
            "ocupadas": ocupadas,
            "libres": c.get("libres", 0),
            # Las camas en higiene no son ni libres ni ocupadas, y sin exponerlas
            # desaparecen de la red: son las que se liberan con un llamado a
            # limpieza, o sea la diferencia entre «no hay lugar» y «hay lugar en
            # veinte minutos». Además son las que explican por qué libres +
            # ocupadas no da operativas, que leído en la pantalla parece un
            # número mal calculado.
            "higiene": c.get("higiene", 0),
            "ocupacion": round(100 * ocupadas / operativas) if operativas else 0,
        })
    return salida


def saturadas(red: Red, umbral=90):
    """
    Establecimientos por encima del umbral de ocupación.

    Se calcula sobre camas en servicio, igual que en el tablero de cada
    hospital: un criterio distinto en la red que en la casa haría que los dos
    números se contradigan y no se pueda confiar en ninguno.
    """
    return saturadas_de(camas_en_red(red), umbral)


def saturadas_de(camas, umbral=90):
    """
    Lo mismo, sobre un panorama de camas YA calculado.

    El umbral vive en un solo lugar y el tablero no vuelve a recorrer la red
    entera para saber quién está lleno: `camas_en_red()` ya se calculó unas
    líneas más arriba y el resultado es idéntico.
    """
    return [c for c in camas if c["operativas"] and c["ocupacion"] >= umbral]


def _minutos(promedio):
    """
    Un promedio de duración calculado por la base, en minutos.

    Postgres devuelve `timedelta` y SQLite un número de microsegundos. Sin
    normalizarlo, el mismo tablero muestra «12′» en el servidor y un número de
    siete cifras en una corrida local, y nadie sabe cuál de los dos creer.
    """
    from datetime import timedelta

    if promedio is None:
        return None
    if isinstance(promedio, timedelta):
        return round(promedio.total_seconds() / 60)
    return round(float(promedio) / 60_000_000)


def tablero(red: Red, dias=30):
    """
    Panorama de la red: cada establecimiento con sus indicadores, comparables
    entre sí.

    Comparables es la palabra: los números se calculan igual en todos —misma
    definición de ocupación, mismo rango de fechas— porque una región usa este
    tablero para decidir a dónde mandar recursos, y dos criterios distintos
    harían que la comparación mienta.

    Los traslados se cuentan por establecimiento de ORIGEN: «cuántos derivó» es
    una medida de lo que ese efector no pudo resolver, que es lo que la región
    quiere ver.

    **Todo se agrega en la base, no de a un establecimiento por vez.** Antes esto
    hacía ocho consultas por efector y traía a memoria los traslados resueltos de
    cada uno: 32 consultas con 3 hospitales y 248 con 30. Una región sanitaria no
    tiene 3 efectores, tiene 40, y esta pantalla es la que abre dirección contra
    la misma base que en ese momento está atendiendo la guardia.
    """
    from datetime import timedelta

    from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Min

    from apps.casos.models import Caso

    desde = timezone.now() - timedelta(days=dias)
    camas = camas_en_red(red)
    instituciones = [c["institucion"] for c in camas]
    por_camas = {c["institucion"].id: c for c in camas}
    ids = [i.id for i in instituciones]

    activo = ~Q(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
    por_casos = {
        c["institucion"]: c
        for c in Caso.objects.filter(institucion__in=ids).values("institucion").annotate(
            activos=Count("id", filter=activo),
            ingresos=Count("id", filter=Q(creado__gte=desde)),
            urgentes=Count("id", filter=activo & Q(prioridad=Caso.Prioridad.URGENTE)),
        )
    }
    por_enviados = {
        t["origen"]: t
        for t in Traslado.objects.filter(origen__in=ids, solicitado_at__gte=desde)
        .values("origen").annotate(derivo=Count("id"))
    }
    espera = ExpressionWrapper(
        F("resuelto_at") - F("solicitado_at"), output_field=DurationField()
    )
    por_recibidos = {
        t["destino"]: t
        for t in Traslado.objects.filter(destino__in=ids, solicitado_at__gte=desde)
        .values("destino").annotate(
            recibio=Count("id"),
            rechazados=Count("id", filter=Q(estado=Traslado.Estado.RECHAZADO)),
            # Cuánto tarda en contestar un pedido de traslado. Es el indicador
            # que más le importa a quien deriva: un hospital que tarda seis
            # horas en decir que sí es, en la práctica, un hospital que no
            # recibe.
            demora=Avg(espera, filter=Q(resuelto_at__isnull=False)),
        )
    }
    # «Sin responder» NO se recorta por el período: es el estado de ahora, no un
    # hecho de la ventana. Contándolo sobre `desde`, elegir «7 días» escondía
    # justamente los peores casos —un pedido que lleva nueve días sin respuesta
    # dejaba de contarse y la cifra ámbar bajaba sin que nada lo explicara—, con
    # un paciente esperando en otra guardia por cada uno. Va con la antigüedad
    # del más viejo, que es el dato que decide si alguien levanta el teléfono.
    por_pendientes = {
        t["destino"]: t
        for t in Traslado.objects.filter(destino__in=ids, estado=Traslado.Estado.SOLICITADO)
        .values("destino").annotate(pendientes=Count("id"), mas_viejo=Min("solicitado_at"))
    }

    filas = []
    for inst in instituciones:
        cam = por_camas.get(inst.id, {})
        cas = por_casos.get(inst.id, {})
        env = por_enviados.get(inst.id, {})
        rec = por_recibidos.get(inst.id, {})
        pen = por_pendientes.get(inst.id, {})
        filas.append({
            "institucion": inst,
            "casos_activos": cas.get("activos", 0),
            "ingresos": cas.get("ingresos", 0),
            "urgentes": cas.get("urgentes", 0),
            "camas_operativas": cam.get("operativas", 0),
            "camas_libres": cam.get("libres", 0),
            "camas_higiene": cam.get("higiene", 0),
            "ocupacion": cam.get("ocupacion", 0),
            "derivo": env.get("derivo", 0),
            "recibio": rec.get("recibio", 0),
            "demora_respuesta_min": _minutos(rec.get("demora")),
            "rechazados": rec.get("rechazados", 0),
            "pendientes": pen.get("pendientes", 0),
            "pendiente_mas_viejo": pen.get("mas_viejo"),
        })

    viaje = ExpressionWrapper(
        F("llegada_at") - F("salida_at"), output_field=DurationField()
    )
    # Sobre los mismos establecimientos que las filas, para que los totales sean
    # la suma de lo que se está mirando y no de algo más.
    totales = Traslado.objects.filter(origen__in=ids, solicitado_at__gte=desde).aggregate(
        traslados=Count("id"),
        resueltos=Count("id", filter=Q(resuelto_at__isnull=False)),
        # Sobre los RESUELTOS: incluir los que todavía nadie contestó haría
        # que el porcentaje mejore solo por dejar pedidos sin responder.
        rechazados=Count("id", filter=Q(estado=Traslado.Estado.RECHAZADO)),
        viaje=Avg(viaje, filter=Q(salida_at__isnull=False, llegada_at__isnull=False)),
    )
    sin_responder = Traslado.objects.filter(
        origen__in=ids, estado=Traslado.Estado.SOLICITADO
    ).aggregate(n=Count("id"), mas_viejo=Min("solicitado_at"))

    return {
        "red": red,
        "dias": dias,
        "establecimientos": filas,
        "totales": {
            "casos_activos": sum(f["casos_activos"] for f in filas),
            "camas_operativas": sum(f["camas_operativas"] for f in filas),
            "camas_libres": sum(f["camas_libres"] for f in filas),
            "camas_higiene": sum(f["camas_higiene"] for f in filas),
            "traslados": totales["traslados"],
            "pendientes": sin_responder["n"],
            "pendiente_mas_viejo": sin_responder["mas_viejo"],
            "rechazo_pct": (
                round(100 * totales["rechazados"] / totales["resueltos"])
                if totales["resueltos"] else 0
            ),
            "viaje_prom_min": _minutos(totales["viaje"]),
        },
        "saturados": [s["institucion"].nombre for s in saturadas_de(camas)],
    }
