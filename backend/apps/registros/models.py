"""
Registros: lo que persiste más allá de un caso.

- Ciudadano: la persona/paciente, identificada a nivel institución.
- HistoriaClinica + EntradaHistoria / Estudio / Receta: el expediente clínico.
El legajo profesional (de los usuarios) vive en `apps.accounts`.
"""
from django.db import models


class Ciudadano(models.Model):
    """Persona registrada en una institución (paciente / ciudadano)."""

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="ciudadanos"
    )
    codigo = models.CharField("código (CIU)", max_length=40, blank=True)
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120, blank=True)
    documento = models.CharField("documento", max_length=30, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    obra_social = models.CharField("obra social", max_length=120, blank=True)
    domicilio = models.CharField(max_length=255, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ciudadano"
        verbose_name_plural = "ciudadanos"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        nombre = f"{self.nombre} {self.apellido}".strip()
        return f"{nombre} ({self.documento})" if self.documento else nombre


class HistoriaClinica(models.Model):
    """Expediente clínico de un ciudadano dentro de una institución."""

    ciudadano = models.OneToOneField(
        Ciudadano, on_delete=models.CASCADE, related_name="historia_clinica"
    )
    alergias = models.CharField(max_length=255, blank=True)
    condiciones = models.CharField("condiciones / antecedentes", max_length=255, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "historia clínica"
        verbose_name_plural = "historias clínicas"

    def __str__(self):
        return f"HC de {self.ciudadano}"


class EntradaHistoria(models.Model):
    """Una entrada de evolución en la historia clínica (atención registrada)."""

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="entradas"
    )
    titulo = models.CharField("título", max_length=200)
    contenido = models.TextField(blank=True)
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entradas_historia",
    )
    # Caso que originó la entrada (si vino del motor de ejecución).
    caso = models.ForeignKey(
        "casos.Caso",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entradas_historia",
    )
    firmada = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entrada de historia clínica"
        verbose_name_plural = "entradas de historia clínica"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.titulo} · {self.historia.ciudadano}"


class Estudio(models.Model):
    """Estudio médico adjunto a una historia clínica."""

    class Resultado(models.TextChoices):
        NORMAL = "normal", "Normal"
        ALTERADO = "alterado", "Alterado"

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="estudios"
    )
    tipo = models.CharField(max_length=150)
    resultado = models.CharField(max_length=20, choices=Resultado.choices, blank=True)
    realizado = models.BooleanField("realizado", default=False)
    archivo = models.CharField("archivo", max_length=255, blank=True)
    autor = models.CharField(max_length=150, blank=True)
    fecha = models.DateField()

    class Meta:
        verbose_name = "estudio"
        verbose_name_plural = "estudios"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} · {self.fecha}"


class Receta(models.Model):
    """Receta emitida en el marco de una historia clínica."""

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="recetas"
    )
    detalle = models.TextField()
    activa = models.BooleanField(default=True)
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recetas",
    )
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "receta"
        verbose_name_plural = "recetas"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Receta · {self.historia.ciudadano} · {self.fecha}"
