from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.accounts.models import Membresia
from apps.common import ROL_CAPACIDADES, tiene_capacidad
from apps.finanzas.permisos import tiene_concesion_financiera
from .models import MembresiaFinanciador


def plataforma(usuario):
    return bool(usuario.is_authenticated and usuario.is_active and (usuario.is_superuser or tiene_capacidad(usuario, "gobierno_plataforma")))


def requerir_financiador(usuario, financiador_id, escritura=False, admin=False):
    if plataforma(usuario):
        return "admin"
    if not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied("La sesión no tiene acceso al financiador.")
    membresia = MembresiaFinanciador.objects.filter(usuario=usuario, financiador_id=financiador_id, financiador__activo=True, activo=True).first()
    if not membresia or (admin and membresia.rol != "admin") or (escritura and membresia.rol == "auditor"):
        raise PermissionDenied("No tenés permiso para esta operación en el financiador.")
    return membresia.rol


def requerir_hospital(usuario, institucion_id, accion, area_id=None, sensible=False):
    if not tiene_concesion_financiera(usuario, accion, institucion_id, area_id, sensible=sensible):
        raise PermissionDenied("Necesitás un permiso financiero explícito para esta operación.")


def requerir_caso(usuario, caso, certificar=False):
    if plataforma(usuario):
        return
    if not usuario.is_active or not tiene_capacidad(usuario, "casos_operar", caso.institucion_id):
        raise PermissionDenied("No tenés permiso para operar este caso.")
    roles = [rol for rol, capacidades in ROL_CAPACIDADES.items() if "casos_operar" in capacidades]
    membresias = Membresia.objects.filter(usuario=usuario, institucion_id=caso.institucion_id, activo=True, rol__in=roles)
    if certificar:
        membresias = membresias.filter(rol__in=["medico", "enfermeria", "jefe_area"])
    if not membresias.filter(Q(areas=caso.area_actual_id) | Q(areas__isnull=True)).exists():
        raise PermissionDenied("La operación requiere personal autorizado del área del caso.")
