"""
Turnos programados.

Hasta acá el sistema sabía atender a quien llega: fila, llamado, atención. Esto
es lo otro —la persona que pidió turno para el martes a las 10— y es el módulo
que más se pide después de la guardia.

Tres piezas:

- `Agenda`: **qué** se agenda. Un profesional o un recurso (un tomógrafo, un
  consultorio). Se modelan igual a propósito: los dos se reservan por franjas,
  los dos tienen días y horarios, y separarlos duplicaría todo para que después
  alguien pregunte cómo agendar «el médico Y el equipo».
- `Disponibilidad`: **cuándo** atiende esa agenda. Una franja semanal repetida
  («martes de 8 a 12, cada 20 minutos»), no fechas sueltas: nadie carga a mano
  los turnos de un año.
- `Turno`: la reserva concreta de una persona en un horario.
"""
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone


class Agenda(models.Model):
    """Lo que se puede reservar: un profesional o un recurso."""

    class Tipo(models.TextChoices):
        PROFESIONAL = "profesional", "Profesional"
        RECURSO = "recurso", "Recurso"

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="agendas"
    )
    area = models.ForeignKey(
        "instituciones.Area", on_delete=models.CASCADE, related_name="agendas"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PROFESIONAL)
    nombre = models.CharField(max_length=150, help_text="Ej.: «Dra. Suárez» o «Tomógrafo»")
    # Sólo para agendas de profesional: quién atiende. Permite que la persona
    # vea su propia agenda y que el turno le asigne el caso al llegar.
    profesional = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="agendas",
    )
    # Flujo que se abre cuando el paciente llega. Sin esto un turno es una
    # anotación: alguien tiene que crear el caso a mano y el turno no sirvió de
    # nada. Con esto, presentarse al turno arranca el circuito de atención.
    flujo = models.ForeignKey(
        "flujos.Flujo", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="agendas",
        help_text="Flujo que se abre cuando el paciente se presenta al turno.",
    )
    duracion_min = models.PositiveIntegerField(
        "duración del turno (minutos)", default=20,
        help_text="Duración por defecto; cada franja puede pisarla.",
    )
    # Cuántos sobreturnos se aceptan por franja. Un sobreturno es un turno de
    # más sobre un horario ya lleno: existe en todas las agendas reales y si el
    # sistema no lo contempla, se anota en un papel y se pierde.
    sobreturnos_max = models.PositiveIntegerField("sobreturnos por franja", default=2)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "agenda"
        verbose_name_plural = "agendas"
        ordering = ["nombre"]
        unique_together = [("institucion", "nombre")]

    def __str__(self):
        return self.nombre


class Disponibilidad(models.Model):
    """
    Franja semanal de atención de una agenda.

    Se guarda la REGLA («martes de 8 a 12, cada 20 minutos»), no los turnos: en
    una agenda de un año son miles de filas que además habría que regenerar cada
    vez que el profesional cambia su horario. Los horarios concretos se calculan
    al consultar.
    """

    DIAS = [
        (0, "Lunes"), (1, "Martes"), (2, "Miércoles"), (3, "Jueves"),
        (4, "Viernes"), (5, "Sábado"), (6, "Domingo"),
    ]

    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="disponibilidades")
    dia_semana = models.PositiveSmallIntegerField("día", choices=DIAS)
    desde = models.TimeField("desde")
    hasta = models.TimeField("hasta")
    # Pisa la duración de la agenda: los turnos de la tarde pueden ser más
    # largos que los de la mañana.
    duracion_min = models.PositiveIntegerField(
        "duración (minutos)", null=True, blank=True,
        help_text="Si se deja vacío, usa la de la agenda.",
    )
    # Desde y hasta cuándo rige esta franja. Sirve para cargar el horario nuevo
    # sin borrar el viejo, que es lo que permite que los turnos ya dados sigan
    # teniendo sentido.
    vigente_desde = models.DateField(null=True, blank=True)
    vigente_hasta = models.DateField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "disponibilidad"
        verbose_name_plural = "disponibilidades"
        ordering = ["dia_semana", "desde"]

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.desde:%H:%M}–{self.hasta:%H:%M} · {self.agenda}"

    @property
    def paso_min(self):
        return self.duracion_min or self.agenda.duracion_min

    def rige_el(self, fecha):
        if not self.activa or fecha.weekday() != self.dia_semana:
            return False
        if self.vigente_desde and fecha < self.vigente_desde:
            return False
        if self.vigente_hasta and fecha > self.vigente_hasta:
            return False
        return True

    def horarios(self, fecha):
        """Horarios que genera esta franja ese día (lista de `datetime` con zona)."""
        if not self.rige_el(fecha):
            return []
        tz = timezone.get_current_timezone()
        inicio = timezone.make_aware(datetime.combine(fecha, self.desde), tz)
        fin = timezone.make_aware(datetime.combine(fecha, self.hasta), tz)
        paso = timedelta(minutes=self.paso_min)
        salida, t = [], inicio
        while t + paso <= fin:
            salida.append(t)
            t += paso
        return salida


