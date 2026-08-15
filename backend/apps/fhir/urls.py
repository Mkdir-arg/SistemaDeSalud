"""
Rutas de la fachada FHIR.

Las rutas son las que manda el estándar (`/fhir/Patient/12`, con la R en
mayúscula), no las de Cauce: un cliente FHIR las arma solo a partir del tipo de
recurso, y renombrarlas «para que combinen» rompe exactamente eso.

El comodín va último y responde en FHIR: sin él, pedir un recurso que no
existe devuelve el 404 de Django y manda a alguien a revisar su cliente
buscando un error que no es suyo.

Las lecturas toman `<str:pk>` y no `<int:pk>`: en FHIR el `id` de un recurso es
una CADENA, así que `Patient/abc` es un pedido bien formado. Con `<int:pk>` caía
en el comodín y salía por `no_soportado` contestando que Patient no está
implementado —lo contrario de lo que el mismo cliente acababa de leer en
/fhir/metadata—. Las vistas resuelven a 404 cuando el id no es numérico; el
mensaje lo arma `no_soportado` mirando si el tipo está entre los que sí existen.
"""
from django.urls import path, re_path

from . import views

urlpatterns = [
    path("metadata", views.metadata, name="fhir-metadata"),

    path("Patient/<str:pk>", views.patient_read, name="fhir-patient-read"),
    path("Patient", views.patient_search, name="fhir-patient-search"),

    path("Encounter/<str:pk>", views.encounter_read, name="fhir-encounter-read"),
    path("Encounter", views.encounter_search, name="fhir-encounter-search"),

    path("Organization/<str:pk>", views.organization_read, name="fhir-organization-read"),
    path("Organization", views.organization_search, name="fhir-organization-search"),

    # El `pk` admite barras a propósito: los sufijos del estándar
    # (`Patient/12/_history`, `Patient/12/$everything`) tienen que salir por acá
    # y no por el 404 en HTML de Django.
    re_path(r"^(?P<tipo>[A-Za-z]+)(?:/(?P<pk>.+?))?/?$", views.no_soportado),
]
