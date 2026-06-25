from rest_framework import serializers

from .models import Conexion, Flujo, Nodo, VersionFlujo


class NodoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    # Lectura: grupos responsables con nombre y área (para mostrar "quién hace esto").
    grupos_detalle = serializers.SerializerMethodField()

    class Meta:
        model = Nodo
        fields = [
            "id", "version", "tipo", "tipo_display", "titulo", "descripcion",
            "x", "y", "config", "formulario", "grupos", "grupos_detalle",
        ]
        extra_kwargs = {"grupos": {"required": False}}

    def get_grupos_detalle(self, obj):
        return [
            {"id": g.id, "nombre": g.nombre, "area": g.area_id, "area_nombre": g.area.nombre}
            for g in obj.grupos.all()
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
    subarea_nombre = serializers.SerializerMethodField()
    ambito = serializers.CharField(read_only=True)
    ambito_label = serializers.SerializerMethodField()
    # Cómo entran los casos a este flujo (config del nodo Inicio publicado):
    # "manual" | "derivado" | "ambos". Por defecto "ambos" (compatibilidad).
    origen_inicio = serializers.SerializerMethodField()
    casos_activos = serializers.SerializerMethodField()

    class Meta:
        model = Flujo
        fields = [
            "id", "institucion", "area", "area_nombre", "subarea", "subarea_nombre",
            "ambito", "ambito_label", "origen_inicio", "titulo", "descripcion", "creado", "versiones", "casos_activos",
        ]
        read_only_fields = ["creado"]

    def get_origen_inicio(self, obj):
        ver = obj.version_publicada
        if not ver:
            return "ambos"
        inicio = ver.nodos.filter(tipo="inicio").first()
        return (inicio.config or {}).get("origen", "ambos") if inicio else "ambos"

    def validate(self, attrs):
        # `area` se deriva de `subarea`; si vienen ambas, deben ser coherentes.
        subarea = attrs.get("subarea", getattr(self.instance, "subarea", None))
        area = attrs.get("area", getattr(self.instance, "area", None))
        if subarea and area and subarea.area_id != area.id:
            raise serializers.ValidationError({"subarea": "La sub-área no pertenece al área indicada."})
        return attrs

    def get_area_nombre(self, obj):
        return obj.area.nombre if obj.area_id else "Institución"

    def get_subarea_nombre(self, obj):
        return obj.subarea.nombre if obj.subarea_id else None

    def get_ambito_label(self, obj):
        if obj.subarea_id:
            return f"{obj.area.nombre} › {obj.subarea.nombre}"
        if obj.area_id:
            return obj.area.nombre
        return "Institución"

    def get_casos_activos(self, obj):
        from apps.casos.models import Caso
        return Caso.objects.filter(version__flujo=obj).exclude(estado=Caso.Estado.CERRADO).count()
