from django.contrib import admin

from .models import Caso, EventoCaso, ItemFila, ValorCampo


class ValorCampoInline(admin.TabularInline):
    model = ValorCampo
    extra = 0


class EventoCasoInline(admin.TabularInline):
    model = EventoCaso
    extra = 0
    readonly_fields = ("fecha",)


@admin.register(Caso)
class CasoAdmin(admin.ModelAdmin):
    list_display = ("id", "version", "estado", "prioridad", "area_actual", "asignado_a", "creado")
    list_filter = ("estado", "prioridad", "institucion")
    search_fields = ("ciudadano__nombre", "ciudadano__apellido")
    inlines = (ValorCampoInline, EventoCasoInline)


@admin.register(ItemFila)
class ItemFilaAdmin(admin.ModelAdmin):
    list_display = ("turno", "caso", "nodo", "urgente", "orden", "atendido")
    list_filter = ("urgente", "atendido")


@admin.register(EventoCaso)
class EventoCasoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "caso", "autor", "fecha")
    search_fields = ("titulo",)
