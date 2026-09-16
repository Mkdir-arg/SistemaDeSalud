"""Decisiones administrativas durables, separadas de la realización clínica."""
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import Membresia
from apps.casos.models import Caso, EventoCaso
from apps.common import ROL_CAPACIDADES
from apps.finanzas.models import HechoAtencionCosteable
from apps.registros.models import normalizar_documento
from . import models as m
from .cobertura import regla_aplicable
from .permisos import plataforma, requerir_caso, requerir_resolver_autorizaciones
from .services import auditar
from .vigencias import convenio_aplicable, convenios_vigentes


def intento_actual(caso):
    inicio = caso.paso_desde or caso.creado
    return uuid5(NAMESPACE_URL, f"cauce:autorizacion:{caso.pk}:{caso.nodo_actual_id}:{inicio.isoformat()}")


def casos_permitidos(usuario):
    qs = Caso.objects.all()
    if not usuario.is_authenticated or not usuario.is_active:
        return qs.none()
    if plataforma(usuario):
        return qs
    alcance = Q(pk__in=[])
    roles = [rol for rol, caps in ROL_CAPACIDADES.items() if "casos_operar" in caps]
    for miembro in Membresia.objects.filter(usuario=usuario, activo=True, rol__in=roles).prefetch_related("areas"):
        filtro = Q(institucion_id=miembro.institucion_id)
        areas = list(miembro.areas.values_list("pk", flat=True))
        if areas:
            filtro &= Q(area_actual_id__in=areas)
        alcance |= filtro
    return qs.filter(alcance)


def solicitudes_visibles_financiador(financiador_id):
    # Tras un cierre sólo se expone el expediente administrativo aún pendiente.
    from .acceso import actividad_visible

    vigente = Q(convenio_id__in=convenios_vigentes().values("pk"),
                afiliado__finalizado_en__isnull=True, afiliado__desde__lte=timezone.localdate())
    usos_pendientes = m.UsoAutorizacion.objects.filter(
        reserva_id__in=actividad_visible(financiador_id).values("pk"),
    ).values("solicitud_id")
    return m.SolicitudAutorizacion.objects.filter(financiador_id=financiador_id).filter(
        vigente | Q(estado__in=m.SolicitudAutorizacion.ABIERTAS) | Q(pk__in=usos_pendientes),
    )


def cantidades_autorizacion(solicitud):
    estados = {fila["estado"]: fila["total"] for fila in solicitud.usos.values("estado").annotate(total=Sum("cantidad"))}
    comprometida, consumida = estados.get("comprometido", 0), estados.get("consumido", 0)
    return {"comprometida": comprometida, "consumida": consumida,
            "disponible": max(0, solicitud.cantidad_aprobada - comprometida - consumida)}


def _texto(valor, limite, etiqueta):
    if not isinstance(valor, str) or not valor.strip() or len(valor.strip()) > limite:
        raise ValidationError(f"Indicá {etiqueta} de hasta {limite} caracteres.")
    return valor.strip()


def _clave(valor):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("La clave de reintento no es válida.") from error


def _reintento(clave, usuario, accion, peticion, solicitud=None):
    previo = m.EventoAutorizacion.objects.filter(clave=clave).select_related("solicitud").first()
    if previo:
        if previo.usuario_id != usuario.pk or previo.accion != accion or previo.peticion != peticion or (solicitud and previo.solicitud_id != solicitud.pk):
            raise ValidationError("La clave ya fue utilizada para otra operación de autorización.")
        return previo.solicitud
    return None


def _evento(solicitud, usuario, clave, accion, anterior, motivo, peticion):
    m.EventoAutorizacion.objects.create(
        solicitud=solicitud, usuario=usuario, clave=clave, accion=accion,
        anterior=anterior, estado=solicitud.estado, revision=solicitud.revision,
        motivo=motivo, peticion=peticion,
    )
    auditar(usuario, f"autorizacion_{accion}", solicitud.pk, financiador=solicitud.financiador,
            institucion=solicitud.institucion, motivo=motivo[:255])
    # La traza clínica sólo informa estado, sin transmitir justificación ni importes.
    EventoCaso.objects.create(caso=solicitud.caso, nodo=solicitud.nodo, autor=usuario,
        titulo=f"Autorización {solicitud.get_estado_display().lower()}", detalle=f"Solicitud #{solicitud.pk}")


