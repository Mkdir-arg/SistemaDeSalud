"""Runner reproducible de #43. Ejecutar desde backend; nunca lee archivos .env."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SUITES = [
    "apps.financiadores.test_autorizaciones", "apps.financiadores.test_uso_autorizaciones",
    "apps.financiadores.test_esperas", "apps.financiadores.test_concurrencia_clinica",
    "apps.financiadores.test_piloto", "apps.finanzas.test_cobros", "apps.finanzas.test_dinero",
    "tests.issue43.test_circuito",
]


def entorno():
    # Conservar PATH y herramientas, pero impedir que dotenv seleccione destinos.
    return {**os.environ, "SALUD_ISSUE43_AISLADO": "1", "ENTORNO": "desarrollo",
            "PYTHON_DOTENV_DISABLED": "1", "DJANGO_SETTINGS_MODULE": "config.settings_issue43_test",
            "PYTHONIOENCODING": "utf-8"}


def ejecutar(*args):
    subprocess.run([sys.executable, *args], cwd=ROOT, env=entorno(), check=True)


if __name__ == "__main__":
    accion = sys.argv[1]
    if accion == "preparar":
        ejecutar("manage.py", "migrate", "--noinput")
        ejecutar("-m", "tests.issue43.escenario", "preparar", sys.argv[2])
    elif accion == "estado":
        ejecutar("-m", "tests.issue43.escenario", "estado", sys.argv[2])
    elif accion in {"suites", "completa"}:
        ejecutar("manage.py", "test", *(SUITES if accion == "suites" else []), "--noinput", "--verbosity=1")
    elif accion == "checks":
        ejecutar("manage.py", "check")
        ejecutar("manage.py", "makemigrations", "--check", "--dry-run")
        ejecutar("manage.py", "spectacular", "--fail-on-warn", "--file", os.devnull)
    else:
        raise SystemExit("Usar preparar <metadata.json>, estado <caso>, suites, completa o checks")
