from rest_framework import serializers

from .models import Area, Institucion, Subarea


class SubareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subarea
        fields = ["id", "area", "nombre", "activa"]


class AreaSerializer(serializers.ModelSerializer):
    subareas = SubareaSerializer(many=True, read_only=True)
    staff = serializers.SerializerMethodField()

    class Meta:
        model = Area
        fields = ["id", "institucion", "nombre", "responsable", "descripcion", "activa", "subareas", "staff"]

    def get_staff(self, obj):
        return obj.miembros.values("usuario").distinct().count()


class InstitucionSerializer(serializers.ModelSerializer):
    areas_count = serializers.IntegerField(source="areas.count", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    staff = serializers.SerializerMethodField()

    def get_staff(self, obj):
        return obj.membresias.values("usuario").distinct().count()

    class Meta:
        model = Institucion
        fields = ["id", "nombre", "tipo", "cuit", "direccion", "estado", "estado_display", "activa", "creada", "areas_count", "staff"]
        read_only_fields = ["creada"]
