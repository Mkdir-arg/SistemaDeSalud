"""Ingreso institucional privado; sin reemplazos ni decisiones médicas automáticas."""
import logging
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage, storages
from django.core.files.storage.handler import InvalidStorageError
from django.db import transaction
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.casos.models import Caso
from apps.common import _sha256_archivo, _tipo_archivo, _validar_archivo_clinico
from apps.simulacion.contexto import autor_real
from . import autorizaciones as a, models as m
from .permisos import plataforma
from .services import auditar


log = logging.getLogger(__name__)
TIPOS = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


class AlmacenamientoNoPrivado(APIException):
    status_code = 503
    default_detail = "La carga de prescripciones requiere almacenamiento privado fuera de media pública."
    default_code = "almacenamiento_no_privado"


def almacenamiento():
    """Nunca recurre a media pública si falta el alias privado."""
    try:
        storage = storages["prescripciones"]
    except InvalidStorageError as error:
        raise AlmacenamientoNoPrivado() from error
    if isinstance(storage, FileSystemStorage):
        ubicacion = Path(storage.location).resolve()
        if ubicacion.is_relative_to(Path(settings.MEDIA_ROOT).resolve()):
            raise AlmacenamientoNoPrivado()
    return storage


def presentar(*, caso, prestacion, usuario, prescripcion, **datos):
    real = autor_real(usuario)
    if plataforma(usuario) or (real != usuario and plataforma(real)):
        raise PermissionDenied("La prescripción debe presentarla la institución prestadora, no plataforma.")
    storage = almacenamiento()
    if _tipo_archivo(prescripcion) not in TIPOS:
        raise ValidationError("La prescripción debe ser un PDF o una imagen JPEG, PNG o WebP.")
    validacion = _validar_archivo_clinico(prescripcion, prescripcion.name)
    if isinstance(validacion, Response):
        raise ValidationError(str(validacion.data["detail"]))
    tipo, extension, tamano = validacion
    huella = _sha256_archivo(prescripcion)
    nueva_ruta = None
    try:
        with transaction.atomic():
            # El mismo lock que solicitar mantiene juntos reintento, expediente y adjunto.
            caso = Caso.objects.select_for_update().get(pk=caso.pk)
            previo = m.EventoAutorizacion.objects.filter(clave=datos["clave"]).exists()
            obj = a.solicitar(caso=caso, prestacion=prestacion, usuario=usuario, **datos)
            adjunto = m.PrescripcionAutorizacion.objects.filter(solicitud=obj).first()
            if previo:
                if adjunto and (adjunto.sha256, adjunto.content_type, adjunto.tamano) == (huella, tipo, tamano):
                    return obj
                raise ValidationError("La clave ya identifica otra presentación. No se modifica la prescripción anterior.")
            nueva_ruta = f"{uuid4().hex}{extension}"
            nueva_ruta = storage.save(nueva_ruta, prescripcion)
            m.PrescripcionAutorizacion.objects.create(solicitud=obj, ruta=nueva_ruta,
                content_type=tipo, extension=extension, tamano=tamano, sha256=huella, creado_por=usuario)
            auditar(usuario, "prescripcion_presentada", obj.pk, financiador=obj.financiador,
                institucion=obj.institucion, motivo="Documento de prescripción presentado")
        return obj
    except Exception:
        if nueva_ruta:
            try:
                storage.delete(nueva_ruta)
            except Exception:
                # No divulgar claves de almacenamiento, documentos ni excepciones del proveedor.
                log.error("No se pudo limpiar el objeto de una presentación fallida de prescripción.")
        raise
