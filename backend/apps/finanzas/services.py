import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Membresia

from .models import AjusteCosto, AjusteGasto, ComponenteEsperadoHecho, ConceptoGasto, ConcesionFinanciera, CorreccionSnapshotCosteo, DefinicionComponente, ExpectativaGasto, Gasto, HechoAtencionCosteable, ImputacionCosto, IndicacionCargaGasto, PendienteCosteo, Prestacion, ValorComponente
from .permisos import concesiones_financieras_en_alcance, tiene_concesion_financiera


logger = logging.getLogger(__name__)


def registrar_atencion_completada(caso, nodo, evento, autor=None):
    """Crea una vez el hecho económico para el evento clínico ya confirmado."""
    hecho, creado = HechoAtencionCosteable.objects.get_or_create(
        evento_origen_id=evento.id,
        defaults={
            "institucion": caso.institucion,
            "caso": caso,
            "caso_origen_id": caso.id,
            "ciudadano": caso.ciudadano,
            "ciudadano_origen_id": caso.ciudadano_id,
            "evento": evento,
            "nodo": nodo,
            "nodo_origen_id": nodo.id,
            "area": caso.area_actual,
            "area_origen_id": caso.area_actual_id,
            "autor": autor,
            "ocurrida_en": timezone.now(),
        },
    )
    if creado:
        try:
            # La captura de catálogo es financiera; un error suyo no debe
            # deshacer la atención ni el hecho durable recién creado.
            with transaction.atomic():
                _congelar_componentes(hecho)
        except Exception:  # noqa: BLE001 - el worker detecta el snapshot incompleto.
            logger.exception("No se pudieron congelar los componentes del hecho %s", hecho.id)
            try:
                with transaction.atomic():
                    _marcar_snapshot_incompleto(hecho)
            except Exception:  # noqa: BLE001 - el hecho sigue durable aunque la base falle por completo.
                logger.exception("No se pudo marcar el snapshot incompleto del hecho %s", hecho.id)
    return hecho


def _pendiente(hecho, motivo, componente=None):
    pendiente, _ = PendienteCosteo.objects.get_or_create(hecho=hecho, componente=componente, motivo=motivo)
    if pendiente.resuelto:
        pendiente.resuelto, pendiente.resuelto_en = False, None
        pendiente.save(update_fields=["resuelto", "resuelto_en"])
    return pendiente


def _resolver(hecho, motivo, componente=None):
    PendienteCosteo.objects.filter(hecho=hecho, componente=componente, motivo=motivo, resuelto=False).update(resuelto=True, resuelto_en=timezone.now())


def _marcar_snapshot_incompleto(hecho):
    """Evita reutilizar en silencio un catálogo modificado después del hecho."""
    _pendiente(hecho, PendienteCosteo.Motivo.SNAPSHOT_INCOMPLETO)
    HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(componentes_congelados=True)
    hecho.componentes_congelados = True


def _marcar_costeo_actualizado(hecho):
    """Anota una ejecución que pudo dejar un resultado completo o parcial."""
    actualizado_en = timezone.now()
    HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(
        ultimo_costeo_en=actualizado_en,
    )
    hecho.ultimo_costeo_en = actualizado_en


def _congelar_componentes(hecho):
    """Sella los componentes aplicables al momento de la atención."""
    prestaciones = Prestacion.objects.filter(
        institucion=hecho.institucion,
        nodo_id=hecho.nodo_origen_id,
        activo=True,
    )
    if not prestaciones.exists():
        _pendiente(hecho, PendienteCosteo.Motivo.SIN_PRESTACION)
    else:
        _resolver(hecho, PendienteCosteo.Motivo.SIN_PRESTACION)
        componentes = list(
            DefinicionComponente.objects.filter(
                prestacion__in=prestaciones,
                activo=True,
                fuente=DefinicionComponente.Fuente.ATENCION_DIRECTA,
            )
        )
        if not componentes:
            _pendiente(hecho, PendienteCosteo.Motivo.SIN_COMPONENTES)
        else:
            ComponenteEsperadoHecho.objects.bulk_create(
                [
                    ComponenteEsperadoHecho(
                        hecho=hecho,
                        componente=componente,
                        sensible=componente.sensible,
                        unidad=componente.unidad,
                        base_calculo=componente.base_calculo,
                    )
                    for componente in componentes
                ],
                ignore_conflicts=True,
            )
            _resolver(hecho, PendienteCosteo.Motivo.SIN_COMPONENTES)
    HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(componentes_congelados=True)
    hecho.componentes_congelados = True


