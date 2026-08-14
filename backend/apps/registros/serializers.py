from rest_framework import serializers

from .models import Ciudadano, ConsentimientoDatos, EntradaHistoria, Estudio, HistoriaClinica, Receta


class EntradaHistoriaSerializer(serializers.ModelSerializer):
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
        read_only_fields = ["fecha", "matricula", "firmada_at", "sello"]

    def get_integra(self, obj) -> bool | None:
        from .integridad import verificar

        return verificar(obj)["ok"]


class EstudioSerializer(serializers.ModelSerializer):
    resultado_display = serializers.CharField(source="get_resultado_display", read_only=True)

    class Meta:
        model = Estudio
        fields = ["id", "historia", "tipo", "resultado", "resultado_display", "realizado", "archivo", "autor", "fecha"]


class RecetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receta
        fields = ["id", "historia", "detalle", "activa", "autor", "fecha"]
        read_only_fields = ["fecha"]


class HistoriaClinicaSerializer(serializers.ModelSerializer):
    entradas = EntradaHistoriaSerializer(many=True, read_only=True)
    estudios = EstudioSerializer(many=True, read_only=True)
    recetas = RecetaSerializer(many=True, read_only=True)

    class Meta:
        model = HistoriaClinica
        fields = [
            "id", "ciudadano", "alergias", "condiciones", "creada",
            "entradas", "estudios", "recetas",
        ]
        read_only_fields = ["creada"]


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

    def get_consentimiento(self, obj) -> dict | None:
        c = obj.consentimientos.order_by("-momento", "-id").first()
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

    def _hc(self, obj):
        return getattr(obj, "historia_clinica", None)

    def get_condiciones(self, obj) -> str:
        hc = self._hc(obj)
        return hc.condiciones if hc else ""

    def get_alergias(self, obj) -> str:
        hc = self._hc(obj)
        return hc.alergias if hc else ""

    def get_entradas(self, obj) -> list[dict]:
        hc = self._hc(obj)
        return hc.entradas.count() if hc else 0

    def get_estudios(self, obj) -> list[dict]:
        hc = self._hc(obj)
        return hc.estudios.count() if hc else 0

    def get_recetas_activas(self, obj) -> list[dict]:
        hc = self._hc(obj)
        return hc.recetas.filter(activa=True).count() if hc else 0

    def get_ultima(self, obj) -> dict | None:
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
