"""Dinero real vinculado: no modifica costos, gastos ni repartos."""
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import AjusteObligacion, ConcesionFinanciera, Gasto, MovimientoDinero, ObligacionFinanciera
from .permisos import tiene_concesion_financiera

CERO = Decimal("0.00")
PENDIENTE = "pendiente_aprobacion"
APROBADO = "aprobado"
RECHAZADO = "rechazado"


class EstadoDineroCambio(APIException):
    status_code = 409
    default_detail = "El saldo cambió. Revisá el resultado antes de confirmar nuevamente."


def _importe(valor):
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValidationError({"importe": "Ingresá un importe válido."})
    if not numero.is_finite() or numero <= 0 or numero >= Decimal("1000000000000") or numero != numero.quantize(Decimal("0.01")):
        raise ValidationError({"importe": "Ingresá un importe positivo de hasta dos decimales."})
    return numero.quantize(Decimal("0.01"))


def _fecha(valor):
    try:
        resultado = date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        raise ValidationError({"fecha": "Ingresá una fecha válida."})
    if resultado > timezone.localdate():
        raise ValidationError({"fecha": "Un movimiento real no puede tener fecha futura."})
    return resultado


def _clave(valor):
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError({"clave": "La clave de operación debe ser un UUID válido."})


def _texto(valor, campo, limite, obligatorio=False):
    texto = str(valor or "").strip()
    if (obligatorio and not texto) or len(texto) > limite:
        raise ValidationError({campo: f"Ingresá un texto válido de hasta {limite} caracteres."})
    return texto


def _permiso(usuario, obligacion, accion):
    if not tiene_concesion_financiera(usuario, accion, obligacion.institucion_id, obligacion.area_id, sensible=obligacion.sensible):
        raise PermissionDenied("No tenés permiso para esta operación en esta institución y área.")


def _repetido(modelo, institucion_id, clave, solicitud):
    anterior = modelo.objects.filter(institucion_id=institucion_id, clave=clave).first()
    if anterior and anterior.solicitud != solicitud:
        raise ValidationError({"clave": "Esta clave ya fue utilizada para otra operación. No se registró ningún cambio."})
    return anterior


def _aprobacion(usuario, obligacion, aprobado):
    if aprobado is not None and not isinstance(aprobado, bool):
        raise ValidationError({"aprobado": "Indicá verdadero o falso."})
    puede_aprobar = tiene_concesion_financiera(usuario, ConcesionFinanciera.Accion.APROBAR_DINERO, obligacion.institucion_id, obligacion.area_id, sensible=obligacion.sensible)
    if aprobado is True and not puede_aprobar:
        raise PermissionDenied("No tenés permiso para aprobar esta operación.")
    confirmado = puede_aprobar if aprobado is None else aprobado
    return {"estado": APROBADO if confirmado else PENDIENTE, "aprobado_por": usuario if confirmado else None, "aprobado_en": timezone.now() if confirmado else None}


@transaction.atomic
def estado_obligacion(obligacion):
    # Evita combinar un pago anterior con una reducción/reintegro posterior.
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=obligacion.pk)
    movimientos = list(obligacion.movimientos.values_list("id", "tipo", "importe", "estado", "ajuste_id"))
    ajustes = list(obligacion.ajustes.values_list("id", "importe", "estado"))
    actual = obligacion.importe_original + sum((importe for _, importe, estado in ajustes if estado == APROBADO), CERO)
    neto = sum((-importe if tipo == "reintegro" else importe for _, tipo, importe, estado, _ in movimientos if estado == APROBADO), CERO)
    pagos_pendientes = sum((importe for _, tipo, importe, estado, _ in movimientos if estado == PENDIENTE and tipo != "reintegro"), CERO)
    reintegros_pendientes = sum((importe for _, tipo, importe, estado, _ in movimientos if estado == PENDIENTE and tipo == "reintegro"), CERO)
    ajustes_conjuntos = {ajuste for _, tipo, _, estado, ajuste in movimientos if tipo == "reintegro" and estado == PENDIENTE and ajuste}
    reducciones_pendientes = -sum((importe for _, importe, estado in ajustes if estado == PENDIENTE), CERO)
    reducciones_independientes = -sum((importe for pk, importe, estado in ajustes if estado == PENDIENTE and pk not in ajustes_conjuntos), CERO)
    disponible_registro = max(actual - neto - pagos_pendientes - reducciones_independientes, CERO)
    disponible_reducir = max(actual - reducciones_pendientes, CERO)
    if pagos_pendientes:
        disponible_reducir = min(disponible_reducir, disponible_registro)
    version = hashlib.sha256(json.dumps([str(obligacion.importe_original), [(pk, tipo, str(importe), estado, ajuste) for pk, tipo, importe, estado, ajuste in movimientos], [(pk, str(importe), estado) for pk, importe, estado in ajustes]], sort_keys=True).encode()).hexdigest()
    return {
        "obligacion_actual": actual,
        "registrado_neto": neto,
        "pendiente": max(actual - neto, CERO),
        "disponible_reintegro": max(neto - reintegros_pendientes, CERO),
        "saldo_a_devolver": max(neto - actual, CERO),
        "por_aprobar": pagos_pendientes,
        "reintegros_por_aprobar": reintegros_pendientes,
        "ajustes_por_aprobar": reducciones_pendientes,
        "reducciones_independientes_por_aprobar": reducciones_independientes,
        "disponible_registro": disponible_registro,
        "disponible_reducir": disponible_reducir,
        "version_esperada": version,
    }


