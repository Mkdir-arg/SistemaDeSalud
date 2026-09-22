"""Cobertura en el paso asistencial: lectura, confirmación y renovación explícita."""
from uuid import UUID

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Membresia
from apps.casos.models import Caso, EventoCaso
from apps.casos.motor import usuario_puede_tomar
from apps.common import ROL_CAPACIDADES
from apps.finanzas.models import HechoAtencionCosteable, Prestacion
from apps.finanzas.permisos import tiene_concesion_financiera
from apps.registros.models import normalizar_documento
from . import models as m
from .cobertura import evaluar, seleccionar_afiliacion
from .permisos import plataforma, requerir_caso, requerir_hospital
from .services import auditar
from .vigencias import afiliados_vigentes, convenios_vigentes


def contexto_actual(caso):
    return {"nodo": caso.nodo_actual_id, "actualizado": caso.actualizado.isoformat()}


def requerir_paso(usuario, caso, contexto):
    requerir_caso(usuario, caso)
    if caso.estado in Caso.ESTADOS_FINALIZADOS:
        raise ValidationError("El caso finalizó. Las correcciones posteriores se gestionan en Finanzas.")
    if contexto != contexto_actual(caso):
        raise ValidationError("El caso cambió de paso o fue actualizado. Actualizá la pantalla antes de continuar.")
    if not usuario_puede_tomar(usuario, caso):
        raise PermissionDenied("No integrás un grupo responsable de este paso.")


def afiliacion_resumida(obj):
    if not obj:
        return None
    return {
        "id": obj.pk, "caso": obj.caso_id, "estado": obj.estado,
        "financiador_nombre": obj.afiliado.financiador.nombre if obj.afiliado_id else "",
        "plan_nombre": obj.plan.nombre if obj.plan_id else "",
        "numero": obj.afiliado.numero if obj.afiliado_id else "",
        "declaracion": obj.declaracion, "motivo": obj.motivo,
        "usuario_nombre": obj.registrado_por.nombre_completo if obj.registrado_por_id else "Sistema",
        "creado": obj.creado.isoformat(),
    }


def afiliaciones():
    return m.AfiliacionCaso.objects.filter(hecho_revision=None).select_related(
        "afiliado__financiador", "plan", "registrado_por",
    )


def reserva_resumida(obj):
    distribucion = getattr(obj, "distribucion", None)
    uso = getattr(obj, "uso_autorizacion", None)
    return {
        "id": obj.pk, "prestacion": obj.prestacion_id, "prestacion_nombre": obj.prestacion.nombre,
        "estado": obj.estado, "fecha": str(obj.fecha), "cantidad": obj.cantidad,
        "evaluacion": obj.evaluacion, "aceptacion": obj.aceptacion,
        "discrepancia": obj.discrepancia,
        "distribucion": {"estado": distribucion.estado} if distribucion else None,
        "uso_autorizacion": {"solicitud": uso.solicitud_id, "estado": uso.estado, "cantidad": uso.cantidad, "hecho": uso.hecho_id} if uso else None,
    }


