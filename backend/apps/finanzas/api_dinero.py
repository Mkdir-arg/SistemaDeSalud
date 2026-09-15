"""API de obligaciones y dinero; la fuente económica conserva su historia."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .auditoria import AuditaLecturaFinanciera
from .dinero import (crear_obligacion_pago, decidir_ajuste, decidir_movimiento, disponible_reduccion, disponible_reintegro,
                     estado_obligacion, previsualizar_reintegro, reducir_obligacion,
                     registrar_movimiento, reintegrar_movimiento, movimiento_conjunto)
from .models import AjusteObligacion, ConcesionFinanciera, Gasto, MovimientoDinero, ObligacionFinanciera
from .permisos import alcance_financiero_q, tiene_accion_financiera


def _dinero(valor):
    return format(valor, ".2f")


CAMPOS_APROBACION = ["estado", "aprobado", "aprobado_por", "aprobado_en", "rechazado_por", "rechazado_en", "motivo_rechazo"]


class MovimientoDineroSerializer(serializers.ModelSerializer):
    aprobado = serializers.BooleanField(read_only=True)
    area = serializers.IntegerField(source="obligacion.area_id", read_only=True, allow_null=True)
    sensible = serializers.BooleanField(source="obligacion.sensible", read_only=True)
    periodo_economico = serializers.DateField(source="obligacion.periodo_economico", read_only=True)
    contraparte_nombre = serializers.CharField(source="obligacion.contraparte_nombre", read_only=True)
    obligacion_tipo = serializers.CharField(source="obligacion.tipo", read_only=True)
    disponible_reintegro = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoDinero
        fields = ["id", "obligacion", "institucion", "area", "sensible", "periodo_economico", "contraparte_nombre", "obligacion_tipo", "tipo", "original", "ajuste", "importe", "fecha", "referencia", "motivo", "autor", "registrado", "disponible_reintegro"] + CAMPOS_APROBACION
        read_only_fields = fields

    def get_disponible_reintegro(self, obj) -> str:
        return _dinero(disponible_reintegro(obj))


class AjusteObligacionSerializer(serializers.ModelSerializer):
    aprobado = serializers.BooleanField(read_only=True)
    disponible_reintegro = serializers.SerializerMethodField()
    movimiento_vinculado = serializers.SerializerMethodField()

    class Meta:
        model = AjusteObligacion
        fields = ["id", "importe", "motivo", "autor", "registrado", "disponible_reintegro", "movimiento_vinculado"] + CAMPOS_APROBACION
        read_only_fields = fields

    def get_disponible_reintegro(self, obj) -> str:
        return _dinero(disponible_reduccion(obj))

    def get_movimiento_vinculado(self, obj) -> int | None:
        movimiento = movimiento_conjunto(obj)
        return movimiento.pk if movimiento else None


class ObligacionFinancieraSerializer(serializers.ModelSerializer):
    movimientos = MovimientoDineroSerializer(many=True, read_only=True)
    ajustes = AjusteObligacionSerializer(many=True, read_only=True)

    class Meta:
        model = ObligacionFinanciera
        fields = ["id", "tipo", "gasto", "hecho", "institucion", "area", "sensible", "moneda", "importe_original", "periodo_economico", "contraparte_nombre", "contraparte_referencia", "creado_por", "creado", "movimientos", "ajustes"]
        read_only_fields = fields

    @transaction.atomic
    def to_representation(self, instance):
        # La lista histórica y los saldos deben describir la misma revisión.
        instance = ObligacionFinanciera.objects.select_for_update().get(pk=instance.pk)
        resultado = super().to_representation(instance)
        estado = estado_obligacion(instance)
        resultado.update({campo: _dinero(valor) if isinstance(valor, Decimal) else valor for campo, valor in estado.items()})
        resultado["discrepancia_gasto"] = None
        if instance.gasto_id:
            gasto = instance.gasto
            importe_gasto = gasto.importe + (gasto.ajustes.filter(estado="aprobado").aggregate(total=Sum("importe"))["total"] or Decimal("0"))
            if importe_gasto != estado["obligacion_actual"] or Gasto.objects.filter(reemplaza=gasto).exists():
                resultado["discrepancia_gasto"] = "El gasto y la obligación son diferentes. Revisá si corresponde ajustar la obligación; no se modificó automáticamente."
        return resultado


class CrearObligacionSerializer(serializers.Serializer):
    gasto = serializers.IntegerField(min_value=1)
    contraparte_nombre = serializers.CharField(max_length=160)
    contraparte_referencia = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    clave = serializers.UUIDField()


class RegistrarMovimientoSerializer(serializers.Serializer):
    aprobado = serializers.BooleanField(required=False)
    importe = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    fecha = serializers.DateField()
    referencia = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    clave = serializers.UUIDField()


class ReducirObligacionSerializer(serializers.Serializer):
    aprobado = serializers.BooleanField(required=False)
    importe = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    motivo = serializers.CharField(max_length=255)
    clave = serializers.UUIDField()


class PreviewReintegroSerializer(serializers.Serializer):
    aprobado = serializers.BooleanField(required=False)
    importe = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"))
    fecha = serializers.DateField()
    motivo = serializers.CharField(max_length=255)
    efecto = serializers.ChoiceField(choices=["mantener", "reducir", "reduccion_existente"])
    ajuste = serializers.IntegerField(min_value=1, required=False, allow_null=True)


class ReintegrarSerializer(PreviewReintegroSerializer):
    clave = serializers.UUIDField()
    version_esperada = serializers.CharField(max_length=64)
    pendiente_esperado = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False)


class RechazarMovimientoSerializer(serializers.Serializer):
    motivo = serializers.CharField(max_length=255)


class DecidirAjusteSerializer(serializers.Serializer):
    ajuste = serializers.IntegerField(min_value=1)


class RechazarAjusteSerializer(DecidirAjusteSerializer):
    motivo = serializers.CharField(max_length=255)


def _validar(clase, datos):
    serializer = clase(data=datos)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _ejecutar(servicio, **kwargs):
    try:
        return servicio(**kwargs)
    except ModelValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", None) or exc.messages) from exc
    except IntegrityError as exc:
        # La restricción de unicidad también cubre claves concurrentes en fuentes distintas.
        raise ValidationError("La operación entra en conflicto con un registro existente. Actualizá y verificá el resultado.") from exc


def _filtrar_contexto(queryset, parametros, prefijo=""):
    sin_area = parametros.get("area_sin_asignar")
    if sin_area is not None:
        if sin_area not in ("true", "false"):
            raise ValidationError({"area_sin_asignar": "Usá true o false."})
        if sin_area == "true":
            if parametros.get("area"):
                raise ValidationError({"area": "No combines un área con la selección sin área."})
            queryset = queryset.filter(**{f"{prefijo}area__isnull": True})
    for campo in ("institucion", "area"):
        if parametros.get(campo):
            try:
                valor = int(parametros[campo])
                if valor < 1:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValidationError({campo: "Elegí una opción válida."})
            queryset = queryset.filter(**{f"{prefijo}{campo}_id": valor})
    return queryset


class ObligacionFinancieraViewSet(AuditaLecturaFinanciera, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ObligacionFinancieraSerializer
    queryset = ObligacionFinanciera.objects.all()

    def get_queryset(self):
        if not tiene_accion_financiera(self.request.user, ConcesionFinanciera.Accion.VER_DINERO):
            raise PermissionDenied("No tenés permiso para consultar pagos y cobros.")
        queryset = self.queryset.filter(alcance_financiero_q(self.request.user, ConcesionFinanciera.Accion.VER_DINERO)).select_related("gasto").prefetch_related("movimientos", "ajustes")
        queryset = _filtrar_contexto(queryset, self.request.query_params)
        tipo = self.request.query_params.get("tipo")
        if tipo:
            if tipo not in ("pagar", "cobrar"):
                raise ValidationError({"tipo": "Elegí pagar o cobrar."})
            queryset = queryset.filter(tipo=tipo)
        mes = self.request.query_params.get("periodo_mes")
        if mes:
            try:
                periodo = date.fromisoformat(f"{mes}-01")
            except ValueError:
                raise ValidationError({"periodo_mes": "Usá el formato AAAA-MM."})
            queryset = queryset.filter(periodo_economico=periodo)
        return queryset

    @transaction.atomic
    def create(self, request):
        if not tiene_accion_financiera(request.user, ConcesionFinanciera.Accion.VER_DINERO):
            raise PermissionDenied("No tenés permiso para consultar pagos y cobros.")
        datos = _validar(CrearObligacionSerializer, request.data)
        # No revelar la existencia de fuentes fuera del alcance autorizado.
        gasto = Gasto.objects.filter(alcance_financiero_q(request.user, ConcesionFinanciera.Accion.REGISTRAR_DINERO), alcance_financiero_q(request.user, ConcesionFinanciera.Accion.VER_DINERO), pk=datos.pop("gasto")).first()
        if gasto is None:
            raise NotFound("No se encontró un gasto disponible en tu alcance.")
        obligacion = _ejecutar(crear_obligacion_pago, gasto=gasto, usuario=request.user, **datos)
        return self.auditar_respuesta(Response(self.get_serializer(obligacion).data, status=201), contexto=obligacion)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def movimientos(self, request, pk=None):
        obligacion = self.get_object()
        _ejecutar(registrar_movimiento, obligacion=obligacion, usuario=request.user, **_validar(RegistrarMovimientoSerializer, request.data))
        return self.auditar_respuesta(Response(self.get_serializer(obligacion).data, status=201), contexto=obligacion)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reducir(self, request, pk=None):
        obligacion = self.get_object()
        _ejecutar(reducir_obligacion, obligacion=obligacion, usuario=request.user, **_validar(ReducirObligacionSerializer, request.data))
        return self.auditar_respuesta(Response(self.get_serializer(obligacion).data, status=201), contexto=obligacion)

    @action(detail=True, methods=["post"], url_path="aprobar-ajuste")
    @transaction.atomic
    def aprobar_ajuste(self, request, pk=None):
        obligacion = self.get_object()
        _ejecutar(decidir_ajuste, obligacion=obligacion, usuario=request.user, aprobar=True, **_validar(DecidirAjusteSerializer, request.data))
        return self.auditar_respuesta(Response(self.get_serializer(obligacion).data), contexto=obligacion)

    @action(detail=True, methods=["post"], url_path="rechazar-ajuste")
    @transaction.atomic
    def rechazar_ajuste(self, request, pk=None):
        obligacion = self.get_object()
        _ejecutar(decidir_ajuste, obligacion=obligacion, usuario=request.user, aprobar=False, **_validar(RechazarAjusteSerializer, request.data))
        return self.auditar_respuesta(Response(self.get_serializer(obligacion).data), contexto=obligacion)


class MovimientoDineroViewSet(AuditaLecturaFinanciera, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MovimientoDineroSerializer
    queryset = MovimientoDinero.objects.all()

    def get_queryset(self):
        if not tiene_accion_financiera(self.request.user, ConcesionFinanciera.Accion.VER_DINERO):
            raise PermissionDenied("No tenés permiso para consultar pagos y cobros.")
        queryset = self.queryset.filter(alcance_financiero_q(self.request.user, ConcesionFinanciera.Accion.VER_DINERO, institucion_path="obligacion__institucion_id", area_path="obligacion__area_id", sensible_path="obligacion__sensible")).select_related("obligacion")
        queryset = _filtrar_contexto(queryset, self.request.query_params, "obligacion__")
        estado = self.request.query_params.get("estado")
        if estado:
            if estado not in ("pendiente_aprobacion", "aprobado", "rechazado"):
                raise ValidationError({"estado": "Elegí un estado válido."})
            queryset = queryset.filter(estado=estado)
        for parametro, filtro in (("fecha_desde", "fecha__gte"), ("fecha_hasta", "fecha__lte")):
            if self.request.query_params.get(parametro):
                valor = serializers.DateField().run_validation(self.request.query_params[parametro])
                queryset = queryset.filter(**{filtro: valor})
        return queryset

    @action(detail=True, methods=["post"], url_path="previsualizar-reintegro")
    def previsualizar_reintegro(self, request, pk=None):
        original = self.get_object()
        resultado = _ejecutar(previsualizar_reintegro, original=original, usuario=request.user, **_validar(PreviewReintegroSerializer, request.data))
        respuesta = Response({campo: _dinero(valor) if isinstance(valor, Decimal) else valor for campo, valor in resultado.items()})
        return self.auditar_respuesta(respuesta, contexto=original.obligacion, objeto_id=original.pk)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reintegrar(self, request, pk=None):
        original = self.get_object()
        reintegro = _ejecutar(reintegrar_movimiento, original=original, usuario=request.user, **_validar(ReintegrarSerializer, request.data))
        return self.auditar_respuesta(Response(ObligacionFinancieraSerializer(original.obligacion).data, status=201), contexto=original.obligacion, objeto_id=reintegro.pk)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def aprobar(self, request, pk=None):
        movimiento = self.get_object()
        _ejecutar(decidir_movimiento, movimiento=movimiento, usuario=request.user, aprobar=True)
        return self.auditar_respuesta(Response(ObligacionFinancieraSerializer(movimiento.obligacion).data), contexto=movimiento.obligacion, objeto_id=movimiento.pk)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def rechazar(self, request, pk=None):
        movimiento = self.get_object()
        _ejecutar(decidir_movimiento, movimiento=movimiento, usuario=request.user, aprobar=False, **_validar(RechazarMovimientoSerializer, request.data))
        return self.auditar_respuesta(Response(ObligacionFinancieraSerializer(movimiento.obligacion).data), contexto=movimiento.obligacion, objeto_id=movimiento.pk)
