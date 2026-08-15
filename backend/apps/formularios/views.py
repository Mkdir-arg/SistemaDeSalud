
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
        #
        # El `order_by` es explícito porque `annotate` arma un GROUP BY y ahí
        # Django IGNORA el `Meta.ordering` del modelo: sin esto los campos
        # salían en el orden en que se crearon, así que reordenarlos no cambiaba
        # nada en la pantalla que completa el administrativo ni en la vista previa.
        Prefetch(
            "campos",
            queryset=Campo.objects.annotate(valores_n=Count("valores")).order_by("orden", "id"),
        )
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
    # Mismo motivo que en el prefetch de arriba: con `annotate` el `Meta.ordering`
    # no se aplica, y una lista sin orden explícito pagina mal (una fila puede
    # salir en dos páginas o en ninguna).
    queryset = (
        Campo.objects.select_related("formulario")
        .annotate(valores_n=Count("valores"))
        .order_by("formulario", "orden", "id")
    )
    serializer_class = CampoSerializer
    capacidad_requerida = "diseno"
    institucion_path = "formulario__institucion"
    filter_fields = ("formulario", "tipo", "requerido", "origen")

    def perform_update(self, serializer):
        """La etiqueta, la ayuda, las opciones y el orden se editan siempre; el TIPO no.

        Corregir «Tensión artrial», agregar una obra social nueva a la lista o
        volver obligatorio el motivo de consulta son cambios que un hospital hace
        todo el tiempo y no tocan un solo dato guardado. El tipo sí: los valores
        se guardan como texto, así que pasar «Nivel de triage» de selección única
        a fecha deja los valores ya cargados sin significado —el detalle del caso
        muestra «Rojo - Emergencia» en un campo fecha— y las Decisiones que
        comparaban ese campo empiezan a mandar los casos por la rama que no era.
        """
        campo = serializer.instance
        nuevo_tipo = serializer.validated_data.get("tipo", campo.tipo)
        if nuevo_tipo != campo.tipo:
            cargados = campo.valores.count()
            if cargados:
                raise CampoConDatos({
                    "detail": (
                        f"«{campo.label}» ya tiene {cargados} "
                        f"{'valor cargado' if cargados == 1 else 'valores cargados'} en casos: "
                        "cambiarle el tipo los dejaría sin sentido. Podés editar la etiqueta, "
                        "la ayuda, las opciones y el orden."
                    ),
                    "valores": cargados,
                })
        serializer.save()

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
