"""
Rutas de la fachada FHIR.

Las rutas son las que manda el estándar (`/fhir/Patient/12`, con la R en
mayúscula), no las de Cauce: un cliente FHIR las arma solo a partir del tipo de
recurso, y renombrarlas «para que combinen» rompe exactamente eso.

El comodín va último y responde en FHIR: sin él, pedir un recurso que no
existe devuelve el 404 de Django y manda a alguien a revisar su cliente
buscando un error que no es suyo.
"""
from django.urls import path, re_path

from . import views

urlpatterns = [
    path("metadata", views.metadata, name="fhir-metadata"),

    path("Patient/<int:pk>", views.patient_read, name="fhir-patient-read"),
    path("Patient", views.patient_search, name="fhir-patient-search"),

    path("Encounter/<int:pk>", views.encounter_read, name="fhir-encounter-read"),
    path("Encounter", views.encounter_search, name="fhir-encounter-search"),

    path("Organization/<int:pk>", views.organization_read, name="fhir-organization-read"),
    path("Organization", views.organization_search, name="fhir-organization-search"),

    re_path(r"^(?P<tipo>[A-Za-z]+)(?:/(?P<pk>[^/]+))?/?$", views.no_soportado),
]
