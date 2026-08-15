
from django.db.models import Count, Prefetch
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.common import BaseModelViewSet

from .models import Campo, Formulario
from .serializers import CampoSerializer, FormularioSerializer


class CampoConDatos(APIException):
    """Se intentó borrar un campo del que ya cuelgan valores de casos reales."""

    status_code = status.HTTP_409_CONFLICT


class FormularioViewSet(BaseModelViewSet):
    queryset = Formulario.objects.select_related("institucion", "area").prefetch_related(
        # El conteo de valores viaja con cada campo (lo usa el diálogo de borrado
        # para decir cuántos datos están en juego). Anotado en el prefetch y no
        # por campo: la pantalla de detalle abre todos los campos de una.
        Prefetch("campos", queryset=Campo.objects.annotate(valores_n=Count("valores")))
    )
    serializer_class = FormularioSerializer
    capacidad_requerida = "diseno"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area")
    # La descripción también se busca: el listado la muestra como columna, así que
    # buscar por algo que está a la vista y no encontrarlo se siente roto.
    search_fields = ["titulo", "descripcion"]
    ordering_fields = ["titulo", "creado"]


class CampoViewSet(BaseModelViewSet):
    queryset = Campo.objects.select_related("formulario").annotate(valores_n=Count("valores"))
    serializer_class = CampoSerializer
    capacidad_requerida = "diseno"
    institucion_path = "formulario__institucion"
    filter_fields = ("formulario", "tipo", "requerido", "origen")

    def perform_destroy(self, instance):
        """No se borra un campo del que ya cuelgan datos cargados.

        `ValorCampo.campo` es CASCADE: borrar el campo «Motivo de consulta» del
        formulario de admisión se lleva puestos todos los valores cargados de
        todos los casos, y el EventoCaso sólo guarda «Formulario X completado ·
        5 campos cargados», sin los valores. Motivo de consulta, nivel de triage,
        alergias o tensión arterial son el registro del proceso asistencial:
        desaparecen sin dejar rastro y no hay de dónde recuperarlos.
        """
        cargados = instance.valores.count()
        if cargados:
            raise CampoConDatos({
                "detail": (
                    f"«{instance.label}» tiene {cargados} "
                    f"{'valor cargado' if cargados == 1 else 'valores cargados'} en casos. "
                    "Borrarlo los borraría a todos y no hay de dónde recuperarlos: "
                    "editá la etiqueta o las opciones en vez de rehacer el campo."
                ),
                "valores": cargados,
            })
        instance.delete()
