"""Persistencia de borradores: no conecta con decisiones prestacionales."""
from django.core.exceptions import ValidationError
from django.db import transaction

from .derechos_borrador import BorradorDerechos
from .propuesta_derechos import comparar_borradores
from .models import BorradorReglaDerechos, Financiador, Plan
from .permisos import requerir_financiador
from .services import auditar


CAMPOS = ("codigo", "version", "fuente", "financiador_id", "regimen", "plan_id", "desde", "hasta", "plazo_dias_corridos")


def _filas(financiador_id):
    return BorradorReglaDerechos.objects.filter(financiador_id=financiador_id).order_by(
        "regimen", "plan_id", "codigo", "version")


def _descriptor(fila):
    return BorradorDerechos(**{c: getattr(fila, c) for c in CAMPOS})


def _descriptores(financiador_id):
    return tuple(_descriptor(fila) for fila in _filas(financiador_id))


def _validar_id(financiador_id):
    if type(financiador_id) is not int or financiador_id <= 0:
        raise ValidationError("El financiador requiere un entero positivo.")


def consultar_borradores(*, usuario, financiador_id):
    _validar_id(financiador_id)
    requerir_financiador(usuario, financiador_id)
    return _descriptores(financiador_id)


def consultar_historial_borradores(*, usuario, financiador_id):
    """Traza de registro de configuración, sin consultar perfiles ni afiliados."""
    _validar_id(financiador_id)
    requerir_financiador(usuario, financiador_id)
    return tuple({"regla": _descriptor(fila), "creado_por_id": fila.creado_por_id,
                  "creado": fila.creado, "motivo": fila.motivo} for fila in _filas(financiador_id))


def _comparar_propuesta(*, financiador_id, propuesta, motivo, regimen, plan_id, fecha, bloquear_planes):
    """Validación compartida; el guardado conserva sus locks, la vista no reserva."""
    if not isinstance(motivo, str) or not motivo.strip() or len(motivo.strip()) > 255:
        raise ValidationError("Indicá un motivo de hasta 255 caracteres.")
    motivo = motivo.strip()
    try:
        propuesta = tuple(propuesta)
        comparacion = comparar_borradores(_descriptores(financiador_id), propuesta,
            financiador_id=financiador_id, regimen=regimen, plan_id=plan_id, fecha=fecha)
    except (TypeError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc
    planes = {b.plan_id for b in propuesta if b.plan_id is not None}
    if plan_id is not None:
        planes.add(plan_id)
    consulta_planes = Plan.objects.select_for_update() if bloquear_planes else Plan.objects.all()
    propios = set(consulta_planes.filter(
        pk__in=planes, financiador_id=financiador_id).order_by("pk").values_list("pk", flat=True))
    if propios != planes:
        raise ValidationError("Los planes deben existir y pertenecer al financiador.")
    return comparacion, motivo


def previsualizar_propuesta(*, usuario, financiador_id, propuesta, motivo, regimen, plan_id, fecha):
    """Consulta administrativa sin guardar, auditar ni activar derechos."""
    _validar_id(financiador_id)
    requerir_financiador(usuario, financiador_id, admin=True)
    comparacion, _ = _comparar_propuesta(financiador_id=financiador_id, propuesta=propuesta,
        motivo=motivo, regimen=regimen, plan_id=plan_id, fecha=fecha, bloquear_planes=False)
    return comparacion

@transaction.atomic
def guardar_borradores(*, usuario, financiador_id, propuesta, motivo, regimen, plan_id, fecha):
    """Apéndice atómico con historia real; sólo admin, sin aprobar o activar."""
    _validar_id(financiador_id)
    requerir_financiador(usuario, financiador_id, admin=True)
    financiador = Financiador.objects.select_for_update().get(pk=financiador_id, activo=True)
    requerir_financiador(usuario, financiador_id, admin=True)
    comparacion, motivo = _comparar_propuesta(financiador_id=financiador_id, propuesta=propuesta,
        motivo=motivo, regimen=regimen, plan_id=plan_id, fecha=fecha, bloquear_planes=True)
    for borrador in comparacion.nuevas:
        obj = BorradorReglaDerechos(**{c: getattr(borrador, c) for c in CAMPOS},
                                   creado_por=usuario, motivo=motivo)
        obj.full_clean()
        obj.save()
        auditar(usuario, "crear_borrador_derechos", obj.pk, financiador=financiador, motivo=motivo)
    return comparacion
