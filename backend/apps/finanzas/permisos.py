"""Verificación de permisos financieros sin ampliar las capacidades clínicas."""
from django.db.models import Q

from apps.accounts.models import Membresia

from .models import ConcesionFinanciera


def concesiones_financieras_de(usuario, accion, sensible=False):
    """Consulta base de concesiones activas para una acción financiera."""
    if not (getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False) and not usuario.is_superuser):
        return ConcesionFinanciera.objects.none()

    concesiones = ConcesionFinanciera.objects.filter(
        membresia__usuario=usuario,
        membresia__activo=True,
        accion=accion,
    )
    if sensible:
        concesiones = concesiones.filter(permite_sensibles=True)
    return concesiones


# El rol no firma ni se audita a sí mismo.
#
# La herencia del admin de institución viene de
# `docs/plans/2026-09-18-finanzas-coberturas-usabilidad-diseno.md` y resuelve un
# problema real: que configurar un hospital no obligue a duplicar concesiones.
# Alcanza para ver, registrar, corregir y configurar en toda la institución,
# incluida la información sensible.
#
# Aprobar es otra cosa. Es el control de cuatro ojos sobre el dinero: si el
# mismo rol registra y aprueba, el control no existe. Y auditar los accesos
# propios vacía de sentido al registro de accesos, que está para decir quién
# miró qué. Estas cuatro se conceden de forma explícita a una persona distinta,
# o no se tienen.
ACCIONES_SIN_HERENCIA = (
    ConcesionFinanciera.Accion.APROBAR_COSTOS,
    ConcesionFinanciera.Accion.APROBAR_GASTOS,
    ConcesionFinanciera.Accion.APROBAR_DINERO,
    ConcesionFinanciera.Accion.AUDITAR_FINANZAS,
)
ACCIONES_ADMIN = tuple(
    accion for accion in ConcesionFinanciera.Accion.values if accion not in ACCIONES_SIN_HERENCIA
)


def instituciones_admin_financiero(usuario, accion):
    """Alcance financiero total del administrador institucional, sin filas derivadas."""
    if not (getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False)) or accion not in ACCIONES_ADMIN:
        return Membresia.objects.none().values_list("institucion_id", flat=True)
    return Membresia.objects.filter(
        usuario=usuario, activo=True, rol=Membresia.Rol.ADMIN_INSTITUCION,
    ).values_list("institucion_id", flat=True)


def tiene_accion_financiera(usuario, accion):
    if not (getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False)):
        return False
    return usuario.is_superuser or instituciones_admin_financiero(usuario, accion).exists() or concesiones_financieras_de(usuario, accion).exists()


def alcance_financiero_q(usuario, accion, *, institucion_path="institucion_id", area_path="area_id", sensible_path="sensible"):
    """Predicado común: misma institución/área, sin mezclar acciones o membresías."""
    if getattr(usuario, "is_active", False) and getattr(usuario, "is_superuser", False):
        return Q()
    alcance = Q(**{f"{institucion_path}__in": instituciones_admin_financiero(usuario, accion)})
    for institucion_id, todas, area_id, sensibles in concesiones_financieras_de(usuario, accion).values_list(
        "membresia__institucion_id", "todas_las_areas", "areas__id", "permite_sensibles",
    ):
        if not todas and area_id is None:
            continue
        scope = Q(**{institucion_path: institucion_id})
        if not todas:
            scope &= Q(**{area_path: area_id})
        if sensible_path and not sensibles:
            scope &= ~Q(**{sensible_path: True})
        alcance |= scope
    return alcance


def gastos_en_alcance_financiero(queryset, usuario, accion=ConcesionFinanciera.Accion.VER_GASTOS):
    return queryset.filter(alcance_financiero_q(usuario, accion)).distinct()


def concesiones_financieras_en_alcance(usuario, accion, institucion_id, area_id=None, sensible=False):
    """Devuelve las concesiones explícitas que alcanzan institución y área.

    El alcance se resuelve sobre la misma membresía que recibió la concesión;
    nunca se combinan áreas de otras membresías del usuario.
    """
    concesiones = concesiones_financieras_de(usuario, accion, sensible=sensible).filter(
        membresia__institucion_id=institucion_id,
    )
    if area_id is None:
        return concesiones.filter(todas_las_areas=True)
    return concesiones.filter(Q(todas_las_areas=True) | Q(areas__id=area_id)).distinct()


def tiene_concesion_financiera(usuario, accion, institucion_id, area_id=None, sensible=False):
    if not (getattr(usuario, "is_authenticated", False) and getattr(usuario, "is_active", False)):
        return False
    if getattr(usuario, "is_superuser", False):
        return True
    if instituciones_admin_financiero(usuario, accion).filter(institucion_id=institucion_id).exists():
        return True
    return concesiones_financieras_en_alcance(
        usuario,
        accion,
        institucion_id,
        area_id,
        sensible=sensible,
    ).exists()


def hechos_en_alcance_financiero(queryset, usuario):
    """Conserva el permiso de hecho completo también al consultar atribuciones."""
    if usuario.is_superuser and usuario.is_active:
        return queryset
    alcance = Q(institucion_id__in=instituciones_admin_financiero(usuario, ConcesionFinanciera.Accion.VER_COSTOS))
    for sensible in (False, True):
        concesiones = concesiones_financieras_de(
            usuario, ConcesionFinanciera.Accion.VER_COSTOS, sensible=sensible,
        )
        for institucion_id, todas, area_id in concesiones.values_list(
            "membresia__institucion_id", "todas_las_areas", "areas__id",
        ):
            if not todas and area_id is None:
                continue
            scope = Q(institucion_id=institucion_id)
            if not todas:
                scope &= Q(area_origen_id=area_id)
            if not sensible:
                scope &= ~Q(componentes_esperados__sensible=True)
                scope &= ~Q(
                    atribuciones_reparto__reparto__gasto__sensible=True,
                    atribuciones_reparto__reparto__reemplazado_por__isnull=True,
                )
            alcance |= scope
    return queryset.filter(alcance).distinct()
