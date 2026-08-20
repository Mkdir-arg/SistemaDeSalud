from rest_framework import serializers

from .models import Conexion, Flujo, Nodo, VersionFlujo


def _publicada_de(flujo):
    """La versión publicada del flujo, leída de las versiones ya precargadas.

    `Flujo.version_publicada` consulta la base cada vez; acá se recorre lo que el
    prefetch del viewset ya trajo (ordenado por -numero), que es lo que mantiene
    el listado en una cantidad fija de consultas."""
    for v in flujo.versiones.all():
        if v.estado == VersionFlujo.Estado.PUBLICADA:
            return v
    return None


def _vigente_de(flujo):
    """La publicada si existe y, si no, la última por número (la misma regla que
    muestra el listado). También sobre las versiones precargadas."""
    versiones = list(flujo.versiones.all())
    for v in versiones:
        if v.estado == VersionFlujo.Estado.PUBLICADA:
            return v
    return versiones[0] if versiones else None


class NodoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    # Lectura: grupos responsables con nombre y área (para mostrar "quién hace esto").
    grupos_detalle = serializers.SerializerMethodField()

    class Meta:
        model = Nodo
        fields = [
            "id", "version", "tipo", "tipo_display", "titulo", "descripcion",
            "x", "y", "config", "formulario", "grupos", "grupos_detalle",
            "pantalla_token",
        ]
        extra_kwargs = {"grupos": {"required": False}}
        read_only_fields = ["pantalla_token"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["version"].read_only = True

    def validate(self, attrs):
        version = attrs.get("version", getattr(self.instance, "version", None))
        formulario = attrs.get("formulario", getattr(self.instance, "formulario", None))
        if version and formulario and formulario.institucion_id != version.flujo.institucion_id:
            raise serializers.ValidationError(
                {"formulario": "El formulario no pertenece a la institucion del flujo."}
            )

        grupos = attrs.get("grupos")
        if version and grupos:
            fuera = [g.id for g in grupos if g.area.institucion_id != version.flujo.institucion_id]
            if fuera:
                raise serializers.ValidationError(
                    {"grupos": "Todos los grupos del nodo deben pertenecer a la institucion del flujo."}
                )
            inactivos = [g.id for g in grupos if not g.activo or not g.area.activa]
            if inactivos:
                raise serializers.ValidationError(
                    {"grupos": "Todos los grupos del nodo deben estar activos."}
                )
        return attrs

    def get_grupos_detalle(self, obj) -> list[dict]:
        return [
            {"id": g.id, "nombre": g.nombre, "area": g.area_id, "area_nombre": g.area.nombre}
            for g in obj.grupos.filter(activo=True, area__activa=True)
        ]


class ConexionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conexion
        fields = ["id", "version", "origen", "destino", "etiqueta", "condicion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            self.fields["version"].read_only = True

    def validate(self, attrs):
        version = attrs.get("version", getattr(self.instance, "version", None))
        origen = attrs.get("origen", getattr(self.instance, "origen", None))
        destino = attrs.get("destino", getattr(self.instance, "destino", None))
        if version and origen and origen.version_id != version.id:
            raise serializers.ValidationError({"origen": "El nodo origen no pertenece a esta version."})
        if version and destino and destino.version_id != version.id:
            raise serializers.ValidationError({"destino": "El nodo destino no pertenece a esta version."})
        return attrs


class VersionFlujoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    etiqueta = serializers.CharField(read_only=True)
    nodos = NodoSerializer(many=True, read_only=True)
    conexiones = ConexionSerializer(many=True, read_only=True)

    class Meta:
        model = VersionFlujo
        fields = [
            "id", "flujo", "numero", "etiqueta", "estado", "estado_display",
            "nota", "autor", "creada", "nodos", "conexiones",
        ]
        # `estado` NO es un campo, es una transición con reglas: la única puerta
        # para publicar es la acción `publicar`, que valida el grafo y degrada a
        # la publicada anterior. Con `estado` escribible, un PATCH marcaba como
        # publicada una versión sin nodo Inicio: el badge decía «Publicado» y
        # cada caso nuevo moría en `iniciar()`.
        read_only_fields = ["creada", "estado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ya creada, `flujo` y `numero` tampoco se tocan: mover una versión de
        # flujo o renumerarla deja a los casos en curso —que apuntan a esta
        # fila— corriendo un proceso que no es el suyo.
        if self.instance is not None:
            for campo in ("flujo", "numero"):
                self.fields[campo].read_only = True


class VersionFlujoResumenSerializer(serializers.ModelSerializer):
    """Versión sin el grafo, para listados anidados en Flujo."""

    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    etiqueta = serializers.CharField(read_only=True)

    class Meta:
        model = VersionFlujo
        fields = ["id", "numero", "etiqueta", "estado", "estado_display", "creada"]


class FlujoSerializer(serializers.ModelSerializer):
    versiones = VersionFlujoResumenSerializer(many=True, read_only=True)
    area_nombre = serializers.SerializerMethodField()
    subarea_nombre = serializers.SerializerMethodField()
    ambito = serializers.CharField(read_only=True)
    ambito_label = serializers.SerializerMethodField()
    # Cómo entran los casos a este flujo (config del nodo Inicio publicado):
    # "manual" | "derivado" | "ambos". Por defecto "ambos" (compatibilidad).
    origen_inicio = serializers.SerializerMethodField()
    casos_activos = serializers.SerializerMethodField()

    class Meta:
        model = Flujo
        fields = [
            "id", "institucion", "area", "area_nombre", "subarea", "subarea_nombre",
            "ambito", "ambito_label", "origen_inicio", "titulo", "descripcion", "creado", "versiones", "casos_activos",
        ]
        read_only_fields = ["creado"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            for campo in ("institucion", "area", "subarea"):
                self.fields[campo].read_only = True

    def get_origen_inicio(self, obj) -> str:
        # Se resuelve sobre las versiones YA precargadas: `obj.version_publicada`
        # hace `.filter()` sobre el related manager, que arma un queryset nuevo y
        # anula el prefetch del viewset — una consulta por flujo, y este listado
        # lo abren también las pantallas de ejecución.
        ver = _publicada_de(obj)
        if not ver:
            return "ambos"
        # `is None` y no `or`: el `to_attr` del prefetch existe siempre y una
        # versión sin nodo Inicio lo trae en `[]`, que es falsy — con `or` esa
        # versión volvía a consultar la base, una vez por flujo.
        inicios = getattr(ver, "nodos_inicio", None)
        if inicios is None:
            inicios = ver.nodos.filter(tipo="inicio")[:1]
        inicio = next(iter(inicios), None)
        return (inicio.config or {}).get("origen", "ambos") if inicio else "ambos"

    def validate(self, attrs):
        # `area` se deriva de `subarea`; si vienen ambas, deben ser coherentes.
        institucion = attrs.get("institucion", getattr(self.instance, "institucion", None))
        subarea = attrs.get("subarea", getattr(self.instance, "subarea", None))
        area = attrs.get("area", getattr(self.instance, "area", None))
        if area and institucion and area.institucion_id != institucion.id:
            raise serializers.ValidationError({"area": "El area no pertenece a esta institucion."})
        if subarea and institucion and subarea.area.institucion_id != institucion.id:
            raise serializers.ValidationError(
                {"subarea": "La subarea no pertenece a esta institucion."}
            )
        if subarea and area and subarea.area_id != area.id:
            raise serializers.ValidationError({"subarea": "La sub-área no pertenece al área indicada."})
        return attrs

    def get_area_nombre(self, obj) -> str | None:
        return obj.area.nombre if obj.area_id else "Institución"

    def get_subarea_nombre(self, obj) -> str | None:
        return obj.subarea.nombre if obj.subarea_id else None

    def get_ambito_label(self, obj) -> str:
        if obj.subarea_id:
            return f"{obj.area.nombre} › {obj.subarea.nombre}"
        if obj.area_id:
            return obj.area.nombre
        return "Institución"

    def get_casos_activos(self, obj) -> int:
        # El viewset lo trae anotado en la misma consulta del listado. El conteo
        # suelto queda como salida para los usos fuera del listado (por ejemplo
        # el flujo recién duplicado, que todavía no pasó por el queryset).
        anotado = getattr(obj, "casos_activos_anot", None)
        if anotado is not None:
            return anotado
        from apps.casos.models import Caso
        return Caso.objects.filter(version__flujo=obj).exclude(estado__in=Caso.ESTADOS_FINALIZADOS).count()
