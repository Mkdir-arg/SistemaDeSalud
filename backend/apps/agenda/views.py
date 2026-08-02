from datetime import date

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common import BaseModelViewSet
from apps.registros.models import Ciudadano

from . import motor
from .models import Agenda, Bloqueo, Disponibilidad, Turno
from .serializers import (
    AgendaSerializer, BloqueoSerializer, DisponibilidadSerializer, TurnoSerializer,
)


def _fecha(texto, por_defecto=None):
    try:
        return date.fromisoformat(texto)
    except (TypeError, ValueError):
        return por_defecto or timezone.localdate()


class AgendaViewSet(BaseModelViewSet):
    """
    Agendas de profesional y de recurso.

    Crear una agenda o cargarle horarios es configurar la institución
    (`config`); consultar la grilla del día es operación de mostrador, y por eso
    la lectura queda abierta a cualquier miembro.
    """

    queryset = Agenda.objects.select_related("area", "profesional", "flujo").prefetch_related(
        "disponibilidades"
    )
    serializer_class = AgendaSerializer
    capacidad_requerida = "config"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "tipo", "profesional", "activa")
    search_fields = ("nombre",)
    ordering_fields = ("nombre", "creada")
    nombre_csv = "agendas"
    columnas_csv = [
        ("nombre", "Agenda"),
        ("tipo_display", "Tipo"),
        ("area_nombre", "Área"),
        ("profesional_nombre", "Profesional"),
        ("duracion_min", "Duración (min)"),
        ("activa", "Activa"),
    ]

    @action(detail=True, methods=["get"])
    def dia(self, request, pk=None):
        """
        Grilla de un día: `?fecha=2026-08-11`. Sin fecha, hoy.

        Devuelve todos los horarios, ocupados incluidos. Quien atiende el
        mostrador necesita la grilla completa para poder decir «a las 10 está
        con otro paciente, ¿le sirve 10:20?».
        """
        agenda = self.get_object()
        fecha = _fecha(request.query_params.get("fecha"))
        return Response({
            "agenda": {"id": agenda.id, "nombre": agenda.nombre,
                       "sobreturnos_max": agenda.sobreturnos_max},
            "fecha": fecha,
            "horarios": motor.horarios_del_dia(agenda, fecha),
        })

    @action(detail=True, methods=["get"], url_path="proximos-libres")
    def proximos_libres(self, request, pk=None):
        """Los próximos horarios libres, para dar un turno sin mirar día por día."""
        agenda = self.get_object()
        try:
            cuantos = min(int(request.query_params.get("cuantos", 10)), 50)
        except ValueError:
            cuantos = 10
        return Response({"horarios": motor.proximos_libres(agenda, cuantos=cuantos)})


class DisponibilidadViewSet(BaseModelViewSet):
    queryset = Disponibilidad.objects.select_related("agenda")
    serializer_class = DisponibilidadSerializer
    capacidad_requerida = "config"
    institucion_path = "agenda__institucion"
    filter_fields = ("agenda", "agenda__institucion", "dia_semana", "activa")


class BloqueoViewSet(BaseModelViewSet):
    """
    Vacaciones, feriados, mantenimiento.

    Es `trabajo` y no `config`: bloquear una tarde porque el profesional se
    tuvo que ir es una decisión del día a día, no una reconfiguración de la
    institución.
    """

    queryset = Bloqueo.objects.select_related("agenda")
    serializer_class = BloqueoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "agenda__institucion"
    filter_fields = ("agenda", "agenda__institucion")


class TurnoViewSet(BaseModelViewSet):
    """
    Turnos dados.

    `POST /api/turnos/` da un turno; el estado después se mueve sólo con las
    acciones, que además abren el caso o liberan el horario.
    """

    queryset = Turno.objects.select_related("agenda__area", "ciudadano", "caso")
    serializer_class = TurnoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "agenda__institucion"
    filter_fields = (
        "agenda", "agenda__institucion", "agenda__area", "ciudadano", "estado", "sobreturno",
    )
    search_fields = ("ciudadano__nombre", "ciudadano__apellido", "ciudadano__documento")
    ordering_fields = ("inicio", "creado", "estado")
    nombre_csv = "turnos"
    columnas_csv = [
        ("inicio", "Fecha y hora"),
        ("paciente", "Paciente"),
        ("documento", "Documento"),
        ("agenda_nombre", "Agenda"),
        ("area_nombre", "Área"),
        ("estado_display", "Estado"),
        ("sobreturno", "Sobreturno"),
        ("motivo", "Motivo"),
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        # Rango de fechas: es como se mira una agenda («la semana que viene»),
        # y sin esto la pantalla tendría que traerse todos los turnos históricos
        # y descartar en el cliente.
        p = self.request.query_params
        if (d := p.get("desde")):
            qs = qs.filter(inicio__date__gte=_fecha(d))
        if (h := p.get("hasta")):
            qs = qs.filter(inicio__date__lte=_fecha(h))
        return qs

    def create(self, request, *args, **kwargs):
        """
        Da un turno. Pasa por el motor y no por el serializer: la comprobación
        de horario libre y la reserva tienen que ir bajo el mismo candado —dos
        personas pueden estar sacando el mismo horario a la vez, una por
        teléfono y otra en el mostrador—.
        """
        agenda = Agenda.objects.filter(pk=request.data.get("agenda")).first()
        ciudadano = Ciudadano.objects.filter(pk=request.data.get("ciudadano")).first()
        if agenda is None or ciudadano is None:
            return Response({"detail": "Falta la agenda o el paciente."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, agenda)
        inicio = serializers_parse_dt(request.data.get("inicio"))
        if inicio is None:
            return Response({"detail": "Falta el horario del turno."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            turno = motor.reservar(
                agenda, ciudadano, inicio, autor=request.user,
                motivo=(request.data.get("motivo") or "").strip(),
                origen=request.data.get("origen") or Turno.Origen.MOSTRADOR,
                sobreturno=bool(request.data.get("sobreturno")),
            )
        except motor.ErrorAgenda as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(turno).data, status=status.HTTP_201_CREATED)

    def _accion(self, request, fn, **kw):
        turno = self.get_object()
        try:
            turno = fn(turno, autor=request.user, **kw)
        except motor.ErrorAgenda as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(turno).data)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Cancela el turno y libera el horario (cuerpo opcional: {"motivo": "..."})."""
        return self._accion(request, motor.cancelar, motivo=(request.data.get("motivo") or "").strip())

    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        """El paciente avisó que viene."""
        return self._accion(request, motor.confirmar)

    @action(detail=True, methods=["post"])
    def ausente(self, request, pk=None):
        """No vino y no avisó. No libera el horario: la hora se perdió igual."""
        return self._accion(request, motor.marcar_ausente)

    @action(detail=True, methods=["post"])
    def llegada(self, request, pk=None):
        """Se presentó: abre el caso en el flujo de la agenda."""
        return self._accion(request, motor.registrar_llegada)


def serializers_parse_dt(valor):
    """Parsea el horario que manda la pantalla, con o sin zona."""
    from django.utils.dateparse import parse_datetime

    if not valor:
        return None
    dt = parse_datetime(valor)
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt
