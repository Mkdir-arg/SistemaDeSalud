"""Espera administrativa del paso: aprobar nunca registra una atención."""
import logging
from decimal import Decimal, InvalidOperation
from uuid import NAMESPACE_URL, uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Membresia
from apps.casos.models import Caso, EventoCaso, Notificacion
from apps.finanzas.models import HechoAtencionCosteable, Prestacion
from apps.flujos.models import Nodo, VersionFlujo
from . import models as m
from .permisos import requerir_caso


logger = logging.getLogger(__name__)
SALIDAS_EXPRESAS = {"supervisada", "urgencia"}


def _intento(caso):
    from .autorizaciones import intento_actual
    return str(intento_actual(caso))


def _config_paso(caso):
    """La config del nodo sólo cuenta en una atención de circuito programado."""
    config = caso.nodo_actual.config if caso.nodo_actual_id else {}
    if not (caso.nodo_actual_id and caso.nodo_actual.tipo == Nodo.Tipo.ATENCION
            and caso.version.tipo_circuito == VersionFlujo.TipoCircuito.PROGRAMADO
            and isinstance(config, dict)):
        return {}
    return config


def _programado(caso):
    return _config_paso(caso).get("esperar_autorizacion") is True


def exige_aceptacion_paciente(caso):
    """El paso exige que la responsabilidad del paciente esté asumida, no cobrada."""
    return _config_paso(caso).get("exigir_aceptacion_paciente") is True


def _con_espera(caso):
    # Un solo paso, una sola espera: dos guardas paralelas sobre la misma
    # transición serían dos estados bloqueantes y dos salidas que auditar.
    return _programado(caso) or exige_aceptacion_paciente(caso)


def _actual(caso):
    valor = caso.espera_autorizacion or {}
    return valor if valor.get("intento") == _intento(caso) else {}


def _guardar(caso, estado, solicitudes, usuario, motivo):
    caso.espera_autorizacion = {
        "intento": _intento(caso), "solicitudes": sorted(set(solicitudes)), "estado": estado,
        "motivo": motivo, "usuario": getattr(usuario, "pk", None), "fecha": timezone.now().isoformat(),
    }
    caso.save(update_fields=["espera_autorizacion", "actualizado"])
    EventoCaso.objects.create(caso=caso, nodo=caso.nodo_actual, autor=usuario,
                             titulo=f"Espera de autorización: {estado}", detalle=motivo)
    return caso.espera_autorizacion


def _aceptacion_pendiente(reserva, resultado):
    """Sin aceptación vigente del importe exacto no hay responsabilidad asumida.

    Se compara contra el importe evaluado ahora, con el mismo criterio que usa
    la distribución al capturar: una aceptación de otro precio no vale, porque
    la persona asumió otra cosa.
    """
    if not resultado.get("cobrar"):
        return False
    importe = resultado.get("importe_paciente")
    try:
        if importe is None or Decimal(importe) <= 0:
            return False
    except InvalidOperation:
        return True
    return not (reserva and reserva.aceptacion.get("importe") == importe)


