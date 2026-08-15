"""
Estructura organizativa.

Plataforma → Institución (autocontenida) → Área → Sub-área.
Las instituciones son independientes entre sí (no hay jurisdicciones ni redes).
"""
from django.db import models
from django.db.models.signals import pre_delete
from django.utils import timezone


class Institucion(models.Model):
    """Una organización autocontenida: hospital, centro de salud, organismo."""

    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa"
        EN_ALTA = "en_alta", "En alta"
        INACTIVA = "inactiva", "Inactiva"

    nombre = models.CharField(max_length=200)
    tipo = models.CharField("tipo", max_length=120, blank=True, help_text="Hospital general, Centro de salud, Organismo…")
    cuit = models.CharField("CUIT", max_length=20, blank=True)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVA)
    # Ubicación, para poder ordenar los destinos de un traslado por cercanía.
    #
    # Es media hora de ambulancia lo que separa dos opciones que en una lista
    # alfabética se ven iguales. Opcional: una institución sin coordenadas
    # sigue funcionando, sólo que aparece sin distancia.
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "institución"
        verbose_name_plural = "instituciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Area(models.Model):
    """Nivel organizativo dentro de una institución (Admisión, Cardiología…)."""

    institucion = models.ForeignKey(
        Institucion, on_delete=models.CASCADE, related_name="areas"
    )
    nombre = models.CharField(max_length=150)
    responsable = models.CharField("responsable / jefe", max_length=150, blank=True)
    descripcion = models.TextField("descripción", blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "área"
        verbose_name_plural = "áreas"
        ordering = ["nombre"]
        unique_together = [("institucion", "nombre")]

    def __str__(self):
        return f"{self.nombre} ({self.institucion})"


class Subarea(models.Model):
    """Subdivisión de un área (Hemodinamia, Consultorios externos…)."""

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="subareas")
    nombre = models.CharField(max_length=150)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "sub-área"
        verbose_name_plural = "sub-áreas"
        ordering = ["nombre"]
        unique_together = [("area", "nombre")]

    def __str__(self):
        return f"{self.nombre} · {self.area.nombre}"


class Box(models.Model):
    """
    Consultorio / box de atención de un área. Desde un box, un profesional llama
    al siguiente de la fila de espera para atenderlo.
    """

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="boxes")
    nombre = models.CharField(max_length=80, help_text="Ej.: «Box 1», «Consultorio A»")
    activo = models.BooleanField(default=True)
    # Ocupación: el profesional «registrado» en el box (lo libera al salir).
    ocupado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="boxes_ocupados"
    )
    ocupado_desde = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "box"
        verbose_name_plural = "boxes"
        ordering = ["nombre"]
        unique_together = [("area", "nombre")]

    def __str__(self):
        return f"{self.nombre} · {self.area.nombre}"


class Grupo(models.Model):
    """
    Equipo de trabajo dentro de un área (ej: 'Guardia mañana', 'Comité de ablación').
    Agrupa personas del área; estos grupos luego se usan como destinatarios en los flujos.
    """

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="grupos")
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField("descripción", blank=True)
    miembros = models.ManyToManyField(
        "accounts.Usuario", blank=True, related_name="grupos"
    )
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "grupo"
        verbose_name_plural = "grupos"
        ordering = ["nombre"]
        unique_together = [("area", "nombre")]

    def __str__(self):
        return f"{self.nombre} · {self.area.nombre}"


# Nombre estable para el esquema OpenAPI: hay tres modelos con un campo
# «estado» distinto y sin esto quedan documentados como «Estado719Enum».
ESTADOS_INSTITUCION = Institucion.Estado.choices


