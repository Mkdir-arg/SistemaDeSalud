from rest_framework import serializers

from .models import HechoAtencionCosteable


class HechoAtencionCosteableSerializer(serializers.ModelSerializer):
    """Detalle económico sin narrativa ni valores clínicos del paciente."""

    total_conocido = serializers.SerializerMethodField()
    total_es_completo = serializers.SerializerMethodField()
    estado_costo = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()
    imputaciones = serializers.SerializerMethodField()
    limite = serializers.SerializerMethodField()

    class Meta:
        model = HechoAtencionCosteable
        fields = [
            "id", "institucion", "caso", "ciudadano", "area", "ocurrida_en",
            "total_conocido", "total_es_completo", "estado_costo", "faltantes",
            "imputaciones", "limite",
        ]
        read_only_fields = fields

    @staticmethod
    def _pendientes(obj):
        return [p for p in obj.pendientes.all() if not p.resuelto]

    def get_total_conocido(self, obj):
        imputaciones = list(obj.imputaciones.all())
        if not imputaciones:
            return None
        # Igual que `importe` en las imputaciones: texto decimal para no perder
        # precisión al cruzar JSON, y `null` reservado para lo desconocido.
        return str(sum((imputacion.importe for imputacion in imputaciones), start=0))

    def get_total_es_completo(self, obj):
        return bool(obj.componentes_esperados.all()) and not self._pendientes(obj)

    def get_estado_costo(self, obj):
        pendientes = self._pendientes(obj)
        if pendientes:
            return "parcial" if obj.imputaciones.all() else "pendiente"
        return "disponible" if obj.componentes_esperados.all() else "pendiente"

    def get_faltantes(self, obj):
        return [
            {
                "motivo": pendiente.motivo,
                "motivo_display": pendiente.get_motivo_display(),
                "componente": pendiente.componente_id,
                "componente_codigo": pendiente.componente.codigo if pendiente.componente_id else None,
            }
            for pendiente in self._pendientes(obj)
        ]

    def get_imputaciones(self, obj):
        return [
            {
                "componente": imputacion.componente_id,
                "componente_codigo": imputacion.componente.codigo,
                "componente_nombre": imputacion.componente.nombre,
                "importe": imputacion.importe,
            }
            for imputacion in obj.imputaciones.all()
        ]

    @staticmethod
    def get_limite(_obj):
        return "Sólo componentes directos configurados; no incluye aranceles, cargos ni dinero cobrado."
