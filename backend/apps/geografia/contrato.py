"""Validaciones puras del catálogo; nunca normalizan identidades por similitud."""
import hashlib
import json
import unicodedata

NIVELES = ("provincia", "partido", "localidad")
SEMANA = 7 * 24 * 60 * 60


def nombre_valido(valor):
    if not isinstance(valor, str):
        raise ValueError("El nombre debe ser texto.")
    texto = " ".join(unicodedata.normalize("NFC", valor).strip().split())
    if not texto or len(texto) > 100 or any(unicodedata.category(c).startswith("C") for c in texto):
        raise ValueError("Informá un nombre de lugar de hasta 100 caracteres, sin caracteres de control.")
    return texto


def clave_manual(tipo, nombre, institucion_id, financiador_id, provincia_id, partido_id):
    if tipo not in NIVELES or bool(institucion_id) == bool(financiador_id):
        raise ValueError("El lugar manual requiere una organización y un tipo válido.")
    datos = [tipo, nombre_valido(nombre).casefold(), institucion_id, financiador_id, provincia_id, partido_id]
    return hashlib.sha256(json.dumps(datos, ensure_ascii=False).encode()).hexdigest()


def id_valido(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and 0 < valor <= 2**63 - 1


def validar_catalogo(colecciones):
    """Valida una descarga completa antes de publicar nada. IDs siempre textuales."""
    if set(colecciones) != set(NIVELES):
        raise ValueError("Faltan colecciones territoriales.")
    salida, vistos = [], {}
    for tipo in NIVELES:
        filas = colecciones[tipo]
        if not isinstance(filas, list) or not filas:
            raise ValueError("El catálogo recibido está vacío o incompleto.")
        vistos[tipo] = set()
        for fila in filas:
            if not isinstance(fila, dict):
                raise ValueError("Entidad territorial inválida.")
            codigo = fila.get("id")
            if not isinstance(codigo, str) or not codigo or len(codigo) > 32 or not codigo.isascii() or not codigo.isdigit():
                raise ValueError("Código territorial inválido; debe ser texto numérico.")
            if codigo in vistos[tipo]:
                raise ValueError("La descarga contiene códigos duplicados.")
            vistos[tipo].add(codigo)
            provincia = fila.get("provincia") or {}
            partido = fila.get("departamento") or {}
            if not isinstance(provincia, dict) or not isinstance(partido, dict):
                raise ValueError("Relación territorial inválida.")
            prov = provincia.get("id") if tipo != "provincia" else None
            dep = partido.get("id") if tipo == "localidad" else None
            if tipo != "provincia" and prov not in vistos["provincia"]:
                raise ValueError("La entidad no pertenece a una provincia descargada.")
            if dep and dep not in vistos["partido"]:
                raise ValueError("La localidad referencia un departamento no descargado.")
            salida.append(dict(tipo=tipo, codigo=codigo, nombre=nombre_valido(fila.get("nombre")), provincia=prov, partido=dep))
    provincias_departamento = {f["codigo"]: f["provincia"] for f in salida if f["tipo"] == "partido"}
    if any(f["partido"] and provincias_departamento[f["partido"]] != f["provincia"] for f in salida):
        raise ValueError("La localidad y el departamento pertenecen a provincias distintas.")
    return salida
