"""Revisión de accesos clínicos que no se pudieron registrar (#172).

`AccesoClinico` sigue fuera del Admin a propósito: el registro de accesos no se
edita ni se borra. `FalloAuditoria` tampoco: solo se marca revisado, que saca el
aviso de `/api/estado/` y deja quién lo revisó y cuándo.
"""
from django.contrib import admin, messages
from django.utils import timezone

from .models import FalloAuditoria


@admin.register(FalloAuditoria)
class FalloAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("momento", "tipo", "recurso", "institucion", "error", "revisado_at", "revisado_por")
    list_filter = (("revisado_at", admin.EmptyFieldListFilter), "error", "institucion")
    readonly_fields = ("momento", "tipo", "recurso", "institucion", "error", "revisado_at", "revisado_por")
    actions = ["marcar_revisado"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Marcar como revisado", permissions=["change"])
    def marcar_revisado(self, request, queryset):
        n = queryset.filter(revisado_at__isnull=True).update(revisado_at=timezone.now(), revisado_por=request.user)
        self.message_user(request, f"{n} fallo(s) marcados como revisados.", messages.SUCCESS)
