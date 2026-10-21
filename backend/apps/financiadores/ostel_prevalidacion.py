"""Lectura técnica OSTEL, sin Django, IO externo ni interpretación de negocio.

La entrada son bytes; los valores numéricos/fechas permanecen como texto XML,
sin convertir seriales, redondear identificadores ni reconstruir ceros perdidos.
`filas` contiene datos privados y NO debe registrarse en logs. `resumen` y las
anomalías sólo contienen conteos, códigos y coordenadas, nunca valores recibidos.
No es una autorización de carga ni un reemplazo del importador existente.

Decisión de producto 21/10/2026 (#180/#185): primera entrega de padrón
administrativo, con aplicación parcial y conflictos de identidad para revisión
humana. Los derechos de cobertura esperan sus reglas de OSTEL. El adaptador
ostel_importacion crea registros con cobertura_habilitada=False; este lector
continúa siendo puro y no autoriza aplicaciones por sí mismo.
"""
from dataclasses import dataclass, field
from io import BytesIO
import posixpath
import re
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_STORED, ZipFile
from zlib import error as ZlibError

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from openpyxl.styles.numbers import BUILTIN_FORMATS
from openpyxl.utils.datetime import ISO_DURATION, ISO_REGEX, from_ISO8601


COLUMNAS = tuple(
    "TIPO,NROAFI,CODEMP,CODPAR,APENOM,TIPODOC,NRODOC,CUIL,SEXO,COD_PLAN,"
    "FEC_NAC,FECING,FECBAJ,FECVTO,MOTIVO,NROBENE,NROPENS,CARNET,NIV,INCAPA,"
    "FACTURA,TABVAL,NUMERO,NROREF,A_CALLE,A_NRO,A_PISO,A_DPTO,A_TEL1,CELU1,"
    "EMAIL1,CODPOS,DESLOCA,CODPROV,CODZON,CODLOCA,CODEST,CODNAC,ESTADO".split(",")
)
HOJAS = ("Hoja1", "afimotook")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MAX_BYTES = 5 * 1024 * 1024
MAX_EXPANDIDO = 25 * 1024 * 1024
MAX_ENTRADAS = 128
# Límites locales independientes del importador de 2.000 filas.
MAX_FILAS = 10000  # posiciones por hoja, además del encabezado
MAX_COLUMNAS = 256  # permite diagnosticar columnas adicionales sin expansión ilimitada
NUMERO_XML = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


class ArchivoOstelInvalido(ValueError):
    """Archivo inseguro, ilegible o fuera de los límites técnicos."""


