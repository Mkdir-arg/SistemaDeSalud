"""API de organizaciones pagadoras; los ámbitos nunca se deducen de un id hospitalario."""
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes
from config.pagination import Paginacion

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import normalizar_documento
from . import models as m
from . import serializers as s
from .permisos import plataforma, requerir_financiador
from .services import auditar, registrar_afiliado, registrar_consumo_externo, corregir_consumo, corregir_identidad
from . import vigencias
from .acceso import actividad_visible
from .actividad import FiltrosActividad, consultar_actividad


def datos(request, campos):
    serializer = serializers.Serializer(data=request.data)
    serializer.fields.update(campos)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def entero():
    return serializers.IntegerField(min_value=1)


class CoberturaBaseViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = Paginacion

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
        elif isinstance(exc, IntegrityError):
            exc = ValidationError("Ya existe un registro con esos identificadores. Actualizá la consulta antes de reintentar.")
        return super().handle_exception(exc)

    def lista(self, queryset, serializer):
        pagina = self.paginate_queryset(queryset.order_by("pk"))
        return self.get_paginated_response(serializer(pagina, many=True, context={"request": self.request}).data)


@extend_schema_view(
    activar=extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT),
    aceptar_convenio=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ConvenioSerializer),
    corregir_consumo=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ConsumoSerializer),
    corregir_identidad=extend_schema(request=OpenApiTypes.OBJECT, responses=s.AfiliadoSerializer),
    editar_plan=extend_schema(request=OpenApiTypes.OBJECT, responses=s.PlanSerializer),
    finalizar_afiliacion=extend_schema(request=OpenApiTypes.OBJECT, responses=s.AfiliadoSerializer),
    reactivar_afiliacion=extend_schema(request=OpenApiTypes.OBJECT, responses=s.AfiliadoSerializer),
    cerrar_convenio=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ConvenioSerializer),
    rechazar_convenio=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ConvenioSerializer),
    actividad=extend_schema(parameters=[FiltrosActividad], responses={200: OpenApiTypes.OBJECT, (200, "text/csv"): OpenApiTypes.BINARY}),
    aranceles=extend_schema(responses=OpenApiTypes.OBJECT),
    instituciones=extend_schema(responses=OpenApiTypes.OBJECT),
    usuarios=extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT),
    confirmar_importacion=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ImportacionSerializer),
    plantilla=extend_schema(responses={(200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY}),
    rechazos=extend_schema(responses={(200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY}),
    resumen=extend_schema(responses=OpenApiTypes.OBJECT),
    plazo_autorizacion=extend_schema(request=OpenApiTypes.OBJECT, responses=s.ConvenioSerializer),
)
class FinanciadorViewSet(CoberturaBaseViewSet):
    serializer_class = s.FinanciadorSerializer

    @extend_schema(methods=["GET"], responses=s.CatalogoSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.CatalogoSerializer, responses=s.CatalogoSerializer)
    @action(detail=False, methods=["get", "post"], url_path="catalogo-comun")
    def catalogo_comun(self, request):
        """Catálogo de plataforma, también cuando todavía no existe financiador."""
        if not plataforma(request.user):
            raise PermissionDenied("El catálogo común es administrado por plataforma.")
        if request.method == "POST":
            d = datos(request, {k: serializers.CharField(max_length=n) for k, n in [
                ("codigo", 60), ("nombre", 160), ("categoria", 80),
            ]})
            item = m.PrestacionComun.objects.create(**d)
            return Response(s.CatalogoSerializer(item).data, status=201)
        return self.lista(m.PrestacionComun.objects.filter(activo=True), s.CatalogoSerializer)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        return response

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return m.Financiador.objects.none()
        qs = m.Financiador.objects.all()
        if not plataforma(self.request.user):
            qs = qs.filter(membresiafinanciador__usuario=self.request.user, membresiafinanciador__activo=True, activo=True)
        return qs.distinct()

    def organizacion(self, escritura=False, admin=False):
        obj = self.get_object()
        requerir_financiador(self.request.user, obj.pk, escritura=escritura, admin=admin)
        return obj

    def list(self, request):
        return self.lista(self.get_queryset(), self.serializer_class)

    @transaction.atomic
    def create(self, request):
        if not plataforma(request.user):
            raise PermissionDenied("Sólo plataforma puede crear financiadores.")
        d = datos(request, {"nombre": serializers.CharField(max_length=160), "tipo": serializers.ChoiceField(choices=["obra_social", "mutual", "otro"])})
        obj = m.Financiador.objects.create(**d)
        auditar(request.user, "crear_financiador", obj.pk, financiador=obj)
        return Response(self.get_serializer(obj).data, status=201)

    @extend_schema(methods=["GET"], responses=s.PlanSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.PlanSerializer, responses=s.PlanSerializer)
    @action(detail=True, methods=["get", "post"])
    def planes(self, request, pk=None):
        org = self.organizacion(admin=request.method == "POST")
        if request.method == "GET":
            return self.lista(m.Plan.objects.filter(financiador=org), s.PlanSerializer)
        d = datos(request, {"codigo": serializers.CharField(max_length=60), "nombre": serializers.CharField(max_length=160)})
        with transaction.atomic():
            plan = m.Plan.objects.create(financiador=org, **d)
            auditar(request.user, "crear_plan", plan.pk, financiador=org)
        return Response(s.PlanSerializer(plan).data, status=201)

    @action(detail=True, methods=["post"], url_path="editar-plan")
    def editar_plan(self, request, pk=None):
        org = self.organizacion(admin=True)
        d = datos(request, {"plan": serializers.PrimaryKeyRelatedField(queryset=m.Plan.objects.filter(financiador=org)), "nombre": serializers.CharField(max_length=160), "activo": serializers.BooleanField(), "motivo": serializers.CharField(max_length=255)})
        return Response(s.PlanSerializer(vigencias.editar_plan(usuario=request.user, **d)).data)

    @action(detail=True, methods=["post"], url_path="finalizar-afiliacion")
    def finalizar_afiliacion(self, request, pk=None):
        org = self.organizacion(escritura=True)
        d = datos(request, {"afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.filter(financiador=org)), "motivo": serializers.CharField(max_length=255)})
        return Response(s.AfiliadoSerializer(vigencias.finalizar_afiliacion(usuario=request.user, **d)).data)

    @action(detail=True, methods=["post"], url_path="reactivar-afiliacion")
    def reactivar_afiliacion(self, request, pk=None):
        org = self.organizacion(escritura=True)
        d = datos(request, {"afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.filter(financiador=org)), "plan": serializers.PrimaryKeyRelatedField(queryset=m.Plan.objects.filter(financiador=org, activo=True), allow_null=True), "motivo": serializers.CharField(max_length=255)})
        return Response(s.AfiliadoSerializer(vigencias.reactivar_afiliacion(usuario=request.user, **d)).data)

    @extend_schema(methods=["GET"], responses=s.CatalogoSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.CatalogoSerializer, responses=s.CatalogoSerializer)
    @action(detail=True, methods=["get", "post"])
    def catalogo(self, request, pk=None):
        self.organizacion()
        if request.method == "POST":
            if not plataforma(request.user):
                raise PermissionDenied("El catálogo común es administrado por plataforma.")
            d = datos(request, {k: serializers.CharField(max_length=n) for k, n in [("codigo", 60), ("nombre", 160), ("categoria", 80)]})
            item = m.PrestacionComun.objects.create(**d)
            return Response(s.CatalogoSerializer(item).data, status=201)
        return self.lista(m.PrestacionComun.objects.filter(activo=True), s.CatalogoSerializer)

    @extend_schema(methods=["GET"], responses=s.ReglaSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.ReglaSerializer, responses=s.ReglaSerializer)
    @action(detail=True, methods=["get", "post"])
    def reglas(self, request, pk=None):
        org = self.organizacion(admin=request.method == "POST")
        if request.method == "GET":
            return self.lista(m.ReglaCobertura.objects.filter(financiador=org), s.ReglaSerializer)
        d = datos(request, {"plan": serializers.PrimaryKeyRelatedField(queryset=m.Plan.objects.filter(financiador=org), required=False, allow_null=True), "prestacion": serializers.PrimaryKeyRelatedField(queryset=m.PrestacionComun.objects.filter(activo=True), required=False, allow_null=True), "categoria": serializers.CharField(max_length=80, required=False, allow_blank=True, default=""), "porcentaje": serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=100), "cupo": serializers.IntegerField(min_value=0, required=False, allow_null=True), "periodo": serializers.ChoiceField(choices=["mes", "anio"]), "vigente_desde": serializers.DateField(), "requiere_autorizacion": serializers.BooleanField(default=False)})
        if bool(d.get("prestacion")) == bool(d.get("categoria")):
            raise ValidationError("Elegí una prestación o una categoría del catálogo.")
        if d.get("categoria") and not m.PrestacionComun.objects.filter(categoria=d["categoria"], activo=True).exists():
            raise ValidationError("La categoría no pertenece al catálogo común.")
        if d["vigente_desde"] < timezone.localdate():
            raise ValidationError("Las reglas nuevas se aplican desde hoy o una fecha futura.")
        with transaction.atomic():
            regla = m.ReglaCobertura.objects.create(financiador=org, creado_por=request.user, **d)
            auditar(request.user, "version_regla", regla.pk, financiador=org)
        return Response(s.ReglaSerializer(regla).data, status=201)

    @extend_schema(methods=["GET"], responses=s.AfiliadoSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.AfiliadoSerializer, responses=s.AfiliadoSerializer)
    @action(detail=True, methods=["get", "post"])
    def padron(self, request, pk=None):
        org = self.organizacion(escritura=request.method == "POST")
        if request.method == "GET":
            qs = m.Afiliado.objects.filter(financiador=org)
            if request.query_params.get("documento"):
                qs = qs.filter(documento=normalizar_documento(request.query_params["documento"]))
            if request.query_params.get("search"):
                busqueda = request.query_params["search"].strip()
                qs = qs.filter(Q(numero__icontains=busqueda) | Q(nombre__icontains=busqueda) | Q(documento__icontains=normalizar_documento(busqueda)))
            auditar(request.user, "consultar_padron", org.pk, financiador=org)
            return self.lista(qs, s.AfiliadoSerializer)
        d = datos(request, {"numero": serializers.CharField(max_length=80), "documento": serializers.CharField(max_length=80), "nombre": serializers.CharField(max_length=160), "plan": serializers.PrimaryKeyRelatedField(queryset=m.Plan.objects.filter(financiador=org), allow_null=True, required=False, default=None), "desde": serializers.DateField()})
        obj = registrar_afiliado(financiador=org, usuario=request.user, **d)
        return Response(s.AfiliadoSerializer(obj).data, status=201)

    @extend_schema(methods=["GET"], responses=s.ConsumoSerializer(many=True))
    @extend_schema(methods=["POST"], request=s.ConsumoSerializer, responses=s.ConsumoSerializer)
    @action(detail=True, methods=["get", "post"])
    def consumos(self, request, pk=None):
        org = self.organizacion(escritura=request.method == "POST")
        if request.method == "GET":
            qs = m.ConsumoExterno.objects.filter(financiador=org)
            if request.query_params.get("search"):
                busqueda = request.query_params["search"].strip()
                qs = qs.filter(Q(referencia__icontains=busqueda) | Q(afiliado__nombre__icontains=busqueda) | Q(afiliado__numero__icontains=busqueda) | Q(prestacion__codigo__icontains=busqueda))
            auditar(request.user, "consultar_consumos_externos", org.pk, financiador=org)
            return self.lista(qs, s.ConsumoSerializer)
        d = datos(request, {"afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.filter(financiador=org)), "prestacion": serializers.PrimaryKeyRelatedField(queryset=m.PrestacionComun.objects.all()), "fecha": serializers.DateField(), "cantidad": entero(), "referencia": serializers.CharField(max_length=120, required=False, allow_blank=True, default=""), "motivo_duplicado": serializers.CharField(max_length=255, required=False, allow_blank=True, default="")})
        obj = registrar_consumo_externo(financiador=org, usuario=request.user, **d)
        return Response(s.ConsumoSerializer(obj).data, status=201)

    @action(detail=True, methods=["post"], url_path="corregir-identidad")
    def corregir_identidad(self, request, pk=None):
        org = self.organizacion(escritura=True)
        d = datos(request, {"afiliado": serializers.PrimaryKeyRelatedField(queryset=m.Afiliado.objects.filter(financiador=org)), "numero": serializers.CharField(max_length=80), "documento": serializers.CharField(max_length=80), "motivo": serializers.CharField(max_length=255)})
        return Response(s.AfiliadoSerializer(corregir_identidad(usuario=request.user, **d)).data)

    @action(detail=True, methods=["get"])
    def actividad(self, request, pk=None):
        org = self.organizacion()
        return consultar_actividad(self, request, org)

    @action(detail=True, methods=["get"])
    def aranceles(self, request, pk=None):
        from .cobertura import arancel_aplicable

        org = self.organizacion()
        convenios = {x.institucion_id: x for x in vigencias.convenios_vigentes().filter(financiador=org)}
        qs = m.VinculoPrestacion.objects.filter(prestacion__institucion_id__in=convenios, prestacion__activo=True, comun__activo=True).select_related("prestacion__institucion", "comun").order_by("prestacion__institucion__nombre", "prestacion__nombre", "pk")
        if request.query_params.get("search"):
            texto = request.query_params["search"].strip()
            qs = qs.filter(Q(prestacion__institucion__nombre__icontains=texto) | Q(prestacion__nombre__icontains=texto) | Q(comun__codigo__icontains=texto))
        corte = timezone.now()
        fecha = timezone.localtime(corte).date()
        items = []
        for vinculo in self.paginate_queryset(qs):
            prestacion = vinculo.prestacion
            convenio = convenios[prestacion.institucion_id]
            politica, excepcion, arancel = arancel_aplicable(prestacion=prestacion, convenio=convenio, fecha=fecha, corte=corte)
            estado = "politica_pendiente" if not politica else "sin_cobro" if not politica.cobrar else "arancel_pendiente" if arancel is None else "vigente"
            vigente_desde = excepcion.vigente_desde if excepcion else timezone.localtime(politica.vigente_desde).date() if politica else None
            items.append({
                "id": prestacion.pk, "convenio": convenio.pk, "hospital": prestacion.institucion.nombre,
                "prestacion": prestacion.nombre, "codigo": vinculo.comun.codigo,
                "arancel_general": str(politica.importe) if politica and politica.importe is not None else None,
                "arancel": "0.00" if estado == "sin_cobro" else str(arancel) if arancel is not None else None,
                "origen_arancel": "acordado_financiador" if excepcion and excepcion.importe is not None else "general_hospital",
                "retorno_arancel_general": bool(excepcion and excepcion.importe is None),
                "cobrar": bool(politica and politica.cobrar), "estado": estado,
                "vigente_desde": vigente_desde, "fecha_consulta": fecha,
            })
        auditar(request.user, "consultar_aranceles", org.pk, financiador=org)
        return self.get_paginated_response(items)

    @action(detail=True, methods=["post"], url_path="corregir-consumo")
    def corregir_consumo(self, request, pk=None):
        org = self.organizacion(escritura=True)
        d = datos(request, {"consumo": serializers.PrimaryKeyRelatedField(queryset=m.ConsumoExterno.objects.filter(financiador=org)), "cantidad": serializers.IntegerField(min_value=0, max_value=100000), "motivo": serializers.CharField(max_length=255)})
        return Response(s.ConsumoSerializer(corregir_consumo(usuario=request.user, **d)).data)

    @action(detail=True, methods=["get"])
    def instituciones(self, request, pk=None):
        self.organizacion()
        return Response(list(Institucion.objects.filter(activa=True, estado="activa").values("id", "nombre")))

    @extend_schema(methods=["GET"], responses=s.ConvenioSerializer(many=True))
    @extend_schema(methods=["POST"], request=OpenApiTypes.OBJECT, responses=s.ConvenioSerializer)
    @action(detail=True, methods=["get", "post"])
    def convenios(self, request, pk=None):
        org = self.organizacion(admin=request.method == "POST")
        if request.method == "GET":
            return self.lista(m.Convenio.objects.filter(financiador=org).select_related("institucion"), s.ConvenioSerializer)
        d = datos(request, {"institucion": serializers.PrimaryKeyRelatedField(queryset=Institucion.objects.filter(activa=True))})
        obj = vigencias.proponer_convenio(usuario=request.user, financiador=org, origen="financiador", **d)
        return Response(s.ConvenioSerializer(obj).data, status=201)

    @action(detail=True, methods=["post"], url_path="aceptar-convenio")
    def aceptar_convenio(self, request, pk=None):
        org = self.organizacion(admin=True)
        d = datos(request, {"convenio": entero()})
        convenio = get_object_or_404(m.Convenio, pk=d["convenio"], financiador=org)
        convenio = vigencias.aceptar_convenio(usuario=request.user, convenio=convenio, origen="financiador")
        return Response(s.ConvenioSerializer(convenio).data)

    def _cerrar_convenio(self, request, rechazar=False):
        org = self.organizacion(admin=True)
        d = datos(request, {"convenio": serializers.PrimaryKeyRelatedField(queryset=m.Convenio.objects.filter(financiador=org)), "motivo": serializers.CharField(max_length=255)})
        obj = vigencias.cerrar_convenio(usuario=request.user, origen="financiador", rechazar=rechazar, **d)
        return Response(s.ConvenioSerializer(obj).data)

    @action(detail=True, methods=["post"], url_path="cerrar-convenio")
    def cerrar_convenio(self, request, pk=None):
        return self._cerrar_convenio(request)

    @action(detail=True, methods=["post"], url_path="rechazar-convenio")
    def rechazar_convenio(self, request, pk=None):
        return self._cerrar_convenio(request, rechazar=True)

    @action(detail=True, methods=["post"], url_path="plazo-autorizacion")
    def plazo_autorizacion(self, request, pk=None):
        org = self.organizacion(admin=True)
        d = datos(request, {"convenio": entero(), "plazo_autorizacion_horas": serializers.IntegerField(min_value=1, max_value=8760, allow_null=True), "motivo": serializers.CharField(max_length=255)})
        with transaction.atomic():
            convenio = get_object_or_404(m.Convenio.objects.select_for_update(), pk=d["convenio"], financiador=org)
            if convenio.estado not in ["propuesto", "activo"]:
                raise ValidationError("Un convenio cerrado conserva sus condiciones históricas.")
            convenio.plazo_autorizacion_horas = d["plazo_autorizacion_horas"]
            convenio.save(update_fields=["plazo_autorizacion_horas"])
            auditar(request.user, "plazo_autorizacion", convenio.pk, financiador=org, institucion=convenio.institucion, motivo=d["motivo"])
        return Response(s.ConvenioSerializer(convenio).data)

    @action(detail=True, methods=["get", "post"])
    def usuarios(self, request, pk=None):
        org = self.organizacion(admin=True)
        if request.method == "GET":
            return Response([{"id": x.pk, "rol": x.rol, "activo": x.activo, "email": x.usuario.email, "nombre": x.usuario.nombre, "resuelve_autorizaciones": x.resuelve_autorizaciones} for x in m.MembresiaFinanciador.objects.filter(financiador=org).select_related("usuario")])
        d = datos(request, {"email": serializers.EmailField(), "nombre": serializers.CharField(max_length=120), "rol": serializers.ChoiceField(choices=["admin", "operador", "auditor"]), "activo": serializers.BooleanField(default=True), "resuelve_autorizaciones": serializers.BooleanField(required=False)})
        if d["rol"] == "auditor" and d.get("resuelve_autorizaciones"):
            raise ValidationError("El rol auditor conserva lectura. Para resolver, designá un operador o administrador explícitamente.")
        with transaction.atomic():
            m.Financiador.objects.select_for_update().get(pk=org.pk)
            user, nuevo = Usuario.objects.get_or_create(email=d["email"], defaults={"nombre": d["nombre"]})
            if nuevo:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            anterior = m.MembresiaFinanciador.objects.filter(financiador=org, usuario=user, activo=True, rol="admin").first()
            if anterior and (d["rol"] != "admin" or not d["activo"]) and not m.MembresiaFinanciador.objects.filter(financiador=org, activo=True, rol="admin").exclude(pk=anterior.pk).exists():
                raise ValidationError("Designá otro administrador antes de retirar este acceso.")
            membresia, _ = m.MembresiaFinanciador.objects.get_or_create(financiador=org, usuario=user, defaults={"rol": d["rol"], "activo": d["activo"], "creo_cuenta": nuevo})
            membresia.rol, membresia.activo = d["rol"], d["activo"]
            membresia.resuelve_autorizaciones = d.get("resuelve_autorizaciones", membresia.resuelve_autorizaciones) if d["rol"] != "auditor" else False
            membresia.save(update_fields=["rol", "activo", "resuelve_autorizaciones"])
            auditar(request.user, "membresia_financiador", membresia.pk, financiador=org,
                motivo=f"rol={membresia.rol}; activo={membresia.activo}; resuelve_autorizaciones={membresia.resuelve_autorizaciones}")
        respuesta = {"id": membresia.pk, "email": user.email, "nombre": user.nombre, "rol": membresia.rol, "resuelve_autorizaciones": membresia.resuelve_autorizaciones}
        if membresia.creo_cuenta and membresia.activo and not user.has_usable_password():
            uid = urlsafe_base64_encode(str(user.pk).encode())
            respuesta["activacion"] = f"/financiadores/activar?uid={uid}&token={default_token_generator.make_token(user)}"
        return Response(respuesta, status=201)

    @action(detail=False, methods=["post"], permission_classes=[AllowAny])
    def activar(self, request):
        d = datos(request, {"uid": serializers.CharField(max_length=100), "token": serializers.CharField(max_length=200), "password": serializers.CharField(max_length=128)})
        try:
            user = Usuario.objects.get(pk=force_str(urlsafe_base64_decode(d["uid"])))
        except (ValueError, TypeError, OverflowError, Usuario.DoesNotExist):
            raise ValidationError("El enlace de activación no es válido.")
        with transaction.atomic():
            user = Usuario.objects.select_for_update().get(pk=user.pk)
            if user.has_usable_password() or not user.is_active or not default_token_generator.check_token(user, d["token"]):
                raise ValidationError("El enlace de activación no es válido o ya fue utilizado.")
            validate_password(d["password"], user)
            user.set_password(d["password"])
            user.save(update_fields=["password"])
        return Response({"detail": "La cuenta está activa. Ya podés iniciar sesión."})

    @extend_schema(methods=["GET"], responses=s.ImportacionSerializer(many=True))
    @extend_schema(methods=["POST"], request={"multipart/form-data": {"type": "object", "required": ["archivo", "tipo", "clave"], "properties": {"archivo": {"type": "string", "format": "binary"}, "tipo": {"type": "string", "enum": ["padron", "consumos"]}, "clave": {"type": "string", "format": "uuid"}}}}, responses=s.ImportacionSerializer)
    @action(detail=True, methods=["get", "post"])
    def importaciones(self, request, pk=None):
        org = self.organizacion(escritura=request.method == "POST")
        if request.method == "GET":
            qs = m.Importacion.objects.filter(financiador=org).order_by("-pk")
            if request.query_params.get("tipo"):
                qs = qs.filter(tipo=request.query_params["tipo"])
            pagina = self.paginate_queryset(qs)
            auditar(request.user, "consultar_importaciones", org.pk, financiador=org)
            return self.get_paginated_response(s.ImportacionSerializer(pagina, many=True).data)
        from .importaciones import previsualizar_importacion
        d = datos(request, {"archivo": serializers.FileField(), "tipo": serializers.ChoiceField(choices=["padron", "consumos"]), "clave": serializers.UUIDField()})
        obj = previsualizar_importacion(financiador=org, usuario=request.user, **d)
        return Response(s.ImportacionSerializer(obj).data, status=201)

    @action(detail=True, methods=["post"], url_path="confirmar-importacion")
    def confirmar_importacion(self, request, pk=None):
        org = self.organizacion(escritura=True)
        from .importaciones import aplicar_importacion
        d = datos(request, {"importacion": serializers.PrimaryKeyRelatedField(queryset=m.Importacion.objects.filter(financiador=org)), "revisiones_duplicados": serializers.DictField(child=serializers.CharField(max_length=255), required=False)})
        obj = aplicar_importacion(usuario=request.user, **d)
        return Response(s.ImportacionSerializer(obj).data)

    def archivo(self, contenido, nombre, org, accion, objeto):
        auditar(self.request.user, accion, objeto, financiador=org)
        response = HttpResponse(contenido, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
        response["Cache-Control"] = "private, no-store"
        return response

    @action(detail=True, methods=["get"])
    def plantilla(self, request, pk=None):
        org = self.organizacion(escritura=True)
        from .importaciones import generar_plantilla
        tipo = request.query_params.get("tipo", "consumos")
        contenido = generar_plantilla(financiador=org, usuario=request.user, tipo=tipo)
        return self.archivo(contenido, "plantilla", org, "descargar_plantilla", tipo)

    @action(detail=True, methods=["get"])
    def rechazos(self, request, pk=None):
        org = self.organizacion()
        from .importaciones import descargar_rechazadas
        obj = get_object_or_404(m.Importacion, pk=request.query_params.get("importacion"), financiador=org)
        return self.archivo(descargar_rechazadas(importacion=obj, usuario=request.user), "filas-para-corregir", org, "descargar_rechazos", obj.pk)

    @action(detail=True, methods=["get"])
    def resumen(self, request, pk=None):
        org = self.organizacion()
        return Response({"planes": m.Plan.objects.filter(financiador=org).count(), "afiliados": m.Afiliado.objects.filter(financiador=org).count(), "consumos": m.ConsumoExterno.objects.filter(financiador=org).count(), "discrepancias": actividad_visible(org).filter(discrepancia=True).count()})
