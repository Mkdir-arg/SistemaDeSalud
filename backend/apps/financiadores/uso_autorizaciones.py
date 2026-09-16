"""Usos de una aprobación, conservando la cotización y el cupo del plan.

Las escrituras se invocan dentro de la transacción del caso/hecho y con el
afiliado bloqueado. Nunca toman un hecho después de tomar al afiliado.
"""
from django.db.models import Q, Sum
from django.utils import timezone

from . import models as m


def disponible(solicitud, excluir=None):
    usos = solicitud.usos.exclude(estado="liberado")
    if excluir:
        usos = usos.exclude(reserva_id=excluir)
    usados = usos.aggregate(total=Sum("cantidad"))["total"] or 0
    return max(0, solicitud.cantidad_aprobada - usados)


def vigente_para(solicitud, fecha, historico=False):
    estados = ("aprobada", "vencida") if historico else ("aprobada",)
    return (solicitud.estado in estados and solicitud.cantidad_aprobada > 0
            and solicitud.vigencia_desde is not None and solicitud.vigencia_hasta is not None
            and solicitud.vigencia_desde <= fecha <= solicitud.vigencia_hasta)


def agregar_evaluacion(resultado, *, caso, afiliacion, regla, fecha, corte,
                       excluir=None, historico=False, intento=None):
    from .autorizaciones import intento_actual

    requiere = bool(regla and regla.requiere_autorizacion and resultado["cubiertas"] > 0)
    resultado.update(requiere_autorizacion=requiere, autorizacion=None,
                     estado_autorizacion="no_requerida", autorizacion_revision=None,
                     autorizacion_disponible=None)
    if not requiere:
        return
    intento = str(intento or intento_actual(caso))
    resultado.update(estado_autorizacion="sin_solicitud", intento_autorizacion=intento)
    candidatas = m.SolicitudAutorizacion.objects.filter(
        convenio_id=resultado["convenio"], afiliado_id=afiliacion.afiliado_id,
        comun_id=resultado["comun"], creado__lte=corte,
    )
    aprobadas = candidatas.filter(estado__in=("aprobada", "vencida") if historico else ("aprobada",),
        cantidad_aprobada__gt=0, vigencia_desde__lte=fecha, vigencia_hasta__gte=fecha,
    ).order_by("vigencia_hasta", "pk")
    uso = m.UsoAutorizacion.objects.filter(reserva_id=excluir).first() if excluir else None
    if uso:
        aprobadas = aprobadas.order_by("pk")
        preferida = aprobadas.filter(pk=uso.solicitud_id).first()
        opciones = ([preferida] if preferida else []) + list(aprobadas.exclude(pk=uso.solicitud_id))
    else:
        opciones = aprobadas
    for solicitud in opciones:
        cantidad = disponible(solicitud, excluir=excluir)
        if cantidad >= resultado["cubiertas"]:
            resultado.update(autorizacion=solicitud.pk, estado_autorizacion="aprobada",
                             autorizacion_revision=solicitud.revision, autorizacion_disponible=cantidad)
            return
    propia = candidatas.filter(caso=caso, intento=intento).order_by("-pk").first()
    if propia:
        estado = propia.estado
        if estado == "aprobada":
            estado = "sin_cantidad" if vigente_para(propia, fecha, historico) else "fuera_vigencia"
        resultado.update(autorizacion=propia.pk, estado_autorizacion=estado,
                         autorizacion_revision=propia.revision,
                         autorizacion_disponible=disponible(propia, excluir=excluir))


def actualizar_confirmada(reserva, fecha, corte, *, historico=False):
    """Revalida autorización sin revocar por consumos tardíos el cupo comprometido."""
    resultado = {**reserva.evaluacion, "fecha": str(fecha)}
    regla = m.ReglaCobertura.objects.filter(pk=resultado.get("regla")).first()
    agregar_evaluacion(resultado, caso=reserva.caso, afiliacion=reserva.afiliacion,
                       regla=regla, fecha=fecha, corte=corte, excluir=reserva.pk,
                       historico=historico, intento=resultado.get("intento_autorizacion"))
    return resultado


