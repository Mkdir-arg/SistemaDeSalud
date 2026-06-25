from rest_framework import serializers

from .models import Caso, EventoCaso, ItemFila, Notificacion, ValorCampo


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = ["id", "titulo", "detalle", "caso", "leida", "creada"]
        read_only_fields = ["creada"]


class ValorCampoSerializer(serializers.ModelSerializer):
    campo_label = serializers.CharField(source="campo.label", read_only=True)

    class Meta:
        model = ValorCampo
        fields = ["id", "caso", "campo", "campo_label", "nodo", "valor", "cargado"]
        read_only_fields = ["cargado"]


class ItemFilaSerializer(serializers.ModelSerializer):
    persona = serializers.SerializerMethodField()
    nodo_titulo = serializers.CharField(source="nodo.titulo", read_only=True)
    # Área del flujo al que pertenece la fila (para mostrar la fila por área).
    area = serializers.IntegerField(source="nodo.version.flujo.area_id", read_only=True)
    area_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ItemFila
        fields = ["id", "caso", "nodo", "nodo_titulo", "area", "area_nombre", "turno", "persona", "urgente", "orden", "atendido", "box", "ingreso"]
        read_only_fields = ["ingreso"]

    def get_persona(self, obj):
        c = obj.caso.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None

    def get_area_nombre(self, obj):
        a = obj.nodo.version.flujo.area
        return a.nombre if a else None


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
    # Grupos responsables del paso actual y si el usuario actual puede tomarlo.
    responsables = serializers.SerializerMethodField()
    puede_tomar = serializers.SerializerMethodField()
    # Si el usuario actual es jefe/supervisor del área del caso (cancelar/reasignar/priorizar).
    puede_supervisar = serializers.SerializerMethodField()
    # Trazabilidad de derivaciones entre flujos.
    origen_flujo = serializers.CharField(source="origen.version.flujo.titulo", read_only=True, default=None)
    # Si este caso vino a realizar un estudio, su tipo (el operador carga el resultado).
    estudio_tipo = serializers.CharField(source="estudio.tipo", read_only=True, default=None)
    # El paso actual es una atención con fila de espera previa.
    nodo_con_fila = serializers.SerializerMethodField()
    # El caso está encolado esperando ser llamado: se opera SOLO desde la Fila,
    # no desde la bandeja. Señal autoritativa para no duplicar la vista.
    en_fila = serializers.SerializerMethodField()

    class Meta:
        model = Caso
        fields = [
            "id", "institucion", "version", "flujo_titulo", "ciudadano", "ciudadano_nombre",
            "estado", "estado_display", "prioridad", "prioridad_display",
            "nodo_actual", "paso_actual", "nodo_tipo", "nodo_con_fila", "en_fila", "area_actual", "area_nombre",
            "asignado_a", "asignado_nombre", "responsables", "puede_tomar", "puede_supervisar", "esperando",
            "origen", "origen_flujo", "estudio", "estudio_tipo", "creado", "actualizado",
        ]
        read_only_fields = ["creado", "actualizado"]

    def get_nodo_con_fila(self, obj):
        return bool(obj.nodo_actual and (obj.nodo_actual.config or {}).get("con_fila"))

    def get_en_fila(self, obj):
        # Hay un ítem de fila activo y todavía sin llamar (sin box) en el paso actual.
        if not obj.nodo_actual_id:
            return False
        return any(
            (it.nodo_id == obj.nodo_actual_id and not it.atendido and it.box_id is None)
            for it in obj.en_filas.all()
        )

    def validate(self, attrs):
        # Un ingreso es siempre de una persona: al crear, exigir paciente.
        if self.instance is None and not attrs.get("ciudadano"):
            raise serializers.ValidationError({"ciudadano": "El caso debe asociarse a un paciente."})
        return attrs

    def get_area_nombre(self, obj):
        return obj.area_actual.nombre if obj.area_actual_id else None

    def get_responsables(self, obj):
        if not obj.nodo_actual_id:
            return []
        return [{"id": g.id, "nombre": g.nombre} for g in obj.nodo_actual.grupos.all()]

    def get_puede_tomar(self, obj):
        # Abierto a todos si el paso no declara grupos; si los declara, el usuario
        # debe integrar alguno (el super admin pasa siempre).
        if not obj.nodo_actual_id:
            return True
        gids = [g.id for g in obj.nodo_actual.grupos.all()]
        if not gids:
            return True
        if self.context.get("es_superuser"):
            return True
        user_gids = self.context.get("user_grupo_ids") or set()
        return any(g in user_gids for g in gids)

    def get_puede_supervisar(self, obj):
        if self.context.get("es_superuser"):
            return True
        area_id = obj.area_actual_id or (obj.version.flujo.area_id if obj.version_id else None)
        return area_id is not None and area_id in (self.context.get("areas_supervisadas") or set())

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
    # Casos generados por derivación desde éste (ingreso → especialidades).
    derivados = serializers.SerializerMethodField()
    # En una atención con fila: ¿ya fue llamado a un box? (si no, está esperando).
    llamado = serializers.SerializerMethodField()

    class Meta(CasoSerializer.Meta):
        fields = CasoSerializer.Meta.fields + ["valores", "eventos", "derivados", "llamado"]

    def get_llamado(self, obj):
        if not obj.nodo_actual_id:
            return False
        return obj.en_filas.filter(nodo=obj.nodo_actual, atendido=False, box__isnull=False).exists()

    def get_derivados(self, obj):
        return [
            {"id": d.id, "flujo_titulo": d.version.flujo.titulo, "estado": d.estado}
            for d in obj.derivados.select_related("version__flujo").all()
        ]
