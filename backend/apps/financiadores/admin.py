"""Admin de financiadores: sólo el diccionario de códigos, sólo superusuario.

Los financiadores no cuelgan de una institución, así que no aplica el alcance
institucional de #172 (`AlcanceInstitucionalAdmin`). Para no abrir a un staff
común los catálogos de todos los financiadores, el acceso queda restringido a
superusuarios.
"""
from django.contrib import admin

from .models import CodigoFinanciador


@admin.register(CodigoFinanciador)
class CodigoFinanciadorAdmin(admin.ModelAdmin):
    list_display = ("financiador", "tabla", "codigo", "descripcion", "activo", "actualizado")
    list_filter = ("financiador", "tabla", "activo")
    search_fields = ("codigo", "descripcion")
    ordering = ("financiador", "tabla", "codigo")
    readonly_fields = ("actualizado",)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)
