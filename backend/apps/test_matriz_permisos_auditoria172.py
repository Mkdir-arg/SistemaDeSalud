"""AUD-039: matriz de control de permiso y alcance institucional de la API (#172).

Recorre TODOS los viewsets de `config.api.router` y exige, para cada uno, dos
declaraciones verificables en el código:

- **Permiso:** `CapacidadPermission` con `capacidad_requerida` o
  `capacidad_por_accion`, una clase de permiso propia (además de
  `IsAuthenticated`) o un `get_permissions` propio.
- **Alcance institucional:** `institucion_path` aplicado por
  `InstitucionScopedMixin` (sin un `get_queryset` que lo saltee).

Lo que no cumple una de las dos tiene que figurar abajo con el motivo y el
lugar donde está el control equivalente. Es una prueba estructural: no
demuestra que el control en código sea correcto, solo que nadie agregó un
recurso sin decidirlo. La evidencia HTTP A/B vive en las pruebas citadas y en
`docs/plans/2026-10-19-matriz-permisos-172.md`, que lista los huecos.

Complementa `apps.casos.test_permisos_barrida` (capacidad de escritura por rol
en una institución); acá se agrega el eje institución A/B.
"""
import inspect

from django.test import SimpleTestCase
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.common import BaseModelViewSet, CapacidadPermission, InstitucionScopedMixin
from config.api import router

GENERICOS = {IsAuthenticated, AllowAny, CapacidadPermission}

# Viewsets sin capacidad ni clase de permiso propia: autorizan en el código.
PERMISO_EN_CODIGO = {
    "financiadores": "Ámbito pagador: queryset por MembresiaFinanciador activa y requerir_financiador/plataforma() por acción.",
    "autorizaciones-cobertura": "requerir_financiador, casos_permitidos y puede_resolver_autorizaciones/puede_cargar_manual por acción.",
    "coberturas": "get_queryset con alcance_financiero_q por acción más casos_operar por institución/área.",
    "seguimiento-cobros": "list() exige puede_seguimiento(usuario, institución) y responde 403.",
    "notificaciones": "Recurso personal: queryset filtrado por usuario=request.user.",
    "obligaciones-financieras": "get_queryset con alcance_financiero_q(ver_dinero) y 403 sin concesión; acciones con registrar_dinero.",
    "movimientos-dinero": "get_queryset con alcance_financiero_q(ver_dinero) y 403 sin concesión.",
    "reportes-dinero": "list() valida concesión financiera en la institución/área pedida (403).",
    "reportes-finanzas": "ConsultaReporte.fuentes(): gastos_en_alcance_financiero y 403 por institución/área.",
    "procesamiento-finanzas": "ConsultaReporte.fuentes(): mismo control que reportes-finanzas.",
    "reportes-costos": "list() exige admin financiero o concesión en la institución/área pedida (403).",
}

# Viewsets que acotan por institución en su propio get_queryset/list, sin
# `institucion_path` aplicado por el mixin.
ALCANCE_EN_CODIGO = {
    "financiadores": "Por financiador (MembresiaFinanciador), no por institución hospitalaria.",
    "autorizaciones-cobertura": "Por financiador o por casos permitidos de la institución pedida.",
    "coberturas": "alcance_financiero_q (institución/área/sensible) o casos_operar en la institución.",
    "usuarios": "Personas con membresía activa en instituciones administradas (config_institucional); global para plataforma.",
    "membresias": "get_queryset propio: institucion__in de las membresías activas; global para plataforma.",
    "legajos": "Personas con membresía activa en instituciones con config_institucional.",
    "instituciones": "id__in de las membresías activas; global para plataforma.",
    "estadias-cama": "cama__area__institucion de las membresías activas.",
    "notificaciones": "Por usuario, no por institución.",
    "redes": "Redes que incluyen una institución del usuario; global para plataforma.",
    "traslados": "motor.visibles_para + origen/destino en instituciones del usuario.",
    "accesos-clinicos": "_instituciones_que_audita: solo donde la persona conduce.",
    "obligaciones-financieras": "alcance_financiero_q (institución/área/sensible).",
    "movimientos-dinero": "alcance_financiero_q sobre la obligación.",
    "politicas-cobro": "alcance_financiero_q(configurar_cobros).",
    "pendientes-cobro": "alcance_financiero_q por acción.",
}

# Sin queryset institucional: el alcance se valida por pedido o no aplica.
SIN_ALCANCE_EN_QUERYSET = {
    "seguimiento-cobros": "Reporte agregado: list() valida la institución y el área del pedido.",
    "reportes-dinero": "Reporte agregado: list() valida la institución y el área del pedido.",
    "reportes-finanzas": "Reporte agregado: fuentes() filtra por institución autorizada.",
    "procesamiento-finanzas": "Estado de procesamiento: fuentes() filtra por institución autorizada.",
    "reportes-costos": "Reporte agregado: list() valida la institución y el área del pedido.",
    "simulaciones": "Solo superusuario (SoloSuperusuario); cada sesión filtrada por superusuario=request.user.",
}

