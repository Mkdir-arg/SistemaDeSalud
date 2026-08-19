"""
Farmacia e insumos.

El módulo se ordena alrededor de dos preguntas, porque son las dos que un
hospital le hace a un sistema de stock:

1. **¿Cuánto hay, de verdad?** Un número que no coincide con el estante no sirve
   para nada: se deja de mirar y se vuelve al cuaderno. Por eso el stock no se
   escribe nunca de forma directa —se calcula de los movimientos— y no puede
   quedar en negativo sin que alguien lo haya declarado.
2. **¿A quién le tocó el lote X?** Cuando ANMAT retira un lote hay que llamar a
   las personas que lo recibieron, y eso es imposible si el consumo se registró
   como «3 ampollas de dipirona» sin decir de cuál.

Esa segunda pregunta es la que obliga a que el consumo esté imputado al caso y
al lote, no sólo al depósito.
"""
from django.db import models
from django.utils import timezone


class Insumo(models.Model):
    """
    Lo que se guarda y se consume: un medicamento o un descartable.

    Es el catálogo de la institución, no un vademécum: sólo lo que realmente se
    usa. Un catálogo enorme sin stock hace que buscar sea inútil.
    """

    class Tipo(models.TextChoices):
        MEDICAMENTO = "medicamento", "Medicamento"
        DESCARTABLE = "descartable", "Descartable"
        INSUMO = "insumo", "Insumo general"

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="insumos"
    )
    codigo = models.CharField(max_length=40, blank=True, help_text="Código interno o de proveedor.")
    nombre = models.CharField(max_length=200)
    # La droga, aparte del nombre comercial: es como lo busca quien prescribe, y
    # además es lo que permite ver que dos productos distintos son lo mismo.
    generico = models.CharField("genérico / droga", max_length=200, blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.MEDICAMENTO)
    presentacion = models.CharField(max_length=120, blank=True, help_text="Ej.: «Ampolla 500 mg».")
    unidad = models.CharField(max_length=30, default="unidad", help_text="Ej.: comprimido, ampolla, ml.")
    # Con lote se puede responder a un retiro de ANMAT; sin lote, no. Los
    # descartables normalmente no lo llevan y exigirlo haría que se cargue
    # cualquier cosa con tal de avanzar.
    requiere_lote = models.BooleanField("lleva lote y vencimiento", default=True)
    # Psicotrópicos y estupefacientes: su movimiento se justifica siempre.
    controlado = models.BooleanField("controlado (Ley 19.303)", default=False)
    # Debajo de esto, falta. Es por insumo y no global porque no es lo mismo
    # quedarse sin gasas que sin adrenalina.
    stock_minimo = models.PositiveIntegerField("stock mínimo", default=0)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "insumo"
        verbose_name_plural = "insumos"
        ordering = ["nombre"]
        unique_together = [("institucion", "nombre", "presentacion")]

    def __str__(self):
        return f"{self.nombre} {self.presentacion}".strip()


class Deposito(models.Model):
    """
    Dónde está el stock: la farmacia central, el botiquín de la guardia, el
    carro de paro.

    Separarlos importa porque «hay 200 ampollas en el hospital» no responde la
    pregunta de la guardia a las 3 de la mañana, que es si hay en SU botiquín.
    """

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="depositos"
    )
    # El área que lo usa. La farmacia central no cuelga de ninguna.
    area = models.ForeignKey(
        "instituciones.Area", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="depositos",
    )
    nombre = models.CharField(max_length=120)
    # El depósito que abastece a los demás. Sirve para que un pedido sepa a
    # quién pedirle sin que alguien lo elija cada vez.
    central = models.BooleanField("es la farmacia central", default=False)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "depósito"
        verbose_name_plural = "depósitos"
        ordering = ["-central", "nombre"]
        unique_together = [("institucion", "nombre")]

    def __str__(self):
        return self.nombre


class Lote(models.Model):
    """
    Una partida de un insumo, con su vencimiento.

    Es lo que hace posible responder un retiro de ANMAT y lo que permite sacar
    primero lo que vence antes.
    """

    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name="lotes")
    numero = models.CharField("número de lote", max_length=60)
    vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        ordering = ["vencimiento", "numero"]
        unique_together = [("insumo", "numero")]

    def __str__(self):
        return f"{self.insumo} · lote {self.numero}"

    @property
    def vencido(self):
        return self.vencimiento is not None and self.vencimiento < timezone.localdate()

    def vence_en_dias(self, dias=60):
        if self.vencimiento is None:
            return False
        return 0 <= (self.vencimiento - timezone.localdate()).days <= dias


