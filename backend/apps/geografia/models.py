from django.db import models
from django.db.models import Q


class Catalogo(models.Model):
    """Una fila de coordinación; la publicación se serializa bajo su lock."""
    version = models.PositiveBigIntegerField(default=0)
    intento = models.DateTimeField(null=True)
    actualizado = models.DateTimeField(null=True)
    error = models.CharField(max_length=160, blank=True)
    huella = models.CharField(max_length=64, blank=True)


class Lugar(models.Model):
    tipo = models.CharField(max_length=10, choices=[(v, v) for v in ("provincia", "partido", "localidad")])
    origen = models.CharField(max_length=10, choices=[("georef", "Georef"), ("manual", "Manual · sin verificar")])
    codigo = models.CharField(max_length=32, blank=True)
    nombre = models.CharField(max_length=100)
    provincia = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="en_provincia")
    partido = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="en_partido")
    institucion = models.ForeignKey("instituciones.Institucion", null=True, blank=True, on_delete=models.PROTECT)
    financiador = models.ForeignKey("financiadores.Financiador", null=True, blank=True, on_delete=models.PROTECT)
    clave_manual = models.CharField(max_length=64, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre", "pk"]
        indexes = [models.Index(fields=["tipo", "activo", "provincia", "partido"], name="geo_busqueda")]
        constraints = [
            models.CheckConstraint(condition=Q(tipo__in=["provincia", "partido", "localidad"]), name="geo_tipo"),
            models.CheckConstraint(condition=(
                Q(origen="georef", institucion__isnull=True, financiador__isnull=True, clave_manual="") & ~Q(codigo="")
                | Q(origen="manual", codigo="") & ~Q(clave_manual="") & (
                    Q(institucion__isnull=False, financiador__isnull=True) | Q(institucion__isnull=True, financiador__isnull=False)
                )), name="geo_origen_ambito"),
            models.UniqueConstraint(fields=["tipo", "codigo"], condition=Q(origen="georef"), name="geo_codigo_unico"),
            models.UniqueConstraint(fields=["clave_manual"], condition=Q(origen="manual"), name="geo_manual_unico"),
        ]


class Ubicacion(models.Model):
    """Instantánea del domicilio: una actualización del catálogo no cambia su texto."""
    provincia = models.ForeignKey(Lugar, null=True, on_delete=models.PROTECT, related_name="domicilios_provincia")
    partido = models.ForeignKey(Lugar, null=True, on_delete=models.PROTECT, related_name="domicilios_partido")
    localidad = models.ForeignKey(Lugar, null=True, on_delete=models.PROTECT, related_name="domicilios_localidad")
    textos = models.JSONField(default=dict)
    origenes = models.JSONField(default=dict)

    def datos(self):
        salida = {}
        for nivel in ("provincia", "partido", "localidad"):
            lugar = getattr(self, nivel)
            salida[nivel] = {"id": lugar.pk if lugar else None, "nombre": self.textos.get(nivel, ""),
                             "origen": lugar.origen if lugar else self.origenes.get(nivel, "legado")}
        return salida
