from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.admin_alcance import AlcanceInstitucionalAdmin, AlcanceInstitucionalInline

from .models import Area, Box, Grupo, Institucion, Subarea


class SubareaInline(AlcanceInstitucionalInline, admin.TabularInline):
    model = Subarea
    extra = 0


class AreaInline(AlcanceInstitucionalInline, admin.TabularInline):
    model = Area
    extra = 0
    can_delete = False


@admin.register(Institucion)
class InstitucionAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("nombre", "cuit", "activa", "creada")
    list_filter = ("activa",)
    search_fields = ("nombre", "cuit")
    inlines = (AreaInline,)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        acciones = super().get_actions(request)
        acciones.pop("delete_selected", None)
        return acciones

    def delete_model(self, request, obj):
        raise PermissionDenied("Las instituciones no se eliminan. Realizá la baja desde su estado.")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("Las instituciones no se eliminan. Realizá la baja desde su estado.")


@admin.register(Area)
class AreaAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("nombre", "institucion", "activa")
    list_filter = ("institucion", "activa")
    search_fields = ("nombre",)
    inlines = (SubareaInline,)

    def delete_model(self, request, obj):
        with transaction.atomic():
            area = Area.objects.select_for_update().get(pk=obj.pk)
            if area.formularios.exists():
                raise PermissionDenied("El área tiene formularios vinculados. Reasigná primero los que sean editables.")
            boxes = list(Box.objects.select_for_update().filter(area=area).order_by("pk"))
            if any(box.ocupado_por_id is not None for box in boxes):
                raise PermissionDenied("El área tiene boxes ocupados. Liberalos antes de eliminarla.")
            super().delete_model(request, area)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            areas = list(Area.objects.select_for_update().filter(pk__in=queryset.values("pk")).order_by("pk"))
            if any(area.formularios.exists() for area in areas):
                raise PermissionDenied("Hay áreas con formularios vinculados. Reasigná primero los que sean editables.")
            boxes = list(Box.objects.select_for_update().filter(area__in=areas).order_by("pk"))
            if any(box.ocupado_por_id is not None for box in boxes):
                raise PermissionDenied("Hay áreas con boxes ocupados. Liberalos antes de eliminarlas.")
            Area.objects.filter(pk__in=[area.pk for area in areas]).delete()


@admin.register(Subarea)
class SubareaAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("nombre", "area", "activa")
    list_filter = ("area__institucion", "activa")
    search_fields = ("nombre",)


@admin.register(Grupo)
class GrupoAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("nombre", "area", "activo", "creado")
    list_filter = ("area__institucion", "activo")
    search_fields = ("nombre",)
    filter_horizontal = ("miembros",)


@admin.register(Box)
class BoxAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("nombre", "area", "activo", "creado")
    list_filter = ("area__institucion", "activo")
    search_fields = ("nombre",)
    readonly_fields = ("ocupado_por", "ocupado_desde")

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("area",) if obj else ())

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change:
                vigente = Box.objects.select_for_update().get(pk=obj.pk)
                # Son datos operativos: el formulario de configuración no debe
                # restaurar los que leyó antes de ocupar/liberar el box.
                obj.ocupado_por_id = vigente.ocupado_por_id
                obj.ocupado_desde = vigente.ocupado_desde
                obj.area_id = vigente.area_id
            super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.ocupado_por_id)

    def delete_model(self, request, obj):
        with transaction.atomic():
            vigente = Box.objects.select_for_update().get(pk=obj.pk)
            if vigente.ocupado_por_id is not None:
                raise PermissionDenied("El box está ocupado. Liberalo antes de eliminarlo.")
            super().delete_model(request, vigente)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            boxes = list(Box.objects.select_for_update().filter(pk__in=queryset.values("pk")).order_by("pk"))
            if any(box.ocupado_por_id is not None for box in boxes):
                raise PermissionDenied("Hay boxes ocupados. Liberalos antes de eliminarlos.")
            Box.objects.filter(pk__in=[box.pk for box in boxes]).delete()
