from rest_framework import serializers

from .models import Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta


class EntradaHistoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntradaHistoria
        fields = [
            "id", "historia", "titulo", "contenido", "autor", "caso", "firmada", "fecha",
        ]
        read_only_fields = ["fecha"]


class EstudioSerializer(serializers.ModelSerializer):
    resultado_display = serializers.CharField(source="get_resultado_display", read_only=True)

    class Meta:
        model = Estudio
        fields = ["id", "historia", "tipo", "resultado", "resultado_display", "realizado", "archivo", "autor", "fecha"]


class RecetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receta
        fields = ["id", "historia", "detalle", "activa", "autor", "fecha"]
        read_only_fields = ["fecha"]


class HistoriaClinicaSerializer(serializers.ModelSerializer):
    entradas = EntradaHistoriaSerializer(many=True, read_only=True)
    estudios = EstudioSerializer(many=True, read_only=True)
    recetas = RecetaSerializer(many=True, read_only=True)

    class Meta:
        model = HistoriaClinica
        fields = [
            "id", "ciudadano", "alergias", "condiciones", "creada",
            "entradas", "estudios", "recetas",
        ]
        read_only_fields = ["creada"]


class CiudadanoSerializer(serializers.ModelSerializer):
    # Resumen de la historia clínica (para la lista de HC).
    condiciones = serializers.SerializerMethodField()
    alergias = serializers.SerializerMethodField()
    entradas = serializers.SerializerMethodField()
    estudios = serializers.SerializerMethodField()
    recetas_activas = serializers.SerializerMethodField()
    ultima = serializers.SerializerMethodField()

    class Meta:
        model = Ciudadano
        fields = [
            "id", "institucion", "codigo", "nombre", "apellido", "documento",
            "fecha_nacimiento", "obra_social", "domicilio", "creado",
            "condiciones", "alergias", "entradas", "estudios", "recetas_activas", "ultima",
        ]
        read_only_fields = ["creado"]

    def _hc(self, obj):
        return getattr(obj, "historia_clinica", None)

    def get_condiciones(self, obj):
        hc = self._hc(obj)
        return hc.condiciones if hc else ""

    def get_alergias(self, obj):
        hc = self._hc(obj)
        return hc.alergias if hc else ""

    def get_entradas(self, obj):
        hc = self._hc(obj)
        return hc.entradas.count() if hc else 0

    def get_estudios(self, obj):
        hc = self._hc(obj)
        return hc.estudios.count() if hc else 0

    def get_recetas_activas(self, obj):
        hc = self._hc(obj)
        return hc.recetas.filter(activa=True).count() if hc else 0

    def get_ultima(self, obj):
        hc = self._hc(obj)
        if not hc:
            return None
        e = hc.entradas.order_by("-fecha").first()
        return e.fecha if e else None
