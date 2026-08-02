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
    capacidad_requerida = "config"
    # `is_superuser` se filtra en el servidor porque el directorio lista sólo
    # candidatos a admin de institución. Excluirlos en el cliente descontaba de la
    # página ya paginada: el total quedaba mal y podían faltar usuarios reales.
    filter_fields = ("is_active", "is_staff", "is_superuser")
    search_fields = ["email", "nombre", "apellido"]
    ordering_fields = ["apellido", "nombre", "creado", "email"]

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
    capacidad_requerida = "config"
    institucion_path = "institucion"
    # `areas` filtra por la M2M: `?areas=3` devuelve el staff de esa área, que es
    # lo que necesita el selector de «reasignar» sin traerse todas las membresías.
    filter_fields = ("usuario", "institucion", "rol", "activo", "areas")
    search_fields = ("usuario__nombre", "usuario__apellido", "usuario__email")
    ordering_fields = ("usuario__apellido", "rol", "creado")


class LegajoProfesionalViewSet(BaseModelViewSet):
    queryset = LegajoProfesional.objects.select_related("usuario")
    serializer_class = LegajoProfesionalSerializer
    capacidad_requerida = "config"
    filter_fields = ("usuario",)
