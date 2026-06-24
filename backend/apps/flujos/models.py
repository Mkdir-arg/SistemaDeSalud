"""
Flujos: la definición (plantilla) que diseña el configurador.

Un `Flujo` agrupa sus `VersionFlujo`. Cada versión es un grafo de `Nodo`
unidos por `Conexion`. El motor lee la versión publicada para dibujar el
lienzo y para renderizar las pantallas de ejecución de cada caso.
"""
from django.db import models


class Flujo(models.Model):
    """Plantilla de proceso. Su contenido vive en las versiones."""

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="flujos"
    )
    area = models.ForeignKey(
        "instituciones.Area",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flujos",
    )
    # Si se fija una sub-área, el flujo es un proceso específico de esa sub-área
    # (y `area` queda apuntando al área padre). Si sólo hay `area`, es un proceso
    # general del área. Sin ninguna de las dos, es un proceso de toda la institución.
    subarea = models.ForeignKey(
        "instituciones.Subarea",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flujos",
    )
    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción", blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "flujo"
        verbose_name_plural = "flujos"
        ordering = ["titulo"]

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        # Una sub-área implica su área padre: mantenemos `area` sincronizada para
        # que los filtros y listados por área sigan funcionando.
        if self.subarea_id:
            self.area_id = self.subarea.area_id
        super().save(*args, **kwargs)

    @property
    def ambito(self):
        """Etiqueta del alcance del flujo: institución, área o sub-área."""
        if self.subarea_id:
            return "subarea"
        if self.area_id:
            return "area"
        return "institucion"

    @property
    def version_publicada(self):
        return self.versiones.filter(estado=VersionFlujo.Estado.PUBLICADA).order_by("-numero").first()


class VersionFlujo(models.Model):
    """Una versión concreta del flujo. El grafo cuelga de acá."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"
        REEMPLAZADA = "reemplazada", "Reemplazada"
        ARCHIVADA = "archivada", "Archivada"

    flujo = models.ForeignKey(Flujo, on_delete=models.CASCADE, related_name="versiones")
    numero = models.PositiveIntegerField(help_text="1, 2, 3… mostrado como v1, v2, v3")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    nota = models.TextField("nota de cambios", blank=True)
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versiones_creadas",
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "versión de flujo"
        verbose_name_plural = "versiones de flujo"
        ordering = ["flujo", "-numero"]
        unique_together = [("flujo", "numero")]

    def __str__(self):
        return f"{self.flujo} · v{self.numero}"

    @property
    def etiqueta(self):
        return f"v{self.numero}"


class Nodo(models.Model):
    """Un paso del grafo. `config` guarda los parámetros propios del tipo."""

    class Tipo(models.TextChoices):
        INICIO = "inicio", "Inicio"
        FORMULARIO = "form", "Formulario"
        DECISION = "decision", "Decisión"
        ACCION = "accion", "Acción"
        ATENCION = "atencion", "Atención"
        DERIVAR = "derivar", "Derivar"
        ESPERA_FILA = "espera", "Espera de fila"
        ESPERA_TIEMPO = "tiempo", "Espera por tiempo"
        ESTADO = "estado", "Estado"
        FIN = "fin", "Fin"

    version = models.ForeignKey(
        VersionFlujo, on_delete=models.CASCADE, related_name="nodos"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción", blank=True)

    # Posición en el lienzo del diseñador.
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)

    # Parámetros propios del tipo de nodo:
    #  - form: {"formulario_id": n}
    #  - derivar: {"area_destino_id": n, "flujo_destino_id": n}
    #  - estado: {"estado": "En espera"}
    #  - tiempo: {"duracion": "1 mes"}
    #  - atencion: {"plantilla": "evaluación inicial"}
    config = models.JSONField(default=dict, blank=True)

    formulario = models.ForeignKey(
        "formularios.Formulario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nodos",
    )

    # Grupos responsables del paso: definen "quién hace esta acción". Cualquier
    # integrante de los grupos asignados puede ejecutar/tomar el nodo. Aplica a
    # los pasos donde una persona trabaja (form, atención, acción, espera).
    grupos = models.ManyToManyField(
        "instituciones.Grupo", blank=True, related_name="nodos"
    )

    class Meta:
        verbose_name = "nodo"
        verbose_name_plural = "nodos"

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.titulo}"


class Conexion(models.Model):
    """Arista dirigida entre dos nodos. La etiqueta soporta ramas de decisión."""

    version = models.ForeignKey(
        VersionFlujo, on_delete=models.CASCADE, related_name="conexiones"
    )
    origen = models.ForeignKey(
        Nodo, on_delete=models.CASCADE, related_name="salidas"
    )
    destino = models.ForeignKey(
        Nodo, on_delete=models.CASCADE, related_name="entradas"
    )
    etiqueta = models.CharField(max_length=120, blank=True)
    # Regla de la rama, p. ej. {"campo": "Prioridad", "operador": "=", "valor": "Alta"}
    condicion = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "conexión"
        verbose_name_plural = "conexiones"

    def __str__(self):
        return f"{self.origen.titulo} → {self.destino.titulo}"
