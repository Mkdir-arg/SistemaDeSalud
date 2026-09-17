"""Distribuye cargos sobre el origen clínico durable, reutilizando obligaciones de Finanzas."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid5, NAMESPACE_URL

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.finanzas.dinero import crear_obligacion_cobro
from apps.finanzas.models import HechoAtencionCosteable, Prestacion
from .cobertura import evaluar
from .models import (
    Afiliado, AfiliacionCaso, ConfiguracionHospital, DistribucionCobro,
    ReservaCobertura, ResolucionSaldo,
    RevisionContexto, Convenio,
)
from .permisos import requerir_hospital
from .services import auditar


def contexto_cobertura(caso, nodo):
    seleccion = AfiliacionCaso.objects.filter(caso=caso, hecho_revision=None).first()
    reservas = ReservaCobertura.objects.filter(caso=caso, prestacion__nodo=nodo, estado="reservada")
    if not reservas.exists() and not ConfiguracionHospital.objects.filter(institucion=caso.institucion, activo=True).exists():
        return {}
    # El modo y el catálogo se capturan con el hecho. Una recuperación nunca cae
    # al generador legado, aunque el hospital desactive el módulo después.
    from .autorizaciones import intento_actual
    return {"afiliacion": seleccion.pk if seleccion else None, "prestaciones": list(Prestacion.objects.filter(institucion=caso.institucion, nodo=nodo, activo=True).values_list("pk", flat=True)), "reservas": list(reservas.values_list("pk", flat=True)), "intento_autorizacion": str(intento_actual(caso))}


def _obligacion(reserva, parte, importe, nombre, referencia):
    return crear_obligacion_cobro(hecho=reserva.hecho, importe=importe, contraparte_nombre=nombre, contraparte_referencia=referencia, clave=uuid5(NAMESPACE_URL, f"salud:cobertura:{reserva.pk}:{parte}"), sensible=reserva.evaluacion.get("sensible", True))


def capturar_cobertura(hecho):
    """Se llama con el hecho bloqueado, dentro de la captura financiera recuperable."""
    contexto = hecho.cobertura_contexto
    if contexto.get("pendiente"):
        revision = RevisionContexto.objects.filter(hecho=hecho).first()
        if not revision:
            raise ValidationError("El contexto de cobertura requiere revisión administrativa antes de recuperar cargos.")
        contexto = revision.contexto
    if contexto["afiliacion"]:
        afiliacion = AfiliacionCaso.objects.get(pk=contexto["afiliacion"])
    else:
        afiliacion, _ = AfiliacionCaso.objects.get_or_create(caso=hecho.caso, hecho_revision=hecho, defaults={"estado": "pendiente", "motivo": "Afiliación no seleccionada al registrar la prestación", "registrado_por": hecho.autor})
    ids = set(contexto["prestaciones"])
    reservadas = list(ReservaCobertura.objects.filter(pk__in=contexto["reservas"]).order_by("afiliado_id", "pk"))
    # Orden estable de afiliados incluso si hubo corrección de afiliación del caso.
    afiliados = {r.afiliado_id for r in reservadas if r.afiliado_id}
    if afiliacion.afiliado_id:
        afiliados.add(afiliacion.afiliado_id)
    list(Afiliado.objects.select_for_update().filter(pk__in=afiliados).order_by("pk"))
    reservadas = list(ReservaCobertura.objects.filter(pk__in=contexto["reservas"]).order_by("afiliado_id", "pk"))
    for prestacion_id in sorted(ids | {r.prestacion_id for r in reservadas}):
        reserva = next((r for r in reservadas if r.prestacion_id == prestacion_id), None)
        if not reserva:
            reserva = ReservaCobertura.objects.filter(hecho=hecho, prestacion_id=prestacion_id).first()
        if not reserva:
            prestacion = Prestacion.objects.get(pk=prestacion_id)
            resultado = evaluar(caso=hecho.caso, prestacion=prestacion, fecha=timezone.localtime(hecho.ocurrida_en).date(), afiliacion=afiliacion, corte=hecho.ocurrida_en, historico=True, nodo_origen_id=hecho.nodo_origen_id, intento_autorizacion=contexto.get("intento_autorizacion"))
            reserva = ReservaCobertura.objects.create(caso=hecho.caso, afiliacion=afiliacion, afiliado=afiliacion.afiliado, prestacion=prestacion, comun_id=resultado["comun"], fecha=date.fromisoformat(resultado["fecha"]), cantidad=1, cubiertas=resultado["cubiertas"], evaluacion=resultado, hecho=hecho)
        if reserva.hecho_id and reserva.hecho_id != hecho.pk:
            raise ValidationError("La reserva ya corresponde a otra atención.")
        if reserva.estado != "realizada":
            anterior = reserva.evaluacion
            actual = evaluar(caso=reserva.caso, prestacion=reserva.prestacion, fecha=timezone.localtime(hecho.ocurrida_en).date(), cantidad=reserva.cantidad, afiliacion=reserva.afiliacion, excluir=reserva.pk, corte=hecho.ocurrida_en, historico=True, nodo_origen_id=hecho.nodo_origen_id, intento_autorizacion=contexto.get("intento_autorizacion"))
            condiciones = ["politica", "regla", "excepcion", "inicio_periodo", "estado"]
            if "convenio" in anterior:
                condiciones.append("convenio")
            # El estado puede cambiar sólo por consumo externo: eso NO revoca Q01.
            condiciones.remove("estado")
            if any(anterior.get(k) != actual.get(k) for k in condiciones):
                actual["evaluacion_confirmada"] = anterior
                reserva.evaluacion, reserva.cubiertas, reserva.aceptacion = actual, actual["cubiertas"], {}
                reserva.discrepancia = True
            elif anterior.get("requiere_autorizacion"):
                # Cambió la autorización, no el precio aceptado ni el cupo que
                # ya se comprometió. Se conserva la primera evaluación completa.
                from .uso_autorizaciones import actualizar_confirmada
                revisada = actualizar_confirmada(reserva, timezone.localtime(hecho.ocurrida_en).date(), hecho.ocurrida_en, historico=True)
                if any(anterior.get(k) != revisada.get(k) for k in ("autorizacion", "estado_autorizacion", "autorizacion_revision")):
                    reserva.evaluacion = {**revisada, "evaluacion_confirmada": anterior}
                    reserva.discrepancia = True
            if reserva.estado == "liberada":
                reserva.discrepancia = True
            reserva.estado, reserva.hecho = "realizada", hecho
            reserva.fecha = timezone.localtime(hecho.ocurrida_en).date()
            reserva.cerrado_en = timezone.now()
            reserva.save(update_fields=["estado", "hecho", "fecha", "cerrado_en", "evaluacion", "cubiertas", "aceptacion", "discrepancia"])
        from .uso_autorizaciones import registrar_uso
        registrar_uso(reserva, consumir=True)
        distribuir(reserva)


def distribuir(reserva, completar=False):
    existente = DistribucionCobro.objects.filter(reserva=reserva).first()
    if existente and not completar:
        return existente
    dato = reserva.evaluacion
    estado = "pendiente"
    if dato["estado"] == "pendiente_evaluacion":
        estado = "evaluacion_pendiente"
    elif dato["estado"] == "arancel_pendiente":
        estado = "arancel_pendiente"
    elif not dato["cobrar"]:
        estado = "sin_cobro"
    from .uso_autorizaciones import autorizacion_cumplida
    resolucion_autorizacion = existente and existente.resoluciones.filter(parte="financiador").exclude(decision="rechazar").exists()
    pendiente_autorizacion = (estado == "pendiente" and not autorizacion_cumplida(reserva)
                             and not resolucion_autorizacion)
    if pendiente_autorizacion:
        estado = "autorizacion_pendiente"
    valores = {"importe_financiador": Decimal(dato["importe_financiador"] or "0"), "importe_paciente": Decimal(dato["importe_paciente"] or "0"), "estado": estado}
    if existente:
        distribucion = existente
        for campo, valor in valores.items():
            setattr(distribucion, campo, valor)
        distribucion.save()
    else:
        distribucion = DistribucionCobro.objects.create(reserva=reserva, **valores)
    if estado not in ("pendiente", "autorizacion_pendiente"):
        return distribucion
    if distribucion.importe_financiador > 0 and not pendiente_autorizacion and not resolucion_autorizacion:
        financiador = reserva.afiliado.financiador
        distribucion.obligacion_financiador = _obligacion(reserva, "financiador", distribucion.importe_financiador, financiador.nombre, f"financiador:{financiador.pk}")
    if distribucion.importe_paciente > 0 and reserva.aceptacion.get("importe") == dato["importe_paciente"] and reserva.hecho.ciudadano_id:
        ciudadano = reserva.hecho.ciudadano
        distribucion.obligacion_paciente = _obligacion(reserva, "paciente", distribucion.importe_paciente, f"{ciudadano.nombre} {ciudadano.apellido}".strip(), f"ciudadano:{ciudadano.pk}")
    if not pendiente_autorizacion and (distribucion.importe_paciente == 0 or distribucion.obligacion_paciente_id):
        distribucion.estado = "resuelta"
    distribucion.save()
    return distribucion


@transaction.atomic
def resolver_saldo(*, reserva, usuario, decision, importe, motivo, evidencia="", clave, parte="paciente"):
    if not reserva.hecho_id:
        raise ValidationError("La resolución corresponde a una prestación realizada.")
    hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=reserva.hecho_id)
    requerir_hospital(usuario, hecho.institucion_id, "resolver_cobertura", hecho.area_origen_id, reserva.evaluacion.get("sensible", True))
    distribucion = DistribucionCobro.objects.select_for_update().get(reserva=reserva)
    clave = UUID(str(clave))
    previa = ResolucionSaldo.objects.filter(clave=clave).first()
    if previa:
        if (previa.distribucion_id, previa.decision, previa.importe, previa.motivo, previa.evidencia, previa.parte) != (distribucion.pk, decision, importe, motivo, evidencia, parte):
            raise ValidationError("La clave ya identifica otra resolución.")
        return previa
    resolver_autorizacion = parte == "financiador" and distribucion.estado == "autorizacion_pendiente"
    saldo = distribucion.importe_financiador if resolver_autorizacion else distribucion.importe_paciente
    if parte not in ("paciente", "financiador") or (parte == "financiador" and not resolver_autorizacion):
        raise ValidationError("Elegí un saldo pendiente de responsabilidad para esta prestación.")
    if (not resolver_autorizacion and distribucion.estado != "pendiente") or importe != saldo or importe <= 0:
        raise ValidationError("Se resuelve el saldo completo pendiente, conservando los cargos previos.")
    if decision not in ["asumir", "rechazar", "paciente", "financiador"] or not motivo.strip():
        raise ValidationError("Elegí la decisión y registrá su motivo.")
    if decision in ["paciente", "financiador"] and not evidencia.strip():
        raise ValidationError("Registrá el respaldo documental de la aceptación expresa para esta prestación e importe.")
    resolucion = ResolucionSaldo.objects.create(distribucion=distribucion, decision=decision, importe=importe, motivo=motivo, evidencia=evidencia, clave=clave, registrado_por=usuario, parte=parte)
    if decision in ["paciente", "financiador"]:
        sujeto = hecho.ciudadano if decision == "paciente" else reserva.afiliado.financiador if reserva.afiliado_id else None
        if not sujeto:
            raise ValidationError("No existe un responsable identificado para esta aceptación.")
        nombre = f"{sujeto.nombre} {getattr(sujeto, 'apellido', '')}".strip()
        clave_parte = "financiador" if resolver_autorizacion and decision == "financiador" else f"resolucion:{resolucion.pk}"
        resolucion.obligacion = _obligacion(reserva, clave_parte, importe, nombre, f"{decision}:{sujeto.pk}")
        resolucion.save(update_fields=["obligacion"])
        if resolver_autorizacion and decision == "financiador":
            distribucion.obligacion_financiador = resolucion.obligacion
    if decision != "rechazar":
        distribucion.estado = "pendiente" if resolver_autorizacion and distribucion.importe_paciente > 0 and not distribucion.obligacion_paciente_id else "resuelta"
        distribucion.save(update_fields=["estado", "obligacion_financiador"])
    auditar(usuario, "resolver_saldo", resolucion.pk, institucion=hecho.institucion, motivo=motivo)
    return resolucion


@transaction.atomic
def completar_pendiente(*, reserva, usuario, motivo, arancel=None, afiliado=None, particular=False):
    """Completa sólo datos pendientes. Nunca cambia obligaciones ni aceptaciones emitidas."""
    from apps.registros.models import normalizar_documento
    hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=reserva.hecho_id)
    requerir_hospital(usuario, hecho.institucion_id, "resolver_cobertura", hecho.area_origen_id, reserva.evaluacion.get("sensible", True))
    if not motivo.strip():
        raise ValidationError("Registrá el motivo de la revisión administrativa.")
    distribucion = DistribucionCobro.objects.select_for_update().get(reserva=reserva)
    if distribucion.estado not in ["arancel_pendiente", "evaluacion_pendiente"] or distribucion.obligacion_financiador_id or distribucion.obligacion_paciente_id:
        raise ValidationError("Sólo se completan datos pendientes sin cargos emitidos.")
    ids = {a for a in [reserva.afiliado_id, getattr(afiliado, "pk", None)] if a}
    list(Afiliado.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    reserva = ReservaCobertura.objects.select_for_update().get(pk=reserva.pk)
    seleccion = reserva.afiliacion
    if particular or afiliado:
        if particular and afiliado:
            raise ValidationError("Elegí afiliado o atención particular.")
        if afiliado:
            if not hecho.ciudadano_id or normalizar_documento(hecho.ciudadano.documento) != afiliado.documento or not Convenio.objects.filter(financiador=afiliado.financiador, institucion=hecho.institucion, estado="activo").exists():
                raise ValidationError("La afiliación requiere documento coincidente y convenio activo.")
        seleccion = AfiliacionCaso.objects.create(caso=reserva.caso, afiliado=afiliado, plan=afiliado.plan if afiliado else None, estado="verificada" if afiliado else "particular", hecho_revision=hecho, motivo=motivo, registrado_por=usuario)
    evaluacion = evaluar(caso=reserva.caso, prestacion=reserva.prestacion, fecha=reserva.fecha, cantidad=reserva.cantidad, afiliacion=seleccion, excluir=reserva.pk, corte=hecho.ocurrida_en, historico=True, nodo_origen_id=hecho.nodo_origen_id)
    if seleccion.pk == reserva.afiliacion_id and reserva.evaluacion["estado"] == "arancel_pendiente":
        evaluacion["cubiertas"] = reserva.cubiertas
        # El compromiso conservado por Q01 también conserva la exigencia de
        # autorización: el consumo tardío no puede convertirla en opcional.
        from .models import ReglaCobertura
        from .uso_autorizaciones import agregar_evaluacion
        agregar_evaluacion(evaluacion, caso=reserva.caso, afiliacion=seleccion,
            regla=ReglaCobertura.objects.filter(pk=evaluacion.get("regla")).first(),
            fecha=reserva.fecha, corte=hecho.ocurrida_en, excluir=reserva.pk,
            historico=True, intento=reserva.evaluacion.get("intento_autorizacion"))
    if arancel is not None:
        requerir_hospital(usuario, hecho.institucion_id, "configurar_cobros", sensible=reserva.evaluacion.get("sensible", True))
        if arancel <= 0:
            raise ValidationError("El arancel debe ser mayor a cero.")
        if not evaluacion["cobrar"] and evaluacion["politica"]:
            raise ValidationError("El hecho no tiene una decisión de cobro. No se activa retroactivamente desde un pendiente.")
        if not evaluacion["politica"] and seleccion.estado != "pendiente":
            evaluacion.update(cobrar=True, estado="arancel_pendiente")
        total = (arancel*reserva.cantidad).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total > Decimal("999999999999.99"):
            raise ValidationError("El importe total supera el máximo admitido por Finanzas.")
        parte = (arancel*evaluacion["cubiertas"]*Decimal(evaluacion["porcentaje"])/100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        evaluacion.update(arancel=str(arancel), importe_total=str(total), importe_financiador=str(parte), importe_paciente=str(total-parte))
        if evaluacion["estado"] == "arancel_pendiente":
            evaluacion.update(estado="parcial" if parte else "no_cubierta", motivo="Arancel completado mediante revisión administrativa")
    if evaluacion["estado"] in ["pendiente_evaluacion", "arancel_pendiente"]:
        raise ValidationError(evaluacion["motivo"])
    evaluacion["evaluacion_original"] = reserva.evaluacion
    evaluacion["revision"] = {"usuario": usuario.pk, "fecha": timezone.now().isoformat(), "motivo": motivo}
    reserva.evaluacion, reserva.aceptacion = evaluacion, {}
    reserva.afiliacion, reserva.afiliado, reserva.cubiertas = seleccion, seleccion.afiliado, evaluacion["cubiertas"]
    reserva.save(update_fields=["evaluacion", "aceptacion", "afiliacion", "afiliado", "cubiertas"])
    from .uso_autorizaciones import registrar_uso
    registrar_uso(reserva, consumir=True)
    auditar(usuario, "completar_cobertura", reserva.pk, institucion=hecho.institucion, motivo=motivo)
    return distribuir(reserva, completar=True)


@transaction.atomic
def revisar_contexto(*, hecho, usuario, motivo, afiliacion, prestaciones):
    hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho.pk)
    requerir_hospital(usuario, hecho.institucion_id, "resolver_cobertura", hecho.area_origen_id, sensible=True)
    if not hecho.cobertura_contexto.get("pendiente") or not motivo.strip():
        raise ValidationError("Sólo corresponde revisar un contexto pendiente, con motivo explícito.")
    if afiliacion and (afiliacion.caso_id != hecho.caso_origen_id or afiliacion.creado > hecho.ocurrida_en):
        raise ValidationError("Elegí una afiliación registrada para el caso antes del hecho.")
    if not prestaciones or any(p.institucion_id != hecho.institucion_id or p.nodo_id != hecho.nodo_origen_id for p in prestaciones):
        raise ValidationError("Elegí las prestaciones del hospital y nodo originales.")
    contexto = {"afiliacion": afiliacion.pk if afiliacion else None, "prestaciones": sorted(p.pk for p in prestaciones), "reservas": list(ReservaCobertura.objects.filter(caso_id=hecho.caso_origen_id, prestacion__in=prestaciones, creado__lte=hecho.ocurrida_en, estado="reservada").values_list("pk", flat=True))}
    anterior, creado = RevisionContexto.objects.get_or_create(hecho=hecho, defaults={"contexto": contexto, "motivo": motivo, "registrado_por": usuario})
    if not creado and anterior.contexto != contexto:
        raise ValidationError("El contexto ya fue revisado con otra selección.")
    from apps.finanzas.cobros import capturar_cobros_atencion
    resultado = capturar_cobros_atencion(hecho.pk)
    auditar(usuario, "revisar_contexto", anterior.pk, institucion=hecho.institucion, motivo=motivo)
    return resultado