def disponible_reintegro(movimiento):
    if movimiento.tipo == MovimientoDinero.Tipo.REINTEGRO or movimiento.estado != APROBADO:
        return CERO
    return movimiento.importe - (movimiento.reintegros.exclude(estado=RECHAZADO).aggregate(total=Sum("importe"))["total"] or CERO)


def disponible_reduccion(ajuste):
    if ajuste.estado != APROBADO:
        return CERO
    return -ajuste.importe - (ajuste.reintegros.exclude(estado=RECHAZADO).aggregate(total=Sum("importe"))["total"] or CERO)


def _validar_reduccion(estado, importe, *, conjunta=False):
    if importe > estado["obligacion_actual"] - estado["ajustes_por_aprobar"]:
        raise ValidationError({"importe": "La reducción supera lo disponible de la obligación, incluidas las reducciones por aprobar."})
    if not conjunta and estado["por_aprobar"] and importe > estado["disponible_registro"]:
        raise ValidationError({"importe": "Hay pagos o cobros por aprobar que reservan este importe. Resolvelos antes de reducir la obligación."})


@transaction.atomic
def crear_obligacion_pago(*, gasto, contraparte_nombre, contraparte_referencia="", clave, usuario):
    # El gasto es el punto de serialización para la creación de una única deuda.
    gasto = Gasto.objects.select_for_update().get(pk=getattr(gasto, "pk", gasto))
    _permiso(usuario, gasto, ConcesionFinanciera.Accion.REGISTRAR_DINERO)
    clave = _clave(clave)
    nombre = _texto(contraparte_nombre, "contraparte_nombre", 160, True)
    referencia = _texto(contraparte_referencia, "contraparte_referencia", 160)
    solicitud = {"tipo": "pagar", "gasto": gasto.pk, "nombre": nombre, "referencia": referencia}
    existente = _repetido(ObligacionFinanciera, gasto.institucion_id, clave, solicitud)
    if existente:
        return existente
    if gasto.estado != Gasto.Estado.APROBADO or Gasto.objects.filter(reemplaza=gasto).exists():
        raise ValidationError({"gasto": "Elegí un gasto aprobado y vigente."})
    if ObligacionFinanciera.objects.filter(gasto=gasto).exists():
        raise ValidationError({"gasto": "Este gasto ya tiene una obligación vinculada."})
    importe = gasto.importe + (gasto.ajustes.filter(estado=APROBADO).aggregate(total=Sum("importe"))["total"] or CERO)
    importe = _importe(importe)
    return ObligacionFinanciera.objects.create(tipo="pagar", gasto=gasto, institucion_id=gasto.institucion_id, area_id=gasto.area_id, sensible=gasto.sensible, importe_original=importe, periodo_economico=gasto.periodo_economico, contraparte_nombre=nombre, contraparte_referencia=referencia, clave=clave, solicitud=solicitud, creado_por=usuario)


