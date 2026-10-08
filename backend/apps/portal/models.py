"""
Portal del paciente: la cuenta propia del paciente y lo que la rodea.

**No es un `accounts.Usuario`, a propósito.** La API institucional deja entrar
a cualquier `Usuario` autenticado y confía en que cada vista filtre por
membresía. Hoy casi todas lo hacen, pero algunas no (`/api/estado/`, el esquema,
las acciones que contestan distinto según exista o no un id) y cada vista nueva
nace con `IsAuthenticated` por defecto. Si el paciente fuera un `Usuario`, cada
descuido futuro le abriría una puerta a cualquier persona con una cuenta de
autorregistro. Con un modelo propio y un token propio (`autenticacion.py`), el
paciente no existe para la API institucional y el personal no existe para
`/api/mi/*`.

- `CuentaPaciente`: email, contraseña (hasher de Django) e identidad validada.
- `SesionPortal`: los tokens de acceso y renovación, guardados como hash.
- `EnlacePortal`: los enlaces de verificación y recupero que van por correo.
- `EventoPortal`: la auditoría de altas, ingresos, contraseñas e identidad.
"""
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class CuentaPaciente(models.Model):
    class Identidad(models.TextChoices):
        SIN_VALIDAR = "sin_validar", "sin validar"
        VALIDADA = "validada", "validada"

    class Sexo(models.TextChoices):
        # Los tres valores que imprime el DNI argentino y que pide RENAPER.
        FEMENINO = "F", "femenino"
        MASCULINO = "M", "masculino"
        NO_BINARIO = "X", "X"

    class Via(models.TextChoices):
        RENAPER = "renaper", "RENAPER"

    email = models.EmailField(unique=True)
    password = models.CharField("contraseña", max_length=128)
    email_verificado_at = models.DateTimeField("email verificado", null=True, blank=True)
    # Una cuenta que se da de baja desde el admin no ingresa ni renueva.
    activa = models.BooleanField(default=True)

    identidad = models.CharField(max_length=12, choices=Identidad.choices, default=Identidad.SIN_VALIDAR)
    # Normalizado como `registros.Ciudadano` (ver `normalizar_documento`): es la
    # clave con la que el #121 busca a la persona en toda la red.
    documento = models.CharField(max_length=30, blank=True)
    sexo = models.CharField(max_length=1, choices=Sexo.choices, blank=True)
    identidad_via = models.CharField("vía de validación", max_length=12, choices=Via.choices, blank=True)
    identidad_validada_at = models.DateTimeField("identidad validada", null=True, blank=True)
    # Lo que devolvió RENAPER, no lo que tipeó el paciente, con «Primera
    # mayúscula» (ver `renaper.formatear_nombre`).
    nombre = models.CharField(max_length=120, blank=True)
    apellido = models.CharField(max_length=120, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)

    # R5: los «no coincide» seguidos. Al llegar al tope se bloquea la validación
    # (no el ingreso) hasta `validacion_bloqueada_hasta`.
    intentos_validacion = models.PositiveSmallIntegerField(default=0)
    validacion_bloqueada_hasta = models.DateTimeField(null=True, blank=True)
    # Marca una consulta a RENAPER en curso: una sola por cuenta a la vez.
    validacion_en_curso_hasta = models.DateTimeField(null=True, blank=True)

    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "cuenta de paciente"
        verbose_name_plural = "cuentas de pacientes"
        constraints = [
            # R2: un documento validado es de una sola cuenta. Si dos cuentas
            # pudieran validar el mismo DNI, las dos verían los turnos y los
            # resultados de esa persona en toda la red. La vista lo controla
            # antes, para avisar a la titular; esto cubre la carrera entre dos
            # validaciones simultáneas.
            models.UniqueConstraint(
                fields=["documento"],
                condition=models.Q(identidad="validada"),
                name="portal_documento_validado_unico",
            ),
        ]

    def __str__(self):
        return self.email

    # DRF pregunta esto para decidir entre 401 y 403.
    is_authenticated = True

    @property
    def email_verificado(self):
        return self.email_verificado_at is not None

    @property
    def validada(self):
        return self.identidad == self.Identidad.VALIDADA

    def set_password(self, crudo):
        self.password = make_password(crudo)

    def set_unusable_password(self):
        # Hasta que se abra el enlace del correo no hay clave con la que entrar.
        self.password = make_password(None)

    def check_password(self, crudo):
        def actualizar(crudo):
            # Django re-hashea si cambió el algoritmo por defecto.
            self.set_password(crudo)
            self.save(update_fields=["password"])

        return check_password(crudo, self.password, actualizar)

    def validacion_bloqueada(self, ahora=None):
        hasta = self.validacion_bloqueada_hasta
        return hasta is not None and hasta > (ahora or timezone.now())


