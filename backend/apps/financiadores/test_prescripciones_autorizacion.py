"""Adjunto clínico ficticio: ingreso institucional y lectura médica separada."""
from uuid import uuid4
from hashlib import sha256
from unittest.mock import patch
from tempfile import mkdtemp
from importlib import reload
from pathlib import Path

from django.conf import settings
from django.core.files.storage import storages
from django.core.files.storage.handler import InvalidStorageError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches
from rest_framework.test import APITestCase

from . import autorizaciones as a
from . import models as m
from .test_autorizaciones import AutorizacionSetup
from apps.accounts.models import Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera


PDF = b"%PDF-1.4\nDocumento totalmente ficticio\n%%EOF"


ESTATICOS = {"staticfiles": settings.STORAGES["staticfiles"]}
ALMACENAMIENTOS_CLINICOS = {**ESTATICOS, **{alias: {
    "BACKEND": "django.core.files.storage.InMemoryStorage"}
    for alias in ("default", "prescripciones")}}


@override_settings(STORAGES=ALMACENAMIENTOS_CLINICOS)
class EstaticosPrescripcionTests(SimpleTestCase):
    def test_estaticos_versionados_con_el_almacenamiento_de_prescripciones(self):
        raiz = Path(mkdtemp(prefix="ostel-prescripcion-estaticos-"))
        css = b"body { color: black; }"
        for nombre in ("ficticio.css", "ficticio.0123456789ab.css"):
            (raiz / nombre).write_bytes(css)
        for faltante in (None, "default", "prescripciones"):
            aliases = {nombre: opciones for nombre, opciones in ALMACENAMIENTOS_CLINICOS.items()
                       if nombre != faltante}
            with self.subTest(faltante=faltante), override_settings(STORAGES=aliases,
                    STATIC_ROOT=raiz, WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False):
                respuesta = self.client_class().get("/static/ficticio.0123456789ab.css")
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(b"".join(respuesta.streaming_content), css)
                if faltante:
                    with self.assertRaises(InvalidStorageError):
                        storages[faltante]


