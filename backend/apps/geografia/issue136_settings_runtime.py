"""JWT institucional real y pruebas operativas locales; nunca importa .env."""
from datetime import timedelta
from .issue136_settings_http import *  # noqa: F403

ROOT_URLCONF = "apps.geografia.issue136_urls_runtime"
MIDDLEWARE = ["apps.accounts.middleware.CorteMembresiasMiddleware"]
AUTHENTICATION_BACKENDS = ["apps.simulacion.autenticacion.BackendSinCuentasDeReferencia"]
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.autenticacion.AutenticacionInstitucional"],
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "CHECK_REVOKE_TOKEN": True,
    "LEEWAY": 30,
    "TOKEN_OBTAIN_SERIALIZER": "apps.accounts.jwt.TokenObtainPairInstitucionalSerializer",
    "TOKEN_REFRESH_SERIALIZER": "apps.accounts.jwt.TokenRefreshInstitucionalSerializer",
    "USER_AUTHENTICATION_RULE": "apps.simulacion.autenticacion.regla_de_autenticacion",
}
CACHES = {alias: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "issue136-" + alias}
          for alias in ("default", "portal")}
INSTITUCIONAL_LOGIN_VENTANA_SEGUNDOS = 300
INSTITUCIONAL_LOGIN_FALLOS_EMAIL = 5
INSTITUCIONAL_LOGIN_FALLOS_IP = 30
