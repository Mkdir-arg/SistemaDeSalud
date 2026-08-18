from datetime import date, datetime, time, timedelta

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
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
    filter_fields = ("institucion", "area", "tipo", "profesional", "activa", "modalidad")
    search_fields = ("nombre",)
    ordering_fields = ("nombre", "creada")
    nombre_csv = "agendas"
    columnas_csv = [
        ("nombre", "Agenda"),
        ("tipo_display", "Tipo"),
        ("modalidad_display", "Modalidad"),
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
                       "sobreturnos_max": agenda.sobreturnos_max,
                       "modalidad": agenda.modalidad,
                       "enlace_virtual": agenda.enlace_virtual},
            "fecha": fecha,
            "horarios": motor.horarios_del_dia(agenda, fecha),
        })

    @action(detail=True, methods=["get"])
    def semana(self, request, pk=None):
        """
        Grilla de siete días: `?desde=2026-08-17`. Sin fecha, el lunes de esta semana.

        Es «¿qué tiene la doctora esta semana?», que con la grilla de un día se
        contesta apretando «Día siguiente» siete veces. Va en una sola respuesta
        y con tres consultas, no siete pedidos.
        """
        agenda = self.get_object()
        pedida = _fecha(request.query_params.get("desde"))
        # Siempre arranca en lunes: una semana que empieza un miércoles no se
        # puede comparar con la de al lado ni con el horario semanal cargado.
        lunes = pedida - timedelta(days=pedida.weekday())
        return Response({
            "agenda": {"id": agenda.id, "nombre": agenda.nombre,
                       "sobreturnos_max": agenda.sobreturnos_max,
                       "modalidad": agenda.modalidad,
                       "enlace_virtual": agenda.enlace_virtual},
            "desde": lunes,
            "dias": motor.grilla_de_dias(agenda, lunes, dias=7),
        })

    @action(detail=True, methods=["get"], url_path="proximos-libres")
    def proximos_libres(self, request, pk=None):
        """
        Los próximos horarios libres, para dar un turno sin mirar día por día.

        `?desde=2026-08-20` arranca en esa fecha en vez de hoy: quien está
        mirando el 20 y necesita el siguiente hueco no quiere que le ofrezcan
        el de mañana.
        """
        agenda = self.get_object()
        try:
            cuantos = min(int(request.query_params.get("cuantos", 10)), 50)
        except ValueError:
            cuantos = 10
        desde = None
        if (d := request.query_params.get("desde")):
            fecha = _fecha(d)
            arranque = timezone.make_aware(
                datetime.combine(fecha, time.min), timezone.get_current_timezone()
            )
            # Nunca hacia atrás: un hueco de la semana pasada no se puede dar.
            desde = max(arranque, timezone.now())
        return Response({"horarios": motor.proximos_libres(agenda, desde=desde, cuantos=cuantos)})


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

    def get_queryset(self):
        qs = super().get_queryset()
        # Rango de fechas, como en los turnos: la pantalla de la semana dibuja
        # los bloqueos encima de la grilla y sin esto tendría que traerse todas
        # las vacaciones de la historia de la agenda para descartarlas en el
        # cliente. Un bloqueo cuenta si TOCA el rango, no si empieza adentro: el
        # que arranca el viernes anterior y termina el martes es el que tapa el
        # lunes que se está mirando.
        p = self.request.query_params
        if (d := p.get("desde")):
            qs = qs.filter(hasta__date__gte=_fecha(d))
        if (h := p.get("hasta")):
            qs = qs.filter(desde__date__lte=_fecha(h))
        return qs

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def create(self, request, *args, **kwargs):
        """
        Bloquea un rango y devuelve, en `turnos_afectados`, los turnos que
        quedan adentro.

        Bloquear NO cancela nada: los turnos siguen dados. Sin esta lista nadie
        se entera de que el bloqueo de las 7 de la mañana pisó doce turnos, y
        esos doce pacientes viajan al hospital para nada. La pantalla la usa
        para pedir confirmación y para tener a quién llamar.
        """
        r = super().create(request, *args, **kwargs)
        bloqueo = Bloqueo.objects.select_related("agenda").get(pk=r.data["id"])
        afectados = motor.turnos_en_rango(bloqueo.agenda, bloqueo.desde, bloqueo.hasta)
        r.data["turnos_afectados"] = TurnoSerializer(afectados, many=True).data
        return r


class TurnoViewSet(BaseModelViewSet):
    """
    Turnos dados.

    `POST /api/turnos/` da un turno; el estado después se mueve sólo con las
    acciones, que además abren el caso o liberan el horario.
    """

    # Sin DELETE: el turno que no va se cancela, no se borra. Borrarlo saca de
    # la base la evidencia de un turno que se perdió, que es justo el dato con
    # el que se calcula el ausentismo del servicio —y deja al paciente que
    # reclama sin nada que mostrar—.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    # `resuelto_por` va acá porque el serializer muestra quién movió el turno:
    # sin traerlo, un listado de 30 filas hace 30 consultas más que uno de 3.
    queryset = Turno.objects.select_related(
        "agenda__area", "ciudadano", "caso", "resuelto_por"
    )
    serializer_class = TurnoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "agenda__institucion"
    filter_fields = (
        "agenda", "agenda__institucion", "agenda__area", "ciudadano", "estado", "sobreturno",
        "modalidad",
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
        ("modalidad_display", "Modalidad"),
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
                modalidad=request.data.get("modalidad") or None,
                enlace=str(request.data.get("enlace") or "").strip(),
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

    @action(detail=True, methods=["post"])
    def modalidad(self, request, pk=None):
        """
        Pasa el turno a virtual o a presencial: `{"modalidad": "virtual"}`.

        Cuerpo opcional `{"enlace": "https://…"}` para usar una sala distinta a
        la de la agenda. Va por acá y no por un PATCH porque hay que comprobar
        que la agenda atienda de esa forma y copiar la sala: un turno virtual sin
        enlace deja al paciente esperando una llamada que nadie va a hacer.
        """
        pedida = request.data.get("modalidad")
        if pedida not in Turno.Modalidad.values:
            return Response({"detail": "Modalidad inválida: presencial o virtual."},
                            status=status.HTTP_400_BAD_REQUEST)
        enlace = request.data.get("enlace")
        return self._accion(
            request, motor.cambiar_modalidad, modalidad=pedida,
            # `str()` porque el cuerpo lo arma un cliente: un número suelto acá
            # rompía con un 500 en vez de contestar qué está mal.
            enlace=None if enlace is None else str(enlace).strip(),
        )

    @action(detail=True, methods=["post"])
    def reprogramar(self, request, pk=None):
        """
        Mueve el turno a otro horario: `{"inicio": "2026-08-20T10:00:00"}`.

        Va por acá y no por un PATCH a `inicio` porque reprogramar tiene que
        pasar por las mismas reglas que dar el turno —grilla, bloqueos,
        ocupación— y bajo el mismo candado.
        """
        inicio = serializers_parse_dt(request.data.get("inicio"))
        if inicio is None:
            return Response({"detail": "Falta el horario nuevo del turno."},
                            status=status.HTTP_400_BAD_REQUEST)
        return self._accion(request, motor.reprogramar, nuevo_inicio=inicio)


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
