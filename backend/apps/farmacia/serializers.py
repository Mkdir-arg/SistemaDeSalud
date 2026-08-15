from django.db import transaction
from rest_framework import serializers

from .models import Deposito, Existencia, Insumo, LineaPedido, Lote, Movimiento, Pedido


class InsumoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    # Cuánto hay en toda la institución. Para decidir si falta hay que mirar por
    # depósito (`/stock/`), pero para el catálogo alcanza con el total.
    total = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Insumo
        fields = [
            "id", "institucion", "codigo", "nombre", "generico", "tipo", "tipo_display",
            "presentacion", "unidad", "requiere_lote", "controlado", "stock_minimo",
            "activo", "creado", "total",
        ]
        read_only_fields = ["creado"]


class DepositoSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source="area.nombre", read_only=True, default=None)

    class Meta:
        model = Deposito
        fields = ["id", "institucion", "area", "area_nombre", "nombre", "central", "activo"]


class LoteSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.__str__", read_only=True)
    vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lote
        fields = ["id", "insumo", "insumo_nombre", "numero", "vencimiento", "vencido"]


class ExistenciaSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.__str__", read_only=True)
    unidad = serializers.CharField(source="insumo.unidad", read_only=True)
    deposito_nombre = serializers.CharField(source="deposito.nombre", read_only=True)
    lote_numero = serializers.CharField(source="lote.numero", read_only=True, default=None)
    vencimiento = serializers.DateField(source="lote.vencimiento", read_only=True, default=None)
    vencido = serializers.SerializerMethodField()
    stock_minimo = serializers.IntegerField(source="insumo.stock_minimo", read_only=True)
    # Viaja con cada fila porque el recuento de estupefacientes se hace mirando
    # esta lista: sin la marca, la morfina se lee igual que una gasa y quien
    # cuenta a la mañana tiene que saber de memoria cuáles exigen doble firma.
    controlado = serializers.BooleanField(source="insumo.controlado", read_only=True)

    class Meta:
        model = Existencia
        fields = [
            "id", "deposito", "deposito_nombre", "insumo", "insumo_nombre", "unidad",
            "lote", "lote_numero", "vencimiento", "vencido", "cantidad", "stock_minimo",
            "controlado", "actualizado",
        ]
        # Se mueve con los movimientos; escribirla a mano rompería la única cosa
        # que el módulo garantiza: que el stock se explique por su historial.
        read_only_fields = fields

    def get_vencido(self, obj) -> bool:
        return bool(obj.lote_id and obj.lote.vencido)


class MovimientoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    insumo_nombre = serializers.CharField(source="insumo.__str__", read_only=True)
    lote_numero = serializers.CharField(source="lote.numero", read_only=True, default=None)
    origen_nombre = serializers.CharField(source="origen.nombre", read_only=True, default=None)
    destino_nombre = serializers.CharField(source="destino.nombre", read_only=True, default=None)
    paciente = serializers.SerializerMethodField()
    autor_nombre = serializers.SerializerMethodField()
    # Quien revisa el historial tiene que poder ver cuáles renglones van al libro
    # de la Ley 19.303; sin el campo, hay que saberlos de memoria (y el CSV
    # tampoco los distinguía).
    controlado = serializers.BooleanField(source="insumo.controlado", read_only=True)

    class Meta:
        model = Movimiento
        fields = [
            "id", "tipo", "tipo_display", "insumo", "insumo_nombre", "controlado",
            "lote", "lote_numero", "origen", "origen_nombre", "destino", "destino_nombre",
            "cantidad", "caso", "paciente", "motivo", "autor_nombre", "fecha",
        ]
        # Un movimiento no se edita: un error se corrige con otro movimiento. Un
        # historial reescribible no sirve para auditar.
        read_only_fields = fields

    def get_paciente(self, obj) -> str | None:
        c = getattr(obj.caso, "ciudadano", None) if obj.caso_id else None
        return f"{c.nombre} {c.apellido}".strip() if c else None

    def get_autor_nombre(self, obj) -> str | None:
        return obj.autor.nombre_completo if obj.autor_id else None


class LineaPedidoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.__str__", read_only=True)
    unidad = serializers.CharField(source="insumo.unidad", read_only=True)
    faltante = serializers.IntegerField(read_only=True)

    class Meta:
        model = LineaPedido
        fields = ["id", "pedido", "insumo", "insumo_nombre", "unidad",
                  "pedido_cant", "entregado", "faltante"]
        read_only_fields = ["entregado"]


class PedidoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    origen_nombre = serializers.CharField(source="origen.nombre", read_only=True)
    destino_nombre = serializers.CharField(source="destino.nombre", read_only=True)
    lineas = LineaPedidoSerializer(many=True, read_only=True)
    # Renglones al crear: un pedido sin líneas no es un pedido, y obligar a
    # crearlo vacío y después cargarlas deja pedidos huérfanos si alguien
    # abandona a la mitad.
    items = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Pedido
        fields = [
            "id", "origen", "origen_nombre", "destino", "destino_nombre", "estado",
            "estado_display", "urgente", "observaciones", "creado", "resuelto",
            "lineas", "items",
        ]
        read_only_fields = ["estado", "creado", "resuelto"]

    @transaction.atomic
    def create(self, validated):
        # Atómico: sin esto, un renglón que fallaba dejaba el Pedido ya
        # commiteado y sin líneas. La central lo veía en su cola sin poder
        # entregarlo ni saber para qué era, y cada request mal armado sumaba uno
        # más a la lista donde se decide qué preparar.
        items = validated.pop("items", [])
        pedido = super().create(validated)
        LineaPedido.objects.bulk_create([
            LineaPedido(pedido=pedido, insumo=it["insumo"], pedido_cant=it["cantidad"])
            for it in items
        ])
        return pedido

    def validate(self, attrs):
        origen = attrs.get("origen", getattr(self.instance, "origen", None))
        destino = attrs.get("destino", getattr(self.instance, "destino", None))
        if origen and destino:
            if origen.id == destino.id:
                raise serializers.ValidationError(
                    {"destino": "Un depósito no se puede pedir a sí mismo."}
                )
            # El permiso del alta se resuelve por `origen__institucion`, o sea
            # contra el depósito propio: sin este chequeo, alguien del hospital A
            # pedía 25 ampollas a la central del hospital B y se las llevaba. B no
            # ve de dónde salió el movimiento, sólo que el número no coincide con
            # el estante.
            if origen.institucion_id != destino.institucion_id:
                raise serializers.ValidationError(
                    {"destino": "Ese depósito es de otra institución."}
                )
        if "items" in attrs:
            attrs["items"] = self._renglones(attrs["items"], origen)
        return attrs

    def _renglones(self, items, origen):
        """
        Los renglones resueltos a objetos, antes de crear nada.

        Resolverlos acá y no en `create` es lo que hace que un pedido mal armado
        sea un 400 con el renglón que falla en vez de un pedido a medias en la
        cola de la central (o un 500: un `insumo` inexistente pasaba el `int()` y
        reventaba en la clave foránea).
        """
        insumos = (
            Insumo.objects.filter(institucion_id=origen.institucion_id)
            if origen is not None else Insumo.objects.none()
        )
        salida = []
        for n, it in enumerate(items, start=1):
            try:
                cantidad = int(it["cantidad"])
                numero = int(it["insumo"])
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(
                    {"items": f"El renglón {n} necesita `insumo` y `cantidad`."}
                )
            # Un id fuera del rango del entero de la base revienta en la consulta:
            # sería otro 500 por un pedido mal armado.
            insumo = insumos.filter(pk=numero).first() if 0 < numero < 2 ** 31 else None
            if insumo is None:
                raise serializers.ValidationError(
                    {"items": f"El renglón {n}: ese insumo no es de tu institución."}
                )
            if not 0 < cantidad < 2 ** 31:
                raise serializers.ValidationError(
                    {"items": f"El renglón {n}: la cantidad tiene que ser mayor que cero."}
                )
            salida.append({"insumo": insumo, "cantidad": cantidad})
        return salida
