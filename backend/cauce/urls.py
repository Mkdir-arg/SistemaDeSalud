"""
URL configuration for cauce project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import logging

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import Http404, JsonResponse
from django.urls import include, path
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.casos.views import MisTareasView, PantallaLlamadosView, PuestoDetalleView
from apps.common import DescargarArchivoView, SubirArchivoView
from cauce.api import router


def media_clinica_no_publica(_request, ruta):
    """Los uploads clinicos se sirven solo por /api/archivos/descargar/."""
    raise Http404


def health(_request):
    """
    ¿Esta instancia puede atender?

    **Toca la base.** Antes devolvía `ok` sin comprobar nada, que es el chequeo
    de salud clásico e inútil: el balanceador ve verde mientras la aplicación no
    llega a Postgres, le sigue mandando gente, y nadie recibe una alarma porque
    la sonda está conforme. Un proceso que responde HTTP pero no puede leer un
    paciente no está sano.

    Va sin autenticación —una sonda no tramita credenciales— y por eso no cuenta
    nada del sistema: `error` a secas. El detalle está en `/api/estado/`, que sí
    pide sesión.
    """
    from django.db import connection

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("health: la base no responde")
        return JsonResponse({"status": "error", "service": "cauce"}, status=503)

    return JsonResponse({"status": "ok", "service": "cauce"})


class EstadoView(APIView):
    """
    Qué está funcionando y qué se quedó callado.

    Lo que se vigila acá no es la aplicación —para eso está `/api/health/`—
    sino los procesos que corren SOLOS y cuya muerte no se nota: el reloj del
    motor, los recordatorios de turno, la alerta de saturación y el respaldo.

    Si el reloj muere, la aplicación sigue respondiendo y las pantallas cargan,
    pero un paciente que entró a «Observación 6 horas» no vuelve nunca y los
    avisos de demora no salen. Es una falla silenciosa y clínica, y hasta acá no
    había forma de enterarse.

    Devuelve 503 cuando hay algo atrasado para que un monitor externo lo pueda
    mirar sin interpretar el cuerpo.
    """

    permission_classes = [IsAuthenticated]

    # Se documenta a mano porque la respuesta se arma sin serializer. Va al
    # esquema y no excluida como la fachada FHIR: quien configura el monitoreo
    # de la institución tiene que poder encontrar este endpoint en la
    # documentación, que es donde lo va a buscar.
    @extend_schema(
        summary="Estado de los procesos periódicos",
        description=(
            "Latido del reloj del motor, los recordatorios de turno, la alerta de "
            "saturación y el respaldo. Devuelve 503 si alguno se quedó callado, "
            "para que un monitor externo lo mire sin interpretar el cuerpo."
        ),
        responses={
            200: {
                "type": "object",
                "properties": {
                    "servicios": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "estado": {"type": "string", "enum": ["al día", "atrasado", "nunca"]},
                                "hace_segundos": {"type": "integer", "nullable": True},
                                "detalle": {"type": "string"},
                            },
                        },
                    },
                    "atrasados": {"type": "array", "items": {"type": "string"}},
                },
            },
            503: {"description": "Hay al menos un proceso atrasado."},
        },
    )
    def get(self, request):
        from apps.auditoria import latidos

        datos = latidos.estado()
        return Response(datos, status=503 if datos["atrasados"] else 200)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    # Estado de los procesos periódicos. Separado de `health` porque muestra
    # cómo anda el sistema por dentro y eso pide sesión.
    path("api/estado/", EstadoView.as_view(), name="estado"),
    # Esquema OpenAPI y su visor. Es lo primero que pide el área de sistemas
    # de la institución cuando hay que integrar con lo que ya tienen.
    path("api/esquema/", SpectacularAPIView.as_view(), name="esquema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="esquema"), name="docs"),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/archivos/", SubirArchivoView.as_view(), name="subir_archivo"),
    path("api/archivos/descargar/<path:ruta>", DescargarArchivoView.as_view(), name="descargar_archivo"),
    path("media/uploads/<path:ruta>", media_clinica_no_publica, name="media_clinica_no_publica"),
    path("api/mis-tareas/", MisTareasView.as_view(), name="mis_tareas"),
    path("api/puestos/<int:nodo_id>/", PuestoDetalleView.as_view(), name="puesto_detalle"),
    path("api/pantalla/<str:token>/", PantallaLlamadosView.as_view(), name="pantalla_llamados"),
    path("api/", include(router.urls)),
    # Fachada FHIR R4. Fuera de /api/ a propósito: las rutas son las del
    # estándar y un cliente FHIR las arma solo a partir de la URL base, así que
    # tiene que poder apuntar a una raíz limpia.
    path("fhir/", include("apps.fhir.urls")),
]

# Servir archivos subidos en desarrollo.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
