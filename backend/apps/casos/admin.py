from django.contrib import admin
from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import NotFound

from apps.admin_alcance import AlcanceInstitucionalAdmin, AlcanceInstitucionalInline
from apps.formularios.integridad import bloquear_formularios, congelar_formularios
from apps.formularios.models import Campo

from .models import Caso, EventoCaso, ItemFila, ValorCampo


class ValorCampoInline(AlcanceInstitucionalInline, admin.TabularInline):
    model = ValorCampo
    extra = 0


class EventoCasoInline(AlcanceInstitucionalInline, admin.TabularInline):
    model = EventoCaso
    extra = 0
    readonly_fields = ("fecha",)


@admin.register(Caso)
class CasoAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("id", "version", "estado", "prioridad", "area_actual", "asignado_a", "creado")
    list_filter = ("estado", "prioridad", "institucion")
    search_fields = ("ciudadano__nombre", "ciudadano__apellido")
    inlines = (ValorCampoInline, EventoCasoInline)

    def save_formset(self, request, form, formset, change):
        if formset.model is not ValorCampo:
            return super().save_formset(request, form, formset, change)
        campos = {f.cleaned_data["campo"].pk: f.cleaned_data["campo"].formulario_id
                  for f in formset.forms if f.has_changed() and f.cleaned_data.get("campo")
                  and not f.cleaned_data.get("DELETE")}
        formularios = set(campos.values())
        with transaction.atomic():
            try:
                bloquear_formularios(formularios)
            except NotFound as error:
                raise Http404(str(error.detail)) from None
            actuales = dict(Campo.objects.filter(pk__in=campos).values_list("pk", "formulario_id"))
            if actuales != campos:
                raise Http404("Un campo del formulario ya no existe. Recargá antes de guardar.")
            congelar_formularios(formularios)
            return super().save_formset(request, form, formset, change)


@admin.register(ItemFila)
class ItemFilaAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("ticket", "caso", "nodo", "urgente", "orden", "atendido")
    list_filter = ("urgente", "atendido")


@admin.register(EventoCaso)
class EventoCasoAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("titulo", "caso", "autor", "fecha")
    search_fields = ("titulo",)
