"""Comprobación operativa de configuración, sin habilitar ni completar datos."""
from collections import Counter
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone

from apps.finanzas.models import ConcesionFinanciera, Prestacion
from apps.instituciones.models import Institucion
from .cobertura import arancel_aplicable, regla_aplicable
from .models import (
    Afiliado, ConfiguracionHospital, Convenio, Financiador, MembresiaFinanciador,
    Plan, ReservaCobertura, VinculoPrestacion,
)
from .permisos import puede_resolver_autorizaciones
from .vigencias import convenios_vigentes


ACCIONES_OPERATIVAS = (
    "ver_dinero", "registrar_dinero", "aprobar_dinero", "corregir_dinero",
    "registrar_aceptacion", "resolver_cobertura",
)


def verificar_preparacion(*, institucion_id, financiadores=None, usuarios=None, corte=None):
    """Un resultado completo acredita configuración comprobable, no aceptación.

    Sin una lista de financiadores se revisan los convenios activos o propuestos
    del hospital. Las concesiones explícitas son las designaciones existentes;
    usuarios permite limitar el ensayo a los responsables elegidos para el piloto.
    """
    institucion = Institucion.objects.filter(pk=institucion_id).first()
    if not institucion:
        raise ValidationError("La institución indicada no existe.")
    corte = corte or timezone.now()
    fecha = timezone.localdate(corte)
    hallazgos = {}

    def registrar(codigo, nivel, detalle, **referencias):
        registro = hallazgos.setdefault(codigo, {
            "codigo": codigo, "nivel": nivel, "detalle": detalle, "cantidad": 0, "ejemplos": [],
        })
        registro["cantidad"] += 1
        if referencias and len(registro["ejemplos"]) < 20:
            registro["ejemplos"].append(referencias)

    activo = ConfiguracionHospital.objects.filter(institucion_id=institucion_id, activo=True).exists()
    if not activo:
        registrar("circuito_desactivado", "informacion", "El circuito sigue desactivado. Este comando no lo habilita.")
    if not institucion.activa or institucion.estado != "activa":
        registrar("institucion_inactiva", "error", "La institución no está activa para iniciar el piloto.")
    ids = set(financiadores if financiadores is not None else Convenio.objects.filter(
        institucion_id=institucion_id, estado__in=["activo", "propuesto"],
    ).values_list("financiador_id", flat=True))
    organizaciones = list(Financiador.objects.filter(pk__in=ids).order_by("pk"))
    if len(organizaciones) != len(ids):
        raise ValidationError("Algún financiador indicado no existe.")
    if not organizaciones:
        registrar("sin_financiadores", "error", "Indicá los financiadores del piloto o registrá sus convenios.")
    convenios = {
        c.financiador_id: c for c in convenios_vigentes(corte).filter(
            institucion_id=institucion_id, financiador_id__in=ids, estado="activo",
        ).order_by("pk")
    }
    prestaciones = list(Prestacion.objects.filter(institucion_id=institucion_id, activo=True).select_related(
        "nodo__version__flujo",
    ).order_by("pk"))
    vinculos = {
        v.prestacion_id: v.comun for v in VinculoPrestacion.objects.filter(
            prestacion__institucion_id=institucion_id, prestacion__activo=True,
        ).select_related("comun").order_by("pk")
    }
    if not prestaciones:
        registrar("sin_prestaciones", "error", "No hay prestaciones hospitalarias activas para ensayar.")
    scopes = set()
    for prestacion in prestaciones:
        if not prestacion.nodo_id or prestacion.nodo.version.flujo.institucion_id != institucion_id:
            registrar("prestacion_sin_nodo_valido", "error", "Una prestación activa no tiene un paso del hospital.", prestacion=prestacion.pk)
        comun = vinculos.get(prestacion.pk)
        if not comun or not comun.activo:
            registrar("equivalencia_ausente_o_inactiva", "error", "Vinculá cada prestación activa a una prestación común activa.", prestacion=prestacion.pk)
        politica, _, arancel = arancel_aplicable(prestacion=prestacion, convenio=None, fecha=fecha, corte=corte)
        if not politica:
            registrar("politica_cobro_ausente", "error", "Falta una política de cobro vigente del paso actual.", prestacion=prestacion.pk)
        elif politica.cobrar and arancel is None:
            registrar("arancel_general_pendiente", "advertencia", "Falta arancel general; una excepción sólo resuelve el convenio que la tiene.", prestacion=prestacion.pk)
        elif not politica.cobrar:
            registrar("prestacion_sin_cobro", "informacion", "La política indica no cobrar; el verificador conserva esa decisión.", prestacion=prestacion.pk)
        area = prestacion.nodo.version.flujo.area_id if prestacion.nodo_id else None
        scopes.add((area, bool(politica and politica.sensible)))
    totales = Counter(prestaciones=len(prestaciones), financiadores=len(organizaciones))
    reglas_revisadas = set()
    for financiador in organizaciones:
        if not financiador.activo:
            registrar("financiador_inactivo", "error", "El financiador indicado no está activo.", financiador=financiador.pk)
        convenio = convenios.get(financiador.pk)
        if not convenio:
            registrar("convenio_no_vigente", "error", "Falta un convenio activo y aceptado para el hospital.", financiador=financiador.pk)
        miembros = MembresiaFinanciador.objects.filter(
            financiador=financiador, activo=True, usuario__is_active=True,
        )
        if not miembros.filter(rol="admin").exists():
            registrar("sin_administrador_financiador", "error", "Designá una cuenta activa que administre la parametría del financiador.", financiador=financiador.pk)
        requiere_autorizacion = False
        padron = Afiliado.objects.filter(financiador=financiador, finalizado_en=None, desde__lte=fecha)
        cantidad = padron.count()
        totales["afiliaciones_vigentes"] += cantidad
        if not cantidad:
            registrar("padron_sin_vigentes", "error", "Cargá padrón confirmado con el importador existente antes del ensayo.", financiador=financiador.pk)
        invalidas = padron.exclude(plan=None).filter(Q(plan__activo=False) | ~Q(plan__financiador_id=F("financiador_id"))).count()
        if invalidas:
            registrar("padron_plan_invalido", "error", "Hay afiliaciones vigentes con plan inactivo o de otro financiador.", financiador=financiador.pk, afiliaciones=invalidas)
        planes = list(Plan.objects.filter(financiador=financiador, activo=True).order_by("pk"))
        totales["planes_activos"] += len(planes)
        if not planes:
            registrar("sin_planes", "advertencia", "No hay planes activos; sólo se evaluarán reglas generales para afiliación sin plan.", financiador=financiador.pk)
        planes_ids = [p.pk for p in planes]
        if not planes_ids or padron.filter(plan=None).exists():
            planes_ids.append(None)
        for prestacion in prestaciones:
            comun = vinculos.get(prestacion.pk)
            if not comun or not comun.activo:
                continue
            politica, _, arancel = arancel_aplicable(prestacion=prestacion, convenio=convenio, fecha=fecha, corte=corte)
            if politica and politica.cobrar and arancel is None:
                registrar("arancel_pendiente", "error", "La prestación no tiene importe general ni excepción aplicable al convenio.", financiador=financiador.pk, prestacion=prestacion.pk)
            for plan_id in planes_ids:
                clave = (financiador.pk, plan_id, comun.pk)
                if clave in reglas_revisadas:
                    continue
                reglas_revisadas.add(clave)
                afiliacion = SimpleNamespace(afiliado=SimpleNamespace(financiador=financiador), plan_id=plan_id)
                regla = regla_aplicable(afiliacion, comun, fecha, corte)
                requiere_autorizacion = requiere_autorizacion or bool(regla and regla.requiere_autorizacion)
                if not regla and (not convenio or convenio.porcentaje_default is None):
                    registrar("sin_regla_aplicable", "advertencia", "La combinación se evaluará como no cubierta; confirmar que sea intencional.", financiador=financiador.pk, plan=plan_id, prestacion_comun=comun.pk)
        if requiere_autorizacion and not any(
            puede_resolver_autorizaciones(m.usuario, financiador.pk)
            for m in miembros.filter(resuelve_autorizaciones=True).select_related("usuario")
        ):
            registrar("sin_resolutor_autorizaciones", "error", "Hay reglas que exigen autorización y falta una designación activa para resolverlas.", financiador=financiador.pk)
    concesiones = ConcesionFinanciera.objects.filter(
        membresia__institucion_id=institucion_id, membresia__activo=True,
        membresia__usuario__is_active=True, membresia__usuario__is_superuser=False,
    )
    if usuarios is not None:
        concesiones = concesiones.filter(membresia__usuario_id__in=usuarios)
    permisos = list(concesiones.prefetch_related("areas").order_by("pk"))

    def tiene_responsable(accion, area, sensible):
        return any(
            p.accion == accion and (not sensible or p.permite_sensibles)
            and (p.todas_las_areas or (area is not None and any(a.pk == area for a in p.areas.all())))
            for p in permisos
        )

    if not tiene_responsable("configurar_cobros", None, any(s for _, s in scopes)):
        registrar("sin_responsable_configuracion", "error", "Falta una concesión explícita institucional para configurar cobros, con el alcance sensible necesario.")
    for area, sensible in sorted(scopes or {(None, False)}, key=lambda s: (s[0] or 0, s[1])):
        for accion in ACCIONES_OPERATIVAS:
            if not tiene_responsable(accion, area, sensible):
                registrar("sin_responsable_operativo", "error", "Falta una persona activa con concesión explícita para el área y sensibilidad indicadas.", accion=accion, area=area, sensible=sensible)
    totales["reservas_abiertas"] = ReservaCobertura.objects.filter(caso__institucion_id=institucion_id, estado="reservada").count()
    if totales["reservas_abiertas"]:
        registrar("reservas_por_conservar", "informacion", "Hay reservas abiertas: desactivar no las libera ni permite asumir que no hubo atención.", cantidad=totales["reservas_abiertas"])
    resultado = sorted(hallazgos.values(), key=lambda h: ({"error": 0, "advertencia": 1, "informacion": 2}[h["nivel"]], h["codigo"]))
    return {
        "institucion": institucion_id, "generado_en": corte.isoformat(), "criterio": "preparacion_financiadores_v1",
        "solo_lectura": True, "circuito_activo": activo,
        "configuracion_completa": not any(h["nivel"] == "error" for h in resultado),
        "requiere_revision_operativa": True, "totales": dict(totales), "hallazgos": resultado,
    }