class Existencia(models.Model):
    """
    Cuánto hay de un insumo, en un depósito, de un lote.

    Es un acumulado que el motor mantiene junto con cada movimiento; la verdad
    está en los movimientos. Se guarda igual porque la pregunta «¿cuánto hay?»
    se hace todo el tiempo y sumar el historial completo cada vez no escala.

    Hay un test que recalcula desde los movimientos y compara: si el acumulado
    se separa, el módulo entero deja de servir y nadie lo notaría a tiempo.
    """

    deposito = models.ForeignKey(Deposito, on_delete=models.CASCADE, related_name="existencias")
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name="existencias")
    lote = models.ForeignKey(
        Lote, on_delete=models.CASCADE, null=True, blank=True, related_name="existencias"
    )
    cantidad = models.IntegerField(default=0)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "existencia"
        verbose_name_plural = "existencias"
        ordering = ["insumo__nombre", "lote__vencimiento"]
        unique_together = [("deposito", "insumo", "lote")]
        indexes = [models.Index(fields=["deposito", "insumo"])]

    def __str__(self):
        return f"{self.cantidad} × {self.insumo} en {self.deposito}"


class Movimiento(models.Model):
    """
    Todo lo que entra, sale o se mueve. Es la fuente de verdad del stock.

    Nunca se edita ni se borra: un error se corrige con otro movimiento. Un
    historial que se puede reescribir no sirve para auditar, y el stock de una
    farmacia se audita.
    """

    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"           # compra, donación
        CONSUMO = "consumo", "Consumo"           # se usó en un paciente
        TRANSFERENCIA = "transferencia", "Transferencia"
        AJUSTE = "ajuste", "Ajuste de inventario"
        BAJA = "baja", "Baja"                    # vencido, roto, extraviado

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="movimientos")
    lote = models.ForeignKey(
        Lote, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos"
    )
    # De dónde sale y a dónde entra. Un ingreso no tiene origen; un consumo o
    # una baja no tienen destino; una transferencia tiene los dos.
    origen = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, null=True, blank=True, related_name="salidas"
    )
    destino = models.ForeignKey(
        Deposito, on_delete=models.PROTECT, null=True, blank=True, related_name="entradas"
    )
    cantidad = models.PositiveIntegerField()
    # A qué paciente se le dio. Es lo que permite contestar un retiro de lote y
    # lo que imputa el consumo al caso.
    caso = models.ForeignKey(
        "casos.Caso", on_delete=models.SET_NULL, null=True, blank=True, related_name="consumos"
    )
    motivo = models.CharField(max_length=200, blank=True)
    autor = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="movimientos_stock",
    )
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "movimiento de stock"
        verbose_name_plural = "movimientos de stock"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["insumo", "-fecha"]),
            models.Index(fields=["lote"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad} × {self.insumo}"


class Pedido(models.Model):
    """
    Un área le pide reposición a la farmacia central.

    Existe porque sin él la reposición se hace por teléfono y no queda registro
    de qué se pidió, cuándo, ni qué se entregó de menos.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PREPARADO = "preparado", "Preparado"
        PARCIAL = "parcial", "Parcial"
        ENTREGADO = "entregado", "Entregado"
        RECHAZADO = "rechazado", "Rechazado"

    origen = models.ForeignKey(
        Deposito, on_delete=models.CASCADE, related_name="pedidos_hechos",
        help_text="Depósito que pide.",
    )
    destino = models.ForeignKey(
        Deposito, on_delete=models.CASCADE, related_name="pedidos_recibidos",
        help_text="Depósito al que se le pide (normalmente la central).",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    urgente = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pedidos_hechos",
    )
    resuelto = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pedido de reposición"
        verbose_name_plural = "pedidos de reposición"
        ordering = ["-urgente", "creado"]

    def __str__(self):
        return f"Pedido #{self.pk} · {self.origen} → {self.destino}"


class LineaPedido(models.Model):
    """
    Un renglón del pedido.

    `entregado` se guarda aparte de `pedido` a propósito: entregar de menos es
    lo normal cuando falta stock, y si el sistema sólo guarda lo pedido nadie
    puede ver después qué quedó sin cubrir.
    """

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="lineas")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="lineas_pedido")
    pedido_cant = models.PositiveIntegerField("cantidad pedida")
    entregado = models.PositiveIntegerField("cantidad entregada", default=0)

    class Meta:
        verbose_name = "línea de pedido"
        verbose_name_plural = "líneas de pedido"
        ordering = ["insumo__nombre"]

    def __str__(self):
        return f"{self.pedido_cant} × {self.insumo}"

    @property
    def faltante(self):
        return max(0, self.pedido_cant - self.entregado)
