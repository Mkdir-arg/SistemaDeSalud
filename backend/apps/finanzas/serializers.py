from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import TypedDict
from uuid import uuid4

from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db.models import F
from django.utils import timezone
from apps.accounts.models import Membresia

from .models import AjusteCosto, AjusteGasto, ConceptoGasto, ConcesionFinanciera, CorreccionSnapshotCosteo, DefinicionComponente, EstadoAprobacion, Gasto, HechoAtencionCosteable, Prestacion, TrabajoReparto, ValorComponente


CAMPOS_APROBACION = ["estado", "aprobado_por", "aprobado_en", "rechazado_por", "rechazado_en", "motivo_rechazo"]


def _decision_serializada(obj):
    return {
        "estado": obj.estado, "aprobado": obj.estado == EstadoAprobacion.APROBADO,
        "aprobado_por": obj.aprobado_por_id, "aprobado_en": obj.aprobado_en,
        "rechazado_por": obj.rechazado_por_id, "rechazado_en": obj.rechazado_en,
        "motivo_rechazo": obj.motivo_rechazo,
    }


class DetalleAjusteGasto(TypedDict):
    id: int
    importe: str
    motivo: str
    registrado_por: int | None
    registrado: datetime


class FaltanteCosto(TypedDict):
    motivo: str
    motivo_display: str
    componente: int | None
    componente_codigo: str | None


class AlcanceCosto(TypedDict):
    incluye: list[str]
    pendiente_de_integracion: list[str]


class DetalleAjusteCosto(TypedDict):
    id: int
    importe: str
    moneda: str
    motivo: str
    registrado: datetime
    registrado_por: int | None
    area: int | None
    sensible: bool


class DetalleImputacionCosto(TypedDict):
    componente: int
    componente_codigo: str
    componente_nombre: str
    importe: str
    unidad: str
    base_calculo: str
    moneda: str
    ajustes: list[DetalleAjusteCosto]


class ConcesionFinancieraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConcesionFinanciera
        fields = [
            "id", "membresia", "accion", "todas_las_areas", "permite_sensibles", "areas",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        membresia = attrs.get("membresia", getattr(self.instance, "membresia", None))
        todas_las_areas = attrs.get(
            "todas_las_areas", getattr(self.instance, "todas_las_areas", False)
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
        if membresia and not membresia.activo:
            raise serializers.ValidationError({"membresia": "La membresía debe estar activa."})
        return attrs


class ConcesionesMultiplesSerializer(serializers.Serializer):
    membresia = serializers.PrimaryKeyRelatedField(queryset=Membresia.objects.all())
    acciones = serializers.ListField(
        child=serializers.ChoiceField(choices=ConcesionFinanciera.Accion.choices),
        allow_empty=False, max_length=len(ConcesionFinanciera.Accion.values),
    )
    todas_las_areas = serializers.BooleanField(default=False)
    permite_sensibles = serializers.BooleanField(default=False)
    areas = ConcesionFinancieraSerializer().fields["areas"]

    def validate_acciones(self, acciones):
        if len(acciones) != len(set(acciones)):
            raise serializers.ValidationError("No repitas acciones financieras.")
        return acciones


class CatalogoConCodigoSerializer(serializers.ModelSerializer):
    """Genera referencias internas sólo en altas; conserva las manuales."""

    codigo = serializers.CharField(max_length=60, required=False)

    def to_internal_value(self, data):
        if self.instance is None and isinstance(data, Mapping):
            codigo = data.get("codigo", serializers.empty)
            if codigo is serializers.empty or (isinstance(codigo, str) and not codigo.strip()):
                data = data.copy()
                # UUID evita una secuencia calculada por COUNT/MAX que colisione
                # con altas simultáneas. La restricción única del catálogo sigue
                # validándose, incluidos los códigos ingresados manualmente.
                data["codigo"] = f"{self.prefijo_codigo}-{uuid4().hex.upper()}"
        return super().to_internal_value(data)


class PrestacionSerializer(CatalogoConCodigoSerializer):
    prefijo_codigo = "PRE"

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


class DefinicionComponenteSerializer(CatalogoConCodigoSerializer):
    prefijo_codigo = "CMP"

    class Meta:
        model = DefinicionComponente
        fields = [
            "id", "prestacion", "codigo", "nombre", "fuente", "unidad", "base_calculo",
            "activo", "sensible", "orden",
        ]
        read_only_fields = ["id"]


class ConceptoGastoSerializer(CatalogoConCodigoSerializer):
    prefijo_codigo = "GAS"

    class Meta:
        model = ConceptoGasto
        fields = [
            "id", "institucion", "codigo", "nombre", "activo", "sensible",
            "registrado_por", "registrado",
        ]
        read_only_fields = ["id", "registrado_por", "registrado"]


class ValorComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValorComponente
        fields = [
            "id", "componente", "importe", "moneda", "vigente_desde", "vigente_hasta", "fuente",
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
    aprobado = serializers.BooleanField(required=False)
    institucion = serializers.IntegerField(source="imputacion.hecho.institucion_id", read_only=True)
    area = serializers.IntegerField(source="imputacion.hecho.area_origen_id", read_only=True, allow_null=True)
    sensible = serializers.SerializerMethodField()

    @staticmethod
    def get_sensible(obj) -> bool:
        from .services import _hecho_sensible
        return _hecho_sensible(obj.imputacion.hecho)

    class Meta:
        model = AjusteCosto
        fields = ["id", "imputacion", "importe", "motivo", "registrado_por", "registrado", "institucion", "area", "sensible", "aprobado", *CAMPOS_APROBACION]
        read_only_fields = ["id", "registrado_por", "registrado", "institucion", "area", "sensible", *CAMPOS_APROBACION]


class AjusteGastoSerializer(serializers.ModelSerializer):
    aprobado = serializers.BooleanField(required=False)
    institucion = serializers.IntegerField(source="gasto.institucion_id", read_only=True)
    area = serializers.IntegerField(source="gasto.area_id", read_only=True, allow_null=True)
    sensible = serializers.BooleanField(source="gasto.sensible", read_only=True)
    periodo_economico = serializers.DateField(source="gasto.periodo_economico", read_only=True)

    class Meta:
        model = AjusteGasto
        fields = ["id", "gasto", "importe", "motivo", "registrado_por", "registrado", "institucion", "area", "sensible", "periodo_economico", "aprobado", *CAMPOS_APROBACION]
        read_only_fields = ["id", "registrado_por", "registrado", "institucion", "area", "sensible", "periodo_economico", *CAMPOS_APROBACION]


class GastoSerializer(serializers.ModelSerializer):
    aprobado = serializers.BooleanField(required=False)
    cuenta_por_pagar = serializers.IntegerField(read_only=True, default=None)
    area_nombre = serializers.CharField(source="area.nombre", read_only=True, default=None)
    reemplazado_por = serializers.SerializerMethodField()
    estado_operativo = serializers.SerializerMethodField()
    ajustes = serializers.SerializerMethodField()
    total_ajustes = serializers.SerializerMethodField()
    importe_resultante = serializers.SerializerMethodField()

    class Meta:
        model = Gasto
        fields = [
            "id", "concepto", "concepto_codigo", "concepto_nombre", "institucion", "area", "area_nombre",
            "importe", "moneda", "periodo_economico", "origen", "estado", "estado_operativo",
            "sensible", "registrado_por", "registrado", "aprobado_por", "aprobado_en",
            "rechazado_por", "rechazado_en", "motivo_rechazo", "reemplaza", "reemplazado_por",
            "ajustes", "total_ajustes", "importe_resultante", "aprobado", "cuenta_por_pagar",
        ]
        read_only_fields = [
            "id", "concepto_codigo", "concepto_nombre", "moneda", "origen", "estado",
            "estado_operativo", "sensible", "registrado_por", "registrado", "aprobado_por",
            "aprobado_en", "rechazado_por", "rechazado_en", "motivo_rechazo", "reemplazado_por",
            "ajustes", "total_ajustes", "importe_resultante",
        ]

    @staticmethod
    def get_reemplazado_por(obj) -> int | None:
        try:
            return obj.reemplazado_por.id
        except ObjectDoesNotExist:
            return None

    def get_estado_operativo(self, obj) -> str:
        return "reemplazado" if self.get_reemplazado_por(obj) is not None else obj.estado

    @staticmethod
    def _total_ajustes(obj):
        if hasattr(obj, "total_ajustes"):
            return obj.total_ajustes
        return sum((ajuste.importe for ajuste in obj.ajustes.all() if ajuste.estado == EstadoAprobacion.APROBADO), Decimal("0.00"))

    def get_total_ajustes(self, obj) -> str:
        return format(self._total_ajustes(obj), ".2f")

    def get_importe_resultante(self, obj) -> str:
        return format(obj.importe + self._total_ajustes(obj), ".2f")

    @staticmethod
    def get_ajustes(obj) -> list[DetalleAjusteGasto]:
        return [
            {
                "id": ajuste.id,
                "importe": str(ajuste.importe),
                "motivo": ajuste.motivo,
                "registrado_por": ajuste.registrado_por_id,
                "registrado": ajuste.registrado,
                **_decision_serializada(ajuste),
            }
            for ajuste in obj.ajustes.all()
        ]


class RechazoGastoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255)


class CorreccionSnapshotCosteoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CorreccionSnapshotCosteo
        fields = ["id", "hecho", "motivo", "registrado_por", "registrado"]
        read_only_fields = ["id", "hecho", "registrado_por", "registrado"]


class HechoAtencionCosteableSerializer(serializers.ModelSerializer):
    """Detalle económico sin narrativa ni valores clínicos del paciente."""

    total_conocido = serializers.SerializerMethodField()
    total_directo_es_completo = serializers.SerializerMethodField()
    total_es_completo = serializers.SerializerMethodField()
    estado_costo = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()
    alcance = serializers.SerializerMethodField()
    imputaciones = serializers.SerializerMethodField()
    limite = serializers.SerializerMethodField()
    moneda = serializers.SerializerMethodField()
    total_compartido_conocido = serializers.SerializerMethodField()
    repartos_compartidos = serializers.SerializerMethodField()
    reparto_actualizando = serializers.SerializerMethodField()
    actualizado_en = serializers.DateTimeField(source="ultimo_costeo_en", read_only=True)

    class Meta:
        model = HechoAtencionCosteable
        fields = [
            "id", "institucion", "caso", "ciudadano", "area", "ocurrida_en",
            "actualizado_en", "total_conocido", "total_directo_es_completo", "total_es_completo",
            "estado_costo", "faltantes", "alcance", "moneda",
            "imputaciones", "limite", "total_compartido_conocido", "repartos_compartidos", "reparto_actualizando",
        ]
        read_only_fields = fields

    @staticmethod
    def get_reparto_actualizando(obj) -> bool:
        # Incluye fuentes recién registradas que todavía no tienen atribución.
        if hasattr(obj, "reparto_actualizando"):
            return obj.reparto_actualizando
        return TrabajoReparto.objects.filter(
            gasto__institucion_id=obj.institucion_id, gasto__area_id=obj.area_origen_id,
            gasto__periodo_economico=timezone.localtime(obj.ocurrida_en).date().replace(day=1),
            gasto__reemplazado_por__isnull=True, revision__gt=F("revision_procesada"),
        ).exists()

    @staticmethod
    def _atribuciones_vigentes(obj):
        vigentes = []
        for atribucion in obj.atribuciones_reparto.all():
            try:
                atribucion.reparto.reemplazado_por
            except ObjectDoesNotExist:
                vigentes.append(atribucion)
        return vigentes

    @classmethod
    def get_total_compartido_conocido(cls, obj) -> str:
        centavos = sum(a.importe_centavos for a in cls._atribuciones_vigentes(obj))
        return str((Decimal(centavos) / Decimal("100")).quantize(Decimal("0.01")))

    @classmethod
    def get_repartos_compartidos(cls, obj) -> list[dict]:
        return [
            {
                "reparto": atribucion.reparto_id,
                "version": atribucion.reparto.version,
                "gasto": atribucion.reparto.gasto_id,
                "concepto": atribucion.reparto.gasto.concepto_nombre,
                "periodo_economico": atribucion.reparto.gasto.periodo_economico,
                "importe": str(
                    (Decimal(atribucion.importe_centavos) / Decimal("100")).quantize(Decimal("0.01"))
                ),
                "moneda": "ARS",
            }
            for atribucion in cls._atribuciones_vigentes(obj)
        ]

    @staticmethod
    def _pendientes(obj):
        return [p for p in obj.pendientes.all() if not p.resuelto]

    def get_total_conocido(self, obj) -> str | None:
        imputaciones = list(obj.imputaciones.all())
        if not imputaciones:
            return None
        # Igual que `importe` en las imputaciones: texto decimal para no perder
        # precisión al cruzar JSON, y `null` reservado para lo desconocido.
        total = sum((imputacion.importe for imputacion in imputaciones), start=0)
        total += sum(
            (ajuste.importe for imputacion in imputaciones for ajuste in imputacion.ajustes.all() if ajuste.estado == EstadoAprobacion.APROBADO),
            start=0,
        )
        return str(total)

    @staticmethod
    def get_moneda(_obj) -> str:
        return ValorComponente.Moneda.ARS

    def get_total_directo_es_completo(self, obj) -> bool:
        componentes_esperados = {
            esperado.componente_id for esperado in obj.componentes_esperados.all()
        }
        componentes_imputados = {
            imputacion.componente_id for imputacion in obj.imputaciones.all()
        }
        return (
            bool(componentes_esperados)
            and componentes_esperados <= componentes_imputados
            and not self._pendientes(obj)
        )

    @staticmethod
    def get_total_es_completo(_obj) -> bool:
        # Los gastos compartidos y otras fuentes todavía no integradas impiden
        # declarar un costo total de paciente en este incremento.
        return False

    def get_estado_costo(self, obj) -> str:
        return "parcial" if obj.imputaciones.all() else "pendiente"

    def get_faltantes(self, obj) -> list[FaltanteCosto]:
        faltantes = [
            {
                "motivo": pendiente.motivo,
                "motivo_display": pendiente.get_motivo_display(),
                "componente": pendiente.componente_id,
                "componente_codigo": pendiente.componente.codigo if pendiente.componente_id else None,
            }
            for pendiente in self._pendientes(obj)
        ]
        faltantes.append(
            {
                "motivo": "fuentes_no_integradas",
                "motivo_display": "Fuentes de costo aún no integradas",
                "componente": None,
                "componente_codigo": None,
            }
        )
        return faltantes

    @staticmethod
    def get_alcance(_obj) -> AlcanceCosto:
        return {
            "incluye": ["componentes_directos_configurados", "gastos_compartidos_atribuidos"],
            "pendiente_de_integracion": ["otras_fuentes_de_costo"],
        }

    def get_imputaciones(self, obj) -> list[DetalleImputacionCosto]:
        # Mismo alcance que la decisión del servicio; reutiliza el prefetch
        # del hecho, sin consultar un endpoint por cada ajuste del historial.
        sensible = any(c.sensible for c in obj.componentes_esperados.all()) or any(
            a.reparto.gasto.sensible for a in self._atribuciones_vigentes(obj)
        )
        return [
            {
                "componente": imputacion.componente_id,
                "componente_codigo": imputacion.componente.codigo,
                "componente_nombre": imputacion.componente.nombre,
                "importe": str(imputacion.importe),
                "unidad": imputacion.unidad,
                "base_calculo": imputacion.base_calculo,
                "moneda": imputacion.moneda,
                "ajustes": [
                    {
                        "id": ajuste.id,
                        "importe": str(ajuste.importe),
                        "moneda": imputacion.moneda,
                        "motivo": ajuste.motivo,
                        "registrado": ajuste.registrado,
                        "registrado_por": ajuste.registrado_por_id,
                        "area": obj.area_origen_id,
                        "sensible": sensible,
                        **_decision_serializada(ajuste),
                    }
                    for ajuste in imputacion.ajustes.all()
                ],
            }
            for imputacion in obj.imputaciones.all()
        ]

    @staticmethod
    def get_limite(_obj) -> str:
        return "Componentes directos configurados y gastos compartidos atribuidos; no es el costo total del hospital ni incluye aranceles, cargos o dinero cobrado."