@transaction.atomic
def solicitar(*, caso, prestacion, usuario, intento, cantidad, justificacion, clave):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    requerir_caso(usuario, caso)
    clave = _clave(clave)
    justificacion = _texto(justificacion, 1000, "una justificación destinada al financiador")
    peticion = {"caso": caso.pk, "prestacion": prestacion.pk, "intento": str(intento),
                "cantidad": cantidad, "justificacion": justificacion}
    anterior = _reintento(clave, usuario, "solicitar", peticion)
    if anterior:
        return anterior
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not 1 <= cantidad <= 100000:
        raise ValidationError("La cantidad debe estar entre 1 y 100.000.")
    if caso.estado in Caso.ESTADOS_FINALIZADOS or str(intento_actual(caso)) != str(intento):
        raise ValidationError("El paso cambió o el caso finalizó. Actualizá la pantalla.")
    if not caso.nodo_actual_id or prestacion.nodo_id != caso.nodo_actual_id or prestacion.institucion_id != caso.institucion_id or not prestacion.activo:
        raise ValidationError("La prestación no corresponde al paso actual de este hospital.")
    if not m.ConfiguracionHospital.objects.filter(institucion_id=caso.institucion_id, activo=True).exists():
        raise ValidationError("El hospital todavía no habilitó el circuito de cobertura.")
    afiliacion = m.AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).first()
    if not afiliacion or afiliacion.estado != "verificada" or not afiliacion.afiliado_id:
        raise ValidationError("Verificá la afiliación del caso antes de solicitar autorización.")
    afiliado = m.Afiliado.objects.select_for_update().get(pk=afiliacion.afiliado_id)
    if not caso.ciudadano_id or not normalizar_documento(caso.ciudadano.documento) or normalizar_documento(caso.ciudadano.documento) != normalizar_documento(afiliado.documento):
        raise ValidationError("El paciente del caso cambió o su documento no coincide. Revisá la afiliación antes de solicitar.")
    if afiliado.finalizado_en or afiliado.desde > timezone.localdate() or not afiliado.financiador.activo:
        raise ValidationError("La afiliación no está vigente para una nueva solicitud.")
    convenio = convenio_aplicable(afiliado.financiador_id, caso.institucion_id, timezone.now(), bloquear=True)
    vinculo = m.VinculoPrestacion.objects.filter(prestacion=prestacion, comun__activo=True).select_related("comun").first()
    if not convenio or not vinculo:
        raise ValidationError("La solicitud requiere convenio vigente y prestación vinculada al catálogo común.")
    regla = regla_aplicable(afiliacion, vinculo.comun, timezone.localdate(), timezone.now())
    if not regla or not regla.requiere_autorizacion:
        raise ValidationError("La regla vigente no requiere autorización previa para esta prestación.")
    if m.SolicitudAutorizacion.objects.filter(caso=caso, intento=intento, prestacion=prestacion, estado__in=["pendiente", "observada", "aprobada"]).exists():
        raise ValidationError("Ya existe una solicitud activa para esta prestación e intento.")
    # Un reintento conserva su antecedente sin enlazar expedientes de otro pagador.
    antecedente = m.SolicitudAutorizacion.objects.filter(
        caso=caso, intento=intento, prestacion=prestacion, convenio=convenio,
        financiador_id=afiliado.financiador_id, afiliado=afiliado, comun=vinculo.comun,
        estado__in=["rechazada", "vencida", "anulada"],
    ).order_by("-creado", "-pk").first()
    obj = m.SolicitudAutorizacion.objects.create(
        institucion_id=caso.institucion_id, financiador_id=afiliado.financiador_id,
        convenio=convenio, afiliado=afiliado, afiliacion=afiliacion, comun=vinculo.comun,
        prestacion=prestacion, caso=caso, ciudadano_id=caso.ciudadano_id, nodo_id=caso.nodo_actual_id,
        intento=intento, anterior=antecedente, cantidad_solicitada=cantidad, justificacion=justificacion,
        urgente=caso.prioridad == Caso.Prioridad.URGENTE, creado_por=usuario,
        plazo_respuesta=timezone.now() + timedelta(hours=convenio.plazo_autorizacion_horas) if convenio.plazo_autorizacion_horas else None,
    )
    _evento(obj, usuario, clave, "solicitar", "", justificacion, peticion)
    efectos_solicitud(obj, usuario)
    return obj


