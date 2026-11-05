"""Convivencia de reglas no operativas y padrón familiar completamente ficticio."""
from hashlib import sha256
import json

from rest_framework.test import APITestCase

from . import models as m
from .test_familia_ostel import FamiliaOstelFixture


class DerechosPadronAislamientoTests(FamiliaOstelFixture, APITestCase):
    def setUp(self):
        super().setUp()
        self.importar()
        self.assertEqual(self.confirmar(self.proponer().data).status_code, 200)
        self.member.rol = "admin"
        self.member.save()
        self.reglas = self.base + "borradores-derechos/"
        self.regla = dict(codigo="plazo-ficticio", version=1, fuente="Fuente ficticia",
                          regimen="dependencia", plan_id=None, desde="2030-01-01",
                          hasta=None, plazo_dias_corridos=7)
        self.propuesta = dict(propuesta=[self.regla], motivo="Comprobación ficticia",
                              regimen="dependencia", plan_id=None, fecha="2030-01-08")
        self.simulacion = dict(regla={k: self.regla[k] for k in ("codigo", "version", "regimen", "plan_id")},
                               fecha="2030-01-08", referencia="2030-01-01", evidencia="REF-FICTICIA")

    def huella_padron(self, completa=False):
        modelos = (m.Afiliado, m.SaludPadron, m.HistorialAfiliacion, m.Importacion)
        if completa:
            modelos += (m.BorradorReglaDerechos, m.EventoCobertura,
                        m.Financiador, m.Plan, m.MembresiaFinanciador)
        datos = [list(modelo.objects.order_by("pk").values()) for modelo in modelos]
        return sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()

    def test_preview_guardado_y_simulacion_conservan_familia_revision_y_lote(self):
        familia = self.proponer().json()
        self.familiar.refresh_from_db()
        self.assertIsNotNone(self.familiar.titular_id)
        self.assertFalse(self.familiar.cobertura_habilitada)
        padron = self.huella_padron()
        completa = self.huella_padron(completa=True)
        vista = self.client.post(self.reglas + "previsualizar/", self.propuesta, format="json")
        self.assertEqual(vista.status_code, 200)
        self.assertEqual(vista.json()["nuevas"], [self.regla])
        self.assertEqual(self.huella_padron(completa=True), completa)

        eventos = list(m.EventoCobertura.objects.order_by("pk").values())
        ids_previos = [evento["id"] for evento in eventos]
        guardado = self.client.post(self.reglas, self.propuesta, format="json")
        self.assertEqual(guardado.status_code, 200)
        self.assertEqual(guardado.json(), vista.json())
        self.assertEqual(self.huella_padron(), padron)
        self.assertEqual(list(m.EventoCobertura.objects.filter(pk__in=ids_previos).order_by("pk").values()), eventos)
        nuevos = list(m.EventoCobertura.objects.exclude(pk__in=ids_previos).values_list("accion", flat=True))
        self.assertEqual(nuevos, ["crear_borrador_derechos"])
        self.assertEqual(m.BorradorReglaDerechos.objects.count(), 1)

        for rol in ("admin", "operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            for alternativa, dias, limite in (({}, 7, "2030-01-08"), ({"dias_corridos": 0}, 0, "2030-01-01")):
                completa = self.huella_padron(completa=True)
                r = self.client.post(self.reglas + "simular-plazo/", self.simulacion | alternativa, format="json")
                self.assertEqual(r.status_code, 200)
                self.assertEqual((r.json()["dias_corridos"], r.json()["limite"]), (dias, limite))
                self.assertEqual(self.huella_padron(completa=True), completa)
        self.member.rol = "admin"
        self.member.save()
        self.assertEqual(self.proponer().json(), familia)
        self.assertEqual(self.huella_padron(), padron)

    def test_rechazos_de_reglas_no_alteran_padron_ni_su_evidencia(self):
        for sufijo in ("", "previsualizar/"):
            antes = self.huella_padron(completa=True)
            r = self.client.post(self.reglas + sufijo, self.propuesta | {"activar": True}, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(self.huella_padron(completa=True), antes)
        for rol in ("operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = self.huella_padron(completa=True)
            for sufijo in ("", "previsualizar/"):
                r = self.client.post(self.reglas + sufijo, self.propuesta, format="json")
                self.assertEqual(r.status_code, 403)
                self.assertEqual(self.huella_padron(completa=True), antes)
        self.assertEqual(m.BorradorReglaDerechos.objects.count(), 0)
