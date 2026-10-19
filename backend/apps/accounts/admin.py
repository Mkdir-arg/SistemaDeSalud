from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from rest_framework.exceptions import APIException
from rest_framework.exceptions import PermissionDenied as PermisoDenegadoAPI

from apps.admin_alcance import AlcanceInstitucionalAdmin, AlcanceInstitucionalInline, instituciones_administradas
from apps.common import tiene_capacidad
from apps.simulacion.perfiles import DOMINIO

from .credenciales import solicitar_recuperacion
from .models import LegajoProfesional, Membresia, Usuario
from .serializers import ROLES_GOBIERNO


def _sin_cuentas_de_referencia(request, qs, prefijo=""):
    # Como en la API: las cuentas de referencia de la simulación no se
    # administran desde la gestión de usuarios.
    if instituciones_administradas(request) is None:
        return qs
    return qs.exclude(Q(**{f"{prefijo}email__iendswith": f"@{DOMINIO}"})
                      | Q(**{f"{prefijo}cuenta_referencia__isnull": False}))


class RolAsignableMixin:
    """Como `validar_rol_asignable` de la API: solo plataforma asigna roles estatales."""

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        campo = super().formfield_for_choice_field(db_field, request, **kwargs)
        user = request.user
        if db_field.name == "rol" and not (user.is_superuser or tiene_capacidad(user, "gobierno_plataforma")):
            campo.choices = [(valor, texto) for valor, texto in campo.choices if valor not in ROLES_GOBIERNO]
        return campo


class UsuarioAdminForm(forms.ModelForm):
    # Sin el campo `password` que declara UserChangeForm, ni siquiera de lectura.
    class Meta:
        model = Usuario
        fields = ("nombre", "apellido", "is_active")


class MembresiaInline(RolAsignableMixin, AlcanceInstitucionalInline, admin.TabularInline):
    model = Membresia
    extra = 0
    filter_horizontal = ("areas",)


@admin.register(Usuario)
class UsuarioAdmin(AlcanceInstitucionalAdmin, BaseUserAdmin):
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

    def get_queryset(self, request):
        return _sin_cuentas_de_referencia(request, super().get_queryset(request))

    def _cuenta_solo_de_lo_administrado(self, request, obj):
        # Nombre, bloqueo y borrado son de la cuenta entera: si también pertenece
        # a otra institución (o es estatal), un staff institucional solo la ve.
        ids = instituciones_administradas(request)
        if obj is None or ids is None:
            return True
        return not Membresia.objects_sin_corte.filter(usuario=obj).filter(
            ~Q(institucion_id__in=ids) | Q(institucion__isnull=True)).exists()

    def has_change_permission(self, request, obj=None):
        # Solo un superusuario modifica (o bloquea) a otro superusuario.
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj) and self._cuenta_solo_de_lo_administrado(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._cuenta_solo_de_lo_administrado(request, obj)

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
class MembresiaAdmin(RolAsignableMixin, AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("usuario", "institucion", "rol", "activo")
    list_filter = ("rol", "activo", "institucion")
    filter_horizontal = ("areas",)

    def get_queryset(self, request):
        return _sin_cuentas_de_referencia(request, super().get_queryset(request), "usuario__")


@admin.register(LegajoProfesional)
class LegajoProfesionalAdmin(AlcanceInstitucionalAdmin, admin.ModelAdmin):
    list_display = ("usuario", "especialidad", "matricula")
    search_fields = ("usuario__nombre", "usuario__apellido", "matricula")