@transaction.atomic
def crear_obligacion_cobro(*, hecho, importe, contraparte_nombre, contraparte_referencia="", creado_por=None, clave, periodo_economico=None, sensible=False):
    """Solo para el generador de cargos con política/tarifa explícita congelada."""
    hecho = type(hecho).objects.select_for_update().get(pk=hecho.pk)
    importe = _importe(importe)
    clave = _clave(clave)
    nombre = _texto(contraparte_nombre, "contraparte_nombre", 160, True)
    referencia = _texto(contraparte_referencia, "contraparte_referencia", 160)
    periodo = periodo_economico or timezone.localtime(hecho.ocurrida_en).date().replace(day=1)
    solicitud = {"tipo": "cobrar", "hecho": hecho.pk, "importe": str(importe), "nombre": nombre, "referencia": referencia, "periodo": str(periodo), "sensible": sensible}
    existente = _repetido(ObligacionFinanciera, hecho.institucion_id, clave, solicitud)
    if existente:
        return existente
    return ObligacionFinanciera.objects.create(tipo="cobrar", hecho=hecho, institucion_id=hecho.institucion_id, area_id=hecho.area_origen_id, sensible=sensible, importe_original=importe, periodo_economico=periodo, contraparte_nombre=nombre, contraparte_referencia=referencia, clave=clave, solicitud=solicitud, creado_por=creado_por)


@transaction.atomic
def registrar_movimiento(*, obligacion, importe, fecha, clave, usuario, referencia="", aprobado=None):
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=getattr(obligacion, "pk", obligacion))
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.REGISTRAR_DINERO)
    importe, fecha, clave = _importe(importe), _fecha(fecha), _clave(clave)
    referencia = _texto(referencia, "referencia", 160)
    aprobacion = _aprobacion(usuario, obligacion, aprobado)
    solicitud = {"obligacion": obligacion.pk, "importe": str(importe), "fecha": str(fecha), "referencia": referencia, "operacion": "registrar", "aprobado": aprobado}
    existente = _repetido(MovimientoDinero, obligacion.institucion_id, clave, solicitud)
    if existente:
        return existente
    if importe > estado_obligacion(obligacion)["disponible_registro"]:
        raise ValidationError({"importe": "El importe supera lo disponible de esta obligación, considerando lo que está por aprobar."})
    return MovimientoDinero.objects.create(obligacion=obligacion, institucion_id=obligacion.institucion_id, tipo="pago" if obligacion.tipo == "pagar" else "cobro", importe=importe, fecha=fecha, referencia=referencia, clave=clave, solicitud=solicitud, autor=usuario, **aprobacion)


@transaction.atomic
def reducir_obligacion(*, obligacion, importe, motivo, clave, usuario, aprobado=None):
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=getattr(obligacion, "pk", obligacion))
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.CORREGIR_DINERO)
    importe, clave = _importe(importe), _clave(clave)
    motivo = _texto(motivo, "motivo", 255, True)
    aprobacion = _aprobacion(usuario, obligacion, aprobado)
    solicitud = {"obligacion": obligacion.pk, "importe": str(importe), "motivo": motivo, "operacion": "reducir", "aprobado": aprobado}
    existente = _repetido(AjusteObligacion, obligacion.institucion_id, clave, solicitud)
    if existente:
        return existente
    _validar_reduccion(estado_obligacion(obligacion), importe)
    return AjusteObligacion.objects.create(obligacion=obligacion, institucion_id=obligacion.institucion_id, importe=-importe, motivo=motivo, clave=clave, solicitud=solicitud, autor=usuario, **aprobacion)


def _plan_reintegro(original, importe, fecha, motivo, efecto, ajuste, *, aprobado=True):
    importe, fecha = _importe(importe), _fecha(fecha)
    motivo = _texto(motivo, "motivo", 255, True)
    if original.tipo == "reintegro" or importe > disponible_reintegro(original):
        raise ValidationError({"importe": "El importe supera lo que puede devolverse de este movimiento."})
    if fecha < original.fecha:
        raise ValidationError({"fecha": "La devolución no puede ser anterior al movimiento original."})
    estado = estado_obligacion(original.obligacion)
    actual = estado["obligacion_actual"]
    if efecto == "reducir":
        if ajuste is not None:
            raise ValidationError({"ajuste": "No selecciones una reducción previa al crear una nueva."})
        _validar_reduccion(estado, importe, conjunta=True)
        actual -= importe
    elif efecto == "reduccion_existente":
        if ajuste is None or ajuste.obligacion_id != original.obligacion_id or importe > disponible_reduccion(ajuste):
            raise ValidationError({"ajuste": "Elegí una reducción de esta obligación con importe disponible suficiente."})
    elif efecto != "mantener" or ajuste is not None:
        raise ValidationError({"efecto": "Elegí mantener, reducir o usar una reducción existente."})
    neto = estado["registrado_neto"] - importe
    pendiente_proyectado = max(actual - neto, CERO)
    return {"importe": importe, "fecha": fecha, "motivo": motivo, "efecto": efecto, "aprobado": aprobado, "estado": APROBADO if aprobado else PENDIENTE, "pendiente_anterior": estado["pendiente"], "pendiente_resultante": pendiente_proyectado if aprobado else estado["pendiente"], "pendiente_al_aprobar": pendiente_proyectado, "obligacion_resultante": actual if aprobado else estado["obligacion_actual"], "registrado_neto_resultante": neto if aprobado else estado["registrado_neto"], "importe_reservado": CERO if aprobado else importe, "version_esperada": estado["version_esperada"]}


