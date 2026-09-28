"""Qué encuentra cada usuario de la carga al entrar: su perfil y su trabajo pendiente.

Es el resumen que imprime `seed_entorno_demo` y lo que verifica su test: cada
rol que opera tiene algo que hacer, y cada rol de consulta tiene algo que ver.

Los conteos usan los mismos criterios que las pantallas —los grupos operativos
del motor de casos, el alcance de cada permiso financiero, los estados
abiertos—, pero no las reemplazan: son una guía para recorrer la demo, no una
segunda implementación de las bandejas.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.agenda.models import Turno
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, ItemFila
from apps.casos.motor import areas_que_supervisa, grupos_operativos_de
from apps.finanzas.models import AjusteGasto, Gasto, MovimientoDinero, ObligacionFinanciera, PendienteCosteo
from apps.finanzas.models_cobros import PendienteCobro
from apps.finanzas.permisos import alcance_financiero_q, tiene_concesion_financiera
from apps.financiadores import models as fin
from apps.financiadores.autorizaciones import casos_permitidos
from apps.instituciones.models import Institucion
from apps.red.models import Traslado

R = Membresia.Rol
# Roles que no operan: su «trabajo» es consultar.
ROLES_DE_CONSULTA = {R.PLATAFORMA, R.AUDITOR, R.REPORTES, R.CONFIGURADOR}
ROLES_CLINICOS = {R.MEDICO, R.ENFERMERIA, R.JEFE_AREA, R.ADMINISTRATIVO, R.ADMIN_INSTITUCION}
# Quién decide un traslado entrante y quién despacha uno saliente.
RESPONDEN_TRASLADOS = {R.ADMIN_INSTITUCION, R.JEFE_AREA}
DESPACHAN_TRASLADOS = {R.ADMIN_INSTITUCION, R.JEFE_AREA, R.ADMINISTRATIVO}
# Conteos que son datos para mirar y no trabajo por hacer. El test exige que
# cada perfil que opera tenga al menos un conteo que NO esté acá.
INFORMATIVOS = {
    "instituciones", "accesos registrados", "casos activos en la institución", "flujos publicados",
    "autorizaciones visibles", "afiliados en el padrón", "convenios propuestos esperando al hospital",
}


def _activos():
    return Caso.objects.exclude(estado__in=Caso.ESTADOS_FINALIZADOS)


def _en_alcance(qs, usuario, accion, institucion_path, area_path):
    """Filas que el permiso `accion` le deja ver al usuario, como en Finanzas."""
    alcance = alcance_financiero_q(usuario, accion, institucion_path=institucion_path,
                                   area_path=area_path, sensible_path=None)
    return qs.filter(alcance).distinct().count()


def _clinico(usuario, membresia, inst, t):
    areas = list(membresia.areas.values_list("pk", flat=True))
    grupos = grupos_operativos_de(usuario, inst.pk)
    t["casos en sus grupos"] = _activos().filter(institucion=inst, nodo_actual__grupos__in=grupos).distinct().count()
    t["casos asignados"] = _activos().filter(institucion=inst, asignado_a=usuario).count()
    t["pacientes en fila"] = ItemFila.objects.filter(
        caso__institucion=inst, atendido=False, box__isnull=True, nodo__grupos__in=grupos,
    ).distinct().count()
    if membresia.rol == R.JEFE_AREA:
        t["casos a supervisar"] = _activos().filter(area_actual_id__in=areas_que_supervisa(usuario)).count()
    if membresia.rol == R.ADMINISTRATIVO and areas:
        # La semana y no sólo hoy: una agenda que no atiende hoy igual tiene
        # turnos de los próximos días que confirmar.
        ahora = timezone.now()
        t["turnos de la semana sin confirmar"] = Turno.objects.filter(
            agenda__institucion=inst, agenda__area_id__in=areas, estado="reservado",
            inicio__gte=ahora, inicio__lt=ahora + timedelta(days=7),
        ).count()
    if membresia.rol in RESPONDEN_TRASLADOS:
        t["traslados por responder"] = Traslado.objects.filter(destino=inst, estado="solicitado").count()
    if membresia.rol in DESPACHAN_TRASLADOS:
        t["traslados por despachar"] = Traslado.objects.filter(origen=inst, estado="aceptado").count()
    t["autorizaciones observadas"] = fin.SolicitudAutorizacion.objects.filter(
        institucion=inst, estado="observada", caso__in=casos_permitidos(usuario)).count()


def _finanzas(usuario, inst, t):
    delimitar = Q(institucion=inst)
    t["gastos por aprobar"] = _en_alcance(
        Gasto.objects.filter(delimitar, estado="pendiente_aprobacion"), usuario, "aprobar_gastos",
        "institucion_id", "area_id")
    t["ajustes de gasto por aprobar"] = _en_alcance(
        AjusteGasto.objects.filter(gasto__institucion=inst, estado="pendiente_aprobacion"), usuario, "aprobar_gastos",
        "gasto__institucion_id", "gasto__area_id")
    t["pagos y cobros por aprobar"] = _en_alcance(
        MovimientoDinero.objects.filter(delimitar, estado="pendiente_aprobacion"), usuario, "aprobar_dinero",
        "institucion_id", "obligacion__area_id")
    t["atenciones sin responsable de pago"] = _en_alcance(
        PendienteCobro.objects.filter(delimitar, obligacion__isnull=True), usuario, "registrar_dinero",
        "institucion_id", "area_id")
    t["saldos de cobertura por decidir"] = _en_alcance(
        fin.DistribucionCobro.objects.filter(reserva__caso__institucion=inst,
                                             estado__in=["pendiente", "autorizacion_pendiente"]),
        usuario, "resolver_cobertura", "reserva__caso__institucion_id", "reserva__caso__area_actual_id")
    t["costos sin valor vigente"] = _en_alcance(
        PendienteCosteo.objects.filter(hecho__institucion=inst, resuelto=False, motivo="sin_valor"),
        usuario, "configurar_componentes", "hecho__institucion_id", "hecho__area_id")
    if tiene_concesion_financiera(usuario, "configurar_cobros", inst.pk):
        t["convenios por aceptar"] = fin.Convenio.objects.filter(
            institucion=inst, estado="propuesto", propuesto_por="financiador").count()


def _hospital(usuario, membresia):
    inst = membresia.institucion
    t = {}
    if membresia.rol in ROLES_CLINICOS:
        _clinico(usuario, membresia, inst, t)
    _finanzas(usuario, inst, t)
    if membresia.rol == R.AUDITOR:
        t["accesos registrados"] = AccesoClinico.objects.count()
    if membresia.rol == R.PLATAFORMA:
        t["instituciones"] = Institucion.objects.count()
    if membresia.rol == R.REPORTES:
        t["casos activos en la institución"] = _activos().filter(institucion=inst).count()
    if membresia.rol == R.CONFIGURADOR:
        t["flujos publicados"] = inst.flujos.filter(versiones__estado="publicada").distinct().count()
    return {k: v for k, v in t.items() if v}


def _financiador(membresia):
    f = membresia.financiador
    t = {}
    if membresia.resuelve_autorizaciones and membresia.rol in ("admin", "operador"):
        t["autorizaciones por responder"] = fin.SolicitudAutorizacion.objects.filter(
            financiador=f, estado="pendiente", plazo_respuesta__gt=timezone.now()).count()
    if membresia.rol in ("admin", "operador"):
        # Lo que el financiador todavía no liquidó: el mes en curso queda
        # adeudado a propósito (ver `seed_financiadores._pagos`).
        t["cargos sin liquidar"] = ObligacionFinanciera.objects.filter(
            tipo="cobrar", contraparte_referencia=f"financiador:{f.pk}",
        ).exclude(movimientos__estado="aprobado").count()
    t["autorizaciones visibles"] = fin.SolicitudAutorizacion.objects.filter(financiador=f).count()
    t["afiliados en el padrón"] = fin.Afiliado.objects.filter(financiador=f).count()
    t["convenios propuestos esperando al hospital"] = fin.Convenio.objects.filter(
        financiador=f, estado="propuesto", propuesto_por="financiador").count()
    return {k: v for k, v in t.items() if v}


def trabajo_por_usuario():
    """Una fila por usuario y perfil (membresía de hospital o de financiador)."""
    filas = []
    for usuario in Usuario.objects.filter(is_active=True).order_by("email"):
        if usuario.is_superuser:
            filas.append({"email": usuario.email, "perfil": "superusuario", "donde": "toda la plataforma",
                          "consulta": True, "trabajo": {"instituciones": Institucion.objects.count()}})
        for membresia in (Membresia.objects.filter(usuario=usuario, activo=True)
                          .select_related("institucion").order_by("institucion_id", "rol")):
            filas.append({"email": usuario.email, "perfil": membresia.rol, "donde": membresia.institucion.nombre,
                          "consulta": membresia.rol in ROLES_DE_CONSULTA, "trabajo": _hospital(usuario, membresia)})
        for membresia in (fin.MembresiaFinanciador.objects.filter(usuario=usuario, activo=True)
                          .select_related("financiador").order_by("financiador_id")):
            # Sin convenio activo todavía no hay nada que responder ni liquidar:
            # la prepaga recién llegada se mira, no se opera.
            sin_convenio = not fin.Convenio.objects.filter(financiador=membresia.financiador, estado="activo").exists()
            filas.append({"email": usuario.email, "perfil": f"financiador · {membresia.rol}",
                          "donde": membresia.financiador.nombre,
                          "consulta": membresia.rol == "auditor" or sin_convenio,
                          "trabajo": _financiador(membresia)})
    return filas
