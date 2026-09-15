"""Contrato del checklist institucional; cada acción conserva su propio alcance."""
import hashlib
import json

from rest_framework import serializers

from .models import ConcesionFinanciera


class AccionEditorSerializer(serializers.Serializer):
    accion = serializers.ChoiceField(choices=ConcesionFinanciera.Accion.choices)
    todas_las_areas = serializers.BooleanField()
    permite_sensibles = serializers.BooleanField()
    areas = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=500)

    def validate_areas(self, areas):
        if len(areas) != len(set(areas)):
            raise serializers.ValidationError("No repitas áreas en un permiso.")
        return areas


class EditorPermisosSerializer(serializers.Serializer):
    membresia = serializers.IntegerField(min_value=1)
    version_esperada = serializers.CharField(min_length=64, max_length=64)
    concesiones = AccionEditorSerializer(many=True, max_length=len(ConcesionFinanciera.Accion.values))

    def validate_concesiones(self, concesiones):
        acciones = [concesion["accion"] for concesion in concesiones]
        if len(acciones) != len(set(acciones)):
            raise serializers.ValidationError("No repitas acciones financieras.")
        return concesiones


def version_editor(membresia, concesiones, heredadas):
    """La huella incluye IDs para detectar revocar y volver a otorgar (A→B→A)."""
    estado = {
        "membresia": [membresia.id, membresia.usuario_id, membresia.institucion_id,
                      membresia.rol, membresia.activo],
        "heredadas": sorted(heredadas),
        "concesiones": sorted(({
            "id": fila["id"], "accion": fila["accion"],
            "todas_las_areas": fila["todas_las_areas"],
            "permite_sensibles": fila["permite_sensibles"], "areas": sorted(fila["areas"]),
        } for fila in concesiones), key=lambda fila: fila["accion"]),
    }
    return hashlib.sha256(json.dumps(estado, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