def _requisitos_pendientes(caso):
    """Devuelve `(prestacion_id, motivo)` con motivo en datos/autorizacion/aceptacion."""
    from .cobertura import evaluar
    from .uso_autorizaciones import actualizar_confirmada
    reservas = {r.prestacion_id: r for r in m.ReservaCobertura.objects.filter(
        caso=caso, prestacion__nodo_id=caso.nodo_actual_id, estado="reservada",
    )}
    activo = m.ConfiguracionHospital.objects.filter(institucion_id=caso.institucion_id, activo=True).exists()
    if not activo and not reservas:
        return []
    espera_autorizacion, exige_aceptacion = _programado(caso), exige_aceptacion_paciente(caso)
    pendientes = []
    for prestacion in Prestacion.objects.filter(institucion_id=caso.institucion_id, nodo_id=caso.nodo_actual_id).filter(Q(activo=True) | Q(pk__in=reservas)):
        reserva = reservas.get(prestacion.pk)
        if not activo and not reserva:
            continue
        try:
            if not activo:
                resultado = actualizar_confirmada(reserva, timezone.localdate(), timezone.now())
            else:
                resultado = evaluar(caso=caso, prestacion=prestacion, fecha=timezone.localdate(),
                                    cantidad=reserva.cantidad if reserva else 1, excluir=reserva.pk if reserva else None)
                condiciones = ("afiliacion", "politica", "regla", "excepcion", "convenio", "inicio_periodo")
                if reserva and all(reserva.evaluacion.get(k) == resultado.get(k) for k in condiciones):
                    resultado = actualizar_confirmada(reserva, timezone.localdate(), timezone.now())
        except ValidationError:
            # Sólo se aplica al nodo programado que pidió esperar expresamente:
            # un dato incompleto exige revisión/supervisión, no equivale a aprobado.
            # Guardia/no definido/urgencia pasan por sus guardas antes de llegar aquí.
            # Sin evaluación tampoco se sabe si hay importe del paciente.
            pendientes.append((prestacion.pk, "datos"))
            continue
        if (espera_autorizacion and resultado.get("requiere_autorizacion")
                and resultado.get("cubiertas", 0) > 0 and resultado.get("estado_autorizacion") != "aprobada"):
            pendientes.append((prestacion.pk, "autorizacion"))
        if exige_aceptacion and _aceptacion_pendiente(reserva, resultado):
            pendientes.append((prestacion.pk, "aceptacion"))
    return pendientes


def _mensaje_bloqueo(requisitos):
    if requisitos and {motivo for _, motivo in requisitos} == {"aceptacion"}:
        return ("Falta registrar que el paciente aceptó el importe a su cargo. Registrá la aceptación "
                "en el paso o solicitá una continuación supervisada con motivo.")
    return ("El paso programado requiere revisar la autorización o sus datos de cobertura. "
            "Revisá las solicitudes o solicitá una continuación supervisada con motivo.")


def validar_avance(caso):
    """Guardia/no definido no esperan, incluso ante configuración inválida heredada."""
    if not _con_espera(caso):
        return
    espera = _actual(caso)
    if espera.get("estado") in SALIDAS_EXPRESAS:
        return
    if espera.get("estado") == "esperando" and caso.prioridad == Caso.Prioridad.URGENTE:
        raise ValidationError("La prioridad es urgente. Registrá la salida expresa de la espera con motivo antes de continuar.")
    if caso.prioridad == Caso.Prioridad.URGENTE:
        return
    requisitos = _requisitos_pendientes(caso)
    if espera.get("estado") == "esperando" and not requisitos and _referencias_aprobadas(caso, espera):
        _guardar(caso, "liberada", espera["solicitudes"], None, "La aprobación ya está vigente; la atención aún debe registrarse.")
        return
    if espera.get("estado") == "esperando" or requisitos:
        raise ValidationError(_mensaje_bloqueo(requisitos))


def _referencias_aprobadas(caso, espera):
    ids = espera.get("solicitudes", [])
    hoy = timezone.localdate()
    return bool(ids) and m.SolicitudAutorizacion.objects.filter(
        pk__in=ids, caso=caso, intento=_intento(caso), estado="aprobada",
        vigencia_desde__lte=hoy, vigencia_hasta__gte=hoy,
    ).count() == len(ids)


def registrar_espera(solicitud, usuario):
    """El llamador mantiene bloqueado el Caso durante la transacción de solicitud."""
    caso = solicitud.caso
    if caso.estado in Caso.ESTADOS_FINALIZADOS or str(solicitud.intento) != _intento(caso) or not _programado(caso):
        return
    anterior = _actual(caso)
    if anterior.get("estado") in SALIDAS_EXPRESAS or (caso.prioridad == Caso.Prioridad.URGENTE and not anterior):
        return
    ids = list(m.SolicitudAutorizacion.objects.filter(
        pk__in=anterior.get("solicitudes", []), caso=caso, intento=solicitud.intento,
    ).exclude(prestacion_id=solicitud.prestacion_id).values_list("pk", flat=True)) + [solicitud.pk]
    if anterior.get("estado") == "esperando" and anterior.get("solicitudes") == sorted(ids):
        return
    _guardar(caso, "esperando", ids, usuario, "Pendiente de decisión administrativa del financiador.")