@transaction.atomic
def previsualizar_reintegro(*, original, importe, fecha, motivo, efecto, usuario, ajuste=None, aprobado=None):
    original = MovimientoDinero.objects.get(pk=getattr(original, "pk", original))
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=original.obligacion_id)
    original.obligacion = obligacion
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.CORREGIR_DINERO)
    if ajuste is not None and efecto != "reduccion_existente":
        raise ValidationError({"ajuste": "Sólo seleccioná una reducción cuando elegís usar una reducción existente."})
    ajuste = AjusteObligacion.objects.filter(pk=getattr(ajuste, "pk", ajuste), obligacion=obligacion).first() if ajuste is not None else None
    aprobacion = _aprobacion(usuario, obligacion, aprobado)
    return _plan_reintegro(original, importe, fecha, motivo, efecto, ajuste, aprobado=aprobacion["estado"] == APROBADO)


@transaction.atomic
def reintegrar_movimiento(*, original, importe, fecha, motivo, efecto, clave, version_esperada, usuario, ajuste=None, pendiente_esperado=None, aprobado=None):
    original = MovimientoDinero.objects.get(pk=getattr(original, "pk", original))
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=original.obligacion_id)
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.CORREGIR_DINERO)
    original = MovimientoDinero.objects.select_for_update().get(pk=original.pk)
    original.obligacion = obligacion
    importe, fecha, clave = _importe(importe), _fecha(fecha), _clave(clave)
    motivo = _texto(motivo, "motivo", 255, True)
    ajuste_id = getattr(ajuste, "pk", ajuste)
    aprobacion = _aprobacion(usuario, obligacion, aprobado)
    solicitud = {"original": original.pk, "importe": str(importe), "fecha": str(fecha), "motivo": motivo, "efecto": efecto, "ajuste": ajuste_id, "operacion": "reintegrar", "aprobado": aprobado}
    existente = _repetido(MovimientoDinero, obligacion.institucion_id, clave, solicitud)
    if existente:
        return existente
    if ajuste_id is not None and efecto != "reduccion_existente":
        raise ValidationError({"ajuste": "Sólo seleccioná una reducción cuando elegís usar una reducción existente."})
    ajuste = AjusteObligacion.objects.filter(pk=ajuste_id, obligacion=obligacion).first() if ajuste_id is not None else None
    plan = _plan_reintegro(original, importe, fecha, motivo, efecto, ajuste, aprobado=aprobacion["estado"] == APROBADO)
    if version_esperada != plan["version_esperada"]:
        raise EstadoDineroCambio()
    if pendiente_esperado is not None and Decimal(str(pendiente_esperado)) != plan["pendiente_anterior"]:
        raise EstadoDineroCambio()
    if efecto == "reducir":
        if AjusteObligacion.objects.filter(institucion_id=obligacion.institucion_id, clave=clave).exists():
            raise ValidationError({"clave": "Esta clave ya identifica una reducción. Elegí usar la reducción existente."})
        ajuste = AjusteObligacion.objects.create(obligacion=obligacion, institucion_id=obligacion.institucion_id, importe=-importe, motivo=motivo, clave=clave, solicitud={"operacion": "reduccion_con_reintegro", "aprobado": aprobado}, autor=usuario, **aprobacion)
    return MovimientoDinero.objects.create(obligacion=obligacion, institucion_id=obligacion.institucion_id, tipo="reintegro", original=original, ajuste=ajuste, importe=importe, fecha=fecha, motivo=motivo, clave=clave, solicitud=solicitud, autor=usuario, **aprobacion)


def movimiento_conjunto(ajuste):
    """Una reducción creada con una devolución sólo se decide junto a ella."""
    return ajuste.reintegros.filter(solicitud__efecto="reducir").first()


