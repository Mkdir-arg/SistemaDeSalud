"""Simulación temporal explicable; nunca decide ni modifica derechos."""
from dataclasses import dataclass
from datetime import date, timedelta
from .derechos_borrador import BorradorDerechos, previsualizar_borradores, MAX_DIAS_CORRIDOS


@dataclass(frozen=True)
class SimulacionPlazo:
    regla: BorradorDerechos
    dias_corridos: int
    financiador_id: int
    regimen: str
    plan_id: int | None
    fecha: date
    referencia: date | None
    evidencia: str | None
    estado: str
    limite: date | None = None
    relacion: str | None = None


def simular_plazo(regla, *, dias_corridos, financiador_id, regimen, plan_id, fecha,
                  referencia=None, evidencia=None):
    """Calcula referencia + días, sin elegir qué ocurre antes/en/después."""
    if type(dias_corridos) is not int or not 0 <= dias_corridos <= MAX_DIAS_CORRIDOS:
        raise ValueError("El plazo requiere días corridos enteros no negativos dentro del rango de fechas.")
    if referencia is not None and type(referencia) is not date:
        raise ValueError("La referencia requiere una fecha sin hora o None.")
    if evidencia is not None and (not isinstance(evidencia, str) or not evidencia.strip() or evidencia != evidencia.strip()):
        raise ValueError("La evidencia requiere una referencia textual no vacía sin espacios externos.")

    def resultado(estado, limite=None, relacion=None):
        return SimulacionPlazo(regla, dias_corridos, financiador_id, regimen, plan_id,
                               fecha, referencia, evidencia, estado, limite, relacion)
    vista = previsualizar_borradores((regla,), financiador_id=financiador_id,
                                    regimen=regimen, plan_id=plan_id, fecha=fecha)
    if not vista.coincidencias:
        return resultado("sin_coincidencia")
    if referencia is None or evidencia is None:
        return resultado("requiere_evidencia")
    try:
        limite = referencia + timedelta(days=dias_corridos)
    except OverflowError as exc:
        raise ValueError("El límite calculado excede el rango de fechas soportado.") from exc
    relacion = "antes" if fecha < limite else "despues" if fecha > limite else "en"
    return resultado("calculado", limite, relacion)
