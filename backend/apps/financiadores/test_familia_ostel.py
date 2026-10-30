"""Familias desde evidencia aplicada OSTEL; todas las personas son ficticias."""
from hashlib import sha256
from uuid import uuid4
import json

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from . import models as m
from .ostel_synthetic import COLUMNAS, Lote, generar_xlsx, _persona


class FamiliaOstelFixture:
    def setUp(self):
        self.org = m.Financiador.objects.create(nombre="Familias OSTEL ficticias", tipo="obra_social")
        self.user = Usuario.objects.create_user("familia-ostel@example.invalid")
        self.member = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="operador")
        self.client.force_authenticate(self.user)
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.raiz = dict(zip(COLUMNAS, _persona(1)))

    def importar(self, intermedias=(), raiz_primero=False):
        integrante = _persona(2, NUMERO="000002", CUILTIT=self.raiz["CUIL"], NROAFI=self.raiz["NROAFI"])
        raiz = _persona(1, NUMERO="000001", CUILTIT=self.raiz["CUIL"])
        filas = (raiz, *intermedias, integrante) if raiz_primero else (integrante, *intermedias, raiz)
        archivo = generar_xlsx(Lote("familia", filas))
        respuesta = self.client.post(self.base + "previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("familia-ficticia.xlsx", archivo),
            "clave": str(uuid4()), "fuente": "base", "cobertura_habilitada": False,
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.lote = m.Importacion.objects.get(pk=respuesta.data["id"])
        self.aplicar_padron()
        self.familiar = m.Afiliado.objects.get(cuil=dict(zip(COLUMNAS, integrante))["CUIL"])
        self.url = self.base + f"padron/{self.familiar.pk}/familia-ostel/"
        self.fuente = {"importacion": self.lote.pk, "fila": len(filas) if raiz_primero else 1}

    def aplicar_padron(self):
        respuesta = self.client.post(self.base + "confirmar-importacion/", {"importacion": self.lote.pk}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.lote.refresh_from_db()
        self.assertGreater(self.lote.resumen["aplicada"], 0, [f["errores"] for f in self.lote.filas])

    def huella(self):
        tablas = (m.Afiliado, m.SaludPadron, m.HistorialAfiliacion, m.Importacion, m.EventoCobertura)
        datos = [list(t.objects.order_by("pk").values()) for t in tablas]
        return sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()

    def proponer(self):
        return self.client.get(self.url, self.fuente)

    def confirmar(self, propuesta):
        return self.client.post(self.url, {**self.fuente, **propuesta}, format="json")


class FamiliaOstelTests(FamiliaOstelFixture, APITestCase):
    def test_orden_invertido_propuesta_inocua_y_confirmacion_auditada(self):
        self.importar()
        antes = self.huella()
        propuesta = self.proponer()
        self.assertEqual(propuesta.status_code, 200, getattr(propuesta, "data", None))
        self.assertEqual(self.huella(), antes)

        titular = m.Afiliado.objects.get(cuil=self.raiz["CUIL"])
        self.assertEqual(propuesta.data, {"titular": titular.pk, "revision": self.familiar.revision,
                                         "revision_titular": titular.revision})
        original = m.Importacion.objects.values().get(pk=self.lote.pk)
        respuesta = self.confirmar(propuesta.data)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual((respuesta.data["titular"], respuesta.data["parentesco"]), (titular.pk, ""))
        self.assertFalse(respuesta.data["cobertura_habilitada"])
        self.assertFalse(m.SaludPadron.objects.exists())
        self.assertEqual(m.Importacion.objects.values().get(pk=self.lote.pk), original)
        historia = m.HistorialAfiliacion.objects.filter(afiliado=self.familiar).latest("pk")
        self.assertEqual(historia.lote_id, self.lote.pk)
        self.assertEqual(historia.cambios, {"titular_id": {"anterior": None, "nuevo": titular.pk}})
        antes = self.huella()
        self.assertEqual(self.confirmar(self.proponer().data).status_code, 200)
        self.assertEqual(self.huella(), antes)

    def test_titular_primero_tambien_resuelve_sin_clasificar(self):
        self.importar(raiz_primero=True)
        respuesta = self.confirmar(self.proponer().data)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["parentesco"], "")
        self.assertEqual(respuesta.data["titular"], m.Afiliado.objects.get(cuil=self.raiz["CUIL"]).pk)

    def test_titular_fuera_de_la_primera_tanda_requiere_aplicacion_no_inferencia(self):
        self.importar(tuple(_persona(n, NUMERO=str(n)) for n in range(3, 102)))
        antes = self.huella()
        self.assertEqual(self.proponer().status_code, 400)
        self.assertEqual(self.huella(), antes)
        self.aplicar_padron()
        self.assertEqual(self.confirmar(self.proponer().data).status_code, 200)

    def test_revisiones_esperadas_y_campos_explicitos(self):
        self.importar()
        propuesta = self.proponer().data
        for cambios, estado in (({"revision": 1}, 409), ({"revision_titular": 1}, 409),
                                ({"titular": self.familiar.pk}, 400), ({"parentesco": "otro"}, 400),
                                ({"revision": None}, 400)):
            antes = self.huella()
            self.assertEqual(self.confirmar({**propuesta, **cambios}).status_code, estado)
            self.assertEqual(self.huella(), antes)
        self.member.rol = "auditor"
        self.member.save()
        antes = self.huella()
        self.assertEqual(self.proponer().status_code, 200)
        self.assertEqual(self.confirmar(propuesta).status_code, 403)
        self.assertEqual(self.huella(), antes)

    def test_fuentes_incompletas_ambiguas_ciclicas_o_discordantes_se_detienen(self):
        self.importar()
        propuesta = self.proponer().data
        originales = json.loads(json.dumps(self.lote.filas))
        variantes = []
        for campo, valor in (("CUILTIT", ""), ("CUILTIT", "123"), ("CUIL", self.raiz["CUIL"])):
            filas = json.loads(json.dumps(originales))
            filas[0]["original"][campo] = valor
            variantes.append(filas)
        ciclo = json.loads(json.dumps(originales))
        ciclo[1]["original"]["CUILTIT"] = self.familiar.cuil
        variantes.extend([ciclo, [originales[0]], originales + [{**originales[1], "fila": 3}]])
        for indice in (0, 1):
            filas = json.loads(json.dumps(originales))
            filas[indice]["estado"] = "revision"
            variantes.append(filas)
        for filas in variantes:
            self.lote.filas = filas
            self.lote.save(update_fields=["filas"])
            antes = self.huella()
            self.assertEqual(self.proponer().status_code, 400)
            self.assertEqual(self.confirmar(propuesta).status_code, 400)
            self.assertEqual(self.huella(), antes)

    def test_identidad_actual_y_otro_vinculo_no_se_sobrescriben(self):
        self.importar()
        propuesta = self.proponer().data
        self.familiar.numero_interno = "CAMBIO-FICTICIO"
        self.familiar.save(update_fields=["numero_interno"])
        antes = self.huella()
        self.assertEqual(self.confirmar(propuesta).status_code, 400)
        self.assertEqual(self.huella(), antes)
        self.familiar.numero_interno = self.lote.filas[0]["datos"]["numero_interno"]
        otro = m.Afiliado.objects.create(financiador=self.org, numero="OTRO", documento="FICTICIOOTRO",
                                       nombre="Otro titular ficticio", desde=self.familiar.desde)
        self.familiar.titular = otro
        self.familiar.parentesco = "hijo"
        self.familiar.save()
        antes = self.huella()
        self.assertEqual(self.confirmar(propuesta).status_code, 400)
        self.assertEqual(self.huella(), antes)
        self.familiar.titular = m.Afiliado.objects.get(cuil=self.raiz["CUIL"])
        self.familiar.save()
        self.assertEqual(self.confirmar(self.proponer().data).data["parentesco"], "hijo")

    def test_lote_y_referencias_ajenas_no_se_utilizan(self):
        self.importar()
        propuesta = self.proponer().data
        otra = m.Financiador.objects.create(nombre="Otra ficticia", tipo="obra_social")
        self.lote.financiador = otra
        self.lote.save(update_fields=["financiador"])
        antes = self.huella()
        self.assertEqual(self.proponer().status_code, 404)
        self.assertEqual(self.confirmar(propuesta).status_code, 404)
        self.assertEqual(self.huella(), antes)

    def test_bajas_finalizacion_y_cuerpo_malformado_no_mutan(self):
        self.importar()
        propuesta = self.proponer().data
        for pk in (self.familiar.pk, propuesta["titular"]):
            obj = m.Afiliado.objects.get(pk=pk)
            for campo, valor in (("baja_efectiva", timezone.localdate()), ("finalizado_en", timezone.now())):
                setattr(obj, campo, valor)
                obj.save(update_fields=[campo])
                antes = self.huella()
                self.assertEqual(self.proponer().status_code, 400)
                self.assertEqual(self.confirmar(propuesta).status_code, 400)
                self.assertEqual(self.huella(), antes)
                setattr(obj, campo, None)
                obj.save(update_fields=[campo])
        antes = self.huella()
        self.assertEqual(self.client.post(self.url, [], format="json").status_code, 400)
        self.assertEqual(self.huella(), antes)
