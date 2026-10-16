"""Dueño autoritativo de los adjuntos clínicos (#172, AUD-050).

Un archivo clínico pertenece a un único paciente y a un único estudio. La
pertenencia se fija una sola vez, bajo lock del ArchivoClinico, y no se infiere
de la ruta ni del nombre:

- Un archivo recién subido lo asocia solamente quien lo subió (atención del
  estudio o edición del estudio). Así nadie adjunta a otro paciente un archivo
  ajeno cuya ruta conoce.
- Un archivo sin dueño (legacy o subido por otra persona) lo confirma un admin
  con `config_institucional` en la institución, desde la historia. Queda
  registrado quién y cuándo.
- Un archivo ya asociado no se reasigna a otro estudio ni a otro paciente.

El portal solo publica archivos asociados al estudio que los muestra.
"""
import hashlib
import mimetypes

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.common import partes_de_ruta_clinica
from apps.simulacion.contexto import autor_real

from .models import ArchivoClinico


class ErrorAdjunto(Exception):
    pass


def pertenece_al_estudio(meta, estudio):
    return bool(
        meta is not None and meta.asociado_at is not None
        and meta.objeto_tipo == "Estudio" and meta.objeto_id == estudio.pk
        and meta.ciudadano_id == estudio.historia.ciudadano_id
    )


def _metadata_legacy(ruta, institucion_id):
    """Metadata de un archivo legacy que existe en el almacenamiento sin registro."""
    if not default_storage.exists(ruta):
        raise ErrorAdjunto("El archivo no está en el almacenamiento.")
    digest = hashlib.sha256()
    with default_storage.open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(bloque)
    nombre = ruta.rsplit("/", 1)[-1]
    return ArchivoClinico.objects.create(
        institucion_id=institucion_id, ruta=ruta, nombre_original=nombre,
        content_type=mimetypes.guess_type(nombre)[0] or "application/octet-stream",
        tamano=default_storage.size(ruta), sha256=digest.hexdigest(),
        proposito=ArchivoClinico.Proposito.ESTUDIO, subido_por=None,
    )


def asociar_archivo_a_estudio(estudio, ruta, actor, *, confirmacion_admin=False):
    """Fija el dueño del archivo de `estudio`. Llamar dentro de una transacción.

    Repetir la asociación ya vigente es un no-op. Sin ruta no hay nada que asociar.
    """
    if not ruta:
        return None
    if partes_de_ruta_clinica(ruta) is None:
        raise ErrorAdjunto("El archivo debe subirse al sistema antes de asociarlo al estudio.")
    ciudadano = estudio.historia.ciudadano
    with transaction.atomic():
        meta = ArchivoClinico.objects.select_for_update().filter(ruta=ruta).first()
        if meta is None:
            if not confirmacion_admin:
                raise ErrorAdjunto("El archivo no está registrado en el sistema.")
            meta = _metadata_legacy(ruta, ciudadano.institucion_id)
        if meta.institucion_id != ciudadano.institucion_id or meta.proposito == ArchivoClinico.Proposito.CONSENTIMIENTO:
            raise ErrorAdjunto("El archivo no corresponde a esta institución o a un estudio.")
        if meta.asociado_at is not None:
            if pertenece_al_estudio(meta, estudio):
                return meta
            raise ErrorAdjunto("El archivo ya pertenece a otro estudio.")
        # En simulación `subido_por` guarda al actor real: comparar con el mismo.
        real = autor_real(actor) if actor is not None else None
        if not confirmacion_admin and (real is None or meta.subido_por_id != real.pk):
            raise ErrorAdjunto("Solo quien subió el archivo puede asociarlo. Pedí a un administrador que lo confirme.")
        meta.ciudadano_id = ciudadano.pk
        meta.objeto_tipo = "Estudio"
        meta.objeto_id = estudio.pk
        meta.proposito = ArchivoClinico.Proposito.ESTUDIO
        meta.asociado_por = actor if getattr(actor, "is_authenticated", False) else None
        meta.asociado_at = timezone.now()
        meta.save(update_fields=["ciudadano", "objeto_tipo", "objeto_id", "proposito", "asociado_por", "asociado_at"])
        return meta
