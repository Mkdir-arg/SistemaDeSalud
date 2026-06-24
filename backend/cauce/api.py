"""
Router central de la API REST.

Registra todos los ViewSets bajo `/api/`. La autenticación es JWT (ver
`cauce/urls.py` para los endpoints de token).
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
    ValorCampoViewSet,
)
from apps.flujos.views import (
    ConexionViewSet,
    FlujoViewSet,
    NodoViewSet,
    VersionFlujoViewSet,
)
from apps.formularios.views import CampoViewSet, FormularioViewSet
from apps.instituciones.views import AreaViewSet, InstitucionViewSet, SubareaViewSet
from apps.registros.views import (
    CiudadanoViewSet,
    EntradaHistoriaViewSet,
    EstudioViewSet,
    HistoriaClinicaViewSet,
    RecetaViewSet,
)

router = DefaultRouter()

# accounts
router.register("usuarios", UsuarioViewSet)
router.register("membresias", MembresiaViewSet)
router.register("legajos", LegajoProfesionalViewSet)

# instituciones
router.register("instituciones", InstitucionViewSet)
router.register("areas", AreaViewSet)
router.register("subareas", SubareaViewSet)

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

# registros
router.register("ciudadanos", CiudadanoViewSet)
router.register("historias-clinicas", HistoriaClinicaViewSet)
router.register("entradas-historia", EntradaHistoriaViewSet)
router.register("estudios", EstudioViewSet)
router.register("recetas", RecetaViewSet)
