from rest_framework import serializers

from .models import Area, Box, Cama, EstadiaCama, Grupo, Institucion, Subarea


class SubareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subarea
        fields = ["id", "area", "nombre", "activa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["area"].read_only = True


class BoxSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)
    ocupado_por_nombre = serializers.CharField(source="ocupado_por.nombre_completo", read_only=True, default=None)

    class Meta:
        model = Box
        fields = ["id", "area", "area_nombre", "nombre", "activo", "ocupado_por", "ocupado_por_nombre", "ocupado_desde", "creado"]
        read_only_fields = ["creado", "ocupado_por", "ocupado_desde"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["area"].read_only = True


class GrupoSerializer(serializers.ModelSerializer):
    # Lectura: lista enriquecida de integrantes (id, nombre, email).
    integrantes = serializers.SerializerMethodField()
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)

    class Meta:
        model = Grupo
        fields = ["id", "area", "area_nombre", "nombre", "descripcion", "miembros", "integrantes", "activo", "creado"]
        read_only_fields = ["creado"]
        extra_kwargs = {"miembros": {"write_only": True, "required": False}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["area"].read_only = True

    def get_integrantes(self, obj) -> list[dict]:
        miembros = obj.miembros.filter(
            is_active=True,
            membresias__institucion=obj.area.institucion,
            membresias__areas=obj.area,
            membresias__activo=True,
        ).distinct()
        return [
            {"id": u.id, "nombre": u.nombre_completo, "email": u.email}
            for u in miembros
        ]

    def validate(self, attrs):
        # Los integrantes deben pertenecer al área del grupo (tener membresía
        # en la institución con esa área asignada).
        from apps.accounts.models import Membresia

        area = attrs.get("area", getattr(self.instance, "area", None))
        miembros = attrs.get("miembros")
        if area and miembros:
            permitidos = set(
                Membresia.objects.filter(
                    institucion=area.institucion,
                    areas=area,
                    activo=True,
                    usuario__is_active=True,
                )
                .values_list("usuario_id", flat=True)
            )
            fuera = [u.id for u in miembros if u.id not in permitidos]
            if fuera:
                raise serializers.ValidationError(
                    {"miembros": "Algunas personas no pertenecen al área del grupo."}
                )
        return attrs


class AreaSerializer(serializers.ModelSerializer):
    subareas = SubareaSerializer(many=True, read_only=True)
    staff = serializers.SerializerMethodField()

    class Meta:
        model = Area
        fields = ["id", "institucion", "nombre", "responsable", "descripcion", "activa", "subareas", "staff"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["institucion"].read_only = True

    def get_staff(self, obj) -> int:
        return obj.miembros.filter(activo=True, usuario__is_active=True).values("usuario").distinct().count()


class InstitucionSerializer(serializers.ModelSerializer):
    areas_count = serializers.IntegerField(source="areas.count", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    staff = serializers.SerializerMethodField()

    def get_staff(self, obj) -> int:
        return obj.membresias.filter(activo=True, usuario__is_active=True).values("usuario").distinct().count()

    class Meta:
        model = Institucion
        fields = ["id", "nombre", "tipo", "cuit", "direccion", "estado", "estado_display", "activa", "creada", "areas_count", "staff"]
        read_only_fields = ["creada"]


class CamaSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    sector = serializers.SerializerMethodField()
    # Quién la ocupa: es lo que el tablero muestra en la ficha de la cama.
    paciente = serializers.SerializerMethodField()
    caso_id = serializers.IntegerField(source="caso.id", read_only=True, allow_null=True)
    disponible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cama
        fields = [
            "id", "area", "subarea", "sector", "nombre", "estado", "estado_display",
            "caso", "caso_id", "paciente", "desde", "motivo", "activa", "disponible",
        ]
        # El estado NO se escribe por PATCH: se mueve junto con la estadía del
        # paciente. Marcar «libre» una cama ocupada dejaría a alguien internado
        # en ningún lado. Se cambia por la acción `estado`, que valida.
        read_only_fields = ["estado", "caso", "desde"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["area"].read_only = True
            self.fields["subarea"].read_only = True

    def validate(self, attrs):
        area = attrs.get("area", getattr(self.instance, "area", None))
        subarea = attrs.get("subarea", getattr(self.instance, "subarea", None))
        if area and subarea and subarea.area_id != area.id:
            raise serializers.ValidationError(
                {"subarea": "La subarea/sector debe pertenecer al area de la cama."}
            )
        return attrs

    def get_sector(self, obj) -> str:
        return obj.sector_nombre

    def get_paciente(self, obj) -> str | None:
        c = obj.caso
        if c is None or not c.ciudadano_id:
            return None
        return f"{c.ciudadano.nombre} {c.ciudadano.apellido}".strip()


class EstadiaCamaSerializer(serializers.ModelSerializer):
    cama_nombre = serializers.CharField(source="cama.nombre", read_only=True)
    sector = serializers.SerializerMethodField()
    egreso_display = serializers.CharField(source="get_motivo_egreso_display", read_only=True)

    class Meta:
        model = EstadiaCama
        fields = ["id", "cama", "cama_nombre", "sector", "caso", "desde", "hasta",
                  "motivo_egreso", "egreso_display"]
        read_only_fields = fields

    def get_sector(self, obj) -> str:
        return obj.cama.sector_nombre
