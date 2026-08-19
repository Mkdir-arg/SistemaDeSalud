
from django.db import transaction
from django.db.models import IntegerField, OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditoria.mixins import AuditaLecturaClinica
from apps.common import BaseModelViewSet

from . import integridad, reglas
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
    capacidad_requerida = "padron_admision"
    protege_lectura = True
    institucion_path = "institucion"
    filter_fields = ("institucion", "obra_social")
    search_fields = ["nombre", "apellido", "documento", "codigo"]
    ordering_fields = ["apellido", "nombre", "creado"]
    # Sin DELETE ni PUT, igual que la historia y sus entradas. Borrar al paciente
    # ES borrar su historia: `historia_clinica` es CASCADE y de ella cuelgan
    # entradas, estudios y recetas también en CASCADE, así que un solo DELETE se
    # llevaba diez años de expediente legal —firmado y sellado— sin
    # confirmación, sin baja lógica y sin dejar rastro (el registro de accesos
    # sólo engancha las lecturas). La puerta estaba trabada en los hijos y
    # abierta de par en par en el padre.
    #
    # Peor todavía: `AccesoClinico.ciudadano` es PROTECT, así que el mismo
    # pedido reventaba con un 500 si alguien alguna vez abrió la ficha y borraba
    # todo si nadie la había abierto. Que el expediente sobreviva no puede
    # depender de si un compañero entró a mirarlo.
    #
    # Si hay que dar de baja un registro creado por error, eso es una baja lógica
    # con motivo y autor, no un método HTTP.
    http_method_names = ["get", "head", "options", "post", "patch"]
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
    # El autor de cada entrada y de cada receta va en el prefetch. Sin esto era
    # una consulta a `accounts_usuario` POR entrada de evolución —27 consultas
    # para una historia de 19 atenciones—, y el costo crece con los años de
    # historia: el paciente crónico, el que más urgente es leer, es el que más
    # tarda en abrir. Hay un test que compara las consultas de una historia
    # corta con las de una larga.
    queryset = HistoriaClinica.objects.select_related("ciudadano").prefetch_related(
        Prefetch("entradas", queryset=EntradaHistoria.objects.select_related("autor")),
        "estudios",
        Prefetch("recetas", queryset=Receta.objects.select_related("autor")),
    )
    serializer_class = HistoriaClinicaSerializer
    capacidad_requerida = "historia_clinica"
    protege_lectura = True
    institucion_path = "ciudadano__institucion"
    filter_fields = ("ciudadano",)
    # Sin DELETE ni PUT. La historia clínica es inviolable y de conservación
    # obligatoria por diez años (Ley 26.529, art. 15-16): un DELETE acá se
    # llevaba por cascade todas las entradas, estudios y recetas del paciente,
    # sin confirmación, sin baja lógica y sin dejar nada que verificar. Si hay
    # que dar de baja una historia creada por error, eso es una baja lógica con
    # motivo y autor, no un método HTTP.
    http_method_names = ["get", "head", "options", "post", "patch"]

    def perform_update(self, serializer):
        # Los antecedentes son lo único editable de la historia. Se asienta
        # quién los cargó y cuándo: sin eso, `alergias=""` no distingue «se
        # preguntó y no tiene» de «nunca se preguntó», y la pantalla resuelve la
        # duda afirmando lo primero sobre un paciente alérgico.
        serializer.save(antecedentes_por=self.request.user, antecedentes_at=timezone.now())

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
    queryset = EntradaHistoria.objects.select_related(
        "historia", "historia__ciudadano", "autor", "caso"
    )
    serializer_class = EntradaHistoriaSerializer
    capacidad_requerida = "historia_clinica"
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "autor", "caso", "firmada")
    # Sin DELETE ni PUT: un asiento de la historia clínica no se borra. Borrar
    # la ÚLTIMA entrada no rompe la cadena de sellos y no dejaba ningún rastro
    # —el registro de accesos sólo engancha las lecturas—, así que era la forma
    # más limpia de hacer desaparecer una atención. La corrección de una entrada
    # firmada es una entrada NUEVA.
    http_method_names = ["get", "head", "options", "post", "patch"]

    def perform_create(self, serializer):
        """
        Quién atendió sale de la sesión, y firmar exige ser quien puede firmar.

        Éste es el camino del botón «Nueva atención» de la historia, no un rincón
        raro de la API: antes aceptaba `autor` y `firmada` del cuerpo sin validar
        nada, así que un administrativo de mesa de entradas dejaba un «Alta
        médica» firmado a nombre de una médica que nunca vio al paciente. Y como
        la entrada nacía sin sello, la verificación la clasificaba como
        «anterior al sellado» y la historia seguía diciendo `ok: true`: la
        entrada fabricada ayer se disfrazaba de entrada vieja.
        """
        historia = serializer.validated_data["historia"]
        matricula = ""
        if serializer.validated_data.get("firmada"):
            matricula = reglas.exigir_firmante(historia.ciudadano.institucion, self.request.user)
        with transaction.atomic():
            entrada = serializer.save(autor=self.request.user, matricula=matricula)
            # Sellar en la misma transacción que el alta: una entrada firmada
            # que quedara sin sellar es exactamente el disfraz de arriba.
            integridad.sellar(entrada)

    def perform_update(self, serializer):
        """
        El borrador se corrige; lo firmado, no.

        Una entrada sin firmar es un borrador y editarla es lo esperable. Una
        firmada es el registro legal que se presenta ante un reclamo: pisarla
        deja `integra=False` para siempre y no hay forma de saber qué decía.
        """
        entrada = serializer.instance
        if entrada.firmada:
            raise reglas.RegistroInviolable(
                "Esta atención ya está firmada y no se puede modificar. "
                "Para corregirla, registrá una atención nueva."
            )
        if not serializer.validated_data.get("firmada"):
            serializer.save()
            return

        matricula = reglas.exigir_firmante(
            entrada.historia.ciudadano.institucion, self.request.user
        )
        with transaction.atomic():
            # Firma quien firma, no quien escribió el borrador: la matrícula que
            # se asienta es la de esta persona, y tiene que ir con su autoría o
            # el sello certificaría una atribución falsa.
            obj = serializer.save(autor=self.request.user, matricula=matricula)
            integridad.sellar(obj)


class EstudioViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "historia__ciudadano"
    queryset = Estudio.objects.select_related("historia", "historia__ciudadano")
    serializer_class = EstudioSerializer
    capacidad_requerida = "historia_clinica"
    capacidad_por_accion = {
        "create": "solicitud_estudios",
        "update": "solicitud_estudios",
        "partial_update": "solicitud_estudios",
    }
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "resultado")
    # Sin DELETE ni PUT, como recetas y entradas: un estudio es parte de un
    # expediente de conservación obligatoria por diez años, y hacerlo desaparecer
    # con un DELETE no deja rastro —el estudio no lleva sello y
    # `verificar_historia` sólo recorre entradas firmadas—. Un estudio cargado
    # por error se corrige con uno nuevo.
    http_method_names = ["get", "head", "options", "post", "patch"]

    def perform_create(self, serializer):
        # Solicitar un estudio es un acto clínico, igual que emitirlo desde el
        # flujo. Y `Estudio.autor` es texto libre: si además viniera del cuerpo,
        # quién lo pidió sería una cadena que nadie puede verificar.
        historia = serializer.validated_data["historia"]
        reglas.exigir_clinico(historia.ciudadano.institucion, self.request.user)
        serializer.save(autor=self.request.user.nombre_completo)

    def perform_update(self, serializer):
        # Informar un resultado es tan clínico como pedirlo, y hasta acá sólo el
        # alta lo exigía: mesa de entradas podía pasar un «alterado» a «normal» o
        # cambiar qué estudio fue, y como `autor` es read-only el registro seguía
        # diciendo que lo pidió la médica. Ella no tiene con qué desmentirlo: el
        # estudio no lleva sello ni matrícula, que es el mismo argumento con el
        # que se blindó el alta.
        estudio = serializer.instance
        reglas.exigir_clinico(estudio.historia.ciudadano.institucion, self.request.user)
        serializer.save()


