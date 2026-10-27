"""Sólo PostgreSQL aislado de #136, con credenciales específicas y sin leer .env."""
import os
from .issue136_settings import *  # noqa: F403

DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": os.environ.get("ISSUE136_PG_HOST", "127.0.0.1"),
    "PORT": os.environ.get("ISSUE136_PG_PORT", "55436"),
    "NAME": os.environ.get("ISSUE136_PG_NAME", "issue136"),
    "USER": os.environ.get("ISSUE136_PG_USER", "issue136"),
    "PASSWORD": os.environ["ISSUE136_PG_PASSWORD"],
    "TEST": {"NAME": os.environ.get("ISSUE136_PG_TEST_NAME", "test_issue136")},
}}
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": []}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