@dataclass(frozen=True)
class Celda:
    valor: str | None = field(repr=False)
    tipo: str = "n"
    formato: str = field(default="General", repr=False)
    formula: str | None = field(default=None, repr=False)
    atributos_formula: tuple[tuple[str, str], ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class Anomalia:
    codigo: str
    hoja: str | None = None  # sólo nombres reconocidos, nunca nombres arbitrarios
    fila: int | None = None
    columna: int | None = None  # base 1
    fila_original: int | None = None


@dataclass(frozen=True)
class Fila:
    numero: int
    celdas: tuple[Celda, ...] = field(repr=False)


@dataclass(frozen=True)
class Resultado:
    filas: dict[str, tuple[Fila, ...]] = field(repr=False)
    anomalias: tuple[Anomalia, ...]

    @property
    def resumen(self):
        """Resumen sin contenido nominal; duplicados son repeticiones exactas."""
        return {
            "filas_no_vacias": {h: len(f) for h, f in self.filas.items()},
            "duplicados_exactos": sum(a.codigo == "fila_duplicada" for a in self.anomalias),
            "anomalias": len(self.anomalias),
        }


def _paquete(contenido):
    """Mismos controles ZIP/XML que importaciones, sin importar su capa Django."""
    if not isinstance(contenido, bytes):
        raise ArchivoOstelInvalido("Se requieren bytes de un archivo XLSX.")
    if len(contenido) > MAX_BYTES:
        raise ArchivoOstelInvalido("El archivo supera el límite de bytes.")
    with ZipFile(BytesIO(contenido)) as paquete:
        entradas = paquete.infolist()
        nombres = [e.filename for e in entradas]
        if (len(entradas) > MAX_ENTRADAS
                or sum(e.file_size for e in entradas) > MAX_EXPANDIDO
                or len(nombres) != len(set(nombres))):
            raise ArchivoOstelInvalido("El paquete supera los límites o contiene entradas duplicadas.")
        arboles = {}
        for entrada in entradas:
            nombre = entrada.filename.lower()
            if (entrada.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                    or entrada.flag_bits & 1
                    or any(m in nombre for m in ("vbaproject", "externallinks/", "embeddings/"))
                    or "\\" in nombre or nombre.startswith("/")
                    or ".." in nombre.split("/")):
                raise ArchivoOstelInvalido("El paquete contiene componentes no admitidos.")
            if nombre.endswith((".xml", ".rels")):
                raiz = fromstring(paquete.read(entrada), forbid_dtd=True)
                if nombre.endswith(".rels") and any(
                    n.attrib.get("TargetMode", "").lower() == "external" for n in raiz
                ):
                    raise ArchivoOstelInvalido("No se admiten vínculos externos.")
                arboles[entrada.filename] = raiz
        tipos = [n.get("ContentType", "").lower() for n in arboles["[Content_Types].xml"]]
        if (any(any(m in t for m in ("macro", "vba", "oleobject", "activex")) for t in tipos)
                or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml" not in tipos):
            raise ArchivoOstelInvalido("No es un XLSX sin componentes activos.")
        return arboles


def _texto(elemento):
    # Conserva espacios y rich text, sin incluir anotaciones fonéticas.
    return "".join(n.text or "" for n in elemento.findall(f"{NS}t")
                   + elemento.findall(f"{NS}r/{NS}t"))


def _formatos(estilos):
    if estilos is None:
        return ["General"]
    personalizados = {
        int(n.attrib["numFmtId"]): n.attrib["formatCode"]
        for n in estilos.findall(f"{NS}numFmts/{NS}numFmt")
    }
    return [
        personalizados.get(int(n.get("numFmtId", "0")),
                           BUILTIN_FORMATS.get(int(n.get("numFmtId", "0")), ""))
        for n in estilos.findall(f"{NS}cellXfs/{NS}xf")
    ]


def _celda(nodo, cadenas, formatos):
    tipo = nodo.get("t", "n")
    valor = nodo.findtext(f"{NS}v")
    if tipo == "s":
        indice = int(valor)
        if indice < 0:
            raise ValueError
        valor = cadenas[indice]
    elif tipo == "inlineStr":
        texto = nodo.find(f"{NS}is")
        valor = _texto(texto) if texto is not None else ""
    estilo = int(nodo.get("s", "0"))
    if estilo < 0:
        raise ValueError
    formula = nodo.find(f"{NS}f")
    return Celda(valor, tipo, formatos[estilo],
                 None if formula is None else formula.text or "",
                 () if formula is None else tuple(sorted(formula.attrib.items())))


def _fecha_xml_valida(valor):
    """Valida sólo el tipo XLSX con el soporte ISO de openpyxl ya instalado."""
    if not valor or not valor.isascii():
        return False
    if not (ISO_REGEX.fullmatch(valor) or ISO_DURATION.fullmatch(valor)):
        return False
    try:
        return from_ISO8601(valor) is not None
    except (ValueError, OverflowError):
        return False


def _ruta_relacion(relacion):
    destino = relacion.attrib["Target"]
    ruta = posixpath.normpath(posixpath.join("xl", destino)) if not destino.startswith("/") else destino[1:]
    if not ruta.startswith("xl/") or "\\" in ruta:
        raise ArchivoOstelInvalido("Destino de parte inválido.")
    return ruta


def _parte_opcional(arboles, relaciones, tipo):
    partes = [r for r in relaciones.values() if r.get("Type") == f"{REL[1:-1]}/{tipo}"]
    if len(partes) > 1:
        raise ArchivoOstelInvalido("Relaciones de parte duplicadas.")
    return arboles[_ruta_relacion(partes[0])] if partes else None


def _presente(celda):
    # Espacios, 0, False y fórmulas sin resultado NO son filas vacías.
    return celda.valor not in (None, "") or celda.formula is not None


def _leer_hoja(raiz, nombre, cadenas, formatos, anomalias):
    filas, vistas = [], {}
    anterior = 0
    encabezado = False
    for nodo in raiz.findall(f"{NS}sheetData/{NS}row"):
        numero = int(nodo.attrib["r"])
        if numero <= anterior or numero > MAX_FILAS + 1:
            raise ArchivoOstelInvalido("Orden de filas inválido o límite de posiciones excedido.")
        anterior = numero
        celdas = {}
        for elemento in nodo.findall(f"{NS}c"):
            referencia = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)", elemento.attrib["r"])
            if referencia is None or int(referencia[2]) != numero:
                raise ArchivoOstelInvalido("Coordenada de celda inválida.")
            columna = 0
            for letra in referencia[1]:
                columna = columna * 26 + ord(letra) - ord("A") + 1
            if columna > MAX_COLUMNAS or columna in celdas:
                raise ArchivoOstelInvalido("Columna fuera de límite o celda duplicada.")
            try:
                celda = _celda(elemento, cadenas, formatos)
            except (ValueError, TypeError, IndexError):
                raise ArchivoOstelInvalido(
                    f"Referencia de celda inválida: {nombre}, fila {numero}, columna {columna}."
                ) from None
            celdas[columna] = celda
            if celda.formula is not None:
                anomalias.append(Anomalia("formula", nombre, numero, columna))
            if celda.tipo == "e":
                anomalias.append(Anomalia("error_excel", nombre, numero, columna))
            elif celda.tipo not in ("n", "s", "inlineStr", "str", "b", "d"):
                anomalias.append(Anomalia("tipo_no_admitido", nombre, numero, columna))
            elif celda.tipo == "b" and celda.valor not in ("0", "1"):
                anomalias.append(Anomalia("booleano_invalido", nombre, numero, columna))
            elif celda.tipo == "n" and celda.valor not in (None, ""):
                if not NUMERO_XML.fullmatch(celda.valor.strip(" \t\r\n")):
                    anomalias.append(Anomalia("numero_invalido", nombre, numero, columna))
            elif celda.tipo == "d" and celda.valor not in (None, ""):
                if not _fecha_xml_valida(celda.valor):
                    anomalias.append(Anomalia("fecha_xml_invalida", nombre, numero, columna))
            if columna > len(COLUMNAS) and _presente(celda):
                anomalias.append(Anomalia("columna_adicional", nombre, numero, columna))
        if numero == 1:
            encabezado = True
            for columna, esperado in enumerate(COLUMNAS, 1):
                celda = celdas.get(columna, Celda(None))
                if celda.valor != esperado or celda.tipo not in ("s", "inlineStr", "str") or celda.formula is not None:
                    anomalias.append(Anomalia("encabezado_incorrecto", nombre, 1, columna))
            continue
        if not any(_presente(c) for c in celdas.values()):
            continue
        ancho = max(len(COLUMNAS), max(celdas))
        valores = tuple(celdas.get(c, Celda(None)) for c in range(1, ancho + 1))
        filas.append(Fila(numero, valores))
        # Las fórmulas compartidas/matriciales dependen de otras coordenadas;
        # sin evaluarlas no se puede afirmar igualdad de sus filas.
        if any(c.formula is not None and dict(c.atributos_formula).get("t", "normal") != "normal"
               for c in celdas.values()):
            continue
        # No identifica personas: igualdad de posición, valor, tipo, formato y fórmula.
        clave = tuple((c, v) for c, v in sorted(celdas.items()) if _presente(v))
        if clave in vistas:
            anomalias.append(Anomalia("fila_duplicada", nombre, numero, fila_original=vistas[clave]))
        else:
            vistas[clave] = numero
    if not encabezado:
        anomalias.append(Anomalia("encabezado_ausente", nombre, 1))
    return tuple(filas)


def prevalidar_ostel(contenido: bytes) -> Resultado:
    """Lee todas las hojas reconocidas; reporta las demás sin copiar sus nombres.

    Encabezados inválidos no impiden contar y conservar las filas por posición.
    Los tipos se verifican sólo a nivel XLSX, nunca según el campo OSTEL.
    Errores de paquete abortan sin devolver un resultado parcial ni valores.
    """
    try:
        arboles = _paquete(contenido)
        relaciones = {}
        for relacion in arboles["xl/_rels/workbook.xml.rels"]:
            clave = relacion.attrib["Id"]
            if clave in relaciones:
                raise ArchivoOstelInvalido("Relaciones duplicadas.")
            relaciones[clave] = relacion
        compartidas = _parte_opcional(arboles, relaciones, "sharedStrings")
        cadenas = [] if compartidas is None else [_texto(n) for n in compartidas.findall(f"{NS}si")]
        formatos = _formatos(_parte_opcional(arboles, relaciones, "styles"))
        filas, anomalias = {}, []
        for hoja in arboles["xl/workbook.xml"].findall(f"{NS}sheets/{NS}sheet"):
            nombre = hoja.attrib["name"]
            if nombre not in HOJAS:
                anomalias.append(Anomalia("hoja_no_reconocida"))
                continue
            if nombre in filas:
                raise ArchivoOstelInvalido("Hojas reconocidas duplicadas.")
            relacion = relaciones[hoja.attrib[f"{REL}id"]]
            if relacion.get("Type") != f"{REL[1:-1]}/worksheet":
                raise ArchivoOstelInvalido("La hoja no es una hoja de celdas.")
            ruta = _ruta_relacion(relacion)
            filas[nombre] = _leer_hoja(arboles[ruta], nombre, cadenas, formatos, anomalias)
        if not filas:
            anomalias.append(Anomalia("sin_hojas_reconocidas"))
        return Resultado(filas, tuple(anomalias))
    except ArchivoOstelInvalido:
        raise
    except (BadZipFile, DefusedXmlException, ParseError, ZlibError, OSError,
            ValueError, TypeError, KeyError, IndexError, EOFError, RuntimeError, NotImplementedError):
        raise ArchivoOstelInvalido("El archivo no es una planilla XLSX válida y segura.") from None
