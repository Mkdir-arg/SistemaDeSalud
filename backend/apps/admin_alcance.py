"""Alcance institucional del Django Admin (#172, AUD-042).

Un staff que no es superusuario solo ve y modifica, desde el Admin, objetos de
las instituciones donde tiene una pertenencia activa con `config_institucional`,
la misma capacidad que la API exige para administrar una institución. El
superusuario no se limita.

El Admin no usa los viewsets, así que repite su `institucion_path`: la ruta ORM
de cada modelo hasta su institución está en `RUTA_INSTITUCION`. Esa misma tabla
acota los choices de toda FK o M2M hacia un modelo con institución, para que un
POST forjado no pueda colgar un objeto propio de algo ajeno.

Los mixins solo restringen: cada Admin conserva sus propias protecciones
(solo lectura de grafos, formularios congelados, firmas, credenciales).
"""
from django.contrib import admin
from django.contrib.admin.utils import get_fields_from_path
from django.core.exceptions import FieldDoesNotExist

from apps.common import capacidades_por_institucion_de

# Ruta ORM desde cada modelo hasta su institución (como `institucion_path` de
# los viewsets). "id" es la propia institución. Las rutas que pasan por
# `membresias` cuentan solo pertenencias activas (ver `filtrar_por_alcance`).
RUTA_INSTITUCION = {
    "instituciones.institucion": "id",
    "instituciones.area": "institucion",
    "instituciones.subarea": "area__institucion",
    "instituciones.box": "area__institucion",
    "instituciones.grupo": "area__institucion",
    "accounts.usuario": "membresias__institucion",
    "accounts.membresia": "institucion",
    "accounts.legajoprofesional": "usuario__membresias__institucion",
    "casos.caso": "institucion",
    "casos.valorcampo": "caso__institucion",
    "casos.itemfila": "caso__institucion",
    "casos.eventocaso": "caso__institucion",
    "flujos.flujo": "institucion",
    "flujos.versionflujo": "flujo__institucion",
    "flujos.nodo": "version__flujo__institucion",
    "flujos.conexion": "version__flujo__institucion",
    "formularios.formulario": "institucion",
    "formularios.campo": "formulario__institucion",
    "registros.ciudadano": "institucion",
    "registros.historiaclinica": "ciudadano__institucion",
    "registros.entradahistoria": "historia__ciudadano__institucion",
    "registros.estudio": "historia__ciudadano__institucion",
    "registros.receta": "historia__ciudadano__institucion",
    "registros.archivoclinico": "institucion",
    "auditoria.falloauditoria": "institucion",
    "simulacion.cuentareferencia": "institucion",
    "simulacion.sesionsimulacion": "institucion",
    "simulacion.operacionsimulada": "sesion__institucion",
}


def ruta_institucion(modelo):
    return RUTA_INSTITUCION.get(modelo._meta.label_lower)


def instituciones_administradas(request):
    """Ids de las instituciones que el usuario administra; None = sin límite."""
    user = request.user
    if user.is_superuser:
        return None
    if not hasattr(request, "_admin_instituciones"):
        request._admin_instituciones = [
            int(inst) for inst, caps in capacidades_por_institucion_de(user).items()
            if inst != "global" and "config_institucional" in caps
        ]
    return request._admin_instituciones


def filtrar_por_alcance(queryset, ids):
    ruta = ruta_institucion(queryset.model)
    if ruta is None:
        return queryset.none()
    if ruta == "id":
        return queryset.filter(pk__in=ids)
    filtro = {f"{ruta}__in": ids}
    if "membresias__" in ruta:
        # Mismo filter(): la pertenencia activa y la institución son la misma fila.
        filtro[ruta.replace("__institucion", "__activo")] = True
        return queryset.filter(**filtro).distinct()
    return queryset.filter(**filtro)


class _AcotaChoices:
    """Acota las FK/M2M hacia modelos con institución a las administradas."""

    def _acotar(self, formfield, db_field, request):
        ids = instituciones_administradas(request)
        if (ids is not None and formfield is not None and hasattr(formfield, "queryset")
                and ruta_institucion(db_field.related_model) is not None):
            formfield.queryset = filtrar_por_alcance(formfield.queryset, ids)
        return formfield

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        return self._acotar(super().formfield_for_foreignkey(db_field, request, **kwargs), db_field, request)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        return self._acotar(super().formfield_for_manytomany(db_field, request, **kwargs), db_field, request)


class AlcanceInstitucionalAdmin(_AcotaChoices):
    """Mixin de ModelAdmin; va antes de `admin.ModelAdmin` en las bases."""

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ids = instituciones_administradas(request)
        return qs if ids is None else filtrar_por_alcance(qs, ids)

    def en_alcance(self, request, obj):
        ids = instituciones_administradas(request)
        if obj is None or ids is None:
            return True
        return filtrar_por_alcance(self.model._base_manager.filter(pk=obj.pk), ids).exists()

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self.en_alcance(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self.en_alcance(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self.en_alcance(request, obj)

    def has_add_permission(self, request):
        ids = instituciones_administradas(request)
        if ids is not None and (not ids or ruta_institucion(self.model) in (None, "id")):
            # Sin institución que administrar no hay dónde crear; una institución
            # nueva no está dentro de ninguna administrada.
            return False
        return super().has_add_permission(request)

    def get_list_filter(self, request):
        filtros = super().get_list_filter(request)
        if instituciones_administradas(request) is None:
            return filtros
        # El filtro por defecto lista todas las filas del modelo relacionado
        # (p. ej. todas las instituciones); este solo las que usa lo visible.
        return tuple(self._filtro_acotado(f) for f in filtros)

    def _filtro_acotado(self, filtro):
        if not isinstance(filtro, str):
            return filtro
        try:
            campo = get_fields_from_path(self.model, filtro)[-1]
        except (FieldDoesNotExist, AttributeError):
            return filtro
        return (filtro, admin.RelatedOnlyFieldListFilter) if campo.is_relation else filtro


class AlcanceInstitucionalInline(_AcotaChoices):
    """Mixin de inline: filas y choices de las instituciones administradas.

    El padre ya está acotado; esto cubre hijos que pueden pertenecer a otra
    institución, como las membresías de una cuenta compartida.
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ids = instituciones_administradas(request)
        if ids is None or ruta_institucion(qs.model) is None:
            return qs
        return filtrar_por_alcance(qs, ids)
