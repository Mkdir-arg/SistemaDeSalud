from datetime import datetime

from rest_framework import serializers

from apps.common import capacidades_de

from . import reglas
from .models import (
    Ciudadano, ConsentimientoDatos, EntradaHistoria, Estudio, HistoriaClinica, Receta,
    normalizar_documento,
)


class HistoriaFija:
    """
    La historia se elige al crear y no cambia después.

    Vale para todo lo que cuelga del expediente: una atención, un estudio. Con la
    FK abierta, un PATCH `{"historia": otra}` mueve el asiento a la ficha de otra
    persona —al paciente que lo generó le falta de su evolución y al otro le
    sobra—, y si después alguien lo firma, el sello certifica esa ubicación
    equivocada como correcta. El permiso no ayuda: se valida contra el objeto
    viejo, así que el destino ni se mira.

    Un registro cargado en la historia equivocada se corrige con uno nuevo en la
    correcta, igual que una entrada firmada.
    """

    def validate(self, datos):
        datos = super().validate(datos)
        nueva = datos.get("historia")
        if self.instance is not None and nueva is not None and nueva.pk != self.instance.historia_id:
            raise serializers.ValidationError({
                "historia": "Un registro no cambia de paciente. Cargalo en la historia "
                            "correcta y dejá asentado el error en la que lo tenía."
            })
        return datos


class EntradaHistoriaSerializer(HistoriaFija, serializers.ModelSerializer):
    # Quién firmó, no sólo su id. Una entrada marcada como «Firmada» sin firmante
    # visible no sirve como registro: la matrícula ya se guarda al firmar, y el
    # nombre evita que el cliente tenga que cruzar contra /usuarios/.
    autor_nombre = serializers.CharField(source="autor.nombre_completo", read_only=True, default=None)
    # Si la entrada dice hoy lo mismo que cuando se firmó. `null` = firmada antes
    # de que existiera el sellado: no se puede afirmar ni lo uno ni lo otro, y
    # decir «intacta» sin poder probarlo sería peor que no decir nada.
    integra = serializers.SerializerMethodField()

    class Meta:
        model = EntradaHistoria
        fields = [
            "id", "historia", "titulo", "contenido", "autor", "autor_nombre",
            "caso", "firmada", "matricula", "fecha", "firmada_at", "sello", "integra",
        ]
        # El sello no se escribe desde afuera: lo calcula el sistema al firmar, y
        # poder mandarlo permitiría sellar contenido alterado.
        #
        # `autor` tampoco: quién atendió sale de la sesión. Mandarlo en el cuerpo
        # permitía dejar un «Alta médica» firmado a nombre de una médica que
        # nunca vio al paciente.
        read_only_fields = ["fecha", "matricula", "firmada_at", "sello", "autor"]

    def get_integra(self, obj) -> bool | None:
        from .integridad import verificar

        return verificar(obj)["ok"]


class EstudioSerializer(HistoriaFija, serializers.ModelSerializer):
    resultado_display = serializers.CharField(source="get_resultado_display", read_only=True)

    class Meta:
        model = Estudio
        fields = ["id", "historia", "tipo", "resultado", "resultado_display", "realizado", "archivo", "autor", "fecha"]
        # `autor` acá es texto libre: si además se manda desde el cuerpo, quién
        # pidió el estudio es una cadena que nadie puede verificar. Sale de la
        # sesión.
        read_only_fields = ["autor"]


class RecetaSerializer(serializers.ModelSerializer):
    autor_nombre = serializers.CharField(source="autor.nombre_completo", read_only=True, default=None)

    class Meta:
        model = Receta
        fields = ["id", "historia", "detalle", "activa", "autor", "autor_nombre", "fecha"]
        # `autor` sale de la sesión: una receta atribuida a quien no la
        # prescribió no se puede desmentir, porque la receta no lleva sello ni
        # matrícula. `activa` no se escribe directo: suspender una medicación es
        # un acto clínico con motivo, y va por la acción `suspender`.
        read_only_fields = ["fecha", "autor", "activa"]


