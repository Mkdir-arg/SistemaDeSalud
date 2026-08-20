"""
Operaciones de stock.

Regla única de la que cuelga todo el módulo: **la existencia nunca se escribe a
mano, se mueve junto con un movimiento**. Si se pudiera editar el número, el
historial dejaría de explicar el stock y la farmacia perdería la única cosa que
le pide a un sistema — que el número coincida con el estante y se pueda mostrar
por qué—.
"""
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import Deposito, Existencia, LineaPedido, Lote, Movimiento, Pedido


class ErrorStock(Exception):
    """Regla de stock incumplida. La API la traduce a un 400 con el texto."""


def _existencia(deposito, insumo, lote, crear=True):
    """La fila de existencia, bloqueada para actualizar.

    El `order_by()` vacío no es adorno: `Existencia` ordena por
    `lote__vencimiento` y el lote es opcional, así que el orden por defecto arma
    un LEFT JOIN y Postgres no deja bloquear filas sobre el lado nullable de un
    outer join. Acá se busca una fila puntual y el orden no aporta nada.
    """
    qs = Existencia.objects.order_by().select_for_update().filter(
        deposito=deposito, insumo=insumo, lote=lote
    )
    e = qs.first()
    if e is None and crear:
        e, _ = Existencia.objects.get_or_create(
            deposito=deposito, insumo=insumo, lote=lote, defaults={"cantidad": 0}
        )
        e = Existencia.objects.order_by().select_for_update().get(pk=e.pk)
    return e


def disponible(deposito, insumo, lote=None) -> int:
    """Cuánto hay. Sin lote, la suma de todos los lotes de ese insumo."""
    qs = Existencia.objects.filter(deposito=deposito, insumo=insumo)
    if lote is not None:
        qs = qs.filter(lote=lote)
    return qs.aggregate(t=Sum("cantidad"))["t"] or 0


def _filas_por_vencimiento(deposito, insumo):
    """Las existencias con stock, de la que vence antes a la que vence después."""
    return list(
        Existencia.objects.select_related("lote")
        .filter(deposito=deposito, insumo=insumo, cantidad__gt=0)
        .order_by(F("lote__vencimiento").asc(nulls_last=True), "lote__numero", "id")
    )


def _esta_vencida(fila, hoy):
    return bool(fila.lote and fila.lote.vencimiento and fila.lote.vencimiento < hoy)


def _repartir(filas, cantidad):
    """Plan `[(lote, cuánto)]` tomando de `filas` en el orden en que vienen."""
    plan, resta = [], cantidad
    for f in filas:
        if resta <= 0:
            break
        toma = min(f.cantidad, resta)
        plan.append((f.lote, toma))
        resta -= toma
    return plan


def _validar_lote_explicito(insumo, lote, accion):
    """Las dos reglas de un lote que alguien nombra a mano.

    Estaban sólo en `ingresar`, así que consumir o transferir indicando el lote
    dejaba aplicarle a un paciente un medicamento vencido —y quedaba registrado
    como un consumo cualquiera, imposible de encontrar después en el historial—.
    """
    if lote.insumo_id != insumo.id:
        raise ErrorStock("Ese lote es de otro insumo.")
    if lote.vencido:
        raise ErrorStock(f"El lote {lote.numero} está vencido: no se puede {accion}.")


def lotes_para_sacar(deposito, insumo, cantidad):
    """
    De qué lotes sacar, en qué orden: primero el que vence antes.

    Es la regla real de una farmacia (FEFO) y no es una optimización: sacar del
    lote más nuevo hace que el viejo venza en el estante y se tire.

    Los vencidos no se ofrecen. Si el stock alcanza sólo contándolos, se avisa
    que hay stock pero está vencido, que es una situación distinta a no tener.
    """
    hoy = timezone.localdate()
    filas = _filas_por_vencimiento(deposito, insumo)
    usables = [f for f in filas if not _esta_vencida(f, hoy)]
    total = sum(f.cantidad for f in usables)
    if total < cantidad:
        vencido = sum(f.cantidad for f in filas) - total
        detalle = f" (hay {vencido} vencido/s, que no se pueden usar)" if vencido else ""
        raise ErrorStock(
            f"No alcanza el stock de {insumo} en {deposito}: hay {total} y se piden "
            f"{cantidad}{detalle}."
        )
    return _repartir(usables, cantidad)


