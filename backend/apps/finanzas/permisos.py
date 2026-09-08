"""Verificación de permisos financieros sin ampliar las capacidades clínicas."""
from django.db.models import Q

from apps.accounts.models import Membresia

from .models import ConcesionFinanciera


ACCIONES_ADMINISTRATIVAS = {
    ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
    ConcesionFinanciera.Accion.CORREGIR_COSTOS,
}


def tiene_concesion_financiera(usuario, accion, institucion_id, area_id=None, sensible=False):
    """Indica si el usuario tiene una concesión explícita para ese alcance.

    El alcance se resuelve sobre la misma membresía que recibió la concesión;
    nunca se combinan áreas de otras membresías del usuario.
    """
    if not getattr(usuario, "is_authenticated", False):
        return False
    if usuario.is_superuser:
        return True

    concesiones = ConcesionFinanciera.objects.filter(
        membresia__usuario=usuario,
        membresia__institucion_id=institucion_id,
        membresia__activo=True,
        accion=accion,
    )
    if accion in ACCIONES_ADMINISTRATIVAS or sensible:
        concesiones = concesiones.filter(
            membresia__rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
    if sensible:
        concesiones = concesiones.filter(permite_sensibles=True)
    if area_id is None:
        return concesiones.filter(todas_las_areas=True).exists()
    return concesiones.filter(Q(todas_las_areas=True) | Q(areas__id=area_id)).exists()