class RecetaViewSet(AuditaLecturaClinica, BaseModelViewSet):
    ciudadano_path = "historia__ciudadano"
    queryset = Receta.objects.select_related("historia", "historia__ciudadano", "autor")
    serializer_class = RecetaSerializer
    capacidad_requerida = "historia_clinica"
    capacidad_por_accion = {
        "create": "prescripcion",
        "suspender": "prescripcion",
    }
    protege_lectura = True
    institucion_path = "historia__ciudadano__institucion"
    filter_fields = ("historia", "activa")
    # Una receta emitida no se edita ni se borra: se suspende con motivo, y eso
    # va por la acción `suspender`, que deja el asiento en la evolución.
    http_method_names = ["get", "head", "options", "post"]

    def perform_create(self, serializer):
        # Prescribir es un acto clínico. Sin esto, un administrativo emitía una
        # receta de un psicofármaco a nombre de una médica que no la prescribió,
        # y ella no tenía con qué desmentirlo: la receta no lleva sello ni
        # matrícula.
        historia = serializer.validated_data["historia"]
        reglas.exigir_clinico(historia.ciudadano.institucion, self.request.user)
        serializer.save(autor=self.request.user)

    @extend_schema(
        summary="Suspende una receta vigente",
        description="Pone la receta en inactiva y deja un asiento firmado en la evolución.",
        # El cuerpo no es una receta: es el motivo. Sin declararlo, el esquema
        # documentaría `RecetaSerializer` y quien integre mandaría lo que no es.
        request={"application/json": {
            "type": "object",
            "properties": {"motivo": {"type": "string"}},
            "required": ["motivo"],
        }},
        responses=RecetaSerializer,
    )
    @action(detail=True, methods=["post"])
    def suspender(self, request, pk=None):
        """
        Suspende una medicación vigente y lo asienta en la evolución.

        Sin esto el estado sólo podía crecer: a los dos años el paciente crónico
        tenía veinte recetas «Activas» superpuestas y no había manera de saber
        cuál era el tratamiento vigente. Suspender es un acto clínico de todos
        los días —se rota el antibiótico, se corta el anticoagulante antes de una
        cirugía—, así que va a la historia y no sólo a un booleano.
        """
        receta = self.get_object()
        motivo = (request.data.get("motivo") or "").strip()
        if not motivo:
            raise drf_serializers.ValidationError({
                "motivo": "Decí por qué se suspende: es lo que va a leer quien retome el tratamiento."
            })
        if not receta.activa:
            raise reglas.ReglaClinica("Esta receta ya estaba suspendida.")

        institucion = receta.historia.ciudadano.institucion
        reglas.exigir_clinico(institucion, request.user)
        # La matrícula del legajo si la hay. La entrada se firma igual: es un
        # asiento que arma el sistema con contenido fijo, no texto que alguien
        # escribió a nombre de otro, y el sello cubre la matrícula, así que lo
        # que quedó registrado se puede verificar tal como quedó.
        matricula = (getattr(getattr(request.user, "legajo", None), "matricula", "") or "").strip()

        with transaction.atomic():
            receta.activa = False
            receta.save(update_fields=["activa"])
            entrada = EntradaHistoria.objects.create(
                historia=receta.historia,
                titulo="Medicación suspendida",
                contenido=f"{receta.detalle}\nMotivo: {motivo}",
                autor=request.user,
                firmada=True,
                matricula=matricula,
            )
            integridad.sellar(entrada)

        return Response(self.get_serializer(receta).data)


class ConsentimientoDatosViewSet(AuditaLecturaClinica, BaseModelViewSet):
    """
    Consentimiento del paciente para el tratamiento de sus datos (Ley 25.326).

    Se agregan registros; no se editan ni se borran. Una revocación es una fila
    NUEVA con `otorgado=False`: lo que vale ante un reclamo es el historial —qué
    se consintió y cuándo—, no el estado de hoy.
    """

    queryset = ConsentimientoDatos.objects.select_related("ciudadano", "tomado_por")
    serializer_class = ConsentimientoDatosSerializer
    capacidad_requerida = "padron_admision"
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
