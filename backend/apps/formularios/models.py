"""
Formularios y sus campos.

Un formulario es una definición reutilizable que un nodo de tipo «Formulario»
de un flujo puede usar para pedir datos. Los campos pueden estar «vinculados»
a un origen (Historia clínica / Legajo ciudadano), lo que precarga su valor.
"""
from django.db import models


class Formulario(models.Model):
    """Definición de un formulario perteneciente a un nivel organizativo."""

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="formularios"
    )
    area = models.ForeignKey(
        "instituciones.Area",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="formularios",
    )
    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "formulario"
        verbose_name_plural = "formularios"
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo


class Campo(models.Model):
    """Un campo dentro de un formulario."""

    class Tipo(models.TextChoices):
        TEXTO_CORTO = "texto_corto", "Texto corto"
        TEXTO_LARGO = "texto_largo", "Texto largo"
        FECHA = "fecha", "Fecha"
        SELECCION_UNICA = "seleccion_unica", "Selección única"
        ARCHIVO = "archivo", "Archivo adjunto"

    class Origen(models.TextChoices):
        HISTORIA_CLINICA = "historia_clinica", "Historia clínica"
        LEGAJO_CIUDADANO = "legajo_ciudadano", "Legajo ciudadano"

    formulario = models.ForeignKey(
        Formulario, on_delete=models.CASCADE, related_name="campos"
    )
    label = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    requerido = models.BooleanField(default=False)
    ayuda = models.CharField("texto de ayuda", max_length=255, blank=True)
    # Opciones para SELECCION_UNICA (lista de strings).
    opciones = models.JSONField(default=list, blank=True)
    # Si el campo se precarga desde un registro existente.
    origen = models.CharField(max_length=20, choices=Origen.choices, blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "campo"
        verbose_name_plural = "campos"
        ordering = ["formulario", "orden"]

    def __str__(self):
        return f"{self.label} ({self.formulario})"

    @property
    def vinculado(self):
        return bool(self.origen)
