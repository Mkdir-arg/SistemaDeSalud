"""AUD-003: evidencia de inicio de descarga, sin inventar un paciente dueño."""
from datetime import timedelta
import hashlib
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, ValorCampo
from apps.flujos.models import Flujo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Institucion
from apps.simulacion.models import CuentaReferencia, SesionSimulacion

from .models import ArchivoClinico, Ciudadano, Estudio, HistoriaClinica


class DescargaArchivoAuditoria172Tests(APITestCase):
    contenido = b"%PDF-1.4 contenido clinico sintetico AUD003"

    def setUp(self):
        directorio = TemporaryDirectory(prefix="salud-aud003-")
        self.addCleanup(directorio.cleanup)
        configuracion = override_settings(MEDIA_ROOT=directorio.name)
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        self.institucion = Institucion.objects.create(nombre="Hospital sintético")
        self.usuario = Usuario.objects.create_user("descarga-ficticia@example.test", "x")
        Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.MEDICO,
        )
        self.client.force_authenticate(self.usuario)

    def archivo(self, *, metadatos=True, institucion=None):
        institucion = institucion or self.institucion
        ruta = default_storage.save(
            f"uploads/{institucion.pk}/marcador-nombre-privado.pdf", ContentFile(self.contenido),
        )
        meta = None
        if metadatos:
            meta = ArchivoClinico.objects.create(
                institucion=institucion, ruta=ruta, nombre_original="nombre-privado-sintetico.pdf",
                content_type="application/pdf", tamano=len(self.contenido),
                sha256=hashlib.sha256(self.contenido).hexdigest(), subido_por=self.usuario,
            )
        return ruta, meta

    def comprobar_bytes(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        # El cliente de Django envuelve el iterador y cierra la respuesta al
        # agotarlo. Un segundo close dispara request_finished otra vez y puede
        # cerrar la conexión que TestCase mantiene dentro de su atomic.
        self.assertEqual(b"".join(respuesta.streaming_content), self.contenido)

    def test_descarga_no_permite_cache_de_contenido_clinico(self):
        ruta, _ = self.archivo()
        respuesta = self.client.get(f"/api/archivos/descargar/{ruta}")
        self.comprobar_bytes(respuesta)
        self.assertEqual(respuesta.get("Cache-Control"), "private, no-store")

    def test_descarga_directa_registra_archivo_institucion_y_actor(self):
        ruta, meta = self.archivo()
        self.comprobar_bytes(self.client.get(f"/api/archivos/descargar/{ruta}"))
        self.assertEqual(AccesoClinico.objects.count(), 1, "Falta evidencia de la descarga directa")
        acceso = AccesoClinico.objects.get()
        self.assertEqual(acceso.usuario_id, self.usuario.pk)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
        self.assertEqual(acceso.tipo, AccesoClinico.Tipo.DETALLE)
        self.assertEqual(acceso.recurso, "archivoclinico")
        self.assertEqual(acceso.objeto_id, str(meta.pk))
        self.assertIsNone(acceso.ciudadano_id)
        self.assertEqual(acceso.detalle, "Descarga iniciada de archivo")
        self.assertNotIn(ruta, acceso.detalle)
        self.assertNotIn(meta.nombre_original, acceso.detalle)

    def test_legacy_se_conserva_y_se_identifica_por_hash_sin_pk_inventada(self):
        ruta, _ = self.archivo(metadatos=False)
        self.comprobar_bytes(self.client.get(f"/api/archivos/descargar/{ruta}"))
        self.assertEqual(AccesoClinico.objects.count(), 1, "Falta evidencia de la descarga legacy")
        acceso = AccesoClinico.objects.get()
        self.assertEqual(acceso.objeto_id, "")
        self.assertIsNone(acceso.ciudadano_id)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
        self.assertEqual(acceso.detalle, (
            "Descarga iniciada de archivo sin metadatos "
            f"legacy:{hashlib.sha256(ruta.encode('utf-8')).hexdigest()}"
        ))
        self.assertNotIn(ruta, acceso.detalle)
        self.assertNotIn("marcador-nombre-privado", acceso.detalle)

    def test_referencias_multiples_en_estudios_y_casos_no_inventan_paciente(self):
        ruta, _ = self.archivo()
        flujo = Flujo.objects.create(institucion=self.institucion, titulo="Prueba sintética")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        formulario = Formulario.objects.create(institucion=self.institucion, titulo="Adjunto")
        campo = Campo.objects.create(formulario=formulario, label="Archivo", tipo="archivo")
        for nombre in ("Paciente A", "Paciente B"):
            ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre=nombre)
            historia, _ = HistoriaClinica.objects.get_or_create(ciudadano=ciudadano)
            Estudio.objects.create(
                historia=historia, tipo="Sintético", archivo=ruta, realizado=True, fecha=timezone.localdate(),
            )
            caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano)
            ValorCampo.objects.create(caso=caso, campo=campo, valor=ruta)
        self.comprobar_bytes(self.client.get(f"/api/archivos/descargar/{ruta}"))
        self.assertEqual(AccesoClinico.objects.count(), 1)
        self.assertIsNone(AccesoClinico.objects.get().ciudadano_id)

    def test_404_no_registra_una_descarga(self):
        ruta, _ = self.archivo()
        default_storage.delete(ruta)
        for ruta_inexistente in (ruta, "invalida", f"uploads/{self.institucion.pk}/sin-metadatos.pdf"):
            with self.subTest(ruta=ruta_inexistente):
                respuesta = self.client.get(f"/api/archivos/descargar/{ruta_inexistente}")
                self.assertEqual(respuesta.status_code, 404)
                self.assertFalse(getattr(respuesta, "streaming", False))
        self.assertFalse(AccesoClinico.objects.exists())

    def test_403_no_entrega_bytes_ni_registra_descarga(self):
        otra = Institucion.objects.create(nombre="Institución ajena")
        ruta, _ = self.archivo(institucion=otra)
        respuesta = self.client.get(f"/api/archivos/descargar/{ruta}")
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(getattr(respuesta, "streaming", False))
        self.assertFalse(AccesoClinico.objects.exists())

    def test_fallo_de_auditoria_se_alerta_y_no_interrumpe_atencion(self):
        ruta, _ = self.archivo()
        with patch("apps.auditoria.mixins.AccesoClinico.objects.create", side_effect=RuntimeError("Fallo sintético")):
            with self.assertLogs("apps.auditoria.mixins", level="ERROR"):
                respuesta = self.client.get(f"/api/archivos/descargar/{ruta}")
        self.comprobar_bytes(respuesta)
        self.assertFalse(AccesoClinico.objects.exists())

    def test_descarga_simulada_atribuye_actor_real_y_sesion(self):
        ruta, _ = self.archivo()
        real = Usuario.objects.create_superuser("super-descarga@example.test", "x")
        referencia = Usuario.objects.create_user("medico@referencia.plexo.invalid", None)
        Membresia.objects.create(
            usuario=referencia, institucion=self.institucion, rol=Membresia.Rol.MEDICO,
        )
        CuentaReferencia.objects.create(
            usuario=referencia, ambito="institucion", rol=Membresia.Rol.MEDICO, institucion=self.institucion,
        )
        sesion = SesionSimulacion.objects.create(
            superusuario=real, cuenta=referencia, ambito="institucion", rol=Membresia.Rol.MEDICO,
            institucion=self.institucion, vence=timezone.now() + timedelta(minutes=10),
        )
        cliente = APIClient()
        tokens = cliente.post("/api/auth/token/", {"email": real.email, "password": "x"}, format="json")
        self.assertEqual(tokens.status_code, 200)
        respuesta = cliente.get(f"/api/archivos/descargar/{ruta}",
            HTTP_AUTHORIZATION=f"Bearer {tokens.data['access']}",
            HTTP_X_PLEXO_SIMULACION=str(sesion.pk),
        )
        self.comprobar_bytes(respuesta)
        self.assertEqual(AccesoClinico.objects.count(), 1, "Falta evidencia de la descarga simulada")
        acceso = AccesoClinico.objects.get()
        self.assertEqual(acceso.usuario_id, real.pk)
        self.assertEqual(acceso.simulacion_id, sesion.pk)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
