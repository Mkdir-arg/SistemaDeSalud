from django.contrib import admin

from .models import Conexion, Flujo, Nodo, VersionFlujo


class VersionFlujoInline(admin.TabularInline):
    model = VersionFlujo
    extra = 0


class NodoInline(admin.TabularInline):
    model = Nodo
    extra = 0


class ConexionInline(admin.TabularInline):
    model = Conexion
    extra = 0
    fk_name = "version"


@admin.register(Flujo)
class FlujoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "institucion", "area", "creado")
    list_filter = ("institucion", "area")
    search_fields = ("titulo",)
    inlines = (VersionFlujoInline,)


@admin.register(VersionFlujo)
class VersionFlujoAdmin(admin.ModelAdmin):
    list_display = ("flujo", "numero", "estado", "autor", "creada")
    list_filter = ("estado",)
    inlines = (NodoInline, ConexionInline)


@admin.register(Nodo)
class NodoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "version")
    list_filter = ("tipo",)
    search_fields = ("titulo",)
    filter_horizontal = ("grupos",)
