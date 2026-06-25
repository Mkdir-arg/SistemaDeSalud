from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common import BaseModelViewSet

from . import motor
from .models import Caso, EventoCaso, ItemFila, ValorCampo
from .serializers import (
    CasoDetalleSerializer,
    CasoSerializer,
    EventoCasoSerializer,
    ItemFilaSerializer,
    ValorCampoSerializer,
)


class CasoViewSet(BaseModelViewSet):
    queryset = Caso.objects.select_related(
        "institucion", "version__flujo", "ciudadano", "nodo_actual", "area_actual", "asignado_a",
        "origen__version__flujo",
    ).prefetch_related("valores", "eventos", "nodo_actual__grupos", "derivados__version__flujo")
    institucion_path = "institucion"
    filter_fields = ("institucion", "version", "estado", "prioridad", "area_actual", "asignado_a")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CasoDetalleSerializer
        return CasoSerializer

    def get_serializer_context(self):
        # Para resolver `puede_tomar` sin N+1: precomputamos los grupos del usuario.
        ctx = super().get_serializer_context()
        u = self.request.user
        if u and u.is_authenticated:
            ctx["es_superuser"] = u.is_superuser
            ctx["user_grupo_ids"] = set(u.grupos.values_list("id", flat=True))
        return ctx

    def perform_create(self, serializer):
        # El ingreso siempre es de una persona: aseguramos su historia clínica.
        caso = serializer.save()
        motor.asegurar_historia(caso)

    @action(detail=True, methods=["get"])
    def eventos(self, request, pk=None):
        """Línea de tiempo (trazabilidad) del caso."""
        caso = self.get_object()
        data = EventoCasoSerializer(caso.eventos.all(), many=True).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def tomar(self, request, pk=None):
        """Asigna el caso al usuario autenticado y registra el evento.

        Solo puede tomarlo quien integre alguno de los grupos responsables del
        paso actual (si el paso no declara grupos, queda abierto a todos).
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        caso.asignado_a = request.user
        caso.save(update_fields=["asignado_a", "actualizado"])
        EventoCaso.objects.create(
            caso=caso,
            titulo="Caso tomado",
            detalle=f"Asignado a {request.user.nombre_completo}",
            autor=request.user,
            nodo=caso.nodo_actual,
        )
        # Re-consulta para refrescar el prefetch de eventos/valores.
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)

    @action(detail=True, methods=["post"])
    def llamar(self, request, pk=None):
        """Llama al caso desde un box (cuerpo: {"box_id": <id>}).

        Solo puede llamar quien integre un grupo responsable del paso.
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            motor.llamar(caso, box_id=request.data.get("box_id"), autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def receta(self, request, pk=None):
        """El médico emite una receta (cuerpo: {"detalle": "..."}) en la HC del paciente."""
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response({"detail": "No integrás ningún grupo responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)
        detalle = (request.data.get("detalle") or "").strip()
        if not detalle:
            return Response({"detail": "La receta necesita un detalle."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            motor.agregar_receta(caso, detalle, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def estudio(self, request, pk=None):
        """El médico solicita un estudio (cuerpo: {"tipo": "..."}) en la HC del paciente."""
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response({"detail": "No integrás ningún grupo responsable de este paso."}, status=status.HTTP_403_FORBIDDEN)
        tipo = (request.data.get("tipo") or "").strip()
        if not tipo:
            return Response({"detail": "Indicá el tipo de estudio."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            motor.agregar_estudio(caso, tipo, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        """Coloca el caso en el nodo Inicio y lo corre hasta la 1ª parada."""
        caso = self.get_object()
        try:
            motor.iniciar(caso, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)

    @action(detail=True, methods=["post"])
    def avanzar(self, request, pk=None):
        """
        Completa el nodo actual con los datos enviados y avanza al siguiente.
        Cuerpo según el tipo de nodo (ver `motor.avanzar`).
        """
        caso = self.get_object()
        if not motor.usuario_puede_tomar(request.user, caso):
            return Response(
                {"detail": "No integrás ningún grupo responsable de este paso."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            motor.avanzar(caso, datos=request.data or {}, autor=request.user)
        except motor.ErrorMotor as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        caso = self.get_queryset().get(pk=caso.pk)
        return Response(CasoDetalleSerializer(caso).data)


class ValorCampoViewSet(BaseModelViewSet):
    queryset = ValorCampo.objects.select_related("caso", "campo", "nodo")
    serializer_class = ValorCampoSerializer
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "campo")


class ItemFilaViewSet(BaseModelViewSet):
    queryset = ItemFila.objects.select_related("caso__ciudadano", "nodo__version__flujo__area", "box")
    serializer_class = ItemFilaSerializer
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "nodo", "urgente", "atendido", "nodo__version__flujo__area")


class EventoCasoViewSet(BaseModelViewSet):
    queryset = EventoCaso.objects.select_related("caso", "autor", "nodo")
    serializer_class = EventoCasoSerializer
    institucion_path = "caso__institucion"
    filter_fields = ("caso", "autor")
