from rest_framework import filters

from apps.common import BaseModelViewSet

from .models import Campo, Formulario
from .serializers import CampoSerializer, FormularioSerializer


class FormularioViewSet(BaseModelViewSet):
    queryset = Formulario.objects.select_related("institucion", "area").prefetch_related("campos")
    serializer_class = FormularioSerializer
    institucion_path = "institucion"
    filter_fields = ("institucion", "area")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titulo"]
    ordering_fields = ["titulo", "creado"]


class CampoViewSet(BaseModelViewSet):
    queryset = Campo.objects.select_related("formulario")
    serializer_class = CampoSerializer
    institucion_path = "formulario__institucion"
    filter_fields = ("formulario", "tipo", "requerido", "origen")
