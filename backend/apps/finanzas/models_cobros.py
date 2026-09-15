"""Políticas de cobro separadas de los costos y snapshots de atenciones nuevas."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class PoliticaCobro(models.Model):
    prestacion = models.ForeignKey("finanzas.Prestacion", on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    nodo_origen_id = models.PositiveBigIntegerField()
    nombre_prestacion = models.CharField(max_length=160)
    cobrar = models.BooleanField(default=False)
    importe = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    contraparte_nombre = models.CharField(max_length=160, blank=True)
    contraparte_referencia = models.CharField(max_length=160, blank=True)
    sensible = models.BooleanField(default=False)
    vigente_desde = models.DateTimeField(default=timezone.now)
    registrado = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-vigente_desde", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(importe__isnull=True) | models.Q(importe__gt=0), name="cobro_arancel_positivo")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("La política es histórica. Registrá una nueva versión para futuras atenciones.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Las políticas históricas no se eliminan.")


class SnapshotCobroAtencion(models.Model):
    hecho = models.OneToOneField("finanzas.HechoAtencionCosteable", on_delete=models.PROTECT, related_name="snapshot_cobro")
    capturado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)


class PendienteCobro(models.Model):
    hecho = models.ForeignKey("finanzas.HechoAtencionCosteable", on_delete=models.PROTECT, related_name="pendientes_cobro")
    prestacion = models.ForeignKey("finanzas.Prestacion", on_delete=models.PROTECT)
    politica = models.ForeignKey(PoliticaCobro, on_delete=models.PROTECT)
    institucion = models.ForeignKey("instituciones.Institucion", on_delete=models.PROTECT)
    area = models.ForeignKey("instituciones.Area", null=True, blank=True, on_delete=models.PROTECT)
    sensible = models.BooleanField(default=False)
    importe = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    contraparte_nombre = models.CharField(max_length=160, blank=True)
    contraparte_referencia = models.CharField(max_length=160, blank=True)
    obligacion = models.OneToOneField("finanzas.ObligacionFinanciera", null=True, blank=True, on_delete=models.PROTECT)
    clave = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    creado = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["hecho", "prestacion"], name="cargo_unico_hecho_prestacion")]
