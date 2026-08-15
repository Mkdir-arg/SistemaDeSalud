from rest_framework import serializers

from .models import Campo, Formulario


class CampoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    vinculado = serializers.BooleanField(read_only=True)
    valores_cargados = serializers.SerializerMethodField()

    class Meta:
        model = Campo
        fields = [
            "id", "formulario", "label", "tipo", "tipo_display", "requerido",
            "ayuda", "opciones", "origen", "orden", "vinculado", "valores_cargados",
        ]

    def get_valores_cargados(self, obj) -> int:
        """Cuántos datos de casos reales dependen de este campo.

        Lo necesita la pantalla para decir la verdad antes de quitarlo: el
        diálogo prometía que «los datos ya cargados no se borran» y el borrado
        arrastraba en cascada todos los ValorCampo."""
        n = getattr(obj, "valores_n", None)
        return n if n is not None else obj.valores.count()


class FormularioSerializer(serializers.ModelSerializer):
    campos = CampoSerializer(many=True, read_only=True)

    class Meta:
        model = Formulario
        fields = ["id", "institucion", "area", "titulo", "descripcion", "creado", "campos"]
        read_only_fields = ["creado"]
