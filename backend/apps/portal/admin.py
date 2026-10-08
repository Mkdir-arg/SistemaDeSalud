from django.contrib import admin

from .models import CuentaPaciente, EventoPortal


@admin.register(CuentaPaciente)
class CuentaPacienteAdmin(admin.ModelAdmin):
    """Para soporte: ver el estado y dar de baja una cuenta (`activa`).

    La identidad y la contraseña no se editan desde acá: la identidad la da
    RENAPER y la contraseña la elige el paciente.
    """

    list_display = ["email", "identidad", "documento", "activa", "email_verificado_at", "creada"]
    list_filter = ["identidad", "activa"]
    search_fields = ["email", "documento"]
    fields = [
        "email", "activa", "email_verificado_at", "identidad", "identidad_via", "identidad_validada_at",
        "documento", "sexo", "nombre", "apellido", "fecha_nacimiento", "intentos_validacion",
        "validacion_bloqueada_hasta", "creada",
    ]
    readonly_fields = [f for f in fields if f not in ("activa", "validacion_bloqueada_hasta")]

    def has_add_permission(self, request):
        return False


@admin.register(EventoPortal)
class EventoPortalAdmin(admin.ModelAdmin):
    list_display = ["momento", "tipo", "email", "ip"]
    list_filter = ["tipo"]
    search_fields = ["email"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
