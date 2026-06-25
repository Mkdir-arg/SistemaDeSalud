from rest_framework import filters

from apps.common import BaseModelViewSet

from .models import Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta
from .serializers import (
    CiudadanoSerializer,
    EntradaHistoriaSerializer,
    EstudioSerializer,
    HistoriaClinicaSerializer,
    RecetaSerializer,
)


class CiudadanoViewSet(BaseModelViewSet):
    queryset = Ciudadano.objects.select_related("institucion")
    serializer_class = CiudadanoSerializer
    capacidad_requerida = "registros"
    institucion_path = "institucion"
    filter_fields = ("institucion", "obra_social")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "apellido", "documento", "codigo"]
    ordering_fields = ["apellido", "nombre", "creado"]


class HistoriaClinicaViewSet(BaseModelViewSet):
    queryset = HistoriaClinica.objects.select_related("ciudadano").prefetch_related(
        "entradas", "estudios", "recetas"
    )
    serializer_class = HistoriaClinicaSerializer
    capacidad_requerida = "registros"
    institucion_path = "ciudadano__institucion"
    filter_fields = ("ciudadano",)


class EntradaHistoriaViewSet(BaseModelViewSet):
    queryset = EntradaHistoria.objects.select_related("historia", "autor", "caso")
    serializer_class = EntradaHistoriaSerializer
    capacidad_requerida = "registros"
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "autor", "caso", "firmada")


class EstudioViewSet(BaseModelViewSet):
    queryset = Estudio.objects.select_related("historia")
    serializer_class = EstudioSerializer
    capacidad_requerida = "registros"
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "resultado")


class RecetaViewSet(BaseModelViewSet):
    queryset = Receta.objects.select_related("historia", "autor")
    serializer_class = RecetaSerializer
    capacidad_requerida = "registros"
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "activa")
