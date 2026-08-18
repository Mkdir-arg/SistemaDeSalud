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

    class Modalidad(models.TextChoices):
        """
        Cómo se atiende lo que se agenda acá.

        `MIXTA` no es un estado a medio configurar: es la agenda real de un
        profesional que ve pacientes en el consultorio y hace controles por
        video. Sin ella habría que duplicar la agenda —dos nombres, dos juegos
        de franjas— y entonces las dos pueden dar turno a la misma hora.
        """

        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"
        MIXTA = "mixta", "Presencial o virtual"

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
    # Presencial, virtual, o las dos. Lo que decide es qué puede elegir quien
    # da el turno: en una agenda presencial no hay nada que elegir, y en una
    # virtual el turno tiene que salir con la sala puesta o el paciente espera
    # una llamada que nadie sabe por dónde entra.
    modalidad = models.CharField(
        "modalidad", max_length=20, choices=Modalidad.choices, default=Modalidad.PRESENCIAL,
        help_text="Si es mixta, se elige al dar cada turno.",
    )
    # Sala fija de la agenda: el consultorio virtual del profesional. Se copia
    # al turno virtual que no traiga uno propio, que es el caso normal —nadie
    # pega el mismo link treinta veces por día—.
    enlace_virtual = models.URLField(
        "enlace de la sala", blank=True,
        help_text="Sala de videollamada de esta agenda. Se copia a cada turno virtual.",
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

    def admite(self, modalidad) -> bool:
        """¿Se puede dar un turno de esa modalidad en esta agenda?"""
        if self.modalidad == self.Modalidad.MIXTA:
            return modalidad in Turno.Modalidad.values
        return modalidad == self.modalidad

    @property
    def modalidad_por_defecto(self) -> str:
        """
        Con qué modalidad sale un turno si quien lo da no elige.

        Una agenda mixta cae en presencial a propósito: es lo que pasa en el
        mostrador, y equivocarse hacia presencial deja al paciente viniendo al
        hospital, no esperando frente a una pantalla a alguien que lo espera en
        el consultorio.
        """
        if self.modalidad == self.Modalidad.VIRTUAL:
            return Turno.Modalidad.VIRTUAL
        return Turno.Modalidad.PRESENCIAL


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
    # Cuántas personas entran en CADA horario de esta franja.
    #
    # Uno es el consultorio: la doctora atiende a una persona a la vez. Más de
    # uno es el vacunatorio, la sala de enfermería, la extracción de sangre: tres
    # puestos trabajando en paralelo son tres turnos a las 10:00, y sin esto hay
    # que inventar tres agendas —«Vacunatorio 1/2/3»— que después nadie sabe cuál
    # elegir, o anotar dos en un papel.
    cupos = models.PositiveIntegerField(
        "personas por horario", default=1,
        help_text="1 es lo normal (un consultorio). Más de 1 para puestos en paralelo.",
    )
    # Pisa los sobreturnos de la agenda. La franja de la mañana puede aceptar dos
    # y la de la tarde ninguno: es la que cierra el consultorio, y un sobreturno
    # ahí es alguien esperando a que el profesional se vaya.
    sobreturnos_max = models.PositiveIntegerField(
        "sobreturnos por horario", null=True, blank=True,
        help_text="Si se deja vacío, usa los de la agenda.",
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

    @property
    def tope_sobreturnos(self):
        """Sobreturnos que admite cada horario de esta franja."""
        if self.sobreturnos_max is None:
            return self.agenda.sobreturnos_max
        return self.sobreturnos_max

    @property
    def cuantos_turnos(self):
        """
        Turnos que ofrece la franja: horarios × cupos.

        Es el número que quiere ver quien la carga —«de 10 a 12 cada 30 minutos
        son 4 horarios, y con 3 puestos son 12 turnos»— y calcularlo de cabeza
        con franjas de 20 minutos es incómodo y se hace mal.
        """
        minutos = (
            (self.hasta.hour * 60 + self.hasta.minute)
            - (self.desde.hour * 60 + self.desde.minute)
        )
        paso = self.paso_min or 0
        if minutos <= 0 or paso <= 0:
            return 0
        return (minutos // paso) * self.cupos

    def choca_con(self, otra) -> bool:
        """
        ¿Estas dos franjas se pisan?

        Dos franjas del mismo día que se solapan no dan más turnos: la grilla se
        queda con la primera que genera cada horario y la otra desaparece sin
        avisar, así que la agenda ofrece algo distinto de lo que la pantalla de
        configuración muestra. Se compara también la vigencia: cargar el horario
        nuevo para marzo mientras el viejo rige hasta febrero es justo el caso
        que `vigente_desde`/`vigente_hasta` existen para permitir.
        """
        if self.dia_semana != otra.dia_semana:
            return False
        if self.desde >= otra.hasta or otra.desde >= self.hasta:
            return False
        # Vigencias abiertas (sin fecha) rigen siempre para ese lado.
        if self.vigente_hasta and otra.vigente_desde and self.vigente_hasta < otra.vigente_desde:
            return False
        if otra.vigente_hasta and self.vigente_desde and otra.vigente_hasta < self.vigente_desde:
            return False
        return True

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

    class Modalidad(models.TextChoices):
        PRESENCIAL = "presencial", "Presencial"
        VIRTUAL = "virtual", "Virtual"

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
    # Cuál de los cupos del horario ocupa: 0 en una agenda de consultorio, 0/1/2
    # en una franja de tres puestos. No es un dato para mostrar: existe para que
    # la base pueda seguir garantizando que no se den dos veces el mismo lugar
    # —ver `un_turno_por_cupo`—, ahora que un horario puede tener más de uno.
    posicion = models.PositiveSmallIntegerField(default=0)
    # Se guarda en el turno y no se deduce de la agenda: una agenda mixta da
    # las dos cosas, y sobre todo el papel que se lleva el paciente tiene que
    # decir si el martes viene o se conecta. Cambiar después la modalidad de la
    # agenda no puede reescribir lo que ya se le dijo a la gente.
    modalidad = models.CharField(
        "modalidad", max_length=20, choices=Modalidad.choices, default=Modalidad.PRESENCIAL
    )
    # Sala de este turno. Normalmente es la de la agenda, copiada al reservar;
    # se puede pisar cuando el profesional abre una sala por paciente.
    enlace = models.URLField("enlace de la videollamada", blank=True)
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
            # Red de seguridad abajo del candado de `motor.reservar`: un cupo
            # del horario no se puede dar dos veces. Antes esto era «un titular
            # por horario»; con franjas de varios puestos eso pasó a ser falso,
            # pero la garantía sigue siendo necesaria —dos turnos sobre el mismo
            # lugar no se ven en ninguna pantalla, así que el segundo paciente
            # llega con el turno impreso y para el mostrador no existe—.
            models.UniqueConstraint(
                fields=["agenda", "inicio", "posicion"],
                condition=models.Q(sobreturno=False) & ~models.Q(estado="cancelado"),
                name="un_turno_por_cupo",
            ),
        ]

    def __str__(self):
        return f"{self.ciudadano} · {self.agenda} · {self.inicio:%d/%m %H:%M}"

    @property
    def fin(self):
        return self.inicio + timedelta(minutes=self.duracion_min)

    @property
    def es_virtual(self):
        return self.modalidad == self.Modalidad.VIRTUAL

    @property
    def vigente(self):
        """Ocupa lugar en la agenda. Un cancelado libera el horario."""
        return self.estado not in (self.Estado.CANCELADO,)