@transaction.atomic
def ingresar(deposito, insumo, cantidad, lote=None, autor=None, motivo="") -> Movimiento:
    """Entra stock: una compra, una donación."""
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")
    if insumo.requiere_lote and lote is None:
        # Sin lote no se puede responder un retiro de ANMAT. Es justo el insumo
        # donde eso importa —el que lo declara— así que no se deja pasar.
        raise ErrorStock(f"{insumo} lleva lote: hay que indicar cuál ingresa.")
    if lote is not None:
        _validar_lote_explicito(insumo, lote, "ingresar")

    e = _existencia(deposito, insumo, lote)
    e.cantidad = F("cantidad") + cantidad
    e.save(update_fields=["cantidad", "actualizado"])
    return Movimiento.objects.create(
        tipo=Movimiento.Tipo.INGRESO, insumo=insumo, lote=lote, destino=deposito,
        cantidad=cantidad, autor=autor, motivo=motivo[:200],
    )


@transaction.atomic
def consumir(deposito, insumo, cantidad, caso=None, autor=None, lote=None, motivo=""):
    """
    Sale stock porque se usó en un paciente.

    Imputarlo al caso es lo que después permite contestar «¿a quién le tocó el
    lote X?» cuando hay un retiro, y lo que hace que el consumo se pueda ver en
    la historia del paciente en vez de ser sólo un número que bajó.

    Si no se indica lote, se saca por vencimiento (el que vence antes primero) y
    puede repartirse entre varios: se devuelve un movimiento por lote.
    """
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")
    if insumo.controlado and caso is None and not motivo.strip():
        # Un estupefaciente que sale sin nominar y sin justificar no permite
        # armar el libro de controlados: ante una inspección el faltante no
        # tiene respaldo, y ante un retiro de lote esas unidades son «no
        # sabemos» porque `trazar_lote` sólo ve los consumos con caso.
        raise ErrorStock(
            f"{insumo} es un insumo controlado (Ley 19.303): el consumo tiene que quedar "
            "imputado a un caso, o llevar un motivo que explique a dónde fue."
        )

    if lote is not None:
        _validar_lote_explicito(insumo, lote, "consumir")
        hay = disponible(deposito, insumo, lote)
        if hay < cantidad:
            raise ErrorStock(
                f"No alcanza el lote {lote.numero} en {deposito}: hay {hay} y se piden {cantidad}."
            )
        plan = [(lote, cantidad)]
    else:
        plan = lotes_para_sacar(deposito, insumo, cantidad)

    movimientos = []
    for l, cant in plan:
        e = _existencia(deposito, insumo, l, crear=False)
        if e is None or e.cantidad < cant:
            # Otro pudo haber consumido entre el cálculo y acá. El candado de
            # `_existencia` lo evita dentro de la transacción, pero el chequeo
            # queda: es más barato que un stock en negativo.
            raise ErrorStock(f"El stock de {insumo} cambió mientras se registraba. Reintentá.")
        e.cantidad = F("cantidad") - cant
        e.save(update_fields=["cantidad", "actualizado"])
        movimientos.append(Movimiento.objects.create(
            tipo=Movimiento.Tipo.CONSUMO, insumo=insumo, lote=l, origen=deposito,
            cantidad=cant, caso=caso, autor=autor, motivo=motivo[:200],
        ))
    return movimientos


