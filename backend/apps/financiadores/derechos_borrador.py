"""Borradores en memoria: no otorgan derechos ni seleccionan reglas operativas."""
from dataclasses import dataclass
from datetime import date


MAX_DIAS_CORRIDOS = (date.max - date.min).days

def _entero_positivo(valor):
    return type(valor) is int and valor > 0


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip()) and valor == valor.strip()


@dataclass(frozen=True)
class BorradorDerechos:
    codigo: str
    version: int
    fuente: str
    financiador_id: int
    regimen: str
    plan_id: int | None
    desde: date
    hasta: date | None = None
    plazo_dias_corridos: int | None = None

    def __post_init__(self):
        if self.plazo_dias_corridos is not None and (type(self.plazo_dias_corridos) is not int or not 0 <= self.plazo_dias_corridos <= MAX_DIAS_CORRIDOS):
            raise ValueError("El plazo opcional requiere días corridos enteros no negativos dentro del rango de fechas.")
        if not all(_texto(v) for v in (self.codigo, self.fuente, self.regimen)):
            raise ValueError("Código, fuente y régimen requieren texto no vacío sin espacios externos.")
        if not _entero_positivo(self.version) or not _entero_positivo(self.financiador_id):
            raise ValueError("Versión y financiador requieren enteros positivos.")
        if self.plan_id is not None and not _entero_positivo(self.plan_id):
            raise ValueError("Plan requiere un entero positivo o None.")
        if type(self.desde) is not date or (self.hasta is not None and type(self.hasta) is not date):
            raise ValueError("Vigencia requiere fechas sin hora.")
        if self.hasta is not None and self.hasta <= self.desde:
            raise ValueError("El fin exclusivo debe ser posterior al inicio.")


@dataclass(frozen=True)
class VistaBorradores:
    """Coincidencias técnicas, nunca una autorización o decisión de derechos."""
    coincidencias: tuple[BorradorDerechos, ...]

    @property
    def conflicto(self):
        return len(self.coincidencias) > 1


def previsualizar_borradores(borradores, *, financiador_id, regimen, plan_id, fecha):
    """Consulta [desde,hasta); no aplica precedencia entre ámbitos/versiones.

    El llamador debe resolver identidad, pertenencia del plan y permisos antes
    de cualquier integración futura. Esta función no consulta padrón ni DB.
    """
    if not _entero_positivo(financiador_id) or not _texto(regimen):
        raise ValueError("Consulta requiere financiador positivo y régimen explícito.")
    if plan_id is not None and not _entero_positivo(plan_id):
        raise ValueError("Consulta requiere plan positivo o None.")
    if type(fecha) is not date:
        raise ValueError("Consulta requiere fecha sin hora.")
    borradores = tuple(borradores)
    if any(type(b) is not BorradorDerechos for b in borradores):
        raise ValueError("Sólo se admiten descriptores de borrador controlados.")
    coincidencias = tuple(sorted(
        (b for b in borradores
         if b.financiador_id == financiador_id and b.regimen == regimen
         and (b.plan_id is None or b.plan_id == plan_id)
         and b.desde <= fecha and (b.hasta is None or fecha < b.hasta)),
        key=lambda b: (b.codigo, b.version, b.plan_id or 0, b.desde,
                       b.hasta or date.max, b.fuente),
    ))
    return VistaBorradores(coincidencias)