def _notificar_resolucion(solicitud_id, caso_id, estado):
    """Aviso mínimo; su fallo posterior al commit no revierte una decisión."""
    try:
        caso = Caso.objects.select_related("nodo_actual").get(pk=caso_id)
        ids = set()
        if caso.nodo_actual_id:
            for grupo in caso.nodo_actual.grupos.filter(activo=True, area__activa=True, area__institucion_id=caso.institucion_id):
                ids.update(grupo.miembros.filter(is_active=True, membresias__activo=True,
                    membresias__institucion_id=caso.institucion_id, membresias__areas=grupo.area_id).values_list("pk", flat=True))
        if caso.asignado_a_id and Membresia.objects.filter(
            usuario_id=caso.asignado_a_id, usuario__is_active=True, activo=True, institucion_id=caso.institucion_id,
        ).filter(Q(areas=caso.area_actual_id) | Q(areas__isnull=True)).exists():
            ids.add(caso.asignado_a_id)
        Notificacion.objects.bulk_create([
            Notificacion(usuario_id=pk, caso=caso, titulo=f"Autorización {estado}",
                         detalle=f"Solicitud #{solicitud_id}. Revisá el paso pendiente; la prestación no se registra automáticamente.")
            for pk in sorted(ids)
        ])
    except Exception:
        logger.warning("No se pudo entregar el aviso de autorización %s.", solicitud_id)


def resolver_espera(solicitud, usuario):
    transaction.on_commit(lambda: _notificar_resolucion(solicitud.pk, solicitud.caso_id, solicitud.estado))
    caso = solicitud.caso
    espera = _actual(caso)
    if (caso.estado in Caso.ESTADOS_FINALIZADOS or str(solicitud.intento) != _intento(caso)
            or solicitud.pk not in espera.get("solicitudes", []) or espera.get("estado") in SALIDAS_EXPRESAS):
        return
    ids = espera["solicitudes"]
    estado = "liberada" if _referencias_aprobadas(caso, espera) and not _requisitos_pendientes(caso) else "esperando"
    if estado != espera.get("estado"):
        _guardar(caso, estado, ids, usuario, "Se revisaron las decisiones del intento actual; la atención sigue pendiente de registro.")


def puede_continuar_autorizacion(usuario, caso):
    from apps.casos.motor import usuario_puede_tomar, usuario_supervisa
    if not usuario or not usuario.is_authenticated or not usuario.is_active or caso.estado in Caso.ESTADOS_FINALIZADOS or not _con_espera(caso):
        return False
    try:
        requerir_caso(usuario, caso)
    except PermissionDenied:
        return False
    return bool(usuario_supervisa(usuario, caso) or (caso.prioridad == Caso.Prioridad.URGENTE and usuario_puede_tomar(usuario, caso)))


@transaction.atomic
def continuar(*, caso, usuario, intento, motivo):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    if not puede_continuar_autorizacion(usuario, caso):
        raise PermissionDenied("La continuación requiere supervisión del área o personal autorizado ante una urgencia.")
    if str(intento) != _intento(caso):
        raise ValidationError("El intento cambió. Actualizá el caso antes de continuar.")
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo.strip()) > 255:
        raise ValidationError("Registrá un motivo de hasta 255 caracteres.")
    espera = _actual(caso)
    if espera.get("estado") in SALIDAS_EXPRESAS:
        return espera
    if espera.get("estado") != "esperando" and not _requisitos_pendientes(caso):
        raise ValidationError("El paso no tiene un requisito administrativo pendiente que requiera esta continuación.")
    return _guardar(caso, "urgencia" if caso.prioridad == Caso.Prioridad.URGENTE else "supervisada",
                    espera.get("solicitudes", []), usuario, motivo.strip())