@transaction.atomic
def transferir(origen, destino, insumo, cantidad, autor=None, lote=None, motivo=""):
    """Mueve stock de un depósito a otro (reposición de un botiquín)."""
    if origen.id == destino.id:
        raise ErrorStock("El origen y el destino son el mismo depósito.")
    # La regla vivía sólo en la vista de movimientos, así que el camino de los
    # pedidos —que llama acá— movía stock entre hospitales: la central del
    # hospital B se vaciaba y B sólo veía que el número no coincidía con el
    # estante. Va acá para que ningún camino nuevo se la saltee.
    if not (origen.institucion_id == destino.institucion_id == insumo.institucion_id):
        raise ErrorStock(
            "El origen, el destino y el insumo tienen que ser de la misma institución."
        )
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")

    if lote is not None:
        # Sin esto se podía mandar lo vencido al botiquín de guardia, donde ocupa
        # lugar y engorda el número que la guardia mira a la noche.
        _validar_lote_explicito(insumo, lote, "transferir")
        if disponible(origen, insumo, lote) < cantidad:
            raise ErrorStock(f"No alcanza el lote {lote.numero} en {origen}.")
        plan = [(lote, cantidad)]
    else:
        plan = lotes_para_sacar(origen, insumo, cantidad)

    movimientos = []
    for l, cant in plan:
        salida = _existencia(origen, insumo, l, crear=False)
        if salida is None or salida.cantidad < cant:
            raise ErrorStock(f"El stock de {insumo} cambió mientras se registraba. Reintentá.")
        salida.cantidad = F("cantidad") - cant
        salida.save(update_fields=["cantidad", "actualizado"])

        entrada = _existencia(destino, insumo, l)
        entrada.cantidad = F("cantidad") + cant
        entrada.save(update_fields=["cantidad", "actualizado"])

        movimientos.append(Movimiento.objects.create(
            tipo=Movimiento.Tipo.TRANSFERENCIA, insumo=insumo, lote=l,
            origen=origen, destino=destino, cantidad=cant, autor=autor, motivo=motivo[:200],
        ))
    return movimientos


@transaction.atomic
def ajustar(deposito, insumo, contado, lote=None, autor=None, motivo="") -> Movimiento | None:
    """
    Deja el stock en lo que se contó en el estante.

    Un inventario que no se puede corregir se abandona: la primera vez que el
    número no coincide, la gente vuelve al cuaderno. La corrección queda como un
    movimiento con su motivo, así la diferencia es visible y no un número que
    cambió solo.
    """
    if contado < 0:
        raise ErrorStock("Lo contado no puede ser negativo.")
    if insumo.requiere_lote and lote is None:
        # Un ajuste sin lote deja unidades que no vencen nunca, que no aparecen
        # en «Vencen pronto» y que ante un retiro de ANMAT no se pueden atribuir
        # a ninguna partida. El recuento se hace lote por lote, que es como se
        # cuenta en el estante.
        raise ErrorStock(f"{insumo} lleva lote: el recuento se hace por lote.")
    if lote is not None and lote.insumo_id != insumo.id:
        raise ErrorStock("Ese lote es de otro insumo.")
    e = _existencia(deposito, insumo, lote)
    e.refresh_from_db()
    diferencia = contado - e.cantidad
    if diferencia == 0:
        return None
    e.cantidad = contado
    e.save(update_fields=["cantidad", "actualizado"])
    return Movimiento.objects.create(
        tipo=Movimiento.Tipo.AJUSTE, insumo=insumo, lote=lote,
        # El signo lo lleva el motivo y el destino/origen: un ajuste en más
        # entra, uno en menos sale.
        destino=deposito if diferencia > 0 else None,
        origen=deposito if diferencia < 0 else None,
        cantidad=abs(diferencia), autor=autor,
        motivo=(motivo or f"Inventario: contado {contado}, sistema {contado - diferencia}")[:200],
    )


@transaction.atomic
def dar_de_baja(deposito, insumo, cantidad, lote=None, autor=None, motivo=""):
    """
    Sale stock sin haberse usado: vencido, roto, extraviado.

    Es la única forma de sacar del sistema un lote vencido, así que acá el
    vencido SÍ se puede elegir —al revés que en consumo y transferencia—.

    Sin lote no se busca la fila sin lote: en un insumo con partidas esa fila no
    existe y la baja fallaba siempre con «hay 0» mientras la pantalla mostraba
    «Hay 3». Se reparte entre las partidas que hay, empezando por la que vence
    antes (o ya venció), que es lo que uno saca del estante.
    """
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")
    if not motivo.strip():
        # Una baja sin motivo es indistinguible de un faltante, y en un insumo
        # controlado eso es exactamente lo que hay que poder explicar.
        raise ErrorStock("Una baja necesita un motivo.")

    if lote is not None:
        if lote.insumo_id != insumo.id:
            raise ErrorStock("Ese lote es de otro insumo.")
        hay = disponible(deposito, insumo, lote)
        if hay < cantidad:
            raise ErrorStock(
                f"No alcanza el lote {lote.numero} en {deposito}: hay {hay} y se piden {cantidad}."
            )
        plan = [(lote, cantidad)]
    else:
        filas = _filas_por_vencimiento(deposito, insumo)
        total = sum(f.cantidad for f in filas)
        if total < cantidad:
            raise ErrorStock(
                f"No alcanza el stock de {insumo} en {deposito}: hay {total} y se piden {cantidad}."
            )
        plan = _repartir(filas, cantidad)

    movimientos = []
    for l, cant in plan:
        e = _existencia(deposito, insumo, l, crear=False)
        if e is None or e.cantidad < cant:
            raise ErrorStock(f"El stock de {insumo} cambió mientras se registraba. Reintentá.")
        e.cantidad = F("cantidad") - cant
        e.save(update_fields=["cantidad", "actualizado"])
        movimientos.append(Movimiento.objects.create(
            tipo=Movimiento.Tipo.BAJA, insumo=insumo, lote=l, origen=deposito,
            cantidad=cant, autor=autor, motivo=motivo[:200],
        ))
    return movimientos