def procesar_hecho_atencion(hecho_id):
    """Calcula sólo componentes directos disponibles; es seguro reintentarlo."""
    with transaction.atomic():
        hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        # Si el reproceso llegó a ejecutar, el fallo técnico anterior dejó de
        # ser el faltante vigente: puede quedar otro pendiente de datos, pero
        # no corresponde mostrar ambos como si el error siguiera activo.
        _resolver(hecho, PendienteCosteo.Motivo.ERROR_RECUPERABLE)
        if not hecho.componentes_congelados:
            _congelar_componentes(hecho)
        componentes = list(
            ComponenteEsperadoHecho.objects.filter(hecho=hecho).select_related("componente")
        )
        if not componentes:
            _marcar_costeo_actualizado(hecho)
            return hecho
        for esperado in componentes:
            componente = esperado.componente
            valor = ValorComponente.objects.filter(componente=componente, vigente_desde__lte=hecho.ocurrida_en).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gt=hecho.ocurrida_en)).order_by("-vigente_desde", "-id").first()
            if valor is None:
                _pendiente(hecho, PendienteCosteo.Motivo.SIN_VALOR, componente)
                continue
            try:
                ImputacionCosto.objects.get_or_create(
                    hecho=hecho,
                    componente=componente,
                    defaults={
                        "valor": valor,
                        "importe": valor.importe,
                        "unidad": esperado.unidad,
                        "base_calculo": esperado.base_calculo,
                        "moneda": valor.moneda,
                    },
                )
            except IntegrityError:
                pass
            _resolver(hecho, PendienteCosteo.Motivo.SIN_VALOR, componente)
        _marcar_costeo_actualizado(hecho)
        return hecho


def intentar_costeo_directo(hecho_id):
    """Intenta el costo local sin convertir una falla económica en clínica.

    Las fuentes pesadas o fallidas quedan para recuperación; la atención ya
    completada no se revierte ni se bloquea por ese trabajo.
    """
    try:
        procesar_hecho_atencion(hecho_id)
    except Exception:  # noqa: BLE001 - la recuperación posterior es deliberada.
        logger.exception("No se pudo costear de inmediato el hecho %s", hecho_id)
        try:
            registrar_error_recuperable(hecho_id)
        except Exception:  # noqa: BLE001 - el hecho durable sigue siendo recuperable.
            logger.exception("No se pudo marcar el error recuperable del hecho %s", hecho_id)
        return False
    return True


def registrar_error_recuperable(hecho_id):
    """Marca un fallo técnico bajo el mismo bloqueo del cálculo recuperable."""
    with transaction.atomic():
        hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        return _pendiente(hecho, PendienteCosteo.Motivo.ERROR_RECUPERABLE)


def corregir_snapshot_componentes(hecho_id, motivo, registrado_por):
    """Aplica catálogo actual sólo después de una decisión financiera trazable."""
    with transaction.atomic():
        hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        if not tiene_concesion_financiera(
            registrado_por,
            ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            hecho.institucion_id,
            hecho.area_origen_id,
            sensible=True,
        ):
            raise PermissionDenied("No tenés autorización para corregir este snapshot de costos.")
        pendiente = PendienteCosteo.objects.filter(
            hecho=hecho,
            motivo=PendienteCosteo.Motivo.SNAPSHOT_INCOMPLETO,
            resuelto=False,
        )
        if not pendiente.exists():
            raise ValidationError("El hecho no tiene un snapshot de componentes pendiente de corrección.")
        correccion = CorreccionSnapshotCosteo(
            hecho=hecho,
            motivo=motivo,
            registrado_por=registrado_por,
        )
        correccion.save()
        _congelar_componentes(hecho)
        _resolver(hecho, PendienteCosteo.Motivo.SNAPSHOT_INCOMPLETO)
    intentar_costeo_directo(hecho.id)
    return correccion


def registrar_ajuste_costo(imputacion, importe, motivo, registrado_por):
    """Corrige un importe histórico con un asiento nuevo y autorizado."""
    if not tiene_concesion_financiera(
        registrado_por,
        ConcesionFinanciera.Accion.CORREGIR_COSTOS,
        imputacion.hecho.institucion_id,
        imputacion.hecho.area_origen_id,
        sensible=True,
    ):
        raise PermissionDenied("No tenés autorización para corregir este costo.")
    ajuste = AjusteCosto(
        imputacion=imputacion,
        importe=importe,
        motivo=motivo,
        registrado_por=registrado_por,
    )
    try:
        ajuste.save()
    except ValidationError:
        raise
    return ajuste


def _concesiones_para_gasto(usuario, accion, institucion_id, area_id, sensible):
    return concesiones_financieras_en_alcance(
        usuario,
        accion,
        institucion_id,
        area_id,
        sensible=sensible,
    )


