"""
Proceso periódico de la agenda: arma la lista de llamados del día siguiente.

**Qué es un recordatorio acá.** Cauce no tiene canal al paciente —no manda SMS
ni mail— y fingir que sí sería peor que no tenerlo: el turno figuraría avisado
sin que nadie se haya enterado. Lo que sí existe en un hospital público es que
alguien del mostrador llama por teléfono a los turnos del día siguiente, y esa
persona necesita saber a quién llamar. Eso es lo que arma este comando.

El circuito completo queda: el comando avisa al administrativo del área cuántos
turnos hay para confirmar, la persona llama, y marca `confirmar` en cada uno.
`recordado_at` guarda cuándo se avisó, que es con lo que después se puede medir
si llamar baja el ausentismo.

Se corre una vez por día:

    0 18 * * *  cd /app && python manage.py recordar_turnos

Es idempotente: los turnos ya avisados no se vuelven a contar, así que correrlo
dos veces el mismo día no duplica el aviso.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import Membresia
from apps.casos.models import Notificacion
from apps.agenda.models import Turno


class Command(BaseCommand):
    help = "Avisa al mostrador qué turnos del día siguiente hay que confirmar."

    def add_arguments(self, parser):
        parser.add_argument("--seco", action="store_true", help="Muestra qué haría, sin tocar nada.")
        parser.add_argument(
            "--dias", type=int, default=1,
            help="Cuántos días adelante mirar (1 = mañana).",
        )

    def handle(self, *args, **opciones):
        seco = opciones["seco"]
        objetivo = timezone.localdate() + timedelta(days=opciones["dias"])

        # Sólo los que siguen sin confirmar Y sin haber entrado nunca en una
        # lista de llamados. Los ya confirmados no se llaman de nuevo, los
        # cancelados o resueltos no se llaman nunca, y los ya listados tampoco:
        # sin ese último filtro, correr el comando dos veces el mismo día
        # mandaba el aviso dos veces —el docstring prometía que era idempotente
        # y no lo era—.
        pendientes = (
            Turno.objects.filter(
                inicio__date=objetivo,
                estado=Turno.Estado.RESERVADO,
                recordado_at__isnull=True,
            )
            .select_related("agenda__area", "agenda__institucion", "ciudadano")
        )
        total = pendientes.count()
        if not total:
            self.stdout.write(f"Sin turnos por confirmar para el {objetivo:%d/%m}.")
            return

        # Se agrupa por área: quien llama es del mostrador de esa área, y una
        # notificación por turno sería una lluvia de avisos inservible.
        por_area = {}
        for t in pendientes:
            por_area.setdefault(t.agenda.area_id, []).append(t)

        avisos, huerfanos, avisados = 0, [], []
        for area_id, turnos in por_area.items():
            area = turnos[0].agenda.area
            destinatarios = (
                Membresia.objects.filter(
                    activo=True, areas=area_id,
                    rol__in=["administrativo", "jefe_area", "admin"],
                )
                .select_related("usuario")
                .distinct()
            )
            if not destinatarios.exists():
                # Un área sin nadie del mostrador deja su lista de llamados sin
                # dueño. Callarlo es peor que no tener el comando: los turnos
                # quedan marcados como recordados y nadie llamó.
                huerfanos.append((area.nombre, len(turnos)))
                continue
            avisados += [t.id for t in turnos]
            agendas = sorted({t.agenda.nombre for t in turnos})
            titulo = f"{len(turnos)} turnos por confirmar para el {objetivo:%d/%m}"
            detalle = f"{area.nombre} · {', '.join(agendas)}"
            for m in destinatarios:
                if seco:
                    self.stdout.write(f"  [seco] {m.usuario.email}: {titulo} — {detalle}")
                else:
                    Notificacion.objects.create(
                        usuario=m.usuario, titulo=titulo, detalle=detalle[:255]
                    )
                avisos += 1

        for nombre, cuantos in huerfanos:
            self.stderr.write(
                f"  SIN DESTINATARIO: {cuantos} turno(s) en «{nombre}». El área no tiene "
                f"nadie con rol administrativo, jefe o admin, así que esa lista de "
                f"llamados no le llega a nadie."
            )

        if not seco:
            # `recordado_at` marca que ya entraron en una lista de llamados que
            # ALGUIEN recibió. Marcar también los huérfanos los daría por
            # recordados sin que nadie los vaya a llamar, que es justo el
            # problema que el aviso de arriba señala.
            #
            # No cambia el estado: confirmar es cuando el paciente CONTESTA, y
            # darlo por confirmado porque salió en una lista sería inventar.
            Turno.objects.filter(id__in=avisados).update(recordado_at=timezone.now())

        sin_dueno = sum(c for _, c in huerfanos)
        self.stdout.write(
            f"{total} turno(s) por confirmar para el {objetivo:%d/%m} · "
            f"{avisos} aviso(s) a mostrador"
            + (f" · {sin_dueno} sin destinatario" if sin_dueno else "")
        )
