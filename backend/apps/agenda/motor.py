"""
Operaciones sobre la agenda de turnos.

Igual que el motor de casos: acá vive la regla, y la API y las pantallas sólo la
invocan. Nada de esto se puede hacer editando el modelo directamente sin romper
alguna cuenta.
"""
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.casos import motor as motor_casos
from apps.casos.models import Caso

from .models import Bloqueo, Disponibilidad, Turno


class ErrorAgenda(Exception):
    """Regla de agenda incumplida. La API la traduce a un 400 con el texto."""


def _zona(fecha, hora):
    return timezone.make_aware(datetime.combine(fecha, hora), timezone.get_current_timezone())


def horarios_del_dia(agenda, fecha):
    """
    Horarios de esa agenda ese día, con su ocupación.

    Devuelve `[{inicio, duracion_min, ocupado, turno_id, paciente, sobreturnos,
    admite_sobreturno}]`. Un horario ocupado sigue apareciendo: quien atiende el
    mostrador necesita ver la grilla completa, no sólo lo que queda —si no, no
    puede decir «a las 10 está la Dra. con otro paciente, ¿le sirve 10:20?».
    """
    disponibilidades = list(agenda.disponibilidades.filter(activa=True))
    bloqueos = list(agenda.bloqueos.all())
    inicio_dia = _zona(fecha, datetime.min.time())
    fin_dia = inicio_dia + timedelta(days=1)

    # Un turno cancelado libera el horario; el resto lo ocupa.
    turnos = list(
        agenda.turnos.select_related("ciudadano")
        .filter(inicio__gte=inicio_dia, inicio__lt=fin_dia)
        .exclude(estado=Turno.Estado.CANCELADO)
    )
    normales = {}
    sobre = {}
    for t in turnos:
        (sobre if t.sobreturno else normales).setdefault(t.inicio, []).append(t)

    salida = []
    for d in disponibilidades:
        for momento in d.horarios(fecha):
            if any(b.cubre(momento) for b in bloqueos):
                continue
            ocupantes = normales.get(momento, [])
            extras = sobre.get(momento, [])
            ocupante = ocupantes[0] if ocupantes else None
            salida.append({
                "inicio": momento,
                "duracion_min": d.paso_min,
                "ocupado": ocupante is not None,
                "turno_id": ocupante.id if ocupante else None,
                "paciente": (
                    f"{ocupante.ciudadano.nombre} {ocupante.ciudadano.apellido}".strip()
                    if ocupante else None
                ),
                "estado": ocupante.estado if ocupante else None,
                "sobreturnos": len(extras),
                "admite_sobreturno": len(extras) < agenda.sobreturnos_max,
            })
    salida.sort(key=lambda h: h["inicio"])
    return salida


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
    """
    if not agenda.activa:
        raise ErrorAgenda("La agenda no está activa.")
    duracion = _valida_horario(agenda, inicio)

    ocupados = list(
        Turno.objects.select_for_update()
        .filter(agenda=agenda, inicio=inicio)
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

    return Turno.objects.create(
        agenda=agenda, ciudadano=ciudadano, inicio=inicio, duracion_min=duracion,
        sobreturno=sobreturno, motivo=motivo[:200], origen=origen, creado_por=autor,
    )


@transaction.atomic
def cancelar(turno: Turno, autor=None, motivo="") -> Turno:
    """Cancela el turno y libera el horario."""
    if turno.estado in (Turno.Estado.PRESENTE, Turno.Estado.AUSENTE):
        raise ErrorAgenda("El turno ya fue resuelto: no se puede cancelar.")
    if turno.estado == Turno.Estado.CANCELADO:
        raise ErrorAgenda("El turno ya estaba cancelado.")
    turno.estado = Turno.Estado.CANCELADO
    turno.cancelado_at = timezone.now()
    if motivo:
        turno.observaciones = (turno.observaciones + "\n" + motivo).strip()
    turno.save(update_fields=["estado", "cancelado_at", "observaciones"])
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
    if turno.estado not in (Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO):
        raise ErrorAgenda("Sólo un turno pendiente puede quedar como ausente.")
    turno.estado = Turno.Estado.AUSENTE
    turno.save(update_fields=["estado"])
    return turno


@transaction.atomic
def confirmar(turno: Turno, autor=None) -> Turno:
    """El paciente avisó que viene (llamado de recordatorio contestado)."""
    if turno.estado != Turno.Estado.RESERVADO:
        raise ErrorAgenda("Sólo un turno reservado se puede confirmar.")
    turno.estado = Turno.Estado.CONFIRMADO
    turno.recordado_at = timezone.now()
    turno.save(update_fields=["estado", "recordado_at"])
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
    if turno.estado in (Turno.Estado.CANCELADO, Turno.Estado.AUSENTE):
        raise ErrorAgenda("El turno ya fue resuelto.")
    if turno.estado == Turno.Estado.PRESENTE:
        raise ErrorAgenda("La llegada ya estaba registrada.")

    turno.estado = Turno.Estado.PRESENTE
    campos = ["estado"]

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


def proximos_libres(agenda, desde=None, dias=30, cuantos=10):
    """
    Los próximos horarios libres. Es lo que se necesita para dar un turno por
    teléfono sin tener que ir mirando día por día.
    """
    hoy = timezone.localdate(desde or timezone.now())
    ahora = desde or timezone.now()
    libres = []
    for i in range(dias):
        for h in horarios_del_dia(agenda, hoy + timedelta(days=i)):
            if not h["ocupado"] and h["inicio"] > ahora:
                libres.append(h)
                if len(libres) >= cuantos:
                    return libres
    return libres
