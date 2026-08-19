from rest_framework import serializers

from apps.accounts.models import Membresia

from .models import Agenda, Bloqueo, Disponibilidad, Turno


class DisponibilidadSerializer(serializers.ModelSerializer):
    dia_display = serializers.CharField(source="get_dia_semana_display", read_only=True)
    paso_min = serializers.IntegerField(read_only=True)
    # Los dos calculados que la pantalla necesita para dibujar la franja sin
    # tener que saber las reglas: los sobreturnos que rigen de verdad (los de la
    # franja o los de la agenda) y cuántos turnos ofrece.
    tope_sobreturnos = serializers.IntegerField(read_only=True)
    cuantos_turnos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Disponibilidad
        fields = [
            "id", "agenda", "dia_semana", "dia_display", "desde", "hasta",
            "duracion_min", "paso_min", "cupos", "sobreturnos_max", "tope_sobreturnos",
            "cuantos_turnos", "vigente_desde", "vigente_hasta", "activa",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["agenda"].read_only = True

    def validate_cupos(self, valor):
        # Cero cupos es una franja que se dibuja en la pantalla y no da ningún
        # turno: para eso está `activa=False`, que además lo dice.
        if valor < 1:
            raise serializers.ValidationError("Tiene que haber al menos una persona por horario.")
        return valor

    def validate(self, attrs):
        def dato(nombre):
            return attrs.get(nombre, getattr(self.instance, nombre, None))

        desde, hasta = dato("desde"), dato("hasta")
        if desde and hasta and hasta <= desde:
            raise serializers.ValidationError(
                {"hasta": "La franja tiene que terminar después de empezar."}
            )
        duracion = dato("duracion_min")
        if duracion is not None and duracion < 1:
            raise serializers.ValidationError({"duracion_min": "La duracion debe ser mayor que cero."})
        vigente_desde, vigente_hasta = dato("vigente_desde"), dato("vigente_hasta")
        if vigente_desde and vigente_hasta and vigente_hasta < vigente_desde:
            raise serializers.ValidationError(
                {"vigente_hasta": "La vigencia hasta no puede ser anterior a la vigencia desde."}
            )
        agenda = dato("agenda")
        if agenda and desde and hasta:
            # La franja no se guarda todavía: se arma una en memoria para poder
            # preguntarle al modelo si choca, y así la regla vive en un solo lado.
            propuesta = Disponibilidad(
                agenda=agenda, dia_semana=dato("dia_semana"), desde=desde, hasta=hasta,
                vigente_desde=dato("vigente_desde"), vigente_hasta=dato("vigente_hasta"),
            )
            otras = agenda.disponibilidades.filter(dia_semana=propuesta.dia_semana, activa=True)
            if self.instance is not None:
                otras = otras.exclude(pk=self.instance.pk)
            # Dos franjas del mismo día que se pisan no dan más turnos: la grilla
            # se queda con la primera que genera cada horario y la otra
            # desaparece sin avisar, así que la agenda ofrece algo distinto de lo
            # que la pantalla de configuración muestra.
            choque = next((o for o in otras if propuesta.choca_con(o)), None)
            if choque is not None:
                raise serializers.ValidationError({
                    "desde": (
                        f"Se pisa con la franja de {choque.desde:%H:%M} a {choque.hasta:%H:%M} "
                        f"del mismo día."
                    )
                })
        return attrs


class BloqueoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bloqueo
        fields = ["id", "agenda", "desde", "hasta", "motivo", "creado"]
        read_only_fields = ["creado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["agenda"].read_only = True

    def validate(self, attrs):
        desde = attrs.get("desde", getattr(self.instance, "desde", None))
        hasta = attrs.get("hasta", getattr(self.instance, "hasta", None))
        if desde and hasta and hasta <= desde:
            raise serializers.ValidationError({"hasta": "El bloqueo tiene que terminar después de empezar."})
        return attrs


class AgendaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    modalidad_display = serializers.CharField(source="get_modalidad_display", read_only=True)
    area_nombre = serializers.CharField(source="area.nombre", read_only=True)
    profesional_nombre = serializers.SerializerMethodField()
    flujo_titulo = serializers.CharField(source="flujo.titulo", read_only=True, default=None)
    disponibilidades = DisponibilidadSerializer(many=True, read_only=True)

    class Meta:
        model = Agenda
        fields = [
            "id", "institucion", "area", "area_nombre", "tipo", "tipo_display", "nombre",
            "profesional", "profesional_nombre", "flujo", "flujo_titulo",
            "modalidad", "modalidad_display", "enlace_virtual",
            "duracion_min", "sobreturnos_max", "activa", "creada", "disponibilidades",
        ]
        read_only_fields = ["creada"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["institucion"].read_only = True
            self.fields["area"].read_only = True

    def get_profesional_nombre(self, obj) -> str | None:
        return obj.profesional.nombre_completo if obj.profesional_id else None

    def validate(self, attrs):
        # Una agenda de recurso con profesional asignado, o una de profesional
        # sin nadie, son configuraciones que después no se pueden operar: el
        # caso no sabría a quién asignarse.
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", Agenda.Tipo.PROFESIONAL))
        institucion = attrs.get("institucion", getattr(self.instance, "institucion", None))
        area = attrs.get("area", getattr(self.instance, "area", None))
        if area and institucion and area.institucion_id != institucion.id:
            raise serializers.ValidationError({"area": "El area de la agenda debe pertenecer a la institucion."})
        prof = attrs.get("profesional", getattr(self.instance, "profesional", None))
        activa = attrs.get("activa", getattr(self.instance, "activa", True))
        if tipo == Agenda.Tipo.RECURSO and prof:
            raise serializers.ValidationError(
                {"profesional": "Una agenda de recurso no lleva profesional."}
            )
        if tipo == Agenda.Tipo.PROFESIONAL and activa and not prof:
            raise serializers.ValidationError(
                {"profesional": "Una agenda profesional necesita un profesional asignado."}
            )
        if prof and institucion and not Membresia.objects.filter(
            usuario=prof, institucion=institucion, activo=True
        ).exists():
            raise serializers.ValidationError(
                {"profesional": "El profesional no pertenece a esta institucion."}
            )
        flujo = attrs.get("flujo", getattr(self.instance, "flujo", None))
        if flujo and institucion and flujo.institucion_id != institucion.id:
            raise serializers.ValidationError({"flujo": "El flujo no pertenece a esta institucion."})
        # Una sala guardada en una agenda presencial no se muestra en ninguna
        # pantalla y no se copia a ningún turno, pero queda ahí: el día que
        # alguien pase la agenda a virtual hereda un link viejo sin haberlo
        # elegido. Se limpia al pasar a presencial en vez de rechazar el guardado
        # —quien está cambiando la modalidad no tiene por qué borrar el campo a
        # mano para poder guardar—.
        modalidad = attrs.get("modalidad", getattr(self.instance, "modalidad", None))
        if modalidad == Agenda.Modalidad.PRESENCIAL:
            attrs["enlace_virtual"] = ""
        return attrs


class TurnoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    modalidad_display = serializers.CharField(source="get_modalidad_display", read_only=True)
    agenda_nombre = serializers.CharField(source="agenda.nombre", read_only=True)
    # La modalidad de la AGENDA, no la del turno: es lo que dice si este turno
    # se puede pasar a video. Sin esto, la pantalla que atiende el teléfono
    # —donde el pedido llega— tendría que ir a buscar la agenda por su cuenta.
    agenda_modalidad = serializers.CharField(source="agenda.modalidad", read_only=True)
    area_nombre = serializers.CharField(source="agenda.area.nombre", read_only=True)
    paciente = serializers.SerializerMethodField()
    documento = serializers.CharField(source="ciudadano.documento", read_only=True)
    fin = serializers.DateTimeField(read_only=True)
    resuelto_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Turno
        fields = [
            "id", "agenda", "agenda_nombre", "agenda_modalidad", "area_nombre",
            "ciudadano", "paciente",
            "documento", "inicio", "fin", "duracion_min", "estado", "estado_display",
            "sobreturno", "modalidad", "modalidad_display", "enlace",
            "motivo", "origen", "caso", "observaciones",
            "recordado_at", "cancelado_at", "creado",
            "resuelto_por", "resuelto_por_nombre", "resuelto_at",
        ]
        # El estado se mueve con las acciones (`cancelar`, `llegada`, `ausente`),
        # que además de cambiarlo abren el caso o liberan el horario. Por PATCH
        # se podría marcar «presente» sin que exista el caso.
        #
        # `inicio`, `agenda` y `ciudadano` también: el alta pasa por
        # `motor.reservar` y el cambio de horario por `motor.reprogramar`, que
        # validan la grilla, los bloqueos y la ocupación bajo candado. Editables
        # por PATCH, un «reprogramar» hecho de la forma obvia apilaba dos
        # titulares en la misma hora —invisibles en la grilla—, y además dejaba
        # mover el turno a una agenda o a un paciente de OTRA institución, con la
        # respuesta devolviendo nombre y documento de esa persona.
        #
        # `modalidad` y `enlace` también: pasar un turno a virtual tiene que
        # copiar la sala de la agenda y comprobar que la agenda atienda de esa
        # forma, y eso vive en `motor.cambiar_modalidad`. Por PATCH se dejaba un
        # turno «virtual» sin ningún enlace en una agenda que sólo atiende en el
        # consultorio: el paciente no viene y espera una llamada que no existe.
        read_only_fields = [
            "estado", "agenda", "ciudadano", "inicio", "caso", "duracion_min", "sobreturno",
            "modalidad", "enlace",
            "recordado_at", "cancelado_at", "creado", "resuelto_por", "resuelto_at",
        ]

    def get_paciente(self, obj) -> str | None:
        c = obj.ciudadano
        return f"{c.nombre} {c.apellido}".strip() if c else None

    def get_resuelto_por_nombre(self, obj) -> str | None:
        return obj.resuelto_por.nombre_completo if obj.resuelto_por_id else None