def cancelar_pendientes(*, caso, usuario, motivo, reservas_no_realizadas=None):
    from .autorizaciones import anular
    from .cobertura import liberar
    solicitudes = list(m.SolicitudAutorizacion.objects.filter(caso=caso, estado__in=m.SolicitudAutorizacion.ABIERTAS).order_by("afiliado_id", "convenio_id", "pk"))
    ids = reservas_no_realizadas or []
    if not isinstance(ids, list) or any(type(pk) is not int or pk <= 0 for pk in ids):
        raise ValidationError("Indicá una lista de reservas confirmadas como no realizadas.")
    reservas = list(m.ReservaCobertura.objects.filter(caso=caso, pk__in=ids).order_by("afiliado_id", "pk"))
    if len(reservas) != len(set(ids)):
        raise ValidationError("Alguna reserva no pertenece al caso.")
    if not solicitudes and not reservas:
        return
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo.strip()) > 255:
        raise ValidationError("Cancelar solicitudes o liberar reservas requiere un motivo de hasta 255 caracteres.")
    # El Caso ya está bloqueado por el motor. Anticipar el conjunto completo
    # evita tomar un Hecho nuevo después del primer Afiliado de otra solicitud.
    list(HechoAtencionCosteable.objects.select_for_update().filter(caso_origen_id=caso.pk).order_by("pk"))
    afiliados = {s.afiliado_id for s in solicitudes} | {r.afiliado_id for r in reservas if r.afiliado_id}
    list(m.Afiliado.objects.select_for_update().filter(pk__in=afiliados).order_by("pk"))
    list(m.Convenio.objects.select_for_update().filter(pk__in={s.convenio_id for s in solicitudes}).order_by("pk"))
    for solicitud in solicitudes:
        anular(solicitud=solicitud, usuario=usuario, revision=solicitud.revision, motivo=motivo,
               clave=uuid5(NAMESPACE_URL, f"salud:cancelar-caso:{caso.pk}:solicitud:{solicitud.pk}:{solicitud.revision}"))
    for reserva in reservas:
        liberar(reserva=reserva, usuario=usuario, motivo=motivo, no_realizada=True)


def vencer_autorizaciones(*, ahora=None, limite=500, seco=False):
    from .autorizaciones import _evento, bloquear_solicitud, efectos_resolucion
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    if type(limite) is not int or not 1 <= limite <= 10000:
        raise ValidationError("El límite debe estar entre 1 y 10.000.")
    pendientes = m.SolicitudAutorizacion.objects.filter(estado__in=m.SolicitudAutorizacion.ABIERTAS, plazo_respuesta__lte=ahora)
    aprobadas = m.SolicitudAutorizacion.objects.filter(estado="aprobada", vigencia_hasta__lt=hoy)
    ids = list(pendientes.order_by("plazo_respuesta", "pk").values_list("pk", "caso_id")[:limite])
    ids += list(aprobadas.order_by("vigencia_hasta", "pk").values_list("pk", "caso_id")[:max(0, limite-len(ids))])
    if seco:
        return len(ids)
    cantidad = 0
    for pk, caso_id in ids:
        with transaction.atomic():
            # No retener una solicitud mientras se espera al Caso: mantiene el
            # orden canónico y permite clock simultáneo con aprobación/captura.
            caso = Caso.objects.select_for_update(skip_locked=True).filter(pk=caso_id).first()
            if not caso:
                continue
            original = m.SolicitudAutorizacion.objects.filter(pk=pk).first()
            if not original:
                continue
            obj = bloquear_solicitud(original)
            vencio = (obj.estado in obj.ABIERTAS and obj.plazo_respuesta and obj.plazo_respuesta <= ahora) or (
                obj.estado == "aprobada" and obj.vigencia_hasta and obj.vigencia_hasta < hoy)
            if not vencio:
                continue
            anterior = obj.estado
            obj.estado, obj.revision, obj.resuelto_en = "vencida", obj.revision + 1, ahora
            obj.motivo_resolucion = "Venció el plazo administrativo; requiere revisión hospitalaria."
            obj.save(update_fields=["estado", "revision", "resuelto_en", "motivo_resolucion", "actualizado"])
            _evento(obj, None, uuid5(NAMESPACE_URL, f"salud:vencer-autorizacion:{pk}:{obj.revision}"),
                    "vencer", anterior, obj.motivo_resolucion, {"origen": "correr_tiempos"})
            efectos_resolucion(obj, None)
            cantidad += 1
    return cantidad
