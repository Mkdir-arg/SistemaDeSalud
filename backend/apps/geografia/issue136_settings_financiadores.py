"""Suite completa de financiadores en PG efímero, sin importar settings productivos."""
from pathlib import Path
from .issue136_settings_runtime import *  # noqa: F403

BASE_DIR = Path(__file__).resolve().parents[2]
INSTALLED_APPS = [*INSTALLED_APPS, "django.contrib.admin", "django.contrib.messages", "django.contrib.staticfiles"]  # noqa: F405
ROOT_URLCONF = "apps.geografia.issue136_urls_financiadores"
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.CorteMembresiasMiddleware",
    "apps.simulacion.middleware.SimulacionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_AUTHENTICATION_CLASSES": [  # noqa: F405
    "apps.simulacion.autenticacion.SimulacionAuthentication",
    "apps.accounts.autenticacion.AutenticacionInstitucional",
]}
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True,
    "DIRS": [BASE_DIR / "templates"], "OPTIONS": {"context_processors": [
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]}}]
STATIC_URL = "/static/"
MEDIA_ROOT = "/tmp/issue136-media"
SALUD_FACTURAS_ADJUNTOS = False
SALUD_FACTURAS_ADJUNTOS_DIR = "/tmp/issue136-privado/facturas"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
