"""Adaptadores de fixtures #185; no genera personas ni interpreta referencias."""

def cambiar_columnas(sintetico, fila, **cambios):
    desconocidas = cambios.keys() - set(sintetico.COLUMNAS)
    if desconocidas:
        raise ValueError("Columna fuera del esquema OSTEL")
    valores = dict(zip(sintetico.COLUMNAS, fila))
    valores.update(cambios)
    return tuple(valores[c] for c in sintetico.COLUMNAS)


def referencias_crudas(sintetico):
    """Estímulos de referencias recíprocas/autorreferencia, sin afirmar familia."""
    catalogo = {e.codigo: e for e in sintetico.generar_escenarios()}
    a, b = catalogo["identidad_individual"].lotes[0].filas
    return {
        "referencias_reciprocas": (
            cambiar_columnas(sintetico, a, NROREF="000002"),
            cambiar_columnas(sintetico, b, NROREF="000001"),
        ),
        "autorreferencia": (cambiar_columnas(sintetico, a, NROREF="000001"),),
    }
