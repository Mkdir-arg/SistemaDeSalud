"""Fixture visual explícita #172; nunca configuración de correo productivo."""
import os as _os

if _os.environ.get("SALUD_AUDITORIA172_VISUAL") != "1":
    raise RuntimeError("El escenario visual requiere SALUD_AUDITORIA172_VISUAL=1.")

from .settings_auditoria172 import *  # noqa: F403,E402

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", "backend-auditoria172"]
CORS_ALLOWED_ORIGINS = ["http://127.0.0.1:5172", "http://localhost:5172"]
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
INSTITUCIONAL_URL_BASE = "http://127.0.0.1:5172"
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "/laboratorio/privado/correo-visual"
EMAIL_TIMEOUT = 3
DEFAULT_FROM_EMAIL = "aud172-sistema@visual.example.invalid"
# Valores exclusivos del ensayo visual, no defaults ni políticas productivas.
INSTITUCIONAL_INVITACION_TIMEOUT = 86400
INSTITUCIONAL_RECUPERACION_TIMEOUT = 1800
INSTITUCIONAL_EMAIL_TIMEOUT = 1800
INSTITUCIONAL_THROTTLE_RATES = {"ip": "1000/min", "email": "1000/min", "usuario": "1000/min"}


# Política explícita del laboratorio; no habilita SMTP ni fija retención legal.
INSTITUCIONAL_CORREO_MODO = "outbox"
INSTITUCIONAL_OUTBOX_POLITICA = {
    "max_intentos": 3,
    "lease_segundos": 60,
    "backoff_inicial_segundos": 1,
    "backoff_maximo_segundos": 30,
    "espera_segundos": 1,
}
