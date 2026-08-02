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


def lotes_para_sacar(deposito, insumo, cantidad):
    """
    De qué lotes sacar, en qué orden: primero el que vence antes.

    Es la regla real de una farmacia (FEFO) y no es una optimización: sacar del
    lote más nuevo hace que el viejo venza en el estante y se tire.

    Los vencidos no se ofrecen. Si el stock alcanza sólo contándolos, se avisa
    que hay stock pero está vencido, que es una situación distinta a no tener.
    """
    hoy = timezone.localdate()
    filas = list(
        Existencia.objects.select_related("lote")
        .filter(deposito=deposito, insumo=insumo, cantidad__gt=0)
        .order_by(F("lote__vencimiento").asc(nulls_last=True), "lote__numero", "id")
    )
    usables = [f for f in filas if not (f.lote and f.lote.vencimiento and f.lote.vencimiento < hoy)]
    total = sum(f.cantidad for f in usables)
    if total < cantidad:
        vencido = sum(f.cantidad for f in filas) - total
        detalle = f" (hay {vencido} vencido/s, que no se pueden usar)" if vencido else ""
        raise ErrorStock(
            f"No alcanza el stock de {insumo} en {deposito}: hay {total} y se piden "
            f"{cantidad}{detalle}."
        )

    plan, resta = [], cantidad
    for f in usables:
        if resta <= 0:
            break
        toma = min(f.cantidad, resta)
        plan.append((f.lote, toma))
        resta -= toma
    return plan


@transaction.atomic
def ingresar(deposito, insumo, cantidad, lote=None, autor=None, motivo="") -> Movimiento:
    """Entra stock: una compra, una donación."""
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")
    if insumo.requiere_lote and lote is None:
        # Sin lote no se puede responder un retiro de ANMAT. Es justo el insumo
        # donde eso importa —el que lo declara— así que no se deja pasar.
        raise ErrorStock(f"{insumo} lleva lote: hay que indicar cuál ingresa.")
    if lote is not None and lote.insumo_id != insumo.id:
        raise ErrorStock("Ese lote es de otro insumo.")
    if lote is not None and lote.vencido:
        raise ErrorStock(f"El lote {lote.numero} está vencido: no se puede ingresar.")

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
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")

    plan = [(lote, cantidad)] if lote is not None else lotes_para_sacar(origen, insumo, cantidad)
    if lote is not None and disponible(origen, insumo, lote) < cantidad:
        raise ErrorStock(f"No alcanza el lote {lote.numero} en {origen}.")

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
def dar_de_baja(deposito, insumo, cantidad, lote=None, autor=None, motivo="") -> Movimiento:
    """Sale stock sin haberse usado: vencido, roto, extraviado."""
    if cantidad <= 0:
        raise ErrorStock("La cantidad tiene que ser mayor que cero.")
    if not motivo.strip():
        # Una baja sin motivo es indistinguible de un faltante, y en un insumo
        # controlado eso es exactamente lo que hay que poder explicar.
        raise ErrorStock("Una baja necesita un motivo.")
    e = _existencia(deposito, insumo, lote, crear=False)
    if e is None or e.cantidad < cantidad:
        hay = e.cantidad if e else 0
        raise ErrorStock(f"No alcanza el stock de {insumo} en {deposito}: hay {hay}.")
    e.cantidad = F("cantidad") - cantidad
    e.save(update_fields=["cantidad", "actualizado"])
    return Movimiento.objects.create(
        tipo=Movimiento.Tipo.BAJA, insumo=insumo, lote=lote, origen=deposito,
        cantidad=cantidad, autor=autor, motivo=motivo[:200],
    )


# --------------------------------------------------------------------------- #
# Pedidos de reposición
# --------------------------------------------------------------------------- #
@transaction.atomic
def entregar_pedido(pedido: Pedido, entregas: dict, autor=None) -> Pedido:
    """
    Entrega un pedido: transfiere lo que hay y deja registrado lo que faltó.

    `entregas` es `{linea_id: cantidad}`. Entregar de menos es lo normal cuando
    falta stock, y guardarlo es lo que después permite ver qué quedó sin cubrir;
    si el sistema sólo guardara lo pedido, el faltante desaparecería.
    """
    if pedido.estado in (Pedido.Estado.ENTREGADO, Pedido.Estado.RECHAZADO):
        raise ErrorStock("El pedido ya está cerrado.")

    for linea in pedido.lineas.select_related("insumo"):
        cant = int(entregas.get(linea.id, entregas.get(str(linea.id), 0)) or 0)
        if cant <= 0:
            continue
        if cant > linea.pedido_cant:
            raise ErrorStock(
                f"No se puede entregar {cant} de {linea.insumo}: se pidieron {linea.pedido_cant}."
            )
        transferir(pedido.destino, pedido.origen, linea.insumo, cant, autor=autor,
                   motivo=f"Pedido #{pedido.pk}")
        linea.entregado = cant
        linea.save(update_fields=["entregado"])

    pedido.estado = Pedido.Estado.ENTREGADO
    pedido.resuelto = timezone.now()
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
    """
    qs = Existencia.objects.filter(
        deposito__institucion=institucion, insumo__activo=True, insumo__stock_minimo__gt=0
    )
    if deposito is not None:
        qs = qs.filter(deposito=deposito)
    por_clave = {}
    for e in qs.select_related("insumo", "deposito"):
        clave = (e.deposito_id, e.insumo_id)
        d = por_clave.setdefault(clave, {"deposito": e.deposito, "insumo": e.insumo, "cantidad": 0})
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
