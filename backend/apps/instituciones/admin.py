from django.contrib import admin

from .models import Area, Grupo, Institucion, Subarea


class SubareaInline(admin.TabularInline):
    model = Subarea
    extra = 0


class AreaInline(admin.TabularInline):
    model = Area
    extra = 0


@admin.register(Institucion)
class InstitucionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cuit", "activa", "creada")
    list_filter = ("activa",)
    search_fields = ("nombre", "cuit")
    inlines = (AreaInline,)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "institucion", "activa")
    list_filter = ("institucion", "activa")
    search_fields = ("nombre",)
    inlines = (SubareaInline,)


@admin.register(Subarea)
class SubareaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "area", "activa")
    list_filter = ("area__institucion", "activa")
    search_fields = ("nombre",)


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "area", "activo", "creado")
    list_filter = ("area__institucion", "activo")
    search_fields = ("nombre",)
    filter_horizontal = ("miembros",)
