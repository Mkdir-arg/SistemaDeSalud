"""
Usuarios y pertenencia institucional.

Un usuario se autentica por email. Sus roles viven en `Membresia`: los roles
institucionales tienen institución; los estatales pueden ser globales.
"""
import uuid

from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("El superusuario debe tener is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("El superusuario debe tener is_superuser=True")
        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Persona que opera el sistema. Login por email."""

    email = models.EmailField("email", unique=True)
    nombre = models.CharField("nombre", max_length=120)
    apellido = models.CharField("apellido", max_length=120, blank=True)

    # El super admin de plataforma es is_superuser; el resto opera vía Membresia.
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)

    creado = models.DateTimeField("creado", auto_now_add=True)
    actualizado = models.DateTimeField("actualizado", auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["apellido", "nombre"]

    def __str__(self):
        nombre_completo = f"{self.nombre} {self.apellido}".strip()
        return nombre_completo or self.email

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()


class MembresiaManager(models.Manager):
    """Oculta al actor sus membresías con una baja posterior al inicio de su sesión.

    Bloquear o borrar una pertenencia en A cierra A para las sesiones abiertas
    antes de la baja, aunque después se reactive: hace falta un nuevo login
    (#172, D-c). No toca otras instituciones ni a otros usuarios. Fuera de una
    solicitud autenticada con sesión institucional (workers, comandos, Admin)
    no hay corte. Los filtros por join (`membresias__activo`) no pasan por acá.
    """

    def get_queryset(self):
        from .sesiones import aplicar_corte_membresias

        return aplicar_corte_membresias(super().get_queryset())


class Membresia(models.Model):
    """
    Da un rol institucional o, para plataforma/auditor, un rol estatal global.
    Un mismo usuario puede tener membresías en varias instituciones, y dentro
    de una institución puede actuar sobre una o más áreas.
    """

    class Rol(models.TextChoices):
        PLATAFORMA = "plataforma", "Autoridad estatal / plataforma"
        AUDITOR = "auditor", "Auditor estatal"
        REPORTES = "reportes", "Reportes / solo lectura"
        ADMIN_INSTITUCION = "admin", "Admin de institución"
        CONFIGURADOR = "configurador", "Configurador"
        JEFE_AREA = "jefe_area", "Jefe / Supervisor de área"
        ADMINISTRATIVO = "administrativo", "Administrativo"
        ENFERMERIA = "enfermeria", "Enfermería"
        MEDICO = "medico", "Médico / profesional"

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="membresias"
    )
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="membresias",
        null=True, blank=True,
    )
    rol = models.CharField(max_length=20, choices=Rol.choices)
    areas = models.ManyToManyField(
        "instituciones.Area", blank=True, related_name="miembros"
    )
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    objects = MembresiaManager()

    class Meta:
        # Orden explícito: sin él la paginación es inestable y un registro
        # puede salir en dos páginas o en ninguna.
        ordering = ["institucion_id", "rol", "id"]
        base_manager_name = "objects_sin_corte"
        verbose_name = "membresía"
        verbose_name_plural = "membresías"
        unique_together = [("usuario", "institucion", "rol")]
        constraints = [
            models.CheckConstraint(
                condition=Q(institucion__isnull=False) | Q(rol__in=["plataforma", "auditor"]),
                name="accounts_membresia_global_solo_estatal",
            ),
            models.UniqueConstraint(
                fields=["usuario", "rol"], condition=Q(institucion__isnull=True),
                name="accounts_membresia_global_unica",
            ),
        ]

    objects_sin_corte = models.Manager()

    def __str__(self):
        return f"{self.usuario} · {self.get_rol_display()} @ {self.institucion or 'Plataforma'}"

    def save(self, *args, **kwargs):
        # La baja se detecta contra la fila guardada, no contra la instancia,
        # que puede venir de otra lectura. `.update()` masivo no pasa por acá.
        anterior = None
        if self.pk is not None:
            anterior = Membresia.objects_sin_corte.filter(pk=self.pk).values("activo", "institucion_id", "rol").first()
        super().save(*args, **kwargs)
        if anterior and anterior["activo"] and (
            not self.activo or anterior["institucion_id"] != self.institucion_id or anterior["rol"] != self.rol
        ):
            BajaMembresia.objects.create(usuario_id=self.usuario_id, institucion_id=anterior["institucion_id"])


class LegajoProfesional(models.Model):
    """Datos profesionales de un usuario (matrícula, especialidad)."""

    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="legajo"
    )
    especialidad = models.CharField(max_length=120, blank=True)
    matricula = models.CharField(max_length=60, blank=True)

    class Meta:
        # Orden explícito: sin él la paginación es inestable y un registro
        # puede salir en dos páginas o en ninguna.
        ordering = ["id"]
        verbose_name = "legajo profesional"
        verbose_name_plural = "legajos profesionales"

    def __str__(self):
        return f"Legajo de {self.usuario}"


class CorreoInstitucionalOutbox(models.Model):
    """Intención durable; contiene direcciones/IDs, nunca enlaces ni tokens."""

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PROCESANDO = "procesando", "Procesando"
        ENVIADO = "enviado", "Aceptado por backend de correo"
        DESCARTADO = "descartado", "Descartado"
        ERROR = "error", "Error definitivo"

    solicitud = models.JSONField(default=dict)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    creado = models.DateTimeField(auto_now_add=True)
    vence = models.DateTimeField()
    disponible_en = models.DateTimeField()
    reserva = models.UUIDField(null=True, blank=True)
    reservado_hasta = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveIntegerField(default=0)
    terminado_en = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["estado", "disponible_en"], name="accounts_correo_listo_idx"),
            models.Index(fields=["estado", "reservado_hasta"], name="accounts_correo_lease_idx"),
        ]


class SesionInstitucional(models.Model):
    """Familia JWT revocable; guarda huella del refresh vigente, nunca tokens."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="sesiones_institucionales")
    creada = models.DateTimeField(auto_now_add=True)
    revocada_at = models.DateTimeField(null=True, blank=True)
    refresh_jti_hash = models.CharField(max_length=64, editable=False)
    refresh_vence = models.DateTimeField()

    class Meta:
        verbose_name = "sesión institucional"
        verbose_name_plural = "sesiones institucionales"


class BajaMembresia(models.Model):
    """Registro append-only de bajas de pertenencia (desactivar o borrar).

    Una sesión institucional creada antes de la última baja de su titular en una
    institución ya no ve esa institución; `institucion` nula es el alcance global.
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="bajas_membresia")
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="+", null=True, blank=True,
    )
    momento = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["usuario", "momento"], name="accounts_baja_usuario_idx")]
        verbose_name = "baja de membresía"
        verbose_name_plural = "bajas de membresía"


@receiver(post_delete, sender=Membresia, dispatch_uid="accounts_baja_por_borrado")
def registrar_baja_por_borrado(sender, instance, origin=None, **kwargs):
    # Borrar y volver a crear no rehabilita sesiones anteriores. En la cascada de
    # un Usuario o una Institución no queda a quién o qué cortar.
    origen = origin.model if isinstance(origin, models.QuerySet) else type(origin)
    etiqueta = getattr(getattr(origen, "_meta", None), "label", "")
    if not instance.activo or etiqueta in {"accounts.Usuario", "instituciones.Institucion"}:
        return
    BajaMembresia.objects.create(usuario_id=instance.usuario_id, institucion_id=instance.institucion_id)
