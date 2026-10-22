"""Destino cerrado para #43: no hereda conexiones ni carga backend/.env."""
import os

from django.core.exceptions import ImproperlyConfigured

if os.environ.get("SALUD_ISSUE43_AISLADO") != "1":
    raise ImproperlyConfigured("#43 requiere SALUD_ISSUE43_AISLADO=1")
if os.environ.get("ENTORNO", "desarrollo") != "desarrollo":
    raise ImproperlyConfigured("#43 sólo admite ENTORNO=desarrollo")
# Antes del import: impedir que dotenv lea configuración de otro entorno.
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["DJANGO_DEBUG"] = "true"
os.environ["DJANGO_SECRET_KEY"] = "issue43-ficticio-exclusivo-no-usar-fuera-de-tests"
os.environ["DATABASE_URL"] = "postgres://issue43@127.0.0.1:55443/salud_issue43"

from .settings import *  # noqa: E402,F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": "salud_issue43", "USER": "issue43", "PASSWORD": "",
    "HOST": "127.0.0.1", "PORT": "55443", "CONN_MAX_AGE": 0,
    "TEST": {"NAME": "test_salud_issue43"},
}}
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
INTEGRACIONES_PERMITIDAS = []
RENAPER_MODO = "simulado"
RENAPER_URL = RENAPER_USUARIO = RENAPER_CLAVE = ""
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
