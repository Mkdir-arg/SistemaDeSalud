from django.contrib import admin
from django.core.exceptions import PermissionDenied

from apps.admin_alcance import AlcanceInstitucionalAdmin, AlcanceInstitucionalInline

from .models import Conexion, Flujo, Nodo, VersionFlujo


class DefinicionSoloLecturaAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    """El constructor/API valida y publica; Admin sólo consulta definiciones.

    Incluye borradores: no mantener un segundo escritor del grafo que omita
    validación, congelación de formularios o el orden de locks del constructor.
    """
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return {}

    def save_model(self, request, obj, form, change):
        raise PermissionDenied("Modificá la definición desde el constructor de flujos.")

    def save_formset(self, request, form, formset, change):
        raise PermissionDenied("Modificá la definición desde el constructor de flujos.")

    def delete_model(self, request, obj):
        raise PermissionDenied("Las definiciones se administran desde el constructor de flujos.")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("Las definiciones se administran desde el constructor de flujos.")


class DefinicionSoloLecturaInline(AlcanceInstitucionalInline, admin.TabularInline):
    extra = 0
    can_delete = False

    def get_readonly_fields(self, request, obj=None):
        return tuple(campo.name for campo in self.model._meta.fields)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class VersionFlujoInline(DefinicionSoloLecturaInline):
    model = VersionFlujo


class NodoInline(DefinicionSoloLecturaInline):
    model = Nodo


class ConexionInline(DefinicionSoloLecturaInline):
    model = Conexion
    fk_name = "version"


@admin.register(Flujo)
class FlujoAdmin(DefinicionSoloLecturaAdmin):
    list_display = ("titulo", "institucion", "area", "creado")
    list_filter = ("institucion", "area")
    search_fields = ("titulo",)
    inlines = (VersionFlujoInline,)


@admin.register(VersionFlujo)
class VersionFlujoAdmin(DefinicionSoloLecturaAdmin):
    list_display = ("flujo", "numero", "estado", "autor", "creada")
    list_filter = ("estado",)
    inlines = (NodoInline, ConexionInline)


@admin.register(Nodo)
class NodoAdmin(DefinicionSoloLecturaAdmin):
    list_display = ("titulo", "tipo", "version")
    list_filter = ("tipo",)
    search_fields = ("titulo",)
    filter_horizontal = ("grupos",)