class Cama(models.Model):
    """
    Cama de internación.

    El sector (`subarea`) es lo que se mira para operar: «UTI», «Clínica
    médica», «Pediatría». Se reutiliza la jerarquía que ya existe —área y
    sub-área— en vez de inventar una paralela: una cama vive en el mismo lugar
    del organigrama que todo lo demás, y así hereda el alcance por institución,
    los permisos y los tableros sin nada especial.

    **Estado y ocupante son dos hechos distintos.** `estado` responde «¿se puede
    usar?» y `caso` responde «¿quién está?». La invariante es que
    `estado == OCUPADA` si y solo si hay un caso; el motor las mueve juntas y
    hay un test que la verifica sobre la base entera.

    El historial de quién pasó por cada cama vive en `EstadiaCama`: es lo que
    responde «¿dónde estuvo este paciente?» y lo que permite medir la ocupación
    de un período que ya pasó.
    """

    class Estado(models.TextChoices):
        LIBRE = "libre", "Libre"
        OCUPADA = "ocupada", "Ocupada"
        # Entre un paciente y el siguiente la cama NO está disponible. Sin este
        # estado, el sistema ofrecería una cama sin higienizar apenas se va
        # alguien, que es exactamente el error que nadie quiere cometer.
        HIGIENE = "higiene", "En higiene"
        BLOQUEADA = "bloqueada", "Fuera de servicio"

    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name="camas")
    # El sector de internación. Opcional porque no toda institución subdivide.
    subarea = models.ForeignKey(
        Subarea, on_delete=models.SET_NULL, null=True, blank=True, related_name="camas",
        verbose_name="sector",
    )
    nombre = models.CharField(max_length=80, help_text="Ej.: «101-A», «UTI 3»")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.LIBRE)
    # Quién la ocupa ahora. Nulo en cualquier otro estado (ver invariante arriba).
    caso = models.ForeignKey(
        "casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="camas",
    )
    # Desde cuándo está en el estado actual: es la antigüedad que se muestra en
    # el tablero («ocupada hace 3 días», «esperando higiene hace 40 minutos»).
    desde = models.DateTimeField(null=True, blank=True)
    # Por qué está fuera de servicio (mantenimiento, aislamiento, obra).
    motivo = models.CharField(max_length=200, blank=True)
    activa = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cama"
        verbose_name_plural = "camas"
        ordering = ["subarea__nombre", "nombre"]
        unique_together = [("area", "nombre")]

    def __str__(self):
        return f"{self.nombre} · {self.subarea.nombre if self.subarea_id else self.area.nombre}"

    @property
    def sector_nombre(self):
        return self.subarea.nombre if self.subarea_id else self.area.nombre

    @property
    def disponible(self):
        return self.activa and self.estado == self.Estado.LIBRE


class EstadiaCama(models.Model):
    """
    Paso de un caso por una cama: desde cuándo, hasta cuándo y por qué se fue.

    Es el historial que responde «¿dónde estuvo este paciente?» —una pregunta
    clínica y administrativa real— y el único dato que permite medir la
    ocupación de un período que ya pasó: la foto de `Cama.estado` sólo sabe del
    momento actual.

    Un pase de sector cierra una estadía y abre otra: así el recorrido queda
    completo sin ningún registro aparte.
    """

    class Egreso(models.TextChoices):
        ALTA = "alta", "Alta"
        PASE = "pase", "Pase a otro sector"
        DERIVACION = "derivacion", "Derivación a otra institución"
        FALLECIMIENTO = "fallecimiento", "Fallecimiento"

    cama = models.ForeignKey(Cama, on_delete=models.CASCADE, related_name="estadias")
    caso = models.ForeignKey("casos.Caso", on_delete=models.CASCADE, related_name="estadias")
    desde = models.DateTimeField()
    hasta = models.DateTimeField(null=True, blank=True)
    motivo_egreso = models.CharField(max_length=20, choices=Egreso.choices, blank=True)
    # Quién asignó la cama (para trazabilidad; no es el responsable clínico).
    autor = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="estadias_asignadas",
    )

    class Meta:
        verbose_name = "estadía en cama"
        verbose_name_plural = "estadías en cama"
        ordering = ["-desde", "-id"]

    def __str__(self):
        return f"{self.caso_id} en {self.cama} desde {self.desde:%d/%m/%Y}"

    @property
    def abierta(self):
        return self.hasta is None


def liberar_camas_de_un_caso_borrado(sender, instance, **kwargs):
    """
    Borrar un caso internado dejaba su cama ocupada por nadie, para siempre.

    `Cama.caso` es SET_NULL y `EstadiaCama` es CASCADE: al borrarse el caso la
    referencia al ocupante se anula sola pero el `estado` NO, y la estadía
    abierta desaparece. Desde ahí no hay ninguna salida por la aplicación —
    cambiar el estado de una cama OCUPADA está prohibido, el egreso necesita una
    estadía abierta que ya no existe y `estado` no se escribe por PATCH—: la
    cama se pierde del stock, la ocupación del sector queda inflada de forma
    permanente y recuperarla exige entrar a la base a mano, en producción, en un
    hospital. El síntoma ya estaba documentado en el seed de la guardia: «medio
    sector inutilizable por pacientes que ya no existen».

    Queda en higiene y no libre porque es lo que queda cuando alguien deja una
    cama: ofrecerla sin higienizar es el error que este módulo existe para
    evitar.
    """
    Cama.objects.filter(caso=instance).update(
        estado=Cama.Estado.HIGIENE, caso=None, desde=timezone.now(), motivo="",
    )


# Sender por string: `casos` importa `instituciones`, así que importar el modelo
# acá cerraría el círculo.
pre_delete.connect(
    liberar_camas_de_un_caso_borrado,
    sender="casos.Caso",
    dispatch_uid="instituciones.liberar_camas_de_un_caso_borrado",
)
