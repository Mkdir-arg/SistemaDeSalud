"""Coverage R4 actual de un paciente hospitalario, bajo permiso de Admisión."""
import re

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.auditoria.mixins import registrar_acceso
from apps.auditoria.models import AccesoClinico
from apps.common import ROL_CAPACIDADES
from apps.financiadores.administrativa import resumenes_administrativos
from apps.registros.models import Ciudadano
from . import recursos
from .views import _aviso_ignorados, _enlaces, _error, _fhir, _ignorados, _paginacion, fuera_del_openapi


def _pacientes(request):
    qs = Ciudadano.objects.all()
    if not request.user.is_superuser:
        roles = [rol for rol, caps in ROL_CAPACIDADES.items() if "padron_admision" in caps]
        ids = request.user.membresias.filter(activo=True, rol__in=roles).values("institucion_id")
        qs = qs.filter(institucion_id__in=ids)
    return qs


def _recursos(ciudadano):
    resumen = resumenes_administrativos([ciudadano])[ciudadano.pk]
    return [recursos.coverage(ciudadano, a) for a in resumen["afiliaciones"] if a["seleccionable"]]


def _auditar(request, ciudadano, cantidad):
    # No registra el documento ni los parámetros arbitrarios en el log.
    registrar_acceso(request, AccesoClinico.Tipo.DETALLE, "cobertura",
                     ciudadano=ciudadano, objeto_id=ciudadano.pk,
                     detalle="fhir Coverage: padrón vigente del hospital", resultados=cantidad,
                     estricto=True)


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coverage_search(request):
    # Una referencia local identifica la ficha y su ámbito. No hay búsqueda por
    # DNI ni descarga transversal del padrón de una obra social.
    referencia = request.query_params.get("beneficiary", "")
    match = re.fullmatch(r"(?:Patient/)?([1-9][0-9]*)", referencia)
    if not match:
        return _error(400, "required", "Indicá beneficiary=Patient/<id> del hospital autorizado.")
    ciudadano = _pacientes(request).filter(pk=match[1]).first()
    if ciudadano is None:
        return _error(404, "not-found", "No hay un Patient accesible con ese id.")
    filas = _recursos(ciudadano)
    offset, count = _paginacion(request)
    pagina = filas[offset:offset + count]
    _auditar(request, ciudadano, len(pagina))
    return _fhir(recursos.bundle(
        pagina, total=len(filas),
        enlaces=_enlaces(request, offset, count, len(pagina), len(filas)),
        avisos=_aviso_ignorados(_ignorados(request, {"beneficiary"})),
    ))


@fuera_del_openapi
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coverage_read(request, pk):
    match = re.fullmatch(r"([1-9][0-9]*)-([1-9][0-9]*)", pk)
    if not match:
        return _error(404, "not-found", "No hay una Coverage vigente con ese id.")
    ciudadano = _pacientes(request).filter(pk=match[1]).first()
    if ciudadano is not None:
        for recurso in _recursos(ciudadano):
            if recurso["id"] == pk:
                _auditar(request, ciudadano, 1)
                return _fhir(recurso)
    return _error(404, "not-found", "No hay una Coverage vigente con ese id.")
