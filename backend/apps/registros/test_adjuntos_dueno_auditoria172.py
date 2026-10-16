"""Dueño autoritativo de adjuntos clínicos (#172, AUD-050, AUD-002 backend, AUD-003).

Un archivo pertenece a un paciente y a un estudio. Solo quien lo subió lo asocia;
un admin de la institución confirma los que no tienen dueño; el portal publica
solo lo asociado. Datos y archivos sintéticos en un MEDIA_ROOT temporal.
"""
import shutil
import tempfile
from datetime import date

from django.apps import apps as django_apps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.instituciones.models import Institucion
from apps.portal.views_datos import _archivo_del_estudio

from .models import ArchivoClinico, Ciudadano, Estudio, HistoriaClinica


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class DuenoAdjuntoAuditoria172Tests(APITestCase):
    def setUp(self):
        media = tempfile.mkdtemp()
        ajuste = override_settings(MEDIA_ROOT=media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        self.inst = Institucion.objects.create(nombre="Hospital sintético de adjuntos")
        self.otra = Institucion.objects.create(nombre="Otro hospital sintético")
        self.medica = self.usuario("medica-adjuntos@example.test", Membresia.Rol.MEDICO)
        self.otro_medico = self.usuario("otro-medico-adjuntos@example.test", Membresia.Rol.MEDICO)
        self.admin = self.usuario("admin-adjuntos@example.test", Membresia.Rol.ADMIN_INSTITUCION)
        self.estudio_a = self.estudio("Paciente A sintético")
        self.estudio_b = self.estudio("Paciente B sintético")

    def usuario(self, email, rol, institucion=None):
        usuario = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        Membresia.objects.create(usuario=usuario, institucion=institucion or self.inst, rol=rol)
        return usuario

    def estudio(self, nombre, institucion=None):
        ciudadano = Ciudadano.objects.create(institucion=institucion or self.inst, nombre=nombre)
        historia = HistoriaClinica.objects.create(ciudadano=ciudadano)
        return Estudio.objects.create(historia=historia, tipo="Ecografía", fecha=date(2026, 10, 1), realizado=True)

    def cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def subir(self, usuario, institucion=None):
        respuesta = self.cliente(usuario).post("/api/archivos/", {
            "archivo": SimpleUploadedFile("eco.pdf", b"%PDF-1.4 sintetico", content_type="application/pdf"),
            "institucion": (institucion or self.inst).pk,
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 201)
        return respuesta.data["ruta"]

    def asignar(self, usuario, estudio, ruta):
        return self.cliente(usuario).patch(f"/api/estudios/{estudio.pk}/", {"archivo": ruta}, format="json")

    def test_quien_subio_asocia_y_el_portal_publica_solo_ese_estudio(self):
        ruta = self.subir(self.medica)
        respuesta = self.asignar(self.medica, self.estudio_a, ruta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["archivo_asociado"])
        meta = ArchivoClinico.objects.get(ruta=ruta)
        self.assertEqual((meta.ciudadano_id, meta.objeto_tipo, meta.objeto_id, meta.asociado_por_id),
                         (self.estudio_a.historia.ciudadano_id, "Estudio", self.estudio_a.pk, self.medica.pk))
        self.estudio_a.refresh_from_db()
        self.assertEqual(_archivo_del_estudio(self.estudio_a), ruta)
        # Repetir la misma asociación es un no-op.
        self.assertEqual(self.asignar(self.medica, self.estudio_a, ruta).status_code, 200)

    def test_archivo_de_un_paciente_no_se_publica_en_el_estudio_de_otro(self):
        ruta = self.subir(self.medica)
        self.assertEqual(self.asignar(self.medica, self.estudio_a, ruta).status_code, 200)
        for actor in (self.medica, self.otro_medico):
            with self.subTest(actor=actor.email):
                respuesta = self.asignar(actor, self.estudio_b, ruta)
                self.assertEqual(respuesta.status_code, 400)
                self.estudio_b.refresh_from_db()
                self.assertEqual(self.estudio_b.archivo, "")
        # Aunque la ruta se copie por fuera de la API, el portal no la publica.
        Estudio.objects.filter(pk=self.estudio_b.pk).update(archivo=ruta)
        self.estudio_b.refresh_from_db()
        self.assertIsNone(_archivo_del_estudio(self.estudio_b))
        self.assertEqual(ArchivoClinico.objects.get(ruta=ruta).objeto_id, self.estudio_a.pk)

    def test_solo_quien_subio_asocia_un_archivo_sin_dueno(self):
        ruta = self.subir(self.medica)
        respuesta = self.asignar(self.otro_medico, self.estudio_b, ruta)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Solo quien subió", str(respuesta.data["archivo"]))
        self.assertIsNone(ArchivoClinico.objects.get(ruta=ruta).asociado_at)

    def test_referencias_externas_consentimiento_u_otra_institucion_se_rechazan(self):
        ajena = self.subir(self.usuario("medica-otra@example.test", Membresia.Rol.MEDICO, self.otra), self.otra)
        consentimiento = default_storage.save(f"uploads/{self.inst.pk}/consentimiento.pdf", ContentFile(b"%PDF-c"))
        ArchivoClinico.objects.create(
            institucion=self.inst, ruta=consentimiento, nombre_original="c.pdf", content_type="application/pdf",
            tamano=6, sha256="0" * 64, proposito=ArchivoClinico.Proposito.CONSENTIMIENTO, subido_por=self.medica,
        )
        for ruta in ("https://externo.test/estudio.pdf", "uploads/../secreto.pdf", ajena, consentimiento):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.asignar(self.medica, self.estudio_a, ruta).status_code, 400)
        self.estudio_a.refresh_from_db()
        self.assertEqual(self.estudio_a.archivo, "")

    def test_admin_confirma_legacy_sin_metadata_y_otros_roles_no(self):
        legacy = default_storage.save(f"uploads/{self.inst.pk}/legacy.pdf", ContentFile(b"%PDF-legacy"))
        Estudio.objects.filter(pk=self.estudio_a.pk).update(archivo=legacy)
        self.estudio_a.refresh_from_db()
        self.assertIsNone(_archivo_del_estudio(self.estudio_a))
        url = f"/api/estudios/{self.estudio_a.pk}/confirmar-archivo/"
        self.assertEqual(self.cliente(self.medica).post(url).status_code, 403)
        respuesta = self.cliente(self.admin).post(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.data["archivo_asociado"])
        meta = ArchivoClinico.objects.get(ruta=legacy)
        self.assertEqual((meta.asociado_por_id, meta.subido_por_id, meta.tamano), (self.admin.pk, None, len(b"%PDF-legacy")))
        self.assertEqual(_archivo_del_estudio(self.estudio_a), legacy)

    def test_admin_no_reasigna_un_archivo_que_ya_pertenece_a_otro_estudio(self):
        ruta = self.subir(self.medica)
        self.assertEqual(self.asignar(self.medica, self.estudio_a, ruta).status_code, 200)
        Estudio.objects.filter(pk=self.estudio_b.pk).update(archivo=ruta)
        respuesta = self.cliente(self.admin).post(f"/api/estudios/{self.estudio_b.pk}/confirmar-archivo/")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(ArchivoClinico.objects.get(ruta=ruta).objeto_id, self.estudio_a.pk)

    def test_descarga_institucional_audita_al_paciente_duenio(self):
        ruta = self.subir(self.medica)
        self.asignar(self.medica, self.estudio_a, ruta)
        respuesta = self.cliente(self.otro_medico).get(f"/api/archivos/descargar/{ruta}")
        self.assertEqual(respuesta.status_code, 200)
        b"".join(respuesta.streaming_content)
        acceso = AccesoClinico.objects.filter(recurso="archivoclinico").latest("pk")
        self.assertEqual(acceso.ciudadano_id, self.estudio_a.historia.ciudadano_id)

    def test_backfill_asocia_solo_metadata_inequivoca(self):
        from importlib import import_module

        asociar = import_module("apps.registros.migrations.0012_archivo_clinico_dueno").asociar_inequivocos

        def meta(estudio, ruta, objeto_id, institucion=None):
            Estudio.objects.filter(pk=estudio.pk).update(archivo=ruta)
            return ArchivoClinico.objects.create(
                institucion=institucion or self.inst, ruta=ruta, nombre_original="x.pdf",
                content_type="application/pdf", tamano=1, sha256="0" * 64,
                proposito=ArchivoClinico.Proposito.ESTUDIO, objeto_tipo="Estudio", objeto_id=objeto_id,
            )

        claro = meta(self.estudio_a, f"uploads/{self.inst.pk}/claro.pdf", self.estudio_a.pk)
        otro_id = meta(self.estudio_b, f"uploads/{self.inst.pk}/otro-id.pdf", self.estudio_a.pk)
        compartido_c = self.estudio("Paciente C sintético")
        compartido = meta(compartido_c, f"uploads/{self.inst.pk}/compartido.pdf", compartido_c.pk)
        Estudio.objects.filter(pk=self.estudio("Paciente D sintético").pk).update(archivo=compartido.ruta)
        lejano = self.estudio("Paciente E sintético")
        otra_inst = meta(lejano, f"uploads/{self.otra.pk}/otra.pdf", lejano.pk, self.otra)

        asociar(django_apps, None)
        for registro, esperado in ((claro, True), (otro_id, False), (compartido, False), (otra_inst, False)):
            with self.subTest(ruta=registro.ruta):
                registro.refresh_from_db()
                self.assertEqual(registro.asociado_at is not None, esperado)
        self.assertEqual(claro.ciudadano_id, self.estudio_a.historia.ciudadano_id)
