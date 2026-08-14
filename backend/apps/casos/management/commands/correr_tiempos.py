"""
Proceso periódico de tiempos: reactiva esperas vencidas y avisa las demoras.

Sin esto, dos cosas del diseñador son sólo un dibujo:

  · La **espera por tiempo** no volvía nunca. Un caso que entraba a
    «Observación 6 horas» se quedaba ahí para siempre hasta que alguien lo
    tocara a mano. La duración era un rótulo informativo, nada más.

  · El **SLA** no existía. «Si tarda más de X, avisá» es lo primero que pide un
    director de hospital, y no había forma de expresarlo.

Se corre cada pocos minutos. En Docker Compose, con un contenedor que lo llame
en bucle; en un servidor, con cron o un timer de systemd:

    */5 * * * * cd /app && python manage.py correr_tiempos

Es idempotente y seguro de correr en paralelo consigo mismo: cada caso se toma
con `select_for_update(skip_locked=True)`, así dos pasadas superpuestas no
avanzan el mismo caso dos veces.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.auditoria.latidos import latir
from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Nodo


class Command(BaseCommand):
    help = "Reactiva esperas por tiempo vencidas y avisa las demoras (SLA)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seco", action="store_true",
            help="Muestra qué haría, sin tocar nada.",
        )
        parser.add_argument(
            "--limite", type=int, default=500,
            help="Tope de casos por pasada (evita una corrida eterna tras una caída).",
        )

    def handle(self, *args, **opciones):
        seco = opciones["seco"]
        limite = opciones["limite"]
        ahora = timezone.now()

        reactivados = self._reactivar(ahora, limite, seco)
        avisados = self._avisar_demoras(ahora, limite, seco)

        resumen = f"{reactivados} espera(s) reactivada(s) · {avisados} demora(s) avisada(s)"
        prefijo = "[en seco] " if seco else ""
        self.stdout.write(f"{prefijo}{resumen}")

        if not seco:
            # El latido va DESPUÉS de hacer el trabajo, no al empezar: lo que
            # interesa saber es que el proceso llegó hasta el final, no que
            # arrancó. Un bucle que arranca y muere a la mitad se vería sano.
            latir("correr_tiempos", resumen)

    # ----------------------------------------------------------------- #
    def _reactivar(self, ahora, limite, seco) -> int:
        """Avanza los casos cuya espera por tiempo ya venció."""
        pendientes = (
            Caso.objects
            .filter(reactivar_en__lte=ahora, nodo_actual__tipo=Nodo.Tipo.ESPERA_TIEMPO)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .order_by("reactivar_en")
            .values_list("pk", flat=True)[:limite]
        )
        hechos = 0
        for pk in list(pendientes):
            if seco:
                self.stdout.write(f"  reactivaría el caso #{pk}")
                hechos += 1
                continue
            try:
                with transaction.atomic():
                    caso = (
                        Caso.objects.select_for_update(skip_locked=True)
                        .filter(pk=pk, reactivar_en__lte=ahora)
                        .first()
                    )
                    # Otra pasada se lo llevó primero, o alguien lo avanzó a mano.
                    if caso is None:
                        continue
                    motor.avanzar(caso, {}, autor=None)
                hechos += 1
            except motor.ErrorMotor as e:
                # Un caso que no puede avanzar no debe frenar a los demás: se
                # anota en su propio historial y la pasada sigue.
                self.stderr.write(f"  caso #{pk}: {e}")
        return hechos

    # ----------------------------------------------------------------- #
    def _avisar_demoras(self, ahora, limite, seco) -> int:
        """
        Avisa cuando un caso lleva más tiempo del declarado en su paso.

        El plazo lo declara el nodo (`config.sla_minutos`). Sólo se mira lo que
        está detenido esperando a una persona: un nodo automático no puede
        «demorarse».
        """
        candidatos = (
            Caso.objects
            .filter(sla_avisado=False, paso_desde__isnull=False,
                    nodo_actual__tipo__in=list(motor.TIPOS_DETENCION))
            .exclude(nodo_actual__tipo=Nodo.Tipo.FIN)
            .exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
            .select_related("nodo_actual", "ciudadano")
            .order_by("paso_desde")[:limite]
        )

        hechos = 0
        for caso in candidatos:
            nodo = caso.nodo_actual
            plazo = motor.minutos_de_sla(nodo)
            if not plazo:
                continue
            demora = (ahora - caso.paso_desde).total_seconds() / 60
            if demora < plazo:
                continue

            paciente = motor._nombre_paciente(caso) or f"Caso #{caso.pk}"
            detalle = f"{paciente} lleva {int(demora)} min en «{nodo.titulo}» (límite: {plazo} min)."
            if seco:
                self.stdout.write(f"  avisaría: {detalle}")
                hechos += 1
                continue

            with transaction.atomic():
                motor._notificar_grupo(nodo, "Paso demorado", detalle, caso=caso)
                if (nodo.config or {}).get("sla_accion") == "escalar":
                    # Escalar = avisarle también al jefe del área, que es quien
                    # puede reasignar o pedir refuerzos.
                    self._avisar_a_jefes(caso, "Paso demorado — requiere atención", detalle)
                motor._registrar(caso, "Demora en el paso", detalle=detalle, nodo=nodo)
                # Se marca para no repetir el aviso en cada pasada: molestar cada
                # cinco minutos consigue que se ignoren todos los avisos.
                Caso.objects.filter(pk=caso.pk).update(sla_avisado=True)
            hechos += 1
        return hechos

    def _avisar_a_jefes(self, caso, titulo, detalle):
        from apps.accounts.models import Membresia

        area_id = caso.area_actual_id or (caso.version.flujo.area_id if caso.version_id else None)
        if not area_id:
            return
        jefes = Membresia.objects.filter(
            institucion=caso.institucion, rol=Membresia.Rol.JEFE_AREA,
            activo=True, areas=area_id,
        ).select_related("usuario")
        for m in jefes:
            motor._notificar(m.usuario, titulo, detalle, caso=caso)
