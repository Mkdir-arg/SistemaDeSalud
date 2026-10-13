"""Pruebas de concurrencia sólo sobre PostgreSQL local o demo Docker dedicado."""
import os
import dj_database_url
from .settings_financiadores_test import *  # noqa: F403
from .postgres_test_guard import validar_destino_postgres

url = os.environ.get("SALUD_TEST_POSTGRES_URL", "")
validar_destino_postgres(
    url, entorno=ENTORNO,  # noqa: F405
    proyecto_docker=os.environ.get("SALUD_TEST_DOCKER_PROJECT", ""),
)
DATABASES = {"default": dj_database_url.parse(url, conn_max_age=0)}
DATABASES["default"]["TEST"] = {"NAME": "test_salud_financiadores_test"}
