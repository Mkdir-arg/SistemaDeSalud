from rest_framework import serializers

from .models import LegajoProfesional, Membresia, Usuario


class LegajoProfesionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = LegajoProfesional
        fields = ["id", "usuario", "especialidad", "matricula"]


class MembresiaSerializer(serializers.ModelSerializer):
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)

    class Meta:
        model = Membresia
        fields = ["id", "usuario", "institucion", "rol", "rol_display", "areas", "activo", "creado"]
        read_only_fields = ["creado"]


class UsuarioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})

    class Meta:
        model = Usuario
        fields = [
            "id", "email", "nombre", "apellido", "nombre_completo",
            "is_active", "is_staff", "is_superuser", "password", "creado",
        ]
        read_only_fields = ["creado", "is_superuser"]

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
