"""Consulta explícita y de sólo lectura del registro financiero."""
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.common import BaseModelViewSet
from .calendario import en_alcance_financiero
from .models import AccesoFinanciero, ConcesionFinanciera
from .permisos import concesiones_financieras_de


class PuedeAuditarFinanzas(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or concesiones_financieras_de(
            request.user, ConcesionFinanciera.Accion.AUDITAR_FINANZAS,
        ).exists()


class AccesoFinancieroSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccesoFinanciero
        fields = [
            "id", "usuario", "institucion", "area", "sensible", "recurso", "accion",
            "objeto_id", "periodo_economico", "resultados", "registrado",
        ]
        read_only_fields = fields


class AccesoFinancieroViewSet(BaseModelViewSet):
    serializer_class = AccesoFinancieroSerializer
    queryset = AccesoFinanciero.objects.all()
    permission_classes = [IsAuthenticated, PuedeAuditarFinanzas]
    http_method_names = ["get", "head", "options"]
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "usuario", "recurso", "accion", "periodo_economico")
    ordering_fields = ("registrado", "id")

    def get_queryset(self):
        return en_alcance_financiero(
            super().get_queryset(), self.request.user, ConcesionFinanciera.Accion.AUDITAR_FINANZAS,
        )
