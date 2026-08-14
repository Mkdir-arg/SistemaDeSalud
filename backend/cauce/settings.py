"""
Django settings for the Cauce project.

Cauce — constructor y motor de flujos para procesos de salud / Estado.
Backend: Django + DRF. Base de datos: Supabase (Postgres). Auth: JWT (SimpleJWT).
"""

from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga variables desde backend/.env
load_dotenv(BASE_DIR / ".env")


def env(key: str, default=None):
    return os.environ.get(key, default)


def env_bool(key: str, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# --- Seguridad -------------------------------------------------------------
CLAVE_DE_DESARROLLO = "django-insecure-dev-key-change-me"

SECRET_KEY = env("DJANGO_SECRET_KEY", CLAVE_DE_DESARROLLO)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Sin DEBUG y con la clave de desarrollo, el sistema NO arranca.
#
# Esa clave está escrita en el repositorio y en el docker-compose. Con ella,
# cualquiera que haya leído el proyecto puede firmar un JWT válido y entrar como
# quien quiera —incluido un admin de institución— sin tocar la base ni conocer
# ninguna contraseña. No hay señal de que esté pasando: los tokens falsos son
# indistinguibles de los buenos.
#
# Falla al arrancar y no con un aviso en el log a propósito: el día del
# despliegue nadie lee los logs de arranque, y un sistema que anda igual con una
# clave pública queda así durante años.
if not DEBUG and SECRET_KEY == CLAVE_DE_DESARROLLO:
    raise RuntimeError(
        "DJANGO_SECRET_KEY es la clave de desarrollo, que está publicada en el "
        "repositorio: con ella cualquiera puede firmar un token y entrar como "
        "cualquier usuario. Generá una y ponela en el entorno:\n"
        "  python -c \"import secrets; print(secrets.token_urlsafe(64))\""
    )

# --- Endurecimiento para producción ---------------------------------------- #
#
# Sólo se aplica con DEBUG apagado: en desarrollo se corre sobre http, y forzar
# HTTPS ahí deja a todo el equipo con un redirect infinito.
#
# `manage.py check --deploy` los pide todos y hay un test que lo corre: sin eso,
# la lista se completa el día que alguien se acuerda de mirar el checklist.
if not DEBUG:
    # El proxy termina el TLS y habla http con la aplicación; sin esto Django ve
    # http y redirige para siempre.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)

    # Un año, con subdominios. HSTS es difícil de revertir —el navegador lo
    # recuerda—, así que se puede bajar por entorno para el primer despliegue.
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # La sesión del admin de Django. La API usa JWT, pero el admin existe y por
    # ahí se entra a todo.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Un hospital con la aplicación embebida en un iframe ajeno es clickjacking
    # sobre acciones clínicas: «llamar paciente», «dar el alta». Hoy coincide con
    # el default de Django; se deja escrito porque es una decisión, no una
    # herencia, y porque hay un test que la nombra.
    X_FRAME_OPTIONS = "DENY"

    # No se repiten acá los ajustes que Django ya trae seguros por defecto
    # (nosniff, referrer-policy, cookies httponly): el test de `check --deploy`
    # se pone en rojo si alguno cambia, así que restatearlos sólo agrega ruido.


# --- Apps ------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    # Apps del proyecto
    "apps.accounts",
    "apps.instituciones",
    "apps.flujos",
    "apps.formularios",
    "apps.casos",
    "apps.registros",
    "apps.agenda",
    "apps.farmacia",
    "apps.red",
    "apps.auditoria",
    "apps.fhir",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cauce.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cauce.wsgi.application"


# --- Base de datos ---------------------------------------------------------
# Supabase es un Postgres administrado: usar la DATABASE_URL del pooler.
# Si no hay DATABASE_URL definida, cae a SQLite para desarrollo local.
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=env_bool("DATABASE_SSL", True),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# --- Auth ------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- DRF + JWT -------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "cauce.pagination.Paginacion",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --------------------------------------------------------------------------- #
# Documentación de la API (OpenAPI 3)
# --------------------------------------------------------------------------- #
# Un hospital no compra un sistema que no se pueda integrar con lo que ya tiene.
# El esquema es lo primero que pide el área de sistemas del otro lado, y además
# es la referencia que evita tener que leer el código para saber qué devuelve
# cada endpoint.
SPECTACULAR_SETTINGS = {
    "TITLE": "Cauce · API",
    "DESCRIPTION": """
API de Cauce: flujos de trabajo para instituciones de salud.

**Autenticación.** Todo requiere un token JWT (`Authorization: Bearer <token>`)
que se obtiene en `POST /api/auth/token/`. Las dos excepciones son ese mismo
endpoint y la pantalla pública de llamados de sala (`/api/pantalla/<token>/`),
que se sirve sin sesión porque corre en un televisor.

**Alcance.** Los listados devuelven sólo lo de las instituciones donde quien
consulta tiene una membresía activa; el filtro es del servidor, no de la
pantalla.

**Listados.** Vienen paginados (`?page`, `?page_size`) y aceptan `?formato=csv`
cuando el recurso declara columnas exportables.

**Interoperabilidad (FHIR R4).** Además de esta API hay una fachada FHIR de sólo
lectura en `/fhir/`, con `Patient`, `Encounter` y `Organization`. No se documenta
acá porque FHIR trae su propio documento de contrato: `GET /fhir/metadata`
devuelve el CapabilityStatement y se sirve sin credenciales.
""",
    "VERSION": "1.0.0",
    # En producción el esquema pide sesión.
    #
    # No expone datos, pero sí el mapa completo de la API: qué endpoints existen,
    # con qué campos y qué acciones acepta cada uno —incluidos los de historia
    # clínica—. Publicarle eso a cualquiera que llegue al servidor le ahorra la
    # mitad del trabajo a quien esté buscando por dónde entrar, y no le sirve a
    # nadie más: quien tiene que integrar tiene credenciales.
    #
    # En desarrollo queda abierto, que es cuando se lo consulta a cada rato.
    "SERVE_PERMISSIONS": ["apps.common.PuedeVerElEsquema"],
    # El esquema no incluye la pantalla de Swagger a sí misma.
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Agrupa por app en vez de por el primer segmento de la URL: así «casos» y
    # «items-fila» quedan juntos, que es como se los usa.
    # Tres modelos tienen un campo «estado» con opciones distintas. Sin esto
    # el esquema los nombra «Estado719Enum», que es lo que termina leyendo quien
    # tiene que integrar.
    "ENUM_NAME_OVERRIDES": {
        "EstadoCasoEnum": "apps.casos.models.ESTADOS_CASO",
        "EstadoVersionEnum": "apps.flujos.models.ESTADOS_VERSION",
        "EstadoInstitucionEnum": "apps.instituciones.models.ESTADOS_INSTITUCION",
    },
    "TAGS": [
        {"name": "casos", "description": "Casos, su operación y la cola de espera."},
        {"name": "flujos", "description": "Diseño de flujos: versiones, nodos y conexiones."},
        {"name": "formularios", "description": "Formularios y campos de los pasos."},
        {"name": "instituciones", "description": "Estructura organizativa: áreas, boxes, grupos."},
        {"name": "registros", "description": "Pacientes e historia clínica."},
        {"name": "usuarios", "description": "Cuentas, membresías y legajos."},
    ],
}

# --------------------------------------------------------------------------- #
# Integraciones con sistemas externos (nodo «Integración» del diseñador)
# --------------------------------------------------------------------------- #
# Lista blanca de hosts a los que un flujo puede llamar.
#
# El nodo de integración deja que alguien con permiso de DISEÑO configure una URL
# que llama el SERVIDOR. Sin restricción eso es un SSRF con formulario: quien
# diseñe un flujo podría hacer que el backend consulte `http://localhost:5432`,
# el endpoint de metadatos de la nube (169.254.169.254) o cualquier servicio
# interno que no está expuesto a internet — y guardar la respuesta en un campo
# del caso, que después se lee desde la pantalla.
#
# Se resuelve con lista blanca y no bloqueando rangos privados porque el DNS
# puede cambiar de respuesta entre la validación y la petición (rebinding).
#
# VACÍA POR DEFECTO: la función viene apagada y hay que habilitar cada host a
# conciencia, del lado de la infraestructura y no del diseñador del flujo.
INTEGRACIONES_PERMITIDAS = [
    h.strip() for h in env("CAUCE_INTEGRACIONES_PERMITIDAS", "").split(",") if h.strip()
]
# Tope de espera de una llamada externa. El motor la hace en línea, así que un
# servicio lento colgaría el avance del caso.
INTEGRACIONES_TIMEOUT = int(env("CAUCE_INTEGRACIONES_TIMEOUT", "6"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}


# --- CORS ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in env("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if o.strip()
]


# --- Internacionalización --------------------------------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True


# --- Estáticos -------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise: sirve los estáticos (incluido el admin) con gunicorn sin nginx.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Media (archivos subidos) ----------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Tope de subida en memoria / tamaño máximo razonable: 10 MB.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
