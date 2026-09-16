"""Bandeja administrativa acotada; nunca serializa la historia clínica del caso."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes

from apps.auditoria.mixins import registrar_accesos
from apps.auditoria.models import AccesoClinico
from apps.finanzas.models import Prestacion
from apps.instituciones.models import Institucion
from . import autorizaciones as a, models as m
from .cobertura import regla_aplicable
from .permisos import puede_resolver_autorizaciones, requerir_financiador
from .services import auditar
from .vigencias import convenios_vigentes
from .views import CoberturaBaseViewSet


class FiltrosAutorizaciones(serializers.Serializer):
    financiador = serializers.IntegerField(min_value=1, required=False)
    institucion = serializers.IntegerField(min_value=1, required=False)
    hospital = serializers.IntegerField(min_value=1, required=False)
    caso = serializers.IntegerField(min_value=1, required=False)
    estado = serializers.ChoiceField(choices=m.SolicitudAutorizacion.ESTADOS, required=False)
    urgente = serializers.BooleanField(required=False)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    search = serializers.CharField(max_length=120, required=False)

    def validate(self, datos):
        if bool(datos.get("financiador")) == bool(datos.get("institucion")):
            raise serializers.ValidationError("Indicá exactamente un ámbito: financiador o institución.")
        if datos.get("desde") and datos.get("hasta") and datos["desde"] > datos["hasta"]:
            raise serializers.ValidationError("La fecha inicial no puede ser posterior a la final.")
        return datos


class SolicitarAutorizacionSerializer(serializers.Serializer):
    caso = serializers.IntegerField(min_value=1)
    prestacion = serializers.IntegerField(min_value=1)
    intento = serializers.UUIDField()
    cantidad = serializers.IntegerField(min_value=1, max_value=100000)
    justificacion = serializers.CharField(max_length=1000)
    clave = serializers.UUIDField()


class ResolverAutorizacionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)
    decision = serializers.ChoiceField(choices=["observar", "aprobar", "rechazar"])
    motivo = serializers.CharField(max_length=255)
    evidencia = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")
    numero_externo = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    cantidad_aprobada = serializers.IntegerField(min_value=1, max_value=100000, required=False)
    vigencia_desde = serializers.DateField(required=False)
    vigencia_hasta = serializers.DateField(required=False)
    clave = serializers.UUIDField()


class ReenviarAutorizacionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)
    justificacion = serializers.CharField(max_length=1000)
    clave = serializers.UUIDField()


class AnularAutorizacionSerializer(serializers.Serializer):
    revision = serializers.IntegerField(min_value=1)
    motivo = serializers.CharField(max_length=255)
    clave = serializers.UUIDField()


class SolicitudAutorizacionSerializer(serializers.ModelSerializer):
    anterior = serializers.PrimaryKeyRelatedField(read_only=True)
    financiador_nombre = serializers.CharField(source="financiador.nombre")
    institucion_nombre = serializers.CharField(source="institucion.nombre")
    prestacion_nombre = serializers.CharField(source="prestacion.nombre")
    codigo = serializers.CharField(source="comun.codigo")
    afiliado_nombre = serializers.CharField(source="afiliado.nombre")
    afiliado_numero = serializers.CharField(source="afiliado.numero")
    documento = serializers.CharField(source="afiliado.documento")
    cantidades = serializers.SerializerMethodField()
    puede_resolver = serializers.SerializerMethodField()
    puede_reenviar = serializers.SerializerMethodField()
    puede_anular = serializers.SerializerMethodField()

    class Meta:
        model = m.SolicitudAutorizacion
        fields = ["id", "financiador", "financiador_nombre", "institucion", "institucion_nombre",
            "convenio", "caso", "nodo", "intento", "anterior", "prestacion", "prestacion_nombre", "comun", "codigo",
            "afiliado_nombre", "afiliado_numero", "documento", "estado", "revision", "cantidad_solicitada",
            "cantidad_aprobada", "cantidades", "plazo_respuesta", "vigencia_desde", "vigencia_hasta",
            "justificacion", "urgente", "motivo_resolucion", "evidencia", "numero_externo", "creado",
            "actualizado", "puede_resolver", "puede_reenviar", "puede_anular"]

    def get_cantidades(self, obj) -> dict:
        comprometida, consumida = obj.cantidad_comprometida, obj.cantidad_consumida
        return {"comprometida": comprometida, "consumida": consumida,
                "disponible": max(0, obj.cantidad_aprobada - comprometida - consumida)}

    def get_puede_resolver(self, obj) -> bool:
        return bool(self.context.get("financiador") and obj.estado in obj.ABIERTAS
            and (not obj.plazo_respuesta or obj.plazo_respuesta > timezone.now())
            and self.context.get("resuelve_autorizaciones", False))

    def get_puede_reenviar(self, obj) -> bool:
        return bool(not self.context.get("financiador") and obj.estado == "observada"
            and obj.intento == a.intento_actual(obj.caso) and obj.caso.estado not in obj.caso.ESTADOS_FINALIZADOS
            and (not obj.plazo_respuesta or obj.plazo_respuesta > timezone.now())
            and not obj.afiliado.finalizado_en and obj.convenio.estado == "activo")

    def get_puede_anular(self, obj) -> bool:
        return bool(not self.context.get("financiador") and obj.estado in obj.ABIERTAS)


def consulta_solicitudes():
    return m.SolicitudAutorizacion.objects.select_related(
        "financiador", "institucion", "prestacion", "comun", "afiliado", "ciudadano", "caso", "convenio",
    ).annotate(
        cantidad_comprometida=Sum("usos__cantidad", filter=Q(usos__estado="comprometido"), default=0),
        cantidad_consumida=Sum("usos__cantidad", filter=Q(usos__estado="consumido"), default=0),
    )


@extend_schema_view(
    list=extend_schema(operation_id="api_autorizaciones_cobertura_list", parameters=[FiltrosAutorizaciones], responses=OpenApiTypes.OBJECT),
    retrieve=extend_schema(responses=OpenApiTypes.OBJECT),
    create=extend_schema(request=SolicitarAutorizacionSerializer, responses=OpenApiTypes.OBJECT),
    contexto=extend_schema(responses=OpenApiTypes.OBJECT),
    resolver=extend_schema(request=ResolverAutorizacionSerializer, responses=OpenApiTypes.OBJECT),
    reenviar=extend_schema(request=ReenviarAutorizacionSerializer, responses=OpenApiTypes.OBJECT),
    anular=extend_schema(request=AnularAutorizacionSerializer, responses=OpenApiTypes.OBJECT),
)
class AutorizacionCoberturaViewSet(CoberturaBaseViewSet):
    serializer_class = SolicitudAutorizacionSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def ambito(self):
        if not hasattr(self, "_filtros"):
            filtro = FiltrosAutorizaciones(data=self.request.query_params.dict())
            filtro.is_valid(raise_exception=True)
            self._filtros = filtro.validated_data
        return self._filtros

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return m.SolicitudAutorizacion.objects.none()
        f = self.ambito()
        if f.get("financiador"):
            requerir_financiador(self.request.user, f["financiador"])
            qs = consulta_solicitudes().filter(pk__in=a.solicitudes_visibles_financiador(f["financiador"]).values("pk"))
        else:
            casos = a.casos_permitidos(self.request.user).filter(institucion_id=f["institucion"])
            qs = consulta_solicitudes().filter(institucion_id=f["institucion"], caso_id__in=casos.values("pk"))
        for campo, lookup in (("hospital", "institucion_id"), ("caso", "caso_id"), ("estado", "estado"), ("urgente", "urgente"), ("desde", "creado__date__gte"), ("hasta", "creado__date__lte")):
            if campo in f:
                qs = qs.filter(**{lookup: f[campo]})
        if f.get("search"):
            texto = f["search"]
            qs = qs.filter(Q(afiliado__nombre__icontains=texto) | Q(afiliado__numero__icontains=texto) | Q(afiliado__documento__icontains=texto) | Q(numero_externo__icontains=texto))
        return qs.order_by("creado", "pk")

    def serializar(self, obj, *, detalle=False, financiador=None):
        if financiador and not hasattr(self, "_resuelve_autorizaciones"):
            self._resuelve_autorizaciones = puede_resolver_autorizaciones(self.request.user, financiador)
        datos = self.serializer_class(obj, context={"request": self.request, "financiador": financiador,
            "resuelve_autorizaciones": getattr(self, "_resuelve_autorizaciones", False)}).data
        if detalle:
            datos["historial"] = [{"id": e.pk, "accion": e.accion, "anterior": e.anterior,
                "estado": e.estado, "revision": e.revision, "motivo": e.motivo,
                "usuario_nombre": e.usuario.nombre_completo if e.usuario_id else "Sistema",
                "creado": e.creado} for e in obj.historial.select_related("usuario").all()]
        return datos

    def auditar_lectura(self, objetos, financiador=None):
        # Usuario/hospital/ciudadano original; acceso administrativo obligatorio.
        with transaction.atomic():
            registrar_accesos(self.request, AccesoClinico.Tipo.FINANCIADOR if financiador else AccesoClinico.Tipo.DETALLE,
                "solicitudautorizacion", ({"ciudadano": obj.ciudadano, "institucion_id": obj.institucion_id,
                    "objeto_id": obj.pk, "detalle": f"solicitud={obj.pk}", "resultados": 1} for obj in objetos), estricto=True)
            if financiador:
                auditar(self.request.user, "consultar_autorizaciones", financiador,
                    financiador=m.Financiador.objects.get(pk=financiador))

    def list(self, request):
        qs = self.get_queryset()
        pagina = list(self.paginate_queryset(qs))
        f = self.ambito()
        response = self.get_paginated_response([self.serializar(obj, financiador=f.get("financiador")) for obj in pagina])
        response.data["opciones"] = {"instituciones": list(Institucion.objects.filter(pk__in=qs.values("institucion_id")).order_by("nombre", "pk").values("id", "nombre"))}
        self.auditar_lectura(pagina, f.get("financiador"))
        return response

    def retrieve(self, request, pk=None):
        obj = self.get_object()
        f = self.ambito()
        respuesta = self.serializar(obj, detalle=True, financiador=f.get("financiador"))
        self.auditar_lectura([obj], f.get("financiador"))
        return Response(respuesta)

    def create(self, request):
        d = SolicitarAutorizacionSerializer(data=request.data)
        d.is_valid(raise_exception=True)
        valores = dict(d.validated_data)
        caso = get_object_or_404(a.casos_permitidos(request.user), pk=valores.pop("caso"))
        prestacion = get_object_or_404(Prestacion, pk=valores.pop("prestacion"), institucion_id=caso.institucion_id)
        obj = a.solicitar(caso=caso, prestacion=prestacion, usuario=request.user, **valores)
        return Response(self.serializar(consulta_solicitudes().get(pk=obj.pk), detalle=True), status=201)

    @action(detail=False, methods=["get"])
    def contexto(self, request):
        raw = request.query_params.get("caso", "")
        if not raw.isdigit():
            raise serializers.ValidationError("Indicá el caso.")
        caso = get_object_or_404(a.casos_permitidos(request.user), pk=int(raw))
        activo = m.ConfiguracionHospital.objects.filter(institucion_id=caso.institucion_id, activo=True).exists()
        afiliacion = m.AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).select_related("afiliado").first()
        puede = bool(activo and afiliacion and afiliacion.afiliado_id and afiliacion.estado == "verificada"
            and not afiliacion.afiliado.finalizado_en and afiliacion.afiliado.desde <= timezone.localdate()
            and convenios_vigentes().filter(institucion_id=caso.institucion_id,
                financiador_id=afiliacion.afiliado.financiador_id, financiador__activo=True).exists()
            and caso.nodo_actual_id and caso.estado not in caso.ESTADOS_FINALIZADOS)
        prestaciones = []
        if puede:
            for prestacion in Prestacion.objects.filter(institucion_id=caso.institucion_id, nodo_id=caso.nodo_actual_id, activo=True).select_related("vinculoprestacion__comun"):
                vinculo = getattr(prestacion, "vinculoprestacion", None)
                regla = regla_aplicable(afiliacion, vinculo.comun, timezone.localdate(), timezone.now()) if vinculo else None
                if regla and regla.requiere_autorizacion:
                    prestaciones.append({"id": prestacion.pk, "nombre": prestacion.nombre, "codigo": prestacion.codigo})
        from .esperas import puede_continuar_autorizacion
        return Response({"caso": caso.pk, "intento": str(a.intento_actual(caso)), "prestaciones": prestaciones,
            "espera_autorizacion": caso.espera_autorizacion,
            "puede_continuar_autorizacion": puede_continuar_autorizacion(request.user, caso),
            "puede_solicitar": puede and bool(prestaciones), "motivo": "" if puede and prestaciones else "Verificá afiliación, paso actual y una regla que requiera autorización."})

    def _mutar(self, serializer, servicio, *, financiador):
        obj = self.get_object()
        if bool(self.ambito().get("financiador")) != financiador:
            raise PermissionDenied("Esta operación corresponde al otro ámbito de la solicitud.")
        entrada = serializer(data=self.request.data)
        entrada.is_valid(raise_exception=True)
        obj = servicio(solicitud=obj, usuario=self.request.user, **entrada.validated_data)
        obj = consulta_solicitudes().get(pk=obj.pk)
        respuesta = self.serializar(obj, detalle=True, financiador=self.ambito().get("financiador"))
        self.auditar_lectura([obj], self.ambito().get("financiador"))
        return Response(respuesta)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resolver(self, request, pk=None):
        return self._mutar(ResolverAutorizacionSerializer, a.resolver, financiador=True)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def reenviar(self, request, pk=None):
        return self._mutar(ReenviarAutorizacionSerializer, a.reenviar, financiador=False)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def anular(self, request, pk=None):
        return self._mutar(AnularAutorizacionSerializer, a.anular, financiador=False)
