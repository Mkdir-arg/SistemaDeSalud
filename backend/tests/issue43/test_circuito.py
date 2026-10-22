"""Brecha de integración: dinero tras observar, reenviar y aprobar por HTTP real."""
from decimal import Decimal
from uuid import uuid4

from django.db import connection
from rest_framework.test import APITestCase

from apps.financiadores import models as m
from apps.financiadores.test_esperas import EsperaSetup
from apps.finanzas.models import ConcesionFinanciera, HechoAtencionCosteable, MovimientoDinero, ObligacionFinanciera
from apps.flujos.models import Conexion, Nodo


class CircuitoIntegralTests(EsperaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(connection.vendor, "postgresql", "#43 requiere PostgreSQL real")
        final = Nodo.objects.create(version=self.caso.version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.caso.version, origen=self.nodo, destino=final)
        for accion in ("registrar_aceptacion", "ver_dinero", "registrar_dinero", "aprobar_dinero"):
            ConcesionFinanciera.objects.create(membresia=self.miembro_hospital, accion=accion, todas_las_areas=True)

    def post(self, usuario, url, datos, esperado=200):
        self.client.force_authenticate(usuario)
        respuesta = self.client.post(url, datos, format="json")
        self.assertEqual(respuesta.status_code, esperado, respuesta.data)
        return respuesta.data

    def test_observacion_reenvio_realizacion_cobro_y_reintento_persisten(self):
        self.client.force_authenticate(self.usuario)
        intento = self.client.get(self.url + "contexto/", {"caso": self.caso.pk}).data["intento"]
        solicitud = self.post(self.usuario, self.url, {
            "caso": self.caso.pk, "prestacion": self.prestacion.pk, "intento": intento,
            "cantidad": 1, "justificacion": "Orden ficticia #43", "clave": str(uuid4()),
        }, 201)
        base = f"{self.url}{solicitud['id']}/"
        self.post(self.operador, base + f"resolver/?financiador={self.financiador.pk}", {
            "revision": 1, "decision": "observar", "motivo": "Aclarar orden", "clave": str(uuid4()),
        })
        self.post(self.usuario, base + f"reenviar/?institucion={self.institucion.pk}", {
            "revision": 2, "justificacion": "Orden aclarada", "clave": str(uuid4()),
        })
        self.post(self.operador, base + f"resolver/?financiador={self.financiador.pk}", {
            **self.aprobacion(revision=3, cantidad_aprobada=1),
        })
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.client.force_authenticate(self.usuario)
        api_caso = f"/api/casos/{self.caso.pk}/"
        contexto = self.client.get(api_caso + "cobertura/").data["contexto"]
        cotizacion = self.post(self.usuario, api_caso + "cobertura-evaluar/", {
            "contexto": contexto, "prestacion": self.prestacion.pk,
        })
        self.assertEqual(cotizacion["importe_paciente"], "20.00")
        payload = {"contexto": contexto, "prestacion": self.prestacion.pk,
                   "firma": cotizacion["firma"], "acepta": True, "clave": str(uuid4())}
        reserva = self.post(self.usuario, api_caso + "cobertura-confirmar/", payload, 201)
        self.assertEqual(self.post(self.usuario, api_caso + "cobertura-confirmar/", payload, 201)["id"], reserva["id"])
        self.post(self.usuario, api_caso + "avanzar/", {"titulo": "Atención ficticia", "contenido": "Realizada", "firmada": False})
        distribucion = m.DistribucionCobro.objects.get(reserva_id=reserva["id"])
        self.assertEqual(distribucion.obligacion_financiador.importe_original, Decimal("80"))
        self.assertEqual(distribucion.obligacion_paciente.importe_original, Decimal("20"))
        url = f"/api/obligaciones-financieras/{distribucion.obligacion_financiador_id}/movimientos/"
        pago = {"importe": "80.00", "fecha": str(self.hoy), "aprobado": True, "clave": str(uuid4())}
        self.post(self.usuario, url, pago, 201)
        self.post(self.usuario, url, pago, 201)
        self.assertEqual(HechoAtencionCosteable.objects.count(), 1)
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)
        self.assertEqual(MovimientoDinero.objects.count(), 1)
        self.assertEqual(MovimientoDinero.objects.get().importe, Decimal("80"))
        self.assertEqual(m.UsoAutorizacion.objects.get().estado, "consumido")
