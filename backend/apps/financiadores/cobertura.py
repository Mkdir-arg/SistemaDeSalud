"""Evaluación sin efectos y reserva serializada por afiliado, compartida entre hospitales."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import Prestacion
from apps.finanzas.models_cobros import PoliticaCobro
from apps.registros.models import normalizar_documento
from .models import (
    Afiliado, AfiliacionCaso, ArancelConvenio, ConfiguracionHospital, ConsumoExterno,
    Convenio, ReglaCobertura, ReservaCobertura, VinculoCiudadano, VinculoPrestacion,
)
from .permisos import requerir_caso, requerir_hospital
from .services import auditar


def periodo(fecha, unidad):
    inicio = fecha.replace(day=1, month=1 if unidad == "anio" else fecha.month)
    if unidad == "anio":
        return inicio, inicio.replace(year=inicio.year + 1)
    return inicio, (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)


def cantidades_periodo(afiliado, comun, inicio, fin, excluir=None):
    externos = ConsumoExterno.objects.filter(afiliado=afiliado, prestacion=comun, fecha__gte=inicio, fecha__lt=fin).aggregate(n=Sum("cantidad"))["n"] or 0
    reservas = ReservaCobertura.objects.filter(afiliado=afiliado, comun=comun, fecha__gte=inicio, fecha__lt=fin, estado__in=["reservada", "realizada"])
    if excluir:
        reservas = reservas.exclude(pk=excluir)
    return externos + (reservas.aggregate(n=Sum("cubiertas"))["n"] or 0)


@transaction.atomic
def seleccionar_afiliacion(*, caso, usuario, afiliado=None, particular=False, declaracion="", motivo):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    requerir_caso(usuario, caso)
    if not motivo.strip():
        raise ValidationError("Indicá el motivo de la selección o corrección de afiliación.")
    if ReservaCobertura.objects.filter(caso=caso, estado="reservada").exists():
        raise ValidationError("El caso tiene reservas abiertas. Revisalas y liberá las prestaciones no realizadas antes de corregir la afiliación.")
    if not ConfiguracionHospital.objects.filter(institucion=caso.institucion, activo=True).exists():
        raise ValidationError("El hospital todavía no habilitó el circuito de cobertura.")
    if particular and afiliado:
        raise ValidationError("Elegí afiliación o atención particular.")
    estado, plan = "pendiente", None
    if particular:
        estado = "particular"
    elif afiliado:
        afiliado = Afiliado.objects.select_for_update().get(pk=afiliado.pk)
        from .vigencias import convenio_aplicable
        if afiliado.finalizado_en or afiliado.desde > timezone.localdate() or not afiliado.financiador.activo:
            raise ValidationError("La afiliación no está vigente para una nueva selección. Los casos anteriores conservan su afiliación.")
        if afiliado.plan_id:
            plan_actual = type(afiliado.plan).objects.select_for_update().get(pk=afiliado.plan_id)
            if not plan_actual.activo:
                raise ValidationError("El plan está inactivo para nuevas selecciones. Los casos anteriores conservan su plan.")
        convenio = convenio_aplicable(afiliado.financiador_id, caso.institucion_id, timezone.now(), bloquear=True)
        coincide = caso.ciudadano_id and normalizar_documento(caso.ciudadano.documento) == normalizar_documento(afiliado.documento)
        if not convenio or not coincide:
            raise ValidationError("La vinculación requiere convenio activo y documento coincidente. Registrá una declaración pendiente si hay discrepancias.")
        VinculoCiudadano.objects.get_or_create(afiliado=afiliado, ciudadano=caso.ciudadano, defaults={"verificado_por": usuario})
        estado, plan = "verificada", afiliado.plan
    elif not declaracion.strip():
        raise ValidationError("Indicá la afiliación declarada o elegí particular.")
    seleccion = AfiliacionCaso.objects.create(caso=caso, afiliado=afiliado, plan=plan, estado=estado, declaracion=declaracion, motivo=motivo, registrado_por=usuario)
    auditar(usuario, "seleccionar_afiliacion", seleccion.pk, institucion=caso.institucion, motivo=motivo)
    EventoCaso.objects.create(caso=caso, nodo=caso.nodo_actual, autor=usuario,
        titulo="Afiliación del caso registrada", detalle=f"{seleccion.get_estado_display()}. {motivo}")
    caso.save(update_fields=["actualizado"])
    return seleccion


def regla_aplicable(afiliacion, comun, fecha, corte):
    qs = ReglaCobertura.objects.filter(financiador=afiliacion.afiliado.financiador, vigente_desde__lte=fecha, creado__lte=corte)
    filtros = []
    if afiliacion.plan_id:
        filtros += [Q(plan_id=afiliacion.plan_id, prestacion=comun), Q(plan_id=afiliacion.plan_id, prestacion=None, categoria=comun.categoria)]
    filtros += [Q(plan=None, prestacion=comun), Q(plan=None, prestacion=None, categoria=comun.categoria)]
    for filtro in filtros:
        regla = qs.filter(filtro).first()
        if regla:
            return regla
    return None


def arancel_aplicable(*, prestacion, convenio, fecha, corte, nodo_origen_id=None):
    """Precio compartido por la consulta del financiador y la evaluación clínica."""
    politicas = PoliticaCobro.objects.filter(prestacion=prestacion, registrado__lte=corte, vigente_desde__date__lte=fecha).order_by("-vigente_desde", "-id")
    if fecha == timezone.localtime(corte).date():
        politicas = politicas.filter(vigente_desde__lte=corte)
    politica = politicas.first()
    if politica and politica.nodo_origen_id != (nodo_origen_id or prestacion.nodo_id):
        politica = None
    excepcion = None
    arancel = None
    if politica and politica.cobrar:
        excepcion = ArancelConvenio.objects.filter(convenio=convenio, prestacion=prestacion, vigente_desde__lte=fecha, creado__lte=corte).first() if convenio else None
        arancel = excepcion.importe if excepcion and excepcion.importe is not None else politica.importe
    return politica, excepcion, arancel


def evaluar(*, caso, prestacion, fecha, cantidad=1, afiliacion=None, excluir=None, corte=None, historico=False, nodo_origen_id=None, bloquear_convenio=False, intento_autorizacion=None):
    if not isinstance(cantidad, int) or isinstance(cantidad, bool) or not 1 <= cantidad <= 100000:
        raise ValidationError("La cantidad debe estar entre 1 y 100.000.")
    if prestacion.institucion_id != caso.institucion_id or (not historico and (not prestacion.activo or not prestacion.nodo_id or prestacion.nodo.version_id != caso.version_id)):
        raise ValidationError("Elegí una prestación activa de este hospital y flujo.")
    if not historico and not ConfiguracionHospital.objects.filter(institucion=caso.institucion, activo=True).exists():
        raise ValidationError("El circuito de cobertura no está habilitado para el hospital.")
    afiliacion = afiliacion or AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).first()
    vinculo = VinculoPrestacion.objects.filter(prestacion=prestacion).select_related("comun").first()
    if not afiliacion or not vinculo:
        raise ValidationError("Seleccioná afiliación y vinculá la prestación al catálogo común antes de evaluar.")
    corte = corte or timezone.now()
    from .vigencias import convenio_aplicable
    convenio = convenio_aplicable(afiliacion.afiliado.financiador_id, caso.institucion_id, corte, bloquear=bloquear_convenio) if afiliacion.afiliado_id and afiliacion.estado != "pendiente" else None
    politica, excepcion, arancel = arancel_aplicable(prestacion=prestacion, convenio=convenio, fecha=fecha, corte=corte, nodo_origen_id=nodo_origen_id)
    resultado = {
        "caso": caso.pk, "afiliacion": afiliacion.pk, "prestacion": prestacion.pk, "comun": vinculo.comun_id,
        "institucion": caso.institucion_id, "area": caso.area_actual_id,
        "nombre_prestacion": prestacion.nombre, "fecha": str(fecha), "cantidad": cantidad,
        "estado": "no_cubierta", "motivo": "No cubierta — sin regla aplicable",
        "porcentaje": "0.00", "cupo": None, "periodo": "anio", "cubiertas": 0,
        "disponibles": None, "importe_total": None, "importe_financiador": None, "importe_paciente": None,
        "arancel": None, "cobrar": bool(politica and politica.cobrar), "sensible": bool(politica and politica.sensible),
        "origen_arancel": "general_hospital", "retorno_arancel_general": False,
        "politica": politica.pk if politica else None, "regla": None, "excepcion": None,
        "convenio": convenio.pk if convenio else None,
    }
    porcentaje, regla = Decimal(0), None
    if afiliacion.estado == "pendiente":
        resultado.update(estado="pendiente_evaluacion", motivo="Afiliación pendiente de verificación")
    elif afiliacion.afiliado_id:
        if not convenio:
            resultado.update(estado="no_cubierta", motivo="No cubierta — sin convenio vigente. El importe del paciente requiere aceptación expresa")
        else:
            regla = regla_aplicable(afiliacion, vinculo.comun, fecha, corte)
            porcentaje = regla.porcentaje if regla else convenio.porcentaje_default or Decimal(0)
            if regla:
                resultado.update(regla=regla.pk, cupo=regla.cupo, periodo=regla.periodo)
            inicio, fin = periodo(fecha, resultado["periodo"])
            usados = cantidades_periodo(afiliacion.afiliado, vinculo.comun, inicio, fin, excluir)
            disponibles = max(0, regla.cupo-usados) if regla and regla.cupo is not None else cantidad
            cubiertas = min(cantidad, disponibles) if porcentaje > 0 else 0
            resultado.update(cubiertas=cubiertas, disponibles=disponibles if regla and regla.cupo is not None else None)
            if cubiertas:
                resultado.update(estado="cubierta" if cubiertas == cantidad and porcentaje == 100 else "parcial", motivo="Cobertura según plan y cupo disponible")
            elif regla and regla.cupo is not None and disponibles == 0:
                resultado["motivo"] = "No cubierta — cupo agotado"
    else:
        resultado["motivo"] = "Atención particular"
    resultado["porcentaje"] = str(porcentaje)
    resultado["inicio_periodo"] = str(periodo(fecha, resultado["periodo"])[0])
    if not politica:
        resultado.update(estado="pendiente_evaluacion", motivo="Falta definir la política de cobro del hospital")
    elif not politica.cobrar:
        resultado.update(importe_total="0.00", importe_financiador="0.00", importe_paciente="0.00", motivo=resultado["motivo"] + ". El hospital no cobra esta prestación")
    else:
        resultado["excepcion"] = excepcion.pk if excepcion else None
        resultado["origen_arancel"] = "acordado_financiador" if excepcion and excepcion.importe is not None else "general_hospital"
        resultado["retorno_arancel_general"] = bool(excepcion and excepcion.importe is None)
        if arancel is None:
            resultado.update(estado="arancel_pendiente", motivo="Arancel pendiente")
        else:
            total = (arancel*cantidad).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if total > Decimal("999999999999.99"):
                resultado.update(estado="pendiente_evaluacion", motivo="El importe total supera el máximo admitido por Finanzas")
                return resultado
            financiador = (arancel*resultado["cubiertas"]*porcentaje/100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            resultado.update(arancel=str(arancel), importe_total=str(total), importe_financiador=str(financiador), importe_paciente=str(total-financiador))
    from .uso_autorizaciones import agregar_evaluacion
    agregar_evaluacion(resultado, caso=caso, afiliacion=afiliacion, regla=regla,
                       fecha=fecha, corte=corte, excluir=excluir, historico=historico,
                       intento=intento_autorizacion)
    return resultado


def cotizacion(**datos):
    resultado = evaluar(**datos)
    return {**resultado, "firma": signing.dumps(resultado, salt="cobertura-cotizacion", compress=True)}


@transaction.atomic
def reservar(*, caso, prestacion, usuario, fecha, cantidad, clave, firma, acepta=False):
    caso = Caso.objects.select_for_update().get(pk=caso.pk)
    requerir_caso(usuario, caso)
    clave = UUID(str(clave))
    solicitud = {"caso": caso.pk, "prestacion": prestacion.pk, "fecha": str(fecha), "cantidad": cantidad, "firma": firma, "acepta": acepta}
    previa = ReservaCobertura.objects.filter(clave=clave).first()
    if previa:
        if previa.solicitud != solicitud:
            raise ValidationError("La clave ya fue utilizada para otra confirmación.")
        return previa
    if fecha < timezone.localdate():
        raise ValidationError("No se puede reservar una prestación con fecha pasada.")
    if caso.estado in Caso.ESTADOS_FINALIZADOS:
        raise ValidationError("El caso ya finalizó.")
    afiliacion = AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).first()
    if afiliacion and afiliacion.afiliado_id:
        Afiliado.objects.select_for_update().get(pk=afiliacion.afiliado_id)
    resultado = evaluar(caso=caso, prestacion=prestacion, fecha=fecha, cantidad=cantidad, afiliacion=afiliacion, bloquear_convenio=True)
    try:
        mostrada = signing.loads(firma, salt="cobertura-cotizacion", max_age=1800)
    except signing.BadSignature as error:
        raise ValidationError("La evaluación venció. Volvé a consultar los importes.") from error
    if mostrada != resultado:
        raise ValidationError("La cobertura o el importe cambió. Revisá una nueva evaluación antes de confirmar.", code="evaluacion_cambio")
    if resultado["estado"] in ["pendiente_evaluacion", "arancel_pendiente"]:
        raise ValidationError("Completá los datos pendientes antes de confirmar cobertura. La atención puede continuar.")
    if ReservaCobertura.objects.filter(caso=caso, prestacion=prestacion, estado="reservada").exists():
        raise ValidationError("Ya existe una reserva abierta para esta prestación. Revisala antes de crear otra.")
    aceptacion = {}
    if acepta:
        requerir_hospital(usuario, caso.institucion_id, "registrar_aceptacion", caso.area_actual_id, resultado["sensible"])
        aceptacion = {"prestacion": prestacion.pk, "importe": resultado["importe_paciente"], "usuario": usuario.pk, "fecha": timezone.now().isoformat()}
    reserva = ReservaCobertura.objects.create(caso=caso, afiliacion=afiliacion, afiliado=afiliacion.afiliado, prestacion=prestacion, comun_id=resultado["comun"], fecha=fecha, cantidad=cantidad, cubiertas=resultado["cubiertas"], evaluacion=resultado, aceptacion=aceptacion, clave=clave, solicitud=solicitud, creado_por=usuario)
    from .uso_autorizaciones import registrar_uso
    registrar_uso(reserva)
    auditar(usuario, "reservar_cobertura", reserva.pk, institucion=caso.institucion)
    return reserva


@transaction.atomic
def liberar(*, reserva, usuario, motivo, no_realizada):
    caso = Caso.objects.select_for_update().get(pk=reserva.caso_id)
    requerir_caso(usuario, caso, certificar=True)
    if reserva.afiliado_id:
        Afiliado.objects.select_for_update().get(pk=reserva.afiliado_id)
    reserva = ReservaCobertura.objects.select_for_update().get(pk=reserva.pk)
    if reserva.estado == "liberada":
        return reserva
    from apps.finanzas.models import HechoAtencionCosteable
    registrada = HechoAtencionCosteable.objects.filter(caso_origen_id=caso.pk, nodo_origen_id=reserva.prestacion.nodo_id, ocurrida_en__gte=reserva.creado).exists()
    if reserva.estado != "reservada" or registrada or not no_realizada or not motivo.strip():
        raise ValidationError("Sólo se libera después de confirmar que la prestación no se realizó y registrar el motivo.")
    reserva.estado, reserva.motivo = "liberada", motivo
    reserva.cerrado_por, reserva.cerrado_en = usuario, timezone.now()
    reserva.save(update_fields=["estado", "motivo", "cerrado_por", "cerrado_en"])
    from .uso_autorizaciones import liberar_uso
    liberar_uso(reserva)
    auditar(usuario, "liberar_reserva", reserva.pk, institucion=caso.institucion, motivo=motivo)
    return reserva