# --------------------------------------------------------------------------- #
# Pedidos de reposición
# --------------------------------------------------------------------------- #
@transaction.atomic
def preparar_pedido(pedido: Pedido, autor=None) -> Pedido:
    """
    Marca un pedido como preparado para despacho.

    Preparar no mueve stock: es la validacion operativa de picking antes de
    entregar. La transferencia real sigue ocurriendo en `entregar_pedido`, donde
    queda el movimiento auditable. Si no alcanza para cubrir lo pendiente, no se
    promete un pedido listo.
    """
    estado_entrada = pedido.estado
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if pedido.estado != estado_entrada:
        raise ErrorStock("El pedido cambio mientras se preparaba. Recarga y volve a intentar.")
    if pedido.estado in (Pedido.Estado.ENTREGADO, Pedido.Estado.RECHAZADO):
        raise ErrorStock("El pedido ya esta cerrado.")
    if pedido.estado == Pedido.Estado.PREPARADO:
        return pedido

    lineas = list(pedido.lineas.select_related("insumo"))
    if not lineas:
        raise ErrorStock("El pedido no tiene renglones para preparar.")

    pendientes = [linea for linea in lineas if linea.faltante > 0]
    if not pendientes:
        raise ErrorStock("El pedido no tiene cantidades pendientes.")
    for linea in pendientes:
        # Valida stock usable y FEFO sin modificar existencias. Si hay vencido,
        # el error lo distingue de un faltante real.
        lotes_para_sacar(pedido.destino, linea.insumo, linea.faltante)

    pedido.estado = Pedido.Estado.PREPARADO
    pedido.resuelto = None
    pedido.save(update_fields=["estado", "resuelto"])
    return pedido


@transaction.atomic
def entregar_pedido(pedido: Pedido, entregas: dict, autor=None) -> Pedido:
    """
    Entrega un pedido: transfiere lo que hay y deja registrado lo que faltó.

    `entregas` es `{linea_id: cantidad}`. Entregar de menos es lo normal cuando
    falta stock, y guardarlo es lo que después permite ver qué quedó sin cubrir;
    si el sistema sólo guardara lo pedido, el faltante desaparecería.
    """
    # El estado se relee con candado y no se confía en la copia que trajo la
    # vista. El caso real no es un ataque sino un timeout: la farmacia entrega,
    # el navegador no contesta y la persona vuelve a apretar; con las dos copias
    # diciendo «pendiente» salían 60 ampollas de la central para un pedido de 30.
    estado_entrada = pedido.estado
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if pedido.estado != estado_entrada:
        raise ErrorStock("El pedido cambio mientras se registraba. Recarga y volve a intentar.")
    if pedido.estado in (Pedido.Estado.ENTREGADO, Pedido.Estado.RECHAZADO):
        raise ErrorStock("El pedido ya está cerrado.")

    lineas = list(pedido.lineas.select_related("insumo"))
    algo_entregado = False
    for linea in lineas:
        try:
            cant = int(entregas.get(linea.id, entregas.get(str(linea.id), 0)) or 0)
        except (TypeError, ValueError):
            raise ErrorStock(f"La cantidad de {linea.insumo} no es valida.")
        if cant <= 0:
            continue
        pendiente = linea.pedido_cant - linea.entregado
        if cant > pendiente:
            raise ErrorStock(
                f"No se puede entregar {cant} de {linea.insumo}: quedan {pendiente} por entregar."
            )
        transferir(pedido.destino, pedido.origen, linea.insumo, cant, autor=autor,
                   motivo=f"Pedido #{pedido.pk}")
        # Se acumula: si alguna vez se entrega en dos veces, pisarlo dejaría el
        # renglón diciendo lo mismo que la primera entrega y el resto invisible.
        linea.entregado += cant
        linea.save(update_fields=["entregado"])
        algo_entregado = True

    if not algo_entregado:
        raise ErrorStock("Indica al menos una cantidad a entregar.")

    if all(linea.entregado >= linea.pedido_cant for linea in lineas):
        pedido.estado = Pedido.Estado.ENTREGADO
        pedido.resuelto = timezone.now()
    else:
        pedido.estado = Pedido.Estado.PARCIAL
        pedido.resuelto = None
    pedido.save(update_fields=["estado", "resuelto"])
    return pedido


