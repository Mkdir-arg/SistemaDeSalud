from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.common import OrdenEstable

from .models import AccesoClinico


class PuedeAuditar(BasePermission):
    """
    Quién puede leer el registro de accesos.

    El registro dice quién miró la historia de quién: es tan sensible como lo
    que audita. Lo ven el superusuario de plataforma y los roles de conducción
    —admin de institución y jefe de área—, que son quienes tienen que responder
    ante un reclamo. Un médico no audita a sus colegas.
    """

    def has_permission(self, request, view):
        u = request.user
        if not (u and u.is_authenticated):
            return False
        if u.is_superuser:
            return True
        return u.membresias.filter(activo=True, rol__in=["admin", "jefe_area"]).exists()


class AccesoClinicoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)
    paciente = serializers.SerializerMethodField()
    documento = serializers.CharField(source="ciudadano.documento", read_only=True, default=None)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    institucion_nombre = serializers.CharField(
        source="institucion.nombre", read_only=True, default=None
    )

    class Meta:
        model = AccesoClinico
        fields = [
            "id", "usuario", "usuario_nombre", "usuario_email", "ciudadano", "paciente",
            "documento", "institucion", "institucion_nombre", "tipo", "tipo_display",
            "recurso", "objeto_id", "detalle", "resultados", "ip", "momento",
        ]
        read_only_fields = fields

    def get_usuario_nombre(self, obj) -> str | None:
        return obj.usuario.nombre_completo if obj.usuario_id else None

    def get_paciente(self, obj) -> str | None:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None


class AccesoClinicoViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    Registro de accesos a datos clínicos (Ley 26.529).

    **Sólo lectura, y a propósito.** No hay create, update ni delete: un
    registro de auditoría que se puede escribir o borrar desde la API no sirve
    para auditar nada. Lo escribe el sistema al leer, y nadie más.
    """

    queryset = AccesoClinico.objects.select_related("usuario", "ciudadano", "institucion")
    serializer_class = AccesoClinicoSerializer
    permission_classes = [IsAuthenticated, PuedeAuditar]
    filter_backends = [OrdenEstable, SearchFilter]
    search_fields = (
        "usuario__email", "usuario__nombre", "usuario__apellido",
        "ciudadano__documento", "ciudadano__apellido", "recurso",
    )
    ordering_fields = ("momento", "usuario", "recurso")

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if not u.is_superuser:
            # Cada institución audita lo suyo. Los accesos sin institución
            # —listados que no apuntan a un paciente— quedan para el
            # superusuario de plataforma.
            ids = list(u.membresias.filter(activo=True).values_list("institucion_id", flat=True))
            qs = qs.filter(institucion_id__in=ids)
        p = self.request.query_params
        for campo in ("ciudadano", "usuario", "tipo", "recurso"):
            if p.get(campo):
                qs = qs.filter(**{campo: p[campo]})
        if p.get("desde"):
            qs = qs.filter(momento__date__gte=p["desde"])
        if p.get("hasta"):
            qs = qs.filter(momento__date__lte=p["hasta"])
        return qs

    @action(detail=False, methods=["get"], url_path="de-paciente")
    def de_paciente(self, request):
        """
        Quién consultó la historia de una persona: `?ciudadano=<id>`.

        Es el derecho concreto que da la ley —el paciente puede pedir esta
        lista— y por eso está separado del listado general: quien atiende un
        reclamo necesita esta respuesta, no un filtro más entre otros.
        """
        cid = request.query_params.get("ciudadano")
        if not cid:
            return Response({"detail": "Falta el paciente."}, status=400)
        qs = self.filter_queryset(self.get_queryset()).filter(ciudadano_id=cid)
        pagina = self.paginate_queryset(qs)
        datos = self.get_serializer(pagina if pagina is not None else qs, many=True).data
        if pagina is not None:
            return self.get_paginated_response(datos)
        return Response(datos)
