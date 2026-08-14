
from django.db.models import IntegerField, OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from .models import (
    Ciudadano, ConsentimientoDatos, EntradaHistoria, Estudio, HistoriaClinica, Receta,
)
from .serializers import (
    CiudadanoSerializer,
    ConsentimientoDatosSerializer,
    EntradaHistoriaSerializer,
    EstudioSerializer,
    HistoriaClinicaSerializer,
    RecetaSerializer,
)


def _conteo(modelo, **filtros):
    """
    Cuántas filas de `modelo` cuelgan de la historia de cada ciudadano.

    Va como subconsulta y no como `Count(..., distinct=True)` sobre varios
    `join`: contar entradas, estudios y recetas en la misma consulta multiplica
    las filas entre sí, y en una historia larga eso es peor que el N+1 que se
    está sacando.
    """
    from django.db.models import Count, OuterRef, Subquery

    sub = (
        modelo.objects.filter(historia__ciudadano=OuterRef("pk"), **filtros)
        .order_by()
        .values("historia__ciudadano")
        .annotate(n=Count("id"))
        .values("n")
    )
    return Coalesce(Subquery(sub, output_field=IntegerField()), 0)


class CiudadanoViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "self"
    # El resumen de cada paciente se anota de una vez. Calculado por fila en el
    # serializer eran seis consultas por paciente: 155 para mostrar 30, y peor
    # cuanto más grande el padrón. Hay un test que compara las consultas con 3 y
    # con 30 filas; si alguien saca esto, se pone en rojo.
    queryset = (
        Ciudadano.objects
        .select_related("institucion", "historia_clinica")
        .prefetch_related(Prefetch(
            "consentimientos",
            # El orden va acá: el serializer lee `all()` para no saltear la
            # precarga, así que el «último consentimiento» tiene que ser el
            # primero de esta lista.
            queryset=ConsentimientoDatos.objects.order_by("-momento", "-id"),
        ))
        .annotate(
            _entradas=_conteo(EntradaHistoria),
            _estudios=_conteo(Estudio),
            _recetas_activas=_conteo(Receta, activa=True),
            _ultima=Subquery(
                EntradaHistoria.objects
                .filter(historia__ciudadano=OuterRef("pk"))
                .order_by("-fecha").values("fecha")[:1]
            ),
        )
    )
    serializer_class = CiudadanoSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "institucion"
    filter_fields = ("institucion", "obra_social")
    search_fields = ["nombre", "apellido", "documento", "codigo"]
    ordering_fields = ["apellido", "nombre", "creado"]
    # El padrón de pacientes con registro. Son datos sensibles: la exportación
    # pasa por el mismo permiso que la lectura (`protege_lectura`), así que sólo
    # la obtiene quien ya podía ver la pantalla.
    nombre_csv = "pacientes"
    columnas_csv = [
        ("documento", "Documento"),
        ("apellido", "Apellido"),
        ("nombre", "Nombre"),
        ("fecha_nacimiento", "Fecha de nacimiento"),
        ("obra_social", "Obra social"),
        ("condiciones", "Condiciones"),
        ("alergias", "Alergias"),
        ("entradas", "Entradas de historia"),
        ("ultima", "Última atención"),
    ]


class HistoriaClinicaViewSet(AuditaLecturaClinica, BaseModelViewSet):
    queryset = HistoriaClinica.objects.select_related("ciudadano").prefetch_related(
        "entradas", "estudios", "recetas"
    )
    serializer_class = HistoriaClinicaSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "ciudadano__institucion"
    filter_fields = ("ciudadano",)

    @action(detail=True, methods=["get"])
    def verificar(self, request, pk=None):
        """
        ¿Esta historia dice hoy lo mismo que cuando se firmó cada entrada?

        Verifica cada entrada y la cadena entre ellas. Es lo que se presenta
        ante un reclamo o una auditoría: sin esto, «está firmada» es una
        afirmación que nadie puede comprobar.
        """
        from .integridad import verificar_historia

        historia = self.get_object()
        return Response(verificar_historia(historia))


class EntradaHistoriaViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "historia__ciudadano"
    queryset = EntradaHistoria.objects.select_related("historia", "autor", "caso")
    serializer_class = EntradaHistoriaSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "autor", "caso", "firmada")


class EstudioViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "historia__ciudadano"
    queryset = Estudio.objects.select_related("historia")
    serializer_class = EstudioSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "resultado")


class RecetaViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "historia__ciudadano"
    queryset = Receta.objects.select_related("historia", "autor")
    serializer_class = RecetaSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "activa")


class ConsentimientoDatosViewSet(AuditaLecturaClinica, BaseModelViewSet):
    """
    Consentimiento del paciente para el tratamiento de sus datos (Ley 25.326).

    Se agregan registros; no se editan ni se borran. Una revocación es una fila
    NUEVA con `otorgado=False`: lo que vale ante un reclamo es el historial —qué
    se consintió y cuándo—, no el estado de hoy.
    """

    queryset = ConsentimientoDatos.objects.select_related("ciudadano", "tomado_por")
    serializer_class = ConsentimientoDatosSerializer
    capacidad_requerida = "registros"
    protege_lectura = True
    institucion_path = "ciudadano__institucion"
    filter_fields = ("ciudadano", "otorgado", "modo")
    http_method_names = ["get", "head", "options", "post"]

    def perform_create(self, serializer):
        # Quién lo tomó sale de la sesión, no del cuerpo: un consentimiento que
        # se puede atribuir a cualquiera no se puede verificar.
        obj = serializer.save(tomado_por=self.request.user)
        if obj.institucion_id is None:
            obj.institucion = obj.ciudadano.institucion
            obj.save(update_fields=["institucion"])
