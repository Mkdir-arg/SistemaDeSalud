"""Operaciones hospitalarias: ámbito institucional y permisos por acción."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes

from apps.accounts.models import Membresia
from apps.casos.models import Caso
from apps.common import ROL_CAPACIDADES, tiene_capacidad
from apps.finanzas.models import HechoAtencionCosteable, Prestacion
from apps.finanzas.permisos import alcance_financiero_q, concesiones_financieras_de, tiene_concesion_financiera
from apps.instituciones.models import Institucion
from apps.registros.models import normalizar_documento
from . import models as m
from . import serializers as s
from .cobertura import cotizacion, liberar, reservar, seleccionar_afiliacion
from .cobros import completar_pendiente, resolver_saldo, revisar_contexto
from .permisos import plataforma, requerir_caso, requerir_hospital
from .services import auditar
from . import vigencias
from .seguimiento import puede_seguimiento
from .views import CoberturaBaseViewSet, datos, entero


@extend_schema_view(**{
    nombre: extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    for nombre in ("opciones", "configurar", "vincular_prestacion", "convenio", "aceptar_convenio", "cerrar_convenio", "rechazar_convenio", "arancel", "afiliados", "afiliacion", "evaluar", "resolver", "recuperables", "revisar_contexto", "recuperar")
})
class CoberturaHospitalViewSet(CoberturaBaseViewSet):
    serializer_class = s.ReservaSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return m.ReservaCobertura.objects.none()
        qs = m.ReservaCobertura.objects.select_related("caso", "prestacion", "distribucion", "uso_autorizacion")
        if plataforma(self.request.user):
            return qs
        user = self.request.user
        financiero = Q(pk__in=[])
        for accion in ("ver_dinero", "resolver_cobertura"):
            financiero |= Q(hecho__isnull=False) & alcance_financiero_q(user, accion, institucion_path="hecho__institucion_id", area_path="hecho__area_origen_id", sensible_path="evaluacion__sensible")
            financiero |= Q(hecho__isnull=True) & alcance_financiero_q(user, accion, institucion_path="caso__institucion_id", area_path="evaluacion__area", sensible_path="evaluacion__sensible")
        # El operador asistencial ve importes de su área, sin acceso al libro de cobros.
        clinico = Q(pk__in=[])
        for miembro in Membresia.objects.filter(usuario=user, activo=True).prefetch_related("areas"):
            if "casos_operar" in ROL_CAPACIDADES.get(miembro.rol, set()):
                filtro = Q(caso__institucion_id=miembro.institucion_id)
                areas = list(miembro.areas.values_list("pk", flat=True))
                if areas:
                    filtro &= Q(caso__area_actual_id__in=areas)
                clinico |= filtro
        return qs.filter(financiero | clinico).distinct()

    def institucion(self):
        raw = self.request.query_params.get("institucion") or self.request.data.get("institucion")
        if not str(raw).isdigit():
            raise ValidationError("Indicá la institución.")
        return get_object_or_404(Institucion, pk=int(raw))

    def list(self, request):
        institucion = self.institucion()
        qs = self.get_queryset().filter(caso__institucion=institucion)
        if request.query_params.get("estado"):
            qs = qs.filter(estado=request.query_params["estado"])
        return self.lista(qs, self.serializer_class)

    @action(detail=False, methods=["get"])
    def opciones(self, request):
        institucion = self.institucion()
        user = request.user
        configurar = tiene_concesion_financiera(user, "configurar_cobros", institucion.pk)
        operar = tiene_capacidad(user, "casos_operar", institucion.pk)
        ver = puede_seguimiento(user, institucion.pk)
        resolver = concesiones_financieras_de(user, "resolver_cobertura").filter(membresia__institucion=institucion).exists()
        if not (configurar or operar or ver or resolver or plataforma(user)):
            raise PermissionDenied("No tenés acceso a cobertura en este hospital.")
        config = m.ConfiguracionHospital.objects.filter(institucion=institucion).first()
        casos = Caso.objects.filter(institucion=institucion).exclude(estado__in=Caso.ESTADOS_FINALIZADOS).order_by("-pk")
        if request.query_params.get("caso"):
            valor = request.query_params["caso"].strip()
            casos = casos.filter(pk=int(valor)) if valor.isdigit() else casos.none()
        if not plataforma(user):
            permitidos = Q(pk__in=[])
            roles = [rol for rol, caps in ROL_CAPACIDADES.items() if "casos_operar" in caps]
            for miembro in Membresia.objects.filter(usuario=user, activo=True, institucion=institucion, rol__in=roles).prefetch_related("areas"):
                areas = list(miembro.areas.values_list("pk", flat=True))
                permitidos |= Q(area_actual_id__in=areas) if areas else Q(institucion=institucion)
            casos = casos.filter(permitidos)
        return Response({
            "configuracion": {"activo": bool(config and config.activo), "dias_reserva_antigua": config.dias_reserva_antigua if config else 7},
            "permisos": {"configurar": configurar, "operar": operar or plataforma(user), "seguimiento": ver, "registrar_aceptacion": tiene_concesion_financiera(user, "registrar_aceptacion", institucion.pk), "resolver": tiene_concesion_financiera(user, "resolver_cobertura", institucion.pk)},
            "catalogo": s.CatalogoSerializer(m.PrestacionComun.objects.filter(activo=True), many=True).data,
            "prestaciones": [{"id": p.pk, "codigo": p.codigo, "nombre": p.nombre, "nodo_id": p.nodo_id, "comun": getattr(getattr(p, "vinculoprestacion", None), "comun_id", None)} for p in Prestacion.objects.filter(institucion=institucion, activo=True).select_related("vinculoprestacion")],
            "casos": [self.opcion_caso(c) for c in casos.select_related("ciudadano")[:100]],
            "convenios": s.ConvenioSerializer(m.Convenio.objects.filter(institucion=institucion), many=True).data,
            "financiadores": list(m.Financiador.objects.filter(activo=True).values("id", "nombre")),
        })

    @staticmethod
    def opcion_caso(caso):
        afiliacion = m.AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).select_related("afiliado__financiador").first()
        seleccion = None
        if afiliacion:
            seleccion = {"id": afiliacion.pk, "estado": afiliacion.estado, "financiador_nombre": afiliacion.afiliado.financiador.nombre if afiliacion.afiliado_id else "", "plan": afiliacion.plan_id}
        return {"id": caso.pk, "titulo": f"Caso {caso.pk}", "documento": caso.ciudadano.documento if caso.ciudadano_id else "", "version_id": caso.version_id, "afiliacion": seleccion}

    @action(detail=False, methods=["post"])
    def configurar(self, request):
        d = datos(request, {"institucion": serializers.PrimaryKeyRelatedField(queryset=Institucion.objects.all()), "activo": serializers.BooleanField(), "dias_reserva_antigua": serializers.IntegerField(min_value=1, max_value=365)})
        requerir_hospital(request.user, d["institucion"].pk, "configurar_cobros")
        with transaction.atomic():
            obj, _ = m.ConfiguracionHospital.objects.update_or_create(institucion=d.pop("institucion"), defaults=d)
            auditar(request.user, "configurar_cobertura", obj.pk, institucion=obj.institucion)
        return Response({"activo": obj.activo, "dias_reserva_antigua": obj.dias_reserva_antigua})

    @action(detail=False, methods=["post"], url_path="vincular-prestacion")
    def vincular_prestacion(self, request):
        d = datos(request, {"prestacion": serializers.PrimaryKeyRelatedField(queryset=Prestacion.objects.all()), "comun": serializers.PrimaryKeyRelatedField(queryset=m.PrestacionComun.objects.filter(activo=True))})
        requerir_hospital(request.user, d["prestacion"].institucion_id, "configurar_cobros")
        with transaction.atomic():
            obj, creado = m.VinculoPrestacion.objects.get_or_create(prestacion=d["prestacion"], defaults={"comun": d["comun"]})
            if not creado and obj.comun_id != d["comun"].pk:
                raise ValidationError("La prestación ya tiene un vínculo. Conservá su identidad histórica y creá otra prestación para un concepto diferente.")
            auditar(request.user, "vincular_prestacion", obj.pk, institucion=d["prestacion"].institucion)
        return Response({"id": obj.pk, "comun": obj.comun_id})

    @action(detail=False, methods=["post"])
    def convenio(self, request):
        d = datos(request, {"institucion": serializers.PrimaryKeyRelatedField(queryset=Institucion.objects.all()), "financiador": serializers.PrimaryKeyRelatedField(queryset=m.Financiador.objects.filter(activo=True))})
        requerir_hospital(request.user, d["institucion"].pk, "configurar_cobros")
        obj = vigencias.proponer_convenio(usuario=request.user, origen="hospital", **d)
        return Response(s.ConvenioSerializer(obj).data, status=201)

    @action(detail=False, methods=["post"], url_path="aceptar-convenio")
    def aceptar_convenio(self, request):
        d = datos(request, {"convenio": entero()})
        obj = get_object_or_404(m.Convenio, pk=d["convenio"])
        obj = vigencias.aceptar_convenio(usuario=request.user, convenio=obj, origen="hospital")
        return Response(s.ConvenioSerializer(obj).data)

    def _cerrar_convenio(self, request, rechazar=False):
        d = datos(request, {"convenio": serializers.PrimaryKeyRelatedField(queryset=m.Convenio.objects.all()), "motivo": serializers.CharField(max_length=255)})
        obj = vigencias.cerrar_convenio(usuario=request.user, origen="hospital", rechazar=rechazar, **d)
        return Response(s.ConvenioSerializer(obj).data)

    @action(detail=False, methods=["post"], url_path="cerrar-convenio")
    def cerrar_convenio(self, request):
        return self._cerrar_convenio(request)

    @action(detail=False, methods=["post"], url_path="rechazar-convenio")
    def rechazar_convenio(self, request):
        return self._cerrar_convenio(request, rechazar=True)

    @action(detail=False, methods=["post"])
    def arancel(self, request):
        """Importe nulo vuelve expresamente al arancel general; no inicia una negociación."""
        d = datos(request, {"convenio": serializers.PrimaryKeyRelatedField(queryset=m.Convenio.objects.filter(estado="activo")), "prestacion": serializers.PrimaryKeyRelatedField(queryset=Prestacion.objects.all()), "importe": serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), allow_null=True), "vigente_desde": serializers.DateField()})
        prestacion = d["prestacion"]
        requerir_hospital(request.user, prestacion.institucion_id, "configurar_cobros", sensible=prestacion.politicacobro_set.filter(sensible=True).exists())
        if d["convenio"].institucion_id != prestacion.institucion_id or d["vigente_desde"] < timezone.localdate():
            raise ValidationError("Elegí un convenio del mismo hospital y una vigencia actual o futura.")
        with transaction.atomic():
            convenio = m.Convenio.objects.select_for_update().get(pk=d["convenio"].pk)
            if convenio.estado != "activo":
                raise ValidationError("El convenio ya no está activo. Actualizá la consulta.")
            obj = m.ArancelConvenio.objects.create(**d, creado_por=request.user)
            auditar(request.user, "arancel_excepcion", obj.pk, institucion=prestacion.institucion)
        return Response({"id": obj.pk}, status=201)

    @action(detail=False, methods=["get"])
    def afiliados(self, request):
        institucion = self.institucion()
        documento = normalizar_documento(request.query_params.get("documento", ""))
        if not tiene_capacidad(request.user, "casos_operar", institucion.pk) and not plataforma(request.user):
            reserva = get_object_or_404(self.get_queryset(), pk=request.query_params.get("reserva"), caso__institucion=institucion)
            requerir_hospital(request.user, institucion.pk, "resolver_cobertura", reserva.hecho.area_origen_id if reserva.hecho_id else reserva.caso.area_actual_id, reserva.evaluacion.get("sensible", True))
            ciudadano = reserva.hecho.ciudadano if reserva.hecho_id else reserva.caso.ciudadano
            if not ciudadano or documento != normalizar_documento(ciudadano.documento):
                raise PermissionDenied("La búsqueda administrativa corresponde al paciente de este saldo.")
        if not documento:
            return Response([])
        qs = vigencias.afiliados_vigentes().filter(documento=documento, financiador_id__in=vigencias.convenios_vigentes().filter(institucion=institucion).values("financiador_id")).filter(Q(plan__isnull=True) | Q(plan__activo=True))
        return Response([{**s.AfiliadoSerializer(a).data, "financiador": a.financiador_id, "financiador_nombre": a.financiador.nombre} for a in qs.select_related("financiador")[:30]])

    @action(detail=False, methods=["post"])
    def afiliacion(self, request):
        d = datos(request, {"caso": serializers.PrimaryKeyRelatedField(queryset=Caso.objects.all()), "afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.all(), allow_null=True, required=False), "particular": serializers.BooleanField(default=False), "declaracion": serializers.CharField(max_length=160, allow_blank=True, default=""), "motivo": serializers.CharField(max_length=255)})
        obj = seleccionar_afiliacion(usuario=request.user, **d)
        return Response({"id": obj.pk, "estado": obj.estado, "plan": obj.plan_id}, status=201)

    def entrada_evaluacion(self, request, confirmar=False):
        campos = {"caso": serializers.PrimaryKeyRelatedField(queryset=Caso.objects.all()), "prestacion": serializers.PrimaryKeyRelatedField(queryset=Prestacion.objects.all()), "fecha": serializers.DateField(), "cantidad": serializers.IntegerField(min_value=1, max_value=100000)}
        if confirmar:
            campos.update(clave=serializers.UUIDField(), firma=serializers.CharField(max_length=10000), acepta=serializers.BooleanField(default=False))
        d = datos(request, campos)
        requerir_caso(request.user, d["caso"])
        return d

    @action(detail=False, methods=["post"])
    def evaluar(self, request):
        return Response(cotizacion(**self.entrada_evaluacion(request)))

    @extend_schema(request=OpenApiTypes.OBJECT, responses=s.ReservaSerializer)
    @action(detail=False, methods=["post"])
    def reservar(self, request):
        obj = reservar(usuario=request.user, **self.entrada_evaluacion(request, confirmar=True))
        return Response(self.get_serializer(obj).data, status=201)

    @extend_schema(request=OpenApiTypes.OBJECT, responses=s.ReservaSerializer)
    @action(detail=True, methods=["post"])
    def liberar(self, request, pk=None):
        reserva = self.get_object()
        d = datos(request, {"motivo": serializers.CharField(max_length=255), "no_realizada": serializers.BooleanField()})
        obj = liberar(reserva=reserva, usuario=request.user, **d)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def resolver(self, request, pk=None):
        reserva = self.get_object()
        d = datos(request, {"decision": serializers.ChoiceField(choices=["asumir", "rechazar", "paciente", "financiador"]), "parte": serializers.ChoiceField(choices=["paciente", "financiador"], default="paciente"), "importe": serializers.DecimalField(max_digits=14, decimal_places=2), "motivo": serializers.CharField(max_length=255), "evidencia": serializers.CharField(max_length=5000, allow_blank=True, default=""), "clave": serializers.UUIDField()})
        obj = resolver_saldo(reserva=reserva, usuario=request.user, **d)
        return Response({"id": obj.pk, "decision": obj.decision, "obligacion": obj.obligacion_id})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=s.ReservaSerializer)
    @action(detail=True, methods=["post"])
    def completar(self, request, pk=None):
        reserva = self.get_object()
        d = datos(request, {"motivo": serializers.CharField(max_length=255), "arancel": serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True), "afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.all(), required=False, allow_null=True), "particular": serializers.BooleanField(default=False)})
        completar_pendiente(reserva=reserva, usuario=request.user, **d)
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=False, methods=["get"])
    def recuperables(self, request):
        institucion = self.institucion()
        qs = HechoAtencionCosteable.objects.filter(institucion=institucion).filter(Q(snapshot_cobro__isnull=True) | Q(snapshot_cobro__capturado=False)).exclude(cobertura_contexto={})
        if not plataforma(request.user):
            qs = qs.filter(alcance_financiero_q(request.user, "resolver_cobertura", institucion_path="institucion_id", area_path="area_origen_id", sensible_path=None))
            # La sensibilidad todavía puede ser desconocida: exigir concesión sensible.
            qs = [h for h in qs.order_by("pk")[:100] if tiene_concesion_financiera(request.user, "resolver_cobertura", h.institucion_id, h.area_origen_id, sensible=True)]
        else:
            qs = qs.order_by("pk")[:100]
        return Response([{"id": h.pk, "caso": h.caso_origen_id, "fecha": h.ocurrida_en, "contexto_pendiente": bool(h.cobertura_contexto.get("pendiente")), "afiliaciones": list(m.AfiliacionCaso.objects.filter(caso_id=h.caso_origen_id, creado__lte=h.ocurrida_en).values("id", "estado", "declaracion")), "prestaciones": list(Prestacion.objects.filter(institucion=institucion, nodo_id=h.nodo_origen_id).values("id", "nombre"))} for h in qs])

    @action(detail=False, methods=["post"], url_path="revisar-contexto")
    def revisar_contexto(self, request):
        d = datos(request, {"hecho": serializers.PrimaryKeyRelatedField(queryset=HechoAtencionCosteable.objects.all()), "motivo": serializers.CharField(max_length=255), "afiliacion": serializers.PrimaryKeyRelatedField(queryset=m.AfiliacionCaso.objects.all(), allow_null=True), "prestaciones": serializers.PrimaryKeyRelatedField(queryset=Prestacion.objects.all(), many=True)})
        obj = revisar_contexto(usuario=request.user, **d)
        return Response({"capturado": obj.capturado})

    @action(detail=False, methods=["post"])
    def recuperar(self, request):
        from apps.finanzas.cobros import capturar_cobros_atencion
        d = datos(request, {"hecho": serializers.PrimaryKeyRelatedField(queryset=HechoAtencionCosteable.objects.all())})
        hecho = d["hecho"]
        requerir_hospital(request.user, hecho.institucion_id, "resolver_cobertura", hecho.area_origen_id, sensible=True)
        obj = capturar_cobros_atencion(hecho.pk)
        return Response({"capturado": obj.capturado})
