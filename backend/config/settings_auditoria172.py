"""Laboratorio #172: sólo PostgreSQL dedicado, sin dotenv ni proveedores reales.

Usar exclusivamente con docker-compose.auditoria172.yml y su red interna.
Las guardas de nombres no reemplazan el aislamiento de red de Compose.
"""
import os
import sys
from unittest.mock import patch

import dj_database_url

from .auditoria172_guard import validar_laboratorio

_url = validar_laboratorio(os.environ)
if "config.settings" in sys.modules:
    raise RuntimeError("Cargar settings_auditoria172 directamente, antes de config.settings.")

# settings.py llama load_dotenv sin una opción propia para omitirlo. El parche
# se limita a esa importación: ni se abre backend/.env ni se modifica producción.
_opciones = {
    "DJANGO_DEBUG": "false",
    "DATABASE_SSL": "false",
    "DJANGO_SSL_REDIRECT": "false",
    "DJANGO_HSTS_SECONDS": "0",
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,testserver,backend-auditoria172",
    "SALUD_INTEGRACIONES_PERMITIDAS": "",
    "RENAPER_MODO": "simulado",
    "RENAPER_URL": "",
    "RENAPER_USUARIO": "",
    "RENAPER_CLAVE": "",
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "EMAIL_HOST": "",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "PORTAL_URL_BASE": "http://127.0.0.1:8172",
    "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:8172",
    "SALUD_FACTURAS_ADJUNTOS_DIR": "/laboratorio/privado/facturas",
    # Sin bucket aunque el host lo tenga configurado (#171): archivos en disco.
    "BUCKET": "",
    "ACCESS_KEY_ID": "",
    "SECRET_ACCESS_KEY": "",
    "ENDPOINT": "",
}
with patch("dotenv.load_dotenv", return_value=False), patch.dict(os.environ, _opciones):
    from .settings import *  # noqa: F403

DATABASES = {"default": dj_database_url.parse(_url, conn_max_age=0)}
DATABASES["default"]["TEST"] = {"NAME": "test_auditoria172"}
MEDIA_ROOT = Path("/laboratorio/media")  # noqa: F405
SALUD_FACTURAS_ADJUNTOS_DIR = Path("/laboratorio/privado/facturas")  # noqa: F405
# Mantener DatabaseCache y su tabla migrada: está aislada por la DB exclusiva;
# reemplazarla por memoria escondería el comportamiento multiworker del portal.
CACHES["default"]["LOCATION"] = "auditoria172"  # noqa: F405
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PORTAL_CORREO_EN_SEGUNDO_PLANO = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405
