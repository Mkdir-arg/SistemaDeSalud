"""Revisión obligatoria: no guardar ni firmar un estado distinto del leído."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.instituciones.models import Institucion

from . import integridad
from .models import Ciudadano, EntradaHistoria, HistoriaClinica
from .views import EntradaHistoriaViewSet


class EscenarioRevision:
    def preparar(self):
        self.institucion = Institucion.objects.create(nombre="Revisión clínica sintética")
        self.autor = Usuario.objects.create_superuser("autor-revision@example.test", "x")
        Membresia.objects.create(usuario=self.autor, institucion=self.institucion, rol=Membresia.Rol.MEDICO)
        LegajoProfesional.objects.create(usuario=self.autor, matricula="MP sintética")
        paciente = Ciudadano.objects.create(institucion=self.institucion, nombre="Paciente sintético")
        self.historia = HistoriaClinica.objects.create(ciudadano=paciente)
        self.entrada = EntradaHistoria.objects.create(
            historia=self.historia, autor=self.autor, titulo="Título leído", contenido="Contenido leído",
        )
        self.url = f"/api/entradas-historia/{self.entrada.pk}/"
        self.api = APIClient()
        self.api.force_authenticate(self.autor)

    def leer(self):
        respuesta = self.api.get(self.url)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIn("revision", respuesta.data)
        self.assertNotIn("revision_esperada", respuesta.data)
        return respuesta.data


class RevisionBorradorAuditoria172Tests(EscenarioRevision, APITestCase):
    def setUp(self):
        self.preparar()

    def test_revision_es_opaca_y_edicion_devuelve_nuevo_estado(self):
        inicial = self.leer()
        self.assertRegex(inicial["revision"], r"^rev1\.[0-9a-f]{64}$")
        self.assertNotIn(self.entrada.contenido, inicial["revision"])
        respuesta = self.api.patch(self.url, {
            "contenido": "Cambio confirmado", "revision_esperada": inicial["revision"],
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotEqual(respuesta.data["revision"], inicial["revision"])
        self.assertNotIn("revision_esperada", respuesta.data)

    def test_dos_pestanas_del_autor_no_pisan_el_cambio_ajeno(self):
        primera, segunda = self.leer(), self.leer()
        self.assertEqual(primera["revision"], segunda["revision"])
        respuesta = self.api.patch(self.url, {
            "contenido": "Texto guardado en pestaña A", "revision_esperada": primera["revision"],
        }, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        respuesta = self.api.patch(self.url, {
            "contenido": "Texto obsoleto de pestaña B", "revision_esperada": segunda["revision"],
        }, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(set(respuesta.data), {"detail"})
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Texto guardado en pestaña A")

    def test_firma_obsoleta_no_firma_contenido_no_leido_y_relectura_permite_firmar(self):
        inicial = self.leer()
        editada = self.api.patch(self.url, {
            "contenido": "Contenido posterior", "revision_esperada": inicial["revision"],
        }, format="json")
        self.assertEqual(editada.status_code, 200, editada.data)
        respuesta = self.api.patch(self.url, {"firmada": True, "revision_esperada": inicial["revision"]}, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.entrada.refresh_from_db()
        self.assertFalse(self.entrada.firmada)
        self.assertEqual(self.entrada.sello, "")
        releida = self.leer()
        respuesta = self.api.patch(self.url, {"firmada": True, "revision_esperada": releida["revision"]}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.entrada.refresh_from_db()
        self.assertTrue(integridad.verificar(self.entrada)["ok"])
        self.assertEqual(self.entrada.contenido, "Contenido posterior")

    def test_falta_revision_da_400_sin_modificacion_y_token_falso_409(self):
        for datos, esperado in (({"contenido": "Sin revisión"}, 400),
                                ({"contenido": "Con token falso", "revision_esperada": "rev1." + "0" * 64}, 409)):
            with self.subTest(esperado=esperado):
                respuesta = self.api.patch(self.url, datos, format="json")
                self.assertEqual(respuesta.status_code, esperado, respuesta.data)
                self.entrada.refresh_from_db()
                self.assertEqual(self.entrada.contenido, "Contenido leído")

    def test_no_sustituye_403_de_autor_o_409_de_firmada_por_error_de_revision(self):
        otro = Usuario.objects.create_superuser("otro-revision@example.test", "x")
        self.api.force_authenticate(otro)
        self.assertEqual(self.api.patch(self.url, {"contenido": "Ajeno"}).status_code, 403)
        self.api.force_authenticate(self.autor)
        self.entrada.firmada = True
        self.entrada.save(update_fields=["firmada"])
        integridad.sellar(self.entrada)
        self.assertEqual(self.api.patch(self.url, {"contenido": "Firmado"}).status_code, 409)

    def test_revision_cubre_todos_los_campos_del_asiento(self):
        from .revision_borrador import revision_de_entrada

        original = revision_de_entrada(self.entrada)
        cambios = {
            "titulo": "Otro título", "contenido": "Otro contenido", "autor_id": self.autor.pk + 99,
            "caso_id": 172, "fecha": self.entrada.fecha + timedelta(microseconds=1),
            "firmada": True, "matricula": "MP distinta", "sello": "a" * 64,
            "sello_previo": "b" * 64, "sello_version": "formato-distinto", "firmada_at": self.entrada.fecha,
        }
        for campo, valor in cambios.items():
            with self.subTest(campo=campo):
                anterior = getattr(self.entrada, campo)
                setattr(self.entrada, campo, valor)
                self.assertNotEqual(revision_de_entrada(self.entrada), original)
                setattr(self.entrada, campo, anterior)
        otra_historia = HistoriaClinica.objects.create(ciudadano=Ciudadano.objects.create(institucion=self.institucion, nombre="Otro"))
        self.entrada.historia = otra_historia
        self.assertNotEqual(revision_de_entrada(self.entrada), original)

    def test_snapshot_no_es_contador_y_aba_exacto_conserva_revision(self):
        from .revision_borrador import revision_de_entrada

        inicial = revision_de_entrada(self.entrada)
        self.entrada.contenido = "B"
        self.assertNotEqual(revision_de_entrada(self.entrada), inicial)
        self.entrada.contenido = "Contenido leído"
        self.assertEqual(revision_de_entrada(self.entrada), inicial)

    def datos_admin(self, revision):
        return {
            "ciudadano": str(self.historia.ciudadano_id), "alergias": "", "condiciones": "",
            "entradas-TOTAL_FORMS": "1", "entradas-INITIAL_FORMS": "1",
            "entradas-MIN_NUM_FORMS": "0", "entradas-MAX_NUM_FORMS": "1000",
            "entradas-0-id": str(self.entrada.pk), "entradas-0-historia": str(self.historia.pk),
            "entradas-0-titulo": "Título leído", "entradas-0-contenido": "Cambio desde Admin",
            "entradas-0-revision_esperada": revision,
            "estudios-TOTAL_FORMS": "0", "estudios-INITIAL_FORMS": "0",
            "estudios-MIN_NUM_FORMS": "0", "estudios-MAX_NUM_FORMS": "1000", "_save": "Guardar",
        }

    def test_admin_hidden_refleja_revision_mostrada_y_rechaza_snapshot_viejo(self):
        self.client.force_login(self.autor)
        url = f"/admin/registros/historiaclinica/{self.historia.pk}/change/"
        pagina = self.client.get(url)
        formset = next(f.formset for f in pagina.context["inline_admin_formsets"] if f.opts.model is EntradaHistoria)
        revision = formset.forms[0]["revision_esperada"].value()
        self.assertEqual(revision, self.leer()["revision"])
        self.api.patch(self.url, {"contenido": "Cambio de otra pestaña", "revision_esperada": revision}, format="json")
        respuesta = self.client.post(url, self.datos_admin(revision))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "cambió")
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Cambio de otra pestaña")

    def test_admin_revision_actual_permite_guardar_y_ausente_no(self):
        self.client.force_login(self.autor)
        url = f"/admin/registros/historiaclinica/{self.historia.pk}/change/"
        respuesta = self.client.post(url, self.datos_admin(""))
        self.assertEqual(respuesta.status_code, 200)
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Contenido leído")
        respuesta = self.client.post(url, self.datos_admin(self.leer()["revision"]))
        self.assertEqual(respuesta.status_code, 302)
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Cambio desde Admin")


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL")
class RevisionConcurrenteAuditoria172Tests(EscenarioRevision, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def test_dos_ediciones_con_misma_revision_solo_persisten_una(self):
        revision = self.leer()["revision"]
        preparados, primera_finalizada = Barrier(2, timeout=10), Event()
        original = EntradaHistoriaViewSet.perform_update

        def pausar(view, serializer):
            preparados.wait()
            if view.request.data["contenido"] == "Primera edición":
                return original(view, serializer)
            if not primera_finalizada.wait(timeout=10):
                raise AssertionError("Timeout de la primera edición")
            return original(view, serializer)

        def escribir(primera):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.autor.pk))
                respuesta = cliente.patch(self.url, {
                    "contenido": "Primera edición" if primera else "Segunda edición",
                    "revision_esperada": revision,
                }, format="json")
                return respuesta.status_code
            finally:
                if primera:
                    primera_finalizada.set()
                connections.close_all()

        with patch.object(EntradaHistoriaViewSet, "perform_update", pausar):
            with ThreadPoolExecutor(max_workers=2) as pool:
                primera, segunda = pool.submit(escribir, True), pool.submit(escribir, False)
                self.assertEqual([primera.result(timeout=20), segunda.result(timeout=20)], [200, 409])
        self.entrada.refresh_from_db()
        self.assertEqual(self.entrada.contenido, "Primera edición")
