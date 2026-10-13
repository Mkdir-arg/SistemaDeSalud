"""Validar destino de tests sin abrir conexiones ni aceptar una base operativa."""
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ImproperlyConfigured


def validar_destino_postgres(url, *, entorno, proyecto_docker):
    destino = urlparse(url)
    local = destino.hostname in {"localhost", "127.0.0.1", "::1"}
    docker_demo = (destino.hostname == "db" and entorno == "demo"
                   and proyecto_docker == "salud-padron-130")
    # OPTIONS del driver no deben poder sustituir host/base mediante query params.
    parametros = parse_qs(destino.query, keep_blank_values=True)
    if (entorno not in {"demo", "desarrollo"}
            or destino.scheme not in {"postgres", "postgresql"}
            or destino.path != "/salud_financiadores_test"
            or not (local or docker_demo)
            or set(parametros) - {"sslmode"}
            or destino.fragment):
        raise ImproperlyConfigured(
            "SALUD_TEST_POSTGRES_URL requiere la base dedicada salud_financiadores_test "
            "en localhost, o db sólo con ENTORNO=demo y "
            "SALUD_TEST_DOCKER_PROJECT=salud-padron-130; nunca producción."
        )
