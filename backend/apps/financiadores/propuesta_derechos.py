"""Comparación en memoria de propuestas; no aprueba ni activa derechos."""
from dataclasses import dataclass

from .derechos_borrador import BorradorDerechos, VistaBorradores, previsualizar_borradores


@dataclass(frozen=True)
class ComparacionBorradores:
    nuevas: tuple[BorradorDerechos, ...]
    antes: VistaBorradores
    despues: VistaBorradores


def _clave(borrador):
    return (borrador.financiador_id, borrador.regimen,
            borrador.plan_id, borrador.codigo, borrador.version)


def comparar_borradores(historial, propuesta, *, financiador_id, regimen, plan_id, fecha):
    """Compara instantáneas explícitas; ninguna constituye un registro persistido."""
    historial, propuesta = tuple(historial), tuple(propuesta)
    contexto = dict(financiador_id=financiador_id, regimen=regimen, plan_id=plan_id, fecha=fecha)
    antes = previsualizar_borradores(historial, **contexto)
    despues = previsualizar_borradores(propuesta, **contexto)
    if any(b.financiador_id != financiador_id for b in (*historial, *propuesta)):
        raise ValueError("Historial y propuesta deben pertenecer al financiador indicado.")
    anteriores = {_clave(b): b for b in historial}
    propuestas = {_clave(b): b for b in propuesta}
    if len(anteriores) != len(historial) or len(propuestas) != len(propuesta):
        raise ValueError("Cada ámbito, código y versión debe ser único en la instantánea.")
    if any(propuestas.get(clave) != b for clave, b in anteriores.items()):
        raise ValueError("La propuesta no puede borrar ni redefinir versiones anteriores.")
    claves_previas = set(anteriores)
    nuevas = tuple(b for b in propuesta if _clave(b) not in claves_previas)
    maximas = {}
    for clave in anteriores:
        maximas[clave[:-1]] = max(maximas.get(clave[:-1], 0), clave[-1])
    if any(b.version <= maximas.get(_clave(b)[:-1], 0) for b in nuevas):
        raise ValueError("Las versiones nuevas deben superar el máximo previo de su ámbito y código.")
    nuevas = tuple(sorted(nuevas, key=lambda b: (b.regimen, b.plan_id or 0, b.codigo, b.version)))
    return ComparacionBorradores(nuevas, antes, despues)
