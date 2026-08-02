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

    class Meta:
        model = Existencia
        fields = [
            "id", "deposito", "deposito_nombre", "insumo", "insumo_nombre", "unidad",
            "lote", "lote_numero", "vencimiento", "vencido", "cantidad", "stock_minimo",
            "actualizado",
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

    class Meta:
        model = Movimiento
        fields = [
            "id", "tipo", "tipo_display", "insumo", "insumo_nombre", "lote", "lote_numero",
            "origen", "origen_nombre", "destino", "destino_nombre", "cantidad",
            "caso", "paciente", "motivo", "autor_nombre", "fecha",
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

    def create(self, validated):
        items = validated.pop("items", [])
        pedido = super().create(validated)
        for it in items:
            try:
                LineaPedido.objects.create(
                    pedido=pedido, insumo_id=int(it["insumo"]), pedido_cant=int(it["cantidad"])
                )
            except (KeyError, TypeError, ValueError):
                raise serializers.ValidationError(
                    {"items": "Cada renglón necesita `insumo` y `cantidad`."}
                )
        return pedido

    def validate(self, attrs):
        origen = attrs.get("origen", getattr(self.instance, "origen", None))
        destino = attrs.get("destino", getattr(self.instance, "destino", None))
        if origen and destino and origen.id == destino.id:
            raise serializers.ValidationError(
                {"destino": "Un depósito no se puede pedir a sí mismo."}
            )
        return attrs
