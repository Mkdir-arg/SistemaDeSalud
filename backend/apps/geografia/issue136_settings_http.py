"""Endpoints reales sobre PostgreSQL de pruebas, sin settings productivos ni .env."""
from .issue136_settings_postgres import *  # noqa: F403

ROOT_URLCONF = "apps.geografia.issue136_urls"
ALLOWED_HOSTS = ["testserver"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_PAGINATION_CLASS": "config.pagination.Paginacion",
    "PAGE_SIZE": 25,
}