class Bloqueo(models.Model):
    """
    Un rango en el que la agenda NO atiende, pese a la disponibilidad semanal.

    Vacaciones, un feriado, un congreso, el equipo en mantenimiento. Sin esto
    habría que borrar la franja semanal y volver a cargarla, y en el medio se
    pierde el horario habitual.
    """

    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="bloqueos")
    desde = models.DateTimeField()
    hasta = models.DateTimeField()
    motivo = models.CharField(max_length=200, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bloqueo de agenda"
        verbose_name_plural = "bloqueos de agenda"
        ordering = ["desde"]

    def __str__(self):
        return f"{self.agenda} bloqueada {self.desde:%d/%m %H:%M}–{self.hasta:%H:%M}"

    def cubre(self, momento):
        return self.desde <= momento < self.hasta


class Turno(models.Model):
    """
    La reserva de una persona en un horario.

    El estado sigue lo que pasa de verdad con un turno: se reserva, la persona
    se presenta (y ahí arranca el caso), o no se presenta, o avisa que no viene.
    «No se presentó» y «canceló» se cuentan por separado a propósito: son dos
    problemas distintos —uno se puede reasignar, el otro no— y mezclarlos hace
    que el indicador de ausentismo no sirva para decidir nada.
    """

    class Estado(models.TextChoices):
        RESERVADO = "reservado", "Reservado"
        CONFIRMADO = "confirmado", "Confirmado"
        PRESENTE = "presente", "Se presentó"
        AUSENTE = "ausente", "No se presentó"
        CANCELADO = "cancelado", "Cancelado"

    class Origen(models.TextChoices):
        MOSTRADOR = "mostrador", "Mostrador"
        TELEFONO = "telefono", "Teléfono"
        DERIVACION = "derivacion", "Derivación"

    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="turnos")
    ciudadano = models.ForeignKey(
        "registros.Ciudadano", on_delete=models.CASCADE, related_name="turnos"
    )
    inicio = models.DateTimeField()
    duracion_min = models.PositiveIntegerField(default=20)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RESERVADO)
    # Turno de más sobre un horario ya ocupado. Se marca en vez de prohibirse:
    # pasa todos los días, y si el sistema no lo admite se anota en un papel.
    sobreturno = models.BooleanField(default=False)
    motivo = models.CharField(max_length=200, blank=True)
    origen = models.CharField(max_length=20, choices=Origen.choices, default=Origen.MOSTRADOR)
    # Caso que se abrió al presentarse. Es lo que conecta el turno con el resto
    # del sistema: sin esto un turno es una anotación en una grilla.
    caso = models.OneToOneField(
        "casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="turno"
    )
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="turnos_dados",
    )
    # Cuándo se avisó y cuándo se canceló: son los datos con los que se mide si
    # el recordatorio sirve para bajar el ausentismo.
    recordado_at = models.DateTimeField(null=True, blank=True)
    cancelado_at = models.DateTimeField(null=True, blank=True)
    # Quién movió el turno de `reservado` y cuándo. El reclamo típico del
    # mostrador es «me cancelaron el turno y nadie me avisó», y el «no vino» es
    # el estado que perjudica al paciente: sin esto no hay a quién preguntarle.
    resuelto_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="turnos_resueltos",
    )
    resuelto_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        ordering = ["inicio", "id"]
        indexes = [models.Index(fields=["agenda", "inicio"])]
        constraints = [
            # Red de seguridad abajo del candado de `motor.reservar`. Dos
            # titulares en el mismo horario no se ven en ninguna pantalla —la
            # grilla muestra uno solo—, así que el segundo paciente llega con el
            # turno impreso y para el mostrador no existe.
            models.UniqueConstraint(
                fields=["agenda", "inicio"],
                condition=models.Q(sobreturno=False) & ~models.Q(estado="cancelado"),
                name="un_titular_por_horario",
            ),
        ]

    def __str__(self):
        return f"{self.ciudadano} · {self.agenda} · {self.inicio:%d/%m %H:%M}"

    @property
    def fin(self):
        return self.inicio + timedelta(minutes=self.duracion_min)

    @property
    def vigente(self):
        """Ocupa lugar en la agenda. Un cancelado libera el horario."""
        return self.estado not in (self.Estado.CANCELADO,)
