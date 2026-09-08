"""Verificación de permisos financieros sin ampliar las capacidades clínicas."""
from django.db.models import Q

from apps.accounts.models import Membresia

from .models import ConcesionFinanciera


def concesiones_financieras_de(usuario, accion, sensible=False):
    """Consulta base de concesiones activas para una acción financiera."""
    if not (getattr(usuario, "is_authenticated", False) and not usuario.is_superuser):
        return ConcesionFinanciera.objects.none()

    concesiones = ConcesionFinanciera.objects.filter(
        membresia__usuario=usuario,
        membresia__activo=True,
        accion=accion,
    )
    if ConcesionFinanciera.accion_requiere_administracion(accion) or sensible:
        concesiones = concesiones.filter(
            membresia__rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
    if sensible:
        concesiones = concesiones.filter(permite_sensibles=True)
    return concesiones


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
    if getattr(usuario, "is_superuser", False):
        return True
    return concesiones_financieras_en_alcance(
        usuario,
        accion,
        institucion_id,
        area_id,
        sensible=sensible,
    ).exists()
