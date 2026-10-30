"""Vínculo familiar conocido con clasificación pendiente, sin inferir derechos."""
from hashlib import sha256
from io import BytesIO
import json
from uuid import uuid4

from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from . import models as m
from .importaciones import aplicar_importacion, generar_plantilla, previsualizar_importacion
from .services import registrar_afiliado


class FamiliaPendienteTests(APITestCase):
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="Familias ficticias", tipo="obra_social")
        self.user = Usuario.objects.create_user("familias@example.invalid")
        m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="operador")
        self.titular = self.persona("RAIZ")
        self.familiar = self.persona("INTEGRANTE")
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.url = self.base + f"padron/{self.familiar.pk}/"
        self.client.force_authenticate(self.user)

    def persona(self, numero, org=None):
        return m.Afiliado.objects.create(
            financiador=org or self.org, numero=numero, documento=f"FICTICIO{numero}",
            nombre=f"Persona ficticia {numero}", desde=timezone.localdate(),
            cobertura_habilitada=False,
        )

    def editar(self, revision=1, **cambios):
        return self.client.patch(self.url, {
            "revision": revision, "motivo": "Vínculo ficticio confirmado", **cambios,
        }, format="json")

    def huella(self):
        tablas = (m.Afiliado, m.SaludPadron, m.HistorialAfiliacion, m.EventoCobertura)
        datos = [list(t.objects.order_by("pk").values()) for t in tablas]
        return sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()

    def test_vinculo_sin_clasificacion_se_conserva_en_familia_y_auditoria(self):
        respuesta = self.editar(titular=self.titular.pk, parentesco="")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual((respuesta.data["titular"], respuesta.data["parentesco"]), (self.titular.pk, ""))
        self.assertEqual(respuesta.data["revision"], 2)
        familia = self.client.get(self.url + "familia/").data
        self.assertEqual(familia["titular"]["id"], self.titular.pk)
        self.assertEqual({x["id"] for x in familia["integrantes"]}, {self.titular.pk, self.familiar.pk})
        self.assertEqual(next(x for x in familia["integrantes"] if x["id"] == self.familiar.pk)["parentesco"], "")
        historia = self.client.get(self.url + "historial/").data["results"]
        self.assertEqual(historia[0]["cambios"], {"titular_id": {"anterior": None, "nuevo": self.titular.pk}})
        self.familiar.refresh_from_db()
        self.assertFalse(self.familiar.cobertura_habilitada)
        self.assertIsNone(self.familiar.finalizado_en)
        self.assertIsNone(self.familiar.plan_id)
        self.assertFalse(m.SaludPadron.objects.exists())
        self.assertEqual(self.editar(revision=2, titular=self.titular.pk, parentesco="").data["revision"], 2)
        self.assertEqual(self.client.get(self.url + "historial/").data["count"], 1)

    def test_clasificacion_posterior_y_desvinculacion_explicita(self):
        self.assertEqual(self.editar(titular=self.titular.pk).status_code, 200)
        self.assertEqual(self.editar(revision=2, parentesco="hijo").status_code, 200)
        antes = self.huella()
        respuesta = self.editar(revision=3, titular=None)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Se requiere un titular para informar parentesco.", str(respuesta.data))
        self.assertEqual(self.huella(), antes)
        respuesta = self.editar(revision=3, parentesco="")
        self.assertEqual((respuesta.status_code, respuesta.data["titular"]), (200, self.titular.pk))
        respuesta = self.editar(revision=4, titular=None, parentesco="")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["titular"])
        familia = self.client.get(self.url + "familia/").data
        self.assertEqual([x["id"] for x in familia["integrantes"]], [self.familiar.pk])

    def test_rechazos_sin_cambios_y_revision_optimista(self):
        otra = m.Financiador.objects.create(nombre="Ajena ficticia", tipo="obra_social")
        ajeno = self.persona("AJENO", otra)
        for entrada in ({"titular": self.familiar.pk}, {"titular": ajeno.pk}, {"parentesco": "hijo"}):
            antes = self.huella()
            self.assertEqual(self.editar(**entrada).status_code, 400)
            self.assertEqual(self.huella(), antes)
        self.assertEqual(self.editar(titular=self.titular.pk).status_code, 200)
        antes = self.huella()
        self.assertEqual(self.editar(titular=None).status_code, 409)
        self.assertEqual(self.huella(), antes)
        self.url = self.base + f"padron/{self.titular.pk}/"
        for destino in (self.familiar, self.persona("OTRARAIZ")):
            antes = self.huella()
            self.assertEqual(self.editar(titular=destino.pk, parentesco="").status_code, 400)
            self.assertEqual(self.huella(), antes)

    def test_consulta_exportacion_y_escritor_legacy_conservan_vinculo(self):
        self.assertEqual(self.editar(titular=self.titular.pk).status_code, 200)
        self.familiar.refresh_from_db()
        registrar_afiliado(
            financiador=self.org, usuario=self.user, numero=self.familiar.numero,
            documento=self.familiar.documento, nombre="Nombre ficticio corregido",
            plan=None, desde=self.familiar.desde,
        )
        listado = self.client.get(self.base + "padron/", {"search": self.familiar.documento}).data["results"]
        self.assertEqual(len(listado), 1)
        self.assertEqual((listado[0]["titular"], listado[0]["parentesco"]), (self.titular.pk, ""))
        respuesta = self.client.get(self.base + "padron/exportar/", {
            "search": self.familiar.documento, "columnas": "nombre,numero,documento,titular_nombre,parentesco",
        })
        self.assertEqual(respuesta.status_code, 200)
        hoja = load_workbook(BytesIO(respuesta.content))["Padrón"]
        self.assertEqual(list(hoja.values)[1][-2:], (self.titular.nombre, None))
        self.assertFalse(m.SaludPadron.objects.exists())

    def lote_generico(self, filas):
        libro = load_workbook(BytesIO(generar_plantilla(
            financiador=self.org, usuario=self.user, tipo="padron", version=2,
        )))
        hoja = libro["Carga"]
        for datos in filas:
            hoja.append([datos.get(celda.value, "") for celda in hoja[1]])
        archivo = BytesIO()
        libro.save(archivo)
        return previsualizar_importacion(
            financiador=self.org, usuario=self.user, tipo="padron", archivo=archivo.getvalue(), clave=uuid4(),
        )

    def test_importacion_v2_relacion_pendiente_y_regresion_clasificacion_huerfana(self):
        datos = {"N.º de afiliado": "NUEVO", "Documento": "FICTICIONUEVO",
                 "Nombre y apellido": "Integrante ficticio nuevo", "Vigente desde": timezone.localdate().isoformat()}
        lote = self.lote_generico([{**datos, "titular_documento": self.titular.documento}])
        self.assertEqual(lote.resumen["valida"], 1, lote.filas)
        self.assertFalse(m.Afiliado.objects.filter(documento="FICTICIONUEVO").exists())
        aplicar_importacion(importacion=lote, usuario=self.user)
        self.assertEqual(lote.resumen["aplicada"], 1, lote.filas)
        familiar = m.Afiliado.objects.get(documento="FICTICIONUEVO")
        self.assertEqual((familiar.titular_id, familiar.parentesco), (self.titular.pk, ""))
        historia = familiar.historial.count()
        aplicar_importacion(importacion=lote, usuario=self.user)
        self.assertEqual(familiar.historial.count(), historia)
        # La omisión en v2 conserva la clasificación ya almacenada, no la borra.
        url = self.base + f"padron/{familiar.pk}/"
        self.assertEqual(self.client.patch(url, {
            "revision": familiar.revision, "motivo": "Clasificación ficticia", "parentesco": "hijo",
        }, format="json").status_code, 200)
        otro_lote = self.lote_generico([datos])
        aplicar_importacion(importacion=otro_lote, usuario=self.user)
        familiar.refresh_from_db()
        self.assertEqual((familiar.titular_id, familiar.parentesco), (self.titular.pk, "hijo"))
        rechazado = self.lote_generico([{**datos, "Documento": "FICTICIOHUERFANO", "parentesco": "hijo"}])
        self.assertEqual(rechazado.resumen["rechazada"], 1)
        aplicar_importacion(importacion=rechazado, usuario=self.user)
        self.assertFalse(m.Afiliado.objects.filter(documento="FICTICIOHUERFANO").exists())
