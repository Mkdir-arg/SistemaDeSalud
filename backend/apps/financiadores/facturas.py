"""Registros documentales del financiador; no generan deuda ni comprobantes fiscales."""
import hashlib
import json
import unicodedata
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from rest_framework.exceptions import ValidationError

from apps.common import ARCHIVO_CLINICO_MAX_BYTES, _sha256_archivo, _validar_archivo_clinico


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto).strip().lower())
    return " ".join("".join(c for c in texto if not unicodedata.combining(c)).split())


def clave_duplicado(datos):
    contraparte = (f"convenio:{datos['convenio'].pk}" if datos.get("convenio") else
                   f"afiliado:{datos['afiliado'].pk}" if datos.get("afiliado") else
                   f"{datos['contraparte_tipo']}:{normalizar(datos['contraparte_nombre'])}:{normalizar(datos.get('contraparte_identificador', ''))}")
    partes = [datos["direccion"], contraparte, datos["tipo"], datos.get("letra", ""), datos["numero"].strip()]
    return hashlib.sha256(json.dumps(partes, ensure_ascii=False).encode()).hexdigest()


def almacenamiento_privado():
    ruta = Path(settings.SALUD_FACTURAS_ADJUNTOS_DIR).resolve()
    media = Path(settings.MEDIA_ROOT).resolve()
    if ruta == media or media in ruta.parents:
        raise ValidationError("El directorio de adjuntos de facturas debe estar fuera de MEDIA_ROOT.")
    return FileSystemStorage(location=ruta)


def validar_adjunto(archivo):
    if not settings.SALUD_FACTURAS_ADJUNTOS:
        raise ValidationError("Los adjuntos de facturas no están disponibles en este entorno.")
    almacenamiento = almacenamiento_privado()
    nombre = Path(archivo.name).name
    if archivo.size > ARCHIVO_CLINICO_MAX_BYTES:
        raise ValidationError("El archivo supera el máximo permitido de 10 MB.")
    valido = _validar_archivo_clinico(archivo, nombre)
    if not isinstance(valido, tuple):
        raise ValidationError(valido.data["detail"])
    content_type, ext, tamano = valido
    if content_type not in {"application/pdf", "image/jpeg", "image/png", "image/webp"}:
        raise ValidationError("Adjuntá un PDF o una imagen válida.")
    return almacenamiento, nombre, content_type, ext, tamano, _sha256_archivo(archivo)