class HistoriaClinicaSerializer(serializers.ModelSerializer):
    entradas = EntradaHistoriaSerializer(many=True, read_only=True)
    estudios = EstudioSerializer(many=True, read_only=True)
    recetas = RecetaSerializer(many=True, read_only=True)
    # Quién cargó los antecedentes. Con esto la pantalla puede decir «se
    # preguntó y no tiene» en vez de afirmar «sin alergias» sobre un paciente al
    # que nunca se le preguntó.
    antecedentes_por_nombre = serializers.CharField(
        source="antecedentes_por.nombre_completo", read_only=True, default=None
    )

    class Meta:
        model = HistoriaClinica
        fields = [
            "id", "ciudadano", "alergias", "condiciones", "creada",
            "antecedentes_por", "antecedentes_por_nombre", "antecedentes_at",
            "entradas", "estudios", "recetas",
        ]
        # Quién y cuándo los cargó lo pone el servidor: un antecedente que se
        # puede atribuir a cualquiera no contesta «¿quién preguntó?».
        read_only_fields = ["creada", "antecedentes_por", "antecedentes_at"]

    def validate(self, datos):
        """
        La historia no cambia de dueño. Los antecedentes son lo único editable.

        Un PATCH `{"ciudadano": otro}` —un integrador, un formulario que manda el
        objeto entero— mudaba el expediente completo: el paciente A quedaba sin
        historia y el B con trece atenciones ajenas, y el médico prescribe
        leyendo eso. Peor todavía: el canónico del sello incluye el ciudadano, así
        que `verificar_historia` pasaba a denunciar «el contenido cambió después
        de firmarse» sobre entradas que nadie tocó. Ese falso positivo es el peor
        error posible del módulo: convierte la única prueba de integridad que
        tiene el hospital en una acusación contra sí mismo, y no se puede deshacer
        desde la aplicación.

        Mandar el MISMO ciudadano no es error: el formulario que reenvía el objeto
        entero tiene que seguir funcionando.
        """
        nuevo = datos.get("ciudadano")
        if self.instance is not None and nuevo is not None and nuevo.pk != self.instance.ciudadano_id:
            raise serializers.ValidationError({
                "ciudadano": "Una historia clínica no se puede pasar a otro paciente."
            })
        return datos


