"""Router productivo y vistas públicas de #136; sin importar config.settings."""
from django.urls import include, path
from config.api import router
from .api import EstadoCatalogoView, LugaresView

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/geografia/lugares/", LugaresView.as_view()),
    path("api/geografia/estado/", EstadoCatalogoView.as_view()),
    path("fhir/", include("apps.fhir.urls")),
]
