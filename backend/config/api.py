"""
Router central de la API REST.

Registra todos los ViewSets bajo `/api/`. La autenticación es JWT (ver
`config/urls.py` para los endpoints de token).
"""
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    LegajoProfesionalViewSet,
    MembresiaViewSet,
    UsuarioViewSet,
)
from apps.casos.views import (
    CasoViewSet,
    EventoCasoViewSet,
    ItemFilaViewSet,
    NotificacionViewSet,
    ValorCampoViewSet,
)
from apps.flujos.views import (
    ConexionViewSet,
    FlujoViewSet,
    NodoViewSet,
    VersionFlujoViewSet,
)
from apps.formularios.views import CampoViewSet, FormularioViewSet
from apps.finanzas.api_calendario import ExpectativaGastoViewSet
from apps.finanzas.api_cobros import PoliticaCobroViewSet, PendienteCobroViewSet
from apps.finanzas.api_dinero import ObligacionFinancieraViewSet, MovimientoDineroViewSet
from apps.finanzas.api_reportes_dinero import ReporteDineroViewSet
from apps.finanzas.api_auditoria import AccesoFinancieroViewSet
from apps.finanzas.api_reportes import ReporteFinanzasViewSet, ProcesamientoFinanzasViewSet
from apps.finanzas.api_repartos import CoberturaActividadViewSet, ReglaRepartoViewSet, RepartoGastoViewSet
from apps.finanzas.views import (
    AjusteCostoViewSet,
    AjusteGastoViewSet,
    ConceptoGastoViewSet,
    ConcesionFinancieraViewSet,
    DefinicionComponenteViewSet,
    HechoAtencionCosteableViewSet,
    GastoViewSet,
    PrestacionViewSet,
    ValorComponenteViewSet,
)
from apps.auditoria.views import AccesoClinicoViewSet
from apps.red.views import RedViewSet, TrasladoViewSet
from apps.farmacia.views import (
    DepositoViewSet, ExistenciaViewSet, InsumoViewSet, LoteViewSet,
    MovimientoViewSet, PedidoViewSet,
)
from apps.agenda.views import (
    AgendaViewSet, BloqueoViewSet, DisponibilidadViewSet, TurnoViewSet,
)
from apps.instituciones.views import (
    AreaViewSet, BoxViewSet, CamaViewSet, EstadiaCamaViewSet, GrupoViewSet,
    InstitucionViewSet, SubareaViewSet,
)
from apps.registros.views import (
    ConsentimientoDatosViewSet,
    CiudadanoViewSet,
    EntradaHistoriaViewSet,
    EstudioViewSet,
    HistoriaClinicaViewSet,
    RecetaViewSet,
)

router = DefaultRouter()

from apps.financiadores.views import FinanciadorViewSet
from apps.financiadores.api_autorizaciones import AutorizacionCoberturaViewSet
from apps.financiadores.api_hospital import CoberturaHospitalViewSet
from apps.finanzas.api_seguimiento_cobertura import SeguimientoCobrosViewSet

router.register("financiadores", FinanciadorViewSet, basename="financiador")
router.register("autorizaciones-cobertura", AutorizacionCoberturaViewSet, basename="autorizacion-cobertura")
router.register("coberturas", CoberturaHospitalViewSet, basename="cobertura")
router.register("seguimiento-cobros", SeguimientoCobrosViewSet, basename="seguimiento-cobros")

# accounts
router.register("usuarios", UsuarioViewSet)
router.register("membresias", MembresiaViewSet)
router.register("legajos", LegajoProfesionalViewSet)

# instituciones
router.register("instituciones", InstitucionViewSet)
router.register("areas", AreaViewSet)
router.register("subareas", SubareaViewSet)
router.register("grupos", GrupoViewSet)
router.register("boxes", BoxViewSet)
router.register("camas", CamaViewSet)
router.register("estadias-cama", EstadiaCamaViewSet)

# formularios
router.register("formularios", FormularioViewSet)
router.register("campos", CampoViewSet)

# flujos
router.register("flujos", FlujoViewSet)
router.register("versiones-flujo", VersionFlujoViewSet)
router.register("nodos", NodoViewSet)
router.register("conexiones", ConexionViewSet)

# casos
router.register("casos", CasoViewSet)
router.register("valores-campo", ValorCampoViewSet)
router.register("items-fila", ItemFilaViewSet)
router.register("eventos-caso", EventoCasoViewSet)
router.register("notificaciones", NotificacionViewSet, basename="notificacion")

# registros
router.register("ciudadanos", CiudadanoViewSet)
router.register("historias-clinicas", HistoriaClinicaViewSet)
router.register("entradas-historia", EntradaHistoriaViewSet)
router.register("estudios", EstudioViewSet)
router.register("recetas", RecetaViewSet)

# Agenda de turnos.
router.register("agendas", AgendaViewSet)
router.register("disponibilidades", DisponibilidadViewSet)
router.register("bloqueos-agenda", BloqueoViewSet)
router.register("turnos", TurnoViewSet)

# Farmacia e insumos.
router.register("insumos", InsumoViewSet)
router.register("depositos", DepositoViewSet)
router.register("lotes", LoteViewSet)
router.register("stock", ExistenciaViewSet)
router.register("movimientos-stock", MovimientoViewSet)
router.register("pedidos-stock", PedidoViewSet)

# Red de establecimientos.
router.register("redes", RedViewSet)
router.register("traslados", TrasladoViewSet, basename="traslado")

# Auditoría de accesos a datos clínicos (Ley 26.529).
router.register("accesos-clinicos", AccesoClinicoViewSet, basename="acceso-clinico")
router.register("consentimientos", ConsentimientoDatosViewSet)

# Finanzas: separado de la API clínica porque sus permisos son propios.
router.register("obligaciones-financieras", ObligacionFinancieraViewSet, basename="obligacion-financiera")
router.register("movimientos-dinero", MovimientoDineroViewSet, basename="movimiento-dinero")
router.register("politicas-cobro", PoliticaCobroViewSet, basename="politica-cobro")
router.register("pendientes-cobro", PendienteCobroViewSet, basename="pendiente-cobro")
router.register("reportes-dinero", ReporteDineroViewSet, basename="reporte-dinero")
router.register("accesos-financieros", AccesoFinancieroViewSet, basename="acceso-financiero")
router.register("reportes-finanzas", ReporteFinanzasViewSet, basename="reporte-finanzas")
router.register("procesamiento-finanzas", ProcesamientoFinanzasViewSet, basename="procesamiento-finanzas")
router.register("hechos-costo", HechoAtencionCosteableViewSet, basename="hecho-costo")
router.register("concesiones-financieras", ConcesionFinancieraViewSet)
router.register("prestaciones-costo", PrestacionViewSet)
router.register("componentes-costo", DefinicionComponenteViewSet)
router.register("conceptos-gasto", ConceptoGastoViewSet)
router.register("valores-componentes", ValorComponenteViewSet)
router.register("ajustes-costo", AjusteCostoViewSet, basename="ajuste-costo")
router.register("gastos", GastoViewSet, basename="gasto")
router.register("ajustes-gasto", AjusteGastoViewSet, basename="ajuste-gasto")
router.register("expectativas-gasto", ExpectativaGastoViewSet, basename="expectativa-gasto")
router.register("coberturas-actividad", CoberturaActividadViewSet, basename="cobertura-actividad")
router.register("reglas-reparto", ReglaRepartoViewSet, basename="regla-reparto")
router.register("repartos-gasto", RepartoGastoViewSet, basename="reparto-gasto")
