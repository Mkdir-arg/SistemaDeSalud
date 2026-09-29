"""Consulta de simulaciones para el superusuario. Solo lectura: es evidencia."""
from django.contrib import admin

from .models import CuentaReferencia, OperacionSimulada, SesionSimulacion


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CuentaReferencia)
class CuentaReferenciaAdmin(SoloLectura):
    list_display = ("usuario", "ambito", "rol", "institucion", "financiador", "creada")
    list_filter = ("ambito", "rol")


@admin.register(SesionSimulacion)
class SesionSimulacionAdmin(SoloLectura):
    list_display = ("iniciada", "superusuario", "rol", "ambito", "institucion", "financiador", "finalizada", "fin")
    list_filter = ("ambito", "rol", "fin")
    search_fields = ("superusuario__email",)


@admin.register(OperacionSimulada)
class OperacionSimuladaAdmin(SoloLectura):
    list_display = ("momento", "sesion", "metodo", "ruta", "estado")
    list_filter = ("metodo", "estado")
