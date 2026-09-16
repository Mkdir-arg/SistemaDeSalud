"""Cobertura en el circuito clínico: importes explícitos y ámbito del caso real."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core import signing
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, LegajoProfesional
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera, Prestacion
from apps.flujos.models import Conexion, Nodo, VersionFlujo
from apps.instituciones.models import Area, Grupo
from apps.registros.models import EntradaHistoria

from . import models as m
from .cobertura import cantidades_periodo, periodo, seleccionar_afiliacion
from .test_cobertura import CoberturaSetup


class CoberturaClinicaTests(CoberturaSetup, TestCase):
    def setUp(self):
        super().setUp()
        self.caso.refresh_from_db()
        self.caso.nodo_actual = self.nodo
        self.caso.estado = Caso.Estado.EN_EVALUACION
        self.caso.save()
        self.membresia_hospital = Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol="medico",
        )
        self.membresia_hospital.areas.add(self.area)
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)
        self.base = f"/api/casos/{self.caso.pk}/"

    def resumen(self):
        response = self.client.get(self.base + "cobertura/")
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def cotizar(self, **cambios):
        payload = {"contexto": self.resumen()["contexto"], "prestacion": self.prestacion.pk}
        payload.update(cambios)
        return self.client.post(self.base + "cobertura-evaluar/", payload, format="json")

    def solicitud(self, *, acepta=False, **cambios):
        contexto = self.resumen()["contexto"]
        response = self.cotizar(contexto=contexto)
        self.assertEqual(response.status_code, 200, response.data)
        return {"contexto": contexto, "prestacion": self.prestacion.pk,
                "firma": response.data["firma"], "clave": str(uuid4()), "acepta": acepta, **cambios}

    def confirmar(self, payload=None, **cambios):
        payload = payload if payload is not None else self.solicitud(**cambios)
        return self.client.post(self.base + "cobertura-confirmar/", payload, format="json")

    def seleccionar(self, **cambios):
        payload = {"contexto": self.resumen()["contexto"], "particular": True,
                   "motivo": "Corrección documentada en admisión"}
        payload.update(cambios)
        return self.client.post(self.base + "cobertura-afiliacion/", payload, format="json")

    def avanzar(self):
        fin = Nodo.objects.create(version=self.nodo.version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.nodo.version, origen=self.nodo, destino=fin)
        return self.client.post(self.base + "avanzar/", {
            "titulo": "Consulta realizada", "contenido": "Atención registrada", "firmada": False,
        }, format="json")

    def test_consultar_y_evaluar_no_reservan_no_consumen_ni_generan_deuda(self):
        contexto = self.resumen()["contexto"]
        eventos = EventoCaso.objects.filter(caso=self.caso).count()
        for _ in range(2):
            response = self.cotizar()
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["importe_total"], "100.00")
            self.assertEqual(response.data["importe_paciente"], "20.00")
            self.assertEqual(response.data["disponibles"], 6)
            self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.resumen()["contexto"], contexto)
        self.assertEqual(EventoCaso.objects.filter(caso=self.caso).count(), eventos)
        self.assertFalse(m.ReservaCobertura.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertTrue(AccesoClinico.objects.filter(
            usuario=self.usuario, ciudadano=self.paciente, recurso="AfiliacionCaso",
        ).exists())

    def test_candidatos_se_derivan_del_paciente_no_del_documento_en_querystring(self):
        ajeno = m.Afiliado.objects.create(financiador=self.financiador, plan=self.plan,
            numero="AJENO", documento="99888777", nombre="Otra persona", desde=self.hoy)
        response = self.client.get(self.base + f"cobertura/?documento={ajeno.documento}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([a["id"] for a in response.data["afiliados"]], [self.afiliado.pk])
        response = self.seleccionar(particular=False, afiliado=ajeno.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(m.AfiliacionCaso.objects.filter(caso=self.caso).count(), 1)

    def test_financiador_no_puede_consultar_caso_ni_historia_hospitalaria(self):
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(self.base + "cobertura/").status_code, 404)
        self.assertIn(self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/").status_code, (403, 404))
        self.assertEqual(self.client.post(self.base + "cobertura-afiliacion/", {}, format="json").status_code, 404)

    def test_otro_hospital_no_es_consultable_ni_operable_por_url_directa(self):
        ajeno, _ = self.otro_hospital()
        url = f"/api/casos/{ajeno.pk}/"
        self.assertEqual(self.client.get(url + "cobertura/").status_code, 404)
        self.assertIn(self.client.post(url + "cobertura-evaluar/", {}, format="json").status_code, (403, 404))
        self.assertIn(self.client.get(f"/api/ciudadanos/{ajeno.ciudadano_id}/cobertura/").status_code, (403, 404))

    def test_area_no_autorizada_bloquea_lectura_y_escritura(self):
        otra = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        self.membresia_hospital.areas.set([otra])
        self.assertEqual(self.client.get(self.base + "cobertura/").status_code, 403)
        self.assertEqual(self.client.post(self.base + "cobertura-evaluar/", {
            "contexto": {"nodo": self.nodo.pk, "actualizado": self.caso.actualizado.isoformat()},
            "prestacion": self.prestacion.pk,
        }, format="json").status_code, 403)

    def test_grupo_responsable_impide_operar_pero_permite_consultar_el_historial(self):
        grupo = Grupo.objects.create(area=self.area, nombre="Responsables")
        self.nodo.grupos.add(grupo)
        resumen = self.resumen()
        self.assertFalse(resumen["puede_operar"])
        self.assertEqual(self.cotizar().status_code, 403)
        self.assertEqual(self.seleccionar().status_code, 403)
        grupo.miembros.add(self.usuario)
        self.assertTrue(self.resumen()["puede_operar"])
        self.assertEqual(self.cotizar().status_code, 200)
        grupo.activo = False
        grupo.save(update_fields=["activo"])
        self.assertEqual(self.cotizar().status_code, 403)

    def test_membresia_revocada_no_conserva_acceso(self):
        self.membresia_hospital.activo = False
        self.membresia_hospital.save(update_fields=["activo"])
        self.assertIn(self.client.get(self.base + "cobertura/").status_code, (403, 404))
        self.assertEqual(self.client.post(self.base + "cobertura-evaluar/", {}, format="json").status_code, 404)

    def test_caso_finalizado_conserva_lectura_sin_permitir_correccion_o_confirmacion(self):
        payload = self.solicitud()
        self.caso.estado = Caso.Estado.CERRADO
        self.caso.save()
        self.assertFalse(self.resumen()["puede_operar"])
        self.assertEqual(self.confirmar(payload).status_code, 400)
        self.assertEqual(self.cotizar().status_code, 400)
        self.assertEqual(self.seleccionar().status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_configuracion_inactiva_no_ofrece_nuevas_operaciones(self):
        m.ConfiguracionHospital.objects.filter(institucion=self.institucion).update(activo=False)
        data = self.resumen()
        self.assertFalse(data["activo"])
        self.assertFalse(data["puede_operar"])
        self.assertEqual(data["afiliados"], [])
        self.assertEqual(data["prestaciones"], [])
        self.assertEqual(self.cotizar().status_code, 400)
        self.assertEqual(self.seleccionar().status_code, 400)

    def test_contexto_viejo_no_confirma_ni_cambia_afiliacion(self):
        payload = self.solicitud()
        self.caso.save(update_fields=["actualizado"])
        self.assertEqual(self.confirmar(payload).status_code, 400)
        response = self.seleccionar(contexto=payload["contexto"])
        self.assertEqual(response.status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())
        self.assertEqual(m.AfiliacionCaso.objects.filter(caso=self.caso).count(), 1)

    def test_prestacion_de_otro_paso_del_mismo_flujo_no_es_evaluable(self):
        otro = Nodo.objects.create(version=self.nodo.version, tipo=Nodo.Tipo.ATENCION, titulo="Control")
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=otro, codigo="CONTROL", nombre="Control")
        m.VinculoPrestacion.objects.create(prestacion=prestacion, comun=self.comun)
        self.assertEqual([p["id"] for p in self.resumen()["prestaciones"]], [self.prestacion.pk])
        response = self.cotizar(prestacion=prestacion.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("paso actual", str(response.data))

    def test_fecha_y_cantidad_del_cliente_no_alteran_la_evaluacion_del_paso(self):
        response = self.cotizar(fecha=str(self.hoy - timedelta(days=500)), cantidad=999)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["fecha"], str(self.hoy))
        self.assertEqual(response.data["cantidad"], 1)
        self.assertEqual(response.data["importe_total"], "100.00")

    def test_firma_alterada_es_rechazada_sin_reserva(self):
        payload = self.solicitud()
        payload["firma"] += "manipulada"
        response = self.confirmar(payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_cotizacion_vencida_no_confirma_importes_aunque_no_hayan_cambiado(self):
        payload = self.solicitud()
        firmado = signing.loads(payload["firma"], salt="cobertura-paso")
        with patch("django.core.signing.time.time", return_value=(timezone.now() - timedelta(hours=1)).timestamp()):
            payload["firma"] = signing.dumps(firmado, salt="cobertura-paso", compress=True)
        response = self.confirmar(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("venció", str(response.data))
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_mixin_preserva_rechazo_de_edicion_generica_del_caso(self):
        response = self.client.put(self.base, {"estado": "cerrado"}, format="json")
        self.assertEqual(response.status_code, 405, response.data)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.EN_EVALUACION)

    def test_importe_enviado_por_cliente_no_reemplaza_el_importe_firmado(self):
        self.conceder("registrar_aceptacion")
        response = self.confirmar(self.solicitud(acepta=True, importe_paciente="0.01", aceptacion={"importe": "0.01"}))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["aceptacion"]["importe"], "20.00")
        self.assertEqual(response.data["evaluacion"]["importe_paciente"], "20.00")

    def test_firma_valida_con_payload_cambiado_tambien_se_rechaza(self):
        payload = self.solicitud()
        firmado = signing.loads(payload["firma"], salt="cobertura-paso")
        firmado["evaluacion"]["importe_paciente"] = "0.01"
        payload["firma"] = signing.dumps(firmado, salt="cobertura-paso", compress=True)
        self.assertEqual(self.confirmar(payload).status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_aceptacion_requiere_permiso_explicito_y_no_se_hereda_del_rol(self):
        self.assertFalse(self.resumen()["prestaciones"][0]["puede_aceptar"])
        response = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(m.ReservaCobertura.objects.exists())
        self.conceder("registrar_aceptacion")
        self.assertTrue(self.resumen()["prestaciones"][0]["puede_aceptar"])
        response = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["aceptacion"]["prestacion"], self.prestacion.pk)
        self.assertEqual(response.data["aceptacion"]["usuario"], self.usuario.pk)
        self.assertIn("fecha", response.data["aceptacion"])
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_reintento_idempotente_no_duplica_reserva_evento_ni_cupo(self):
        payload = self.solicitud()
        primera = self.confirmar(payload)
        segunda = self.confirmar(payload)
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)
        self.assertEqual(primera.data["id"], segunda.data["id"])
        self.assertEqual(m.ReservaCobertura.objects.count(), 1)
        self.assertEqual(EventoCaso.objects.filter(caso=self.caso, titulo="Cobertura confirmada").count(), 1)
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, *periodo(self.hoy, "anio")), 1)

    def test_clave_reutilizada_con_otra_decision_no_sobrescribe_reserva(self):
        payload = self.solicitud()
        self.assertEqual(self.confirmar(payload).status_code, 201)
        response = self.confirmar({**payload, "acepta": True})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(m.ReservaCobertura.objects.count(), 1)
        self.assertEqual(m.ReservaCobertura.objects.get().aceptacion, {})

    def test_cambio_arancel_invalida_cotizacion_hasta_revisar_importe_nuevo(self):
        self.conceder("registrar_aceptacion")
        payload = self.solicitud(acepta=True)
        self.politica(importe=Decimal("250"))
        response = self.confirmar(payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())
        nuevo = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(nuevo.status_code, 201, nuevo.data)
        self.assertEqual(nuevo.data["aceptacion"]["importe"], "50.00")

    def test_renovacion_excluye_cupo_propio_y_conserva_cotizacion_anterior(self):
        self.conceder("registrar_aceptacion")
        self.externo(5)
        original = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(original.status_code, 201, original.data)
        anterior = m.ReservaCobertura.objects.get(pk=original.data["id"])
        evaluacion, aceptacion = deepcopy(anterior.evaluacion), deepcopy(anterior.aceptacion)
        consulta = self.cotizar()
        self.assertEqual(consulta.data["cubiertas"], 1)
        self.assertEqual(consulta.data["importe_paciente"], "20.00")
        renovada = self.confirmar(self.solicitud(acepta=True, no_realizada=True))
        self.assertEqual(renovada.status_code, 201, renovada.data)
        anterior.refresh_from_db()
        self.assertEqual(anterior.estado, "liberada")
        self.assertEqual(anterior.evaluacion, evaluacion)
        self.assertEqual(anterior.aceptacion, aceptacion)
        self.assertEqual(m.ReservaCobertura.objects.filter(estado="reservada").count(), 1)
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, *periodo(self.hoy, "anio")), 6)

    def test_renovacion_por_regla_distinta_no_transfiere_aceptacion_anterior(self):
        self.conceder("registrar_aceptacion")
        original = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(original.status_code, 201, original.data)
        self.nueva_regla(porcentaje=Decimal("50"))
        response = self.confirmar(self.solicitud(acepta=False, no_realizada=True))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["evaluacion"]["importe_paciente"], "50.00")
        self.assertEqual(response.data["aceptacion"], {})
        original = m.ReservaCobertura.objects.get(pk=original.data["id"])
        self.assertEqual(original.aceptacion["importe"], "20.00")
        self.assertEqual(original.estado, "liberada")

    def test_consumo_externo_tardio_conserva_compromiso_y_senala_discrepancia(self):
        self.conceder("registrar_aceptacion")
        original = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(original.status_code, 201, original.data)
        self.externo(6)
        consulta = self.cotizar()
        self.assertEqual(consulta.data["importe_paciente"], "20.00")
        self.assertEqual(consulta.data["cubiertas"], 1)
        nueva = self.confirmar(self.solicitud(acepta=True, no_realizada=True))
        self.assertEqual(nueva.status_code, 201, nueva.data)
        self.assertTrue(nueva.data["discrepancia"])
        self.assertEqual(nueva.data["aceptacion"]["importe"], "20.00")

    def test_confirmar_sin_aceptar_permite_atender_y_deja_saldo_administrativo(self):
        response = self.confirmar()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["aceptacion"], {})
        response = self.avanzar()
        self.assertEqual(response.status_code, 200, response.data)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.CERRADO)
        self.assertTrue(EntradaHistoria.objects.exists())
        reserva = m.ReservaCobertura.objects.get()
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.distribucion.estado, "pendiente")
        self.assertEqual(reserva.distribucion.importe_paciente, Decimal("20"))
        self.assertIsNone(reserva.distribucion.obligacion_paciente_id)
        self.assertIsNotNone(reserva.distribucion.obligacion_financiador_id)

    def test_sin_reserva_y_sin_afiliacion_no_se_bloquea_la_atencion(self):
        m.AfiliacionCaso.objects.filter(caso=self.caso).delete()
        response = self.avanzar()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(HechoAtencionCosteable.objects.filter(caso_origen_id=self.caso.pk).exists())
        self.assertTrue(EntradaHistoria.objects.exists())
        self.assertFalse(m.DistribucionCobro.objects.exclude(obligacion_paciente=None).exists())

    def test_correccion_explicita_conserva_versiones_y_traza_autor_fecha_motivo(self):
        contexto = self.resumen()["contexto"]
        response = self.seleccionar()
        self.assertEqual(response.status_code, 201, response.data)
        data = self.resumen()
        self.assertEqual(data["afiliacion"]["estado"], "particular")
        self.assertEqual(len(data["historial_afiliaciones"]), 2)
        self.assertNotEqual(data["contexto"], contexto)
        self.seleccion.refresh_from_db()
        self.assertEqual(self.seleccion.afiliado_id, self.afiliado.pk)
        self.assertEqual(self.seleccion.plan_id, self.plan.pk)
        evento = EventoCaso.objects.filter(caso=self.caso, titulo="Afiliación del caso registrada").latest("pk")
        self.assertEqual(evento.autor_id, self.usuario.pk)
        self.assertIn("Corrección documentada en admisión", evento.detalle)
        self.assertTrue(response.data["creado"])

    def test_reserva_abierta_impide_cambiar_afiliacion(self):
        self.assertEqual(self.confirmar().status_code, 201)
        response = self.seleccionar()
        self.assertEqual(response.status_code, 400)
        self.assertIn("reservas abiertas", str(response.data))
        self.assertEqual(m.AfiliacionCaso.objects.filter(caso=self.caso).count(), 1)

    def test_renovar_exige_confirmar_no_realizacion_y_preserva_reserva_ante_rechazo(self):
        self.conceder("registrar_aceptacion")
        primera = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(primera.status_code, 201, primera.data)
        original = m.ReservaCobertura.objects.get()
        evaluacion, aceptacion = deepcopy(original.evaluacion), deepcopy(original.aceptacion)
        self.politica(importe=Decimal("250"))
        rechazada = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(rechazada.status_code, 400, rechazada.data)
        self.assertIn("no se realizó", str(rechazada.data))
        original.refresh_from_db()
        self.assertEqual(original.estado, "reservada")
        self.assertEqual(original.evaluacion, evaluacion)
        self.assertEqual(original.aceptacion, aceptacion)
        self.assertEqual(m.ReservaCobertura.objects.count(), 1)

    def test_prestacion_con_hecho_registrado_no_puede_renovarse_como_no_realizada(self):
        self.assertEqual(self.confirmar().status_code, 201)
        reserva = m.ReservaCobertura.objects.get()
        hecho = self.atencion()
        # Simula un hecho durable cuya captura de cobertura quedó pendiente.
        m.ReservaCobertura.objects.filter(pk=reserva.pk).update(estado="reservada", hecho=None)
        self.assertGreaterEqual(hecho.ocurrida_en, reserva.creado)
        response = self.cotizar()
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("atención registrada", str(response.data))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "reservada")

    def test_declaracion_pendiente_se_conserva_sin_inventar_cobertura(self):
        response = self.seleccionar(particular=False, declaracion="Mutual declarada, credencial pendiente")
        self.assertEqual(response.status_code, 201, response.data)
        consulta = self.cotizar()
        self.assertEqual(consulta.status_code, 200, consulta.data)
        self.assertEqual(consulta.data["estado"], "pendiente_evaluacion")
        self.assertEqual(self.confirmar().status_code, 400)
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_historial_paciente_es_paginado_sin_obligaciones_ni_datos_clinicos(self):
        for indice in range(4):
            seleccionar_afiliacion(caso=self.caso, usuario=self.usuario, particular=True, motivo=f"Corrección {indice}")
        response = self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/?page_size=2")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response.data["count"], 5)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        segunda = self.client.get(response.data["next"])
        self.assertEqual(segunda.status_code, 200)
        self.assertTrue(set(a["id"] for a in response.data["results"]).isdisjoint(a["id"] for a in segunda.data["results"]))
        fila = response.data["results"][0]
        self.assertEqual(fila["caso"], self.caso.pk)
        self.assertEqual(fila["flujo_titulo"], "Guardia")
        self.assertNotIn("obligaciones", fila)
        self.assertNotIn("evaluacion", fila)
        self.assertNotIn("contenido", fila)

    def test_historial_paciente_solo_muestra_casos_del_area_permitida(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Área restringida")
        otro_caso = Caso.objects.create(institucion=self.institucion, version=self.caso.version,
            ciudadano=self.paciente, area_actual=otra_area)
        seleccionar_afiliacion(caso=otro_caso, usuario=self.admin, particular=True, motivo="Otro servicio")
        response = self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["caso"], self.caso.pk)
        self.membresia_hospital.areas.add(otra_area)
        response = self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/")
        self.assertEqual(response.data["count"], 2)

    def test_historial_paciente_excluye_revision_financiera_de_hecho(self):
        hecho = self.atencion()
        m.AfiliacionCaso.objects.create(caso=self.caso, estado="particular", hecho_revision=hecho,
            registrado_por=self.admin, motivo="Corrección exclusiva de la deuda")
        response = self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.seleccion.pk)

    def test_reserva_abierta_antigua_sigue_visible_tras_cincuenta_y_un_cierres(self):
        response = self.confirmar()
        self.assertEqual(response.status_code, 201, response.data)
        abierta = m.ReservaCobertura.objects.get(pk=response.data["id"])
        cerradas = m.ReservaCobertura.objects.bulk_create([
            m.ReservaCobertura(caso=self.caso, afiliacion=self.seleccion, afiliado=self.afiliado,
                prestacion=self.prestacion, comun=self.comun, fecha=self.hoy,
                cantidad=1, cubiertas=1, estado="liberada", evaluacion=abierta.evaluacion,
                creado_por=self.usuario, cerrado_por=self.usuario, cerrado_en=timezone.now(),
                motivo="Prestación no realizada, confirmación documentada")
            for _ in range(51)
        ])
        data = self.resumen()
        self.assertTrue(data["historial_truncado"])
        self.assertEqual(len(data["reservas"]), 51)
        self.assertEqual([r["id"] for r in data["reservas"] if r["estado"] == "reservada"], [abierta.pk])
        self.assertEqual(
            {r["id"] for r in data["reservas"] if r["estado"] == "liberada"},
            {r.pk for r in cerradas[1:]},
        )
        abierta.refresh_from_db()
        self.assertEqual(abierta.estado, "reservada")

    def test_ingreso_http_hereda_area_del_flujo_y_operador_limitado_completa_cobertura_y_atencion(self):
        LegajoProfesional.objects.create(usuario=self.usuario, matricula="MP-CIRCUITO")
        version = self.nodo.version
        version.estado = VersionFlujo.Estado.PUBLICADA
        version.save(update_fields=["estado"])
        inicio = Nodo.objects.create(version=version, tipo=Nodo.Tipo.INICIO, titulo="Ingreso")
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=version, origen=inicio, destino=self.nodo)
        Conexion.objects.create(version=version, origen=self.nodo, destino=fin)
        grupo = Grupo.objects.create(area=self.area, nombre="Equipo del circuito")
        grupo.miembros.add(self.usuario)
        self.nodo.grupos.add(grupo)
        self.conceder("registrar_aceptacion", area=self.area)
        self.assertEqual(list(self.membresia_hospital.areas.all()), [self.area])

        creado = self.client.post("/api/casos/", {
            "institucion": self.institucion.pk, "version": version.pk,
            "ciudadano": self.paciente.pk, "prioridad": "normal",
        }, format="json")
        self.assertEqual(creado.status_code, 201, creado.data)
        caso = Caso.objects.get(pk=creado.data["id"])
        self.assertEqual(caso.area_actual_id, self.area.pk)
        self.base = f"/api/casos/{caso.pk}/"
        iniciado = self.client.post(self.base + "iniciar/", {}, format="json")
        self.assertEqual(iniciado.status_code, 200, iniciado.data)
        resumen = self.resumen()
        self.assertTrue(resumen["puede_operar"])
        self.assertEqual(resumen["contexto"]["nodo"], self.nodo.pk)
        self.assertIsNone(resumen["afiliacion"])
        self.assertEqual([a["id"] for a in resumen["afiliados"]], [self.afiliado.pk])

        seleccion = self.seleccionar(particular=False, afiliado=self.afiliado.pk,
            motivo="Afiliación verificada en el ingreso real")
        self.assertEqual(seleccion.status_code, 201, seleccion.data)
        confirmada = self.confirmar(self.solicitud(acepta=True))
        self.assertEqual(confirmada.status_code, 201, confirmada.data)
        self.assertEqual(confirmada.data["aceptacion"]["importe"], "20.00")
        completado = self.client.post(self.base + "avanzar/", {
            "titulo": "Consulta del ingreso real", "contenido": "Atención realizada", "firmada": True,
        }, format="json")
        self.assertEqual(completado.status_code, 200, completado.data)

        caso.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.CERRADO)
        self.assertEqual(caso.area_actual_id, self.area.pk)
        hecho = HechoAtencionCosteable.objects.get(caso_origen_id=caso.pk)
        self.assertEqual(hecho.area_id, self.area.pk)
        self.assertEqual(hecho.area_origen_id, self.area.pk)
        reserva = m.ReservaCobertura.objects.get(pk=confirmada.data["id"])
        self.assertEqual(reserva.hecho_id, hecho.pk)
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertEqual(reserva.distribucion.obligacion_financiador.importe_original, Decimal("80"))
        entrada = EntradaHistoria.objects.get(caso=caso)
        self.assertTrue(entrada.firmada)
        self.assertEqual(entrada.matricula, "MP-CIRCUITO")

    def test_ingreso_con_area_conserva_asignacion_clinica_explicita_para_atender(self):
        version = self.nodo.version
        version.estado = VersionFlujo.Estado.PUBLICADA
        version.save(update_fields=["estado"])
        inicio = Nodo.objects.create(version=version, tipo=Nodo.Tipo.INICIO, titulo="Ingreso")
        Conexion.objects.create(version=version, origen=inicio, destino=self.nodo)
        self.membresia_hospital.areas.clear()
        LegajoProfesional.objects.create(usuario=self.usuario, matricula="MP-CIRCUITO")
        creado = self.client.post("/api/casos/", {
            "institucion": self.institucion.pk, "version": version.pk,
            "ciudadano": self.paciente.pk,
        }, format="json")
        self.assertEqual(creado.status_code, 201, creado.data)
        base = f"/api/casos/{creado.data['id']}/"
        self.assertEqual(self.client.post(base + "iniciar/", {}, format="json").status_code, 200)
        for firmada in (True, False):
            with self.subTest(firmada=firmada):
                respuesta = self.client.post(base + "avanzar/", {
                    "titulo": "Atención", "contenido": "No autorizada en el área", "firmada": firmada,
                }, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn("No estás asignado al área", str(respuesta.data))
        self.assertFalse(HechoAtencionCosteable.objects.filter(caso_origen_id=creado.data["id"]).exists())
