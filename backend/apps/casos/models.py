"""
Casos: el mundo de ejecución.

Un `Caso` es una instancia de una `VersionFlujo` corriendo con datos reales.
Avanza nodo a nodo; cada formulario completado se guarda como `ValorCampo`;
cada paso queda asentado en `EventoCaso` (trazabilidad); los nodos de espera
encolan el caso como `ItemFila`.
"""
from django.db import models


class Caso(models.Model):
    """Instancia de un flujo en ejecución."""

    class Estado(models.TextChoices):
        RECIBIDO = "recibido", "Recibido"
        EN_EVALUACION = "en_evaluacion", "En evaluación"
        EN_ESPERA = "en_espera", "En espera"
        DERIVADO = "derivado", "Derivado"
        ATENDIDO = "atendido", "Atendido"
        CERRADO = "cerrado", "Cerrado"

    class Prioridad(models.TextChoices):
        NORMAL = "normal", "Normal"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="casos"
    )
    version = models.ForeignKey(
        "flujos.VersionFlujo", on_delete=models.PROTECT, related_name="casos"
    )
    ciudadano = models.ForeignKey(
        "registros.Ciudadano",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos",
    )

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RECIBIDO)
    prioridad = models.CharField(max_length=20, choices=Prioridad.choices, default=Prioridad.NORMAL)

    # Posición actual en el grafo.
    nodo_actual = models.ForeignKey(
        "flujos.Nodo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_en_paso",
    )
    area_actual = models.ForeignKey(
        "instituciones.Area",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos",
    )
    asignado_a = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_asignados",
    )

    # Caso que originó éste por una derivación entre flujos (ingreso → especialidad).
    origen = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivados",
    )

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "caso"
        verbose_name_plural = "casos"
        ordering = ["-creado"]

    def __str__(self):
        return f"Caso #{self.pk} · {self.version.flujo.titulo}"


class ValorCampo(models.Model):
    """Valor cargado para un campo de formulario en un caso concreto."""

    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="valores")
    campo = models.ForeignKey(
        "formularios.Campo", on_delete=models.CASCADE, related_name="valores"
    )
    nodo = models.ForeignKey(
        "flujos.Nodo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="valores",
    )
    valor = models.TextField(blank=True)
    cargado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "valor de campo"
        verbose_name_plural = "valores de campo"
        unique_together = [("caso", "campo")]

    def __str__(self):
        return f"{self.campo.label} = {self.valor[:40]}"


class ItemFila(models.Model):
    """Un caso encolado en un nodo de Espera de fila (FIFO, urgentes primero)."""

    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="en_filas")
    nodo = models.ForeignKey(
        "flujos.Nodo", on_delete=models.CASCADE, related_name="fila"
    )
    turno = models.CharField(max_length=20, blank=True)
    urgente = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)
    atendido = models.BooleanField(default=False)
    # Box desde el que se llamó a esta persona (se completa al llamar).
    box = models.ForeignKey(
        "instituciones.Box", on_delete=models.SET_NULL, null=True, blank=True, related_name="llamados"
    )
    ingreso = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ítem de fila"
        verbose_name_plural = "ítems de fila"
        ordering = ["-urgente", "orden", "ingreso"]

    def __str__(self):
        return f"{self.turno or self.caso} en {self.nodo.titulo}"


class EventoCaso(models.Model):
    """Línea de tiempo / trazabilidad de un caso."""

    caso = models.ForeignKey(Caso, on_delete=models.CASCADE, related_name="eventos")
    titulo = models.CharField("título", max_length=200)
    detalle = models.CharField(max_length=255, blank=True)
    # Autor: usuario o "Sistema" (si autor es null).
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos",
    )
    nodo = models.ForeignKey(
        "flujos.Nodo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos",
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evento de caso"
        verbose_name_plural = "eventos de caso"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.titulo} · caso #{self.caso_id}"
