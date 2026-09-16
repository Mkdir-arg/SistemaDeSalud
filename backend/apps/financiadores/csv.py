"""Texto literal compartido por las exportaciones administrativas de cobertura."""
import unicodedata


def texto_csv_seguro(valor, *, identificador=False):
    texto = str(valor)
    if not texto:
        return texto
    inicio = texto
    while inicio and (inicio[0].isspace() or unicodedata.category(inicio[0]).startswith("C")):
        inicio = inicio[1:]
    # Nunca usar fórmulas ="00123" para conservar identificadores. Tampoco
    # reinterpretar como fecha un nombre o código con apariencia de fecha.
    if identificador or inicio.startswith(("=", "+", "-", "@")) or texto[0] in "\t\r\n":
        return "'" + texto
    return texto
