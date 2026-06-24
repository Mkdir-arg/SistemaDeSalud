from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common import BaseModelViewSet

from .models import LegajoProfesional, Membresia, Usuario
from .serializers import (
    LegajoProfesionalSerializer,
    MembresiaSerializer,
    UsuarioSerializer,
)


class UsuarioViewSet(BaseModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    filter_fields = ("is_active", "is_staff")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email", "nombre", "apellido"]
    ordering_fields = ["apellido", "nombre", "creado"]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Datos del usuario autenticado."""
        return Response(self.get_serializer(request.user).data)

    @action(detail=True, methods=["get"])
    def legajo(self, request, pk=None):
        """Dashboard del legajo profesional: métricas + actividad reciente."""
        from apps.casos.models import Caso, EventoCaso

        user = self.get_object()
        casos = Caso.objects.filter(asignado_a=user)
        atendidos = casos.filter(estado__in=[Caso.Estado.ATENDIDO, Caso.Estado.CERRADO]).count()
        pacientes = casos.exclude(ciudadano=None).values("ciudadano").distinct().count()
        eventos_qs = EventoCaso.objects.filter(autor=user).select_related("caso", "caso__ciudadano")
        atenciones = eventos_qs.filter(titulo__icontains="Atención").count()
        llamados_fila = eventos_qs.filter(titulo__icontains="Llamado desde la fila").count()
        recientes = list(eventos_qs.order_by("-fecha")[:10])
        actividad = [{
            "fecha": e.fecha,
            "paciente": (f"{e.caso.ciudadano.nombre} {e.caso.ciudadano.apellido}".strip()
                         if e.caso and e.caso.ciudadano_id else None),
            "accion": e.titulo,
            "caso": e.caso_id,
        } for e in recientes]
        legajo = getattr(user, "legajo", None)
        return Response({
            "usuario": {
                "id": user.id, "nombre": user.nombre_completo, "email": user.email,
                "especialidad": legajo.especialidad if legajo else "",
                "matricula": legajo.matricula if legajo else "",
            },
            "casos_atendidos": atendidos,
            "pacientes_vistos": pacientes,
            "atenciones": atenciones,
            "llamados_fila": llamados_fila,
            "ultima_actividad": recientes[0].fecha if recientes else None,
            "actividad": actividad,
        })


class MembresiaViewSet(BaseModelViewSet):
    queryset = Membresia.objects.select_related("usuario", "institucion").prefetch_related("areas")
    serializer_class = MembresiaSerializer
    institucion_path = "institucion"
    filter_fields = ("usuario", "institucion", "rol", "activo")


class LegajoProfesionalViewSet(BaseModelViewSet):
    queryset = LegajoProfesional.objects.select_related("usuario")
    serializer_class = LegajoProfesionalSerializer
    filter_fields = ("usuario",)
