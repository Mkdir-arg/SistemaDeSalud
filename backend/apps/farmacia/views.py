from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.casos.models import Caso
from apps.common import BaseModelViewSet
from apps.instituciones.models import Institucion

from . import motor
from .models import Deposito, Existencia, Insumo, Lote, Movimiento, Pedido
from .serializers import (
    DepositoSerializer, ExistenciaSerializer, InsumoSerializer, LoteSerializer,
    MovimientoSerializer, PedidoSerializer,
)


def _obj(modelo, valor):
    return modelo.objects.filter(pk=valor).first() if valor else None


class InsumoViewSet(BaseModelViewSet):
    """
    Catálogo de la institución: sólo lo que realmente se usa. Un catálogo
    enorme sin stock hace que buscar sea inútil.
    """

    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    capacidad_requerida = "config"
    institucion_path = "institucion"
    filter_fields = ("institucion", "tipo", "activo", "controlado")
    search_fields = ("nombre", "generico", "codigo")
    ordering_fields = ("nombre", "stock_minimo")
    nombre_csv = "insumos"
    columnas_csv = [
        ("codigo", "Código"),
        ("nombre", "Insumo"),
        ("generico", "Genérico"),
        ("presentacion", "Presentación"),
        ("tipo_display", "Tipo"),
        ("unidad", "Unidad"),
        ("stock_minimo", "Mínimo"),
        ("total", "Stock total"),
    ]

    def get_queryset(self):
        return super().get_queryset().annotate(total=Sum("existencias__cantidad"))


class DepositoViewSet(BaseModelViewSet):
    queryset = Deposito.objects.select_related("area")
    serializer_class = DepositoSerializer
    capacidad_requerida = "config"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "central", "activo")


class LoteViewSet(BaseModelViewSet):
    """Las partidas. Se cargan al recibir mercadería, así que es `trabajo`."""

    queryset = Lote.objects.select_related("insumo")
    serializer_class = LoteSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "insumo__institucion"
    filter_fields = ("insumo", "insumo__institucion")
    search_fields = ("numero",)


class ExistenciaViewSet(BaseModelViewSet):
    """
    El stock. Sólo lectura: se mueve con los movimientos, y poder escribirlo
    rompería lo único que el módulo garantiza —que el número se explique por su
    historial—.
    """

    queryset = Existencia.objects.select_related("deposito", "insumo", "lote")
    serializer_class = ExistenciaSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "deposito__institucion"
    filter_fields = ("deposito", "deposito__institucion", "insumo", "lote")
    search_fields = ("insumo__nombre", "insumo__generico", "lote__numero")
    ordering_fields = ("cantidad", "insumo__nombre")
    http_method_names = ["get", "head", "options"]
    nombre_csv = "stock"
    columnas_csv = [
        ("insumo_nombre", "Insumo"),
        ("deposito_nombre", "Depósito"),
        ("lote_numero", "Lote"),
        ("vencimiento", "Vence"),
        ("cantidad", "Cantidad"),
        ("unidad", "Unidad"),
        ("stock_minimo", "Mínimo"),
    ]


