"""
Los datos del paciente en toda la red (#121): turnos, llamado, resultados y
cobertura.

Todas las vistas heredan de `_ConCuenta` (sólo el token del portal) y piden
`IdentidadValidada`. Ninguna recibe un id de institución ni de ciudadano: la
persona sale siempre de la cuenta (ver `red.persona_de`), y un id que no es
suyo responde 404, igual que uno que no existe.

R2: nunca se devuelven evoluciones, recetas, casos ni la historia clínica.
"""
import ipaddress
from datetime import timedelta

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from apps.agenda import motor as agenda
from apps.agenda.models import Turno
from apps.auditoria.models import AccesoClinico
from apps.casos.models import ItemFila
from apps.casos.views import VIGENCIA_LLAMADO_H
from apps.common import institucion_de_archivo, partes_de_ruta_clinica, respuesta_de_archivo
from apps.financiadores.models import VinculoCiudadano
from apps.financiadores.vigencias import afiliados_vigentes
from apps.registros.models import ArchivoClinico, Estudio

from .autenticacion import IdentidadValidada
from .red import patron_documento, persona_de
from .views import ETIQUETA, _ConCuenta, _error, _ip

# R3: cancelar hasta 24 horas antes del turno.
ANTICIPACION_CANCELAR = timedelta(hours=24)
# Cuánto hacia atrás se listan los turnos ya pasados.
TURNOS_RECIENTES = timedelta(days=90)
# Un paciente que entró a la fila hace más que esto y nunca salió es un ítem
# olvidado, no alguien esperando. Más largo que la vigencia del llamado: una
# espera de guardia puede pasar las 8 horas.
ESPERA_VIGENTE = timedelta(hours=24)
MOTIVO_CANCELACION = "cancelado por el paciente"
NO_ENCONTRADO = "No encontramos ese turno."


class _DelPaciente(_ConCuenta):
    permission_classes = [IdentidadValidada]


def _institucion(inst):
    return {"id": inst.id, "nombre": inst.nombre} if inst else None


def _no_cancelable(turno, ahora):
    """Por qué el paciente no puede cancelar este turno, o None si puede."""
    if turno.estado not in (Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO):
        return "Este turno ya no se puede cancelar."
    if turno.inicio - ahora <= ANTICIPACION_CANCELAR:
        return "Faltan menos de 24 horas para el turno. Para cancelarlo, comunicate con la institución."
    return None


def _no_confirmable(turno, ahora):
    if turno.estado != Turno.Estado.RESERVADO:
        return "Sólo se puede confirmar un turno reservado."
    if turno.inicio <= ahora:
        return "El turno ya pasó."
    return None


def _turno(t, ahora):
    no_cancelable = _no_cancelable(t, ahora)
    agenda_ = t.agenda
    return {
        "id": t.id,
        "institucion": _institucion(agenda_.institucion),
        "agenda": agenda_.nombre,
        "area": agenda_.area.nombre if agenda_.area_id else None,
        "profesional": agenda_.profesional.nombre_completo if agenda_.profesional_id else None,
        "inicio": t.inicio,
        "fin": t.fin,
        "modalidad": t.modalidad,
        # La sala sólo mientras el turno sigue en pie.
        "enlace": t.enlace if t.es_virtual and t.estado in (Turno.Estado.RESERVADO, Turno.Estado.CONFIRMADO) else "",
        "estado": t.estado,
        "estado_display": t.get_estado_display(),
        "confirmado_via": t.confirmado_via,
        "cancelado_via": t.cancelado_via,
        "puede_confirmar": _no_confirmable(t, ahora) is None,
        "puede_cancelar": no_cancelable is None,
        "motivo_no_cancelable": no_cancelable,
    }


_RELACIONES_TURNO = ("agenda__institucion", "agenda__area", "agenda__profesional")


def _turnos_de(persona):
    return Turno.objects.filter(ciudadano_id__in=persona.ids).select_related(*_RELACIONES_TURNO)


