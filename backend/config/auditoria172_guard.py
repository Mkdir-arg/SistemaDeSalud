"""Guardas puras del laboratorio #172; no importan Django ni abren conexiones."""
from urllib.parse import urlsplit


def validar_laboratorio(entorno):
    """Aceptar solamente el servicio/base/rol del proyecto Docker dedicado."""
    mensaje = "Auditoría172 requiere proyecto, PostgreSQL y credenciales exclusivos del laboratorio."
    if (entorno.get("SALUD_AUDITORIA172") != "1"
            or entorno.get("SALUD_TEST_DOCKER_PROJECT") != "salud-auditoria172"
            or entorno.get("ENTORNO") != "demo"):
        raise ValueError(mensaje)
    url = entorno.get("DATABASE_URL", "")
    try:
        destino = urlsplit(url)
        valido = (
            destino.scheme in {"postgres", "postgresql"}
            and destino.hostname == "db-auditoria172"
            and destino.port == 5432
            and destino.path == "/auditoria172"
            and destino.username == "auditoria172"
            and bool(destino.password)
            and not destino.query
            and not destino.fragment
        )
    except ValueError:
        valido = False
    if not valido or entorno.get("SALUD_TEST_POSTGRES_URL", url) != url:
        raise ValueError(mensaje)
    if not entorno.get("DJANGO_SECRET_KEY"):
        raise ValueError("Definir una DJANGO_SECRET_KEY exclusiva externamente.")
    return url
