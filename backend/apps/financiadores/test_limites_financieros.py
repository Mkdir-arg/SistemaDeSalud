"""Cobranza declarada y facturas documentales no ejecutan negocio financiero."""
from decimal import Decimal
from uuid import uuid4

from django.apps import apps
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Usuario
from apps.finanzas.dinero import registrar_movimiento
from apps.finanzas.models import MovimientoDinero, ObligacionFinanciera
from . import models as m
from .test_cobertura import CoberturaSetup


class LimitesFinancierosTests(CoberturaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.membresia.rol = "admin"
        self.membresia.acceso_padron_cobranza = True
        self.membresia.save()
        self.client.force_authenticate(self.operador)
        self.otra = m.Financiador.objects.create(nombre="Financiador ficticio B", tipo="otro")
        otro_usuario = Usuario.objects.create_user("finanzas-b@example.invalid", "x")
        m.MembresiaFinanciador.objects.create(
            financiador=self.otra, usuario=otro_usuario, rol="admin",
            acceso_padron_cobranza=True,
        )
        self.cliente_b = APIClient()
        self.cliente_b.force_authenticate(otro_usuario)
        self.plan_b = m.Plan.objects.create(financiador=self.otra, codigo="BASE", nombre="Plan ficticio B")
        self.afiliado_b = m.Afiliado.objects.create(
            financiador=self.otra, numero=self.afiliado.numero,
            documento=self.afiliado.documento, nombre="Persona ficticia B",
            desde=self.hoy, plan=self.plan_b, cobertura_habilitada=False,
        )
        self.convenio_b = m.Convenio.objects.create(
            financiador=self.otra, institucion=self.institucion,
            propuesto_por="financiador", creado_por=otro_usuario,
        )
        for org, cliente, afiliado in (
            (self.financiador, self.client, self.afiliado),
            (self.otra, self.cliente_b, self.afiliado_b),
        ):
            m.CobranzaPadron.objects.create(afiliado=afiliado)
            regla = dict(codigo="plazo-ficticio", version=1, fuente="Fuente ficticia",
                         regimen="dependencia", plan_id=None, desde="2030-01-01",
                         hasta=None, plazo_dias_corridos=7)
            respuesta = cliente.post(
                f"/api/financiadores/{org.pk}/borradores-derechos/",
                dict(propuesta=[regla], motivo="Caracterización ficticia",
                     regimen="dependencia", plan_id=None, fecha="2030-01-08"),
                format="json",
            )
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.reservar(acepta=True)
        self.atencion()
        self.assertEqual(
            sorted(ObligacionFinanciera.objects.values_list("importe_original", flat=True)),
            [Decimal("20.00"), Decimal("80.00")],
        )
        registrar_movimiento(
            obligacion=ObligacionFinanciera.objects.order_by("pk").first(),
            importe="5.00", fecha=self.hoy, clave=uuid4(), usuario=self.admin,
            aprobado=True, referencia="Movimiento completamente ficticio",
        )
        self.assertEqual(MovimientoDinero.objects.get().importe, Decimal("5.00"))
        self.assertEqual(m.BorradorReglaDerechos.objects.count(), 2)
        self.assertEqual(m.ReservaCobertura.objects.count(), 1)
        self.base = f"/api/financiadores/{self.financiador.pk}/"
        self.base_b = f"/api/financiadores/{self.otra.pk}/"
        self.factura = dict(
            direccion="recibida", contraparte_tipo="institucion", convenio=self.convenio.pk,
            tipo="factura", letra="A", numero="FICTICIA-001", fecha=str(self.hoy), importe="125.50",
        )
        respuesta = self.cliente_b.post(
            self.base_b + "facturas/", {**self.factura, "convenio": self.convenio_b.pk}, format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def instantanea(self):
        """Valores completos y ordenados: detecta altas, bajas y cambios sin variar conteos."""
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for aplicacion in ("finanzas", "financiadores")
            for modelo in apps.get_app_config(aplicacion).get_models()
        }

    def sin_otros_cambios(self, antes, permitidos=()):
        despues = self.instantanea()
        for tabla, filas in antes.items():
            if tabla not in permitidos:
                self.assertEqual(despues[tabla], filas, tabla)

    def evento_nuevo(self, antes, accion, objeto):
        previos = antes["financiadores.EventoCobertura"]
        ids = [fila["id"] for fila in previos]
        self.assertEqual(list(m.EventoCobertura.objects.filter(pk__in=ids).order_by("pk").values()), previos)
        self.assertEqual(
            list(m.EventoCobertura.objects.exclude(pk__in=ids).values_list("accion", "objeto", "financiador_id")),
            [(accion, str(objeto), self.financiador.pk)],
        )

    def alta_factura(self, **cambios):
        return self.client.post(self.base + "facturas/", {**self.factura, **cambios}, format="json")

    def test_cobranza_declarada_cambia_solo_bloque_e_historia_no_saldo_ni_derechos(self):
        antes = self.instantanea()
        respuesta = self.client.patch(
            self.base + f"padron/{self.afiliado.pk}/cobranza/",
            dict(revision=1, motivo="Caracterización ficticia", situacion="deuda",
                 fuente="Fuente ficticia", informado_en=str(self.hoy)), format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual((respuesta.data["situacion"], respuesta.data["revision"]), ("deuda", 2))
        bloque = m.CobranzaPadron.objects.get(afiliado=self.afiliado)
        self.assertEqual((bloque.situacion, bloque.fuente, bloque.informado_en, bloque.revision),
                         ("deuda", "Fuente ficticia", self.hoy, 2))
        filas = antes["financiadores.CobranzaPadron"]
        for fila in filas:
            if fila["afiliado_id"] == self.afiliado.pk:
                fila.update(situacion="deuda", fuente="Fuente ficticia", informado_en=self.hoy, revision=2)
        self.assertEqual(list(m.CobranzaPadron.objects.order_by("pk").values()), filas)
        historial = m.HistorialPadronProtegido.objects.get()
        self.assertEqual((historial.afiliado_id, historial.bloque, historial.revision),
                         (self.afiliado.pk, "cobranza", 2))
        self.evento_nuevo(antes, "editar_padron_protegido", self.afiliado.pk)
        self.sin_otros_cambios(antes, (
            "financiadores.CobranzaPadron", "financiadores.HistorialPadronProtegido",
            "financiadores.EventoCobertura",
        ))

    def test_factura_documental_alta_y_edicion_no_generan_obligacion_ni_cambian_cobertura(self):
        antes = self.instantanea()
        respuesta = self.alta_factura()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        pk = respuesta.data["id"]
        self.assertEqual(m.RegistroFactura.objects.get(pk=pk).importe, Decimal("125.50"))
        self.assertEqual(list(m.RegistroFactura.objects.exclude(pk=pk).order_by("pk").values()),
                         antes["financiadores.RegistroFactura"])
        self.evento_nuevo(antes, "crear_factura", pk)
        self.sin_otros_cambios(antes, ("financiadores.RegistroFactura", "financiadores.EventoCobertura"))
        antes = self.instantanea()
        respuesta = self.client.patch(self.base + f"facturas/{pk}/",
                                     {"concepto": "Concepto ficticio actualizado"}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["concepto"], "Concepto ficticio actualizado")
        actualizado = m.RegistroFactura.objects.get(pk=pk)
        filas = antes["financiadores.RegistroFactura"]
        for fila in filas:
            if fila["id"] == pk:
                fila.update(concepto="Concepto ficticio actualizado", actualizado=actualizado.actualizado)
        self.assertEqual(list(m.RegistroFactura.objects.order_by("pk").values()), filas)
        self.evento_nuevo(antes, "editar_factura", pk)
        self.sin_otros_cambios(antes, ("financiadores.RegistroFactura", "financiadores.EventoCobertura"))

    def test_duplicado_rechazado_conserva_documentos_historia_finanzas_y_derechos(self):
        self.assertEqual(self.alta_factura().status_code, 201)
        antes = self.instantanea()
        respuesta = self.alta_factura()
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("misma dirección", str(respuesta.data))
        self.sin_otros_cambios(antes)

    def test_acceso_y_vinculos_cruzados_rechazados_no_alteran_ningun_financiador(self):
        pk = self.alta_factura().data["id"]
        intentos = (
            (self.cliente_b, "get", self.base_b + f"facturas/{pk}/", None, 404),
            (self.cliente_b, "patch", self.base_b + f"facturas/{pk}/", {"concepto": "Cambio rechazado"}, 404),
            (self.client, "post", self.base + "facturas/", {**self.factura, "convenio": self.convenio_b.pk}, 400),
            (self.client, "post", self.base + "facturas/", {**self.factura, "contraparte_tipo": "afiliado",
                                                        "convenio": None, "afiliado": self.afiliado_b.pk}, 400),
            (self.cliente_b, "patch", self.base_b + f"padron/{self.afiliado.pk}/cobranza/",
             dict(revision=1, motivo="Cambio rechazado", situacion="deuda",
                  fuente="Fuente ficticia", informado_en=str(self.hoy)), 404),
        )
        for cliente, metodo, url, datos, codigo in intentos:
            with self.subTest(metodo=metodo, url=url):
                antes = self.instantanea()
                respuesta = getattr(cliente, metodo)(url, datos, format="json")
                self.assertEqual(respuesta.status_code, codigo, respuesta.data)
                self.sin_otros_cambios(antes)
