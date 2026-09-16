"""Recuperación por HTTP: origen inmutable y permisos de la misma área/acción."""
from decimal import Decimal
from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.finanzas.models import ConcesionFinanciera, ObligacionFinanciera, Prestacion
from apps.finanzas.models_cobros import PendienteCobro, SnapshotCobroAtencion
from apps.flujos.models import Nodo
from apps.instituciones.models import Area

from .cobertura import seleccionar_afiliacion
from .models import AfiliacionCaso, DistribucionCobro, ReservaCobertura, RevisionContexto
from .test_cobertura import CoberturaSetup


class RecuperacionCoberturaApiTests(CoberturaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def contexto_fallido(self):
        with patch("apps.financiadores.cobros.contexto_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.assertTrue(hecho.cobertura_contexto.get("pendiente"))
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        return hecho

    def revision(self, hecho, **datos):
        payload = {"hecho": hecho.pk, "motivo": "Documentación original revisada",
                   "afiliacion": self.seleccion.pk, "prestaciones": [self.prestacion.pk]}
        payload.update(datos)
        return self.client.post("/api/coberturas/revisar-contexto/", payload, format="json")

    def permiso_financiero(self, usuario, accion, *, area=None, sensible=False):
        membresia, _ = Membresia.objects.get_or_create(
            usuario=usuario, institucion=self.institucion, rol="reportes",
        )
        permiso = ConcesionFinanciera.objects.create(
            membresia=membresia, accion=accion, todas_las_areas=area is None,
            permite_sensibles=sensible,
        )
        if area:
            permiso.areas.add(area)
        return permiso

    def recuperables(self):
        return self.client.get(f"/api/coberturas/recuperables/?institucion={self.institucion.pk}")

    def reservas(self):
        return self.client.get(f"/api/coberturas/?institucion={self.institucion.pk}")

    def test_completar_arancel_por_http_conserva_original_y_no_acepta_deuda_paciente(self):
        self.politica(importe=None)
        hecho = self.atencion()
        reserva = ReservaCobertura.objects.get(hecho=hecho)
        original = reserva.evaluacion.copy()
        response = self.client.post(f"/api/coberturas/{reserva.pk}/completar/", {
            "motivo": "Se comprobó el arancel pactado", "arancel": "100.00",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["evaluacion"]["evaluacion_original"], original)
        self.assertEqual(response.data["distribucion"]["importe_financiador"], "80.00")
        self.assertEqual(response.data["distribucion"]["importe_paciente"], "20.00")
        self.assertIsNone(response.data["distribucion"]["obligacion_paciente"])
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)

    def test_revisar_contexto_recupera_una_vez_sin_sobrescribir_origen(self):
        hecho = self.contexto_fallido()
        contexto_original = hecho.cobertura_contexto.copy()
        pendientes = self.recuperables()
        self.assertEqual(pendientes.status_code, 200, pendientes.data)
        self.assertEqual([item["id"] for item in pendientes.data], [hecho.pk])
        self.assertTrue(pendientes.data[0]["contexto_pendiente"])
        self.assertIn(self.seleccion.pk, [a["id"] for a in pendientes.data[0]["afiliaciones"]])
        response = self.client.post("/api/coberturas/recuperar/", {"hecho": hecho.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        response = self.revision(hecho)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["capturado"])
        self.assertEqual(self.revision(hecho).status_code, 200)
        hecho.refresh_from_db()
        self.assertEqual(hecho.cobertura_contexto, contexto_original)
        revision = RevisionContexto.objects.get(hecho=hecho)
        self.assertEqual(revision.contexto["afiliacion"], self.seleccion.pk)
        self.assertEqual(revision.registrado_por_id, self.admin.pk)
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)
        self.assertEqual(self.recuperables().data, [])
        self.assertFalse(PendienteCobro.objects.exists())

    def test_sin_seleccion_previa_revision_null_deja_afiliacion_pendiente_completable(self):
        self.caso = Caso.objects.create(institucion=self.institucion, version=self.nodo.version,
                                       ciudadano=self.paciente, area_actual=self.area)
        hecho = self.contexto_fallido()
        contexto_original = hecho.cobertura_contexto.copy()
        self.assertEqual(self.recuperables().data[0]["afiliaciones"], [])
        response = self.revision(hecho, afiliacion=None)
        self.assertEqual(response.status_code, 200, response.data)
        reserva = ReservaCobertura.objects.get(hecho=hecho)
        self.assertEqual(reserva.distribucion.estado, "evaluacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())
        response = self.client.post(f"/api/coberturas/{reserva.pk}/completar/", {
            "motivo": "Afiliación verificada posteriormente", "afiliado": self.afiliado.pk,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["distribucion"]["importe_financiador"], "80.00")
        self.assertIsNone(response.data["distribucion"]["obligacion_paciente"])
        hecho.refresh_from_db()
        self.assertEqual(hecho.cobertura_contexto, contexto_original)
        self.assertFalse(AfiliacionCaso.objects.filter(caso=self.caso, hecho_revision=None).exists())

    def test_revision_rechaza_prestacion_de_otro_hospital(self):
        hecho = self.contexto_fallido()
        _, prestacion = self.otro_hospital()
        response = self.revision(hecho, prestaciones=[prestacion.pk])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(RevisionContexto.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_revision_rechaza_prestacion_de_otro_nodo_del_mismo_hospital(self):
        hecho = self.contexto_fallido()
        nodo = Nodo.objects.create(version=self.nodo.version, tipo=Nodo.Tipo.ATENCION, titulo="Otra atención")
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=nodo, codigo="OTRA", nombre="Otra")
        response = self.revision(hecho, prestaciones=[prestacion.pk])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(RevisionContexto.objects.exists())

    def test_revision_no_reemplaza_afiliacion_por_una_creada_despues_del_hecho(self):
        hecho = self.contexto_fallido()
        posterior = seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                                           particular=True, motivo="Cambio posterior de cobertura")
        response = self.revision(hecho, afiliacion=posterior.pk)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(RevisionContexto.objects.exists())

    def test_revision_ya_capturada_rechaza_cambiar_la_seleccion(self):
        hecho = self.contexto_fallido()
        self.assertEqual(self.revision(hecho).status_code, 200)
        response = self.revision(hecho, afiliacion=None)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(RevisionContexto.objects.count(), 1)
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)

    def test_recuperar_captura_normal_por_http_preserva_snapshot_e_importe(self):
        self.reservar(acepta=True)
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.politica(importe=Decimal("300"))
        response = self.client.post("/api/coberturas/recuperar/", {"hecho": hecho.pk}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["capturado"])
        distribucion = DistribucionCobro.objects.get(reserva__hecho=hecho)
        self.assertEqual(distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertEqual(distribucion.obligacion_financiador.importe_original, Decimal("80"))

    def test_recuperables_y_revision_exigen_permiso_sensible_del_area_original(self):
        hecho = self.contexto_fallido()
        destino = Area.objects.create(institucion=self.institucion, nombre="Destino")
        self.caso.area_actual = destino
        self.caso.save(update_fields=["area_actual"])
        permiso = self.permiso_financiero(self.usuario, "resolver_cobertura", area=self.area)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.recuperables().data, [])
        self.assertEqual(self.revision(hecho).status_code, 403)
        permiso.permite_sensibles = True
        permiso.save(update_fields=["permite_sensibles"])
        self.assertEqual([h["id"] for h in self.recuperables().data], [hecho.pk])
        response = self.revision(hecho)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(RevisionContexto.objects.get(hecho=hecho).registrado_por_id, self.usuario.pk)

    def test_saldo_trasladado_se_completa_por_finanzas_del_area_de_origen(self):
        self.politica(importe=None)
        hecho = self.atencion()
        reserva = ReservaCobertura.objects.get(hecho=hecho)
        destino = Area.objects.create(institucion=self.institucion, nombre="Destino")
        self.caso.area_actual = destino
        self.caso.save(update_fields=["area_actual"])
        ajeno = Usuario.objects.create_user("finanzas-destino@example.test", "x")
        self.permiso_financiero(ajeno, "resolver_cobertura", area=destino)
        self.client.force_authenticate(ajeno)
        self.assertEqual(self.reservas().data["results"], [])
        payload = {"motivo": "Arancel verificado", "arancel": "100.00"}
        self.assertEqual(self.client.post(f"/api/coberturas/{reserva.pk}/completar/", payload, format="json").status_code, 404)
        self.permiso_financiero(self.usuario, "resolver_cobertura", area=self.area)
        self.permiso_financiero(self.usuario, "configurar_cobros")
        self.client.force_authenticate(self.usuario)
        self.assertEqual([r["id"] for r in self.reservas().data["results"]], [reserva.pk])
        response = self.client.post(f"/api/coberturas/{reserva.pk}/completar/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["evaluacion"]["revision"]["usuario"], self.usuario.pk)

    def test_rol_de_lectura_no_amplia_la_exposicion_clinica_a_otra_area(self):
        reserva = self.reservar()
        medico = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="medico")
        medico.areas.add(self.area)
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="reportes")
        destino = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        self.caso.area_actual = destino
        self.caso.save(update_fields=["area_actual"])
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.reservas().data["results"], [])
        opciones = self.client.get(f"/api/coberturas/opciones/?institucion={self.institucion.pk}")
        self.assertEqual(opciones.status_code, 200, opciones.data)
        self.assertEqual(opciones.data["casos"], [])
        response = self.client.post("/api/coberturas/evaluar/", {
            "caso": self.caso.pk, "prestacion": self.prestacion.pk,
            "fecha": str(self.hoy), "cantidad": 1,
        }, format="json")
        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(self.client.post(f"/api/coberturas/{reserva.pk}/liberar/", {
            "motivo": "Intento de otra área", "no_realizada": True,
        }, format="json").status_code, 404)

    def test_financiador_no_consulta_ni_revisa_contexto_hospitalario(self):
        hecho = self.contexto_fallido()
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.recuperables().data, [])
        self.assertEqual(self.revision(hecho).status_code, 403)
        self.assertFalse(RevisionContexto.objects.exists())