class MovimientoViewSet(BaseModelViewSet):
    """
    El historial y la forma de operar el stock.

    Los movimientos no se crean por POST directo: cada tipo tiene su acción,
    porque cada uno mueve el stock de forma distinta y validarlo en el
    serializer duplicaría el motor.
    """

    queryset = Movimiento.objects.select_related(
        "insumo", "lote", "origen", "destino", "caso__ciudadano", "autor"
    )
    serializer_class = MovimientoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "insumo__institucion"
    filter_fields = ("tipo", "insumo", "lote", "origen", "destino", "caso", "insumo__institucion")
    search_fields = ("insumo__nombre", "lote__numero", "motivo")
    ordering_fields = ("fecha", "cantidad")
    http_method_names = ["get", "head", "options", "post"]
    nombre_csv = "movimientos"
    columnas_csv = [
        ("fecha", "Fecha"),
        ("tipo_display", "Tipo"),
        ("insumo_nombre", "Insumo"),
        ("lote_numero", "Lote"),
        ("cantidad", "Cantidad"),
        ("origen_nombre", "Origen"),
        ("destino_nombre", "Destino"),
        ("paciente", "Paciente"),
        ("motivo", "Motivo"),
        ("autor_nombre", "Registró"),
    ]

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Usá las acciones (`ingreso`, `consumo`, `transferencia`, "
                       "`ajuste`, `baja`): cada tipo mueve el stock distinto."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _comun(self, request):
        return (
            _obj(Insumo, request.data.get("insumo")),
            _obj(Lote, request.data.get("lote")),
            (request.data.get("motivo") or "").strip(),
        )

    def _cantidad(self, request, clave="cantidad"):
        try:
            return int(request.data.get(clave))
        except (TypeError, ValueError):
            return None

    def _responder(self, movs):
        datos = self.get_serializer(movs, many=True).data if isinstance(movs, list) else \
            self.get_serializer(movs).data
        return Response(datos, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def ingreso(self, request):
        """Entra stock: {"deposito", "insumo", "cantidad", "lote", "motivo"}."""
        deposito = _obj(Deposito, request.data.get("deposito"))
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, insumo)
        try:
            return self._responder(
                motor.ingresar(deposito, insumo, cantidad, lote=lote, autor=request.user, motivo=motivo)
            )
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def consumo(self, request):
        """Se usó en un paciente: {"deposito", "insumo", "cantidad", "caso", "lote"}."""
        deposito = _obj(Deposito, request.data.get("deposito"))
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        caso = _obj(Caso, request.data.get("caso"))
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, insumo)
        try:
            return self._responder(
                motor.consumir(deposito, insumo, cantidad, caso=caso, autor=request.user,
                               lote=lote, motivo=motivo)
            )
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def transferencia(self, request):
        """Mueve entre depósitos: {"origen", "destino", "insumo", "cantidad", "lote"}."""
        origen = _obj(Deposito, request.data.get("origen"))
        destino = _obj(Deposito, request.data.get("destino"))
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (origen and destino and insumo and cantidad):
            return Response({"detail": "Faltan origen, destino, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, insumo)
        try:
            return self._responder(
                motor.transferir(origen, destino, insumo, cantidad, autor=request.user,
                                 lote=lote, motivo=motivo)
            )
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def ajuste(self, request):
        """Inventario: {"deposito", "insumo", "contado", "lote", "motivo"}."""
        deposito = _obj(Deposito, request.data.get("deposito"))
        insumo, lote, motivo = self._comun(request)
        contado = self._cantidad(request, "contado")
        if not (deposito and insumo) or contado is None:
            return Response({"detail": "Faltan depósito, insumo o lo contado."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, insumo)
        try:
            mov = motor.ajustar(deposito, insumo, contado, lote=lote, autor=request.user, motivo=motivo)
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if mov is None:
            # No es un error: el recuento coincidió. Decirlo evita que la
            # pantalla muestre «listo» y la persona busque un movimiento que no
            # existe.
            return Response({"detail": "El recuento coincide con el sistema: no hubo ajuste."})
        return self._responder(mov)

    @action(detail=False, methods=["post"])
    def baja(self, request):
        """Vencido, roto, extraviado: {"deposito", "insumo", "cantidad", "lote", "motivo"}."""
        deposito = _obj(Deposito, request.data.get("deposito"))
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self.check_object_permissions(request, insumo)
        try:
            return self._responder(
                motor.dar_de_baja(deposito, insumo, cantidad, lote=lote, autor=request.user,
                                  motivo=motivo)
            )
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="trazar-lote")
    def trazar_lote(self, request):
        """
        A quién le tocó un lote: `?lote=<id>`.

        Es la respuesta a un retiro de ANMAT, y la razón por la que el consumo
        se imputa al caso.
        """
        lote = _obj(Lote, request.query_params.get("lote"))
        if lote is None:
            return Response({"detail": "Falta el lote."}, status=status.HTTP_400_BAD_REQUEST)
        movs = motor.trazar_lote(lote)
        return Response({
            "lote": {"id": lote.id, "numero": lote.numero, "insumo": str(lote.insumo),
                     "vencimiento": lote.vencimiento},
            "pacientes": [{
                "caso": m.caso_id,
                "paciente": f"{m.caso.ciudadano.nombre} {m.caso.ciudadano.apellido}".strip()
                if m.caso.ciudadano_id else None,
                "cantidad": m.cantidad,
                "fecha": m.fecha,
                "deposito": m.origen.nombre if m.origen_id else None,
            } for m in movs],
        })


class PedidoViewSet(BaseModelViewSet):
    queryset = Pedido.objects.select_related("origen", "destino").prefetch_related("lineas__insumo")
    serializer_class = PedidoSerializer
    capacidad_requerida = "trabajo"
    institucion_path = "origen__institucion"
    filter_fields = ("origen", "destino", "estado", "urgente", "origen__institucion")
    ordering_fields = ("creado", "urgente")

    @action(detail=True, methods=["post"])
    def entregar(self, request, pk=None):
        """
        Entrega: {"entregas": {"<linea_id>": cantidad}}.

        Se puede entregar de menos —es lo normal cuando falta stock— y lo que
        quedó sin cubrir queda visible en la línea.
        """
        pedido = self.get_object()
        try:
            pedido = motor.entregar_pedido(pedido, request.data.get("entregas") or {},
                                           autor=request.user)
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(pedido).data)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        pedido = self.get_object()
        if pedido.estado in (Pedido.Estado.ENTREGADO, Pedido.Estado.RECHAZADO):
            return Response({"detail": "El pedido ya está cerrado."},
                            status=status.HTTP_400_BAD_REQUEST)
        pedido.estado = Pedido.Estado.RECHAZADO
        pedido.observaciones = (
            pedido.observaciones + "\n" + (request.data.get("motivo") or "")
        ).strip()
        pedido.save(update_fields=["estado", "observaciones"])
        return Response(self.get_serializer(pedido).data)

    @action(detail=False, methods=["get"])
    def alertas(self, request):
        """
        Lo que falta y lo que vence: `?institucion=<id>&deposito=<id>&dias=60`.

        Las dos juntas porque son la misma pregunta operativa —qué tengo que
        resolver hoy— y separarlas obliga a mirar dos pantallas.
        """
        inst = _obj(Institucion, request.query_params.get("institucion"))
        if inst is None:
            inst = Institucion.objects.filter(
                id__in=request.user.membresias.filter(activo=True).values("institucion")
            ).first()
        if inst is None:
            return Response({"faltantes": [], "por_vencer": []})
        deposito = _obj(Deposito, request.query_params.get("deposito"))
        try:
            dias = int(request.query_params.get("dias", 60))
        except ValueError:
            dias = 60

        faltantes = [{
            "deposito": f["deposito"].nombre,
            "deposito_id": f["deposito"].id,
            "insumo": str(f["insumo"]),
            "insumo_id": f["insumo"].id,
            "cantidad": f["cantidad"],
            "minimo": f["insumo"].stock_minimo,
            "unidad": f["insumo"].unidad,
        } for f in motor.bajo_minimo(inst, deposito)]

        vencen = [{
            "deposito": v["existencia"].deposito.nombre,
            "insumo": str(v["existencia"].insumo),
            "lote": v["existencia"].lote.numero,
            "vencimiento": v["existencia"].lote.vencimiento,
            "cantidad": v["existencia"].cantidad,
            "dias": v["dias"],
            "vencido": v["vencido"],
        } for v in motor.por_vencer(inst, dias=dias, deposito=deposito)]

        return Response({"faltantes": faltantes, "por_vencer": vencen})
