"""API mínima de configuración y explicación del reparto por actividad."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db.models import Count, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.common import BaseModelViewSet, OrdenEstable, tiene_capacidad
from apps.instituciones.models import Area, Institucion

from .auditoria import AuditaLecturaFinanciera
from .models import (
    AtribucionReparto,
    CoberturaActividadCosteable,
    ConceptoGasto,
    ConcesionFinanciera,
    Gasto,
    HechoAtencionCosteable,
    ReglaRepartoActividad,
    RepartoGasto,
)
from .permisos import concesiones_financieras_de, hechos_en_alcance_financiero, tiene_concesion_financiera, tiene_accion_financiera, alcance_financiero_q
from .filtros import filtrar_rangos, filtrar_tabla
from .services import registrar_cobertura_actividad, registrar_regla_reparto, resumen_actividad_reparto


class PuedeConfigurarRepartos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or concesiones_financieras_de(
                    usuario, ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
                ).exists()
            )
        )


class PuedeVerRepartos(BasePermission):
    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario and usuario.is_authenticated and (
                usuario.is_superuser
                or tiene_accion_financiera(usuario, ConcesionFinanciera.Accion.VER_GASTOS)
            )
        )


def _alcance(queryset, usuario, accion, *, sensible_path=None):
    return queryset.filter(alcance_financiero_q(usuario, accion, sensible_path=sensible_path)).distinct()


def _filtrar_vigencia(queryset, valor, *, relacion_sucesora="reemplazado_por"):
    filtro = {f"{relacion_sucesora}__isnull": valor in {"1", "true", "True"}}
    if valor in {"1", "true", "True"}:
        return queryset.filter(**filtro)
    if valor in {"0", "false", "False"}:
        filtro[f"{relacion_sucesora}__isnull"] = False
        return queryset.filter(**filtro)
    return queryset


class VerificacionActividadEntradaSerializer(serializers.Serializer):
    institucion = serializers.PrimaryKeyRelatedField(queryset=Institucion.objects.all())
    area = serializers.PrimaryKeyRelatedField(queryset=Area.objects.all())
    periodo_economico = serializers.DateField()
    incluir_importes = serializers.BooleanField(required=False, default=True)
    concepto = serializers.PrimaryKeyRelatedField(
        queryset=ConceptoGasto.objects.all(), required=False, allow_null=True,
    )

    def validate(self, attrs):
        if attrs["periodo_economico"].day != 1:
            raise serializers.ValidationError("Indicá el primer día del mes (AAAA-MM-01).")
        if attrs["area"].institucion_id != attrs["institucion"].id:
            raise serializers.ValidationError("El área debe pertenecer a la institución elegida.")
        concepto = attrs.get("concepto")
        if concepto and concepto.institucion_id != attrs["institucion"].id:
            raise serializers.ValidationError("El concepto debe pertenecer a la institución elegida.")
        return attrs


class CoberturaActividadSerializer(serializers.ModelSerializer):
    sensible = serializers.SerializerMethodField()
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)
    confirmacion_operativa = serializers.BooleanField(write_only=True)

    class Meta:
        model = CoberturaActividadCosteable
        fields = [
            "id", "institucion", "area", "area_nombre", "vigente_desde", "vigente_hasta",
            "reemplaza", "motivo_correccion", "registrado_por", "registrado", "sensible",
            "confirmacion_operativa",
        ]
        read_only_fields = ["id", "registrado_por", "registrado", "sensible"]

    @staticmethod
    def get_sensible(obj) -> bool:
        return False

    def create(self, validated_data):
        confirmacion_operativa = validated_data.pop("confirmacion_operativa")
        try:
            return registrar_cobertura_actividad(
                registrado_por=self.context["request"].user,
                confirmacion_operativa=confirmacion_operativa,
                **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                getattr(error, "message_dict", error.messages)
            ) from error


class ReglaRepartoSerializer(serializers.ModelSerializer):
    concepto_nombre = serializers.CharField(source="concepto.nombre", read_only=True)
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)

    class Meta:
        model = ReglaRepartoActividad
        fields = [
            "id", "concepto", "concepto_nombre", "institucion", "area", "area_nombre",
            "vigente_desde", "vigente_hasta",
            "sensible", "reemplaza", "motivo_correccion", "registrado_por", "registrado",
        ]
        read_only_fields = ["id", "sensible", "registrado_por", "registrado"]

    def create(self, validated_data):
        try:
            return registrar_regla_reparto(
                registrado_por=self.context["request"].user, **validated_data,
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                getattr(error, "message_dict", error.messages)
            ) from error


class RepartoGastoSerializer(serializers.ModelSerializer):
    institucion = serializers.IntegerField(source="gasto.institucion_id", read_only=True)
    area = serializers.IntegerField(source="gasto.area_id", read_only=True)
    area_nombre = serializers.CharField(source="gasto.area.nombre", read_only=True, default=None)
    concepto = serializers.IntegerField(source="gasto.concepto_id", read_only=True)
    concepto_nombre = serializers.CharField(source="gasto.concepto.nombre", read_only=True)
    periodo_economico = serializers.DateField(source="gasto.periodo_economico", read_only=True)
    sensible = serializers.BooleanField(source="gasto.sensible", read_only=True)
    atribuciones = serializers.IntegerField(source="cantidad_atribuciones", read_only=True)
    vigente = serializers.SerializerMethodField()
    actualizando = serializers.SerializerMethodField()
    saldo_no_atribuido_centavos = serializers.IntegerField(source="saldo_sin_distribuir", read_only=True)

    class Meta:
        model = RepartoGasto
        fields = [
            "id", "gasto", "concepto", "concepto_nombre", "institucion", "area", "area_nombre",
            "periodo_economico",
            "sensible", "regla", "cobertura", "version", "estado", "motivo",
            "importe_fuente_centavos", "importe_ajustes_centavos", "saldo_centavos",
            "saldo_no_atribuido_centavos", "atribuciones", "reemplaza", "vigente", "calculado", "actualizando",
        ]
        read_only_fields = fields

    @staticmethod
    def get_actualizando(obj) -> bool:
        try:
            trabajo = obj.gasto.trabajo_reparto
        except ObjectDoesNotExist:
            return False
        return trabajo.revision > trabajo.revision_procesada

    @staticmethod
    def get_vigente(obj) -> bool:
        try:
            obj.reemplazado_por
        except ObjectDoesNotExist:
            return True
        return False


class CoberturaActividadViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = CoberturaActividadCosteable.objects.select_related("institucion", "area", "reemplaza")
    serializer_class = CoberturaActividadSerializer
    permission_classes = [IsAuthenticated, PuedeConfigurarRepartos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        queryset = _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        )
        return _filtrar_vigencia(
            queryset,
            self.request.query_params.get("vigente"),
            relacion_sucesora="reemplazada_por",
        )

    @action(detail=False, methods=["get"])
    def verificacion(self, request):
        entrada = VerificacionActividadEntradaSerializer(data=request.query_params)
        entrada.is_valid(raise_exception=True)
        institucion = entrada.validated_data["institucion"]
        area = entrada.validated_data["area"]
        concepto = entrada.validated_data.get("concepto")
        sensible = bool(concepto and concepto.sensible)
        incluir_importes = entrada.validated_data["incluir_importes"]
        acciones = [ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS]
        if incluir_importes:
            acciones.append(ConcesionFinanciera.Accion.VER_GASTOS)
        if not all(tiene_concesion_financiera(
            request.user, accion, institucion.id, area.id, sensible=sensible,
        ) for accion in acciones):
            raise PermissionDenied("Necesitás permiso para configurar repartos y consultar gastos de esta área.")
        # El resumen sin concepto también puede contener gastos sensibles: ambas
        # capacidades deben permitirlos en esta misma institución y área.
        incluir_sensibles = incluir_importes and (sensible or (concepto is None and all(tiene_concesion_financiera(
            request.user, accion, institucion.id, area.id, sensible=True,
        ) for accion in acciones)))
        resumen = resumen_actividad_reparto(
            institucion_id=institucion.id,
            area_id=area.id,
            periodo=entrada.validated_data["periodo_economico"],
            concepto_id=concepto.id if concepto else None,
            incluir_sensibles=incluir_sensibles,
            incluir_importes=incluir_importes,
        )
        # Contexto ya validado y autorizado; auditar antes de entregar totales.
        # Es un resumen, no una lectura de una cobertura concreta.
        resumen.update(
            institucion=institucion.pk, area=area.pk, sensible=incluir_sensibles,
            periodo_economico=entrada.validated_data["periodo_economico"].isoformat(),
        )
        return self.auditar_respuesta(Response(resumen))


class ReglaRepartoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = ReglaRepartoActividad.objects.select_related(
        "concepto", "institucion", "area", "reemplaza",
    )
    serializer_class = ReglaRepartoSerializer
    permission_classes = [IsAuthenticated, PuedeConfigurarRepartos]
    institucion_path = "institucion"
    http_method_names = ["get", "head", "options", "post"]
    filter_fields = ("institucion", "area", "concepto", "sensible")
    ordering_fields = ("vigente_desde", "registrado", "id")

    def get_queryset(self):
        queryset = _alcance(
            super().get_queryset(), self.request.user,
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            sensible_path="sensible",
        )
        return _filtrar_vigencia(
            queryset,
            self.request.query_params.get("vigente"),
            relacion_sucesora="reemplazada_por",
        )


class OrdenRepartos(OrdenEstable):
    def get_ordering(self, request, queryset, view):
        orden = super().get_ordering(request, queryset, view)
        return [campo.replace("saldo_no_atribuido_centavos", "saldo_sin_distribuir") for campo in orden] if orden else orden


class RepartoGastoViewSet(AuditaLecturaFinanciera, BaseModelViewSet):
    queryset = RepartoGasto.objects.select_related(
        "gasto", "gasto__concepto", "gasto__area", "regla", "cobertura", "reemplaza", "gasto__trabajo_reparto",
        "reemplazado_por",
    ).annotate(cantidad_atribuciones=Coalesce(Subquery(
        AtribucionReparto.objects.filter(reparto_id=OuterRef("pk")).order_by().values(
            "reparto_id",
        ).annotate(cantidad=Count("pk")).values("cantidad")[:1],
    ), Value(0))).annotate(saldo_sin_distribuir=F("saldo_centavos") - Coalesce(Subquery(
        AtribucionReparto.objects.filter(reparto_id=OuterRef("pk")).order_by().values(
            "reparto_id",
        ).annotate(total=Sum("importe_centavos")).values("total")[:1],
    ), Value(0)))
    serializer_class = RepartoGastoSerializer
    filter_backends = [OrdenRepartos, SearchFilter]
    permission_classes = [IsAuthenticated, PuedeVerRepartos]
    institucion_path = "gasto__institucion"
    http_method_names = ["get", "head", "options"]
    filter_fields = (
        "gasto", "gasto__institucion", "gasto__area", "gasto__periodo_economico",
        "gasto__concepto", "estado", "motivo",
    )
    ordering_fields = (
        "calculado", "version", "id", "gasto", "gasto__concepto__nombre", "gasto__area__nombre",
        "gasto__periodo_economico",
        "estado", "motivo", "saldo_centavos", "saldo_no_atribuido_centavos",
        "importe_fuente_centavos", "importe_ajustes_centavos", "cantidad_atribuciones",
    )

    @property
    def search_fields(self):
        return ("gasto__concepto_nombre", "gasto__area__nombre") if self.action == "list" else ()

    def filter_queryset(self, queryset):
        # El nombre público se conserva; listado, filtro y orden usan el mismo
        # saldo derivado que el detalle, también para versiones preexistentes.
        parametros = self.request.query_params.copy()
        if "sin_distribuir" in parametros:
            if parametros["sin_distribuir"] != "true":
                raise serializers.ValidationError({"sin_distribuir": "Usá true para consultar fuentes aprobadas con saldo sin distribuir."})
            # Mismo universo del resumen: no incluir pendientes/rechazados ni
            # eliminar saldos negativos de correcciones legítimas.
            queryset = queryset.filter(gasto__estado=Gasto.Estado.APROBADO, gasto__reemplazado_por__isnull=True).exclude(saldo_sin_distribuir=0)
        for limite in ("min", "max"):
            clave = f"saldo_no_atribuido_centavos_{limite}"
            if clave in parametros:
                parametros[f"saldo_sin_distribuir_{limite}"] = parametros[clave]
        queryset = filtrar_rangos(
            queryset, parametros,
            cantidades=(
                "saldo_centavos", "saldo_sin_distribuir", "cantidad_atribuciones",
                "importe_fuente_centavos", "importe_ajustes_centavos", "version",
            ),
            fechas=("calculado",),
        )
        return super().filter_queryset(queryset)

    @action(detail=True, methods=["get"])
    def atribuciones(self, request, pk=None):
        reparto = self.get_object()
        hechos_visibles = hechos_en_alcance_financiero(
            HechoAtencionCosteable.objects.all(), request.user,
        ).values("pk")
        atribuciones = reparto.atribuciones.select_related(
            "hecho__area", "hecho__caso__version__flujo", "hecho__nodo",
        ).order_by("hecho_id", "id")
        # No devolver una parte que se confunda con el total del reparto. El
        # detalle respeta el mismo permiso de hecho completo que hechos-costo.
        if atribuciones.exclude(hecho_id__in=hechos_visibles).exists():
            raise PermissionDenied(
                "No tenés autorización para ver el detalle de las atenciones de este reparto.",
            )
        importe_atribuido = atribuciones.aggregate(total=Sum("importe_centavos"))["total"] or 0
        atribuciones = filtrar_tabla(
            atribuciones, request,
            ordenables=("hecho_id", "hecho__ocurrida_en", "hecho__area__nombre", "importe_centavos"),
            busqueda=("hecho__id",), orden=("hecho_id", "id"),
        )
        pagina = self.paginate_queryset(atribuciones)
        datos = AtribucionRepartoSerializer(pagina, many=True, context={
            "institucion_id": reparto.gasto.institucion_id,
            "puede_abrir_casos": tiene_capacidad(request.user, "casos_operar", reparto.gasto.institucion_id),
        }).data
        respuesta = self.get_paginated_response(datos)
        respuesta.data.update(
            periodo_economico=reparto.gasto.periodo_economico.isoformat(),
            saldo_centavos=reparto.saldo_centavos,
            importe_atribuido_centavos=importe_atribuido,
            saldo_no_atribuido_centavos=reparto.saldo_centavos - importe_atribuido,
            actualizando=RepartoGastoSerializer.get_actualizando(reparto),
        )
        return self.auditar_respuesta(respuesta, contexto=reparto.gasto, objeto_id=reparto.pk)

    def get_queryset(self):
        qs = super().get_queryset()
        usuario = self.request.user
        qs = qs.filter(alcance_financiero_q(
            usuario, ConcesionFinanciera.Accion.VER_GASTOS,
            institucion_path="gasto__institucion_id", area_path="gasto__area_id", sensible_path="gasto__sensible",
        )).distinct()
        return _filtrar_vigencia(qs, self.request.query_params.get("vigente"))


class AtribucionRepartoSerializer(serializers.ModelSerializer):
    atencion = serializers.IntegerField(source="hecho_id", read_only=True)
    referencia_atencion = serializers.IntegerField(source="hecho.evento_origen_id", read_only=True)
    ocurrida_en = serializers.DateTimeField(source="hecho.ocurrida_en", read_only=True)
    area = serializers.IntegerField(source="hecho.area_origen_id", read_only=True, allow_null=True)
    area_nombre = serializers.CharField(source="hecho.area.nombre", read_only=True, default=None)
    caso_navegable = serializers.SerializerMethodField()
    caso_descripcion = serializers.SerializerMethodField()

    def get_caso_navegable(self, obj):
        # El permiso financiero nunca concede navegación clínica. No usar el
        # id histórico: puede sobrevivir a la eliminación del caso original.
        caso = obj.hecho.caso
        if (self.context.get("puede_abrir_casos") and caso is not None
                and caso.institucion_id == self.context.get("institucion_id")):
            return caso.pk
        return None

    def get_caso_descripcion(self, obj):
        if self.get_caso_navegable(obj) is None:
            return None
        caso = obj.hecho.caso
        # Describir la atención de origen, nunca el paso actual del caso ni
        # texto libre de un evento clínico. No se consulta el nombre del paciente.
        nodo = obj.hecho.nodo
        if nodo is not None and nodo.version_id == caso.version_id and nodo.titulo.strip():
            return nodo.titulo
        flujo = caso.version.flujo
        if flujo.institucion_id == caso.institucion_id and flujo.titulo.strip():
            return flujo.titulo
        return None

    class Meta:
        model = AtribucionReparto
        fields = ["id", "atencion", "referencia_atencion", "ocurrida_en", "area", "area_nombre", "importe_centavos", "caso_navegable", "caso_descripcion"]
        read_only_fields = fields
