from rest_framework import serializers

from .models import Caso, EventoCaso, ItemFila, ValorCampo


class ValorCampoSerializer(serializers.ModelSerializer):
    campo_label = serializers.CharField(source="campo.label", read_only=True)

    class Meta:
        model = ValorCampo
        fields = ["id", "caso", "campo", "campo_label", "nodo", "valor", "cargado"]
        read_only_fields = ["cargado"]


class ItemFilaSerializer(serializers.ModelSerializer):
    persona = serializers.SerializerMethodField()
    nodo_titulo = serializers.CharField(source="nodo.titulo", read_only=True)

    class Meta:
        model = ItemFila
        fields = ["id", "caso", "nodo", "nodo_titulo", "turno", "persona", "urgente", "orden", "atendido", "ingreso"]
        read_only_fields = ["ingreso"]

    def get_persona(self, obj):
        c = obj.caso.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None


class EventoCasoSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = EventoCaso
        fields = ["id", "caso", "titulo", "detalle", "autor", "autor_nombre", "nodo", "fecha"]
        read_only_fields = ["fecha"]

    def get_autor_nombre(self, obj):
        return obj.autor.nombre_completo if obj.autor else "Sistema"


class CasoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    prioridad_display = serializers.CharField(source="get_prioridad_display", read_only=True)
    flujo_titulo = serializers.CharField(source="version.flujo.titulo", read_only=True)
    paso_actual = serializers.CharField(source="nodo_actual.titulo", read_only=True)
    nodo_tipo = serializers.CharField(source="nodo_actual.tipo", read_only=True)
    area_nombre = serializers.SerializerMethodField()
    ciudadano_nombre = serializers.SerializerMethodField()
    asignado_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Caso
        fields = [
            "id", "institucion", "version", "flujo_titulo", "ciudadano", "ciudadano_nombre",
            "estado", "estado_display", "prioridad", "prioridad_display",
            "nodo_actual", "paso_actual", "nodo_tipo", "area_actual", "area_nombre",
            "asignado_a", "asignado_nombre", "creado", "actualizado",
        ]
        read_only_fields = ["creado", "actualizado"]

    def get_area_nombre(self, obj):
        return obj.area_actual.nombre if obj.area_actual_id else None

    def get_ciudadano_nombre(self, obj):
        if obj.ciudadano_id:
            return f"{obj.ciudadano.nombre} {obj.ciudadano.apellido}".strip()
        return None

    def get_asignado_nombre(self, obj):
        return obj.asignado_a.nombre_completo if obj.asignado_a_id else None


class CasoDetalleSerializer(CasoSerializer):
    """Caso con valores, fila y trazabilidad anidados (vista de detalle)."""

    valores = ValorCampoSerializer(many=True, read_only=True)
    eventos = EventoCasoSerializer(many=True, read_only=True)

    class Meta(CasoSerializer.Meta):
        fields = CasoSerializer.Meta.fields + ["valores", "eventos"]
