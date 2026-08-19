from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.response import Response

from apps.casos.models import Caso
from apps.common import BaseModelViewSet, capacidades_de
from apps.instituciones.models import Institucion

from . import motor
from .models import Deposito, Existencia, Insumo, Lote, Movimiento, Pedido
from .serializers import (
    DepositoSerializer, ExistenciaSerializer, InsumoSerializer, LoteSerializer,
    MovimientoSerializer, PedidoSerializer,
)


class DatoInvalido(APIException):
    """Un id del cuerpo que no resuelve. 400 con el texto, no un 500 ni un 201."""

    status_code = status.HTTP_400_BAD_REQUEST


# Ruta ORM de cada modelo hacia su institución. Los ids que llegan en el cuerpo se
# resuelven contra ella: el queryset del viewset scopea la LECTURA, pero estas
# acciones traían los objetos con un `filter(pk=...)` pelado, y con eso alguien de
# un hospital podía mover el stock de otro mandando los ids.
_RUTA_INSTITUCION = {
    Caso: "institucion_id",
    Deposito: "institucion_id",
    Institucion: "id",
    Insumo: "institucion_id",
    Lote: "insumo__institucion_id",
}


def _instituciones(user):
    """Las instituciones donde el usuario actúa. None = superusuario, ve todas."""
    if user.is_superuser:
        return None
    return list(user.membresias.filter(activo=True).values_list("institucion_id", flat=True))


def _obj(modelo, valor, instituciones=None, nombre=""):
    """
    El objeto de ese id, o None si no vino ninguno.

    Un id que vino y no resuelve corta con 400 en vez de devolver None: son cosas
    distintas y confundirlas hacía que un consumo con un caso inexistente se
    registrara con 201 y sin paciente —la imputación al paciente se perdía sin
    que nadie se enterara hasta el día del retiro de lote—, y que un lote
    inventado se descontara por FEFO de otra partida.
    """
    if valor in (None, ""):
        return None
    qs = modelo.objects.all()
    if instituciones is not None:
        qs = qs.filter(**{f"{_RUTA_INSTITUCION[modelo]}__in": instituciones})
    try:
        obj = qs.filter(pk=valor).first()
    except (ValidationError, TypeError, ValueError):
        # Un id no numérico reventaba con un 500; es un pedido mal armado.
        obj = None
    if obj is None:
        raise DatoInvalido(
            f"No existe {nombre or modelo._meta.verbose_name} con id «{valor}» "
            f"en tu institución."
        )
    return obj


class InsumoViewSet(BaseModelViewSet):
    """
    Catálogo de la institución: sólo lo que realmente se usa. Un catálogo
    enorme sin stock hace que buscar sea inútil.
    """

    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer
    capacidad_requerida = "config_institucional"
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
    capacidad_requerida = "config_institucional"
    institucion_path = "institucion"
    filter_fields = ("institucion", "area", "central", "activo")