def resumen_caso(caso, usuario):
    requerir_caso(usuario, caso)
    activo = m.ConfiguracionHospital.objects.filter(institucion=caso.institucion, activo=True).exists()
    selecciones = list(afiliaciones().filter(caso=caso)[:21])
    registros = m.ReservaCobertura.objects.filter(caso=caso).select_related("prestacion", "distribucion", "uso_autorizacion").order_by("-pk")
    # Una reserva pendiente antigua debe seguir visible aunque haya muchas
    # renovaciones posteriores en otros pasos del caso.
    abiertas = list(registros.filter(estado="reservada"))
    anteriores = list(registros.exclude(estado="reservada")[:51])
    documento = normalizar_documento(caso.ciudadano.documento) if caso.ciudadano_id else ""
    candidatos = afiliados_vigentes().filter(
        documento=documento,
        financiador_id__in=convenios_vigentes().filter(institucion=caso.institucion).values("financiador_id"),
    ).filter(Q(plan=None) | Q(plan__activo=True)).select_related("financiador", "plan") if documento and activo else m.Afiliado.objects.none()
    prestaciones = Prestacion.objects.filter(institucion=caso.institucion, nodo_id=caso.nodo_actual_id, activo=True) if caso.nodo_actual_id and activo else Prestacion.objects.none()
    puede = activo and caso.estado not in Caso.ESTADOS_FINALIZADOS and usuario_puede_tomar(usuario, caso)
    from .esperas import exige_aceptacion_paciente
    return {
        "activo": activo, "contexto": contexto_actual(caso), "puede_operar": puede,
        # Sin aceptación el paso no avanza: el panel debe decirlo antes, no después.
        "exige_aceptacion": exige_aceptacion_paciente(caso),
        "afiliacion": afiliacion_resumida(selecciones[0]) if selecciones else None,
        "afiliados": [{"id": a.pk, "financiador_nombre": a.financiador.nombre, "plan_nombre": a.plan.nombre if a.plan_id else "Sin plan", "numero": a.numero} for a in candidatos],
        "prestaciones": [{"id": p.pk, "codigo": p.codigo, "nombre": p.nombre,
            "puede_aceptar": tiene_concesion_financiera(usuario, "registrar_aceptacion", caso.institucion_id, caso.area_actual_id, sensible=p.politicacobro_set.filter(sensible=True).exists())} for p in prestaciones],
        "reservas": [reserva_resumida(r) for r in abiertas + anteriores[:50]],
        "historial_afiliaciones": [afiliacion_resumida(a) for a in selecciones[:20]],
        "historial_truncado": len(anteriores) > 50 or len(selecciones) > 20,
    }


@transaction.atomic
def seleccionar_en_paso(*, caso, usuario, contexto, **datos):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    requerir_paso(usuario, caso, contexto)
    return seleccionar_afiliacion(caso=caso, usuario=usuario, **datos)


def _evaluacion_paso(caso, usuario, contexto, prestacion, bloquear=False):
    requerir_paso(usuario, caso, contexto)
    if not caso.nodo_actual_id or prestacion.nodo_id != caso.nodo_actual_id:
        raise ValidationError("La prestación no corresponde al paso actual del caso.")
    reserva = m.ReservaCobertura.objects.filter(caso=caso, prestacion=prestacion, estado="reservada").first()
    if reserva and HechoAtencionCosteable.objects.filter(caso_origen_id=caso.pk, nodo_origen_id=prestacion.nodo_id, ocurrida_en__gte=reserva.creado).exists():
        raise ValidationError("La prestación ya tiene una atención registrada. Revisá su recuperación en Finanzas.")
    seleccion = afiliaciones().filter(caso=caso).first()
    if bloquear and seleccion and seleccion.afiliado_id:
        m.Afiliado.objects.select_for_update().get(pk=seleccion.afiliado_id)
        # Un consumo externo puede haber marcado la reserva mientras esperábamos.
        if reserva:
            reserva.refresh_from_db()
    actual = evaluar(caso=caso, prestacion=prestacion, fecha=timezone.localdate(),
        cantidad=reserva.cantidad if reserva else 1, afiliacion=seleccion,
        excluir=reserva.pk if reserva else None, bloquear_convenio=bloquear)
    if reserva:
        condiciones = ("afiliacion", "politica", "regla", "excepcion", "convenio", "inicio_periodo")
        if all(reserva.evaluacion.get(k) == actual.get(k) for k in condiciones):
            # Un consumo externo tardío no revoca el compromiso previo (Q01).
            from .uso_autorizaciones import actualizar_confirmada
            actual = actualizar_confirmada(reserva, timezone.localdate(), timezone.now())
    return actual, reserva


def cotizar_en_paso(*, caso, usuario, contexto, prestacion):
    actual, reserva = _evaluacion_paso(caso, usuario, contexto, prestacion)
    payload = {"contexto": contexto, "evaluacion": actual, "reserva": reserva.pk if reserva else None}
    return {**actual, "firma": signing.dumps(payload, salt="cobertura-paso", compress=True)}


