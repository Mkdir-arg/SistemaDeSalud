"""
Red de establecimientos.

Hasta acá cada institución era un mundo cerrado: todo lo que se deriva se deriva
adentro. Esto es lo otro — el hospital de una localidad que manda un paciente al
de mayor complejidad— y es el cambio de alcance más profundo del sistema,
porque hasta ahora «ver» y «pertenecer a la institución» eran lo mismo.

**La decisión que ordena todo el módulo:** un traslado NO le da al hospital de
origen acceso a los datos del de destino, ni al revés. Cada institución sigue
siendo dueña de sus casos. Lo que se comparte es el traslado en sí —un objeto
que los dos ven— con el estado, el motivo y las marcas de tiempo. Sin eso, o
bien el que deriva manda al paciente a un agujero negro y nunca sabe qué pasó,
o bien se abre la historia clínica de un hospital a otro, que ni la ley ni el
sentido común permiten.

El paciente sí se comparte, porque es la misma persona: el `Ciudadano` viaja con
su documento. Lo que no viaja es el caso.
"""
from django.db import models
from django.utils import timezone


class Red(models.Model):
    """
    Un conjunto de establecimientos que pueden derivarse entre sí.

    Existe para que «a dónde puedo derivar» sea una lista corta y deliberada. Sin
    red, cualquier institución podría mandarle un paciente a cualquier otra del
    sistema, incluida una con la que no tiene ninguna relación.
    """

    nombre = models.CharField(max_length=150, unique=True)
    descripcion = models.TextField("descripción", blank=True)
    instituciones = models.ManyToManyField(
        "instituciones.Institucion", related_name="redes", blank=True
    )
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "red de establecimientos"
        verbose_name_plural = "redes de establecimientos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Traslado(models.Model):
    """
    El pedido de mandar un paciente a otro establecimiento.

    **No es automático a propósito.** Un hospital no puede obligar a otro a
    recibir un paciente: el de destino tiene que aceptar, y puede rechazar
    —porque no tiene camas, porque no tiene la especialidad— con un motivo que
    queda registrado. Un traslado que se diera por hecho terminaría con una
    ambulancia en una puerta donde no la esperan.

    Es el único objeto que ven las dos instituciones. El caso de origen y el de
    destino son cada uno de su dueño.
    """

    class Estado(models.TextChoices):
        SOLICITADO = "solicitado", "Solicitado"
        ACEPTADO = "aceptado", "Aceptado"
        RECHAZADO = "rechazado", "Rechazado"
        EN_CAMINO = "en_camino", "En camino"
        RECIBIDO = "recibido", "Recibido"
        CANCELADO = "cancelado", "Cancelado"

    class Motivo(models.TextChoices):
        COMPLEJIDAD = "complejidad", "Mayor complejidad"
        ESPECIALIDAD = "especialidad", "Especialidad no disponible"
        CAMA = "cama", "Falta de cama"
        ESTUDIO = "estudio", "Estudio no disponible"
        CERCANIA = "cercania", "Cercanía al domicilio"
        OTRO = "otro", "Otro"

    red = models.ForeignKey(
        Red, on_delete=models.SET_NULL, null=True, blank=True, related_name="traslados"
    )
    origen = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="traslados_enviados"
    )
    destino = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="traslados_recibidos"
    )
    # El caso que se está derivando. Queda esperando hasta que se resuelve.
    caso_origen = models.ForeignKey(
        "casos.Caso", on_delete=models.CASCADE, related_name="traslados"
    )
    # El caso que se abre en el destino, recién al aceptar. Antes de eso no
    # existe: crear un caso en un hospital que todavía no dijo que sí sería
    # meterle trabajo en la bandeja por algo que puede rechazar.
    caso_destino = models.ForeignKey(
        "casos.Caso", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="traslado_recibido",
    )
    # El paciente viaja: es la misma persona. El caso, no.
    ciudadano = models.ForeignKey(
        "registros.Ciudadano", on_delete=models.CASCADE, related_name="traslados"
    )
    # Área del destino a la que va. Opcional: a veces se deriva «al hospital» y
    # ellos deciden dónde.
    area_destino = models.ForeignKey(
        "instituciones.Area", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="traslados_recibidos",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.SOLICITADO)
    motivo = models.CharField(max_length=20, choices=Motivo.choices, default=Motivo.COMPLEJIDAD)
    detalle = models.TextField(blank=True, help_text="Resumen clínico para quien recibe.")
    urgente = models.BooleanField(default=False)
    # Por qué se rechazó. Sin esto el que deriva no sabe si insistir, buscar otro
    # hospital o esperar.
    respuesta = models.TextField("respuesta del destino", blank=True)

    solicitado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="traslados_solicitados",
    )
    solicitado_at = models.DateTimeField(auto_now_add=True)
    resuelto_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="traslados_resueltos",
    )
    resuelto_at = models.DateTimeField(null=True, blank=True)
    # Cuándo salió y cuándo llegó: es lo que permite medir cuánto tarda un
    # traslado en la red, que es el indicador que se le pide a una región.
    salida_at = models.DateTimeField(null=True, blank=True)
    llegada_at = models.DateTimeField(null=True, blank=True)
    movil = models.CharField("móvil / ambulancia", max_length=80, blank=True)

    class Meta:
        verbose_name = "traslado"
        verbose_name_plural = "traslados"
        ordering = ["-urgente", "-solicitado_at"]
        indexes = [
            models.Index(fields=["destino", "estado"]),
            models.Index(fields=["origen", "estado"]),
        ]

    def __str__(self):
        return f"{self.ciudadano} · {self.origen} → {self.destino}"

    @property
    def abierto(self):
        return self.estado in (
            self.Estado.SOLICITADO, self.Estado.ACEPTADO, self.Estado.EN_CAMINO
        )

    @property
    def demora_min(self):
        """Cuánto tardó en resolverse el pedido (aceptar o rechazar)."""
        if self.resuelto_at is None:
            return None
        return round((self.resuelto_at - self.solicitado_at).total_seconds() / 60)

    @property
    def traslado_min(self):
        """Cuánto tardó el viaje, de la salida a la llegada."""
        if not (self.salida_at and self.llegada_at):
            return None
        return round((self.llegada_at - self.salida_at).total_seconds() / 60)