class CiudadanoSerializer(serializers.ModelSerializer):
    # Resumen de la historia clínica (para la lista de HC).
    condiciones = serializers.SerializerMethodField()
    alergias = serializers.SerializerMethodField()
    entradas = serializers.SerializerMethodField()
    estudios = serializers.SerializerMethodField()
    recetas_activas = serializers.SerializerMethodField()
    ultima = serializers.SerializerMethodField()
    # Estado del consentimiento (Ley 25.326). Derivado del último registro, no
    # un campo editable: lo que vale es el historial, y un booleano suelto no
    # puede contestar «¿cuándo lo dio?».
    consentimiento = serializers.SerializerMethodField()

    class Meta:
        model = Ciudadano
        fields = [
            "id", "institucion", "codigo", "nombre", "apellido", "documento",
            "fecha_nacimiento", "obra_social", "domicilio", "creado",
            "condiciones", "alergias", "entradas", "estudios", "recetas_activas", "ultima",
            "consentimiento",
        ]
        read_only_fields = ["creado"]
        # DRF arma solo un `UniqueTogetherValidator` desde la constraint del
        # modelo, y contesta «Los campos institucion, documento deben formar un
        # conjunto único» bajo `non_field_errors`. Eso es cierto y no sirve: al
        # administrativo que está cargando al paciente que volvió no le dice a
        # quién corresponde ese documento ni adónde ir. Se desactiva para que la
        # respuesta sea la de `validate`, más abajo.
        validators = []

    def validate_documento(self, valor):
        # Se normaliza ANTES de buscar el duplicado: el filtro de abajo compara
        # cadenas, y con «30.111.222» contra «30111222» guardado no encuentra
        # nada, devuelve 201 y deja al paciente con dos historias clínicas. El
        # DNI con puntos es como está impreso en el documento, o sea lo que el
        # administrativo copia.
        return normalizar_documento(valor)

    def validate(self, datos):
        """
        Frena el alta del mismo documento dos veces en la misma institución.

        La constraint de la base ya lo impide, pero sola devolvería un 500: acá
        se contesta 400 diciendo A QUIÉN corresponde ese documento, que es lo
        único que le sirve al administrativo que lo está cargando —el caso real
        es el paciente que vuelve y no aparece por un error de tipeo del ingreso
        anterior—.

        El paciente sin documento no entra en esta regla: el NN de guardia tiene
        que poder anotarse igual, y varios a la vez.
        """
        documento = (datos.get("documento") if "documento" in datos else getattr(self.instance, "documento", "")) or ""
        institucion = datos.get("institucion") or getattr(self.instance, "institucion", None)
        if not documento.strip() or institucion is None:
            return datos

        otros = Ciudadano.objects.filter(institucion=institucion, documento=documento)
        if self.instance is not None:
            otros = otros.exclude(pk=self.instance.pk)
        existente = otros.first()
        if existente is not None:
            nombre = f"{existente.nombre} {existente.apellido}".strip()
            raise reglas.RegistroDuplicado(
                f"El documento {documento} ya es de {nombre} en esta institución. "
                f"Abrí su historia en vez de crear una copia: cada copia arranca "
                f"su propia historia clínica y no hay forma de fusionarlas."
            )
        return datos

    # Los campos derivados salen de ANOTACIONES del queryset, no de una consulta
    # por fila.
    #
    # Antes cada paciente costaba seis consultas —una por resumen— y el padrón se
    # degradaba solo a medida que la institución lo usaba: con 30 pacientes en la
    # página eran 155 consultas para abrir una pantalla. `CiudadanoViewSet` las
    # anota de una sola vez; acá sólo se leen, con el cálculo viejo de respaldo
    # para cuando el serializer se usa fuera de esa lista —al responder un alta,
    # por ejemplo, donde el objeto recién creado no viene anotado—.

    def get_consentimiento(self, obj) -> dict | None:
        # `all()` y no `order_by()`: cualquier cambio al queryset saltea la
        # precarga y vuelve a consultar por fila. El orden lo pone el Prefetch.
        c = next(iter(obj.consentimientos.all()), None)
        if c is None:
            # Nunca se registró. No es lo mismo que revocado, y confundirlos
            # haría creer que el paciente dijo que no.
            return None
        return {
            "otorgado": c.otorgado,
            "modo": c.modo,
            "momento": c.momento,
            "alcance": c.alcance,
        }

    def _puede_ver_historia(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        cache = getattr(self, "_caps_por_inst", None)
        if cache is None:
            cache = self._caps_por_inst = {}
        inst_id = obj.institucion_id
        if inst_id not in cache:
            cache[inst_id] = capacidades_de(user, inst_id)
        return "historia_clinica" in cache[inst_id]

    def _hc(self, obj):
        if not self._puede_ver_historia(obj):
            return None
        return getattr(obj, "historia_clinica", None)

    def _anotado(self, obj, nombre, calcular):
        valor = getattr(obj, nombre, None)
        return calcular() if valor is None else valor

    def get_condiciones(self, obj) -> str:
        hc = self._hc(obj)
        return hc.condiciones if hc else ""

    def get_alergias(self, obj) -> str:
        hc = self._hc(obj)
        return hc.alergias if hc else ""

    def get_entradas(self, obj) -> int:
        if not self._puede_ver_historia(obj):
            return 0
        hc = self._hc(obj)
        return self._anotado(obj, "_entradas", lambda: hc.entradas.count() if hc else 0)

    def get_estudios(self, obj) -> int:
        if not self._puede_ver_historia(obj):
            return 0
        hc = self._hc(obj)
        return self._anotado(obj, "_estudios", lambda: hc.estudios.count() if hc else 0)

    def get_recetas_activas(self, obj) -> int:
        if not self._puede_ver_historia(obj):
            return 0
        hc = self._hc(obj)
        return self._anotado(
            obj, "_recetas_activas",
            lambda: hc.recetas.filter(activa=True).count() if hc else 0,
        )

    def get_ultima(self, obj) -> datetime | None:
        if not self._puede_ver_historia(obj):
            return None
        if hasattr(obj, "_ultima"):
            return obj._ultima
        hc = self._hc(obj)
        if not hc:
            return None
        e = hc.entradas.order_by("-fecha").first()
        return e.fecha if e else None


class ConsentimientoDatosSerializer(serializers.ModelSerializer):
    paciente = serializers.SerializerMethodField()
    tomado_por_nombre = serializers.SerializerMethodField()
    modo_display = serializers.CharField(source="get_modo_display", read_only=True)

    class Meta:
        model = ConsentimientoDatos
        fields = [
            "id", "ciudadano", "paciente", "otorgado", "modo", "modo_display",
            "alcance", "tomado_por", "tomado_por_nombre", "institucion",
            "momento", "observaciones",
        ]
        # No se edita ni se borra: una revocación es un registro NUEVO, no una
        # corrección del anterior. Poder editarlo dejaría sin poder contestar
        # qué se consintió y cuándo, que es la pregunta de la ley.
        read_only_fields = ["momento", "tomado_por"]

    def get_paciente(self, obj) -> str:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip()

    def get_tomado_por_nombre(self, obj) -> str | None:
        return obj.tomado_por.nombre_completo if obj.tomado_por_id else None
