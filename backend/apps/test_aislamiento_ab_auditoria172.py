"""AUD-039: negativos A/B por HTTP para recursos clínicos y de administración (#172).

Un admin de la institución A tiene todas las capacidades institucionales
(`historia_clinica`, `prescripcion`, `config_institucional`, `casos_operar`…),
así que todo rechazo se debe al alcance institucional y no a su rol. Sobre
objetos de B: el listado no los incluye, el detalle responde 404 (no enumera)
y ninguna escritura, borrado o acción los modifica.

Cubre los huecos que dejaba la cobertura previa: historias clínicas, entradas,
estudios, recetas, consentimientos, valores de formulario, eventos de caso,
listado/edición/borrado de padrón y membresías, acciones de detalle de casos y
filas, registro de accesos por paciente y subida de archivos. El resto de la
matriz está en `docs/plans/2026-10-19-matriz-permisos-172.md`.
"""
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso, ItemFila, ValorCampo
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Institucion
from apps.registros.models import (
    Ciudadano, ConsentimientoDatos, EntradaHistoria, Estudio, HistoriaClinica, Receta,
)


class AislamientoInstitucionalABAuditoria172Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Institucion.objects.create(nombre="Hospital A sintético")
        cls.b = Institucion.objects.create(nombre="Hospital B sintético")
        cls.admin_a = Usuario.objects.create_user("admin-a-ab@example.test", "x", nombre="AdminA")
        Membresia.objects.create(usuario=cls.admin_a, institucion=cls.a, rol="admin")
        cls.medico_b = Usuario.objects.create_user("medico-b-ab@example.test", "x", nombre="MedicoB")
        cls.memb_b = Membresia.objects.create(usuario=cls.medico_b, institucion=cls.b, rol="medico")

        cls.ciu_b = Ciudadano.objects.create(institucion=cls.b, nombre="Paciente", apellido="B", documento="40111222")
        cls.hc_b = HistoriaClinica.objects.create(ciudadano=cls.ciu_b, alergias="Dato clínico B")
        cls.entrada_b = EntradaHistoria.objects.create(historia=cls.hc_b, titulo="Evolución B",
                                                       contenido="Texto clínico B", autor=cls.medico_b)
        cls.estudio_b = Estudio.objects.create(historia=cls.hc_b, tipo="Laboratorio B", fecha=date(2026, 10, 1))
        cls.receta_b = Receta.objects.create(historia=cls.hc_b, detalle="Indicación B", autor=cls.medico_b)
        cls.consent_b = ConsentimientoDatos.objects.create(ciudadano=cls.ciu_b, institucion=cls.b, otorgado=True,
                                                           alcance="Uso sintético", tomado_por=cls.medico_b)

        form_b = Formulario.objects.create(institucion=cls.b, titulo="Formulario B")
        campo_b = Campo.objects.create(formulario=form_b, label="Dato B", tipo="texto_corto")
        version_b = VersionFlujo.objects.create(flujo=Flujo.objects.create(institucion=cls.b, titulo="Flujo B"), numero=1)
        nodo_b = Nodo.objects.create(version=version_b, tipo="form", titulo="Paso B", formulario=form_b)
        cls.caso_b = Caso.objects.create(institucion=cls.b, version=version_b, ciudadano=cls.ciu_b, nodo_actual=nodo_b)
        cls.valor_b = ValorCampo.objects.create(caso=cls.caso_b, campo=campo_b, nodo=nodo_b, valor="Valor clínico B")
        cls.evento_b = EventoCaso.objects.create(caso=cls.caso_b, titulo="Evento B", detalle="Detalle B")
        cls.item_b = ItemFila.objects.create(caso=cls.caso_b, nodo=nodo_b, ticket="B-001")
        AccesoClinico.objects.create(usuario=cls.medico_b, ciudadano=cls.ciu_b, institucion=cls.b,
                                     tipo=AccesoClinico.Tipo.DETALLE, recurso="ciudadano")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.admin_a)

    def ids(self, url, **params):
        respuesta = self.api.get(url, params)
        self.assertEqual(respuesta.status_code, 200, url)
        datos = respuesta.json()
        filas = datos["results"] if isinstance(datos, dict) and "results" in datos else datos
        return {fila["id"] for fila in filas}

    def test_lectura_de_b_no_aparece_ni_se_abre(self):
        recursos = [
            ("historias-clinicas", self.hc_b), ("entradas-historia", self.entrada_b),
            ("estudios", self.estudio_b), ("recetas", self.receta_b),
            ("consentimientos", self.consent_b), ("valores-campo", self.valor_b),
            ("eventos-caso", self.evento_b), ("ciudadanos", self.ciu_b),
            ("membresias", self.memb_b), ("items-fila", self.item_b),
        ]
        for prefijo, objeto in recursos:
            with self.subTest(recurso=prefijo):
                self.assertNotIn(objeto.pk, self.ids(f"/api/{prefijo}/"))
                self.assertEqual(self.api.get(f"/api/{prefijo}/{objeto.pk}/").status_code, 404)
        with self.subTest(recurso="valores-campo?caso"):
            self.assertEqual(self.ids("/api/valores-campo/", caso=self.caso_b.pk), set())
        with self.subTest(recurso="consentimientos/evidencia"):
            self.assertEqual(self.api.get(f"/api/consentimientos/{self.consent_b.pk}/evidencia/").status_code, 404)

    def test_escrituras_y_borrados_sobre_b_no_modifican(self):
        intentos = [
            ("historias-clinicas", self.hc_b, {"alergias": "Pisado"}),
            ("entradas-historia", self.entrada_b, {"contenido": "Pisado"}),
            ("estudios", self.estudio_b, {"tipo": "Pisado"}),
            ("recetas", self.receta_b, {"detalle": "Pisado"}),
            ("consentimientos", self.consent_b, {"observaciones": "Pisado"}),
            ("eventos-caso", self.evento_b, {"titulo": "Pisado"}),
            ("ciudadanos", self.ciu_b, {"nombre": "Pisado"}),
            ("membresias", self.memb_b, {"activo": False}),
            ("items-fila", self.item_b, {"urgente": True}),
        ]
        for prefijo, objeto, cambio in intentos:
            with self.subTest(recurso=prefijo):
                antes = type(objeto).objects.filter(pk=objeto.pk).values().get()
                self.assertIn(self.api.patch(f"/api/{prefijo}/{objeto.pk}/", cambio, format="json").status_code,
                              (403, 404, 405))
                self.assertIn(self.api.delete(f"/api/{prefijo}/{objeto.pk}/").status_code, (403, 404, 405))
                self.assertEqual(type(objeto).objects.filter(pk=objeto.pk).values().get(), antes)

    def test_acciones_de_detalle_sobre_b_responden_404_sin_efecto(self):
        acciones = [
            (f"/api/casos/{self.caso_b.pk}/priorizar/", {"prioridad": "urgente"}),
            (f"/api/casos/{self.caso_b.pk}/cancelar/", {"motivo": "x"}),
            (f"/api/items-fila/{self.item_b.pk}/mover/", {"orden": 0}),
            (f"/api/recetas/{self.receta_b.pk}/suspender/", {"motivo": "x"}),
            (f"/api/estudios/{self.estudio_b.pk}/confirmar-archivo/", {}),
        ]
        for url, cuerpo in acciones:
            with self.subTest(url=url):
                self.assertEqual(self.api.post(url, cuerpo, format="json").status_code, 404)
        self.caso_b.refresh_from_db()
        self.receta_b.refresh_from_db()
        self.assertEqual((self.caso_b.prioridad, self.caso_b.estado), ("normal", "recibido"))
        self.assertTrue(self.receta_b.activa)
        self.assertEqual(EventoCaso.objects.filter(caso=self.caso_b).count(), 1)

    def test_registro_de_accesos_de_un_paciente_de_b_no_se_revela(self):
        respuesta = self.api.get("/api/accesos-clinicos/de-paciente/", {"ciudadano": self.ciu_b.pk})
        # El admin de A audita A: para un paciente de B la respuesta es vacía.
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual((respuesta.json()["count"], respuesta.json()["personas"]), (0, []))

    def test_puesto_de_b_no_se_abre(self):
        # PuestoDetalleView exige casos_operar en la institución del flujo del paso.
        self.assertEqual(self.api.get(f"/api/puestos/{self.caso_b.nodo_actual_id}/").status_code, 403)

    def test_no_sube_archivos_clinicos_a_b(self):
        archivo = SimpleUploadedFile("nota.txt", b"texto sintetico", content_type="text/plain")
        respuesta = self.api.post("/api/archivos/", {"archivo": archivo, "institucion": self.b.pk}, format="multipart")
        self.assertEqual(respuesta.status_code, 403)
