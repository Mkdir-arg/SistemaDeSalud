from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.forms.models import BaseInlineFormSet

from apps.simulacion.contexto import usuario_real

from .models import ArchivoClinico, Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta
from .revision_borrador import REVISION_OBSOLETA, REVISION_REQUERIDA, coincide_revision, revision_de_entrada


class EntradaHistoriaAdminForm(forms.ModelForm):
    revision_esperada = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = EntradaHistoria
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["revision_esperada"].initial = revision_de_entrada(self.instance)


class EntradaHistoriaFormSet(BaseInlineFormSet):
    usuario_actor_id = None

    def clean(self):
        super().clean()
        if any(self.errors) or not self.instance.pk:
            return
        cambiadas = {form.instance.pk for form in self.forms
                     if form.instance.pk and form.has_changed()}
        if not cambiadas:
            return
        # ModelAdmin.changeform_view mantiene esta transacción hasta guardar
        # padre e inlines. El atomic propio permite tomar el lock explícitamente.
        with transaction.atomic():
            HistoriaClinica.objects.select_for_update().get(pk=self.instance.pk)
            entradas = EntradaHistoria.objects.select_for_update().filter(
                historia=self.instance, pk__in=cambiadas,
            ).order_by("pk")
            for entrada in entradas:
                if entrada.firmada:
                    raise ValidationError(
                        "Esta atención está firmada y no se puede modificar ni borrar. Registrá una atención nueva."
                    )
                if entrada.autor_id is None or entrada.autor_id != self.usuario_actor_id:
                    raise ValidationError("Solo el autor puede modificar o borrar este borrador. Registrá una atención nueva.")
                formulario = next(form for form in self.forms if form.instance.pk == entrada.pk)
                esperada = formulario.cleaned_data.get("revision_esperada")
                if not esperada:
                    raise ValidationError(REVISION_REQUERIDA)
                if not coincide_revision(entrada, esperada):
                    raise ValidationError(REVISION_OBSOLETA)


class EntradaHistoriaInline(admin.TabularInline):
    model = EntradaHistoria
    form = EntradaHistoriaAdminForm
    formset = EntradaHistoriaFormSet
    extra = 0
    readonly_fields = ("fecha", "autor", "firmada", "matricula", "firmada_at", "sello", "sello_previo", "sello_version")

    def has_add_permission(self, request, obj=None):
        return False

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        actor_id = usuario_real(request).pk

        class FormSetDelAutor(formset):
            usuario_actor_id = actor_id

        return FormSetDelAutor


class ConservaEntradasFirmadasAdmin(admin.ModelAdmin):
    """La eliminación del padre tampoco permite borrar entradas firmadas."""

    def _historias(self, obj):
        if isinstance(obj, HistoriaClinica):
            return HistoriaClinica.objects.filter(pk=obj.pk)
        return HistoriaClinica.objects.filter(ciudadano=obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and EntradaHistoria.objects.filter(historia__in=self._historias(obj)).exclude(
            firmada=False, autor_id=usuario_real(request).pk,
        ).exists():
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        acciones = super().get_actions(request)
        # La acción estándar usa queryset.delete y saltea delete_model.
        acciones.pop("delete_selected", None)
        return acciones

    def delete_model(self, request, obj):
        with transaction.atomic():
            if isinstance(obj, Ciudadano):
                Ciudadano.objects.select_for_update().get(pk=obj.pk)
            historias = list(self._historias(obj).select_for_update().order_by("pk"))
            entradas = EntradaHistoria.objects.select_for_update().filter(
                historia__in=historias,
            ).order_by("pk")
            actor_id = usuario_real(request).pk
            if any(entrada.firmada or entrada.autor_id != actor_id for entrada in entradas):
                raise PermissionDenied("No se puede borrar una historia con atenciones firmadas o borradores ajenos/sin autor.")
            super().delete_model(request, obj)


class EstudioInline(admin.TabularInline):
    model = Estudio
    extra = 0


@admin.register(Ciudadano)
class CiudadanoAdmin(ConservaEntradasFirmadasAdmin):
    list_display = ("nombre", "apellido", "documento", "obra_social", "institucion")
    list_filter = ("institucion", "obra_social")
    search_fields = ("nombre", "apellido", "documento", "codigo")


@admin.register(HistoriaClinica)
class HistoriaClinicaAdmin(ConservaEntradasFirmadasAdmin):
    list_display = ("ciudadano", "condiciones", "alergias", "creada")
    search_fields = ("ciudadano__nombre", "ciudadano__apellido")
    inlines = (EntradaHistoriaInline, EstudioInline)

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        return (*campos, "ciudadano") if obj is not None else campos


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ("tipo", "historia", "resultado", "fecha", "autor")
    list_filter = ("resultado",)


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ("historia", "activa", "autor", "fecha")
    list_filter = ("activa",)


@admin.register(ArchivoClinico)
class ArchivoClinicoAdmin(admin.ModelAdmin):
    list_display = ("nombre_original", "institucion", "content_type", "tamano", "proposito", "creado")
    list_filter = ("institucion", "content_type", "proposito")
    search_fields = ("nombre_original", "ruta", "sha256")
    # La pertenencia la fija `registros.adjuntos` (#172, AUD-050); el Admin no la
    # reasigna ni la crea por fuera de esa regla.
    readonly_fields = ("ruta", "sha256", "tamano", "content_type", "creado", "subido_por", "institucion",
                       "proposito", "objeto_tipo", "objeto_id", "ciudadano", "asociado_por", "asociado_at")
