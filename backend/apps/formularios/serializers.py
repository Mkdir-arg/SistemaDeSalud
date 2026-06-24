from rest_framework import serializers

from .models import Campo, Formulario


class CampoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    vinculado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Campo
        fields = [
            "id", "formulario", "label", "tipo", "tipo_display", "requerido",
            "ayuda", "opciones", "origen", "orden", "vinculado",
        ]


class FormularioSerializer(serializers.ModelSerializer):
    campos = CampoSerializer(many=True, read_only=True)

    class Meta:
        model = Formulario
        fields = ["id", "institucion", "area", "titulo", "descripcion", "creado", "campos"]
        read_only_fields = ["creado"]
