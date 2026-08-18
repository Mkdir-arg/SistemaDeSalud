"""
Formularios y sus campos.

Un formulario es una definición reutilizable que un nodo de tipo «Formulario»
de un flujo puede usar para pedir datos.

`Campo.origen` está declarado pero TODAVÍA NO HACE NADA: ningún código lo lee.
El docstring decía que «precarga su valor» y era falso —no hay un solo consumidor
de `origen` ni de `vinculado` fuera de esta definición y de la serialización—, así
que la pantalla mostraba un badge y una columna «Vinculados» que no podían
aparecer nunca. Las dos se sacaron hasta que la precarga exista: hay que
implementarla en el motor, al abrir el nodo Formulario, completando los campos con
origen desde el ciudadano y su historia sin pisar lo ya cargado (la misma regla
del padrón FHIR). El campo se conserva para no perder el dato de los formularios
que ya lo tengan seteado.
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
        NUMERO = "numero", "Número"
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
    # Sólo para NUMERO. La unidad se muestra al lado del casillero (no se guarda
    # dentro del valor: si el valor fuera «36.8 °C» dejaría de ser comparable, y
    # las Decisiones de orden hacen float sobre el texto guardado).
    unidad = models.CharField("unidad", max_length=20, blank=True)
    # Rango admitido, inclusive. Ninguno de los dos es obligatorio: «peso» tiene
    # piso y techo razonables, «dosis» a veces no tiene techo.
    minimo = models.FloatField("mínimo", null=True, blank=True)
    maximo = models.FloatField("máximo", null=True, blank=True)
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
