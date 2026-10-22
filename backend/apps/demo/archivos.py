"""Los archivos de la app en el bucket, para vaciarlos al recargar la demo (#171, D4).

Solo se tocan los prefijos que escribe la app: `uploads/` del almacenamiento
`default` (adjuntos clínicos, estudios, evidencia de consentimientos) y todo
el almacenamiento `facturas` (que en el bucket ya vive bajo `facturas/`).

Fuera de `ENTORNO=demo`, o con los archivos en disco local, no hay nada que
vaciar: en desarrollo los archivos son del desarrollador, y en producción son
datos de pacientes.
"""
import logging
from posixpath import join

from django.conf import settings
from django.core.files.storage import storages

logger = logging.getLogger(__name__)

PREFIJOS = (("default", "uploads"), ("facturas", ""))


def _recorrer(almacenamiento, carpeta):
    try:
        carpetas, archivos = almacenamiento.listdir(carpeta)
    except FileNotFoundError:
        return
    for nombre in archivos:
        yield join(carpeta, nombre) if carpeta else nombre
    for nombre in carpetas:
        yield from _recorrer(almacenamiento, join(carpeta, nombre) if carpeta else nombre)


def corresponde_vaciar():
    return settings.ENTORNO == "demo" and settings.ALMACENAMIENTO_EN_BUCKET


def claves_a_vaciar():
    """[(alias de almacenamiento, clave)] de los objetos de la app, o [] si no corresponde."""
    if not corresponde_vaciar():
        return []
    return [(alias, clave) for alias, prefijo in PREFIJOS for clave in _recorrer(storages[alias], prefijo)]


def borrar(claves):
    """Borra las claves y devuelve las que no se pudieron borrar.

    Un fallo no frena el resto: lo que queda es un objeto huérfano, que ninguna
    fila de la base referencia y se lleva la próxima recarga.
    """
    fallidas = []
    for alias, clave in claves:
        try:
            storages[alias].delete(clave)
        except Exception:
            logger.exception("No se pudo borrar un archivo de la demo (%s)", alias)
            fallidas.append((alias, clave))
    return fallidas
