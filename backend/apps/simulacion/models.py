"""
Simulación de perfiles del backoffice por un superusuario.

Sirve para recorrer HEN con los límites reales de cada perfil: el backend
autoriza y acota con la **cuenta de referencia** elegida, no con el acceso
total del superusuario. La autoría de lo que se haga sigue siendo del
superusuario.

- `CuentaReferencia` es el catálogo: una cuenta técnica por perfil y ámbito
  («Superusuario Enfermería» del Hospital X). No representa a una persona y no
  puede iniciar sesión por su cuenta.
- `SesionSimulacion` registra quién simula qué, en qué ámbito y hasta cuándo.
- `OperacionSimulada` registra cada escritura intentada durante la simulación.

El recorrido del pedido está en `autenticacion.py` y la autoría, en `contexto.py`.
"""
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Ambito(models.TextChoices):
    PLATAFORMA = "plataforma", "Plataforma"
    INSTITUCION = "institucion", "Institución"
    FINANCIADOR = "financiador", "Financiador"


class CuentaReferencia(models.Model):
    """Cuenta técnica que presta sus permisos a una simulación.

    `rol` es un valor de `Membresia.Rol` o del rol de `MembresiaFinanciador`: el
    catálogo no define roles propios. En plataforma la membresía es global y
    `institucion` queda vacía; se admiten anclas antiguas hasta su conversión.
    """

    usuario = models.OneToOneField(
        "accounts.Usuario", on_delete=models.CASCADE, related_name="cuenta_referencia",
    )
    ambito = models.CharField(max_length=20, choices=Ambito.choices)
    rol = models.CharField(max_length=20)
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, null=True, blank=True, related_name="+",
    )
    financiador = models.ForeignKey(
        "financiadores.Financiador", on_delete=models.CASCADE, null=True, blank=True, related_name="+",
    )
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cuenta de referencia"
        verbose_name_plural = "cuentas de referencia"
        ordering = ["ambito", "rol", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(ambito="financiador", financiador__isnull=False, institucion__isnull=True)
                    | Q(ambito="plataforma", financiador__isnull=True)
                    | Q(ambito="institucion", institucion__isnull=False, financiador__isnull=True)
                ),
                name="simulacion_cuenta_ambito_valido",
            ),
            models.UniqueConstraint(
                fields=["rol"], condition=Q(ambito="plataforma"), name="simulacion_cuenta_plataforma_unica",
            ),
            models.UniqueConstraint(
                fields=["rol", "institucion"], condition=Q(ambito="institucion"),
                name="simulacion_cuenta_institucion_unica",
            ),
            models.UniqueConstraint(
                fields=["rol", "financiador"], condition=Q(ambito="financiador"),
                name="simulacion_cuenta_financiador_unica",
            ),
        ]

    def __str__(self):
        return f"{self.usuario} · {self.ambito} · {self.rol}"


class SesionSimulacion(models.Model):
    """Una simulación: del superusuario, con una cuenta y en un ámbito.

    El perfil y el ámbito se copian al iniciar para que el registro siga
    diciendo lo que se simuló aunque después cambie el catálogo. El id es el
    valor que el frontend manda en `X-HEN-Simulacion`; sin la sesión JWT del
    mismo superusuario no sirve de nada.
    """

    class Fin(models.TextChoices):
        SALIDA = "salida", "Volvió a Sistema"
        REEMPLAZO = "reemplazo", "Eligió otro perfil o ámbito"
        CIERRE = "cierre", "Cerró la sesión"
        VENCIMIENTO = "vencimiento", "Venció"
        INVALIDA = "invalida", "La cuenta o el ámbito dejaron de ser válidos"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    superusuario = models.ForeignKey(
        "accounts.Usuario", on_delete=models.PROTECT, related_name="simulaciones",
    )
    cuenta = models.ForeignKey(
        "accounts.Usuario", on_delete=models.PROTECT, related_name="simulaciones_recibidas",
    )
    ambito = models.CharField(max_length=20, choices=Ambito.choices)
    rol = models.CharField(max_length=20)
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    financiador = models.ForeignKey(
        "financiadores.Financiador", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
    )
    iniciada = models.DateTimeField(auto_now_add=True, db_index=True)
    vence = models.DateTimeField()
    finalizada = models.DateTimeField(null=True, blank=True)
    fin = models.CharField(max_length=20, choices=Fin.choices, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = "sesión de simulación"
        verbose_name_plural = "sesiones de simulación"
        ordering = ["-iniciada"]
        indexes = [models.Index(fields=["superusuario", "finalizada"])]

    def __str__(self):
        return f"{self.superusuario} como {self.rol} ({self.ambito}) · {self.iniciada:%d/%m/%Y %H:%M}"

    def finalizar(self, fin):
        """Cierra la sesión una sola vez; un segundo cierre no pisa el primero."""
        if self.finalizada is not None:
            return
        ahora = timezone.now()
        SesionSimulacion.objects.filter(pk=self.pk, finalizada__isnull=True).update(finalizada=ahora, fin=fin)
        self.refresh_from_db(fields=["finalizada", "fin"])


class OperacionSimulada(models.Model):
    """Una escritura intentada durante una simulación, se haya permitido o no."""

    sesion = models.ForeignKey(SesionSimulacion, on_delete=models.PROTECT, related_name="operaciones")
    metodo = models.CharField(max_length=10)
    ruta = models.CharField(max_length=300)
    estado = models.PositiveSmallIntegerField()
    momento = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "operación simulada"
        verbose_name_plural = "operaciones simuladas"
        ordering = ["-momento", "-id"]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Una operación simulada no se modifica.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una operación simulada no se elimina.")
