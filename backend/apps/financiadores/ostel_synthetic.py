"""Fixtures OSTEL creadas desde cero; no validan ni aplican reglas del padrón.

Determinismo de valores, tipos y orden (no del ZIP XLSX). Los códigos son
estímulos de prueba, no un diccionario homologado por OSTEL.
"""

from dataclasses import dataclass
from datetime import date
from io import BytesIO


COLUMNAS = tuple(
    "TIPO,NROAFI,CODEMP,CODPAR,APENOM,TIPODOC,NRODOC,CUIL,SEXO,COD_PLAN,"
    "FEC_NAC,FECING,FECBAJ,FECVTO,MOTIVO,NROBENE,NROPENS,CARNET,NIV,INCAPA,"
    "FACTURA,TABVAL,NUMERO,NROREF,A_CALLE,A_NRO,A_PISO,A_DPTO,A_TEL1,CELU1,"
    "EMAIL1,CODPOS,DESLOCA,CODPROV,CODZON,CODLOCA,CODEST,CODNAC,ESTADO"
    .split(",")
)
HOJAS = ("Hoja1", "afimotook")


@dataclass(frozen=True)
class Lote:
    nombre: str
    filas: tuple[tuple, ...]


@dataclass(frozen=True)
class Escenario:
    codigo: str
    lotes: tuple[Lote, ...]


def _cuil(documento):
    """Checksum módulo 11; no acredita existencia, asignación ni identidad."""
    for prefijo in ("20", "27", "23"):
        base = prefijo + documento
        resto = sum(int(n) * p for n, p in zip(base, (5, 4, 3, 2, 7, 6, 5, 4, 3, 2))) % 11
        digito = (11 - resto) % 11
        if digito != 10:
            return base + str(digito)
    raise ValueError("No se pudo construir el identificador ficticio")


def _persona(indice, **cambios):
    documento = str(99018500 + indice)
    valores = dict.fromkeys(COLUMNAS)
    valores.update(
        TIPO="SINTETICO", NROAFI=f"FIC185-{indice:04d}-AAA",
        CODEMP="EMP-FICTICIA", CODPAR="00",
        APENOM=f"PERSONA FICTICIA OSTEL {indice:04d}", TIPODOC="DNI",
        NRODOC=documento, CUIL=_cuil(documento), SEXO="X",
        COD_PLAN="PLAN-FICTICIO", FEC_NAC=date(1990, 1, 1),
        FECING=date(2026, 1, 1), FECVTO=date(2026, 12, 31),
        A_CALLE="CALLE FICTICIA", A_NRO="001", EMAIL1=f"ostel-{indice}@example.invalid",
        CODPOS="0000", DESLOCA="LOCALIDAD FICTICIA", CODPROV="00",
        CODZON="00", CODLOCA="000", CODEST="00", CODNAC="00",
        ESTADO="SINTETICO",
    )
    desconocidas = cambios.keys() - valores.keys()
    if desconocidas:
        raise ValueError(f"Columnas desconocidas: {sorted(desconocidas)}")
    valores.update(cambios)
    return tuple(valores[c] for c in COLUMNAS)


