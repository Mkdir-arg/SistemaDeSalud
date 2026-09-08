from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import AjusteCosto, ConcesionFinanciera, DefinicionComponente, HechoAtencionCosteable, Prestacion, ValorComponente


class ConcesionFinancieraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConcesionFinanciera
        fields = [
            "id", "membresia", "accion", "todas_las_areas", "permite_sensibles", "areas",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        membresia = attrs.get("membresia", getattr(self.instance, "membresia", None))
        accion = attrs.get("accion", getattr(self.instance, "accion", None))
        todas_las_areas = attrs.get(
            "todas_las_areas", getattr(self.instance, "todas_las_areas", False)
        )
        permite_sensibles = attrs.get(
            "permite_sensibles", getattr(self.instance, "permite_sensibles", False)
        )
        areas = attrs.get("areas")
        if areas is None and self.instance is not None:
            areas = self.instance.areas.all()

        if membresia and areas:
            fuera = [area.id for area in areas if area.institucion_id != membresia.institucion_id]
            if fuera:
                raise serializers.ValidationError(
                    {"areas": "Todas las áreas deben pertenecer a la institución de la membresía."}
                )
        if todas_las_areas and areas:
            raise serializers.ValidationError(
                {"areas": "No indiques áreas si la concesión alcanza a toda la institución."}
            )
        if not todas_las_areas and not areas:
            raise serializers.ValidationError(
                {"areas": "Indicá al menos un área o marcá alcance para toda la institución."}
            )
        if membresia and (
            accion in {
                ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
                ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            }
            or permite_sensibles
        ) and membresia.rol != "admin":
            raise serializers.ValidationError(
                {"membresia": "Esta acción requiere una membresía administrativa."}
            )
        return attrs


class PrestacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prestacion
        fields = ["id", "institucion", "nodo", "codigo", "nombre", "activo"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        institucion = attrs.get("institucion", getattr(self.instance, "institucion", None))
        nodo = attrs.get("nodo", getattr(self.instance, "nodo", None))
        if nodo and institucion and nodo.version.flujo.institucion_id != institucion.id:
            raise serializers.ValidationError(
                {"nodo": "El nodo debe pertenecer a la institución de la prestación."}
            )
        return attrs


class DefinicionComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DefinicionComponente
        fields = ["id", "prestacion", "codigo", "nombre", "fuente", "activo", "orden"]
        read_only_fields = ["id"]


class ValorComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValorComponente
        fields = [
            "id", "componente", "importe", "vigente_desde", "vigente_hasta", "fuente",
            "registrado_por", "registrado", "reemplaza", "motivo_correccion",
        ]
        read_only_fields = ["id", "registrado_por", "registrado"]

    def validate(self, attrs):
        candidato = ValorComponente(
            componente=attrs.get("componente"),
            importe=attrs.get("importe"),
            vigente_desde=attrs.get("vigente_desde"),
            vigente_hasta=attrs.get("vigente_hasta"),
            fuente=attrs.get("fuente", ""),
            reemplaza=attrs.get("reemplaza"),
            motivo_correccion=attrs.get("motivo_correccion", ""),
        )
        try:
            candidato.full_clean()
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.message_dict) from error
        return attrs


class AjusteCostoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AjusteCosto
        fields = ["id", "imputacion", "importe", "motivo", "registrado_por", "registrado"]
        read_only_fields = ["id", "registrado_por", "registrado"]


class HechoAtencionCosteableSerializer(serializers.ModelSerializer):
    """Detalle económico sin narrativa ni valores clínicos del paciente."""

    total_conocido = serializers.SerializerMethodField()
    total_es_completo = serializers.SerializerMethodField()
    estado_costo = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()
    imputaciones = serializers.SerializerMethodField()
    limite = serializers.SerializerMethodField()

    class Meta:
        model = HechoAtencionCosteable
        fields = [
            "id", "institucion", "caso", "ciudadano", "area", "ocurrida_en",
            "total_conocido", "total_es_completo", "estado_costo", "faltantes",
            "imputaciones", "limite",
        ]
        read_only_fields = fields

    @staticmethod
    def _pendientes(obj):
        return [p for p in obj.pendientes.all() if not p.resuelto]

    def get_total_conocido(self, obj):
        imputaciones = list(obj.imputaciones.all())
        if not imputaciones:
            return None
        # Igual que `importe` en las imputaciones: texto decimal para no perder
        # precisión al cruzar JSON, y `null` reservado para lo desconocido.
        total = sum((imputacion.importe for imputacion in imputaciones), start=0)
        total += sum(
            (ajuste.importe for imputacion in imputaciones for ajuste in imputacion.ajustes.all()),
            start=0,
        )
        return str(total)

    def get_total_es_completo(self, obj):
        return bool(obj.componentes_esperados.all()) and not self._pendientes(obj)

    def get_estado_costo(self, obj):
        pendientes = self._pendientes(obj)
        if pendientes:
            return "parcial" if obj.imputaciones.all() else "pendiente"
        return "disponible" if obj.componentes_esperados.all() else "pendiente"

    def get_faltantes(self, obj):
        return [
            {
                "motivo": pendiente.motivo,
                "motivo_display": pendiente.get_motivo_display(),
                "componente": pendiente.componente_id,
                "componente_codigo": pendiente.componente.codigo if pendiente.componente_id else None,
            }
            for pendiente in self._pendientes(obj)
        ]

    def get_imputaciones(self, obj):
        return [
            {
                "componente": imputacion.componente_id,
                "componente_codigo": imputacion.componente.codigo,
                "componente_nombre": imputacion.componente.nombre,
                "importe": str(imputacion.importe),
                "ajustes": [
                    {
                        "id": ajuste.id,
                        "importe": str(ajuste.importe),
                        "motivo": ajuste.motivo,
                        "registrado": ajuste.registrado,
                    }
                    for ajuste in imputacion.ajustes.all()
                ],
            }
            for imputacion in obj.imputaciones.all()
        ]

    @staticmethod
    def get_limite(_obj):
        return "Sólo componentes directos configurados; no incluye aranceles, cargos ni dinero cobrado."
