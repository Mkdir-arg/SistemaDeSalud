"""
Usuarios y pertenencia institucional.

Un usuario se autentica por email. Su rol no es global: depende de la
institución (y opcionalmente del área) en la que actúa. Por eso el rol vive
en `Membresia`, no en el usuario.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


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


class Membresia(models.Model):
    """
    Vincula un usuario con una institución y le da un rol allí.
    Un mismo usuario puede tener membresías en varias instituciones, y dentro
    de una institución puede actuar sobre una o más áreas.
    """

    class Rol(models.TextChoices):
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
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="membresias"
    )
    rol = models.CharField(max_length=20, choices=Rol.choices)
    areas = models.ManyToManyField(
        "instituciones.Area", blank=True, related_name="miembros"
    )
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membresía"
        verbose_name_plural = "membresías"
        unique_together = [("usuario", "institucion", "rol")]

    def __str__(self):
        return f"{self.usuario} · {self.get_rol_display()} @ {self.institucion}"


class LegajoProfesional(models.Model):
    """Datos profesionales de un usuario (matrícula, especialidad)."""

    usuario = models.OneToOneField(
        Usuario, on_delete=models.CASCADE, related_name="legajo"
    )
    especialidad = models.CharField(max_length=120, blank=True)
    matricula = models.CharField(max_length=60, blank=True)

    class Meta:
        verbose_name = "legajo profesional"
        verbose_name_plural = "legajos profesionales"

    def __str__(self):
        return f"Legajo de {self.usuario}"
