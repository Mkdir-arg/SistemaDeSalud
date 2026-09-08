"""Hechos e importes internos de finanzas y costos."""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Prestacion(models.Model):
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.CASCADE, related_name="prestaciones_costo")
    nodo = models.ForeignKey("flujos.Nodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="prestaciones_costo")
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)
    class Meta:
        unique_together = [("institucion", "codigo")]
        ordering = ["institucion_id", "codigo"]


class DefinicionComponente(models.Model):
    class Fuente(models.TextChoices):
        ATENCION_DIRECTA = "atencion_directa", "Atención directa"
    prestacion = models.ForeignKey(Prestacion, on_delete=models.PROTECT, related_name="componentes")
    codigo = models.CharField(max_length=60)
    nombre = models.CharField(max_length=160)
    fuente = models.CharField(max_length=40, choices=Fuente.choices, default=Fuente.ATENCION_DIRECTA)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)
    class Meta:
        unique_together = [("prestacion", "codigo")]
        ordering = ["prestacion_id", "orden", "id"]


class ValorComponente(models.Model):
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, related_name="valores")
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    vigente_desde = models.DateTimeField()
    vigente_hasta = models.DateTimeField(null=True, blank=True)
    fuente = models.CharField(max_length=255, blank=True)
    registrado_por = models.ForeignKey("accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="valores_costo_registrados")
    registrado = models.DateTimeField(auto_now_add=True)
    reemplaza = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reemplazado_por")
    motivo_correccion = models.CharField(max_length=255, blank=True)
    class Meta:
        ordering = ["componente_id", "vigente_desde", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(importe__gte=0), name="valor_componente_no_negativo"),
            models.CheckConstraint(condition=Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=models.F("vigente_desde")), name="vigencia_componente_valida"),
        ]


class HechoAtencionCosteable(models.Model):
    """Atención completada: origen durable, sin narrativa clínica."""
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT, related_name="hechos_atencion_costeables")
    evento = models.ForeignKey("casos.EventoCaso", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    evento_origen_id = models.BigIntegerField(unique=True)
    caso = models.ForeignKey("casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    caso_origen_id = models.BigIntegerField()
    ciudadano = models.ForeignKey("registros.Ciudadano", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    ciudadano_origen_id = models.BigIntegerField(null=True, blank=True)
    nodo = models.ForeignKey("flujos.Nodo", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    nodo_origen_id = models.BigIntegerField()
    area = models.ForeignKey("instituciones.Area", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    area_origen_id = models.BigIntegerField(null=True, blank=True)
    autor = models.ForeignKey("accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="hechos_costo")
    ocurrida_en = models.DateTimeField()
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["ocurrida_en", "id"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Un hecho de atención costeable no se edita; los cambios económicos son ajustes.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un hecho de atención costeable no se elimina.")


class ImputacionCosto(models.Model):
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="imputaciones")
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, related_name="imputaciones")
    valor = models.ForeignKey(ValorComponente, on_delete=models.PROTECT, related_name="imputaciones")
    importe = models.DecimalField(max_digits=14, decimal_places=2)
    creado = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [("hecho", "componente")]
        constraints = [models.CheckConstraint(condition=Q(importe__gte=0), name="imputacion_costo_no_negativa")]


class PendienteCosteo(models.Model):
    class Motivo(models.TextChoices):
        SIN_PRESTACION = "sin_prestacion", "Sin prestación configurada"
        SIN_VALOR = "sin_valor", "Sin valor vigente"
        ERROR_RECUPERABLE = "error_recuperable", "Error recuperable"
    hecho = models.ForeignKey(HechoAtencionCosteable, on_delete=models.PROTECT, related_name="pendientes")
    componente = models.ForeignKey(DefinicionComponente, on_delete=models.PROTECT, null=True, blank=True, related_name="pendientes")
    motivo = models.CharField(max_length=40, choices=Motivo.choices)
    resuelto = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = [("hecho", "componente", "motivo")]
