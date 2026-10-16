"""AUD-048: exclusividad de profesional y preservación de ocupación vigente."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event, get_ident
from time import monotonic, sleep
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connection, connections
from django.test import RequestFactory, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario

from .models import Area, Box, Institucion
from .views import AreaViewSet, BoxViewSet


class EscenarioBoxes:
    def preparar(self):
        self.a = Institucion.objects.create(nombre="Institución A sintética")
        self.b = Institucion.objects.create(nombre="Institución B sintética")
        self.area = Area.objects.create(institucion=self.a, nombre="Guardia")
        self.box1 = Box.objects.create(area=self.area, nombre="Box 1")
        self.box2 = Box.objects.create(area=self.area, nombre="Box 2")
        self.medico = Usuario.objects.create_user("medico-box@example.test", "x")
        self.otro = Usuario.objects.create_user("otro-box@example.test", "x")
        self.ajeno = Usuario.objects.create_user("ajeno-box@example.test", "x")
        self.root = Usuario.objects.create_superuser("root-box@example.test", "x")
        for usuario, institucion in ((self.medico, self.a), (self.otro, self.a), (self.ajeno, self.b)):
            Membresia.objects.create(usuario=usuario, institucion=institucion, rol=Membresia.Rol.MEDICO)

    def cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def ocupar(self, usuario, box):
        return self.cliente(usuario).post(f"/api/boxes/{box.pk}/ocupar/", {}, format="json")


class BoxesReglasAuditoria172Tests(EscenarioBoxes, APITestCase):
    def setUp(self):
        self.preparar()

    def test_box_ocupado_rechaza_toma_y_conserva_box_anterior(self):
        self.box1.ocupado_por = self.medico
        self.box1.save(update_fields=["ocupado_por"])
        self.box2.ocupado_por = self.otro
        self.box2.save(update_fields=["ocupado_por"])
        respuesta = self.ocupar(self.medico, self.box2)
        self.assertEqual(respuesta.status_code, 409)
        self.box1.refresh_from_db(); self.box2.refresh_from_db()
        self.assertEqual(self.box1.ocupado_por_id, self.medico.pk)
        self.assertEqual(self.box2.ocupado_por_id, self.otro.pk)

    def test_transferencia_a_box_libre_conserva_unico_box(self):
        self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200)
        self.assertEqual(self.ocupar(self.medico, self.box2).status_code, 200)
        self.assertEqual(list(Box.objects.filter(ocupado_por=self.medico).values_list("pk", flat=True)), [self.box2.pk])
        self.box1.refresh_from_db()
        self.assertIsNone(self.box1.ocupado_desde)

    def test_reintentar_box_propio_no_reinicia_antiguedad(self):
        desde = timezone.now() - timedelta(hours=4)
        Box.objects.filter(pk=self.box1.pk).update(ocupado_por=self.medico, ocupado_desde=desde)
        self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200)
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.ocupado_desde, desde)

    def test_ambito_ajeno_y_liberacion_de_otro_rechazados(self):
        self.assertEqual(self.ocupar(self.ajeno, self.box1).status_code, 404)
        self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200)
        respuesta = self.cliente(self.otro).post(f"/api/boxes/{self.box1.pk}/liberar/", {})
        self.assertEqual(respuesta.status_code, 403)
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.ocupado_por_id, self.medico.pk)

    def test_medico_no_configura_ni_borra_box(self):
        cliente = self.cliente(self.medico)
        self.assertEqual(cliente.patch(f"/api/boxes/{self.box1.pk}/", {"nombre": "Otro"}).status_code, 403)
        self.assertEqual(cliente.delete(f"/api/boxes/{self.box1.pk}/").status_code, 403)

    def test_api_no_borra_box_ocupado(self):
        self.ocupar(self.medico, self.box1)
        respuesta = self.cliente(self.root).delete(f"/api/boxes/{self.box1.pk}/")
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(Box.objects.filter(pk=self.box1.pk).exists())

    def test_admin_no_expone_campos_operativos(self):
        request = RequestFactory().get("/admin/instituciones/box/")
        request.user = self.root
        formulario = admin.site._registry[Box].get_form(request, self.box1)
        self.assertNotIn("ocupado_por", formulario.base_fields)
        self.assertNotIn("ocupado_desde", formulario.base_fields)

    def test_admin_guardar_instancia_vieja_conserva_ocupacion_actual(self):
        vieja = Box.objects.get(pk=self.box1.pk)
        vieja.nombre = "Nombre actualizado"
        desde = timezone.now()
        Box.objects.filter(pk=self.box1.pk).update(ocupado_por=self.medico, ocupado_desde=desde)
        request = RequestFactory().post("/admin/instituciones/box/")
        request.user = self.root
        admin.site._registry[Box].save_model(request, vieja, SimpleNamespace(changed_data=["nombre"]), True)
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.nombre, "Nombre actualizado")
        self.assertEqual(self.box1.ocupado_por_id, self.medico.pk)
        self.assertEqual(self.box1.ocupado_desde, desde)

    def test_admin_delete_y_bulk_revalidan_ocupacion(self):
        request = RequestFactory().post("/admin/instituciones/box/")
        request.user = self.root
        modelo_admin = admin.site._registry[Box]
        vieja = Box.objects.get(pk=self.box1.pk)
        Box.objects.filter(pk=self.box1.pk).update(ocupado_por=self.medico)
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_model(request, vieja)
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_queryset(request, Box.objects.filter(pk__in=[self.box1.pk, self.box2.pk]))
        self.assertEqual(Box.objects.filter(pk__in=[self.box1.pk, self.box2.pk]).count(), 2)

    def test_api_area_ocupada_no_borra_box_por_cascada(self):
        self.ocupar(self.medico, self.box1)
        respuesta = self.cliente(self.root).delete(f"/api/areas/{self.area.pk}/")
        self.assertEqual(respuesta.status_code, 409)
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())
        self.assertTrue(Box.objects.filter(pk=self.box1.pk, ocupado_por=self.medico).exists())

    def test_admin_area_individual_y_bulk_no_borran_boxes_ocupados(self):
        self.ocupar(self.medico, self.box1)
        request = RequestFactory().post("/admin/instituciones/area/")
        request.user = self.root
        modelo_admin = admin.site._registry[Area]
        vacia = Area.objects.create(institucion=self.a, nombre="Área vacía")
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_model(request, self.area)
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_queryset(request, Area.objects.filter(pk__in=[self.area.pk, vacia.pk]))
        self.assertEqual(Area.objects.filter(pk__in=[self.area.pk, vacia.pk]).count(), 2)
        self.assertTrue(Box.objects.filter(pk=self.box1.pk, ocupado_por=self.medico).exists())

    def test_admin_area_vacia_se_puede_borrar(self):
        request = RequestFactory().post("/admin/instituciones/area/")
        request.user = self.root
        vacia = Area.objects.create(institucion=self.a, nombre="Área borrable")
        pk = vacia.pk
        admin.site._registry[Area].delete_model(request, vacia)
        self.assertFalse(Area.objects.filter(pk=pk).exists())

    def test_inline_de_institucion_no_permite_borrar_areas(self):
        request = RequestFactory().get("/admin/instituciones/institucion/")
        request.user = self.root
        inline = next(i for i in admin.site._registry[Institucion].get_inline_instances(request, self.a) if i.model is Area)
        self.assertFalse(inline.get_formset(request, self.a).can_delete)

    def test_institucion_no_se_borra_por_api_ni_admin_y_conserva_firmada(self):
        from apps.registros import integridad
        from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica

        paciente = Ciudadano.objects.create(institucion=self.a, nombre="Paciente firmado sintético")
        historia = HistoriaClinica.objects.create(ciudadano=paciente)
        entrada = EntradaHistoria.objects.create(
            historia=historia, autor=self.medico, titulo="Atención", contenido="Firmada sintética", firmada=True,
        )
        integridad.sellar(entrada)
        respuesta = self.cliente(self.root).delete(f"/api/instituciones/{self.a.pk}/")
        self.assertEqual(respuesta.status_code, 403)
        request = RequestFactory().post("/admin/instituciones/institucion/")
        request.user = self.root
        modelo_admin = admin.site._registry[Institucion]
        self.assertFalse(modelo_admin.has_delete_permission(request, self.a))
        self.assertNotIn("delete_selected", modelo_admin.get_actions(request))
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_model(request, self.a)
        with self.assertRaises(PermissionDenied):
            modelo_admin.delete_queryset(request, Institucion.objects.filter(pk=self.a.pk))
        entrada.refresh_from_db()
        self.assertTrue(integridad.verificar(entrada)["ok"])
        self.assertTrue(Box.objects.filter(pk=self.box1.pk).exists())

    def test_admin_http_no_borra_institucion_individual_ni_bulk(self):
        self.ocupar(self.medico, self.box1)
        self.client.force_login(self.root)
        respuesta = self.client.post(f"/admin/instituciones/institucion/{self.a.pk}/delete/", {"post": "yes"})
        self.assertEqual(respuesta.status_code, 403)
        self.client.post("/admin/instituciones/institucion/", {
            "action": "delete_selected", "_selected_action": [str(self.a.pk)], "post": "yes",
        })
        self.assertTrue(Institucion.objects.filter(pk=self.a.pk).exists())
        self.assertTrue(Box.objects.filter(pk=self.box1.pk, ocupado_por=self.medico).exists())


@skipUnless(connection.vendor == "postgresql", "Requiere conexiones PostgreSQL y bloqueos reales")
class BoxesConcurrenciaAuditoria172Tests(EscenarioBoxes, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def _ocupar_con_lock(self, mismo_usuario):
        primera_pausada, liberar, segunda_lista = Event(), Event(), Event()
        identificadores, pids = {}, {}
        guardar_original = Box.save

        def pausar_guardado(box, *args, **kwargs):
            if get_ident() == identificadores.get("primera") and box.pk == self.box1.pk:
                primera_pausada.set()
                if not liberar.wait(timeout=10):
                    raise AssertionError("Timeout liberando primera ocupación")
            return guardar_original(box, *args, **kwargs)

        def operar(clave, usuario, box):
            try:
                identificadores[clave] = get_ident()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids[clave] = cursor.fetchone()[0]
                if clave == "segunda":
                    segunda_lista.set()
                respuesta = self.ocupar(Usuario.objects.get(pk=usuario.pk), box)
                return respuesta.status_code
            finally:
                connections.close_all()

        with patch.object(Box, "save", pausar_guardado):
            with ThreadPoolExecutor(max_workers=2) as pool:
                primera = pool.submit(operar, "primera", self.medico, self.box1)
                try:
                    self.assertTrue(primera_pausada.wait(timeout=10))
                    segunda = pool.submit(operar, "segunda", self.medico if mismo_usuario else self.otro,
                                          self.box2 if mismo_usuario else self.box1)
                    self.assertTrue(segunda_lista.wait(timeout=10))
                    limite, espera = monotonic() + 3, False
                    while monotonic() < limite:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pids["segunda"]])
                            espera = pids["primera"] in cursor.fetchone()[0]
                        if espera:
                            break
                        sleep(0.02)
                    self.assertTrue(espera, "La segunda ocupación no esperó el recurso compartido")
                finally:
                    liberar.set()
                codigos = [primera.result(timeout=12), segunda.result(timeout=12)]
        return codigos

    def test_mismo_profesional_dos_boxes_serializa_y_conserva_unico(self):
        self.assertEqual(self._ocupar_con_lock(True), [200, 200])
        self.assertEqual(Box.objects.filter(ocupado_por=self.medico).count(), 1)
        self.box2.refresh_from_db()
        self.assertEqual(self.box2.ocupado_por_id, self.medico.pk)

    def test_dos_profesionales_mismo_box_solo_un_ganador(self):
        self.assertEqual(self._ocupar_con_lock(False), [200, 409])
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.ocupado_por_id, self.medico.pk)

    def _instancia_vieja(self, accion, usuario, metodo, datos, durante):
        leida, continuar = Event(), Event()
        original = BoxViewSet.get_object
        hilo = {}

        def obtener(view):
            objeto = original(view)
            if get_ident() == hilo.get("id") and view.action == accion:
                leida.set()
                if not continuar.wait(timeout=10):
                    raise AssertionError("Timeout de instancia obsoleta")
            return objeto

        def operar():
            try:
                hilo["id"] = get_ident()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                cliente = self.cliente(Usuario.objects.get(pk=usuario.pk))
                respuesta = getattr(cliente, metodo)(f"/api/boxes/{self.box1.pk}/{'' if accion in ('partial_update', 'destroy') else accion + '/'}", datos, format="json")
                return respuesta.status_code
            finally:
                connections.close_all()

        with patch.object(BoxViewSet, "get_object", obtener):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(operar)
                try:
                    self.assertTrue(leida.wait(timeout=10))
                    durante()
                finally:
                    continuar.set()
                return futuro.result(timeout=12)

    def test_liberacion_vieja_no_expulsa_nuevo_ocupante(self):
        self.ocupar(self.medico, self.box1)

        def cambiar_ocupante():
            self.assertEqual(self.cliente(self.root).post(f"/api/boxes/{self.box1.pk}/liberar/", {}).status_code, 200)
            self.assertEqual(self.ocupar(self.otro, self.box1).status_code, 200)

        codigo = self._instancia_vieja("liberar", self.medico, "post", {}, cambiar_ocupante)
        self.assertIn(codigo, (403, 409))
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.ocupado_por_id, self.otro.pk)

    def test_patch_viejo_no_pisa_ocupacion_nueva(self):
        codigo = self._instancia_vieja("partial_update", self.root, "patch", {"nombre": "Nuevo nombre"},
                                      lambda: self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200))
        self.assertEqual(codigo, 200)
        self.box1.refresh_from_db()
        self.assertEqual(self.box1.nombre, "Nuevo nombre")
        self.assertEqual(self.box1.ocupado_por_id, self.medico.pk)

    def test_delete_viejo_no_borra_ocupacion_nueva(self):
        codigo = self._instancia_vieja("destroy", self.root, "delete", {},
                                      lambda: self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200))
        self.assertEqual(codigo, 409)
        self.assertTrue(Box.objects.filter(pk=self.box1.pk, ocupado_por=self.medico).exists())

    def test_box_eliminado_entre_lectura_y_lock_devuelve_404_sin_recrearlo(self):
        for accion, metodo, datos in (
            ("ocupar", "post", {}), ("liberar", "post", {}),
            ("partial_update", "patch", {"nombre": "Cambio obsoleto"}),
            ("destroy", "delete", {}),
        ):
            with self.subTest(accion=accion):
                self.box1 = Box.objects.create(area=self.area, nombre=f"Temporal {accion}")
                pk = self.box1.pk
                codigo = self._instancia_vieja(
                    accion, self.root, metodo, datos,
                    lambda: Box.objects.filter(pk=pk).delete(),
                )
                self.assertEqual(codigo, 404)
                self.assertFalse(Box.objects.filter(pk=pk).exists())

    def test_borrar_area_revalida_box_ocupado_tras_lectura_inicial(self):
        leida, continuar = Event(), Event()
        original = AreaViewSet.get_object

        def obtener(view):
            objeto = original(view)
            leida.set()
            if not continuar.wait(timeout=10):
                raise AssertionError("Timeout de borrado del área")
            return objeto

        def borrar():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                return self.cliente(Usuario.objects.get(pk=self.root.pk)).delete(f"/api/areas/{self.area.pk}/").status_code
            finally:
                connections.close_all()

        with patch.object(AreaViewSet, "get_object", obtener):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(borrar)
                try:
                    self.assertTrue(leida.wait(timeout=10))
                    self.assertEqual(self.ocupar(self.medico, self.box1).status_code, 200)
                finally:
                    continuar.set()
                self.assertEqual(futuro.result(timeout=12), 409)
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())
        self.assertTrue(Box.objects.filter(pk=self.box1.pk, ocupado_por=self.medico).exists())
