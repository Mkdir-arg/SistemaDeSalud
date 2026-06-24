from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LegajoProfesional, Membresia, Usuario


class MembresiaInline(admin.TabularInline):
    model = Membresia
    extra = 0
    filter_horizontal = ("areas",)


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    ordering = ("apellido", "nombre")
    list_display = ("email", "nombre", "apellido", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser")
    search_fields = ("email", "nombre", "apellido")
    inlines = (MembresiaInline,)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "apellido")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nombre", "apellido", "password1", "password2"),
        }),
    )


@admin.register(Membresia)
class MembresiaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "institucion", "rol", "activo")
    list_filter = ("rol", "activo", "institucion")
    filter_horizontal = ("areas",)


@admin.register(LegajoProfesional)
class LegajoProfesionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "especialidad", "matricula")
    search_fields = ("usuario__nombre", "usuario__apellido", "matricula")