# --------------------------------------------------------------------------- #
# Alertas
# --------------------------------------------------------------------------- #
def bajo_minimo(institucion, deposito=None):
    """
    Insumos por debajo de su mínimo.

    Se compara contra el stock del depósito, no el de la institución: «hay 200
    en el hospital» no le sirve a la guardia a las 3 de la mañana, que necesita
    saber si hay en SU botiquín.

    Lo vencido no cuenta como stock —`lotes_para_sacar` tampoco lo deja usar— y
    se devuelve aparte: un botiquín con las 59 ampollas de adrenalina vencidas
    no puede verse igual que uno abastecido, y «0 de 20 · 59 vencidas» es una
    situación distinta a no tener nada, porque hay algo que dar de baja y
    alguien a quien reclamarle.
    """
    hoy = timezone.localdate()
    qs = Existencia.objects.filter(
        deposito__institucion=institucion, insumo__activo=True, insumo__stock_minimo__gt=0
    )
    if deposito is not None:
        qs = qs.filter(deposito=deposito)
    por_clave = {}
    for e in qs.select_related("insumo", "deposito", "lote"):
        clave = (e.deposito_id, e.insumo_id)
        d = por_clave.setdefault(
            clave,
            {"deposito": e.deposito, "insumo": e.insumo, "cantidad": 0, "vencida": 0},
        )
        if _esta_vencida(e, hoy):
            d["vencida"] += e.cantidad
        else:
            d["cantidad"] += e.cantidad
    return sorted(
        (d for d in por_clave.values() if d["cantidad"] < d["insumo"].stock_minimo),
        key=lambda d: (d["cantidad"] / (d["insumo"].stock_minimo or 1), d["insumo"].nombre),
    )


def por_vencer(institucion, dias=60, deposito=None):
    """
    Lo que vence pronto y todavía está en el estante.

    Sólo con existencia: avisar de un lote que ya se consumió entero es ruido, y
    el ruido hace que la alerta se deje de mirar.
    """
    hoy = timezone.localdate()
    qs = (
        Existencia.objects.select_related("insumo", "lote", "deposito")
        .filter(
            deposito__institucion=institucion, cantidad__gt=0, lote__isnull=False,
            lote__vencimiento__isnull=False,
        )
    )
    if deposito is not None:
        qs = qs.filter(deposito=deposito)
    salida = []
    for e in qs:
        faltan = (e.lote.vencimiento - hoy).days
        if faltan <= dias:
            salida.append({"existencia": e, "dias": faltan, "vencido": faltan < 0})
    return sorted(salida, key=lambda x: x["dias"])


def trazar_lote(lote: Lote):
    """
    A quién le tocó este lote.

    Es la razón por la que el consumo se imputa al caso. Cuando ANMAT retira un
    lote hay que llamar a esas personas, y sin esto la única respuesta posible
    es «no sabemos».
    """
    return (
        Movimiento.objects.filter(lote=lote, tipo=Movimiento.Tipo.CONSUMO, caso__isnull=False)
        .select_related("caso__ciudadano", "origen")
        .order_by("-fecha")
    )