@transaction.atomic
def confirmar_en_paso(*, caso, usuario, contexto, prestacion, firma, clave, acepta=False, no_realizada=False):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    requerir_caso(usuario, caso)
    clave = UUID(str(clave))
    solicitud = {"clinica": True, "caso": caso.pk, "prestacion": prestacion.pk, "contexto": contexto, "firma": firma, "acepta": acepta, "no_realizada": no_realizada}
    previa = m.ReservaCobertura.objects.filter(clave=clave).first()
    if previa:
        if previa.solicitud != solicitud:
            raise ValidationError("La clave ya se usó para otra confirmación.")
        return previa
    actual, anterior = _evaluacion_paso(caso, usuario, contexto, prestacion, bloquear=True)
    try:
        mostrada = signing.loads(firma, salt="cobertura-paso", max_age=1800)
    except signing.BadSignature as error:
        raise ValidationError("La evaluación venció. Volvé a consultar los importes.") from error
    if mostrada != {"contexto": contexto, "evaluacion": actual, "reserva": anterior.pk if anterior else None}:
        raise ValidationError("La cobertura o el importe cambió. Consultá y revisá la nueva evaluación.")
    if actual["estado"] in ("pendiente_evaluacion", "arancel_pendiente"):
        raise ValidationError("Completá los datos pendientes antes de confirmar. La atención puede continuar.")
    if anterior and not no_realizada:
        raise ValidationError("Confirmá que la prestación todavía no se realizó antes de renovar su cobertura.")
    aceptacion = {}
    if acepta:
        requerir_hospital(usuario, caso.institucion_id, "registrar_aceptacion", caso.area_actual_id, actual["sensible"])
        aceptacion = {"prestacion": prestacion.pk, "importe": actual["importe_paciente"], "usuario": usuario.pk, "fecha": timezone.now().isoformat()}
    if anterior:
        # Reemplazo atómico, con el cupo propio excluido del cálculo. Se conserva
        # toda la cotización y aceptación anterior en su registro original.
        anterior.estado = "liberada"
        anterior.motivo = "Reemplazada por una nueva confirmación antes de realizar la prestación"
        anterior.cerrado_por, anterior.cerrado_en = usuario, timezone.now()
        anterior.save(update_fields=["estado", "motivo", "cerrado_por", "cerrado_en"])
        from .uso_autorizaciones import liberar_uso
        liberar_uso(anterior)
        auditar(usuario, "renovar_reserva", anterior.pk, institucion=caso.institucion, motivo=anterior.motivo)
    seleccion = afiliaciones().filter(caso=caso).first()
    obj = m.ReservaCobertura.objects.create(
        caso=caso, afiliacion=seleccion, afiliado=seleccion.afiliado, prestacion=prestacion,
        comun_id=actual["comun"], fecha=timezone.localdate(), cantidad=actual["cantidad"],
        cubiertas=actual["cubiertas"], evaluacion=actual, aceptacion=aceptacion,
        discrepancia=bool(anterior and anterior.discrepancia), clave=clave, solicitud=solicitud, creado_por=usuario,
    )
    from .uso_autorizaciones import registrar_uso
    registrar_uso(obj)
    auditar(usuario, "confirmar_cobertura_paso", obj.pk, institucion=caso.institucion)
    EventoCaso.objects.create(caso=caso, nodo=caso.nodo_actual, autor=usuario,
        titulo="Cobertura confirmada", detalle=f"{prestacion.nombre}. {'Aceptación del importe registrada' if acepta else 'Sin aceptación del importe del paciente'}. Referencia {obj.pk}.")
    return obj


def historial_del_paciente(usuario, ciudadano):
    """Sólo selecciones del hospital y las áreas operables; sin acceso al libro."""
    qs = afiliaciones().filter(caso__ciudadano=ciudadano).select_related("caso__version__flujo")
    if plataforma(usuario):
        return qs
    roles = [r for r, caps in ROL_CAPACIDADES.items() if "casos_operar" in caps]
    miembros = Membresia.objects.filter(usuario=usuario, activo=True, institucion=ciudadano.institucion, rol__in=roles)
    if not usuario.is_active or not miembros.exists():
        raise PermissionDenied("Necesitás permiso para operar casos y consultar su cobertura.")
    filtro = Q(pk__in=[])
    for miembro in miembros.prefetch_related("areas"):
        areas = list(miembro.areas.values_list("pk", flat=True))
        filtro |= Q(caso__area_actual_id__in=areas) if areas else Q(caso__institucion=ciudadano.institucion)
    return qs.filter(filtro).order_by("-pk")
