from rest_framework import serializers

from .models import Agenda, Bloqueo, Disponibilidad, Turno


class DisponibilidadSerializer(serializers.ModelSerializer):
    dia_display = serializers.CharField(source="get_dia_semana_display", read_only=True)
    paso_min = serializers.IntegerField(read_only=True)

    class Meta:
        model = Disponibilidad
        fields = [
            "id", "agenda", "dia_semana", "dia_display", "desde", "hasta",
            "duracion_min", "paso_min", "vigente_desde", "vigente_hasta", "activa",
        ]

    def validate(self, attrs):
        desde = attrs.get("desde", getattr(self.instance, "desde", None))
        hasta = attrs.get("hasta", getattr(self.instance, "hasta", None))
        if desde and hasta and hasta <= desde:
            raise serializers.ValidationError(
                {"hasta": "La franja tiene que terminar después de empezar."}
            )
        return attrs


class BloqueoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bloqueo
        fields = ["id", "agenda", "desde", "hasta", "motivo", "creado"]
        read_only_fields = ["creado"]

    def validate(self, attrs):
        desde = attrs.get("desde", getattr(self.instance, "desde", None))
        hasta = attrs.get("hasta", getattr(self.instance, "hasta", None))
        if desde and hasta and hasta <= desde:
            raise serializers.ValidationError({"hasta": "El bloqueo tiene que terminar después de empezar."})
        return attrs


class AgendaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)
    profesional_nombre = serializers.SerializerMethodField()
    flujo_titulo = serializers.CharField(source="flujo.titulo", read_only=True, default=None)
    disponibilidades = DisponibilidadSerializer(many=True, read_only=True)

    class Meta:
        model = Agenda
        fields = [
            "id", "institucion", "area", "area_nombre", "tipo", "tipo_display", "nombre",
            "profesional", "profesional_nombre", "flujo", "flujo_titulo",
            "duracion_min", "sobreturnos_max", "activa", "creada", "disponibilidades",
        ]
        read_only_fields = ["creada"]

    def get_profesional_nombre(self, obj) -> str | None:
        return obj.profesional.nombre_completo if obj.profesional_id else None

    def validate(self, attrs):
        # Una agenda de recurso con profesional asignado, o una de profesional
        # sin nadie, son configuraciones que después no se pueden operar: el
        # caso no sabría a quién asignarse.
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", Agenda.Tipo.PROFESIONAL))
        prof = attrs.get("profesional", getattr(self.instance, "profesional", None))
        if tipo == Agenda.Tipo.RECURSO and prof:
            raise serializers.ValidationError(
                {"profesional": "Una agenda de recurso no lleva profesional."}
            )
        return attrs


class TurnoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    agenda_nombre = serializers.CharField(source="agenda.nombre", read_only=True)
    area_nombre = serializers.CharField(source="agenda.area.nombre", read_only=True)
    paciente = serializers.SerializerMethodField()
    documento = serializers.CharField(source="ciudadano.documento", read_only=True)
    fin = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Turno
        fields = [
            "id", "agenda", "agenda_nombre", "area_nombre", "ciudadano", "paciente",
            "documento", "inicio", "fin", "duracion_min", "estado", "estado_display",
            "sobreturno", "motivo", "origen", "caso", "observaciones",
            "recordado_at", "cancelado_at", "creado",
        ]
        # El estado se mueve con las acciones (`cancelar`, `llegada`, `ausente`),
        # que además de cambiarlo abren el caso o liberan el horario. Por PATCH
        # se podría marcar «presente» sin que exista el caso.
        read_only_fields = [
            "estado", "caso", "duracion_min", "sobreturno",
            "recordado_at", "cancelado_at", "creado",
        ]

    def get_paciente(self, obj) -> str | None:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None