class LoteViewSet(BaseModelViewSet):
    """Las partidas. Se cargan al recibir mercadería, así que es `trabajo`."""

    queryset = Lote.objects.select_related("insumo")
    serializer_class = LoteSerializer
    capacidad_requerida = "farmacia_stock"
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
    capacidad_requerida = "farmacia_stock"
    institucion_path = "deposito__institucion"
    filter_fields = ("deposito", "deposito__institucion", "insumo", "lote")
    search_fields = ("insumo__nombre", "insumo__generico", "lote__numero")
    # `deposito__nombre` está para que la pantalla pueda pedir las filas
    # agrupables juntas: agrupa por (depósito, insumo) en el cliente y, si el
    # orden interpola depósitos, un mismo grupo queda partido entre dos páginas
    # y su total sale menor al real (y se pinta rojo sin faltar).
    ordering_fields = ("cantidad", "insumo__nombre", "deposito__nombre")
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
    capacidad_requerida = "farmacia_stock"
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
        # El libro de controlados se arma con esta exportación: sin la columna
        # hay que ir insumo por insumo a ver cuál lo era.
        ("controlado", "Controlado"),
        ("motivo", "Motivo"),
        ("autor_nombre", "Registró"),
    ]

    def get_queryset(self):
        qs = super().get_queryset()
        dep = self.request.query_params.get("deposito")
        if dep and str(dep).isdigit():
            # «Los movimientos de este depósito» son los que entraron y los que
            # salieron; `origen` solo esconde las reposiciones que llegaron.
            # Filtrar acá y no en el navegador: sobre la página traída, elegir un
            # depósito mostraba «Sin movimientos» habiendo veinte más atrás.
            qs = qs.filter(Q(origen_id=dep) | Q(destino_id=dep))
        return qs

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Usá las acciones (`ingreso`, `consumo`, `transferencia`, "
                       "`ajuste`, `baja`): cada tipo mueve el stock distinto."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _comun(self, request):
        insts = _instituciones(request.user)
        return (
            _obj(Insumo, request.data.get("insumo"), insts, "el insumo"),
            _obj(Lote, request.data.get("lote"), insts, "el lote"),
            (request.data.get("motivo") or "").strip(),
        )

    def _deposito(self, request, clave="deposito"):
        return _obj(Deposito, request.data.get(clave), _instituciones(request.user),
                    f"el depósito «{clave}»")

    def _autorizar(self, request, insumo, *depositos):
        """
        Capacidad del usuario EN la institución del insumo, y depósitos de esa
        misma institución.

        `check_object_permissions` no sirve para estas acciones: el
        `institucion_path` del viewset describe un Movimiento
        («insumo__institucion») y acá se le pasaba un Insumo, así que la ruta se
        cortaba, la institución salía None y el permiso degradaba a «¿tiene
        trabajo en algún lado?». Con eso una enfermera de un hospital movía el
        stock de otro y el hospital víctima sólo veía que el número no coincidía
        con el estante.
        """
        for d in depositos:
            if d is not None and d.institucion_id != insumo.institucion_id:
                raise PermissionDenied("El depósito y el insumo son de instituciones distintas.")
        if request.user.is_superuser:
            return
        if self.capacidad_requerida not in capacidades_de(request.user, insumo.institucion_id):
            raise PermissionDenied("No tenés permiso para mover el stock de esta institución.")

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
        deposito = self._deposito(request)
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self._autorizar(request, insumo, deposito)
        try:
            return self._responder(
                motor.ingresar(deposito, insumo, cantidad, lote=lote, autor=request.user, motivo=motivo)
            )
        except motor.ErrorStock as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def consumo(self, request):
        """Se usó en un paciente: {"deposito", "insumo", "cantidad", "caso", "lote"}."""
        deposito = self._deposito(request)
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        caso = _obj(Caso, request.data.get("caso"), _instituciones(request.user), "el caso")
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self._autorizar(request, insumo, deposito)
        if caso is not None and caso.institucion_id != insumo.institucion_id:
            raise PermissionDenied("Ese caso es de otra institución.")
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
        origen = self._deposito(request, "origen")
        destino = self._deposito(request, "destino")
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (origen and destino and insumo and cantidad):
            return Response({"detail": "Faltan origen, destino, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self._autorizar(request, insumo, origen, destino)
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
        deposito = self._deposito(request)
        insumo, lote, motivo = self._comun(request)
        contado = self._cantidad(request, "contado")
        if not (deposito and insumo) or contado is None:
            return Response({"detail": "Faltan depósito, insumo o lo contado."},
                            status=status.HTTP_400_BAD_REQUEST)
        self._autorizar(request, insumo, deposito)
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
        deposito = self._deposito(request)
        insumo, lote, motivo = self._comun(request)
        cantidad = self._cantidad(request)
        if not (deposito and insumo and cantidad):
            return Response({"detail": "Faltan depósito, insumo o cantidad."},
                            status=status.HTTP_400_BAD_REQUEST)
        self._autorizar(request, insumo, deposito)
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
        lote = _obj(Lote, request.query_params.get("lote"), _instituciones(request.user), "el lote")
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
    capacidad_requerida = "farmacia_stock"
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
        pedido.resuelto = timezone.now()
        pedido.save(update_fields=["estado", "observaciones", "resuelto"])
        return Response(self.get_serializer(pedido).data)

    @action(detail=False, methods=["get"])
    def alertas(self, request):
        """
        Lo que falta y lo que vence: `?institucion=<id>&deposito=<id>&dias=60`.

        Las dos juntas porque son la misma pregunta operativa —qué tengo que
        resolver hoy— y separarlas obliga a mirar dos pantallas.
        """
        insts = _instituciones(request.user)
        inst = _obj(Institucion, request.query_params.get("institucion"), insts, "la institución")
        if inst is None:
            inst = Institucion.objects.filter(
                id__in=request.user.membresias.filter(activo=True).values("institucion")
            ).first()
        if inst is None:
            return Response({"faltantes": [], "por_vencer": []})
        deposito = _obj(Deposito, request.query_params.get("deposito"), insts, "el depósito")
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
            # Lo vencido no cuenta como stock pero tampoco es lo mismo que no
            # tener: «0 de 20 · 59 vencidas» dice que hay algo que dar de baja.
            "vencida": f["vencida"],
            "minimo": f["insumo"].stock_minimo,
            "unidad": f["insumo"].unidad,
            "controlado": f["insumo"].controlado,
        } for f in motor.bajo_minimo(inst, deposito)]

        # Los ids no son decoración: lo único que hay que hacer con un lote
        # vencido es darlo de baja, y sin ellos el renglón no se puede enlazar a
        # esa acción. Sin eso hay que memorizar insumo, depósito y lote, ir a
        # Stock y buscarlos, que es la fricción por la que la ampolla vencida
        # sigue en el botiquín.
        vencen = [{
            "deposito": v["existencia"].deposito.nombre,
            "deposito_id": v["existencia"].deposito_id,
            "insumo": str(v["existencia"].insumo),
            "insumo_id": v["existencia"].insumo_id,
            "unidad": v["existencia"].insumo.unidad,
            "controlado": v["existencia"].insumo.controlado,
            "lote": v["existencia"].lote.numero,
            "lote_id": v["existencia"].lote_id,
            "vencimiento": v["existencia"].lote.vencimiento,
            "cantidad": v["existencia"].cantidad,
            "dias": v["dias"],
            "vencido": v["vencido"],
        } for v in motor.por_vencer(inst, dias=dias, deposito=deposito)]

        return Response({"faltantes": faltantes, "por_vencer": vencen})
