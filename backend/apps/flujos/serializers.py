from rest_framework import serializers

from .models import Conexion, Flujo, Nodo, VersionFlujo


class NodoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Nodo
        fields = [
            "id", "version", "tipo", "tipo_display", "titulo", "descripcion",
            "x", "y", "config", "formulario",
        ]


class ConexionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conexion
        fields = ["id", "version", "origen", "destino", "etiqueta", "condicion"]


class VersionFlujoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    etiqueta = serializers.CharField(read_only=True)
    nodos = NodoSerializer(many=True, read_only=True)
    conexiones = ConexionSerializer(many=True, read_only=True)

    class Meta:
        model = VersionFlujo
        fields = [
            "id", "flujo", "numero", "etiqueta", "estado", "estado_display",
            "nota", "autor", "creada", "nodos", "conexiones",
        ]
        read_only_fields = ["creada"]


class VersionFlujoResumenSerializer(serializers.ModelSerializer):
    """Versión sin el grafo, para listados anidados en Flujo."""

    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    etiqueta = serializers.CharField(read_only=True)

    class Meta:
        model = VersionFlujo
        fields = ["id", "numero", "etiqueta", "estado", "estado_display", "creada"]


class FlujoSerializer(serializers.ModelSerializer):
    versiones = VersionFlujoResumenSerializer(many=True, read_only=True)
    area_nombre = serializers.SerializerMethodField()
    casos_activos = serializers.SerializerMethodField()

    class Meta:
        model = Flujo
        fields = ["id", "institucion", "area", "area_nombre", "titulo", "descripcion", "creado", "versiones", "casos_activos"]
        read_only_fields = ["creado"]

    def get_area_nombre(self, obj):
        return obj.area.nombre if obj.area_id else "Institución"

    def get_casos_activos(self, obj):
        from apps.casos.models import Caso
        return Caso.objects.filter(version__flujo=obj).exclude(estado=Caso.Estado.CERRADO).count()
