"""Configuración simple y resolución administrativa, sin acceso clínico implícito."""
from django.core.exceptions import ValidationError as DjangoValidationError
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Value, BooleanField, IntegerField
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import SearchFilter
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.common import OrdenEstable

from .auditoria import AuditaLecturaFinanciera
from .cobros import registrar_politica_cobro, resolver_pendiente_cobro, recuperar_cobros_atencion
from .filtros import filtrar_tabla
from .models import HechoAtencionCosteable
from .models_cobros import PendienteCobro, PoliticaCobro
from .permisos import alcance_financiero_q, tiene_accion_financiera


def _validacion(funcion, *args, **kwargs):
    try:
        return funcion(*args, **kwargs)
    except DjangoValidationError as error:
        raise serializers.ValidationError(getattr(error, "message_dict", error.messages)) from error


class PermisoCobros(BasePermission):
    def has_permission(self, request, view):
        return tiene_accion_financiera(request.user, view.accion_requerida())


class PoliticaCobroSerializer(serializers.ModelSerializer):
    class Meta:
        model = PoliticaCobro
        fields = ["id", "prestacion", "institucion", "nodo_origen_id", "nombre_prestacion", "cobrar", "importe", "contraparte_nombre", "contraparte_referencia", "sensible", "vigente_desde", "registrado", "registrado_por"]
        # El responsable del pago no es propiedad de la prestación: varía por
        # paciente. Se define por atención al completar el cobro, o lo fija la
        # cobertura. Se siguen leyendo para no ocultar las versiones históricas.
        read_only_fields = ["id", "institucion", "nodo_origen_id", "nombre_prestacion", "registrado", "registrado_por", "contraparte_nombre", "contraparte_referencia"]
        extra_kwargs = {"vigente_desde": {"required": False}, "importe": {"min_value": Decimal("0.01")}}

    def create(self, validated_data):
        return _validacion(registrar_politica_cobro, registrado_por=self.context["request"].user, **validated_data)


class PoliticaCobroViewSet(AuditaLecturaFinanciera, viewsets.ModelViewSet):
    queryset = PoliticaCobro.objects.all()
    serializer_class = PoliticaCobroSerializer
    permission_classes = [IsAuthenticated, PermisoCobros]
    http_method_names = ["get", "post", "head", "options"]

    def accion_requerida(self):
        return "configurar_cobros"

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        respuesta = super().create(request, *args, **kwargs)
        return self.auditar_respuesta(respuesta, objeto_id=respuesta.data["id"])

    def get_queryset(self):
        # La política es institucional: un permiso sólo de área no alcanza.
        qs = self.queryset.annotate(area_id=Value(None, output_field=IntegerField()))
        qs = qs.filter(alcance_financiero_q(self.request.user, "configurar_cobros")).distinct()
        if self.request.query_params.get("institucion"):
            institucion_id = serializers.IntegerField(min_value=1).run_validation(self.request.query_params["institucion"])
            qs = qs.filter(institucion_id=institucion_id)
        return qs


class PendienteCobroSerializer(serializers.ModelSerializer):
    nombre_prestacion = serializers.CharField(source="politica.nombre_prestacion", read_only=True)
    estado = serializers.SerializerMethodField()
    motivo = serializers.SerializerMethodField()
    periodo_economico = serializers.SerializerMethodField()

    class Meta:
        model = PendienteCobro
        fields = ["id", "hecho", "prestacion", "nombre_prestacion", "institucion", "area", "sensible", "importe", "contraparte_nombre", "contraparte_referencia", "estado", "obligacion", "motivo", "periodo_economico", "resuelto_en", "resuelto_por"]
        read_only_fields = fields

    @staticmethod
    def get_estado(obj) -> str:
        return "resuelto" if obj.obligacion_id else "pendiente"

    @staticmethod
    def get_motivo(obj) -> str:
        if obj.obligacion_id:
            return "Cargo generado"
        faltan = []
        if obj.importe is None:
            faltan.append("arancel")
        if not obj.contraparte_nombre:
            faltan.append("responsable del pago")
        return "Falta " + " y ".join(faltan) if faltan else "Pendiente de generación"

    @staticmethod
    @extend_schema_field(serializers.DateField())
    def get_periodo_economico(obj) -> str:
        from django.utils import timezone
        return timezone.localtime(obj.hecho.ocurrida_en).date().replace(day=1).isoformat()


class ResolverCobroSerializer(serializers.Serializer):
    importe = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False)
    contraparte_nombre = serializers.CharField(max_length=160, required=False)
    contraparte_referencia = serializers.CharField(max_length=160, required=False, allow_blank=True)


