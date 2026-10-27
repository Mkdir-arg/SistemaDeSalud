"""Inspección de modelos/migraciones sin .env ni conexión a una base de datos."""
SECRET_KEY = "issue136-static-only-not-for-serving"
AUTH_USER_MODEL = "accounts.Usuario"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
ENTORNO = "desarrollo"
DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    *["apps." + app for app in (
        "accounts", "instituciones", "geografia", "flujos", "formularios", "casos",
        "registros", "agenda", "farmacia", "finanzas", "financiadores", "red", "auditoria",
        "fhir", "demo", "simulacion", "portal",
    )],
]