class SesionPortal(models.Model):
    """Una sesión iniciada con email y contraseña.

    Los tokens son aleatorios y opacos, no JWT: no los firma `SECRET_KEY`, así
    que `JWTAuthentication` no puede confundirlos con los del sistema, y cerrar
    sesión los revoca de verdad. En la base sólo queda el SHA-256.
    """

    cuenta = models.ForeignKey(CuentaPaciente, on_delete=models.CASCADE, related_name="sesiones")
    acceso_hash = models.CharField(max_length=64, unique=True)
    acceso_vence = models.DateTimeField()
    renovacion_hash = models.CharField(max_length=64, unique=True)
    renovacion_vence = models.DateTimeField()
    # Tope absoluto: renovar no estira la sesión más allá de esto.
    vence_maximo = models.DateTimeField()
    creada = models.DateTimeField(auto_now_add=True)
    revocada_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "sesión del portal"
        verbose_name_plural = "sesiones del portal"


class EnlacePortal(models.Model):
    """Enlace de un solo uso que se manda por correo (R4)."""

    class Tipo(models.TextChoices):
        VERIFICACION = "verificacion", "verificación de email"
        RECUPERO = "recupero", "recupero de contraseña"

    cuenta = models.ForeignKey(CuentaPaciente, on_delete=models.CASCADE, related_name="enlaces")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    vence = models.DateTimeField()
    usado_at = models.DateTimeField(null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "enlace del portal"
        verbose_name_plural = "enlaces del portal"


class EventoPortal(models.Model):
    """Auditoría del portal.

    No reusa `auditoria.AccesoClinico`: ahí `usuario` es un `accounts.Usuario`
    obligatorio, y acá no hay ninguno. Nunca se guardan contraseñas, tokens ni
    el número de trámite.
    """

    class Tipo(models.TextChoices):
        ALTA = "alta", "alta de cuenta"
        EMAIL_VERIFICADO = "email_verificado", "email verificado"
        INGRESO = "ingreso", "ingreso"
        INGRESO_FALLIDO = "ingreso_fallido", "ingreso fallido"
        CONTRASENA_CAMBIADA = "contrasena_cambiada", "contraseña cambiada"
        CONTRASENA_RESTABLECIDA = "contrasena_restablecida", "contraseña restablecida"
        IDENTIDAD_VALIDADA = "identidad_validada", "identidad validada"
        IDENTIDAD_RECHAZADA = "identidad_rechazada", "identidad rechazada por RENAPER"
        VALIDACION_BLOQUEADA = "validacion_bloqueada", "validación bloqueada"
        DOCUMENTO_EN_USO = "documento_en_uso", "documento validado en otra cuenta"
        RENAPER_NO_DISPONIBLE = "renaper_no_disponible", "RENAPER no disponible"

    tipo = models.CharField(max_length=24, choices=Tipo.choices)
    # Vacía en un ingreso fallido con un email que no tiene cuenta.
    cuenta = models.ForeignKey(
        CuentaPaciente, on_delete=models.SET_NULL, null=True, blank=True, related_name="eventos"
    )
    email = models.CharField(max_length=254, blank=True)
    ip = models.CharField(max_length=64, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    momento = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "evento del portal"
        verbose_name_plural = "eventos del portal"
        ordering = ["-momento"]
