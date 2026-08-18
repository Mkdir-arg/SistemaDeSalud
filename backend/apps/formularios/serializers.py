from rest_framework import serializers

from .models import Campo, Formulario


class CampoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    vinculado = serializers.BooleanField(read_only=True)
    valores_cargados = serializers.SerializerMethodField()

    class Meta:
        model = Campo
        fields = [
            "id", "formulario", "label", "tipo", "tipo_display", "requerido",
            "ayuda", "opciones", "unidad", "minimo", "maximo", "origen", "orden",
            "vinculado", "valores_cargados",
        ]

    def get_valores_cargados(self, obj) -> int:
        """Cuántos datos de casos reales dependen de este campo.

        Lo necesita la pantalla para decir la verdad antes de quitarlo: el
        diálogo prometía que «los datos ya cargados no se borran» y el borrado
        arrastraba en cascada todos los ValorCampo."""
        n = getattr(obj, "valores_n", None)
        return n if n is not None else obj.valores.count()

    def validate(self, attrs):
        """Un campo que no se puede completar no sirve para nada.

        Se valida acá y no sólo en la pantalla porque un campo mal definido no
        falla al guardarse: falla más tarde, cuando el administrativo tiene el
        paciente delante y el desplegable está vacío, o cuando la Decisión que
        compara ese número recibe texto libre. Con PATCH parcial el valor
        efectivo sale de `attrs` o, si no vino, de lo que ya tiene el campo.
        """
        def efectivo(k, default=None):
            return attrs[k] if k in attrs else getattr(self.instance, k, default)

        tipo = efectivo("tipo")

        if tipo == Campo.Tipo.SELECCION_UNICA:
            # Sólo cuando se están tocando las opciones o el tipo: un formulario
            # viejo puede tener una selección única sin opciones, y exigirlas en
            # cualquier PATCH impediría lo único que la arregla —entrar a editar
            # el campo— por corregir la etiqueta de al lado.
            if self.instance is None or "opciones" in attrs or "tipo" in attrs:
                opciones = [str(o).strip() for o in (efectivo("opciones") or []) if str(o).strip()]
                if not opciones:
                    raise serializers.ValidationError({
                        "opciones": "Una selección única sin opciones es un desplegable "
                                    "vacío: agregá al menos una."
                    })
                if len(set(opciones)) != len(opciones):
                    raise serializers.ValidationError({
                        "opciones": "Hay opciones repetidas. Dos opciones iguales son "
                                    "indistinguibles para quien completa y para las Decisiones."
                    })
        elif "tipo" in attrs or "opciones" in attrs:
            # Un campo que dejó de ser selección se queda con opciones que ya no
            # se muestran en ningún lado y que las Decisiones siguen ofreciendo
            # como valores posibles de una lista cerrada que no existe.
            attrs["opciones"] = []

        if tipo == Campo.Tipo.NUMERO:
            minimo, maximo = efectivo("minimo"), efectivo("maximo")
            if minimo is not None and maximo is not None and minimo > maximo:
                raise serializers.ValidationError({
                    "maximo": "El máximo no puede ser menor que el mínimo: así definido, "
                              "ningún valor entraría."
                })
        elif "tipo" in attrs:
            # Unidad y rango sólo tienen sentido en un número: dejarlos puestos en
            # un campo de texto es una promesa que ninguna capa valida. Se limpian
            # en vez de rechazar el cambio, que es legítimo.
            attrs["unidad"], attrs["minimo"], attrs["maximo"] = "", None, None
        return attrs


class UsoFormularioSerializer(serializers.Serializer):
    """Un paso de un flujo que pide este formulario (ver `FormularioViewSet.usos`)."""

    flujo_id = serializers.IntegerField()
    flujo = serializers.CharField()
    version_id = serializers.IntegerField()
    version_numero = serializers.IntegerField()
    version_estado = serializers.CharField()
    nodo_id = serializers.IntegerField()
    nodo_titulo = serializers.CharField()
    casos_activos = serializers.IntegerField()


class CondicionQueUsaCampoSerializer(serializers.Serializer):
    """Una rama de Decisión cuya condición menciona un campo de este formulario."""

    campo_id = serializers.IntegerField()
    flujo = serializers.CharField()
    version_estado = serializers.CharField()
    desde = serializers.CharField()
    hasta = serializers.CharField()
    etiqueta = serializers.CharField()


class FormularioSerializer(serializers.ModelSerializer):
    campos = CampoSerializer(many=True, read_only=True)
    area_nombre = serializers.SerializerMethodField()
    # Cuántos flujos piden este formulario. Va en el LISTADO porque «se usa o no
    # se usa» es lo primero que hay que saber antes de tocarlo o de borrarlo, y
    # hasta ahora la única forma de averiguarlo era abrir los flujos de a uno.
    usos_n = serializers.SerializerMethodField()

    class Meta:
        model = Formulario
        fields = [
            "id", "institucion", "area", "area_nombre", "titulo", "descripcion",
            "creado", "campos", "usos_n",
        ]
        read_only_fields = ["creado"]

    def get_area_nombre(self, obj) -> str:
        return obj.area.nombre if obj.area_id else "Toda la institución"

    def get_usos_n(self, obj) -> int:
        n = getattr(obj, "usos_n_anotado", None)
        return n if n is not None else obj.nodos.values("version__flujo").distinct().count()

    def validate(self, attrs):
        """El área tiene que ser de la misma institución que el formulario.

        Un formulario cuya área pertenece a otro hospital aparece en el filtro
        por área de una institución que no lo puede usar, y el nodo que lo elija
        va a pedir datos de un circuito ajeno."""
        institucion = attrs.get("institucion", getattr(self.instance, "institucion", None))
        area = attrs.get("area", getattr(self.instance, "area", None))
        if area and institucion and area.institucion_id != institucion.id:
            raise serializers.ValidationError({"area": "El área no pertenece a esta institución."})
        return attrs
