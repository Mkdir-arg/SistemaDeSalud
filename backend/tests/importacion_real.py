"""Preparación y servidor del E2E OSTEL usando el PostgreSQL aislado de CI.

No carga .env, no reutiliza bases existentes y no elimina bases. El servicio
PostgreSQL pertenece al job; limpiar retira sólo el manifiesto con credenciales.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import gettempdir

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.postgres_test_guard import validar_destino_postgres


def rutas(variables):
    if variables.get("SALUD_IMPORTACION_E2E_AISLADO") != "1":
        raise RuntimeError("Se requiere SALUD_IMPORTACION_E2E_AISLADO=1.")
    if variables.get("ENTORNO", "desarrollo") != "desarrollo":
        raise RuntimeError("La importación E2E sólo admite ENTORNO=desarrollo.")
    directorio = Path(variables.get("SALUD_IMPORTACION_DIRECTORIO", ""))
    if not directorio.is_absolute():
        raise RuntimeError("Se requiere un directorio temporal absoluto.")
    directorio = directorio.resolve()
    if directorio.parent != Path(gettempdir()).resolve() or not directorio.name.startswith("salud-importacion182-"):
        raise RuntimeError("El directorio E2E debe ser propio y estar directamente en el temporal del runner.")
    manifiesto = directorio / "manifiesto.json"
    recibido = variables.get("SALUD_IMPORTACION_MANIFEST")
    if recibido and Path(recibido).resolve() != manifiesto:
        raise RuntimeError("El manifiesto no corresponde al directorio E2E.")
    return directorio, manifiesto


def entorno(variables=None):
    env = dict(os.environ if variables is None else variables)
    _, manifiesto = rutas(env)
    url = env.get("SALUD_TEST_POSTGRES_URL", "")
    validar_destino_postgres(url, entorno="desarrollo", proyecto_docker="")
    env.update(
        DJANGO_SETTINGS_MODULE="config.settings_financiadores_postgres_test",
        PYTHON_DOTENV_DISABLED="1", PYTHONIOENCODING="utf-8", ENTORNO="desarrollo",
        DJANGO_DEBUG="true", DJANGO_SECRET_KEY=secrets.token_urlsafe(48),
        DATABASE_URL=url, DATABASE_SSL="false", DJANGO_SSL_REDIRECT="false",
        DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,testserver", DJANGO_HSTS_SECONDS="0",
        RENAPER_MODO="simulado", SEED_DEMO="0", SEED_GUARDIA="0",
        SALUD_IMPORTACION_MANIFEST=str(manifiesto),
    )
    return env


def preparar():
    env = entorno()
    directorio, _ = rutas(env)
    if directorio.exists():
        raise RuntimeError("El directorio E2E ya existe; no se sobrescriben fixtures ni credenciales.")
    # El nombre es constante y el destino ya pasó el guard local de PostgreSQL.
    # La conexión administrativa sólo crea esta base nueva en el servicio del job.
    with psycopg.connect(env["SALUD_TEST_POSTGRES_URL"], dbname="postgres", autocommit=True) as conexion:
        if conexion.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("salud_financiadores_test",)).fetchone():
            raise RuntimeError("La base E2E ya existe; preparar exige un servicio descartable nuevo.")
        conexion.execute("CREATE DATABASE salud_financiadores_test")
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, "../frontend/e2e/fixtures/preparar_importacion_real.py", str(directorio)],
                   cwd=ROOT, env=env, check=True)


def servidor():
    env = entorno()
    _, manifiesto = rutas(env)
    if not manifiesto.is_file():
        raise RuntimeError("Falta preparar el escenario ficticio antes de iniciar el servidor.")
    return subprocess.call([sys.executable, "manage.py", "runserver", "127.0.0.1:8232", "--noreload"],
                           cwd=ROOT, env=env)


def limpiar():
    # No abre conexiones ni recorre directorios. La infraestructura del job
    # elimina PostgreSQL; aquí sólo se retira el archivo con secretos ficticios.
    _, manifiesto = rutas(os.environ)
    manifiesto.unlink(missing_ok=True)


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) == 2 else ""
    if accion == "preparar":
        preparar()
    elif accion == "servidor":
        raise SystemExit(servidor())
    elif accion == "limpiar":
        limpiar()
    else:
        raise SystemExit("Usar preparar, servidor o limpiar.")
