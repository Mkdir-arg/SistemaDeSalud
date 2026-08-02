"""
Farmacia por HTTP.

Los tests del motor llaman a las funciones; estos pegan a las rutas tal como las
arma la pantalla. Ya pasó una vez que una acción quedara declarada en el viewset
equivocado y los tests del motor no lo vieran.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano
from apps.casos.models import Caso

from .models import Deposito, Existencia, Insumo, LineaPedido, Lote, Movimiento, Pedido


class FarmaciaAPITests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            "farma@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.central = Deposito.objects.create(
            institucion=self.inst, nombre="Farmacia central", central=True
        )
        self.botiquin = Deposito.objects.create(
            institucion=self.inst, area=self.area, nombre="Botiquín"
        )
        self.insumo = Insumo.objects.create(
            institucion=self.inst, nombre="Dipirona", presentacion="Ampolla 1 g",
            unidad="ampolla", stock_minimo=20,
        )
        self.lote = Lote.objects.create(
            insumo=self.insumo, numero="A1",
            vencimiento=timezone.localdate() + timedelta(days=200),
        )

    def _ingresar(self, cant=100, deposito=None):
        return self.client.post("/api/movimientos-stock/ingreso/", {
            "deposito": (deposito or self.central).id, "insumo": self.insumo.id,
            "cantidad": cant, "lote": self.lote.id,
        })

    # --- Movimientos ---------------------------------------------------------- #

    def test_las_acciones_existen_donde_las_pide_la_pantalla(self):
        """Guarda contra una acción declarada en el viewset equivocado."""
        for ruta, cuerpo in [
            ("ingreso", {"deposito": self.central.id, "insumo": self.insumo.id,
                         "cantidad": 1, "lote": self.lote.id}),
            ("consumo", {"deposito": self.central.id, "insumo": self.insumo.id, "cantidad": 1}),
            ("transferencia", {"origen": self.central.id, "destino": self.botiquin.id,
                               "insumo": self.insumo.id, "cantidad": 1}),
            ("ajuste", {"deposito": self.central.id, "insumo": self.insumo.id, "contado": 0}),
            ("baja", {"deposito": self.central.id, "insumo": self.insumo.id,
                      "cantidad": 1, "motivo": "x"}),
        ]:
            with self.subTest(accion=ruta):
                r = self.client.post(f"/api/movimientos-stock/{ruta}/", cuerpo)
                self.assertNotEqual(r.status_code, 404, f"{ruta} no existe")

    def test_ingresar_por_http(self):
        r = self._ingresar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            Existencia.objects.get(deposito=self.central, lote=self.lote).cantidad, 100
        )

    def test_el_error_de_stock_llega_con_su_texto(self):
        """
        «No alcanza» tiene que decir cuánto hay: sin eso, quien opera prueba
        números hasta acertar.
        """
        self._ingresar(5)
        r = self.client.post("/api/movimientos-stock/consumo/", {
            "deposito": self.central.id, "insumo": self.insumo.id, "cantidad": 10,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("hay 5", r.data["detail"])

    def test_un_movimiento_no_se_crea_por_post_directo(self):
        """Cada tipo mueve el stock distinto: validarlo en el serializer duplicaría el motor."""
        r = self.client.post("/api/movimientos-stock/", {
            "tipo": "ingreso", "insumo": self.insumo.id, "cantidad": 999,
        })
        self.assertEqual(r.status_code, 405)
        self.assertEqual(Movimiento.objects.count(), 0)

    def test_un_movimiento_no_se_puede_editar_ni_borrar(self):
        """Un historial reescribible no sirve para auditar."""
        self._ingresar()
        m = Movimiento.objects.first()
        self.assertEqual(self.client.patch(f"/api/movimientos-stock/{m.id}/", {"cantidad": 1}).status_code, 405)
        self.assertEqual(self.client.delete(f"/api/movimientos-stock/{m.id}/").status_code, 405)

    def test_el_stock_no_se_puede_escribir(self):
        """Rompería lo único que el módulo garantiza."""
        self._ingresar()
        e = Existencia.objects.first()
        self.assertEqual(self.client.patch(f"/api/stock/{e.id}/", {"cantidad": 9999}).status_code, 405)
        e.refresh_from_db()
        self.assertEqual(e.cantidad, 100)

    def test_el_ajuste_que_coincide_lo_dice_en_vez_de_fingir(self):
        """Si dijera «listo», la persona buscaría un movimiento que no existe."""
        self._ingresar()
        r = self.client.post("/api/movimientos-stock/ajuste/", {
            "deposito": self.central.id, "insumo": self.insumo.id,
            "contado": 100, "lote": self.lote.id,
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("coincide", r.data["detail"])

    # --- Trazabilidad ---------------------------------------------------------- #

    def test_trazar_un_lote_devuelve_los_pacientes(self):
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="G")
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        Nodo.objects.create(version=ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self._ingresar()
        for nombre in ("Ana", "Beto"):
            c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
            caso = Caso.objects.create(institucion=self.inst, version=ver, ciudadano=c)
            self.client.post("/api/movimientos-stock/consumo/", {
                "deposito": self.central.id, "insumo": self.insumo.id,
                "cantidad": 2, "caso": caso.id,
            })
        r = self.client.get(f"/api/movimientos-stock/trazar-lote/?lote={self.lote.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({p["paciente"] for p in r.data["pacientes"]}, {"Ana T", "Beto T"})

    def test_trazar_sin_lote_lo_dice(self):
        self.assertEqual(
            self.client.get("/api/movimientos-stock/trazar-lote/").status_code, 400
        )

    # --- Alertas ---------------------------------------------------------------- #

    def test_las_alertas_traen_faltantes_y_vencimientos_juntos(self):
        """
        Son la misma pregunta operativa —qué tengo que resolver hoy— y
        separarlas obliga a mirar dos pantallas.
        """
        self._ingresar(5)  # mínimo 20
        pronto = Lote.objects.create(
            insumo=self.insumo, numero="P1",
            vencimiento=timezone.localdate() + timedelta(days=10),
        )
        self.client.post("/api/movimientos-stock/ingreso/", {
            "deposito": self.central.id, "insumo": self.insumo.id, "cantidad": 3, "lote": pronto.id,
        })
        r = self.client.get(f"/api/pedidos-stock/alertas/?institucion={self.inst.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["faltantes"]), 1)
        self.assertEqual([v["lote"] for v in r.data["por_vencer"]], ["P1"])

    # --- Pedidos ----------------------------------------------------------------- #

    def test_un_pedido_se_crea_con_sus_renglones(self):
        """Un pedido sin líneas no es un pedido."""
        r = self.client.post("/api/pedidos-stock/", {
            "origen": self.botiquin.id, "destino": self.central.id,
            "items": [{"insumo": self.insumo.id, "cantidad": 30}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data["lineas"]), 1)

    def test_un_deposito_no_se_pide_a_si_mismo(self):
        r = self.client.post("/api/pedidos-stock/", {
            "origen": self.central.id, "destino": self.central.id,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_entregar_mueve_el_stock_y_deja_ver_el_faltante(self):
        self._ingresar(10)
        p = Pedido.objects.create(origen=self.botiquin, destino=self.central)
        linea = LineaPedido.objects.create(pedido=p, insumo=self.insumo, pedido_cant=30)
        r = self.client.post(f"/api/pedidos-stock/{p.id}/entregar/",
                             {"entregas": {str(linea.id): 10}}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        linea.refresh_from_db()
        self.assertEqual(linea.entregado, 10)
        self.assertEqual(linea.faltante, 20)


class FarmaciaPermisosTests(APITestCase):
    """Cargar el catálogo y mover stock son cosas distintas."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.dep = Deposito.objects.create(institucion=self.inst, nombre="Central", central=True)
        self.insumo = Insumo.objects.create(
            institucion=self.inst, nombre="Gasa", requiere_lote=False, unidad="unidad"
        )
        self.usuarios = {}
        for rol in ("admin", "enfermeria", "configurador"):
            u = Usuario.objects.create_user(f"{rol}@test.local", "x")
            Membresia.objects.create(usuario=u, institucion=self.inst, rol=rol, activo=True)
            self.usuarios[rol] = u

    def _como(self, rol):
        self.client.force_authenticate(self.usuarios[rol])

    def test_enfermeria_registra_consumo(self):
        self._como("admin")
        self.client.post("/api/movimientos-stock/ingreso/", {
            "deposito": self.dep.id, "insumo": self.insumo.id, "cantidad": 50,
        })
        self._como("enfermeria")
        r = self.client.post("/api/movimientos-stock/consumo/", {
            "deposito": self.dep.id, "insumo": self.insumo.id, "cantidad": 2,
        })
        self.assertEqual(r.status_code, 201, r.data)

    def test_enfermeria_no_carga_el_catalogo(self):
        """Definir qué insumos existen es configurar la institución."""
        self._como("enfermeria")
        r = self.client.post("/api/insumos/", {"institucion": self.inst.id, "nombre": "Nuevo"})
        self.assertEqual(r.status_code, 403)

    def test_el_configurador_no_toca_el_stock(self):
        """Diseña flujos; la farmacia no es suya."""
        self._como("configurador")
        r = self.client.post("/api/movimientos-stock/consumo/", {
            "deposito": self.dep.id, "insumo": self.insumo.id, "cantidad": 1,
        })
        self.assertEqual(r.status_code, 403)
