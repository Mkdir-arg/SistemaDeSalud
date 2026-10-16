from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as PermisoDenegadoAPI

from .credenciales import solicitar_recuperacion
from .models import LegajoProfesional, Membresia, Usuario


class UsuarioAdminForm(forms.ModelForm):
    # Sin el campo `password` que declara UserChangeForm, ni siquiera de lectura.
    class Meta:
        model = Usuario
        fields = ("nombre", "apellido", "is_active")


class MembresiaInline(admin.TabularInline):
    model = Membresia
    extra = 0
    filter_horizontal = ("areas",)


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """Consulta y bloqueo global; las credenciales las administra el titular (#172).

    Fijar la contraseña o el email de otra persona permitiría actuar como ese
    profesional. La recuperación excepcional sale como enlace al email del
    titular; los privilegios se otorgan con `asignar_privilegios`, que deja
    registro.
    """

    form = UsuarioAdminForm
    ordering = ("apellido", "nombre")
    list_display = ("email", "nombre", "apellido", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "nombre", "apellido")
    inlines = (MembresiaInline,)
    fieldsets = (
        (None, {"fields": ("email",)}),
        ("Datos personales", {"fields": ("nombre", "apellido")}),
        ("Estado y privilegios", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    readonly_fields = ("email", "is_staff", "is_superuser", "groups", "user_permissions")
    filter_horizontal = ()
    actions = ["iniciar_recuperacion"]

    def has_add_permission(self, request):
        # El alta elige una contraseña: va por invitación desde la API.
        return False

    def has_change_permission(self, request, obj=None):
        # Solo un superusuario modifica (o bloquea) a otro superusuario.
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def user_change_password(self, request, id, form_url=""):
        raise PermissionDenied("La contraseña la administra su titular.")

    @admin.action(description="Enviar recuperación de acceso al titular", permissions=["change"])
    def iniciar_recuperacion(self, request, queryset):
        enviadas = rechazadas = 0
        for usuario in queryset:
            try:
                solicitar_recuperacion(usuario, actor=request.user)
            except PermisoDenegadoAPI:
                rechazadas += 1
            except APIException as error:
                # Correo sin configurar: no se aceptó ninguna solicitud más.
                self.message_user(request, str(error.detail), messages.ERROR)
                return
            else:
                enviadas += 1
        if enviadas:
            self.message_user(request, f"Recuperación solicitada para {enviadas} titular(es).", messages.SUCCESS)
        if rechazadas:
            self.message_user(request, f"{rechazadas} cuenta(s) no admiten recuperación por tu acceso.", messages.WARNING)


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "institucion", "rol", "activo")
    list_filter = ("rol", "activo", "institucion")
    filter_horizontal = ("areas",)


@admin.register(LegajoProfesional)
class LegajoProfesionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "especialidad", "matricula")
    search_fields = ("usuario__nombre", "usuario__apellido", "matricula")
