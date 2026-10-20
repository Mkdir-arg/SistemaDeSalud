"""Crea únicamente tres identidades reservadas del escenario visual #172."""
import os

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.credenciales import exigir_configuracion_correo
from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion
from apps.simulacion.perfiles import es_cuenta_referencia

NOMBRE = "AUD172 · Laboratorio visual"
TIPO = "Escenario sintético auditoría 172"
APELLIDO = "Visual AUD172"
CUENTAS = (
    ("aud172-root@visual.example.invalid", "Raíz AUD172", Membresia.Rol.ADMIN_INSTITUCION, True),
    ("aud172-admin@visual.example.invalid", "Administrador AUD172", Membresia.Rol.ADMIN_INSTITUCION, False),
    ("aud172-medico@visual.example.invalid", "Médico AUD172", Membresia.Rol.MEDICO, False),
)


class Command(BaseCommand):
    help = "Prepara identidades sintéticas AUD172 en el laboratorio visual exclusivo; no borra ni resetea datos."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if (os.environ.get("SALUD_AUDITORIA172_VISUAL") != "1"
                or settings.SETTINGS_MODULE != "config.settings_visual_auditoria172"
                or settings.ENTORNO != "demo"
                or connection.vendor != "postgresql"
                or db.get("NAME") != "auditoria172"
                or db.get("HOST") != "db-auditoria172"
                or db.get("USER") != "auditoria172"
                or settings.EMAIL_BACKEND != "django.core.mail.backends.filebased.EmailBackend"
                or settings.EMAIL_FILE_PATH != "/laboratorio/privado/correo-visual"):
            raise CommandError("Destino/configuración ajenos al escenario visual AUD172; no se modificó nada.")
        clave = os.environ.get("AUDITORIA172_VISUAL_PASSWORD")
        if not clave:
            raise CommandError("Definir AUDITORIA172_VISUAL_PASSWORD externamente; no se modificó nada.")
        exigir_configuracion_correo()
        # Abrir la transacción solamente después de verificar el destino.
        with transaction.atomic():
            self._preparar(clave)

    def _preparar(self, clave):
        # Serializar únicamente dos invocaciones de este mismo fixture. No
        # limpiar tablas, cachés ni alterar cuentas de otros escenarios.
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('auditoria172.visual-fixture', 172))")
        instituciones = list(Institucion.objects.select_for_update().filter(nombre=NOMBRE))
        if len(instituciones) > 1 or (instituciones and instituciones[0].tipo != TIPO):
            raise CommandError("El identificador visual de institución está ocupado; no se modificó nada.")
        institucion = instituciones[0] if instituciones else Institucion.objects.create(nombre=NOMBRE, tipo=TIPO)
        cuentas = []
        for email, nombre, rol, root in CUENTAS:
            existentes = list(Usuario.objects.select_for_update().filter(email__iexact=email))
            if len(existentes) > 1:
                raise CommandError("Colisión de identidad visual; no se modificó nada.")
            usuario = existentes[0] if existentes else None
            if usuario is not None:
                if (usuario.email != email or usuario.apellido != APELLIDO
                        or usuario.is_superuser != root or usuario.is_staff != root
                        or es_cuenta_referencia(usuario)
                        or usuario.membresias.exclude(institucion=institucion).exists()):
                    raise CommandError("Identidad preexistente fuera del escenario reservado; no se modificó nada.")
                # No pisar cambios de contraseña efectuados durante la prueba.
                # Repetir el fixture no restaura claves ni reactiva identidades.
            else:
                candidato = Usuario(email=email, nombre=nombre, apellido=APELLIDO)
                try:
                    validate_password(clave, user=candidato)
                except ValidationError:
                    raise CommandError("La contraseña visual no cumple los validadores; no se modificó nada.") from None
                crear = Usuario.objects.create_superuser if root else Usuario.objects.create_user
                usuario = crear(email, clave, nombre=nombre, apellido=APELLIDO)
            membresias = list(usuario.membresias.filter(institucion=institucion))
            if any(m.rol != rol for m in membresias):
                raise CommandError("La cuenta visual tiene un rol ajeno al fixture; no se modificó nada.")
            Membresia.objects.get_or_create(usuario=usuario, institucion=institucion, rol=rol)
            cuentas.append(usuario)
        self.stdout.write(self.style.SUCCESS(f"Escenario visual AUD172 preparado: institución #{institucion.pk}."))
        for usuario in cuentas:
            self.stdout.write(f"Usuario #{usuario.pk}: {usuario.email}")
