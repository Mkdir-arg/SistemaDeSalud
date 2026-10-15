"""AUD-041: dos serializadores viejos no pueden retroceder una firma clínica."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.forms.models import BaseInlineFormSet
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.instituciones.models import Institucion
from apps.simulacion.models import CuentaReferencia, SesionSimulacion

from . import integridad
from .models import Ciudadano, EntradaHistoria, HistoriaClinica
from .revision_borrador import revision_de_entrada
from .views import EntradaHistoriaViewSet


@skipUnless(connection.vendor == "postgresql", "Concurrencia clínica requiere PostgreSQL real")
class ConcurrenciaFirmaAuditoria172Tests(TransactionTestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Clínica de concurrencia sintética")
        self.usuario = Usuario.objects.create_user("firma-sintetica@example.test", "x")
        Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.MEDICO,
        )
        LegajoProfesional.objects.create(usuario=self.usuario, matricula="MP sintética 172")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Paciente sintético")
        self.historia = HistoriaClinica.objects.create(ciudadano=ciudadano)
        self.entrada = EntradaHistoria.objects.create(
            historia=self.historia, autor=self.usuario, titulo="Borrador inicial", contenido="Contenido inicial",
        )

    def intercalar(self, datos_competidor, *, usuario_competidor=None, primera_firma=True):
        revision = revision_de_entrada(self.entrada)
        preparados = Barrier(2)
        primera_finalizada = Event()
        original = EntradaHistoriaViewSet.perform_update

        def preparar(view, serializer):
            # Ambas solicitudes ya cargaron/validaron su borrador antes de que
            # la primera firme. No simular el guard ni el servicio de sellado.
            preparados.wait(timeout=10)
            if view.request.data.get("titulo") == "Primera firma":
                return original(view, serializer)
            if not primera_finalizada.wait(timeout=10):
                raise AssertionError("La primera firma no finalizó")
            return original(view, serializer)

        def solicitar(primera):
            connections.close_all()
            try:
                usuario = Usuario.objects.get(pk=self.usuario.pk if primera else (usuario_competidor or self.usuario).pk)
                cliente = APIClient()
                cliente.force_authenticate(usuario)
                datos = ({"firmada": True, "titulo": "Primera firma"} if primera_firma else {
                    "titulo": "Primera firma", "contenido": "Edición del autor",
                }) if primera else datos_competidor
                datos = {**datos, "revision_esperada": revision}
                respuesta = cliente.patch(f"/api/entradas-historia/{self.entrada.pk}/", datos, format="json")
                return respuesta.status_code, respuesta.data
            finally:
                if primera:
                    primera_finalizada.set()
                connections.close_all()

        with patch.object(EntradaHistoriaViewSet, "perform_update", preparar):
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="clinica") as pool:
                futuros = [pool.submit(solicitar, primera) for primera in (True, False)]
                return [futuro.result(timeout=20) for futuro in futuros]

    def comprobar_firma_preservada(self, resultados):
        self.assertEqual(resultados[0][0], 200, resultados)
        self.assertEqual(resultados[1][0], 409, resultados)
        self.entrada.refresh_from_db()
        self.assertTrue(self.entrada.firmada)
        self.assertEqual(self.entrada.titulo, "Primera firma")
        self.assertEqual(self.entrada.contenido, "Contenido inicial")
        self.assertEqual(self.entrada.sello, resultados[0][1]["sello"])
        self.assertTrue(integridad.verificar(self.entrada)["ok"])
        self.assertTrue(integridad.verificar_historia(self.historia)["ok"])

    def test_edicion_obsoleta_no_desfirma_ni_sobrescribe_contenido(self):
        self.comprobar_firma_preservada(self.intercalar({"contenido": "Edición obsoleta"}))

    def test_segunda_firma_obsoleta_no_reescribe_primera_firma(self):
        self.comprobar_firma_preservada(self.intercalar({"firmada": True, "titulo": "Segunda firma"}))

    def test_dos_actores_sobre_mismo_borrador_solo_guarda_el_autor(self):
        otro = Usuario.objects.create_user("competidor-borrador@example.test", "x")
        Membresia.objects.create(usuario=otro, institucion=self.institucion, rol=Membresia.Rol.MEDICO)
        resultados = self.intercalar({"contenido": "Otro profesional"}, usuario_competidor=otro, primera_firma=False)
        self.assertEqual([codigo for codigo, _ in resultados], [200, 403], resultados)
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.autor_id, self.usuario.pk)
        self.assertEqual(self.entrada.contenido, "Edición del autor")
        self.assertFalse(self.entrada.firmada)

    def test_historia_borrada_despues_de_leer_borrador_devuelve_404(self):
        root = Usuario.objects.create_superuser("autor-borrado-concurrente@example.test", "x")
        self.entrada.autor = root
        self.entrada.save(update_fields=["autor"])
        solicitud_validada = Event()
        borrado_finalizado = Event()
        original = EntradaHistoriaViewSet.perform_update

        def esperar_borrado(view, serializer):
            solicitud_validada.set()
            if not borrado_finalizado.wait(timeout=10):
                raise AssertionError("El borrado autorizado no finalizó")
            return original(view, serializer)

        def editar():
            connections.close_all()
            try:
                cliente = APIClient(raise_request_exception=False)
                cliente.force_authenticate(Usuario.objects.get(pk=root.pk))
                return cliente.patch(f"/api/entradas-historia/{self.entrada.pk}/", {
                    "contenido": "Lectura anterior al borrado",
                    "revision_esperada": revision_de_entrada(self.entrada),
                }, format="json").status_code
            finally:
                connections.close_all()

        def borrar():
            connections.close_all()
            try:
                if not solicitud_validada.wait(timeout=10):
                    raise AssertionError("La edición no llegó a leer el borrador")
                cliente = APIClient()
                cliente.force_login(Usuario.objects.get(pk=root.pk))
                return cliente.post(f"/admin/registros/historiaclinica/{self.historia.pk}/delete/", {
                    "post": "yes",
                }).status_code
            finally:
                borrado_finalizado.set()
                connections.close_all()

        with patch.object(EntradaHistoriaViewSet, "perform_update", esperar_borrado):
            with ThreadPoolExecutor(max_workers=2) as pool:
                edicion = pool.submit(editar)
                borrado = pool.submit(borrar)
                self.assertEqual(borrado.result(timeout=20), 302)
                self.assertEqual(edicion.result(timeout=20), 404)
        self.assertFalse(HistoriaClinica.objects.filter(pk=self.historia.pk).exists())
        self.assertFalse(EntradaHistoria.objects.filter(pk=self.entrada.pk).exists())

    def test_admin_con_formulario_obsoleto_no_pisa_firma_posterior(self):
        root = Usuario.objects.create_superuser("admin-concurrente@example.test", "x")
        formulario_cargado = Event()
        firma_finalizada = Event()
        original = BaseInlineFormSet.clean

        def esperar_firma(formset):
            resultado = original(formset)
            if formset.model is EntradaHistoria:
                formulario_cargado.set()
                if not firma_finalizada.wait(timeout=10):
                    raise AssertionError("La firma concurrente no finalizó")
            return resultado

        def editar_admin():
            connections.close_all()
            try:
                cliente = APIClient()
                cliente.force_login(Usuario.objects.get(pk=root.pk))
                datos = {
                    "ciudadano": str(self.historia.ciudadano_id), "condiciones": "", "alergias": "",
                    "entradas-TOTAL_FORMS": "1", "entradas-INITIAL_FORMS": "1",
                    "entradas-MIN_NUM_FORMS": "0", "entradas-MAX_NUM_FORMS": "1000",
                    "entradas-0-id": str(self.entrada.pk), "entradas-0-historia": str(self.historia.pk),
                    "entradas-0-titulo": "Borrador inicial", "entradas-0-contenido": "Admin obsoleto",
                    "entradas-0-autor": str(self.usuario.pk),
                    "entradas-0-revision_esperada": revision_de_entrada(self.entrada),
                    "estudios-TOTAL_FORMS": "0", "estudios-INITIAL_FORMS": "0",
                    "estudios-MIN_NUM_FORMS": "0", "estudios-MAX_NUM_FORMS": "1000", "_save": "Guardar",
                }
                return cliente.post(f"/admin/registros/historiaclinica/{self.historia.pk}/change/", datos).status_code
            finally:
                connections.close_all()

        def firmar():
            connections.close_all()
            try:
                if not formulario_cargado.wait(timeout=10):
                    raise AssertionError("El formulario admin no llegó a validarse")
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.usuario.pk))
                return cliente.patch(f"/api/entradas-historia/{self.entrada.pk}/", {
                    "firmada": True, "revision_esperada": revision_de_entrada(self.entrada),
                }, format="json").status_code
            finally:
                firma_finalizada.set()
                connections.close_all()

        with patch.object(BaseInlineFormSet, "clean", esperar_firma):
            with ThreadPoolExecutor(max_workers=2) as pool:
                admin = pool.submit(editar_admin)
                firma = pool.submit(firmar)
                self.assertEqual(firma.result(timeout=20), 200)
                self.assertEqual(admin.result(timeout=20), 200)
        self.entrada.refresh_from_db()
        self.assertTrue(self.entrada.firmada)
        self.assertEqual(self.entrada.contenido, "Contenido inicial")
        self.assertTrue(integridad.verificar(self.entrada)["ok"])


class AdminFirmaAuditoria172Tests(TestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Admin clínico sintético")
        self.root = Usuario.objects.create_superuser("admin-firma@example.test", "x")
        self.otro = Usuario.objects.create_user("autor-ajeno@example.test", "x")
        self.paciente = Ciudadano.objects.create(institucion=self.institucion, nombre="Paciente sintético")
        self.historia = HistoriaClinica.objects.create(ciudadano=self.paciente)
        self.entrada = EntradaHistoria.objects.create(
            historia=self.historia, autor=self.otro, titulo="Firmada original",
            contenido="Contenido firmado", firmada=True,
        )
        integridad.sellar(self.entrada)
        self.client.force_login(self.root)

    def formulario_historia(self):
        return {
            "ciudadano": str(self.paciente.pk), "alergias": "", "condiciones": "",
            "entradas-TOTAL_FORMS": "1", "entradas-INITIAL_FORMS": "1",
            "entradas-MIN_NUM_FORMS": "0", "entradas-MAX_NUM_FORMS": "1000",
            "entradas-0-id": str(self.entrada.pk), "entradas-0-historia": str(self.historia.pk),
            "entradas-0-titulo": self.entrada.titulo, "entradas-0-contenido": self.entrada.contenido,
            "entradas-0-autor": str(self.otro.pk), "entradas-0-firmada": "on",
            "entradas-0-revision_esperada": revision_de_entrada(self.entrada),
            "estudios-TOTAL_FORMS": "0", "estudios-INITIAL_FORMS": "0",
            "estudios-MIN_NUM_FORMS": "0", "estudios-MAX_NUM_FORMS": "1000",
            "_save": "Guardar",
        }

    def test_admin_no_modifica_ni_borra_entrada_firmada_por_inline(self):
        for cambio in ({"entradas-0-contenido": "Alteración"}, {"entradas-0-DELETE": "on"}):
            with self.subTest(cambio=cambio):
                datos = {**self.formulario_historia(), **cambio}
                respuesta = self.client.post(f"/admin/registros/historiaclinica/{self.historia.pk}/change/", datos)
                self.assertEqual(respuesta.status_code, 200)
                self.assertContains(respuesta, "firmada", status_code=200)
                self.entrada.refresh_from_db()
                self.assertEqual(self.entrada.contenido, "Contenido firmado")
                self.assertTrue(integridad.verificar(self.entrada)["ok"])

    def test_admin_no_borra_historia_o_paciente_con_firmadas(self):
        for modelo, objeto in (("historiaclinica", self.historia), ("ciudadano", self.paciente)):
            with self.subTest(modelo=modelo):
                respuesta = self.client.post(f"/admin/registros/{modelo}/{objeto.pk}/delete/", {"post": "yes"})
                self.assertEqual(respuesta.status_code, 403)
                self.assertTrue(EntradaHistoria.objects.filter(pk=self.entrada.pk).exists())

    def test_admin_bulk_no_borra_firmadas_por_cascada(self):
        for modelo, objeto in (("historiaclinica", self.historia), ("ciudadano", self.paciente)):
            with self.subTest(modelo=modelo):
                self.client.post(f"/admin/registros/{modelo}/", {
                    "action": "delete_selected", "_selected_action": [str(objeto.pk)], "post": "yes",
                })
                self.assertTrue(EntradaHistoria.objects.filter(pk=self.entrada.pk).exists())

    def test_inline_no_reasigna_autor_ni_firma_borradores(self):
        self.entrada.firmada = False
        self.entrada.sello = ""
        self.entrada.sello_previo = ""
        self.entrada.sello_version = ""
        self.entrada.firmada_at = None
        self.entrada.save()
        datos = self.formulario_historia()
        datos["entradas-0-autor"] = str(self.root.pk)
        self.client.post(f"/admin/registros/historiaclinica/{self.historia.pk}/change/", datos)
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.autor_id, self.otro.pk)
        self.assertFalse(self.entrada.firmada)

    def test_superusuario_no_edita_contenido_de_borrador_ajeno_en_inline(self):
        self.entrada.firmada = False
        self.entrada.save(update_fields=["firmada"])
        datos = self.formulario_historia()
        datos["entradas-0-contenido"] = "Cambio del superusuario"
        respuesta = self.client.post(f"/admin/registros/historiaclinica/{self.historia.pk}/change/", datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solo el autor")
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Contenido firmado")
        self.assertEqual(self.entrada.autor_id, self.otro.pk)

    def test_borradores_ajenos_y_sin_autor_no_se_borran_por_padre(self):
        for autor in (self.otro, None):
            self.entrada.firmada = False
            self.entrada.autor = autor
            self.entrada.save(update_fields=["firmada", "autor"])
            for modelo, objeto in (("historiaclinica", self.historia), ("ciudadano", self.paciente)):
                with self.subTest(autor=autor, modelo=modelo):
                    respuesta = self.client.post(f"/admin/registros/{modelo}/{objeto.pk}/delete/", {"post": "yes"})
                    self.assertEqual(respuesta.status_code, 403)
                    self.assertTrue(EntradaHistoria.objects.filter(pk=self.entrada.pk).exists())

    def test_autor_admin_conserva_edicion_de_su_borrador(self):
        self.entrada.firmada = False
        self.entrada.autor = self.root
        self.entrada.save(update_fields=["firmada", "autor"])
        datos = self.formulario_historia()
        datos["entradas-0-contenido"] = "Edición propia"
        respuesta = self.client.post(f"/admin/registros/historiaclinica/{self.historia.pk}/change/", datos)
        self.assertEqual(respuesta.status_code, 302)
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Edición propia")

    def test_borrado_padre_con_borrador_propio_sigue_disponible(self):
        self.entrada.firmada = False
        self.entrada.autor = self.root
        self.entrada.save(update_fields=["firmada", "autor"])
        respuesta = self.client.post(f"/admin/registros/historiaclinica/{self.historia.pk}/delete/", {"post": "yes"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(HistoriaClinica.objects.filter(pk=self.historia.pk).exists())


class AutorRealSimulacionAuditoria172Tests(APITestCase):
    def test_capacidad_efectiva_conserva_autor_real_sin_impersonar_referencia(self):
        institucion = Institucion.objects.create(nombre="Institución de simulación sintética")
        paciente = Ciudadano.objects.create(institucion=institucion, nombre="Paciente sintético")
        historia = HistoriaClinica.objects.create(ciudadano=paciente)
        real = Usuario.objects.create_superuser("autor-real-clinico@example.test", "x")
        otro_real = Usuario.objects.create_superuser("otro-real-clinico@example.test", "x")
        referencia = Usuario.objects.create_user("medico@referencia.plexo.invalid", None)
        Membresia.objects.create(usuario=referencia, institucion=institucion, rol=Membresia.Rol.MEDICO)
        LegajoProfesional.objects.create(usuario=referencia, matricula="MP perfil sintético")
        CuentaReferencia.objects.create(
            usuario=referencia, ambito="institucion", rol=Membresia.Rol.MEDICO, institucion=institucion,
        )

        def cliente(actor):
            sesion = SesionSimulacion.objects.create(
                superusuario=actor, cuenta=referencia, ambito="institucion", rol=Membresia.Rol.MEDICO,
                institucion=institucion, vence=timezone.now() + timedelta(minutes=10),
            )
            cliente = APIClient()
            cliente.credentials(
                HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(actor).access_token}",
                HTTP_X_PLEXO_SIMULACION=str(sesion.pk),
            )
            return cliente

        titular = cliente(real)
        creado = titular.post("/api/entradas-historia/", {
            "historia": historia.pk, "titulo": "Borrador propio", "firmada": False,
        }, format="json")
        self.assertEqual(creado.status_code, 201, creado.data)
        entrada = EntradaHistoria.objects.get(pk=creado.data["id"])
        self.assertEqual(entrada.autor_id, real.pk)
        url = f"/api/entradas-historia/{entrada.pk}/"
        respuesta = titular.patch(url, {
            "contenido": "Edición del actor real", "revision_esperada": creado.data["revision"],
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        revision_actual = respuesta.data["revision"]
        respuesta = cliente(otro_real).patch(url, {"contenido": "Otro actor con mismo perfil"}, format="json")
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        legado = EntradaHistoria.objects.create(historia=historia, titulo="Autor referencia legacy", autor=referencia)
        respuesta = titular.patch(f"/api/entradas-historia/{legado.pk}/", {"firmada": True}, format="json")
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        respuesta = titular.patch(url, {"firmada": True, "revision_esperada": revision_actual}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        entrada.refresh_from_db()
        self.assertEqual(entrada.autor_id, real.pk)
        self.assertEqual(entrada.matricula, "MP perfil sintético")
        self.assertTrue(integridad.verificar(entrada)["ok"])