def _decidir_registro(registro, usuario, aprobar, motivo=""):
    destino = APROBADO if aprobar else RECHAZADO
    motivo = _texto(motivo, "motivo", 255, not aprobar)
    if registro.estado != PENDIENTE:
        if registro.estado == destino and (aprobar or registro.motivo_rechazo == motivo):
            return registro
        raise ValidationError("Esta operación ya fue resuelta. Los registros aprobados o rechazados no se reescriben.")
    campos = {"estado": destino}
    if aprobar:
        campos.update(aprobado_por=usuario, aprobado_en=timezone.now())
    else:
        campos.update(rechazado_por=usuario, rechazado_en=timezone.now(), motivo_rechazo=motivo)
    # Única excepción acotada a la inmutabilidad: resolución auditada del pendiente.
    for nombre, valor in campos.items():
        setattr(registro, nombre, valor)
    registro.full_clean()
    type(registro).objects.filter(pk=registro.pk, estado=PENDIENTE).update(**campos)
    return registro


@transaction.atomic
def decidir_movimiento(*, movimiento, usuario, aprobar, motivo=""):
    movimiento = MovimientoDinero.objects.get(pk=getattr(movimiento, "pk", movimiento))
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=movimiento.obligacion_id)
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.APROBAR_DINERO)
    movimiento = MovimientoDinero.objects.select_for_update().get(pk=movimiento.pk)
    if movimiento.estado != PENDIENTE:
        return _decidir_registro(movimiento, usuario, aprobar, motivo)
    conjunta = movimiento.tipo == "reintegro" and movimiento.solicitud.get("efecto") == "reducir"
    ajuste = AjusteObligacion.objects.select_for_update().get(pk=movimiento.ajuste_id) if conjunta else None
    if ajuste is not None and ajuste.estado != PENDIENTE:
        raise ValidationError("La devolución y su reducción deben resolverse juntas.")
    if aprobar:
        estado = estado_obligacion(obligacion)
        if movimiento.tipo != "reintegro":
            if estado["por_aprobar"] > estado["obligacion_actual"] - estado["registrado_neto"] - estado["reducciones_independientes_por_aprobar"]:
                raise ValidationError("La obligación ya no alcanza para los movimientos reservados. Revisá los pendientes.")
        else:
            original = MovimientoDinero.objects.select_for_update().get(pk=movimiento.original_id)
            if original.estado != APROBADO or movimiento.importe > disponible_reintegro(original) + movimiento.importe:
                raise ValidationError("El movimiento original no tiene importe disponible para esta devolución.")
            if conjunta:
                estado["ajustes_por_aprobar"] -= movimiento.importe
                _validar_reduccion(estado, movimiento.importe, conjunta=True)
            elif movimiento.ajuste_id:
                existente = AjusteObligacion.objects.get(pk=movimiento.ajuste_id)
                if existente.estado != APROBADO or movimiento.importe > disponible_reduccion(existente) + movimiento.importe:
                    raise ValidationError("La reducción seleccionada no tiene importe disponible.")
    if ajuste is not None:
        _decidir_registro(ajuste, usuario, aprobar, motivo)
    return _decidir_registro(movimiento, usuario, aprobar, motivo)


@transaction.atomic
def decidir_ajuste(*, ajuste, obligacion, usuario, aprobar, motivo=""):
    obligacion = ObligacionFinanciera.objects.select_for_update().get(pk=getattr(obligacion, "pk", obligacion))
    _permiso(usuario, obligacion, ConcesionFinanciera.Accion.APROBAR_DINERO)
    ajuste = AjusteObligacion.objects.select_for_update().filter(pk=getattr(ajuste, "pk", ajuste), obligacion=obligacion).first()
    if ajuste is None:
        raise ValidationError({"ajuste": "No se encontró la reducción en esta obligación."})
    if movimiento_conjunto(ajuste):
        raise ValidationError("Esta reducción pertenece a una devolución. Aprobá o rechazá la devolución para resolver ambas juntas.")
    if aprobar and ajuste.estado == PENDIENTE:
        estado = estado_obligacion(obligacion)
        importe = -ajuste.importe
        estado["ajustes_por_aprobar"] -= importe
        estado["reducciones_independientes_por_aprobar"] -= importe
        estado["disponible_registro"] = max(estado["obligacion_actual"] - estado["registrado_neto"] - estado["por_aprobar"] - estado["reducciones_independientes_por_aprobar"], CERO)
        _validar_reduccion(estado, importe)
    return _decidir_registro(ajuste, usuario, aprobar, motivo)