class PendienteCobroViewSet(AuditaLecturaFinanciera, viewsets.ReadOnlyModelViewSet):
    filter_backends = [OrdenEstable, SearchFilter]
    ordering_fields = ("hecho_id", "importe", "contraparte_nombre")
    search_fields = ("politica__nombre_prestacion", "contraparte_nombre")
    queryset = PendienteCobro.objects.all()
    serializer_class = PendienteCobroSerializer
    permission_classes = [IsAuthenticated, PermisoCobros]

    def accion_requerida(self):
        return "registrar_dinero" if self.action in ("resolver", "recuperar") else "ver_dinero"

    def get_queryset(self):
        qs = self.queryset.filter(alcance_financiero_q(self.request.user, self.accion_requerida())).select_related("politica", "hecho").distinct()
        # Resolver devuelve la fila financiera: escribir no concede leer datos
        # existentes, ni se mezclan áreas de concesiones para acciones distintas.
        if self.action == "resolver":
            qs = qs.filter(alcance_financiero_q(self.request.user, "ver_dinero"))
        for campo in ("institucion", "area", "hecho"):
            valor = self.request.query_params.get(campo)
            if valor:
                try:
                    valor = int(valor)
                except ValueError:
                    raise serializers.ValidationError({campo: "Indicá un identificador válido."})
                qs = qs.filter(**{f"{campo}_id": valor})
        if self.request.query_params.get("area_sin_asignar") == "true":
            qs = qs.filter(area__isnull=True)
        if self.request.query_params.get("estado") == "pendiente":
            qs = qs.filter(obligacion__isnull=True)
        elif self.request.query_params.get("estado") == "resuelto":
            qs = qs.filter(obligacion__isnull=False)
        return qs

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resolver(self, request, pk=None):
        pendiente = self.get_object()
        entrada = ResolverCobroSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        pendiente = _validacion(resolver_pendiente_cobro, pendiente.pk, usuario=request.user, **entrada.validated_data)
        return self.auditar_respuesta(Response(self.get_serializer(pendiente).data), contexto=pendiente)

    @action(detail=False, methods=["get"])
    def recuperables(self, request):
        # Una captura fallida no permite conocer sensibilidad: alcance sensible.
        # El hecho se conserva incluso si no llegó a insertarse el snapshot.
        qs = HechoAtencionCosteable.objects.filter(
            Q(snapshot_cobro__capturado=False) | Q(snapshot_cobro__isnull=True),
        ).annotate(sensible=Value(True, output_field=BooleanField())).filter(
            alcance_financiero_q(request.user, "ver_dinero", area_path="area_origen_id"),
        ).order_by("pk")
        for campo, atributo in (("institucion", "institucion_id"), ("area", "area_origen_id")):
            if request.query_params.get(campo):
                valor = serializers.IntegerField(min_value=1).run_validation(request.query_params[campo])
                qs = qs.filter(**{atributo: valor})
        if request.query_params.get("area_sin_asignar") == "true":
            qs = qs.filter(area_origen_id__isnull=True)
        qs = filtrar_tabla(qs, request, ordenables=("id",), busqueda=("id",), orden=("id",))
        pagina = self.paginate_queryset(qs)
        filas = [{"id": obj.pk, "hecho": obj.pk, "institucion": obj.institucion_id, "area": obj.area_origen_id, "sensible": True, "motivo": "No se pudo completar la captura de cobros. Podés reintentar sin aplicar reglas nuevas."} for obj in (pagina if pagina is not None else qs)]
        respuesta = self.get_paginated_response(filas) if pagina is not None else Response(filas)
        return self.auditar_respuesta(respuesta)

    @action(detail=False, methods=["post"])
    @transaction.atomic
    def recuperar(self, request):
        entrada = serializers.IntegerField(min_value=1)
        hecho_id = entrada.run_validation(request.data.get("hecho"))
        # Admitir también una captura terminada: repetir tras perder la
        # respuesta es idempotente. Nunca revelar hechos fuera del alcance.
        hechos = HechoAtencionCosteable.objects.annotate(
            sensible=Value(True, output_field=BooleanField()),
        ).filter(
            alcance_financiero_q(request.user, "registrar_dinero", area_path="area_origen_id"),
            alcance_financiero_q(request.user, "ver_dinero", area_path="area_origen_id"),
            pk=hecho_id,
        )
        hecho = hechos.first()
        if hecho is None:
            raise NotFound()
        snapshot = _validacion(recuperar_cobros_atencion, hecho_id, usuario=request.user)
        periodo = timezone.localtime(hecho.ocurrida_en).date().replace(day=1)
        grupos = {(hecho.institucion_id, hecho.area_origen_id, True, periodo): 1}
        # La acción opera sobre el hecho de una atención, no sobre un pendiente
        # concreto: no asociar su id a otro modelo en la auditoría.
        return self.auditar_respuesta(Response({"hecho": hecho_id, "capturado": snapshot.capturado}), grupos=grupos)
