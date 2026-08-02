"""
Stock de farmacia.

Un número que no coincide con el estante no sirve para nada: la primera vez que
falla, la gente vuelve al cuaderno. Así que lo que más se cuida acá es que el
stock no pueda quedar mal —ni en negativo, ni separado de su historial— y que se
pueda contestar a quién le tocó un lote.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.casos.models import Caso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from . import motor
from .models import Deposito, Existencia, Insumo, LineaPedido, Lote, Movimiento, Pedido


class StockTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_superuser("farma@cauce.local", "x", nombre="Farm")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.central = Deposito.objects.create(
            institucion=self.inst, nombre="Farmacia central", central=True
        )
        self.botiquin = Deposito.objects.create(
            institucion=self.inst, area=self.area, nombre="Botiquín de guardia"
        )
        self.dipirona = Insumo.objects.create(
            institucion=self.inst, nombre="Dipirona", presentacion="Ampolla 1 g",
            unidad="ampolla", stock_minimo=20,
        )
        self.gasa = Insumo.objects.create(
            institucion=self.inst, nombre="Gasa estéril", tipo=Insumo.Tipo.DESCARTABLE,
            requiere_lote=False, unidad="unidad",
        )

    def _lote(self, numero, dias=180, insumo=None):
        return Lote.objects.create(
            insumo=insumo or self.dipirona, numero=numero,
            vencimiento=timezone.localdate() + timedelta(days=dias),
        )


class IngresoTests(StockTestCase):
    def test_ingresar_suma_stock(self):
        l = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 100, lote=l, autor=self.user)
        self.assertEqual(motor.disponible(self.central, self.dipirona), 100)

    def test_un_insumo_que_lleva_lote_no_entra_sin_lote(self):
        """Sin lote no se puede responder un retiro de ANMAT."""
        with self.assertRaises(motor.ErrorStock):
            motor.ingresar(self.central, self.dipirona, 100, autor=self.user)

    def test_un_descartable_entra_sin_lote(self):
        """Exigírselo haría que se cargue cualquier cosa con tal de avanzar."""
        motor.ingresar(self.central, self.gasa, 500, autor=self.user)
        self.assertEqual(motor.disponible(self.central, self.gasa), 500)

    def test_no_se_ingresa_un_lote_vencido(self):
        viejo = Lote.objects.create(
            insumo=self.dipirona, numero="V1",
            vencimiento=timezone.localdate() - timedelta(days=1),
        )
        with self.assertRaises(motor.ErrorStock):
            motor.ingresar(self.central, self.dipirona, 10, lote=viejo, autor=self.user)

    def test_no_se_ingresa_un_lote_de_otro_insumo(self):
        otro = self._lote("G1", insumo=self.gasa)
        with self.assertRaises(motor.ErrorStock):
            motor.ingresar(self.central, self.dipirona, 10, lote=otro, autor=self.user)

    def test_cantidad_cero_o_negativa_no_pasa(self):
        l = self._lote("A1")
        for n in (0, -5):
            with self.subTest(n=n), self.assertRaises(motor.ErrorStock):
                motor.ingresar(self.central, self.dipirona, n, lote=l, autor=self.user)


class ConsumoTests(StockTestCase):
    def setUp(self):
        super().setUp()
        self.viejo = self._lote("VIEJO", dias=30)
        self.nuevo = self._lote("NUEVO", dias=300)
        motor.ingresar(self.botiquin, self.dipirona, 10, lote=self.viejo, autor=self.user)
        motor.ingresar(self.botiquin, self.dipirona, 50, lote=self.nuevo, autor=self.user)

    def test_saca_primero_lo_que_vence_antes(self):
        """
        Es la regla real de una farmacia. Sacar del lote más nuevo hace que el
        viejo venza en el estante y se tire.
        """
        motor.consumir(self.botiquin, self.dipirona, 4, autor=self.user)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.viejo), 6)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.nuevo), 50)

    def test_se_reparte_entre_lotes_cuando_uno_no_alcanza(self):
        movs = motor.consumir(self.botiquin, self.dipirona, 25, autor=self.user)
        self.assertEqual(len(movs), 2)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.viejo), 0)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.nuevo), 35)

    def test_no_se_consume_mas_de_lo_que_hay(self):
        with self.assertRaises(motor.ErrorStock):
            motor.consumir(self.botiquin, self.dipirona, 61, autor=self.user)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona), 60)

    def test_el_stock_nunca_queda_en_negativo(self):
        """Un stock negativo es un número que nadie sabe leer."""
        try:
            motor.consumir(self.botiquin, self.dipirona, 1000, autor=self.user)
        except motor.ErrorStock:
            pass
        self.assertFalse(Existencia.objects.filter(cantidad__lt=0).exists())

    def test_un_lote_vencido_no_se_puede_usar_pero_se_dice_que_esta(self):
        """
        No tener stock y tenerlo vencido son situaciones distintas: en la
        segunda hay algo que dar de baja y alguien a quien reclamarle.
        """
        Existencia.objects.filter(deposito=self.botiquin, lote=self.nuevo).delete()
        self.viejo.vencimiento = timezone.localdate() - timedelta(days=1)
        self.viejo.save()
        with self.assertRaises(motor.ErrorStock) as e:
            motor.consumir(self.botiquin, self.dipirona, 5, autor=self.user)
        self.assertIn("vencido", str(e.exception))

    def test_se_puede_forzar_un_lote(self):
        motor.consumir(self.botiquin, self.dipirona, 3, lote=self.nuevo, autor=self.user)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.nuevo), 47)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona, self.viejo), 10)


class TrazabilidadTests(StockTestCase):
    """La razón por la que el consumo se imputa al caso."""

    def setUp(self):
        super().setUp()
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.lote = self._lote("L-2026-A")
        motor.ingresar(self.botiquin, self.dipirona, 100, lote=self.lote, autor=self.user)

    def _caso(self, nombre):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        return Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)

    def test_se_puede_saber_a_quien_le_toco_un_lote(self):
        """
        Cuando ANMAT retira un lote hay que llamar a esas personas. Sin esto la
        única respuesta posible es «no sabemos».
        """
        for nombre in ("Ana", "Beto", "Caro"):
            motor.consumir(self.botiquin, self.dipirona, 2, caso=self._caso(nombre), autor=self.user)
        pacientes = {m.caso.ciudadano.nombre for m in motor.trazar_lote(self.lote)}
        self.assertEqual(pacientes, {"Ana", "Beto", "Caro"})

    def test_el_consumo_queda_colgado_del_caso(self):
        caso = self._caso("Ana")
        motor.consumir(self.botiquin, self.dipirona, 2, caso=caso, autor=self.user)
        self.assertEqual(caso.consumos.count(), 1)
        self.assertEqual(caso.consumos.first().insumo_id, self.dipirona.id)


class TransferenciaTests(StockTestCase):
    def setUp(self):
        super().setUp()
        self.lote = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 100, lote=self.lote, autor=self.user)

    def test_mueve_de_un_deposito_a_otro(self):
        motor.transferir(self.central, self.botiquin, self.dipirona, 30, autor=self.user)
        self.assertEqual(motor.disponible(self.central, self.dipirona), 70)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona), 30)

    def test_no_se_transfiere_lo_que_no_hay(self):
        with self.assertRaises(motor.ErrorStock):
            motor.transferir(self.central, self.botiquin, self.dipirona, 101, autor=self.user)

    def test_no_se_transfiere_a_si_mismo(self):
        with self.assertRaises(motor.ErrorStock):
            motor.transferir(self.central, self.central, self.dipirona, 10, autor=self.user)


class AjusteYBajaTests(StockTestCase):
    def setUp(self):
        super().setUp()
        self.lote = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 100, lote=self.lote, autor=self.user)

    def test_el_inventario_deja_el_stock_en_lo_contado(self):
        """
        Un inventario que no se puede corregir se abandona: la primera vez que
        el número no coincide, la gente vuelve al cuaderno.
        """
        motor.ajustar(self.central, self.dipirona, 94, lote=self.lote, autor=self.user,
                      motivo="Recuento mensual")
        self.assertEqual(motor.disponible(self.central, self.dipirona), 94)

    def test_la_diferencia_queda_registrada_y_no_es_un_numero_que_cambio_solo(self):
        m = motor.ajustar(self.central, self.dipirona, 94, lote=self.lote, autor=self.user,
                          motivo="Recuento mensual")
        self.assertEqual(m.tipo, Movimiento.Tipo.AJUSTE)
        self.assertEqual(m.cantidad, 6)
        self.assertIn("Recuento", m.motivo)

    def test_un_ajuste_que_no_cambia_nada_no_deja_movimiento(self):
        self.assertIsNone(
            motor.ajustar(self.central, self.dipirona, 100, lote=self.lote, autor=self.user)
        )

    def test_una_baja_necesita_motivo(self):
        """Sin motivo es indistinguible de un faltante."""
        with self.assertRaises(motor.ErrorStock):
            motor.dar_de_baja(self.central, self.dipirona, 5, lote=self.lote, autor=self.user)

    def test_la_baja_descuenta(self):
        motor.dar_de_baja(self.central, self.dipirona, 5, lote=self.lote, autor=self.user,
                          motivo="Ampollas rotas en el traslado")
        self.assertEqual(motor.disponible(self.central, self.dipirona), 95)


class CoherenciaTests(StockTestCase):
    """
    La invariante que sostiene el módulo.

    El stock es un acumulado que se guarda para no tener que sumar el historial
    cada vez, pero la verdad está en los movimientos. Si los dos se separan, el
    número deja de servir y nadie lo notaría a tiempo.
    """

    def test_el_stock_siempre_se_explica_por_sus_movimientos(self):
        a, b = self._lote("A1"), self._lote("B1", dias=400)
        caso_ciud = Ciudadano.objects.create(institucion=self.inst, nombre="Ana", apellido="T")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="G")
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(institucion=self.inst, version=ver, ciudadano=caso_ciud)

        motor.ingresar(self.central, self.dipirona, 100, lote=a, autor=self.user)
        motor.ingresar(self.central, self.dipirona, 60, lote=b, autor=self.user)
        motor.ingresar(self.central, self.gasa, 500, autor=self.user)
        motor.transferir(self.central, self.botiquin, self.dipirona, 40, autor=self.user)
        motor.consumir(self.botiquin, self.dipirona, 12, caso=caso, autor=self.user)
        motor.dar_de_baja(self.central, self.dipirona, 3, lote=b, autor=self.user, motivo="rotas")
        motor.ajustar(self.central, self.gasa, 480, autor=self.user, motivo="recuento")

        # Se recalcula desde cero y se compara con lo guardado.
        esperado = {}
        for m in Movimiento.objects.all():
            if m.destino_id:
                esperado[(m.destino_id, m.insumo_id, m.lote_id)] = (
                    esperado.get((m.destino_id, m.insumo_id, m.lote_id), 0) + m.cantidad
                )
            if m.origen_id:
                esperado[(m.origen_id, m.insumo_id, m.lote_id)] = (
                    esperado.get((m.origen_id, m.insumo_id, m.lote_id), 0) - m.cantidad
                )
        real = {
            (e.deposito_id, e.insumo_id, e.lote_id): e.cantidad
            for e in Existencia.objects.all()
        }
        for clave, cant in real.items():
            with self.subTest(clave=clave):
                self.assertEqual(
                    cant, esperado.get(clave, 0),
                    "el stock guardado no coincide con la suma de sus movimientos",
                )

    def test_un_movimiento_no_se_puede_borrar_dejando_el_stock_intacto(self):
        """
        No hay una regla técnica que lo impida, pero el módulo se apoya en que
        no pase: este test documenta la consecuencia si alguien lo hace.
        """
        a = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 10, lote=a, autor=self.user)
        Movimiento.objects.all().delete()
        self.assertEqual(
            motor.disponible(self.central, self.dipirona), 10,
            "borrar el historial dejó el stock huérfano: los movimientos no se borran",
        )


class AlertasTests(StockTestCase):
    def test_avisa_lo_que_esta_por_debajo_del_minimo(self):
        l = self._lote("A1")
        motor.ingresar(self.botiquin, self.dipirona, 5, lote=l, autor=self.user)  # mínimo 20
        faltantes = motor.bajo_minimo(self.inst)
        self.assertEqual(len(faltantes), 1)
        self.assertEqual(faltantes[0]["insumo"].id, self.dipirona.id)
        self.assertEqual(faltantes[0]["cantidad"], 5)

    def test_el_minimo_se_mira_por_deposito_y_no_por_hospital(self):
        """
        «Hay 200 en el hospital» no le sirve a la guardia a las 3 de la mañana,
        que necesita saber si hay en SU botiquín.
        """
        l = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 200, lote=l, autor=self.user)
        motor.ingresar(self.botiquin, self.dipirona, 3, lote=l, autor=self.user)
        depositos = {f["deposito"].nombre for f in motor.bajo_minimo(self.inst)}
        self.assertIn("Botiquín de guardia", depositos)
        self.assertNotIn("Farmacia central", depositos)

    def test_avisa_lo_que_vence_pronto(self):
        pronto = self._lote("P1", dias=20)
        lejos = self._lote("L1", dias=400)
        motor.ingresar(self.central, self.dipirona, 10, lote=pronto, autor=self.user)
        motor.ingresar(self.central, self.dipirona, 10, lote=lejos, autor=self.user)
        lotes = {v["existencia"].lote.numero for v in motor.por_vencer(self.inst, dias=60)}
        self.assertEqual(lotes, {"P1"})

    def test_no_avisa_de_un_lote_que_ya_se_consumio_entero(self):
        """Avisar de lo que no está es ruido, y el ruido hace que se deje de mirar."""
        pronto = self._lote("P1", dias=20)
        motor.ingresar(self.central, self.dipirona, 10, lote=pronto, autor=self.user)
        motor.dar_de_baja(self.central, self.dipirona, 10, lote=pronto, autor=self.user,
                          motivo="vencido")
        self.assertEqual(motor.por_vencer(self.inst, dias=60), [])


class PedidoTests(StockTestCase):
    def setUp(self):
        super().setUp()
        self.lote = self._lote("A1")
        motor.ingresar(self.central, self.dipirona, 100, lote=self.lote, autor=self.user)
        motor.ingresar(self.central, self.gasa, 20, autor=self.user)
        self.pedido = Pedido.objects.create(
            origen=self.botiquin, destino=self.central, creado_por=self.user
        )
        self.l1 = LineaPedido.objects.create(pedido=self.pedido, insumo=self.dipirona, pedido_cant=30)
        self.l2 = LineaPedido.objects.create(pedido=self.pedido, insumo=self.gasa, pedido_cant=50)

    def test_entregar_mueve_el_stock(self):
        motor.entregar_pedido(self.pedido, {self.l1.id: 30, self.l2.id: 20}, autor=self.user)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona), 30)
        self.assertEqual(motor.disponible(self.botiquin, self.gasa), 20)

    def test_lo_que_se_entrego_de_menos_queda_visible(self):
        """
        Entregar de menos es lo normal cuando falta stock. Si el sistema sólo
        guardara lo pedido, el faltante desaparecería.
        """
        motor.entregar_pedido(self.pedido, {self.l1.id: 30, self.l2.id: 20}, autor=self.user)
        self.l2.refresh_from_db()
        self.assertEqual(self.l2.entregado, 20)
        self.assertEqual(self.l2.faltante, 30)

    def test_no_se_entrega_mas_de_lo_pedido(self):
        with self.assertRaises(motor.ErrorStock):
            motor.entregar_pedido(self.pedido, {self.l1.id: 90}, autor=self.user)

    def test_un_pedido_cerrado_no_se_entrega_dos_veces(self):
        motor.entregar_pedido(self.pedido, {self.l1.id: 10}, autor=self.user)
        self.pedido.refresh_from_db()
        with self.assertRaises(motor.ErrorStock):
            motor.entregar_pedido(self.pedido, {self.l1.id: 10}, autor=self.user)
        self.assertEqual(motor.disponible(self.botiquin, self.dipirona), 10)
