from django.contrib import admin

from .models import Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta


class EntradaHistoriaInline(admin.TabularInline):
    model = EntradaHistoria
    extra = 0
    readonly_fields = ("fecha",)


class EstudioInline(admin.TabularInline):
    model = Estudio
    extra = 0


@admin.register(Ciudadano)
class CiudadanoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellido", "documento", "obra_social", "institucion")
    list_filter = ("institucion", "obra_social")
    search_fields = ("nombre", "apellido", "documento", "codigo")


@admin.register(HistoriaClinica)
class HistoriaClinicaAdmin(admin.ModelAdmin):
    list_display = ("ciudadano", "condiciones", "alergias", "creada")
    search_fields = ("ciudadano__nombre", "ciudadano__apellido")
    inlines = (EntradaHistoriaInline, EstudioInline)


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ("tipo", "historia", "resultado", "fecha", "autor")
    list_filter = ("resultado",)


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ("historia", "activa", "autor", "fecha")
    list_filter = ("activa",)
