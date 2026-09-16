"""Cobrar es una decisión administrativa explícita, nunca una derivación del costo."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import HechoAtencionCosteable, Prestacion
from .models_cobros import PendienteCobro, PoliticaCobro, SnapshotCobroAtencion
from .permisos import tiene_concesion_financiera


def registrar_politica_cobro(*, prestacion, registrado_por, **datos):
    with transaction.atomic():
        prestacion = Prestacion.objects.select_for_update().get(pk=prestacion.pk)
        sensible = datos.get("sensible", False) or PoliticaCobro.objects.filter(prestacion=prestacion, sensible=True).exists()
        if not tiene_concesion_financiera(registrado_por, "configurar_cobros", prestacion.institucion_id, sensible=sensible):
            raise PermissionDenied("No tenés permiso para configurar cobros en esta institución.")
        # Suspender un cobro existente no requiere reactivar el catálogo de
        # costos. La captura sigue usando versiones históricas, no activo hoy.
        suspende_existente = not datos.get("cobrar", False) and PoliticaCobro.objects.filter(prestacion=prestacion).exists()
        if not prestacion.nodo_id or (not prestacion.activo and not suspende_existente):
            raise ValidationError("Elegí una prestación activa vinculada a una atención.")
        # No se permiten fechas retroactivas. El instante de registro también
        # forma parte del corte histórico al capturar/recuperar una atención.
        desde = datos.get("vigente_desde")
        ahora = timezone.now()
        if desde is not None and desde < ahora:
            raise ValidationError({"vigente_desde": "Las nuevas versiones sólo se aplican a futuras atenciones."})
        datos["vigente_desde"] = desde or ahora
        datos["contraparte_nombre"] = datos.get("contraparte_nombre", "").strip()
        datos["contraparte_referencia"] = datos.get("contraparte_referencia", "").strip()
        return PoliticaCobro.objects.create(
            prestacion=prestacion, institucion=prestacion.institucion,
            nodo_origen_id=prestacion.nodo_id, nombre_prestacion=prestacion.nombre,
            registrado_por=registrado_por, **datos,
        )


def _crear_cargo(pendiente, usuario=None):
    if pendiente.obligacion_id or pendiente.importe is None or not pendiente.contraparte_nombre.strip():
        return pendiente
    from .dinero import crear_obligacion_cobro

    pendiente.obligacion = crear_obligacion_cobro(
        hecho=pendiente.hecho, importe=pendiente.importe,
        contraparte_nombre=pendiente.contraparte_nombre,
        contraparte_referencia=pendiente.contraparte_referencia,
        creado_por=usuario, clave=pendiente.clave, sensible=pendiente.sensible,
    )
    pendiente.resuelto_en = timezone.now()
    pendiente.resuelto_por = usuario
    pendiente.save(update_fields=["obligacion", "resuelto_en", "resuelto_por"])
    return pendiente


def capturar_cobros_atencion(hecho_id):
    """Recupera la captura desde el hecho durable, aunque su ancla haya fallado.

    Las políticas son inmutables y conservan nodo e institución originales.
    El doble corte vigencia/registro impide que una recuperación aplique
    reglas creadas después, incluso si alguien las insertó retroactivamente.
    """
    with transaction.atomic():
        # Orden común de bloqueos: hecho -> snapshot/pendiente -> obligación.
        # No bloquear filas de joins en un orden decidido por el plan de SQL.
        hecho = HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        snapshot, _ = SnapshotCobroAtencion.objects.select_for_update().get_or_create(hecho_id=hecho_id)
        if snapshot.capturado:
            return snapshot
        if hecho.cobertura_contexto:
            from apps.financiadores.cobros import capturar_cobertura
            capturar_cobertura(hecho)
            snapshot.capturado = True
            snapshot.save(update_fields=["capturado"])
            return snapshot
        politicas = PoliticaCobro.objects.filter(
            institucion_id=hecho.institucion_id,
            vigente_desde__lte=hecho.ocurrida_en, registrado__lte=hecho.ocurrida_en,
        ).order_by("prestacion_id", "-vigente_desde", "-id")
        vistos = set()
        # El hecho financiero no concede lectura de la historia clínica.
        sensible = not hecho.componentes_congelados or hecho.componentes_esperados.filter(sensible=True).exists()
        # Ante snapshot de costos incompleto, no presumir que es no sensible.
        sensible = sensible or hecho.pendientes.filter(motivo="snapshot_incompleto", resuelto=False).exists()
        for politica in politicas:
            if politica.prestacion_id in vistos:
                continue
            vistos.add(politica.prestacion_id)
            # Elegir versión antes de comparar nodo: mover una prestación no
            # debe resucitar su política anterior en el nodo viejo.
            if not politica.cobrar or politica.nodo_origen_id != hecho.nodo_origen_id:
                continue
            pendiente, _ = PendienteCobro.objects.get_or_create(
                hecho=hecho, prestacion_id=politica.prestacion_id,
                defaults={
                    "politica": politica, "institucion_id": hecho.institucion_id,
                    "area_id": hecho.area_origen_id, "sensible": sensible or politica.sensible,
                    "importe": politica.importe, "contraparte_nombre": politica.contraparte_nombre,
                    "contraparte_referencia": politica.contraparte_referencia,
                },
            )
            _crear_cargo(pendiente)
        snapshot.capturado = True
        snapshot.save(update_fields=["capturado"])
        return snapshot


def resolver_pendiente_cobro(pendiente_id, *, usuario, **datos):
    with transaction.atomic():
        hecho_id = PendienteCobro.objects.values_list("hecho_id", flat=True).get(pk=pendiente_id)
        HechoAtencionCosteable.objects.select_for_update().get(pk=hecho_id)
        pendiente = PendienteCobro.objects.select_for_update().get(pk=pendiente_id)
        if not tiene_concesion_financiera(usuario, "registrar_dinero", pendiente.institucion_id, pendiente.area_id, sensible=pendiente.sensible):
            raise PermissionDenied("No tenés permiso para completar este cargo.")
        for campo in ("importe", "contraparte_nombre", "contraparte_referencia"):
            if campo not in datos:
                continue
            valor = datos[campo].strip() if isinstance(datos[campo], str) else datos[campo]
            anterior = getattr(pendiente, campo)
            if anterior not in (None, "") and valor != anterior:
                raise ValidationError({campo: "Este dato ya fue definido y no puede reemplazarse desde un pendiente."})
            if pendiente.obligacion_id and valor != anterior:
                raise ValidationError("El cargo ya fue generado. No se modifican sus datos históricos.")
            setattr(pendiente, campo, valor)
        if pendiente.importe is None or pendiente.importe <= Decimal("0") or not pendiente.contraparte_nombre:
            raise ValidationError("Completá un arancel mayor a cero y el responsable del pago.")
        pendiente.full_clean()
        pendiente.save(update_fields=["importe", "contraparte_nombre", "contraparte_referencia"])
        return _crear_cargo(pendiente, usuario)


def recuperar_cobros_atencion(hecho_id, *, usuario):
    hecho = HechoAtencionCosteable.objects.get(pk=hecho_id)
    # Una captura fallida puede no tener aún sensibilidad; exigir alcance
    # sensible para recuperar, sin exponer importes de un alcance más amplio.
    if not tiene_concesion_financiera(usuario, "registrar_dinero", hecho.institucion_id, hecho.area_origen_id, sensible=True):
        raise PermissionDenied("No tenés permiso para recuperar los cobros de esta atención.")
    return capturar_cobros_atencion(hecho.pk)
