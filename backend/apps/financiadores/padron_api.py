"""Recursos de padrón separados de actividad prestacional e historia clínica."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes

from . import models as m
from . import padron as p
from .permisos import puede_padron_protegido, requerir_padron_protegido
from .services import auditar
from .serializers import AfiliadoSerializer


class DocumentoLegajoSerializer(serializers.ModelSerializer):
    adjunto = serializers.SerializerMethodField()

    def get_adjunto(self, obj) -> bool:
        return False

    class Meta:
        model = m.DocumentoLegajo
        fields = ["id", *p.CAMPOS_LEGAJO, "adjunto"]


class SaludPadronSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.SaludPadron
        fields = ["revision", *p.CAMPOS_SALUD]


class CobranzaPadronSerializer(serializers.ModelSerializer):
    estado_informado = serializers.SerializerMethodField()

    def get_estado_informado(self, obj) -> bool:
        return True

    class Meta:
        model = m.CobranzaPadron
        fields = ["revision", *p.CAMPOS_COBRANZA, "estado_informado"]


def fila_historial(h):
    fila = {"id": h.pk, "motivo": h.motivo, "registrado": h.registrado,
            "usuario_nombre": h.registrado_por.nombre_completo, "cambios": h.cambios}
    if isinstance(h, m.HistorialAfiliacion):
        fila.update(tipo=h.tipo, numero=h.numero, documento=h.documento, plan=h.plan_id,
                    desde=h.desde, origen=h.origen, lote=h.lote_id)
    else:
        fila.update(revision=h.revision)
    return fila


def filtrar_padron(qs, query):
    if query.get("regimen"):
        regimen = serializers.ChoiceField(choices=m.Afiliado._meta.get_field("regimen").choices).run_validation(query["regimen"])
        qs = qs.filter(regimen=regimen)
    if query.get("estado_administrativo"):
        estado = serializers.ChoiceField(choices=["activo", "en_tramite", "baja_programada", "baja_administrativa"]).run_validation(query["estado_administrativo"])
        if estado == "baja_programada":
            qs = qs.filter(baja_efectiva__gt=timezone.localdate())
        elif estado == "baja_administrativa":
            qs = qs.filter(baja_efectiva__lte=timezone.localdate())
        elif estado == "activo":
            qs = qs.filter(baja_efectiva__isnull=True, estado_tramite="completo")
        else:
            qs = qs.filter(baja_efectiva__isnull=True).exclude(estado_tramite="completo")
    for prefijo, campo in (("alta", "alta_administrativa"), ("baja", "baja_efectiva")):
        fechas = {}
        for extremo, lookup in (("desde", "gte"), ("hasta", "lte")):
            valor = query.get(f"{prefijo}_{extremo}")
            if valor:
                fechas[extremo] = serializers.DateField().run_validation(valor)
                qs = qs.filter(**{f"{campo}__{lookup}": fechas[extremo]})
        if len(fechas) == 2 and fechas["hasta"] < fechas["desde"]:
            raise serializers.ValidationError("El rango de fechas está invertido.")
    return qs


class PadronMixin:
    def _padron_obj(self, org, afiliado_id):
        return get_object_or_404(m.Afiliado.objects.select_related("plan"), financiador=org, pk=afiliado_id)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=AfiliadoSerializer)
    @action(detail=True, methods=["get", "patch"], url_path=r"padron/(?P<afiliado_id>\d+)")
    def padron_detalle(self, request, pk=None, afiliado_id=None):
        from .serializers import AfiliadoSerializer
        org = self.organizacion(escritura=request.method == "PATCH")
        obj = self._padron_obj(org, afiliado_id)
        if request.method == "PATCH":
            entrada = p.campos_entrada(m.Afiliado, p.CAMPOS_EDITABLES, request.data)
            obj = p.editar_ficha(afiliado=obj, usuario=request.user, entrada=entrada)
        else:
            auditar(request.user, "consultar_ficha_padron", obj.pk, financiador=org)
        resultado = AfiliadoSerializer(obj).data
        resultado["permisos"] = {f"{bloque}_{accion}": puede_padron_protegido(request.user, org.pk, bloque, accion == "edicion")
                                 for bloque in ("salud", "cobranza") for accion in ("consulta", "edicion")}
        return Response(resultado)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"], url_path=r"padron/(?P<afiliado_id>\d+)/familia")
    def padron_familia(self, request, pk=None, afiliado_id=None):
        org = self.organizacion()
        obj = self._padron_obj(org, afiliado_id)
        titular = self._padron_obj(org, obj.titular_id or obj.pk)
        integrantes = m.Afiliado.objects.filter(financiador=org).filter(Q(pk=titular.pk) | Q(titular=titular)).order_by("pk")
        def resumen(x):
            return {"id": x.pk, "numero": x.numero, "documento": x.documento, "nombre": x.nombre, "parentesco": x.parentesco}
        auditar(request.user, "consultar_familia_padron", obj.pk, financiador=org)
        return Response({"titular": resumen(titular), "integrantes": [resumen(x) for x in integrantes]})

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"], url_path=r"padron/(?P<afiliado_id>\d+)/historial")
    def padron_historial(self, request, pk=None, afiliado_id=None):
        org = self.organizacion()
        obj = self._padron_obj(org, afiliado_id)
        qs = obj.historial.select_related("registrado_por").order_by("-pk")
        pagina = self.paginate_queryset(qs)
        auditar(request.user, "consultar_historial_padron", obj.pk, financiador=org)
        return self.get_paginated_response([fila_historial(h) for h in pagina])

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get", "post", "patch"], url_path=r"padron/(?P<afiliado_id>\d+)/legajo")
    def padron_legajo(self, request, pk=None, afiliado_id=None):
        org = self.organizacion(escritura=request.method != "GET")
        obj = self._padron_obj(org, afiliado_id)
        if request.method == "GET":
            auditar(request.user, "consultar_legajo_padron", obj.pk, financiador=org)
            return self.lista(obj.legajo.all(), DocumentoLegajoSerializer)
        documento_id = None
        if request.method == "PATCH":
            documento_id = serializers.IntegerField(min_value=1).run_validation(request.data.get("id"))
        entrada = p.campos_entrada(m.DocumentoLegajo, p.CAMPOS_LEGAJO, {k: v for k, v in request.data.items() if k != "id"})
        documento, revision = p.guardar_legajo(afiliado=obj, usuario=request.user, entrada=entrada, documento_id=documento_id)
        return Response({"documento": DocumentoLegajoSerializer(documento).data, "revision": revision}, status=201 if request.method == "POST" else 200)

    def _padron_protegido(self, request, org, afiliado_id, bloque, historial=False):
        requerir_padron_protegido(request.user, org.pk, bloque, escritura=request.method == "PATCH")
        obj = self._padron_obj(org, afiliado_id)
        modelo, clase, campos = ((m.SaludPadron, SaludPadronSerializer, p.CAMPOS_SALUD) if bloque == "salud"
                                else (m.CobranzaPadron, CobranzaPadronSerializer, p.CAMPOS_COBRANZA))
        if historial:
            qs = m.HistorialPadronProtegido.objects.filter(afiliado=obj, bloque=bloque).select_related("registrado_por").order_by("-pk")
            pagina = self.paginate_queryset(qs)
            auditar(request.user, "consultar_historial_protegido", obj.pk, financiador=org)
            return self.get_paginated_response([fila_historial(h) for h in pagina])
        if request.method == "PATCH":
            entrada = p.campos_entrada(modelo, campos, request.data)
            registro = p.editar_protegido(afiliado=obj, usuario=request.user, bloque=bloque, entrada=entrada)
        else:
            registro = modelo.objects.filter(afiliado=obj).first() or modelo(afiliado=obj)
            auditar(request.user, "consultar_padron_protegido", obj.pk, financiador=org)
        return Response(clase(registro).data)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=SaludPadronSerializer)
    @action(detail=True, methods=["get", "patch"], url_path=r"padron/(?P<afiliado_id>\d+)/salud")
    def padron_salud(self, request, pk=None, afiliado_id=None):
        return self._padron_protegido(request, self.organizacion(), afiliado_id, "salud")

    @extend_schema(request=OpenApiTypes.OBJECT, responses=CobranzaPadronSerializer)
    @action(detail=True, methods=["get", "patch"], url_path=r"padron/(?P<afiliado_id>\d+)/cobranza")
    def padron_cobranza(self, request, pk=None, afiliado_id=None):
        return self._padron_protegido(request, self.organizacion(), afiliado_id, "cobranza")

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"], url_path=r"padron/(?P<afiliado_id>\d+)/salud/historial")
    def padron_salud_historial(self, request, pk=None, afiliado_id=None):
        return self._padron_protegido(request, self.organizacion(), afiliado_id, "salud", historial=True)

    @extend_schema(responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=["get"], url_path=r"padron/(?P<afiliado_id>\d+)/cobranza/historial")
    def padron_cobranza_historial(self, request, pk=None, afiliado_id=None):
        return self._padron_protegido(request, self.organizacion(), afiliado_id, "cobranza", historial=True)
