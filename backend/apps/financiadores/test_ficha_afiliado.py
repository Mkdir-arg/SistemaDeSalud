"""Ficha administrativa del afiliado, acotada al alcance existente del pagador."""
import csv
from io import StringIO
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.auditoria.models import AccesoClinico

from .cobertura import seleccionar_afiliacion
from .models import Afiliado, DistribucionCobro, EventoCobertura, Financiador, ReservaCobertura, SolicitudAutorizacion
from .test_autorizaciones import AutorizacionSetup
from .test_vigencias import VigenciasApiSetup


class FichaAfiliadoTests(VigenciasApiSetup, APITestCase):
    def ficha(self, **parametros):
        return self.client.get(self.base + "ficha-afiliado/", {"afiliado": self.afiliado.pk, **parametros})

    def test_prestaciones_de_dos_hospitales_y_auditoria_por_institucion(self):
        primera = self.reservar()
        caso, prestacion = self.otro_hospital()
        segunda = self.reservar(caso=caso, prestacion=prestacion)
        response = self.ficha()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual({fila["id"] for fila in response.data["results"]}, {primera.pk, segunda.pk})
        self.assertEqual(response.data["afiliado"]["plan_nombre"], self.plan.nombre)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        accesos = AccesoClinico.objects.filter(recurso="financiadores-ficha-afiliado")
        self.assertEqual(set(accesos.values_list("institucion_id", "tipo")), {
            (self.institucion.pk, AccesoClinico.Tipo.FINANCIADOR),
            (caso.institucion_id, AccesoClinico.Tipo.FINANCIADOR),
        })
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_afiliado", financiador=self.financiador).exists())

    def test_otro_financiador_es_404_y_no_audita_acceso(self):
        otro = Financiador.objects.create(nombre="Otra obra social", tipo="obra_social")
        ajeno = Afiliado.objects.create(financiador=otro, numero="2", documento="22222222", nombre="Otra persona", desde=self.hoy)
        for recurso in ("ficha-afiliado", "ficha-afiliado-autorizaciones"):
            response = self.client.get(self.base + recurso + "/", {"afiliado": ajeno.pk})
            self.assertEqual(response.status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())

    def test_sin_membresia_404_y_auditor_200(self):
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.ficha().status_code, 404)
        self.assertEqual(self.client.get("/api/financiadores/abc/ficha-afiliado/", {"afiliado": self.afiliado.pk}).status_code, 404)
        self.assertEqual(self.client.get("/api/financiadores/abc/ficha-afiliado-autorizaciones/", {"afiliado": self.afiliado.pk}).status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.ficha().status_code, 200)

    def test_convenio_cerrado_y_afiliacion_finalizada_solo_historico_pendiente(self):
        saldada = self.realizada()
        self.cobrar(DistribucionCobro.objects.get(reserva=saldada).obligacion_financiador)
        caso = self.nuevo_caso()
        seleccionar_afiliacion(caso=caso, usuario=self.admin, afiliado=self.afiliado, motivo="Atención pendiente")
        pendiente = self.reservar(caso=caso)
        self.cerrar()
        response = self.ficha()
        self.assertEqual([fila["id"] for fila in response.data["results"]], [pendiente.pk])
        self.assertEqual(response.data["results"][0]["acceso"], "pendiente_historico")
        self.finalizar()
        response = self.ficha()
        self.assertEqual([fila["id"] for fila in response.data["results"]], [pendiente.pk])
        self.assertEqual(response.data["afiliado"]["estado"], "finalizada")

    def test_ficha_vacia_audita_evento_sin_acceso_clinico(self):
        response = self.ficha()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        self.assertFalse(AccesoClinico.objects.exists())
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_afiliado").exists())

    def test_pagina_fuera_de_rango_no_audita_acceso_y_parametro_invalido_es_400(self):
        self.reservar()
        response = self.ficha(page=2, page_size=1)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())
        self.assertEqual(self.ficha(afiliado="texto").status_code, 400)

    def test_misma_persona_en_otro_financiador_no_amplia_alcance(self):
        reserva = self.reservar()
        otro = Financiador.objects.create(nombre="Financiador nuevo", tipo="mutual")
        ajeno = Afiliado.objects.create(financiador=otro, numero="OTRO", documento=self.afiliado.documento,
                                        nombre=self.afiliado.nombre, desde=self.hoy)
        # Simula una referencia antigua incongruente para comprobar el filtro de organización.
        ReservaCobertura.objects.filter(pk=reserva.pk).update(afiliado=ajeno)
        response = self.ficha()
        self.assertEqual(response.data["results"], [])
        self.assertFalse(AccesoClinico.objects.exists())

    def test_csv_acotado_y_actividad_conserva_recurso_y_nombre(self):
        reserva = self.reservar()
        otro = Afiliado.objects.create(financiador=self.financiador, numero="OTRO", documento="99999999",
                                       nombre="Otra persona", desde=self.hoy)
        caso = self.nuevo_caso()
        seleccionar_afiliacion(caso=caso, usuario=self.admin, afiliado=self.afiliado, motivo="Otra atención")
        ajena = self.reservar(caso=caso)
        ReservaCobertura.objects.filter(pk=ajena.pk).update(afiliado=otro)
        response = self.ficha(formato="csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ficha-afiliado-", response["Content-Disposition"])
        filas = list(csv.reader(StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([fila[0] for fila in filas[1:]], [str(reserva.pk)])
        self.assertEqual(AccesoClinico.objects.filter(recurso="financiadores-ficha-afiliado-csv").count(), 1)
        self.assertTrue(EventoCobertura.objects.filter(accion="exportar_ficha_afiliado").exists())
        actividad = self.client.get(self.base + "actividad/", {"formato": "csv"})
        self.assertIn("actividad-financiador-", actividad["Content-Disposition"])
        self.assertEqual(AccesoClinico.objects.filter(recurso="financiadores-actividad-csv").count(), 1)
        self.assertIn(str(ajena.pk), actividad.content.decode("utf-8-sig"))

    @override_settings(DEBUG=False)
    def test_csv_no_sale_si_falla_auditoria(self):
        self.reservar()
        self.client.raise_request_exception = False
        with patch("apps.auditoria.mixins.AccesoClinico.objects.bulk_create", side_effect=RuntimeError("Auditoría no disponible")):
            response = self.ficha(formato="csv")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("Content-Disposition", response)
        self.assertNotIn(self.afiliado.documento.encode(), response.content)
        self.assertFalse(EventoCobertura.objects.filter(accion="exportar_ficha_afiliado").exists())


class FichaAutorizacionesTests(AutorizacionSetup, APITestCase):
    def test_lista_minima_y_acceso_por_solicitud(self):
        solicitud = self.solicitud()
        self.client.force_authenticate(self.operador)
        url = f"/api/financiadores/{self.financiador.pk}/ficha-afiliado-autorizaciones/"
        response = self.client.get(url, {"afiliado": self.afiliado.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([fila["id"] for fila in response.data["results"]], [solicitud.pk])
        self.assertFalse({"justificacion", "evidencia", "motivo_resolucion", "historial"} & set(response.data["results"][0]))
        acceso = AccesoClinico.objects.get(recurso="financiadores-ficha-afiliado")
        self.assertEqual((acceso.tipo, acceso.institucion_id, acceso.objeto_id),
                         (AccesoClinico.Tipo.FINANCIADOR, self.institucion.pk, str(solicitud.pk)))
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_afiliado").exists())

    def test_solo_solicitudes_visibles_y_del_afiliado(self):
        solicitud = self.solicitud()
        otro = Afiliado.objects.create(financiador=self.financiador, numero="OTRO", documento="99999999",
                                       nombre="Otra persona", desde=self.hoy)
        self.client.force_authenticate(self.operador)
        url = f"/api/financiadores/{self.financiador.pk}/ficha-afiliado-autorizaciones/"
        self.assertEqual(self.client.get(url, {"afiliado": otro.pk}).data["results"], [])
        self.convenio.estado = "finalizado"
        self.convenio.cerrado_en = timezone.now()
        self.convenio.save(update_fields=["estado", "cerrado_en"])
        self.assertEqual([fila["id"] for fila in self.client.get(url, {"afiliado": self.afiliado.pk}).data["results"]], [solicitud.pk])
        SolicitudAutorizacion.objects.filter(pk=solicitud.pk).update(estado="rechazada")
        self.assertEqual(self.client.get(url, {"afiliado": self.afiliado.pk}).data["results"], [])
