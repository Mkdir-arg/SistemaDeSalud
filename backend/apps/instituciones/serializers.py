from rest_framework import serializers

from .models import Area, Grupo, Institucion, Subarea


class SubareaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subarea
        fields = ["id", "area", "nombre", "activa"]


class GrupoSerializer(serializers.ModelSerializer):
    # Lectura: lista enriquecida de integrantes (id, nombre, email).
    integrantes = serializers.SerializerMethodField()
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)

    class Meta:
        model = Grupo
        fields = ["id", "area", "area_nombre", "nombre", "descripcion", "miembros", "integrantes", "activo", "creado"]
        read_only_fields = ["creado"]
        extra_kwargs = {"miembros": {"write_only": True, "required": False}}

    def get_integrantes(self, obj):
        return [
            {"id": u.id, "nombre": u.nombre_completo, "email": u.email}
            for u in obj.miembros.all()
        ]

    def validate(self, attrs):
        # Los integrantes deben pertenecer al área del grupo (tener membresía
        # en la institución con esa área asignada).
        from apps.accounts.models import Membresia

        area = attrs.get("area", getattr(self.instance, "area", None))
        miembros = attrs.get("miembros")
        if area and miembros:
            permitidos = set(
                Membresia.objects.filter(institucion=area.institucion, areas=area)
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
