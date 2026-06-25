"""
Estructura organizativa.

Plataforma → Institución (autocontenida) → Área → Sub-área.
Las instituciones son independientes entre sí (no hay jurisdicciones ni redes).
"""
from django.db import models


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