def bloquear_solicitud(solicitud):
    """Orden compartido con captura: Caso → Hechos → Afiliado → Convenio → solicitud.

    El llamador ya está en transaction.atomic. Nunca se intenta tomar un Hecho
    después del Afiliado: la captura clínica mantiene el orden inverso a eso.
    """
    caso = Caso.objects.select_for_update().get(pk=solicitud.caso_id)
    hechos = HechoAtencionCosteable.objects.filter(
        Q(caso_origen_id=caso.pk, nodo_origen_id=solicitud.nodo_id)
        | Q(usoautorizacion__solicitud_id=solicitud.pk),
    ).order_by("pk")
    # Evita DISTINCT + FOR UPDATE y los bloqueos de joins anulables.
    ids = hechos.values_list("pk", flat=True).distinct()
    list(HechoAtencionCosteable.objects.filter(pk__in=ids).order_by("pk").select_for_update())
    m.Afiliado.objects.select_for_update().get(pk=solicitud.afiliado_id)
    m.Convenio.objects.select_for_update().get(pk=solicitud.convenio_id)
    obj = m.SolicitudAutorizacion.objects.select_for_update().get(pk=solicitud.pk)
    obj.caso = caso
    return obj


def efectos_resolucion(solicitud, usuario):
    """Punto de integración B5/B6; una decisión por sí sola no realiza atención."""
    from .uso_autorizaciones import aplicar_resolucion
    aplicar_resolucion(solicitud, usuario)
    from .esperas import resolver_espera
    resolver_espera(solicitud, usuario)


def efectos_solicitud(solicitud, usuario):
    """Punto de integración B6 para registrar una espera explícita del paso."""
    from .esperas import registrar_espera
    registrar_espera(solicitud, usuario)


@transaction.atomic
def resolver(*, solicitud, usuario, revision, decision, motivo, clave, evidencia="", numero_externo="", cantidad_aprobada=None, vigencia_desde=None, vigencia_hasta=None):
    requerir_resolver_autorizaciones(usuario, solicitud.financiador_id)
    obj = bloquear_solicitud(solicitud)
    requerir_resolver_autorizaciones(usuario, obj.financiador_id)
    clave, motivo = _clave(clave), _texto(motivo, 255, "un motivo")
    if decision not in ["observar", "aprobar", "rechazar"]:
        raise ValidationError("Elegí observar, aprobar o rechazar.")
    if len(evidencia) > 1000 or len(numero_externo) > 120:
        raise ValidationError("La evidencia o el número externo exceden el límite permitido.")
    peticion = {"revision": revision, "decision": decision, "motivo": motivo, "evidencia": evidencia.strip(),
        "numero_externo": numero_externo.strip(), "cantidad_aprobada": cantidad_aprobada,
        "vigencia_desde": str(vigencia_desde) if vigencia_desde else None,
        "vigencia_hasta": str(vigencia_hasta) if vigencia_hasta else None}
    previo = _reintento(clave, usuario, decision, peticion, obj)
    if previo:
        return previo
    if obj.revision != revision:
        raise ValidationError("La solicitud cambió. Actualizá la pantalla antes de resolver.")
    if obj.estado not in obj.ABIERTAS:
        raise ValidationError("La solicitud ya tiene una resolución terminal. Su historia se conserva.")
    if obj.plazo_respuesta and obj.plazo_respuesta <= timezone.now():
        raise ValidationError("El plazo de respuesta venció. La solicitud requiere revisión hospitalaria y no se aprueba automáticamente.")
    if decision == "aprobar":
        if not isinstance(cantidad_aprobada, int) or isinstance(cantidad_aprobada, bool) or not 1 <= cantidad_aprobada <= obj.cantidad_solicitada:
            raise ValidationError("La cantidad aprobada debe ser positiva y no superar la solicitada.")
        if not vigencia_desde or not vigencia_hasta or vigencia_hasta < vigencia_desde:
            raise ValidationError("Indicá una vigencia completa con fecha final no anterior al inicio.")
        evidencia = _texto(evidencia, 1000, "la evidencia de aprobación")
        obj.cantidad_aprobada = cantidad_aprobada
        obj.vigencia_desde, obj.vigencia_hasta = vigencia_desde, vigencia_hasta
    elif cantidad_aprobada is not None or vigencia_desde is not None or vigencia_hasta is not None:
        raise ValidationError("La cantidad y vigencia corresponden únicamente a una aprobación.")
    anterior = obj.estado
    obj.estado = {"observar": "observada", "aprobar": "aprobada", "rechazar": "rechazada"}[decision]
    obj.revision += 1
    obj.motivo_resolucion, obj.evidencia, obj.numero_externo = motivo, evidencia.strip(), numero_externo.strip()
    obj.resuelto_por, obj.resuelto_en = usuario, timezone.now()
    obj.save()
    _evento(obj, usuario, clave, decision, anterior, motivo, peticion)
    efectos_resolucion(obj, usuario)
    return obj


