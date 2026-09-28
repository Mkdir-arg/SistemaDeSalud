"""Guarda común de los comandos que escriben datos ficticios."""
from django.conf import settings
from django.core.management.base import CommandError


def exigir_entorno_de_prueba(comando):
    """Frena la carga en producción antes de tocar la base.

    Se decide por `ENTORNO` y no por lo que haya cargado: una base con datos
    puede ser una demo que se quiere rehacer, y una vacía puede ser producción
    el día de la instalación.
    """
    if settings.ENTORNO == "produccion":
        raise CommandError(
            f"{comando} carga datos ficticios y está deshabilitado con ENTORNO=produccion. "
            "No se modificó ningún dato."
        )
