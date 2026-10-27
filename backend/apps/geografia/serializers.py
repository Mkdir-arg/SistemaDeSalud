from django.db import transaction
from rest_framework import serializers

from .servicios import ambito, resolver


class CampoGeografia(serializers.JSONField):
    def to_representation(self, value):
        return value.datos()


class DomicilioSerializerMixin:
    """Integra el catálogo al guardado ya autorizado, sin endpoint de escritura global."""
    def get_fields(self):
        campos = super().get_fields()
        if getattr(self, "ocultar_geografia", False):
            campos.pop("geografia", None)
        return campos

    @transaction.atomic
    def create(self, validated_data):
        entrada = validated_data.pop("geografia", None)
        obj = super().create(validated_data)
        if entrada is not None:
            dueno = ambito(institucion_id=obj.pk if obj._meta.model_name == "institucion" else obj.institucion_id)
            obj.geografia = resolver(entrada, dueno=dueno)
            obj.save(update_fields=["geografia"])
        return obj

    @transaction.atomic
    def update(self, instance, validated_data):
        instancia = type(instance).objects.select_for_update().get(pk=instance.pk)
        entrada = validated_data.pop("geografia", serializers.empty)
        texto = "direccion" if instancia._meta.model_name == "institucion" else "domicilio"
        if entrada is not serializers.empty:
            if entrada is None:
                raise serializers.ValidationError({"geografia": "Usá selecciones vacías explícitas para retirar la ubicación."})
            dueno = ambito(institucion_id=instancia.pk if instancia._meta.model_name == "institucion" else instancia.institucion_id)
            instancia.geografia = resolver(entrada, dueno=dueno, anterior=instancia.geografia)
        elif texto in validated_data and validated_data[texto] != getattr(instancia, texto):
            # Un escritor textual anterior no puede dejar referencias territoriales falsas.
            instancia.geografia = None
        return super().update(instancia, validated_data)