@transaction.atomic
def reenviar(*, solicitud, usuario, revision, justificacion, clave):
    obj = bloquear_solicitud(solicitud)
    requerir_caso(usuario, obj.caso)
    clave, justificacion = _clave(clave), _texto(justificacion, 1000, "una justificación destinada al financiador")
    peticion = {"revision": revision, "justificacion": justificacion}
    previo = _reintento(clave, usuario, "reenviar", peticion, obj)
    if previo:
        return previo
    if obj.revision != revision or obj.estado != "observada":
        raise ValidationError("Sólo se reenvía la versión actual de una solicitud observada.")
    if obj.caso.estado in Caso.ESTADOS_FINALIZADOS or obj.intento != intento_actual(obj.caso):
        raise ValidationError("El intento ya no es actual. La solicitud conserva su historia.")
    if not convenios_vigentes().filter(pk=obj.convenio_id).exists() or obj.afiliado.finalizado_en:
        raise ValidationError("La afiliación o el convenio cerraron. No se abre una nueva evaluación.")
    if obj.plazo_respuesta and obj.plazo_respuesta <= timezone.now():
        raise ValidationError("El plazo venció; reenviar no reinicia el plazo acordado.")
    obj.estado, obj.justificacion = "pendiente", justificacion
    obj.revision += 1
    obj.save(update_fields=["estado", "justificacion", "revision", "actualizado"])
    _evento(obj, usuario, clave, "reenviar", "observada", justificacion, peticion)
    efectos_solicitud(obj, usuario)
    return obj


@transaction.atomic
def anular(*, solicitud, usuario, revision, motivo, clave):
    obj = bloquear_solicitud(solicitud)
    requerir_caso(usuario, obj.caso)
    clave, motivo = _clave(clave), _texto(motivo, 255, "un motivo de anulación")
    peticion = {"revision": revision, "motivo": motivo}
    previo = _reintento(clave, usuario, "anular", peticion, obj)
    if previo:
        return previo
    if obj.revision != revision or obj.estado not in obj.ABIERTAS:
        raise ValidationError("Sólo se anula la versión actual de una solicitud pendiente u observada.")
    anterior = obj.estado
    obj.estado, obj.motivo_resolucion = "anulada", motivo
    obj.revision += 1
    obj.resuelto_por, obj.resuelto_en = usuario, timezone.now()
    obj.save(update_fields=["estado", "motivo_resolucion", "revision", "resuelto_por", "resuelto_en", "actualizado"])
    _evento(obj, usuario, clave, "anular", anterior, motivo, peticion)
    efectos_resolucion(obj, usuario)
    return obj