# Acciones que bajan el permiso de la vista a IsAuthenticated/AllowAny.
ACCIONES_SIN_PERMISO_DE_VISTA = {
    "financiadores.activar": "Público a propósito: activa una cuenta con uid+token de un solo uso.",
    "concesiones-financieras.mias": "Las concesiones propias del usuario autenticado (queryset por usuario).",
}

_BASES = (InstitucionScopedMixin, BaseModelViewSet, viewsets.ModelViewSet,
          viewsets.ReadOnlyModelViewSet, viewsets.GenericViewSet, viewsets.ViewSet)


def _propio(viewset, nombre):
    """Clase del proyecto que define `nombre` en el MRO, antes de las bases genéricas."""
    for clase in viewset.__mro__:
        if clase in _BASES:
            return None
        if nombre in clase.__dict__:
            return clase
    return None


def control_de_permiso(viewset):
    permisos = set(viewset.permission_classes)
    capacidad = getattr(viewset, "capacidad_requerida", None) or getattr(viewset, "capacidad_por_accion", None)
    if CapacidadPermission in permisos and capacidad:
        return "capacidad"
    if permisos - GENERICOS:
        return "clase"
    if _propio(viewset, "get_permissions"):
        return "get_permissions"
    return None


def alcance_institucional(viewset):
    if getattr(viewset, "institucion_path", None) and issubclass(viewset, InstitucionScopedMixin):
        propio = _propio(viewset, "get_queryset")
        if propio is None or "super().get_queryset" in inspect.getsource(propio.get_queryset):
            return "institucion_path"
    return "get_queryset" if _propio(viewset, "get_queryset") else None


def acciones_degradadas(prefijo, viewset):
    return {
        f"{prefijo}.{accion.__name__}" for accion in viewset.get_extra_actions()
        if "permission_classes" in accion.kwargs and not set(accion.kwargs["permission_classes"]) - GENERICOS
    }


class MatrizPermisosAuditoria172Tests(SimpleTestCase):
    def test_todo_viewset_declara_permiso_y_alcance_o_exencion(self):
        faltas, permiso_codigo, alcance_codigo, sin_alcance, degradadas = [], set(), set(), set(), set()
        for prefijo, viewset, _ in router.registry:
            if control_de_permiso(viewset) is None:
                permiso_codigo.add(prefijo)
                if prefijo not in PERMISO_EN_CODIGO:
                    faltas.append(f"{prefijo}: sin control de permiso declarado")
            alcance = alcance_institucional(viewset)
            if alcance == "get_queryset":
                alcance_codigo.add(prefijo)
                if prefijo not in ALCANCE_EN_CODIGO:
                    faltas.append(f"{prefijo}: alcance solo en get_queryset propio, sin justificar")
            elif alcance is None:
                sin_alcance.add(prefijo)
                if prefijo not in SIN_ALCANCE_EN_QUERYSET:
                    faltas.append(f"{prefijo}: sin alcance institucional")
            for nombre in acciones_degradadas(prefijo, viewset):
                degradadas.add(nombre)
                if nombre not in ACCIONES_SIN_PERMISO_DE_VISTA:
                    faltas.append(f"{nombre}: la acción baja el permiso a IsAuthenticated/AllowAny")
        self.assertEqual(faltas, [], "\n" + "\n".join(faltas))
        # Exenciones vencidas: que la lista no justifique recursos que ya no lo necesitan.
        self.assertEqual(set(PERMISO_EN_CODIGO) - permiso_codigo, set())
        self.assertEqual(set(ALCANCE_EN_CODIGO) - alcance_codigo, set())
        self.assertEqual(set(SIN_ALCANCE_EN_QUERYSET) - sin_alcance, set())
        self.assertEqual(set(ACCIONES_SIN_PERMISO_DE_VISTA) - degradadas, set())

    def test_el_clasificador_detecta_un_viewset_sin_controles(self):
        class Abierto(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated]

            @action(detail=False, permission_classes=[AllowAny])
            def publica(self, request):
                return None

        class ConCapacidadSinAlcance(BaseModelViewSet):
            capacidad_requerida = "historia_clinica"

        class SaltaElMixin(BaseModelViewSet):
            capacidad_requerida = "historia_clinica"
            institucion_path = "institucion"

            def get_queryset(self):
                return self.queryset

        self.assertIsNone(control_de_permiso(Abierto))
        self.assertIsNone(alcance_institucional(Abierto))
        self.assertEqual(acciones_degradadas("x", Abierto), {"x.publica"})
        self.assertEqual(control_de_permiso(ConCapacidadSinAlcance), "capacidad")
        self.assertIsNone(alcance_institucional(ConCapacidadSinAlcance))
        self.assertEqual(alcance_institucional(SaltaElMixin), "get_queryset")
