"""Circuito administrativo con datos inventados y DB de pruebas aislada."""
from uuid import uuid4
from io import BytesIO

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from openpyxl import load_workbook

from apps.accounts.models import Usuario
from .models import Afiliado, Financiador, MembresiaFinanciador, Importacion
from .ostel_synthetic import Lote, generar_xlsx, _persona


class ImportacionAdministrativaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Financiador.objects.create(nombre="Administrativa ficticia", tipo="obra_social")
        cls.user = Usuario.objects.create_user("admin-ostel@example.invalid", nombre="Operador ficticio")
        cls.miembro = MembresiaFinanciador.objects.create(financiador=cls.org, usuario=cls.user, rol="operador")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.base = f"/api/financiadores/{self.org.pk}/"

    def preview(self, filas=None, fuente="base", clave=None):
        contenido = generar_xlsx(Lote("entrada", tuple(filas or [_persona(1, NUMERO="000001")])) )
        return self.client.post(self.base + "previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("ficticio.xlsx", contenido),
            "clave": str(clave or uuid4()), "fuente": fuente,
        }, format="multipart")

    def aplicar(self, lote):
        return self.client.post(self.base + "confirmar-importacion/", {"importacion": lote["id"]}, format="json")

    def corregir(self, lote, indice=0, **extra):
        fila = lote["filas"][indice]
        return self.client.post(self.base + "subsanar-ostel/", {
            "importacion": lote["id"], "fila": fila["fila"], "revision": fila["revision"],
            "datos": fila["datos"], "motivo": "Comprobación de documento ficticio", **extra,
        }, format="json")

    def test_parcial_reintento_y_cobertura_no_habilitada(self):
        r = self.preview([_persona(1, NUMERO="000001"), _persona(2, NUMERO="000002", CUIL="123")])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["resumen"]["valida"], r.data["resumen"]["revision"]), (1, 1))
        aplicada = self.aplicar(r.data)
        self.assertEqual(aplicada.status_code, 200, aplicada.data)
        self.assertEqual(aplicada.data["resumen"]["aplicada"], 1)
        obj = Afiliado.objects.get()
        self.assertFalse(obj.cobertura_habilitada)
        self.assertEqual(obj.numero_interno, "000001")
        self.assertEqual(obj.numero, "FIC185-0001-AAA")
        self.assertIsNone(obj.plan_id)
        self.aplicar(aplicada.data)
        self.assertEqual(Afiliado.objects.count(), 1)

    def test_conflictos_en_ambas_direcciones_y_omision(self):
        for filas in (
            [_persona(1, NUMERO="000001"), _persona(2, NUMERO="000001")],
            [_persona(1, NUMERO="000001"), _persona(1, NUMERO="000002")],
        ):
            with self.subTest(filas=filas):
                r = self.preview(filas)
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data["resumen"]["revision"], 2)
                res = self.corregir(r.data, indice=1, accion="omitir")
                self.assertEqual(res.status_code, 200, res.data)
                self.assertEqual((res.data["resumen"]["valida"], res.data["resumen"]["omitida"]), (1, 1))

    def test_subsanar_conserva_original_y_rechaza_revision_vieja(self):
        r = self.preview([_persona(1, NUMERO="000001", CUIL="123")]).data
        from .ostel_synthetic import _cuil
        d = {**r["filas"][0]["datos"], "cuil": _cuil("99018501")}
        res = self.corregir(r, datos=d)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["resumen"]["valida"], 1)
        self.assertEqual(res.data["filas"][0]["original"]["CUIL"], "123")
        self.assertEqual(len(res.data["filas"][0]["correcciones"]), 1)
        self.assertEqual(self.corregir(r, datos=d).status_code, 400)
        self.aplicar(res.data)
        self.assertEqual(self.corregir(res.data, datos=d).status_code, 400)

    def test_bajas_no_aplican_ni_se_fuerzan_mediante_correccion(self):
        r = self.preview(fuente="bajas").data
        self.assertEqual(r["resumen"]["valida"], 0)
        self.assertEqual(self.corregir(r).status_code, 400)
        self.aplicar(r)
        self.assertFalse(Afiliado.objects.exists())

    def test_nroafi_compartido_permitido_y_repeticion_archivo_idempotente(self):
        clave = uuid4()
        filas = [_persona(1, NUMERO="000001", NROAFI="FAMILIA"), _persona(2, NUMERO="000002", NROAFI="FAMILIA")]
        r = self.preview(filas, clave=clave)
        self.assertEqual(r.data["resumen"]["valida"], 2)
        # XLSX puede tener metadatos variables: reintento exacto se comprueba aparte.
        self.aplicar(r.data)
        self.assertEqual(Afiliado.objects.filter(numero="FAMILIA").count(), 2)
        segundo = self.preview(filas)
        self.aplicar(segundo.data)
        self.assertEqual(Afiliado.objects.count(), 2)

    def test_actualizacion_preserva_cobertura_plan_fechas_y_detecta_edicion(self):
        r = self.preview().data
        self.aplicar(r)
        obj = Afiliado.objects.get()
        obj.cobertura_habilitada = True
        obj.save(update_fields=["cobertura_habilitada"])
        r = self.preview().data
        obj.revision += 1
        obj.save(update_fields=["revision"])
        res = self.aplicar(r)
        self.assertEqual(res.data["resumen"]["revision"], 1)
        corregida = self.corregir(res.data, datos={**res.data["filas"][0]["datos"], "nombre": "PERSONA FICTICIA CAMBIADA"})
        self.assertEqual(corregida.status_code, 200, corregida.data)
        self.aplicar(corregida.data)
        obj.refresh_from_db()
        self.assertTrue(obj.cobertura_habilitada)
        self.assertEqual(obj.desde, timezone.localdate())
        self.assertEqual(obj.nombre, "PERSONA FICTICIA CAMBIADA")

    def test_diferencias_entre_fuentes_requieren_revision_explicita(self):
        self.aplicar(self.preview().data)
        r = self.preview([_persona(1, NUMERO="000001", APENOM="PERSONA FICTICIA OTRA FUENTE")]).data
        self.assertEqual(r["resumen"]["revision"], 1)
        self.aplicar(r)
        self.assertNotEqual(Afiliado.objects.get().nombre, "PERSONA FICTICIA OTRA FUENTE")
        self.assertEqual(r["filas"][0]["padron_actual"]["nombre"], "PERSONA FICTICIA OSTEL 0001")
        corregida = self.corregir(r)
        self.aplicar(corregida.data)
        self.assertEqual(Afiliado.objects.get().nombre, "PERSONA FICTICIA OTRA FUENTE")

    def test_dimension_declarada_no_expande_la_lectura(self):
        from zipfile import ZipFile, ZIP_DEFLATED
        import re
        original = generar_xlsx(Lote("entrada", (_persona(1, NUMERO="000001"),)))
        salida = BytesIO()
        with ZipFile(BytesIO(original)) as fuente, ZipFile(salida, "w", ZIP_DEFLATED) as destino:
            for nombre in fuente.namelist():
                contenido = fuente.read(nombre)
                if nombre.startswith("xl/worksheets/"):
                    contenido = re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:XFD1048576"', contenido)
                destino.writestr(nombre, contenido)
        r = self.client.post(self.base + "previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("ficticio.xlsx", salida.getvalue()),
            "clave": str(uuid4()), "fuente": "base"}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["resumen"]["total"], 1)

    def test_alta_manual_default_y_excepcion_sin_plan(self):
        for n, extra in ((1, {}), (2, {"cobertura_habilitada": False})):
            r = self.client.post(self.base + "padron/", {
                "numero": str(n), "documento": str(99018500 + n), "nombre": "PERSONA FICTICIA",
                "desde": timezone.localdate().isoformat(), **extra}, format="json")
            self.assertEqual(r.status_code, 201, r.data)
            self.assertEqual(r.data["cobertura_habilitada"], n == 1)

    def test_cambio_de_destino_exige_ver_nueva_identidad_aunque_revision_coincida(self):
        from .ostel_synthetic import _cuil
        for n in (1, 2):
            Afiliado.objects.create(financiador=self.org, documento=str(99018500 + n),
                numero=str(n), nombre=f"PERSONA FICTICIA EXISTENTE {n}", desde=timezone.localdate())
        r = self.preview().data
        destino = {**r["filas"][0]["datos"], "documento": "99018502", "cuil": _cuil("99018502")}
        nuevo = self.corregir(r, datos=destino)
        self.assertEqual(nuevo.status_code, 200, nuevo.data)
        fila = nuevo.data["filas"][0]
        self.assertEqual(fila["padron_actual"]["documento"], "99018502")
        self.assertFalse(fila["cambios_revisados"])
        self.aplicar(nuevo.data)
        self.assertEqual(Afiliado.objects.get(documento="99018502").nombre, "PERSONA FICTICIA EXISTENTE 2")

    def test_reintento_mismos_bytes_y_clave_recupera_lote(self):
        contenido = generar_xlsx(Lote("entrada", (_persona(1, NUMERO="000001"),)))
        clave = str(uuid4())
        def enviar():
            return self.client.post(self.base + "previsualizar-ostel/", {
                "archivo": SimpleUploadedFile("ficticio.xlsx", contenido), "clave": clave, "fuente": "base"}, format="multipart")
        a, b = enviar(), enviar()
        self.assertEqual(a.status_code, 200, a.data)
        self.assertEqual(b.status_code, 200, b.data)
        self.assertEqual(a.data["id"], b.data["id"])
        self.assertEqual(Importacion.objects.count(), 1)

    def test_auditor_y_otro_financiador_no_modifican_lotes(self):
        r = self.preview().data
        MembresiaFinanciador.objects.filter(pk=self.miembro.pk).update(rol="auditor")
        self.assertEqual(self.preview().status_code, 403)
        self.assertEqual(self.aplicar(r).status_code, 403)
        self.assertEqual(self.corregir(r).status_code, 403)
        MembresiaFinanciador.objects.filter(pk=self.miembro.pk).update(rol="operador")
        otro = Financiador.objects.create(nombre="Otro ficticio", tipo="obra_social")
        ajeno = Importacion.objects.create(financiador=otro, tipo="padron", version=3,
            clave=uuid4(), huella="a" * 64, creado_por=self.user)
        self.assertEqual(self.aplicar({"id": ajeno.pk}).status_code, 400)

    def test_exportacion_y_filtro_administrativo(self):
        r = self.preview([_persona(1, NUMERO="000001"), _persona(2, NUMERO="000002", CUIL="123")]).data
        self.aplicar(r)
        listado = self.client.get(self.base + "padron/", {"estado": "administrativas"})
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado.data["count"], 1)
        self.assertFalse(listado.data["results"][0]["vigente"])
        from .importaciones import descargar_rechazadas
        contenido = descargar_rechazadas(importacion=Importacion.objects.get(pk=r["id"]), usuario=self.user)
        libro = load_workbook(BytesIO(contenido), read_only=True)
        self.assertEqual(libro.active.max_row, 2)
        libro.close()
