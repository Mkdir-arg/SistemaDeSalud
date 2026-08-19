from rest_framework import serializers

from .models import LegajoProfesional, Membresia, Usuario


class LegajoProfesionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegajoProfesional
        fields = ["id", "usuario", "especialidad", "matricula"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["usuario"].read_only = True


class MembresiaSerializer(serializers.ModelSerializer):
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)
    # Evita que el cliente tenga que cruzar membresías con /usuarios/ para poder
    # mostrar un nombre en una lista.
    usuario_nombre = serializers.CharField(source="usuario.nombre_completo", read_only=True)
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)
    # Los nombres de las áreas, por el mismo motivo: la pantalla de Fila arma su
    # selector con las áreas propias y sin esto sólo tenía los ids, así que
    # mostraba «Área 3» donde tiene que decir «Guardia».
    areas_nombres = serializers.SerializerMethodField()

    class Meta:
        model = Membresia
        fields = [
            "id", "usuario", "usuario_nombre", "usuario_email",
            "institucion", "rol", "rol_display", "areas", "areas_nombres",
            "activo", "creado",
        ]
        read_only_fields = ["creado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["usuario"].read_only = True
            self.fields["institucion"].read_only = True

    def get_areas_nombres(self, obj) -> dict[str, str]:
        return {str(a.id): a.nombre for a in obj.areas.all()}

    def validate(self, attrs):
        institucion = attrs.get("institucion", getattr(self.instance, "institucion", None))
        areas = attrs.get("areas")
        if institucion and areas:
            fuera = [a.id for a in areas if a.institucion_id != institucion.id]
            if fuera:
                raise serializers.ValidationError(
                    {"areas": "Todas las areas de la membresia deben pertenecer a la institucion."}
                )
        return attrs


class UsuarioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta:
        model = Usuario
        fields = [
            "id", "email", "nombre", "apellido", "nombre_completo",
            "is_active", "is_staff", "is_superuser", "password", "creado",
        ]
        read_only_fields = ["creado", "is_staff", "is_superuser"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        usuario = Usuario(**validated_data)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