def registrar_gasto(concepto, institucion, area, importe, periodo_economico, registrado_por, reemplaza=None):
    """Registra una fuente central aprobada o una carga de área pendiente."""
    es_superusuario = getattr(registrado_por, "is_superuser", False)
    with transaction.atomic():
        concepto = ConceptoGasto.objects.select_for_update().get(pk=concepto.pk)
        concesiones = _concesiones_para_gasto(
            registrado_por,
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            institucion.id,
            getattr(area, "id", None),
            concepto.sensible,
        )
        if not es_superusuario and not concesiones.exists():
            raise PermissionDenied("No tenés autorización para registrar este gasto.")
        if reemplaza is not None:
            reemplaza = Gasto.objects.select_for_update().get(pk=reemplaza.pk)
            if not es_superusuario and not _concesiones_para_gasto(
                registrado_por,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
                reemplaza.institucion_id,
                reemplaza.area_id,
                reemplaza.sensible,
            ).exists():
                raise PermissionDenied("No tenés autorización sobre el gasto que querés reemplazar.")
            if reemplaza.estado == Gasto.Estado.APROBADO:
                raise ValidationError("Un gasto aprobado se corrige mediante un ajuste, no se reemplaza.")
            if Gasto.objects.filter(reemplaza=reemplaza).exists():
                raise ValidationError("El gasto ya tiene un reemplazo registrado.")

        es_central = es_superusuario or concesiones.filter(
            membresia__rol=Membresia.Rol.ADMIN_INSTITUCION,
        ).exists()
        datos = {
            "concepto": concepto,
            "institucion": institucion,
            "area": area,
            "importe": importe,
            "periodo_economico": periodo_economico,
            "origen": Gasto.Origen.CENTRAL if es_central else Gasto.Origen.AREA,
            "registrado_por": registrado_por,
            "reemplaza": reemplaza,
        }
        if es_central:
            datos.update(
                estado=Gasto.Estado.APROBADO,
                aprobado_por=registrado_por,
                aprobado_en=timezone.now(),
            )
        return Gasto.objects.create(**datos)


def aprobar_gasto(gasto_id, aprobado_por):
    """Aprueba una sola vez una carga de área; es seguro ante reintentos."""
    with transaction.atomic():
        gasto = Gasto.objects.select_for_update().get(pk=gasto_id)
        if not tiene_concesion_financiera(
            aprobado_por,
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            gasto.institucion_id,
            gasto.area_id,
            sensible=gasto.sensible,
        ):
            raise PermissionDenied("No tenés autorización para aprobar este gasto.")
        if gasto.estado == Gasto.Estado.APROBADO:
            return gasto
        if gasto.estado == Gasto.Estado.RECHAZADO:
            raise ValidationError("Un gasto rechazado no puede aprobarse.")
        if Gasto.objects.filter(reemplaza=gasto).exists():
            raise ValidationError("Un gasto reemplazado no puede aprobarse.")
        gasto.estado = Gasto.Estado.APROBADO
        gasto.aprobado_por = aprobado_por
        gasto.aprobado_en = timezone.now()
        gasto.save(update_fields=["estado", "aprobado_por", "aprobado_en"])
        return gasto


def rechazar_gasto(gasto_id, motivo, rechazado_por):
    """Rechaza una carga pendiente sin perder su importe ni autor originales."""
    with transaction.atomic():
        gasto = Gasto.objects.select_for_update().get(pk=gasto_id)
        if not tiene_concesion_financiera(
            rechazado_por,
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            gasto.institucion_id,
            gasto.area_id,
            sensible=gasto.sensible,
        ):
            raise PermissionDenied("No tenés autorización para rechazar este gasto.")
        if gasto.estado == Gasto.Estado.RECHAZADO:
            return gasto
        if gasto.estado == Gasto.Estado.APROBADO:
            raise ValidationError("Un gasto aprobado no puede rechazarse.")
        if Gasto.objects.filter(reemplaza=gasto).exists():
            raise ValidationError("Un gasto reemplazado no puede rechazarse.")
        gasto.estado = Gasto.Estado.RECHAZADO
        gasto.rechazado_por = rechazado_por
        gasto.rechazado_en = timezone.now()
        gasto.motivo_rechazo = motivo
        gasto.save(update_fields=["estado", "rechazado_por", "rechazado_en", "motivo_rechazo"])
        return gasto


def registrar_ajuste_gasto(gasto_id, importe, motivo, registrado_por):
    """Agrega una corrección histórica a un gasto aprobado y autorizado."""
    with transaction.atomic():
        gasto = Gasto.objects.select_for_update().get(pk=gasto_id)
        if not tiene_concesion_financiera(
            registrado_por,
            ConcesionFinanciera.Accion.CORREGIR_GASTOS,
            gasto.institucion_id,
            gasto.area_id,
            sensible=gasto.sensible,
        ):
            raise PermissionDenied("No tenés autorización para corregir este gasto.")
        ajuste = AjusteGasto(
            gasto=gasto,
            importe=importe,
            motivo=motivo,
            registrado_por=registrado_por,
        )
        ajuste.save()
        return ajuste


def indicar_carga_esperada(expectativa_id, periodo_economico, estado, registrado_por):
    """Agrega una indicación mensual, conservando las anteriores como historia."""
    with transaction.atomic():
        expectativa = ExpectativaGasto.objects.select_for_update().get(pk=expectativa_id)
        if not tiene_concesion_financiera(
            registrado_por,
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            expectativa.institucion_id,
            expectativa.area_id,
            sensible=expectativa.sensible,
        ):
            raise PermissionDenied("No tenés autorización para indicar la carga esperada.")
        indicacion = IndicacionCargaGasto(
            expectativa=expectativa,
            periodo_economico=periodo_economico,
            estado=estado,
            registrado_por=registrado_por,
        )
        indicacion.save()
        return indicacion
