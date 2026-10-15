from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import BaseInlineFormSet
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound

from .integridad import FormularioCongelado, bloquear_formularios, esta_congelado, exigir_editable
from .models import Campo, Formulario


def _bloquear_admin_formularios(ids):
    try:
        return bloquear_formularios(ids)
    except NotFound as error:
        raise Http404(str(error.detail)) from None


def _datos_definicion(objeto):
    return {campo.attname: getattr(objeto, campo.attname) for campo in objeto._meta.concrete_fields
            if campo.name not in ("id", "creado", "congelado_at")}


def _exigir_admin_editable(formulario, **kwargs):
    try:
        exigir_editable(formulario, **kwargs)
    except FormularioCongelado as error:
        raise PermissionDenied(str(error.detail)) from None


class CamposDefinicionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors) or not self.instance.pk:
            return
        cambios = [form for form in self.forms if form.has_changed()]
        if not cambios:
            return
        # El POST de ModelAdmin.changeform_view mantiene la transacción hasta
        # guardar padre e inlines: los locks de clean no se liberan entre ambos.
        with transaction.atomic():
            formulario = _bloquear_admin_formularios([self.instance.pk])[self.instance.pk]
            existentes = {campo.pk: campo for campo in Campo.objects.order_by("pk").select_for_update()
                          .filter(formulario=formulario)}
            try:
                for form in cambios:
                    campo = existentes.get(form.instance.pk)
                    if form.instance.pk and campo is None:
                        raise ValidationError("El campo ya no existe. Recargá la definición.")
                    if campo is None or form.cleaned_data.get("DELETE"):
                        exigir_editable(formulario)
                    else:
                        exigir_editable(formulario, instancia=campo, cambios=_datos_definicion(form.instance))
            except FormularioCongelado as error:
                raise ValidationError(str(error.detail)) from None


class CampoInline(admin.TabularInline):
    model = Campo
    formset = CamposDefinicionFormSet
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return tuple(campo.name for campo in Campo._meta.fields) if obj and esta_congelado(obj) else ()

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and not (obj and esta_congelado(obj))

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and esta_congelado(obj))


@admin.register(Formulario)
class FormularioAdmin(admin.ModelAdmin):
    list_display = ("titulo", "institucion", "area", "congelado_at")
    list_filter = ("institucion", "area")
    search_fields = ("titulo",)
    inlines = (CampoInline,)
    readonly_fields = ("congelado_at",)

    def get_readonly_fields(self, request, obj=None):
        return tuple(campo.name for campo in Formulario._meta.fields) if obj and esta_congelado(obj) else self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and esta_congelado(obj))

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                vigente = _bloquear_admin_formularios([obj.pk])[obj.pk]
                _exigir_admin_editable(vigente, cambios=_datos_definicion(obj))
                # Un formulario abierto antes de publicar no puede restaurar NULL.
                obj.congelado_at = vigente.congelado_at
            else:
                obj.congelado_at = None
            super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        with transaction.atomic():
            vigente = _bloquear_admin_formularios([obj.pk])[obj.pk]
            _exigir_admin_editable(vigente)
            super().delete_model(request, vigente)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            formularios = _bloquear_admin_formularios(queryset.values_list("pk", flat=True))
            for formulario in formularios.values():
                _exigir_admin_editable(formulario)
            Formulario.objects.filter(pk__in=formularios).delete()


@admin.register(Campo)
class CampoAdmin(admin.ModelAdmin):
    list_display = ("label", "formulario", "tipo", "requerido", "origen")
    list_filter = ("tipo", "requerido", "origen")
    search_fields = ("label",)

    def get_readonly_fields(self, request, obj=None):
        if obj and esta_congelado(obj.formulario):
            return tuple(campo.name for campo in Campo._meta.fields)
        return ("formulario",) if obj else ()

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and esta_congelado(obj.formulario))

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                padre_id = get_object_or_404(Campo.objects.only("formulario_id"), pk=obj.pk).formulario_id
                if obj.formulario_id != padre_id:
                    raise PermissionDenied("Un campo existente no cambia de formulario. Duplicá la definición.")
            else:
                padre_id = obj.formulario_id
            formulario = _bloquear_admin_formularios([padre_id])[padre_id]
            if change:
                vigente = get_object_or_404(Campo.objects.order_by("pk").select_for_update(), pk=obj.pk)
                _exigir_admin_editable(formulario, instancia=vigente, cambios=_datos_definicion(obj))
            else:
                _exigir_admin_editable(formulario)
            super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        with transaction.atomic():
            padre_id = get_object_or_404(Campo.objects.only("formulario_id"), pk=obj.pk).formulario_id
            formulario = _bloquear_admin_formularios([padre_id])[padre_id]
            vigente = get_object_or_404(Campo.objects.order_by("pk").select_for_update(), pk=obj.pk)
            _exigir_admin_editable(formulario)
            super().delete_model(request, vigente)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            seleccion = list(queryset.values_list("pk", "formulario_id"))
            formularios = _bloquear_admin_formularios(padre for _, padre in seleccion)
            ids = [pk for pk, _ in seleccion]
            list(Campo.objects.order_by("pk").select_for_update().filter(pk__in=ids))
            for formulario in formularios.values():
                _exigir_admin_editable(formulario)
            Campo.objects.filter(pk__in=ids).delete()