def registrar_uso(reserva, *, consumir=False, solicitud=None):
    """Compromete/consume una sola vez. Pendiente o vencida no se presume aprobada."""
    dato = reserva.evaluacion
    uso = m.UsoAutorizacion.objects.filter(reserva=reserva).first()
    if not dato.get("requiere_autorizacion"):
        if consumir and uso and uso.estado == "comprometido":
            # La realización quedó bajo otras condiciones. No retener cantidad
            # de la aprobación anterior; conservar su vínculo al hecho revisado.
            uso.estado, uso.hecho_id = "liberado", reserva.hecho_id
            uso.save(update_fields=["estado", "hecho", "actualizado"])
            reserva.discrepancia = True
            reserva.save(update_fields=["discrepancia"])
        return None
    if uso and uso.estado == "consumido":
        return uso
    solicitud_id = getattr(solicitud, "pk", None) or (uso.solicitud_id if uso else dato.get("autorizacion"))
    if not solicitud_id:
        return None
    if uso and uso.solicitud_id != solicitud_id:
        # Una solicitud posterior no reescribe el compromiso anterior. Renovar
        # la reserva no realizada o resolver el hecho conserva ambos antecedentes.
        return None
    solicitud = m.SolicitudAutorizacion.objects.select_for_update().get(pk=solicitud_id)
    coincide = (solicitud.convenio_id == dato.get("convenio")
                and solicitud.institucion_id == reserva.caso.institucion_id
                and solicitud.afiliado_id == reserva.afiliado_id and solicitud.comun_id == reserva.comun_id)
    valida = coincide and vigente_para(solicitud, reserva.fecha, historico=consumir)
    if not valida or disponible(solicitud, excluir=reserva.pk) < reserva.cubiertas:
        if uso and consumir and uso.estado == "comprometido":
            uso.estado, uso.hecho_id = "liberado", reserva.hecho_id
            uso.save(update_fields=["estado", "hecho", "actualizado"])
            reserva.discrepancia = True
            reserva.save(update_fields=["discrepancia"])
        return None
    if reserva.cubiertas <= 0:
        return None
    if uso is None:
        uso = m.UsoAutorizacion(solicitud=solicitud, reserva=reserva)
    uso.cantidad = reserva.cubiertas
    uso.estado = "consumido" if consumir else "comprometido"
    uso.hecho_id = reserva.hecho_id if consumir else None
    uso.save()
    return uso


def liberar_uso(reserva):
    """El llamador ya confirmó no realización bajo los candados del caso/afiliado."""
    m.UsoAutorizacion.objects.filter(reserva=reserva, estado="comprometido").update(
        estado="liberado", actualizado=timezone.now(),
    )


def autorizacion_cumplida(reserva):
    if not reserva.evaluacion.get("requiere_autorizacion"):
        return True
    return m.UsoAutorizacion.objects.filter(reserva=reserva, estado="consumido", hecho_id=reserva.hecho_id).exists()


def aplicar_resolucion(solicitud, usuario=None):
    """Bajo bloquear_solicitud: revisa hechos ya bloqueados, sin crear atención."""
    if solicitud.estado != "aprobada":
        return
    from .cobros import distribuir

    reservas = m.ReservaCobertura.objects.filter(
        afiliado_id=solicitud.afiliado_id, comun_id=solicitud.comun_id,
    ).filter(
        Q(uso_autorizacion__solicitud=solicitud)
        | Q(evaluacion__autorizacion=solicitud.pk)
        | Q(caso=solicitud.caso, prestacion=solicitud.prestacion,
            evaluacion__intento_autorizacion=str(solicitud.intento)),
    ).exclude(estado="liberada").order_by("pk")
    for reserva in reservas:
        realizada = reserva.estado == "realizada" and reserva.hecho_id is not None
        uso = registrar_uso(reserva, consumir=realizada, solicitud=solicitud)
        distribucion = getattr(reserva, "distribucion", None)
        if realizada and uso and (not distribucion or distribucion.estado == "autorizacion_pendiente"):
            distribuir(reserva, completar=True)
