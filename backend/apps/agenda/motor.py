"""
Operaciones sobre la agenda de turnos.

Igual que el motor de casos: acá vive la regla, y la API y las pantallas sólo la
invocan. Nada de esto se puede hacer editando el modelo directamente sin romper
alguna cuenta.
"""
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.casos import motor as motor_casos
from apps.casos.models import Caso

from .models import Agenda, Bloqueo, Disponibilidad, Turno


class ErrorAgenda(Exception):
    """Regla de agenda incumplida. La API la traduce a un 400 con el texto."""


def _zona(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


def _fila(agenda, momento, duracion, ocupantes, extras, bloqueado=False, fuera=False):
    ocupante = ocupantes[0] if ocupantes else None
    return {
        "inicio": momento,
        "duracion_min": duracion,
        "ocupado": ocupante is not None,
        "turno_id": ocupante.id if ocupante else None,
        "paciente": (
            f"{ocupante.ciudadano.nombre} {ocupante.ciudadano.apellido}".strip()
            if ocupante else None
        ),
        "estado": ocupante.estado if ocupante else None,
        # Cuántos titulares hay de verdad. Normalmente 1: si alguna vez son 2,
        # el segundo paciente tiene el papel en la mano y para la pantalla no
        # existe, así que la grilla tiene que poder decirlo en vez de callarlo.
        "titulares": len(ocupantes),
        "sobreturnos": len(extras),
        # Sobre un horario bloqueado o fuera de grilla no se apila nada más: lo
        # que hay que hacer ahí es llamar al paciente, no sumarle otro.
        "admite_sobreturno": (
            not bloqueado and not fuera and len(extras) < agenda.sobreturnos_max
        ),
        "bloqueado": bloqueado,
        "fuera_de_grilla": fuera,
    }


def _grilla(agenda, fecha, disponibilidades, bloqueos, turnos):
    """
    Arma la grilla de un día con los datos YA cargados.

    Separada de `horarios_del_dia` para que `proximos_libres` pueda mirar 30
    días sin repetir las mismas tres consultas por cada uno.
    """
    normales, sobre = {}, {}
    for t in turnos:
        (sobre if t.sobreturno else normales).setdefault(t.inicio, []).append(t)

    salida, emitidos = [], set()
    for d in disponibilidades:
        for momento in d.horarios(fecha):
            if momento in emitidos:
                continue
            ocupantes = normales.get(momento, [])
            extras = sobre.get(momento, [])
            bloqueado = any(b.cubre(momento) for b in bloqueos)
            # Un horario bloqueado SIN turnos no se ofrece: la agenda no atiende.
            # Pero uno bloqueado CON turnos dados se emite igual, marcado.
            # Saltearlo borraba de la pantalla a los doce pacientes que ya
            # tenían hora: nadie se queda con la lista para llamarlos y viajan
            # al hospital para nada.
            if bloqueado and not ocupantes and not extras:
                continue
            emitidos.add(momento)
            salida.append(_fila(agenda, momento, d.paso_min, ocupantes, extras,
                                bloqueado=bloqueado))
    salida.sort(key=lambda h: h["inicio"])

    # Red de seguridad: todo turno vigente cuyo `inicio` no cae en ningún
    # horario generado. Pasa cada vez que se desactiva una franja, se le pone
    # `vigente_hasta` o se le cambia la duración: los turnos viejos dejan de
    # caer en la grilla nueva y desaparecían de la pantalla sin avisar.
    sueltos = []
    for momento in sorted(set(normales) | set(sobre)):
        if momento in emitidos:
            continue
        ocupantes = normales.get(momento, [])
        extras = sobre.get(momento, [])
        duracion = (ocupantes or extras)[0].duracion_min
        sueltos.append(_fila(agenda, momento, duracion, ocupantes, extras, fuera=True))
    return salida + sueltos


def horarios_del_dia(agenda, fecha):
    """
    Horarios de esa agenda ese día, con su ocupación.

    Devuelve `[{inicio, duracion_min, ocupado, turno_id, paciente, titulares,
    sobreturnos, admite_sobreturno, bloqueado, fuera_de_grilla}]`. Un horario
    ocupado sigue apareciendo: quien atiende el mostrador necesita ver la grilla
    completa, no sólo lo que queda —si no, no puede decir «a las 10 está la Dra.
    con otro paciente, ¿le sirve 10:20?».

    Ningún turno vigente puede quedar afuera de esta respuesta, aunque su
    horario esté bloqueado o ya no exista en la agenda: la lista de a quién hay
    que llamar sale de acá.
    """
    inicio_dia = _zona(fecha, datetime.min.time())
    fin_dia = inicio_dia + timedelta(days=1)
    disponibilidades = list(agenda.disponibilidades.filter(activa=True))
    bloqueos = list(agenda.bloqueos.filter(desde__lt=fin_dia, hasta__gt=inicio_dia))
    # Un turno cancelado libera el horario; el resto lo ocupa.
    turnos = list(
        agenda.turnos.select_related("ciudadano")
        .filter(inicio__gte=inicio_dia, inicio__lt=fin_dia)
        .exclude(estado=Turno.Estado.CANCELADO)
    )
    return _grilla(agenda, fecha, disponibilidades, bloqueos, turnos)


def turnos_en_rango(agenda, desde, hasta):
    """
    Turnos vigentes de esa agenda entre dos momentos.

    Es lo que hay que mirar ANTES de bloquear un día: bloquear no cancela nada,
    así que si nadie ve esta lista los turnos quedan dados y sin avisar.
    """
    # Con los relacionados que serializa `TurnoSerializer`: la lista puede tener
    # doce turnos y sin esto son doce consultas más por cada campo.
    return list(
        agenda.turnos.select_related("ciudadano", "agenda__area", "resuelto_por")
        .filter(inicio__gte=desde, inicio__lt=hasta)
        .exclude(estado=Turno.Estado.CANCELADO)
        .order_by("inicio")
    )


def _valida_horario(agenda, inicio):
    """¿Ese horario existe en la agenda y no está bloqueado?"""
    fecha = timezone.localtime(inicio).date()
    if any(b.cubre(inicio) for b in agenda.bloqueos.all()):
        raise ErrorAgenda("La agenda está bloqueada en ese horario.")
    for d in agenda.disponibilidades.filter(activa=True):
        if inicio in d.horarios(fecha):
            return d.paso_min
    raise ErrorAgenda("Ese horario no está en la agenda.")


@transaction.atomic
def reservar(agenda, ciudadano, inicio, autor=None, motivo="", origen=Turno.Origen.MOSTRADOR,
             sobreturno=False) -> Turno:
    """
    Da un turno.

    Dos personas pueden estar sacando turno para el mismo horario al mismo
    tiempo —una por teléfono y otra en el mostrador—, así que la comprobación de
    ocupado y la reserva van bajo el mismo candado.

    El candado va sobre la AGENDA y no sobre los turnos del horario: cuando el
    horario está libre no hay ninguna fila de turno que bloquear, y en Postgres
    un `SELECT ... FOR UPDATE` que no matchea nada no bloquea nada. Las dos
    transacciones leían la lista vacía, las dos pasaban el chequeo y quedaban
    dos titulares a las 10:00 —de los cuales la grilla muestra uno solo, así que
    el segundo paciente tiene el turno impreso y para el mostrador no existe—.
    """
    agenda = Agenda.objects.select_for_update().order_by().get(pk=agenda.pk)
    if not agenda.activa:
        raise ErrorAgenda("La agenda no está activa.")
    duracion = _valida_horario(agenda, inicio)

    ocupados = list(
        Turno.objects.filter(agenda=agenda, inicio=inicio)
        .exclude(estado=Turno.Estado.CANCELADO)
    )
    normales = [t for t in ocupados if not t.sobreturno]
    extras = [t for t in ocupados if t.sobreturno]

    if normales and not sobreturno:
        raise ErrorAgenda(
            f"Ese horario ya está tomado. Se puede dar como sobreturno "
            f"({len(extras)} de {agenda.sobreturnos_max} usados)."
        )
    if sobreturno:
        if not normales:
            # Pedir sobreturno sobre un horario libre es casi siempre un error
            # de quien opera; darlo igual desordena la grilla sin motivo.
            raise ErrorAgenda("Ese horario está libre: no hace falta un sobreturno.")
        if len(extras) >= agenda.sobreturnos_max:
            raise ErrorAgenda(
                f"Ya hay {len(extras)} sobreturnos en ese horario, el máximo de esta agenda."
            )

    # Un paciente no puede tener dos turnos activos en la misma agenda el mismo
    # día: casi siempre es un doble clic o alguien que llamó dos veces, y ocupa
    # un lugar que otro necesita.
    dia = timezone.localtime(inicio).date()
    ya = Turno.objects.filter(
        agenda=agenda, ciudadano=ciudadano,
        inicio__date=dia,
        estado__in=[Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO],
    ).exists()
    if ya:
        raise ErrorAgenda("Esa persona ya tiene un turno ese día en esta agenda.")

    try:
        # Savepoint propio: si la restricción de la base salta, la transacción
        # de afuera tiene que poder seguir para devolver el 400 en vez de un 500.
        with transaction.atomic():
            return Turno.objects.create(
                agenda=agenda, ciudadano=ciudadano, inicio=inicio, duracion_min=duracion,
                sobreturno=sobreturno, motivo=motivo[:200], origen=origen, creado_por=autor,
            )
    except IntegrityError:
        # La red de abajo del candado: `un_titular_por_horario`. Llega acá si
        # alguien crea turnos por fuera de esta función (el admin, una carga).
        raise ErrorAgenda("Ese horario ya está tomado.")


def _bajo_candado(turno: Turno) -> Turno:
    """
    Relee el turno bloqueando su fila.

    El turno llega desde `get_object()`, leído fuera de toda transacción: sin
    esto, dos «Llegó» solapados —el administrativo que aprieta de nuevo porque
    no respondió, o dos mostradores a la vez— leen los dos `reservado`, abren
    los dos un caso y el segundo `save` pisa `turno.caso`. Queda un caso
    fantasma en la fila del área: lo llaman por altavoz, no aparece nadie, y no
    se cierra nunca. Lo mismo deja pasar el cruce cancelar/llegada, que termina
    en un turno cancelado con un caso abierto y circulando.
    """
    return Turno.objects.select_for_update().order_by().get(pk=turno.pk)


def _firma(turno: Turno, autor):
    """
    Deja anotado quién movió el turno y cuándo.

    El reclamo típico del mostrador es «me cancelaron el turno y nadie me
    avisó», y el «no vino» es el estado que perjudica al paciente: sin esto no
    hay a quién preguntarle. Las tres funciones ya recibían `autor` y lo
    tiraban a la basura.
    """
    turno.resuelto_por = autor
    turno.resuelto_at = timezone.now()


@transaction.atomic
def cancelar(turno: Turno, autor=None, motivo="") -> Turno:
    """Cancela el turno y libera el horario."""
    turno = _bajo_candado(turno)
    if turno.estado in (Turno.Estado.PRESENTE, Turno.Estado.AUSENTE):
        raise ErrorAgenda("El turno ya fue resuelto: no se puede cancelar.")
    if turno.estado == Turno.Estado.CANCELADO:
        raise ErrorAgenda("El turno ya estaba cancelado.")
    turno.estado = Turno.Estado.CANCELADO
    turno.cancelado_at = timezone.now()
    if motivo:
        turno.observaciones = (turno.observaciones + "\n" + motivo).strip()
    _firma(turno, autor)
    turno.save(update_fields=["estado", "cancelado_at", "observaciones",
                              "resuelto_por", "resuelto_at"])
    return turno


@transaction.atomic
def marcar_ausente(turno: Turno, autor=None) -> Turno:
    """
    La persona no vino y no avisó.

    Se guarda aparte de «cancelado» a propósito: son dos problemas distintos
    —el turno cancelado con tiempo se puede reasignar, el ausente ya se
    perdió— y mezclarlos hace que el indicador de ausentismo no sirva para
    decidir nada.
    """
    turno = _bajo_candado(turno)
    if turno.estado not in (Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO):
        raise ErrorAgenda("Sólo un turno pendiente puede quedar como ausente.")
    turno.estado = Turno.Estado.AUSENTE
    _firma(turno, autor)
    turno.save(update_fields=["estado", "resuelto_por", "resuelto_at"])
    return turno


@transaction.atomic
def confirmar(turno: Turno, autor=None) -> Turno:
    """El paciente avisó que viene (llamado de recordatorio contestado)."""
    turno = _bajo_candado(turno)
    if turno.estado != Turno.Estado.RESERVADO:
        raise ErrorAgenda("Sólo un turno reservado se puede confirmar.")
    turno.estado = Turno.Estado.CONFIRMADO
    turno.recordado_at = timezone.now()
    _firma(turno, autor)
    turno.save(update_fields=["estado", "recordado_at", "resuelto_por", "resuelto_at"])
    return turno


@transaction.atomic
def registrar_llegada(turno: Turno, autor=None) -> Turno:
    """
    El paciente se presentó: arranca el caso.

    Esto es lo que hace que un turno valga algo. Sin este paso el turno es una
    anotación en una grilla y alguien tiene que abrir el caso a mano, copiando
    los datos que el sistema ya tiene.

    Si la agenda no declara flujo, el turno igual queda como presentado: es
    mejor registrar que la persona vino —el ausentismo depende de eso— que
    negarse porque falta una configuración.
    """
    turno = _bajo_candado(turno)
    if turno.estado in (Turno.Estado.CANCELADO, Turno.Estado.AUSENTE):
        raise ErrorAgenda("El turno ya fue resuelto.")
    if turno.estado == Turno.Estado.PRESENTE:
        raise ErrorAgenda("La llegada ya estaba registrada.")

    turno.estado = Turno.Estado.PRESENTE
    _firma(turno, autor)
    campos = ["estado", "resuelto_por", "resuelto_at"]

    flujo = turno.agenda.flujo
    if flujo is not None:
        version = flujo.versiones.filter(estado="publicada").order_by("-numero").first()
        if version is None:
            raise ErrorAgenda(
                f"El flujo «{flujo.titulo}» no tiene una versión publicada: "
                "no se puede abrir el caso."
            )
        caso = Caso.objects.create(
            institucion=turno.agenda.institucion,
            version=version,
            ciudadano=turno.ciudadano,
            area_actual=turno.agenda.area,
            # El turno lo trae quien lo atiende: si la agenda es de un
            # profesional, el caso ya nace con dueño.
            asignado_a=turno.agenda.profesional,
        )
        motor_casos.iniciar(caso, autor=autor)
        turno.caso = caso
        campos.append("caso")

    turno.save(update_fields=campos)
    return turno


@transaction.atomic
def reprogramar(turno: Turno, nuevo_inicio, autor=None) -> Turno:
    """
    Mueve un turno a otro horario de la misma agenda.

    Existe porque reprogramar es lo que más se pide después de dar el turno, y
    la forma obvia de hacerlo —un PATCH a `inicio`— no pasaba por ninguna regla:
    dejaba apilar un segundo titular sobre un horario tomado, meter el turno
    adentro de un bloqueo, o ponerlo a las 3 de la mañana de un día en que la
    agenda no atiende.
    """
    agenda = Agenda.objects.select_for_update().order_by().get(pk=turno.agenda_id)
    turno = _bajo_candado(turno)
    if turno.estado not in (Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO):
        raise ErrorAgenda("Sólo un turno pendiente se puede reprogramar.")
    if nuevo_inicio == turno.inicio:
        return turno
    if not agenda.activa:
        raise ErrorAgenda("La agenda no está activa.")
    duracion = _valida_horario(agenda, nuevo_inicio)

    ocupados = list(
        Turno.objects.filter(agenda=agenda, inicio=nuevo_inicio)
        .exclude(estado=Turno.Estado.CANCELADO)
        .exclude(pk=turno.pk)
    )
    titulares = [t for t in ocupados if not t.sobreturno]
    extras = [t for t in ocupados if t.sobreturno]
    if turno.sobreturno:
        if not titulares:
            raise ErrorAgenda("Ese horario está libre: no hace falta un sobreturno.")
        if len(extras) >= agenda.sobreturnos_max:
            raise ErrorAgenda(
                f"Ya hay {len(extras)} sobreturnos en ese horario, el máximo de esta agenda."
            )
    elif titulares:
        raise ErrorAgenda(
            f"Ese horario ya está tomado. Se puede dar como sobreturno "
            f"({len(extras)} de {agenda.sobreturnos_max} usados)."
        )

    ya = (
        Turno.objects.filter(
            agenda=agenda, ciudadano_id=turno.ciudadano_id,
            inicio__date=timezone.localtime(nuevo_inicio).date(),
            estado__in=[Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO],
        )
        .exclude(pk=turno.pk)
        .exists()
    )
    if ya:
        raise ErrorAgenda("Esa persona ya tiene un turno ese día en esta agenda.")

    anterior = timezone.localtime(turno.inicio)
    turno.inicio = nuevo_inicio
    turno.duracion_min = duracion
    # Queda escrito de dónde venía: si el paciente llega con el papel del
    # horario viejo, el mostrador tiene con qué explicarle qué pasó.
    turno.observaciones = (
        turno.observaciones + f"\nReprogramado desde el {anterior:%d/%m %H:%M}."
    ).strip()
    _firma(turno, autor)
    try:
        with transaction.atomic():
            turno.save(update_fields=["inicio", "duracion_min", "observaciones",
                                      "resuelto_por", "resuelto_at"])
    except IntegrityError:
        raise ErrorAgenda("Ese horario ya está tomado.")
    return turno


def proximos_libres(agenda, desde=None, dias=30, cuantos=10):
    """
    Los próximos horarios libres. Es lo que se necesita para dar un turno por
    teléfono sin tener que ir mirando día por día.

    Las tres consultas se hacen UNA vez para todo el rango y no una vez por día:
    con `dias=30` eran ~90 idas y vueltas a la base por llamada, y del otro lado
    hay alguien esperando en el teléfono. Ninguna de las tres depende del día.
    """
    ahora = desde or timezone.now()
    hoy = timezone.localdate(ahora)
    inicio_rango = _zona(hoy, datetime.min.time())
    fin_rango = _zona(hoy + timedelta(days=dias), datetime.min.time())

    disponibilidades = list(agenda.disponibilidades.filter(activa=True))
    bloqueos = list(agenda.bloqueos.filter(desde__lt=fin_rango, hasta__gt=inicio_rango))
    por_dia = {}
    for t in (
        agenda.turnos.select_related("ciudadano")
        .filter(inicio__gte=inicio_rango, inicio__lt=fin_rango)
        .exclude(estado=Turno.Estado.CANCELADO)
    ):
        por_dia.setdefault(timezone.localdate(t.inicio), []).append(t)

    libres = []
    for i in range(dias):
        fecha = hoy + timedelta(days=i)
        for h in _grilla(agenda, fecha, disponibilidades, bloqueos, por_dia.get(fecha, [])):
            if h["ocupado"] or h["bloqueado"] or h["fuera_de_grilla"]:
                continue
            if h["inicio"] > ahora:
                libres.append(h)
                if len(libres) >= cuantos:
                    return libres
    return libres
