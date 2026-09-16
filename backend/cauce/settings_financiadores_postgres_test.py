"""Pruebas de concurrencia sólo sobre un PostgreSQL local dedicado."""
import os
from urllib.parse import urlparse
from django.core.exceptions import ImproperlyConfigured
import dj_database_url
from .settings_financiadores_test import *  # noqa: F403

url = os.environ.get("CAUCE_TEST_POSTGRES_URL", "")
destino = urlparse(url)
if destino.hostname not in {"localhost", "127.0.0.1", "::1"} or destino.path != "/cauce_financiadores_test":
    raise ImproperlyConfigured("CAUCE_TEST_POSTGRES_URL debe apuntar al PostgreSQL local dedicado cauce_financiadores_test.")
DATABASES = {"default": dj_database_url.parse(url, conn_max_age=0)}
DATABASES["default"]["TEST"] = {"NAME": "test_cauce_financiadores_test"}