class TurnosView(_DelPaciente):
    @extend_schema(tags=ETIQUETA, summary="Mis turnos en toda la red", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Los próximos y los de los últimos 90 días, de todas las instituciones."""
        ahora = timezone.now()
        persona = persona_de(request.user)
        turnos = _turnos_de(persona).filter(inicio__gte=ahora - TURNOS_RECIENTES).order_by("inicio", "id")
        return Response({"turnos": [_turno(t, ahora) for t in turnos]})


class _AccionTurno(_DelPaciente):
    def _turno(self, request, pk):
        return _turnos_de(persona_de(request.user)).filter(pk=pk).first()

    def _responder(self, turno):
        turno = Turno.objects.select_related(*_RELACIONES_TURNO).get(pk=turno.pk)
        return Response(_turno(turno, timezone.now()))


class ConfirmarTurnoView(_AccionTurno):
    @extend_schema(tags=ETIQUETA, summary="Confirmar asistencia", request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, pk):
        turno = self._turno(request, pk)
        if turno is None:
            return _error(NO_ENCONTRADO, "no_encontrado", status.HTTP_404_NOT_FOUND)
        motivo = _no_confirmable(turno, timezone.now())
        if motivo:
            return _error(motivo, "no_confirmable", status.HTTP_409_CONFLICT)
        try:
            agenda.confirmar(turno, autor=None, via=Turno.Via.PORTAL)
        except agenda.ErrorAgenda as exc:
            return _error(str(exc), "no_confirmable", status.HTTP_409_CONFLICT)
        return self._responder(turno)


class CancelarTurnoView(_AccionTurno):
    @extend_schema(tags=ETIQUETA, summary="Cancelar un turno", request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request, pk):
        """R3: sólo un turno reservado o confirmado que empieza en más de 24 horas."""
        turno = self._turno(request, pk)
        if turno is None:
            return _error(NO_ENCONTRADO, "no_encontrado", status.HTTP_404_NOT_FOUND)
        motivo = _no_cancelable(turno, timezone.now())
        if motivo:
            return _error(motivo, "no_cancelable", status.HTTP_409_CONFLICT)
        try:
            agenda.cancelar(turno, autor=None, motivo=MOTIVO_CANCELACION, via=Turno.Via.PORTAL)
        except agenda.ErrorAgenda as exc:
            return _error(str(exc), "no_cancelable", status.HTTP_409_CONFLICT)
        return self._responder(turno)


class LlamadoView(_DelPaciente):
    @extend_schema(tags=ETIQUETA, summary="¿Me están llamando?", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Liviano: la app lo consulta cada 5 segundos.

        `llamado` si un box llamó al paciente dentro de la vigencia del llamado
        (la misma que la pantalla de la sala), `en_espera` si está en una fila
        sin llamar, `sin_fila` si no.
        """
        ahora = timezone.now()
        persona = persona_de(request.user)
        en_fila = ItemFila.objects.filter(caso__ciudadano_id__in=persona.ids, atendido=False)
        llamado = (
            en_fila.filter(box__isnull=False, llamado_at__isnull=False)
            .annotate(ultimo=Coalesce("rellamado_at", "llamado_at"))
            .filter(ultimo__gte=ahora - timedelta(hours=VIGENCIA_LLAMADO_H))
            .select_related("box", "caso__institucion")
            .order_by("-ultimo")
            .first()
        )
        if llamado:
            return Response({
                "estado": "llamado",
                "box": llamado.box.nombre,
                "institucion": _institucion(llamado.caso.institucion),
                "llamado_at": llamado.ultimo,
                "veces": llamado.veces_llamado,
            })
        espera = (
            en_fila.filter(box__isnull=True, ingreso__gte=ahora - ESPERA_VIGENTE)
            .select_related("caso__institucion").order_by("-ingreso").first()
        )
        if espera:
            return Response({"estado": "en_espera", "institucion": _institucion(espera.caso.institucion)})
        return Response({"estado": "sin_fila"})


def _estudios_de(persona):
    return Estudio.objects.filter(historia__ciudadano_id__in=persona.ids).select_related(
        "historia__ciudadano__institucion",
    )


def _archivo_del_estudio(estudio):
    """La ruta del archivo de un estudio realizado, o None si no tiene uno válido."""
    if not estudio.realizado or partes_de_ruta_clinica(estudio.archivo) is None:
        return None
    return estudio.archivo


class ResultadosView(_DelPaciente):
    @extend_schema(tags=ETIQUETA, summary="Mis estudios", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Todos los estudios, también los solicitados sin resultado todavía."""
        persona = persona_de(request.user)
        estudios = []
        for e in _estudios_de(persona).order_by("-fecha", "-id"):
            realizado = e.realizado
            estudios.append({
                "id": e.id,
                "tipo": e.tipo,
                "fecha": e.fecha,
                "institucion": _institucion(e.historia.ciudadano.institucion),
                "realizado": realizado,
                "resultado": e.resultado if realizado else "",
                "resultado_display": e.get_resultado_display() if realizado and e.resultado else "",
                "descargable": _archivo_del_estudio(e) is not None,
            })
        return Response({"resultados": estudios})


class ArchivoResultadoView(_DelPaciente):
    @extend_schema(tags=ETIQUETA, summary="Descargar un estudio", responses=OpenApiTypes.BINARY)
    def get(self, request, pk):
        """R4: un estudio ajeno, o sin archivo, responde 404. Cada descarga queda auditada."""
        cuenta = request.user
        estudio = _estudios_de(persona_de(cuenta)).filter(pk=pk).first()
        ruta = _archivo_del_estudio(estudio) if estudio else None
        if ruta is None:
            return _error("No encontramos ese estudio.", "no_encontrado", status.HTTP_404_NOT_FOUND)
        ciudadano = estudio.historia.ciudadano
        meta = ArchivoClinico.objects.filter(ruta=ruta).first()
        # El archivo tiene que ser de la institución del estudio. Si `archivo`
        # apunta a otra, no se sirve aunque el estudio sea del paciente: si no,
        # quien carga un estudio en un hospital podría exponer un archivo de
        # otro.
        if (meta and meta.proposito == ArchivoClinico.Proposito.CONSENTIMIENTO) or (
            institucion_de_archivo(ruta, meta) != ciudadano.institucion_id
        ):
            return _error("No encontramos ese estudio.", "no_encontrado", status.HTTP_404_NOT_FOUND)
        respuesta = respuesta_de_archivo(ruta, meta)
        if respuesta is None:
            return _error("El archivo no está disponible. Consultá en la institución.", "no_encontrado",
                          status.HTTP_404_NOT_FOUND)
        AccesoClinico.objects.create(
            cuenta_paciente=cuenta,
            ciudadano=ciudadano,
            institucion_id=ciudadano.institucion_id,
            tipo=AccesoClinico.Tipo.PACIENTE,
            recurso="estudios",
            objeto_id=str(estudio.pk),
            detalle="descarga desde el portal",
            ip=_ip_valida(request),
        )
        return respuesta


def _ip_valida(request):
    """La IP para `AccesoClinico.ip`, o None.

    En PostgreSQL la columna es `inet`: un valor que no es una IP (un proxy mal
    configurado que deja pasar el `X-Forwarded-For` entero) haría fallar la
    escritura del registro, y con ella la descarga.
    """
    ip = _ip(request)
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


class CoberturaView(_DelPaciente):
    @extend_schema(tags=ETIQUETA, summary="Mi cobertura", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        """Afiliaciones vigentes por documento.

        - `confirmada`: algún hospital vinculó la afiliación a un registro de
          esta persona que pasa R1. Es la confirmación fuerte.
        - Sin vínculo, se muestra igual con `confirmada=false`: coincide el
          documento, pero nadie lo verificó (decisión del 08/10/2026).
        - Si un vínculo apunta a un registro descartado por fecha de
          nacimiento, la afiliación es de otra persona y no se muestra.
        """
        cuenta = request.user
        persona = persona_de(cuenta)
        patron = patron_documento(cuenta.documento)
        if patron is None:
            return Response({"coberturas": []})
        afiliados = list(
            afiliados_vigentes()
            .filter(documento__regex=patron)
            .filter(Q(plan__isnull=True) | Q(plan__activo=True))
            .select_related("financiador", "plan")
            .order_by("financiador__nombre", "id")
        )
        vinculos = {}
        for afiliado_id, ciudadano_id in VinculoCiudadano.objects.filter(
            afiliado__in=afiliados,
        ).values_list("afiliado_id", "ciudadano_id"):
            vinculos.setdefault(afiliado_id, set()).add(ciudadano_id)
        propios = set(persona.ids)
        coberturas = []
        for a in afiliados:
            vinculados = vinculos.get(a.id, set())
            if vinculados & persona.descartados:
                continue
            coberturas.append({
                "id": a.id,
                "financiador": a.financiador.nombre,
                "financiador_tipo": a.financiador.get_tipo_display(),
                "plan": a.plan.nombre if a.plan_id else None,
                "numero": a.numero,
                "desde": a.desde,
                "confirmada": bool(vinculados & propios),
            })
        return Response({"coberturas": coberturas})
