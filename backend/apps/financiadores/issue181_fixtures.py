"""Adaptadores de fixtures #185; no genera personas ni interpreta referencias."""

from pathlib import Path
import subprocess
import sys
from types import ModuleType


REFERENCIA_PR186 = "0f8400373da23fa0e54ae62b7d8474f1d38281c9"
RAIZ = Path(__file__).resolve().parents[3]


def cargar_referencia(nombre):
    """Ejecuta sólo los dos módulos puros conocidos del SHA publicado, en memoria.

    No usa el árbol compartido, red, checkout, settings ni base de datos. La
    ausencia del objeto Git es un error explícito, nunca una prueba omitida.
    """
    if nombre not in ("ostel_synthetic", "ostel_prevalidacion"):
        raise ValueError("Sólo se admiten el generador y el lector puros de #186")
    ruta = f"backend/apps/financiadores/{nombre}.py"
    fuente = subprocess.run(
        ["git", "show", f"{REFERENCIA_PR186}:{ruta}"], cwd=RAIZ,
        check=True, capture_output=True, encoding="utf-8",
    ).stdout
    clave = f"issue181_referencia_{nombre}"
    modulo = ModuleType(clave)
    modulo.__file__ = f"{REFERENCIA_PR186}:{ruta}"
    anterior = sys.modules.get(clave)
    sys.modules[clave] = modulo  # dataclasses consulta el módulo durante la carga.
    try:
        exec(compile(fuente, modulo.__file__, "exec"), modulo.__dict__)
    finally:
        if anterior is None:
            sys.modules.pop(clave, None)
        else:
            sys.modules[clave] = anterior
    return modulo


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
