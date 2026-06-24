from django.contrib import admin

from .models import Campo, Formulario


class CampoInline(admin.TabularInline):
    model = Campo
    extra = 0


@admin.register(Formulario)
class FormularioAdmin(admin.ModelAdmin):
    list_display = ("titulo", "institucion", "area")
    list_filter = ("institucion", "area")
    search_fields = ("titulo",)
    inlines = (CampoInline,)


@admin.register(Campo)
class CampoAdmin(admin.ModelAdmin):
    list_display = ("label", "formulario", "tipo", "requerido", "origen")
    list_filter = ("tipo", "requerido", "origen")
    search_fields = ("label",)
