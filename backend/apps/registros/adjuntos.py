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

Los adjuntos de campos de formulario de caso siguen la misma regla con dueño
paciente + caso (`asociar_archivo_a_caso`), sin confirmación de admin. Los ya
cargados antes de esa regla quedan sin dueño.
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
    return _fijar_dueno(
        ruta, actor, institucion_id=ciudadano.institucion_id, ciudadano_id=ciudadano.pk,
        objeto_tipo="Estudio", objeto_id=estudio.pk, proposito=ArchivoClinico.Proposito.ESTUDIO,
        ya_es_suyo=lambda meta: pertenece_al_estudio(meta, estudio), destino="estudio",
        confirmacion_admin=confirmacion_admin,
    )


def asociar_archivo_a_caso(caso, ruta, actor):
    """Fija el dueño del adjunto de un campo de formulario de `caso` (#172, decisión 6).

    Dueño: el paciente del caso y el caso. Solo lo asocia quien lo subió; no hay
    confirmación de admin ni metadata legacy. Si el caso no tiene paciente, el
    archivo queda atado solo al caso (`ciudadano` nulo): no se reutiliza en otro
    caso y su descarga se audita sin paciente. Llamar dentro de una transacción.
    """
    if not ruta:
        return None
    if partes_de_ruta_clinica(ruta) is None:
        raise ErrorAdjunto("El archivo debe subirse al sistema antes de adjuntarlo al caso.")
    return _fijar_dueno(
        ruta, actor, institucion_id=caso.institucion_id, ciudadano_id=caso.ciudadano_id,
        objeto_tipo="Caso", objeto_id=caso.pk, proposito=ArchivoClinico.Proposito.ADJUNTO_CASO,
        ya_es_suyo=lambda meta: (meta.objeto_tipo == "Caso" and meta.objeto_id == caso.pk
                                 and meta.ciudadano_id == caso.ciudadano_id),
        destino="caso",
    )


def _fijar_dueno(ruta, actor, *, institucion_id, ciudadano_id, objeto_tipo, objeto_id, proposito,
                 ya_es_suyo, destino, confirmacion_admin=False):
    with transaction.atomic():
        meta = ArchivoClinico.objects.select_for_update().filter(ruta=ruta).first()
        if meta is None:
            if not confirmacion_admin:
                raise ErrorAdjunto("El archivo no está registrado en el sistema.")
            meta = _metadata_legacy(ruta, institucion_id)
        if meta.institucion_id != institucion_id or meta.proposito == ArchivoClinico.Proposito.CONSENTIMIENTO:
            raise ErrorAdjunto(f"El archivo no corresponde a esta institución o a un {destino}.")
        if meta.asociado_at is not None:
            if ya_es_suyo(meta):
                return meta
            raise ErrorAdjunto("El archivo ya pertenece a otro estudio o caso.")
        # En simulación `subido_por` guarda al actor real: comparar con el mismo.
        real = autor_real(actor) if actor is not None else None
        if not confirmacion_admin and (real is None or meta.subido_por_id != real.pk):
            raise ErrorAdjunto("Solo quien subió el archivo puede asociarlo. Pedí a un administrador que lo confirme."
                               if destino == "estudio" else "Solo quien subió el archivo puede adjuntarlo al caso.")
        meta.ciudadano_id = ciudadano_id
        meta.objeto_tipo = objeto_tipo
        meta.objeto_id = objeto_id
        meta.proposito = proposito
        meta.asociado_por = actor if getattr(actor, "is_authenticated", False) else None
        meta.asociado_at = timezone.now()
        meta.save(update_fields=["ciudadano", "objeto_tipo", "objeto_id", "proposito", "asociado_por", "asociado_at"])
        return meta