def generar_escenarios():
    """Devuelve un catálogo nuevo, inmutable y sin aleatoriedad ni reloj.

    Cada escenario es independiente. Sus lotes se recorren en el orden dado;
    no se deben concatenar los escenarios como si fueran movimientos reales.
    """
    def caso(codigo, *filas):
        return Escenario(codigo, (Lote("entrada", tuple(filas)),))

    referencia = "FIC185-0001-AAA"
    baja = _persona(1, FECBAJ=date(2026, 6, 30), MOTIVO="BAJA-FICTICIA")
    cuil = _cuil("99018501")
    invalido = cuil[:-1] + str((int(cuil[-1]) + 1) % 10)
    cuil_parcial = _cuil("99018502")
    invalido_parcial = cuil_parcial[:-1] + str((int(cuil_parcial[-1]) + 1) % 10)
    return (
        caso("base", _persona(1)),
        caso("numero_compartido", _persona(1), _persona(2, NROAFI=referencia)),
        caso("referencia_presente", _persona(1),
             _persona(2, NROREF=referencia, CODPAR="01")),
        caso("referencia_ausente", _persona(2, NROREF=referencia, CODPAR="01")),
        caso("referencia_no_aaa", _persona(1, NROAFI="FIC185-0001-ZZZ"),
             _persona(2, NROREF="FIC185-0001-ZZZ", CODPAR="01")),
        caso("cuil_invalido", _persona(1, CUIL=invalido)),
        caso("documento_discordante", _persona(1, CUIL=_cuil("99018502"))),
        caso("filas_vacias", (None,) * len(COLUMNAS), _persona(1),
             (None,) * len(COLUMNAS), _persona(2), (None,) * len(COLUMNAS)),
        caso("tipos_mixtos", _persona(1, NROAFI="000185", NRODOC="099018501"),
             _persona(2, NROAFI=185, NRODOC=99018502, FECING="2026-01-01"),
             _persona(3, NROAFI=185.5, NRODOC=True, FECING="no-es-fecha")),
        Escenario("baja_repetida", (Lote("01_baja", (baja,)), Lote("02_repeticion", (baja,)))),
        Escenario("posible_reingreso", (
            Lote("01_baja", (baja,)),
            Lote("02_posterior", (_persona(1, FECING=date(2026, 8, 1)),)),
        )),
        caso("vencimiento_lejano", _persona(1, FECVTO=date(2099, 12, 31))),
        caso("baja_anterior_ingreso", _persona(1, FECBAJ=date(2025, 12, 31))),
        caso("lote_parcial", _persona(1), _persona(2, CUIL=invalido_parcial),
             _persona(3, FECBAJ=date(2025, 12, 31))),
    )


def generar_xlsx(lote, *, hoja="Hoja1"):
    """Devuelve bytes para uso temporal, sin escribir archivos ni importar Django."""
    if hoja not in HOJAS:
        raise ValueError(f"Hoja no soportada: {hoja}")
    if any(len(fila) != len(COLUMNAS) for fila in lote.filas):
        raise ValueError("Cada fila debe tener exactamente 39 columnas")

    from openpyxl import Workbook

    libro = Workbook()
    try:
        tabla = libro.active
        tabla.title = hoja
        tabla.append(COLUMNAS)
        for fila in lote.filas:
            tabla.append(fila)
            if all(valor is None for valor in fila):
                # Excel omite celdas vacías sin estilo, perdiendo filas finales.
                # Una celda con formato conserva la posición sin inventar datos.
                tabla.cell(tabla.max_row, len(COLUMNAS)).number_format = "@"
        # El texto es literal, incluso si un futuro estímulo comienza con '='.
        for fila in tabla:
            for celda in fila:
                if isinstance(celda.value, str):
                    celda.data_type = "s"
        salida = BytesIO()
        libro.save(salida)
        return salida.getvalue()
    finally:
        libro.close()


def exportar_temporales():
    """Prepara los 16 lotes en ambas hojas en una carpeta temporal nueva.

    La carpeta permanece disponible para inspección manual; quien llama debe
    eliminarla cuando termine. No recibe fuentes ni sobrescribe datos existentes.
    """
    from pathlib import Path
    from tempfile import mkdtemp

    destino = Path(mkdtemp(prefix="ostel-185-ficticio-"))
    for hoja in HOJAS:
        for escenario in generar_escenarios():
            carpeta = destino / hoja / escenario.codigo
            carpeta.mkdir(parents=True)
            for lote in escenario.lotes:
                with (carpeta / f"{lote.nombre}.xlsx").open("xb") as archivo:
                    archivo.write(generar_xlsx(lote, hoja=hoja))
    return destino


if __name__ == "__main__":
    print(exportar_temporales())
