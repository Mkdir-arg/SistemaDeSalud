"""Dueño de los adjuntos de formularios de caso (#172, decisión 6 del 19/10).

El archivo de un campo «Archivo adjunto» pertenece al paciente del caso y al
caso. Solo quien lo subió lo asocia, una sola vez y sin reasignar. La descarga
institucional audita al paciente. Datos y archivos sintéticos en un MEDIA_ROOT
temporal.
"""
import shutil
import tempfile

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Institucion
from apps.registros.models import ArchivoClinico, Ciudadano

from . import motor
from .models import Caso, ValorCampo


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdjuntosDeCasoAuditoria172Tests(APITestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        ajuste = override_settings(MEDIA_ROOT=media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self.inst = Institucion.objects.create(nombre="Hospital sintético de adjuntos de caso")
        self.otra = Institucion.objects.create(nombre="Otro hospital sintético de casos")
        self.medica = self.usuario("medica-caso@example.test")
        self.otro_medico = self.usuario("otro-medico-caso@example.test")
        self.paciente_a = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente A sintético")
        self.paciente_b = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente B sintético")

        flujo = Flujo.objects.create(institucion=self.inst, titulo="Flujo sintético con adjunto")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        form = Formulario.objects.create(institucion=self.inst, titulo="Adjuntos")
        self.campo_archivo = Campo.objects.create(formulario=form, label="Informe", tipo="archivo")
        self.campo_nota = Campo.objects.create(formulario=form, label="Nota", tipo="texto_corto", requerido=True)
        self.nodo = Nodo.objects.create(version=version, tipo="form", formulario=form, titulo="Adjuntar")
        inicio = Nodo.objects.create(version=version, tipo="inicio", titulo="Inicio")
        fin = Nodo.objects.create(version=version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=version, origen=inicio, destino=self.nodo)
        Conexion.objects.create(version=version, origen=self.nodo, destino=fin)
        publicador = APIClient()
        publicador.force_authenticate(Usuario.objects.create_superuser("publicador-caso@example.test", "x"))
        publicada = publicador.post(f"/api/versiones-flujo/{version.pk}/publicar/", {}, format="json")
        self.assertEqual(publicada.status_code, 200, publicada.data)
        self.version = version

    def usuario(self, email, institucion=None):
        usuario = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        Membresia.objects.create(usuario=usuario, institucion=institucion or self.inst, rol=Membresia.Rol.MEDICO)
        return usuario

    def caso(self, ciudadano):
        return Caso.objects.create(institucion=self.inst, version=self.version, nodo_actual=self.nodo, ciudadano=ciudadano)

    def cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def subir(self, usuario, institucion=None):
        respuesta = self.cliente(usuario).post("/api/archivos/", {
            "archivo": SimpleUploadedFile("informe.pdf", b"%PDF-1.4 sintetico", content_type="application/pdf"),
            "institucion": (institucion or self.inst).pk,
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 201)
        return respuesta.data["ruta"]

    def completar(self, caso, ruta, autor, nota="Listo"):
        valores = {str(self.campo_archivo.pk): ruta}
        if nota is not None:
            valores[str(self.campo_nota.pk)] = nota
        return motor.avanzar(caso, {"valores": valores}, autor=autor)

    def dueno(self, ruta):
        meta = ArchivoClinico.objects.get(ruta=ruta)
        return meta.ciudadano_id, meta.objeto_tipo, meta.objeto_id, meta.asociado_por_id, meta.asociado_at is not None

    def test_quien_subio_asocia_al_paciente_y_al_caso(self):
        ruta = self.subir(self.medica)
        caso = self.caso(self.paciente_a)
        self.completar(caso, ruta, self.medica)
        self.assertEqual(self.dueno(ruta), (self.paciente_a.pk, "Caso", caso.pk, self.medica.pk, True))
        self.assertEqual(ValorCampo.objects.get(caso=caso, campo=self.campo_archivo).valor, ruta)

    def test_otro_actor_no_asocia_un_archivo_ajeno(self):
        ruta = self.subir(self.medica)
        caso = self.caso(self.paciente_a)
        with self.assertRaisesMessage(motor.ErrorMotor, "Solo quien subió"):
            self.completar(caso, ruta, self.otro_medico)
        self.assertEqual(self.dueno(ruta), (None, "", None, None, False))
        self.assertFalse(ValorCampo.objects.filter(caso=caso).exists())

    def test_archivo_de_otro_caso_no_se_reasigna(self):
        ruta = self.subir(self.medica)
        caso_a = self.caso(self.paciente_a)
        self.completar(caso_a, ruta, self.medica)
        for ciudadano in (self.paciente_b, self.paciente_a):
            with self.subTest(ciudadano=ciudadano.nombre):
                otro = self.caso(ciudadano)
                with self.assertRaises(motor.ErrorMotor):
                    self.completar(otro, ruta, self.medica)
                self.assertFalse(ValorCampo.objects.filter(caso=otro).exists())
        self.assertEqual(self.dueno(ruta), (self.paciente_a.pk, "Caso", caso_a.pk, self.medica.pk, True))

    def test_referencias_externas_sin_metadata_consentimiento_u_otra_institucion_se_rechazan(self):
        medica_otra = self.usuario("medica-otra-caso@example.test", self.otra)
        ajena = self.subir(medica_otra, self.otra)
        sin_meta = default_storage.save(f"uploads/{self.inst.pk}/sin-meta.pdf", ContentFile(b"%PDF-s"))
        consentimiento = default_storage.save(f"uploads/{self.inst.pk}/consentimiento.pdf", ContentFile(b"%PDF-c"))
        ArchivoClinico.objects.create(
            institucion=self.inst, ruta=consentimiento, nombre_original="c.pdf", content_type="application/pdf",
            tamano=6, sha256="0" * 64, proposito=ArchivoClinico.Proposito.CONSENTIMIENTO, subido_por=self.medica,
        )
        for ruta in ("https://externo.test/informe.pdf", "uploads/../secreto.pdf", ajena, sin_meta, consentimiento):
            with self.subTest(ruta=ruta):
                caso = self.caso(self.paciente_a)
                with self.assertRaises(motor.ErrorMotor):
                    self.completar(caso, ruta, self.medica if ruta != ajena else medica_otra)
                self.assertFalse(ValorCampo.objects.filter(caso=caso).exists())

    def test_si_el_avance_falla_la_asociacion_se_deshace(self):
        ruta = self.subir(self.medica)
        caso = self.caso(self.paciente_a)
        with self.assertRaisesMessage(motor.ErrorMotor, "Falta completar"):
            self.completar(caso, ruta, self.medica, nota=None)
        self.assertEqual(self.dueno(ruta), (None, "", None, None, False))
        self.assertFalse(ValorCampo.objects.filter(caso=caso).exists())
        # El mismo archivo sigue disponible para el avance correcto.
        self.completar(caso, ruta, self.medica)
        self.assertEqual(self.dueno(ruta), (self.paciente_a.pk, "Caso", caso.pk, self.medica.pk, True))

    def test_descarga_institucional_audita_al_paciente_del_caso(self):
        ruta = self.subir(self.medica)
        self.completar(self.caso(self.paciente_a), ruta, self.medica)
        respuesta = self.cliente(self.otro_medico).get(f"/api/archivos/descargar/{ruta}")
        self.assertEqual(respuesta.status_code, 200)
        b"".join(respuesta.streaming_content)
        acceso = AccesoClinico.objects.filter(recurso="archivoclinico").latest("pk")
        self.assertEqual(acceso.ciudadano_id, self.paciente_a.pk)

    def test_caso_sin_paciente_asocia_solo_el_caso(self):
        ruta = self.subir(self.medica)
        caso = self.caso(None)
        self.completar(caso, ruta, self.medica)
        self.assertEqual(self.dueno(ruta), (None, "Caso", caso.pk, self.medica.pk, True))
        # Ya tiene dueño: no pasa a otro caso aunque ese sí tenga paciente.
        with self.assertRaises(motor.ErrorMotor):
            self.completar(self.caso(self.paciente_a), ruta, self.medica)

    def test_valor_ya_guardado_en_el_caso_no_se_revalida(self):
        # Los adjuntos cargados antes de este cambio quedan sin dueño (sin
        # backfill): reenviar el mismo valor no los asocia ni los rechaza.
        legacy = default_storage.save(f"uploads/{self.inst.pk}/legacy.pdf", ContentFile(b"%PDF-l"))
        caso = self.caso(self.paciente_a)
        ValorCampo.objects.create(caso=caso, campo=self.campo_archivo, nodo=self.nodo, valor=legacy)
        self.completar(caso, legacy, self.medica)
        self.assertFalse(ArchivoClinico.objects.filter(ruta=legacy).exists())