@override_settings(STORAGES=ALMACENAMIENTOS_CLINICOS)
class PrescripcionAutorizacionTests(AutorizacionSetup, APITestCase):
    def huella(self):
        modelos = (m.SolicitudAutorizacion, m.EventoAutorizacion, m.PrescripcionAutorizacion,
            m.EventoCobertura, m.ReservaCobertura, Caso, EventoCaso)
        return sha256(repr([list(modelo.objects.order_by("pk").values()) for modelo in modelos]).encode()).hexdigest()

    def datos(self, clave=None, contenido=PDF, nombre="orden.pdf", tipo="application/pdf"):
        return dict(caso=self.caso.pk, prestacion=self.prestacion.pk,
            intento=str(a.intento_actual(self.caso)), cantidad=3,
            justificacion="Justificación administrativa ficticia", clave=str(clave or uuid4()),
            prescripcion=SimpleUploadedFile(nombre, contenido, content_type=tipo))

    def presentar(self, **datos):
        self.client.force_authenticate(self.usuario)
        return self.client.post(self.url + "con-prescripcion/", self.datos(**datos), format="multipart")

    def evaluar(self, decision):
        creada = self.presentar()
        self.assertEqual(creada.status_code, 201)
        id_solicitud = creada.data["id"]
        detalle = f"{self.url}{id_solicitud}/?financiador={self.financiador.pk}"
        resolver = f"{self.url}{id_solicitud}/resolver/?financiador={self.financiador.pk}"
        self.membresia.auditoria_medica = True
        self.membresia.resuelve_autorizaciones = False
        self.membresia.save(update_fields=["auditoria_medica", "resuelve_autorizaciones"])
        self.client.force_authenticate(self.operador)
        archivo = self.client.get(f"{self.url}{id_solicitud}/prescripcion/?financiador={self.financiador.pk}")
        self.assertEqual(archivo.status_code, 200)
        self.assertEqual(b"".join(archivo.streaming_content), PDF)
        self.assertFalse(self.client.get(detalle).data["puede_resolver"])
        datos = self.aprobacion() if decision == "aprobar" else {
            "revision": 1, "decision": "rechazar", "motivo": "Referencia de revisión ficticia",
            "clave": str(uuid4())}
        antes = self.huella()
        self.assertEqual(self.client.post(resolver, datos, format="json").status_code, 403)
        self.assertEqual(self.huella(), antes)
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.assertTrue(self.client.get(detalle).data["puede_resolver"])
        respuesta = self.client.post(resolver, datos, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        estado = "aprobada" if decision == "aprobar" else "rechazada"
        self.assertEqual(respuesta.data["id"], id_solicitud)
        self.assertEqual(respuesta.data["estado"], estado)
        self.assertEqual(respuesta.data["revision"], 2)
        self.assertFalse(respuesta.data["puede_resolver"])
        self.assertEqual([h["accion"] for h in respuesta.data["historial"]], ["solicitar", decision])
        self.assertEqual(respuesta.data["cantidades"], {
            "comprometida": 0, "consumida": 0, "disponible": 3 if decision == "aprobar" else 0})
        self.assertEqual(self.client.post(resolver, datos, format="json").data, respuesta.data)
        self.assertEqual(m.SolicitudAutorizacion.objects.count(), 1)
        self.assertEqual(m.PrescripcionAutorizacion.objects.count(), 1)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, "recibido")
        self.assertEqual(self.caso.nodo_actual_id, self.nodo.pk)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertFalse(m.ReservaCobertura.objects.exists())
        self.client.force_authenticate(self.usuario)
        institucional = self.client.get(f"{self.url}{id_solicitud}/?institucion={self.institucion.pk}")
        self.assertEqual(institucional.data["estado"], estado)
        self.assertEqual(institucional.data["prescripcion_estado"], "presentada")

    def test_evaluacion_medica_aprueba_la_solicitud_existente_sin_registrar_atencion(self):
        self.evaluar("aprobar")

    def test_evaluacion_medica_rechaza_la_solicitud_existente_sin_registrar_atencion(self):
        self.evaluar("rechazar")

    def observar_reenviar_y_resolver(self, decision):
        # Plazo ficticio para comprobar conservación, no una política clínica.
        self.convenio.plazo_autorizacion_horas = 48
        self.convenio.save(update_fields=["plazo_autorizacion_horas"])
        clave_presentacion = uuid4()
        creada = self.presentar(clave=clave_presentacion)
        self.assertEqual(creada.status_code, 201, creada.data)
        solicitud_id = creada.data["id"]
        plazo = creada.data["plazo_respuesta"]
        self.assertIsNotNone(plazo)
        original = m.PrescripcionAutorizacion.objects.values().get(solicitud_id=solicitud_id)
        base = f"{self.url}{solicitud_id}/"
        resolver = base + f"resolver/?financiador={self.financiador.pk}"
        descarga = base + f"prescripcion/?financiador={self.financiador.pk}"
        reenviar = base + f"reenviar/?institucion={self.institucion.pk}"
        self.membresia.auditoria_medica = True
        self.membresia.save(update_fields=["auditoria_medica"])
        self.client.force_authenticate(self.operador)
        observacion = {"revision": 1, "decision": "observar",
            "motivo": "Aclarar referencia administrativa ficticia", "clave": str(uuid4())}
        observada = self.client.post(resolver, observacion, format="json")
        self.assertEqual(observada.status_code, 200, observada.data)
        self.assertEqual((observada.data["id"], observada.data["estado"], observada.data["revision"]),
            (solicitud_id, "observada", 2))
        self.assertEqual(observada.data["plazo_respuesta"], plazo)

        self.client.force_authenticate(self.usuario)
        datos = {"revision": 2, "justificacion": "Referencia aclarada sin contenido clínico",
            "clave": str(uuid4())}
        antes = self.huella()
        obsoleta = self.client.post(reenviar, {**datos, "revision": 1}, format="json")
        self.assertEqual(obsoleta.status_code, 400)
        self.assertEqual(self.huella(), antes)
        self.assertEqual(self.client.get(descarga).status_code, 403)
        cambio = self.presentar(clave=clave_presentacion, contenido=PDF + b"otro documento")
        self.assertEqual(cambio.status_code, 400)
        self.assertEqual(self.huella(), antes)

        reenviada = self.client.post(reenviar, datos, format="json")
        self.assertEqual(reenviada.status_code, 200, reenviada.data)
        self.assertEqual((reenviada.data["id"], reenviada.data["estado"], reenviada.data["revision"]),
            (solicitud_id, "pendiente", 3))
        self.assertEqual(reenviada.data["plazo_respuesta"], plazo)
        self.assertEqual(reenviada.data["prescripcion_estado"], "presentada")
        antes = self.huella()
        self.assertEqual(self.client.post(reenviar, datos, format="json").data, reenviada.data)
        self.assertEqual(self.huella(), antes)

        self.client.force_authenticate(self.operador)
        archivo = self.client.get(descarga)
        self.assertEqual(archivo.status_code, 200)
        self.assertEqual(b"".join(archivo.streaming_content), PDF)
        self.membresia.resuelve_autorizaciones = False
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        final = self.aprobacion(revision=3) if decision == "aprobar" else {
            "revision": 3, "decision": "rechazar", "motivo": "Referencia administrativa ficticia",
            "clave": str(uuid4())}
        antes = self.huella()
        self.assertEqual(self.client.post(resolver, final, format="json").status_code, 403)
        self.assertEqual(self.huella(), antes)
        self.membresia.resuelve_autorizaciones = True
        self.membresia.auditoria_medica = False
        self.membresia.save(update_fields=["resuelve_autorizaciones", "auditoria_medica"])
        self.assertEqual(self.client.get(descarga).status_code, 403)
        resuelta = self.client.post(resolver, final, format="json")
        self.assertEqual(resuelta.status_code, 200, resuelta.data)
        self.assertEqual((resuelta.data["id"], resuelta.data["estado"], resuelta.data["revision"]),
            (solicitud_id, "aprobada" if decision == "aprobar" else "rechazada", 4))
        self.assertEqual(resuelta.data["plazo_respuesta"], plazo)
        self.assertEqual([fila["accion"] for fila in resuelta.data["historial"]],
            ["solicitar", "observar", "reenviar", decision])
        modelos = (m.SolicitudAutorizacion, m.EventoAutorizacion, m.PrescripcionAutorizacion,
            m.ReservaCobertura, Caso, EventoCaso)
        dominio = [list(modelo.objects.order_by("pk").values()) for modelo in modelos]
        eventos = list(m.EventoCobertura.objects.order_by("pk").values())
        self.assertEqual(self.client.post(resolver, final, format="json").data, resuelta.data)
        self.assertEqual([list(modelo.objects.order_by("pk").values()) for modelo in modelos], dominio)
        posteriores = list(m.EventoCobertura.objects.order_by("pk").values())
        self.assertEqual(len(posteriores), len(eventos) + 1)
        self.assertEqual(posteriores[:-1], eventos)
        consulta = posteriores[-1]
        self.assertEqual((consulta["accion"], consulta["objeto"], consulta["financiador_id"],
            consulta["institucion_id"], consulta["usuario_id"], consulta["motivo"]),
            ("consultar_autorizaciones", str(self.financiador.pk), self.financiador.pk,
                None, self.operador.pk, ""))
        self.assertEqual(m.PrescripcionAutorizacion.objects.values().get(solicitud_id=solicitud_id), original)
        self.assertEqual(m.PrescripcionAutorizacion.objects.count(), 1)
        self.assertEqual(m.SolicitudAutorizacion.objects.count(), 1)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_observacion_reenvio_y_aprobacion_conservan_prescripcion_y_plazo(self):
        self.observar_reenviar_y_resolver("aprobar")

    def test_observacion_reenvio_y_rechazo_conservan_prescripcion_y_plazo(self):
        self.observar_reenviar_y_resolver("rechazar")

    def test_presentacion_privada_con_solicitud_y_descarga_medica_auditada(self):
        respuesta = self.presentar()
        self.assertEqual(respuesta.status_code, 201, getattr(respuesta, "data", None))
        self.assertEqual(respuesta.data["prescripcion_estado"], "presentada")
        solicitud = respuesta.data["id"]
        descarga = f"{self.url}{solicitud}/prescripcion/?financiador={self.financiador.pk}"
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(descarga).status_code, 403)
        self.membresia.auditoria_medica = True
        self.membresia.save(update_fields=["auditoria_medica"])
        archivo = self.client.get(descarga)
        self.assertEqual(archivo.status_code, 200)
        self.assertEqual(b"".join(archivo.streaming_content), PDF)
        self.assertEqual(archivo["Cache-Control"], "private, no-store")
        self.assertEqual(archivo["X-Content-Type-Options"], "nosniff")
        self.assertTrue(archivo["Content-Disposition"].startswith("attachment;"))
        acceso = AccesoClinico.objects.get(recurso="prescripcionautorizacion")
        self.assertEqual(acceso.usuario_id, self.operador.pk)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
        self.assertEqual(acceso.ciudadano_id, self.caso.ciudadano_id)
        self.assertNotIn("ficticio", acceso.detalle)

    def test_plataforma_no_sustituye_al_presentante_institucional(self):
        plataforma = Usuario.objects.create_user("plataforma-ficticia@example.invalid", "x", is_superuser=True)
        self.client.force_authenticate(plataforma)
        respuesta = self.client.post(self.url + "con-prescripcion/", self.datos(), format="multipart")
        self.assertEqual(respuesta.status_code, 403)

    def test_opciones_desconocidas_no_se_ignoran_ni_modifican_datos(self):
        self.client.force_authenticate(self.usuario)
        antes = self.huella()
        for extra in ({"decision": "aprobar"}, {"financiador": "999"}):
            with self.subTest(extra=extra):
                datos = {**self.datos(), **extra}
                r = self.client.post(self.url + "con-prescripcion/", datos, format="multipart")
                self.assertEqual(r.status_code, 400)
                self.assertEqual(self.huella(), antes)

    def test_storage_en_media_publica_falla_cerrado_sin_escribir(self):
        carpeta = mkdtemp(prefix="ostel-prescripcion-storage-inseguro-")
        antes = self.huella()
        with override_settings(MEDIA_ROOT=carpeta, STORAGES={**ESTATICOS, "prescripciones": {
                "BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": carpeta}}}):
            respuesta = self.presentar()
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(self.huella(), antes)

    def test_alias_ausente_no_recurre_al_almacenamiento_general(self):
        creada = self.presentar()
        self.assertEqual(creada.status_code, 201)
        self.membresia.auditoria_medica = True
        self.membresia.save(update_fields=["auditoria_medica"])
        antes = self.huella()
        publica = Path(mkdtemp(prefix="ostel-prescripciones-media-"))
        accesos = AccesoClinico.objects.filter(recurso="prescripcionautorizacion").count()
        for aliases in ({"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}},
                {"prescripciones": {"BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": str(publica)}}}):
            with override_settings(STORAGES={**ESTATICOS, **aliases}, MEDIA_ROOT=publica):
                self.assertEqual(self.presentar().status_code, 503)
                self.client.force_authenticate(self.operador)
                respuesta = self.client.get(f"{self.url}{creada.data['id']}/prescripcion/?financiador={self.financiador.pk}")
                self.assertEqual(respuesta.status_code, 503)
                self.assertFalse(respuesta.streaming)
            self.assertEqual(self.huella(), antes)
            self.assertEqual(AccesoClinico.objects.filter(recurso="prescripcionautorizacion").count(), accesos)

    def test_storage_fuera_de_media_no_expone_documento_por_rutas_normalizadas(self):
        import config.urls as urls
        patrones_anteriores = urls.urlpatterns
        raiz = Path(mkdtemp(prefix="ostel-prescripcion-privacidad-"))
        try:
            with override_settings(DEBUG=True, MEDIA_ROOT=raiz / "publico", STORAGES={**ESTATICOS, "default": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage"}, "prescripciones": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": str(raiz / "privado")}}}):
                reload(urls)
                clear_url_caches()
                creada = self.presentar()
                self.assertEqual(creada.status_code, 201, creada.data)
                documento = m.PrescripcionAutorizacion.objects.get(solicitud_id=creada.data["id"])
                self.assertEqual((raiz / "privado" / documento.ruta).read_bytes(), PDF)
                self.client.force_authenticate(None)
                for prefijo in ("/media/", "/media/x/../", "/media/x/%2e%2e/"):
                    respuesta = self.client.get(prefijo + documento.ruta)
                    self.assertEqual(respuesta.status_code, 404)
                    self.assertFalse(respuesta.streaming)
                self.membresia.auditoria_medica = True
                self.membresia.save(update_fields=["auditoria_medica"])
                self.client.force_authenticate(self.operador)
                respuesta = self.client.get(f"{self.url}{creada.data['id']}/prescripcion/?financiador={self.financiador.pk}")
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(b"".join(respuesta.streaming_content), PDF)
                respuesta.close()
        finally:
            urls.urlpatterns = patrones_anteriores
            clear_url_caches()

    def test_reintento_mismos_bytes_y_clave_no_duplica_y_no_reemplaza(self):
        clave = uuid4()
        inicial = self.presentar(clave=clave)
        self.assertEqual(inicial.status_code, 201)
        antes = self.huella()
        self.assertEqual(self.presentar(clave=clave).data, inicial.data)
        self.assertEqual(self.huella(), antes)
        self.assertEqual(self.presentar(clave=clave, contenido=PDF + b"otro").status_code, 400)
        self.assertEqual(self.huella(), antes)
        self.assertEqual(self.presentar().status_code, 400)
        self.assertEqual(self.huella(), antes)

    def test_no_completa_retroactivamente_una_solicitud_json_y_no_cambia_su_dto(self):
        self.client.force_authenticate(self.usuario)
        datos = self.datos()
        datos.pop("prescripcion")
        respuesta = self.client.post(self.url, datos, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertNotIn("prescripcion_estado", respuesta.data)
        antes = self.huella()
        self.assertEqual(self.presentar(clave=datos["clave"]).status_code, 400)
        self.assertEqual(self.huella(), antes)

    def test_formato_firma_tamano_y_unico_archivo_antes_de_escribir(self):
        antes = self.huella()
        for nombre, tipo, contenido in [("orden.txt", "text/plain", b"texto"),
                ("orden.svg", "image/svg+xml", b"<svg/>"), ("orden.png", "image/png", PDF),
                ("orden.jpg", "application/pdf", PDF), ("vacio.pdf", "application/pdf", b"")]:
            with self.subTest(nombre=nombre, tipo=tipo):
                self.assertEqual(self.presentar(nombre=nombre, tipo=tipo, contenido=contenido).status_code, 400)
                self.assertEqual(self.huella(), antes)
        with override_settings(ARCHIVO_CLINICO_MAX_BYTES=5):
            self.assertEqual(self.presentar().status_code, 400)
        self.client.force_authenticate(self.usuario)
        datos = self.datos()
        datos["prescripcion"] = [datos["prescripcion"], SimpleUploadedFile("otro.pdf", PDF, content_type="application/pdf")]
        self.assertEqual(self.client.post(self.url + "con-prescripcion/", datos, format="multipart").status_code, 400)
        self.assertEqual(self.huella(), antes)

    def test_otros_tipos_de_imagen_reutilizan_validacion_sin_abrir_texto(self):
        for nombre, tipo, contenido in [("a.png", "image/png", b"\x89PNG\r\n\x1a\nFICTICIO"),
                ("a.jpg", "image/jpeg", b"\xff\xd8\xffFICTICIO"),
                ("a.webp", "image/webp", b"RIFF1234WEBPFICTICIO")]:
            with self.subTest(tipo=tipo):
                datos = self.datos(nombre=nombre, tipo=tipo, contenido=contenido)
                self.client.force_authenticate(self.usuario)
                r = self.client.post(self.url + "con-prescripcion/", datos, format="multipart")
                self.assertEqual(r.status_code, 201, getattr(r, "data", None))
                anulada = self.client.post(f"{self.url}{r.data['id']}/anular/?institucion={self.institucion.pk}",
                    {"revision": 1, "motivo": "Fin de escenario ficticio", "clave": str(uuid4())}, format="json")
                self.assertEqual(anulada.status_code, 200, anulada.data)

    def test_metadatos_no_aparecen_en_bandeja_historial_ni_descarga_generica(self):
        obj = self.presentar()
        documento = m.PrescripcionAutorizacion.objects.get(solicitud_id=obj.data["id"])
        self.client.force_authenticate(self.operador)
        for url in (f"{self.url}?financiador={self.financiador.pk}",
                f"{self.url}{obj.data['id']}/?financiador={self.financiador.pk}"):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            for privado in (documento.ruta, documento.sha256, "orden.pdf", "content_type", "prescripcion.pdf"):
                self.assertNotIn(privado, repr(respuesta.data))
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.client.get(f"/api/archivos/descargar/{documento.ruta}").status_code, 404)
        self.assertEqual(self.client.get(f"/media/{documento.ruta}").status_code, 404)

    def test_permisos_revocados_y_ambitos_ajenos_sin_bytes(self):
        obj = self.presentar()
        url = f"{self.url}{obj.data['id']}/prescripcion/"
        self.membresia.auditoria_medica = True
        self.membresia.save(update_fields=["auditoria_medica"])
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(url, {"institucion": self.institucion.pk}).status_code, 403)
        otro = m.Financiador.objects.create(nombre="Otro ficticio", tipo="otro")
        m.MembresiaFinanciador.objects.create(financiador=otro, usuario=self.operador, rol="auditor", auditoria_medica=True)
        self.assertEqual(self.client.get(url, {"financiador": otro.pk}).status_code, 404)
        self.membresia.auditoria_medica = False
        self.membresia.save(update_fields=["auditoria_medica"])
        self.assertEqual(self.client.get(url, {"financiador": self.financiador.pk}).status_code, 403)
        self.assertFalse(AccesoClinico.objects.filter(recurso="prescripcionautorizacion").exists())

    def test_fallo_auditoria_rechaza_lectura_y_revierte_presentacion_con_archivo(self):
        antes = self.huella()
        rutas = []
        storage = storages["prescripciones"]
        guardar = storage.save
        def observar(ruta, archivo):
            resultado = guardar(ruta, archivo)
            rutas.append(resultado)
            return resultado
        self.client.raise_request_exception = False
        with patch.object(storage, "save", side_effect=observar), \
                patch("apps.financiadores.prescripciones_autorizacion.auditar", side_effect=RuntimeError("Fallo ficticio")):
            self.assertEqual(self.presentar().status_code, 500)
        self.assertEqual(self.huella(), antes)
        self.assertTrue(rutas)
        self.assertTrue(all(not storage.exists(ruta) for ruta in rutas))
        obj = self.presentar()
        self.membresia.auditoria_medica = True
        self.membresia.save(update_fields=["auditoria_medica"])
        self.client.force_authenticate(self.operador)
        with patch("apps.financiadores.api_autorizaciones.registrar_accesos", side_effect=RuntimeError("Fallo ficticio")):
            r = self.client.get(f"{self.url}{obj.data['id']}/prescripcion/?financiador={self.financiador.pk}")
        self.assertEqual(r.status_code, 500)
        self.assertFalse(r.streaming)
