from rest_framework import serializers

from .models import Red, Traslado


class RedSerializer(serializers.ModelSerializer):
    instituciones_detalle = serializers.SerializerMethodField()

    class Meta:
        model = Red
        fields = ["id", "nombre", "descripcion", "instituciones", "instituciones_detalle",
                  "activa", "creada"]
        read_only_fields = ["creada"]

    def get_instituciones_detalle(self, obj) -> list[dict]:
        return [{"id": i.id, "nombre": i.nombre} for i in obj.instituciones.all()]


class TrasladoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    motivo_display = serializers.CharField(source="get_motivo_display", read_only=True)
    origen_nombre = serializers.CharField(source="origen.nombre", read_only=True)
    destino_nombre = serializers.CharField(source="destino.nombre", read_only=True)
    area_destino_nombre = serializers.CharField(
        source="area_destino.nombre", read_only=True, default=None
    )
    paciente = serializers.SerializerMethodField()
    documento = serializers.CharField(source="ciudadano.documento", read_only=True)
    solicitado_por_nombre = serializers.SerializerMethodField()
    demora_min = serializers.IntegerField(read_only=True)
    traslado_min = serializers.IntegerField(read_only=True)
    abierto = serializers.BooleanField(read_only=True)
    # De qué lado está quien mira. La misma pantalla sirve para los dos, pero
    # las acciones son distintas: uno pide y el otro responde.
    soy_origen = serializers.SerializerMethodField()

    class Meta:
        model = Traslado
        fields = [
            "id", "red", "origen", "origen_nombre", "destino", "destino_nombre",
            "caso_origen", "caso_destino", "ciudadano", "paciente", "documento",
            "area_destino", "area_destino_nombre", "estado", "estado_display",
            "motivo", "motivo_display", "detalle", "urgente", "respuesta",
            "solicitado_por_nombre", "solicitado_at", "resuelto_at",
            "salida_at", "llegada_at", "movil",
            "demora_min", "traslado_min", "abierto", "soy_origen",
        ]
        # Todo el ciclo pasa por el motor: cada paso cambia el estado Y toca el
        # caso de alguno de los dos lados. Por PATCH se podría marcar «recibido»
        # sin que el caso de origen se cierre.
        read_only_fields = [
            "id", "red", "origen", "destino", "caso_origen", "caso_destino", "ciudadano",
            "estado", "respuesta", "solicitado_at", "resuelto_at", "salida_at",
            "llegada_at", "movil",
        ]

    def get_paciente(self, obj) -> str:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip()

    def get_solicitado_por_nombre(self, obj) -> str | None:
        return obj.solicitado_por.nombre_completo if obj.solicitado_por_id else None

    def get_soy_origen(self, obj) -> bool:
        return obj.origen_id in (self.context.get("mis_instituciones") or set())
