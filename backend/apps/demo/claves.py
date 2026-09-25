"""Contraseña de los usuarios ficticios."""
import os

CLAVE_POR_DEFECTO = "demo1234"


def clave_demo():
    """`DEMO_PASSWORD` si está definida; si no, la clave conocida de siempre.

    Una sola para todos los usuarios de la carga: la demo se recorre cambiando de
    rol, y una clave distinta por persona sólo agrega una planilla que perder. El
    valor no se imprime nunca; la clave por defecto sí se avisa, porque en un
    entorno publicado cualquiera que haya leído el repositorio la conoce.
    """
    return os.environ.get("DEMO_PASSWORD") or CLAVE_POR_DEFECTO


def usa_clave_por_defecto():
    return not os.environ.get("DEMO_PASSWORD")
