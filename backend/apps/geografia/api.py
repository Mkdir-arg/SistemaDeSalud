from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from apps.accounts.models import Membresia
from apps.common import tiene_capacidad
from apps.financiadores.permisos import requerir_financiador
from .contrato import NIVELES
from .models import Catalogo, Lugar
from .servicios import ambito, visibles


class LugarLecturaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    origen = serializers.ChoiceField(choices=["georef", "manual"])
    provincia_id = serializers.IntegerField(allow_null=True)
    partido_id = serializers.IntegerField(allow_null=True)


class LugaresRespuestaSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.IntegerField(allow_null=True)
    results = LugarLecturaSerializer(many=True)


class EstadoCatalogoSerializer(serializers.Serializer):
    version = serializers.IntegerField()
    actualizado = serializers.DateTimeField(allow_null=True)
    error = serializers.CharField(allow_blank=True)


def autorizar_ambito(usuario, params):
    tipo, valor = params.get("ambito"), params.get("organizacion")
    if tipo is None and valor is None:
        return None
    if tipo not in ("institucion", "financiador"):
        raise ValidationError("Organización inválida.")
    pk = serializers.IntegerField(min_value=1, max_value=2**63 - 1).run_validation(valor)
    if tipo == "financiador":
        requerir_financiador(usuario, pk)
        return ambito(financiador_id=pk)
    if not (usuario.is_superuser or tiene_capacidad(usuario, "gobierno_plataforma")
            or Membresia.objects.filter(usuario=usuario, institucion_id=pk, activo=True).exists()):
        raise PermissionDenied("No tenés acceso a esta institución.")
    return ambito(institucion_id=pk)


class LugaresView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=LugaresRespuestaSerializer, parameters=[
        OpenApiParameter("tipo", OpenApiTypes.STR, enum=list(NIVELES)),
        OpenApiParameter("ambito", OpenApiTypes.STR, enum=["institucion", "financiador"]),
        OpenApiParameter("organizacion", OpenApiTypes.INT),
        OpenApiParameter("provincia", OpenApiTypes.INT), OpenApiParameter("partido", OpenApiTypes.INT),
        OpenApiParameter("search", OpenApiTypes.STR), OpenApiParameter("page", OpenApiTypes.INT),
    ])
    def get(self, request):
        params = request.query_params
        dueno = autorizar_ambito(request.user, params)
        tipo = params.get("tipo", "provincia")
        if tipo not in NIVELES:
            raise ValidationError("Tipo territorial inválido.")
        qs = visibles(dueno) if dueno else Lugar.objects.filter(origen="georef")
        qs = qs.filter(tipo=tipo, activo=True)
        for campo in ("provincia", "partido"):
            if params.get(campo):
                valor = serializers.IntegerField(min_value=1, max_value=2**63 - 1).run_validation(params[campo])
                qs = qs.filter(**{campo + "_id": valor})
        nombre = params.get("search", "").strip()
        if len(nombre) > 100:
            raise ValidationError("Búsqueda demasiado larga.")
        if nombre:
            qs = qs.filter(nombre__icontains=nombre)
        try:
            pagina = int(params.get("page", "1"))
            if not 1 <= pagina <= 10000:
                raise ValueError
        except ValueError:
            raise ValidationError("Página inválida.") from None
        total, inicio = qs.count(), (pagina - 1) * 30
        filas = list(qs.order_by("nombre", "pk").values("id", "nombre", "origen", "provincia_id", "partido_id")[inicio:inicio + 30])
        return Response({"count": total, "next": pagina + 1 if inicio + 30 < total else None, "results": filas})


class EstadoCatalogoView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=EstadoCatalogoSerializer)
    def get(self, request):
        c = Catalogo.objects.filter(pk=1).first()
        return Response({"version": c.version if c else 0, "actualizado": c.actualizado if c else None,
                         "error": c.error if c else "Catálogo sin cargar; podés ingresar lugares manualmente."})
