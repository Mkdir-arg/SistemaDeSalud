"""AUD-052/054: transiciones válidas y conservación de entregas existentes."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.contrib import admin
from django.db import connection, connections
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.admin import AreaAdmin
from apps.instituciones.models import Area, Institucion

from . import motor
from .models import Deposito, Existencia, Insumo, LineaPedido, Movimiento, Pedido
from .views import PedidoViewSet


class EscenarioPedido:
    def preparar(self):
        self.usuario = Usuario.objects.create_superuser("pedidos-auditoria@example.test", "x")
        self.institucion = Institucion.objects.create(nombre="Farmacia sintética")
        self.central = Deposito.objects.create(institucion=self.institucion, nombre="Central", central=True)
        self.botiquin = Deposito.objects.create(institucion=self.institucion, nombre="Botiquín")
        self.insumo = Insumo.objects.create(institucion=self.institucion, nombre="Insumo sintético", requiere_lote=False)
        motor.ingresar(self.central, self.insumo, 100, autor=self.usuario)
        self.pedido = Pedido.objects.create(origen=self.botiquin, destino=self.central, creado_por=self.usuario)
        self.linea = LineaPedido.objects.create(pedido=self.pedido, insumo=self.insumo, pedido_cant=30)

    def cliente(self, usuario=None):
        cliente = APIClient()
        cliente.force_authenticate(usuario or self.usuario)
        return cliente

    def accion(self, accion, datos=None):
        datos = dict(datos or {})
        if accion == "entregar":
            # Clave de operación obligatoria (#172, AUD-053): cada entrega es nueva.
            datos.setdefault("clave", str(uuid4()))
        return self.cliente().post(f"/api/pedidos-stock/{self.pedido.pk}/{accion}/", datos, format="json")

    def evidencia(self):
        return (
            list(Movimiento.objects.order_by("pk").values()),
            list(Existencia.objects.order_by("pk").values()),
            list(LineaPedido.objects.filter(pedido=self.pedido).order_by("pk").values()),
        )


class PedidosConservacionAuditoria172Tests(EscenarioPedido, APITestCase):
    def setUp(self):
        self.preparar()

    def test_rechazo_parcial_cierra_solo_faltante_y_conserva_evidencia(self):
        self.assertEqual(self.accion("entregar", {"entregas": {str(self.linea.pk): 10}}).status_code, 200)
        anterior = self.evidencia()
        respuesta = self.accion("rechazar", {"motivo": "No se despacha el saldo"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self.evidencia(), anterior)
        self.pedido.refresh_from_db(); self.linea.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.RECHAZADO)
        self.assertIsNotNone(self.pedido.resuelto)
        self.assertEqual((self.linea.pedido_cant, self.linea.entregado), (30, 10))
        self.assertIn("No se despacha el saldo", self.pedido.observaciones)
        self.assertEqual(self.accion("preparar").status_code, 400)
        self.assertEqual(self.accion("entregar", {"entregas": {str(self.linea.pk): 20}}).status_code, 400)
        self.assertEqual(self.evidencia(), anterior)

    def test_delete_pendiente_con_o_sin_lineas_se_conserva_y_se_cierra_por_rechazo(self):
        for con_lineas in (False, True):
            with self.subTest(con_lineas=con_lineas):
                pedido = Pedido.objects.create(origen=self.botiquin, destino=self.central)
                if con_lineas:
                    LineaPedido.objects.create(pedido=pedido, insumo=self.insumo, pedido_cant=1)
                antes = list(pedido.lineas.values())
                url = f"/api/pedidos-stock/{pedido.pk}/"
                respuesta = self.cliente().delete(url)
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
                self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())
                self.assertEqual(list(pedido.lineas.values()), antes)
                respuesta = self.cliente().post(url + "rechazar/", {"motivo": "Cancelado por titular"})
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data["estado"], Pedido.Estado.RECHAZADO)
                self.assertEqual(self.cliente().delete(url).status_code, 409)
                self.assertEqual(list(pedido.lineas.values()), antes)

    def test_no_rechaza_entregado_completo_ni_repite_rechazo(self):
        self.assertEqual(self.accion("entregar", {"entregas": {str(self.linea.pk): 30}}).status_code, 200)
        anterior = self.evidencia()
        self.assertEqual(self.accion("rechazar", {"motivo": "Fuera de tiempo"}).status_code, 400)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ENTREGADO)
        self.assertEqual(self.evidencia(), anterior)

    def test_delete_preparado_parcial_entregado_o_rechazado_preserva_pedido_y_lineas(self):
        for estado, cantidad in ((Pedido.Estado.PREPARADO, 0), (Pedido.Estado.PARCIAL, 10),
                                  (Pedido.Estado.ENTREGADO, 30), (Pedido.Estado.RECHAZADO, 0)):
            with self.subTest(estado=estado):
                Pedido.objects.filter(pk=self.pedido.pk).update(estado=estado)
                LineaPedido.objects.filter(pk=self.linea.pk).update(entregado=cantidad)
                anterior = self.evidencia()
                respuesta = self.cliente().delete(f"/api/pedidos-stock/{self.pedido.pk}/")
                self.assertEqual(respuesta.status_code, 409)
                self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())
                self.assertEqual(self.evidencia(), anterior)

    def test_delete_no_pierde_entrega_real_parcial_o_completa(self):
        for cantidad in (10, 30):
            with self.subTest(cantidad=cantidad):
                pedido = Pedido.objects.create(origen=self.botiquin, destino=self.central, creado_por=self.usuario)
                linea = LineaPedido.objects.create(pedido=pedido, insumo=self.insumo, pedido_cant=30)
                motor.entregar_pedido(pedido, {linea.pk: cantidad}, autor=self.usuario)
                movimientos = list(Movimiento.objects.order_by("pk").values())
                existencias = list(Existencia.objects.order_by("pk").values())
                respuesta = self.cliente().delete(f"/api/pedidos-stock/{pedido.pk}/")
                self.assertEqual(respuesta.status_code, 409)
                self.assertTrue(LineaPedido.objects.filter(pk=linea.pk, entregado=cantidad).exists())
                self.assertEqual(list(Movimiento.objects.order_by("pk").values()), movimientos)
                self.assertEqual(list(Existencia.objects.order_by("pk").values()), existencias)

    def test_delete_pendiente_inconsistente_con_entrega_o_resolucion_se_conserva(self):
        from django.utils import timezone

        for campo in ("entregado", "resuelto", "movimiento"):
            with self.subTest(evidencia=campo):
                pedido = Pedido.objects.create(origen=self.botiquin, destino=self.central)
                linea = LineaPedido.objects.create(pedido=pedido, insumo=self.insumo, pedido_cant=30)
                if campo == "entregado":
                    LineaPedido.objects.filter(pk=linea.pk).update(entregado=1)
                elif campo == "resuelto":
                    Pedido.objects.filter(pk=pedido.pk).update(resuelto=timezone.now())
                else:
                    motor.ingresar(self.central, self.insumo, 1, autor=self.usuario,
                                   motivo=f"Pedido #{pedido.pk}")
                anterior = self.evidencia()
                respuesta = self.cliente().delete(f"/api/pedidos-stock/{pedido.pk}/")
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
                self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())
                self.assertTrue(LineaPedido.objects.filter(pk=linea.pk).exists())
                self.assertEqual(self.evidencia(), anterior)

    def test_otro_ambito_no_rechaza_ni_borra_pedido_y_medico_no_administra_stock(self):
        otra = Institucion.objects.create(nombre="Institución ajena")
        ajeno = Usuario.objects.create_user("ajeno-pedido@example.test", "x")
        medico = Usuario.objects.create_user("medico-pedido@example.test", "x")
        Membresia.objects.create(usuario=ajeno, institucion=otra, rol=Membresia.Rol.ADMIN_INSTITUCION)
        Membresia.objects.create(usuario=medico, institucion=self.institucion, rol=Membresia.Rol.MEDICO)
        self.assertEqual(self.cliente(ajeno).post(f"/api/pedidos-stock/{self.pedido.pk}/rechazar/", {}).status_code, 404)
        self.assertEqual(self.cliente(ajeno).delete(f"/api/pedidos-stock/{self.pedido.pk}/").status_code, 404)
        self.assertEqual(self.cliente(medico).post(f"/api/pedidos-stock/{self.pedido.pk}/rechazar/", {}).status_code, 403)
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL")
class PedidosConcurrentesAuditoria172Tests(EscenarioPedido, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def intercalar(self, accion_obsoleta, datos, primero):
        leido, continuar = Event(), Event()
        original, hilo = PedidoViewSet.get_object, {}

        def pausar(view):
            pedido = original(view)
            if get_ident() == hilo.get("id"):
                leido.set()
                if not continuar.wait(timeout=10):
                    raise AssertionError("No se liberó la solicitud con pedido obsoleto")
            return pedido

        def solicitar():
            try:
                hilo["id"] = get_ident()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                cliente = self.cliente(Usuario.objects.get(pk=self.usuario.pk))
                base = f"/api/pedidos-stock/{self.pedido.pk}/"
                if accion_obsoleta == "destroy":
                    respuesta = cliente.delete(base)
                elif accion_obsoleta == "partial_update":
                    respuesta = cliente.patch(base, datos, format="json")
                else:
                    respuesta = cliente.post(base + accion_obsoleta + "/", datos, format="json")
                return respuesta.status_code, getattr(respuesta, "data", None)
            finally:
                connections.close_all()

        with patch.object(PedidoViewSet, "get_object", pausar):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(solicitar)
                try:
                    self.assertTrue(leido.wait(timeout=10))
                    primero()
                finally:
                    continuar.set()
                return futuro.result(timeout=12)

    def entregar(self, cantidad):
        respuesta = self.accion("entregar", {"entregas": {str(self.linea.pk): cantidad}})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_rechazo_obsoleto_tras_borrado_orm_confiable_responde_error_controlado(self):
        def borrar():
            # Limpieza ORM privilegiada: DELETE API conserva todos los pedidos.
            Pedido.objects.filter(pk=self.pedido.pk).delete()

        codigo, detalle = self.intercalar("rechazar", {"motivo": "Lectura anterior"}, borrar)
        self.assertEqual(codigo, 400, detalle)
        self.assertFalse(Pedido.objects.filter(pk=self.pedido.pk).exists())

    def test_rechazo_obsoleto_no_pisa_entrega_completa(self):
        codigo, detalle = self.intercalar("rechazar", {"motivo": "Viejo"}, lambda: self.entregar(30))
        self.assertEqual(codigo, 400, detalle)
        self.pedido.refresh_from_db(); self.linea.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.ENTREGADO)
        self.assertEqual(self.linea.entregado, 30)

    def test_rechazo_obsoleto_no_pisa_entrega_parcial(self):
        codigo, detalle = self.intercalar("rechazar", {"motivo": "Viejo"}, lambda: self.entregar(10))
        self.assertEqual(codigo, 400, detalle)
        self.pedido.refresh_from_db(); self.linea.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.PARCIAL)
        self.assertEqual(self.linea.entregado, 10)

    def test_rechazo_obsoleto_no_pisa_preparacion(self):
        def preparar():
            respuesta = self.accion("preparar")
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
        codigo, detalle = self.intercalar("rechazar", {"motivo": "Viejo"}, preparar)
        self.assertEqual(codigo, 400, detalle)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Pedido.Estado.PREPARADO)

    def test_entregar_y_preparar_obsoletos_no_reabren_rechazado(self):
        for accion in ("entregar", "preparar"):
            with self.subTest(accion=accion):
                Pedido.objects.filter(pk=self.pedido.pk).update(estado=Pedido.Estado.PENDIENTE, resuelto=None)
                antes = self.evidencia()
                codigo, detalle = self.intercalar(accion, {"entregas": {str(self.linea.pk): 10}},
                    lambda: self.assertEqual(self.accion("rechazar", {"motivo": "No despachar"}).status_code, 200))
                self.assertEqual(codigo, 400, detalle)
                self.pedido.refresh_from_db()
                self.assertEqual(self.pedido.estado, Pedido.Estado.RECHAZADO)
                self.assertEqual(self.evidencia(), antes)

    def test_delete_obsoleto_no_elimina_pedido_con_entrega_nueva(self):
        codigo, detalle = self.intercalar("destroy", {}, lambda: self.entregar(10))
        self.assertEqual(codigo, 409, detalle)
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk, estado=Pedido.Estado.PARCIAL).exists())
        self.assertTrue(LineaPedido.objects.filter(pk=self.linea.pk, entregado=10).exists())

    def test_patch_obsoleto_no_restaura_estado_pendiente(self):
        codigo, detalle = self.intercalar("partial_update", {"urgente": True}, lambda: self.entregar(30))
        self.assertEqual(codigo, 200, detalle)
        self.pedido.refresh_from_db(); self.linea.refresh_from_db()
        self.assertTrue(self.pedido.urgente)
        self.assertEqual(self.pedido.estado, Pedido.Estado.ENTREGADO)
        self.assertIsNotNone(self.pedido.resuelto)
        self.assertEqual(self.linea.entregado, 30)
        self.assertEqual(detalle["estado"], Pedido.Estado.ENTREGADO)
        self.assertEqual(detalle["lineas"][0]["entregado"], 30)


class PedidosPadresConservacionAuditoria172Tests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_superuser("padres-pedido@example.test", "x")
        self.institucion = Institucion.objects.create(nombre="Padres sintéticos")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Área sintética")
        self.origen = Deposito.objects.create(institucion=self.institucion, area=self.area, nombre="Pide")
        self.destino = Deposito.objects.create(institucion=self.institucion, nombre="Abastece")
        self.insumo = Insumo.objects.create(institucion=self.institucion, nombre="Insumo sin efectos", requiere_lote=False)
        self.pedido = Pedido.objects.create(origen=self.origen, destino=self.destino)
        self.linea = LineaPedido.objects.create(pedido=self.pedido, insumo=self.insumo, pedido_cant=1)
        self.client.force_authenticate(self.usuario)

    def comprobar_conservacion(self):
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk, estado=Pedido.Estado.PENDIENTE).exists())
        self.assertTrue(LineaPedido.objects.filter(pk=self.linea.pk, pedido=self.pedido).exists())
        self.assertEqual(Deposito.objects.filter(pk__in=(self.origen.pk, self.destino.pk)).count(), 2)

    def test_deposito_api_protegido_en_ambas_relaciones_devuelve_409(self):
        for deposito in (self.origen, self.destino):
            with self.subTest(deposito=deposito.pk):
                respuesta = self.client.delete(f"/api/depositos/{deposito.pk}/")
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
                self.comprobar_conservacion()

    def test_deposito_orm_individual_y_bulk_no_cascadan_pedidos(self):
        for deposito in (self.origen, self.destino):
            with self.subTest(deposito=deposito.pk):
                with self.assertRaises(ProtectedError):
                    deposito.delete()
                self.comprobar_conservacion()
        with self.assertRaises(ProtectedError):
            Deposito.objects.filter(pk__in=(self.origen.pk, self.destino.pk)).delete()
        self.comprobar_conservacion()

    def test_institucion_orm_no_cascada_pedido_incluso_sin_lineas(self):
        # Aislar el nuevo PROTECT de Pedido: no depender del PROTECT de Insumo.
        self.linea.delete()
        with self.assertRaises(ProtectedError):
            self.institucion.delete()
        self.assertTrue(Institucion.objects.filter(pk=self.institucion.pk).exists())
        self.assertTrue(Pedido.objects.filter(pk=self.pedido.pk).exists())
        self.assertEqual(Deposito.objects.filter(pk__in=(self.origen.pk, self.destino.pk)).count(), 2)

    def test_area_api_desvincula_deposito_sin_borrar_pedido(self):
        respuesta = self.client.delete(f"/api/areas/{self.area.pk}/")
        self.assertEqual(respuesta.status_code, 204, getattr(respuesta, "data", None))
        self.origen.refresh_from_db()
        self.assertIsNone(self.origen.area_id)
        self.comprobar_conservacion()

    def test_area_admin_individual_y_bulk_desvincula_sin_borrar_pedidos(self):
        request = RequestFactory().post("/admin/instituciones/area/")
        request.user = self.usuario
        modelo_admin = AreaAdmin(Area, admin.site)
        for bulk in (False, True):
            with self.subTest(bulk=bulk):
                area = Area.objects.create(institucion=self.institucion, nombre=f"Admin {bulk}")
                Deposito.objects.filter(pk=self.origen.pk).update(area=area)
                if bulk:
                    modelo_admin.delete_queryset(request, Area.objects.filter(pk=area.pk))
                else:
                    modelo_admin.delete_model(request, area)
                self.origen.refresh_from_db()
                self.assertIsNone(self.origen.area_id)
                self.comprobar_conservacion()
        # No existe administración directa de pedidos/depósitos que deba adaptarse.
        self.assertNotIn(Pedido, admin.site._registry)
        self.assertNotIn(Deposito, admin.site._registry)

    @override_settings(ENTORNO="demo")
    def test_reset_demo_con_pedido_protegido_revierte_borrados_previos(self):
        from apps.instituciones.views import NOMBRE_ESCUELA

        self.institucion.nombre = NOMBRE_ESCUELA
        self.institucion.save(update_fields=["nombre"])
        movimiento = motor.ingresar(self.destino, self.insumo, 3, autor=self.usuario)
        existencias = list(Existencia.objects.filter(deposito=self.destino).values())
        respuesta = self.client.post(f"/api/instituciones/{self.institucion.pk}/reset-escuela/")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertTrue(Movimiento.objects.filter(pk=movimiento.pk).exists())
        self.assertEqual(list(Existencia.objects.filter(deposito=self.destino).values()), existencias)
        self.comprobar_conservacion()
