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


def _avisar_destino(t: Traslado):
    """
    Avisa a quien puede resolverlo en el establecimiento de destino.

    Un traslado que nadie mira es un paciente esperando. Se avisa a los jefes y
    administrativos del área destino, o de toda la institución si no se indicó
    área.
    """
    from apps.accounts.models import Membresia
    from apps.casos.models import Notificacion

    qs = Membresia.objects.filter(
        activo=True, institucion=t.destino, rol__in=["administrativo", "jefe_area", "admin"]
    )
    if t.area_destino_id:
        qs = qs.filter(Q(areas=t.area_destino_id) | Q(rol="admin"))
    titulo = f"Traslado {'URGENTE ' if t.urgente else ''}desde {t.origen}"
    detalle = f"{t.ciudadano} · {t.get_motivo_display()}"
    for m in qs.select_related("usuario").distinct():
        Notificacion.objects.create(usuario=m.usuario, titulo=titulo, detalle=detalle[:255])


@transaction.atomic
def aceptar(t: Traslado, autor=None, area_destino=None) -> Traslado:
    """
    El destino acepta y abre el caso de su lado.

    El caso nuevo es del destino: su institución, su flujo, su gente. Lo único
    que viaja es el paciente y el resumen que escribió el origen.
    """
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

    caso = Caso.objects.create(
        institucion=t.destino, version=ver, ciudadano=t.ciudadano, area_actual=area,
        prioridad=Caso.Prioridad.URGENTE if t.urgente else t.caso_origen.prioridad,
    )
    motor_casos._registrar(
        caso, f"Recibido por traslado desde {t.origen}",
        detalle=t.detalle[:200] or t.get_motivo_display(), autor=autor,
    )
    motor_casos.iniciar(caso, autor=autor)

    t.caso_destino = caso
    t.area_destino = area
    t.estado = Traslado.Estado.ACEPTADO
    t.resuelto_por = autor
    t.resuelto_at = timezone.now()
    t.save(update_fields=["caso_destino", "area_destino", "estado", "resuelto_por", "resuelto_at"])

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
    return t


@transaction.atomic
def marcar_en_camino(t: Traslado, movil="", autor=None) -> Traslado:
    """Salió la ambulancia."""
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
    return t


@transaction.atomic
def marcar_recibido(t: Traslado, autor=None) -> Traslado:
    """
    Llegó. Recién acá se cierra el caso de origen.

    Antes no: mientras el paciente está en la ambulancia sigue siendo
    responsabilidad de quien lo mandó, y un caso cerrado desaparece de su
    bandeja.
    """
    if t.estado not in (Traslado.Estado.ACEPTADO, Traslado.Estado.EN_CAMINO):
        raise ErrorTraslado("El traslado no está en curso.")
    t.estado = Traslado.Estado.RECIBIDO
    t.llegada_at = timezone.now()
    t.save(update_fields=["estado", "llegada_at"])

    caso = t.caso_origen
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
    from apps.instituciones.models import Cama

    salida = []
    for inst in red.instituciones.filter(activa=True).order_by("nombre"):
        camas = Cama.objects.filter(area__institucion=inst, activa=True)
        total = camas.count()
        fuera = camas.filter(estado=Cama.Estado.BLOQUEADA).count()
        ocupadas = camas.filter(estado=Cama.Estado.OCUPADA).count()
        operativas = total - fuera
        salida.append({
            "institucion": inst,
            "total": total,
            "operativas": operativas,
            "ocupadas": ocupadas,
            "libres": camas.filter(estado=Cama.Estado.LIBRE).count(),
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
    return [c for c in camas_en_red(red) if c["operativas"] and c["ocupacion"] >= umbral]
