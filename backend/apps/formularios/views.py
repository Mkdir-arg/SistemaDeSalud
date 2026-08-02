
from apps.common import BaseModelViewSet

from .models import Campo, Formulario
from .serializers import CampoSerializer, FormularioSerializer


class FormularioViewSet(BaseModelViewSet):
    queryset = Formulario.objects.select_related("institucion", "area").prefetch_related("campos")
    serializer_class = FormularioSerializer
    capacidad_requerida = "diseno"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area")
    # La descripción también se busca: el listado la muestra como columna, así que
    # buscar por algo que está a la vista y no encontrarlo se siente roto.
    search_fields = ["titulo", "descripcion"]
    ordering_fields = ["titulo", "creado"]


class CampoViewSet(BaseModelViewSet):
    queryset = Campo.objects.select_related("formulario")
    serializer_class = CampoSerializer
    capacidad_requerida = "diseno"
    institucion_path = "formulario__institucion"
    filter_fields = ("formulario", "tipo", "requerido", "origen")
