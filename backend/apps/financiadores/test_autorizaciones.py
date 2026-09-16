"""Autorización previa: permisos, historia, idempotencia y límites clínicos."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera, Prestacion
from apps.instituciones.models import Area
from apps.registros.models import Ciudadano
from . import autorizaciones as a, models as m
from .cobertura import liberar, seleccionar_afiliacion
from .test_cobertura import CoberturaSetup


class AutorizacionSetup(CoberturaSetup):
    def setUp(self):
        super().setUp()
        self.caso.nodo_actual = self.nodo
        self.caso.paso_desde = timezone.now()
        self.caso.save(update_fields=["nodo_actual", "paso_desde"])
        self.regla.requiere_autorizacion = True
        self.regla.save(update_fields=["requiere_autorizacion"])
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.miembro_hospital = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="medico")
        self.miembro_hospital.areas.add(self.area)
        self.url = "/api/autorizaciones-cobertura/"

    def solicitud(self, **cambios):
        datos = dict(caso=self.caso, prestacion=self.prestacion, usuario=self.usuario,
            intento=a.intento_actual(self.caso), cantidad=3, justificacion="Orden para tres atenciones", clave=uuid4())
        datos.update(cambios)
        return a.solicitar(**datos)

    def aprobacion(self, **cambios):
        datos = dict(revision=1, decision="aprobar", motivo="Documentación verificada",
            cantidad_aprobada=3, vigencia_desde=self.hoy, vigencia_hasta=self.hoy + timedelta(days=30),
            evidencia="Orden presentada y validada", numero_externo="AUT-001", clave=uuid4())
        datos.update(cambios)
        return datos


class AutorizacionApiTests(AutorizacionSetup, APITestCase):
    def resolver_http(self, obj, datos=None, usuario=None):
        self.client.force_authenticate(usuario or self.operador)
        return self.client.post(f"{self.url}{obj.pk}/resolver/?financiador={obj.financiador_id}", datos or self.aprobacion(), format="json")

    def test_crear_observar_reenviar_aprobar_conserva_paso_y_no_emite_cargos(self):
        self.client.force_authenticate(self.usuario)
        contexto = self.client.get(self.url + "contexto/", {"caso": self.caso.pk})
        self.assertEqual(contexto.status_code, 200)
        self.assertTrue(contexto.data["puede_solicitar"])
        datos = {"caso": self.caso.pk, "prestacion": self.prestacion.pk, "intento": contexto.data["intento"],
            "cantidad": 3, "justificacion": "Necesidad administrativa explícita", "clave": str(uuid4())}
        creada = self.client.post(self.url, datos, format="json")
        self.assertEqual(creada.status_code, 201, creada.data)
        obj = m.SolicitudAutorizacion.objects.get(pk=creada.data["id"])
        observada = self.resolver_http(obj, {"revision": 1, "decision": "observar", "motivo": "Precisar orden", "clave": str(uuid4())})
        self.assertEqual(observada.status_code, 200, observada.data)
        self.client.force_authenticate(self.usuario)
        reenviada = self.client.post(f"{self.url}{obj.pk}/reenviar/?institucion={self.institucion.pk}", {
            "revision": 2, "justificacion": "Orden aclarada por el hospital", "clave": str(uuid4()),
        }, format="json")
        self.assertEqual(reenviada.status_code, 200, reenviada.data)
        aprobada = self.resolver_http(obj, self.aprobacion(revision=3))
        self.assertEqual(aprobada.status_code, 200, aprobada.data)
        self.assertEqual(aprobada.data["estado"], "aprobada")
        self.assertEqual(aprobada.data["cantidades"], {"comprometida": 0, "consumida": 0, "disponible": 3})
        self.assertEqual([e["accion"] for e in aprobada.data["historial"]], ["solicitar", "observar", "reenviar", "aprobar"])
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.nodo_actual_id, self.nodo.pk)
        self.assertEqual(self.caso.estado, "recibido")
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertFalse(m.ReservaCobertura.objects.exists())

    def test_reintentos_exactos_no_duplican_y_clave_reutilizada_rechaza(self):
        clave = uuid4()
        obj = self.solicitud(clave=clave)
        self.assertEqual(self.solicitud(clave=clave).pk, obj.pk)
        with self.assertRaises(ValidationError):
            self.solicitud(clave=clave, cantidad=2)
        datos = self.aprobacion()
        self.assertEqual(self.resolver_http(obj, datos).status_code, 200)
        self.assertEqual(self.resolver_http(obj, datos).status_code, 200)
        self.assertEqual(self.resolver_http(obj, {**datos, "motivo": "Otra decisión"}).status_code, 400)
        self.assertEqual(obj.historial.count(), 2)

    def test_revision_vieja_y_terminal_no_se_reabren(self):
        obj = self.solicitud()
        datos = {"revision": 1, "decision": "rechazar", "motivo": "No corresponde", "clave": str(uuid4())}
        self.assertEqual(self.resolver_http(obj, datos).status_code, 200)
        self.assertEqual(self.resolver_http(obj).status_code, 400)
        self.assertEqual(self.resolver_http(obj, self.aprobacion(revision=2)).status_code, 400)
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "rechazada")
        self.assertEqual(obj.historial.count(), 2)

    def test_nueva_solicitud_enlaza_ultima_terminal_sin_reabrir_ni_duplicar(self):
        primera = self.solicitud()
        self.assertIsNone(primera.anterior_id)
        a.anular(solicitud=primera, usuario=self.usuario, revision=1, motivo="Revisar orden", clave=uuid4())
        clave = uuid4()
        segunda = self.solicitud(clave=clave)
        self.assertEqual(segunda.anterior_id, primera.pk)
        self.assertEqual(self.solicitud(clave=clave).pk, segunda.pk)
        a.resolver(solicitud=segunda, usuario=self.operador, revision=1,
            decision="rechazar", motivo="Orden incompleta", clave=uuid4())

        # Un ID enviado por el cliente no permite elegir ni cambiar el antecedente.
        self.client.force_authenticate(self.usuario)
        creada = self.client.post(self.url, {"caso": self.caso.pk, "prestacion": self.prestacion.pk,
            "intento": str(a.intento_actual(self.caso)), "cantidad": 1, "justificacion": "Orden completa",
            "clave": str(uuid4()), "anterior": primera.pk}, format="json")
        self.assertEqual(creada.status_code, 201, creada.data)
        self.assertEqual(creada.data["anterior"], segunda.pk)
        detalle = self.client.get(f"{self.url}{creada.data['id']}/", {"institucion": self.institucion.pk})
        self.assertEqual(detalle.data["anterior"], segunda.pk)
        self.client.force_authenticate(self.operador)
        listado = self.client.get(self.url, {"financiador": self.financiador.pk})
        self.assertEqual({s["id"]: s["anterior"] for s in listado.data["results"]},
                         {primera.pk: None, segunda.pk: primera.pk, creada.data["id"]: segunda.pk})

        m.SolicitudAutorizacion.objects.filter(pk=creada.data["id"]).update(estado="vencida")
        cuarta = self.solicitud()
        self.assertEqual(cuarta.anterior_id, creada.data["id"])
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual((primera.estado, primera.revision, primera.historial.count()), ("anulada", 2, 2))
        self.assertEqual((segunda.estado, segunda.revision, segunda.historial.count()), ("rechazada", 2, 2))
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_antecedente_no_cruza_caso_intento_o_prestacion(self):
        primera = self.solicitud()
        a.anular(solicitud=primera, usuario=self.usuario, revision=1, motivo="Nueva orden", clave=uuid4())
        otra_prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo,
            codigo="CONS-OTRA", nombre="Otra consulta")
        m.VinculoPrestacion.objects.create(prestacion=otra_prestacion, comun=self.comun)
        self.assertIsNone(self.solicitud(prestacion=otra_prestacion).anterior_id)

        otro_caso = Caso.objects.create(institucion=self.institucion, version=self.caso.version,
            ciudadano=self.paciente, area_actual=self.area, nodo_actual=self.nodo,
            paso_desde=self.caso.paso_desde)
        seleccionar_afiliacion(caso=otro_caso, usuario=self.admin, afiliado=self.afiliado, motivo="Nuevo caso")
        self.assertIsNone(self.solicitud(caso=otro_caso, intento=a.intento_actual(otro_caso)).anterior_id)

        self.caso.paso_desde += timedelta(minutes=1)
        self.caso.save(update_fields=["paso_desde"])
        self.assertIsNone(self.solicitud().anterior_id)

    def test_cambio_de_obra_social_no_expone_antecedente_del_pagador_anterior(self):
        primera = self.solicitud()
        a.anular(solicitud=primera, usuario=self.usuario, revision=1, motivo="Cambió la afiliación", clave=uuid4())
        mutual = m.Financiador.objects.create(nombre="Nueva mutual", tipo="mutual")
        m.Convenio.objects.create(financiador=mutual, institucion=self.institucion,
            estado="activo", propuesto_por="plataforma", creado_por=self.admin)
        afiliado = m.Afiliado.objects.create(financiador=mutual, numero="N-1", nombre=self.afiliado.nombre,
            documento=self.afiliado.documento, desde=self.hoy)
        self.nueva_regla(financiador=mutual, plan=None, requiere_autorizacion=True)
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin, afiliado=afiliado, motivo="Afiliación actualizada")
        segunda = self.solicitud()
        self.assertIsNone(segunda.anterior_id)
        m.MembresiaFinanciador.objects.create(financiador=mutual, usuario=self.operador, rol="operador")
        self.client.force_authenticate(self.operador)
        detalle = self.client.get(f"{self.url}{segunda.pk}/", {"financiador": mutual.pk})
        self.assertEqual(detalle.status_code, 200)
        self.assertIsNone(detalle.data["anterior"])
        self.assertEqual(self.client.get(f"{self.url}{primera.pk}/", {"financiador": mutual.pk}).status_code, 404)

    def test_admin_y_plataforma_sin_designacion_no_resuelven(self):
        obj = self.solicitud()
        for rol in ["admin", "operador", "auditor"]:
            with self.subTest(rol=rol):
                self.membresia.rol, self.membresia.resuelve_autorizaciones = rol, False
                self.membresia.save(update_fields=["rol", "resuelve_autorizaciones"])
                self.assertEqual(self.resolver_http(obj).status_code, 403)
        self.assertEqual(self.resolver_http(obj, usuario=self.admin).status_code, 403)
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.assertEqual(self.resolver_http(obj).status_code, 403, "Un auditor no decide aunque quede un flag antiguo")
        self.membresia.rol = "operador"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.resolver_http(obj).status_code, 200)

    def test_auditor_lee_sin_historia_clinica_y_lectura_es_auditada(self):
        obj = self.solicitud()
        EventoCaso.objects.create(caso=self.caso, titulo="Hallazgo clínico", detalle="SECRETO-CLINICO")
        self.membresia.rol, self.membresia.resuelve_autorizaciones = "auditor", False
        self.membresia.save(update_fields=["rol", "resuelve_autorizaciones"])
        self.client.force_authenticate(self.operador)
        response = self.client.get(f"{self.url}{obj.pk}/", {"financiador": self.financiador.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["puede_resolver"])
        self.assertNotIn(b"SECRETO-CLINICO", response.content)
        self.assertIn("no-store", response["Cache-Control"])
        acceso = AccesoClinico.objects.get(recurso="solicitudautorizacion")
        self.assertEqual((acceso.usuario_id, acceso.institucion_id, acceso.ciudadano_id), (self.operador.pk, self.institucion.pk, self.paciente.pk))

    def test_membresia_revocada_y_otro_financiador_no_acceden(self):
        obj = self.solicitud()
        otra = m.Financiador.objects.create(nombre="Otra mutual", tipo="mutual")
        m.MembresiaFinanciador.objects.create(financiador=otra, usuario=self.operador, rol="admin", resuelve_autorizaciones=True)
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(f"{self.url}{obj.pk}/", {"financiador": otra.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"financiador": otra.pk}).data["count"], 0)
        self.membresia.activo = False
        self.membresia.save(update_fields=["activo"])
        self.assertEqual(self.client.get(self.url, {"financiador": self.financiador.pk}).status_code, 403)
        self.assertFalse(AccesoClinico.objects.filter(recurso="solicitudautorizacion").exists())

    def test_hospital_y_area_ajenos_no_listan_ni_modifican(self):
        obj = self.solicitud()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        self.miembro_hospital.areas.set([otra_area])
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.client.get(self.url, {"institucion": self.institucion.pk}).data["count"], 0)
        self.assertEqual(self.client.get(f"{self.url}{obj.pk}/", {"institucion": self.institucion.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.url + "contexto/", {"caso": self.caso.pk}).status_code, 404)
        self.assertFalse(AccesoClinico.objects.filter(recurso="solicitudautorizacion").exists())

    def test_cierre_convenio_y_baja_dejan_solo_expediente_pendiente(self):
        obj = self.solicitud()
        self.convenio.estado, self.convenio.cerrado_en = "finalizado", timezone.now()
        self.convenio.save(update_fields=["estado", "cerrado_en"])
        self.afiliado.finalizado_en = timezone.now()
        self.afiliado.save(update_fields=["finalizado_en"])
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(self.url, {"financiador": self.financiador.pk}).data["count"], 1)
        self.assertEqual(self.resolver_http(obj).status_code, 200)
        self.assertEqual(self.client.get(self.url, {"financiador": self.financiador.pk}).data["count"], 0)
        self.afiliado.refresh_from_db()
        self.convenio.refresh_from_db()
        self.assertIsNotNone(self.afiliado.finalizado_en)
        self.assertEqual(self.convenio.estado, "finalizado")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_aprobada_con_uso_pendiente_sigue_visible_hasta_liberacion_confirmada(self):
        obj = self.solicitud()
        a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion())
        reserva = self.reservar()
        m.UsoAutorizacion.objects.get_or_create(reserva=reserva, defaults={"solicitud": obj, "cantidad": 1})
        self.convenio.estado, self.convenio.cerrado_en = "finalizado", timezone.now()
        self.convenio.save(update_fields=["estado", "cerrado_en"])
        self.afiliado.finalizado_en = timezone.now()
        self.afiliado.save(update_fields=["finalizado_en"])
        self.client.force_authenticate(self.operador)
        parametros = {"financiador": self.financiador.pk}
        self.assertEqual(self.client.get(self.url, parametros).data["count"], 1)
        liberar(reserva=reserva, usuario=self.admin, motivo="Confirmada no realización", no_realizada=True)
        self.assertEqual(self.client.get(self.url, parametros).data["count"], 0)

    def test_intento_estable_ante_actualizaciones_y_distinto_al_volver_al_nodo(self):
        original = a.intento_actual(self.caso)
        self.caso.save()
        self.caso.refresh_from_db()
        self.assertEqual(a.intento_actual(self.caso), original)
        self.solicitud()
        self.caso.paso_desde += timedelta(minutes=1)
        self.caso.save(update_fields=["paso_desde"])
        self.assertNotEqual(a.intento_actual(self.caso), original)
        with self.assertRaises(ValidationError):
            self.solicitud(intento=original)
        self.solicitud()
        self.assertEqual(m.SolicitudAutorizacion.objects.count(), 2)

    def test_intento_inicial_sin_paso_desde_usa_creado(self):
        self.caso.paso_desde = None
        self.caso.save(update_fields=["paso_desde"])
        inicial = a.intento_actual(self.caso)
        self.caso.save()
        self.caso.refresh_from_db()
        self.assertEqual(a.intento_actual(self.caso), inicial)

    def test_plazo_se_congela_sla_ausente_no_vencido_y_reenvio_no_reinicia(self):
        sin_plazo = self.solicitud()
        self.assertIsNone(sin_plazo.plazo_respuesta)
        self.assertEqual(self.resolver_http(sin_plazo, self.aprobacion(vigencia_hasta=self.hoy)).status_code, 200)
        self.caso.paso_desde += timedelta(seconds=1)
        self.caso.save(update_fields=["paso_desde"])
        self.convenio.plazo_autorizacion_horas = 24
        self.convenio.save(update_fields=["plazo_autorizacion_horas"])
        obj = self.solicitud()
        plazo = obj.plazo_respuesta
        a.resolver(solicitud=obj, usuario=self.operador, revision=1, decision="observar", motivo="Precisar orden", clave=uuid4())
        self.convenio.plazo_autorizacion_horas = 100
        self.convenio.save(update_fields=["plazo_autorizacion_horas"])
        a.reenviar(solicitud=obj, usuario=self.usuario, revision=2, justificacion="Orden aclarada", clave=uuid4())
        obj.refresh_from_db()
        self.assertEqual(obj.plazo_respuesta, plazo)
        m.SolicitudAutorizacion.objects.filter(pk=obj.pk).update(plazo_respuesta=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.resolver_http(obj, self.aprobacion(revision=3)).status_code, 400)

    def test_validacion_cantidad_vigencia_y_evidencia_no_modifica_solicitud(self):
        obj = self.solicitud()
        for cambios in ({"cantidad_aprobada": 0}, {"cantidad_aprobada": 4}, {"vigencia_hasta": self.hoy - timedelta(days=1)}, {"evidencia": ""}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.resolver_http(obj, self.aprobacion(**cambios)).status_code, 400)
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "pendiente")
        self.assertEqual(obj.historial.count(), 1)

    def test_anular_no_realiza_prestacion_y_no_revive_con_nueva_decision(self):
        obj = self.solicitud()
        a.anular(solicitud=obj, usuario=self.usuario, revision=1, motivo="Orden desistida", clave=uuid4())
        self.assertEqual(self.resolver_http(obj, self.aprobacion(revision=2)).status_code, 400)
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_solicitud_no_activa_urgencia_a_pedido_del_cliente(self):
        self.client.force_authenticate(self.usuario)
        response = self.client.post(self.url, {"caso": self.caso.pk, "prestacion": self.prestacion.pk,
            "intento": str(a.intento_actual(self.caso)), "cantidad": 1, "justificacion": "Orden", "urgente": True, "clave": str(uuid4())}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertFalse(response.data["urgente"])

    def test_no_solicita_sin_regla_configurada_o_con_cantidad_invalida(self):
        with self.assertRaises(ValidationError):
            self.solicitud(cantidad=0)
        self.regla.requiere_autorizacion = False
        self.regla.save(update_fields=["requiere_autorizacion"])
        with self.assertRaises(ValidationError):
            self.solicitud()
        self.assertFalse(m.SolicitudAutorizacion.objects.exists())

    def test_corregir_paciente_del_caso_requiere_reverificar_afiliacion(self):
        self.caso.ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Otra persona", documento="99887766")
        self.caso.save(update_fields=["ciudadano"])
        with self.assertRaisesMessage(ValidationError, "documento no coincide"):
            self.solicitud()
        self.assertFalse(m.SolicitudAutorizacion.objects.exists())

    def test_filtros_paginacion_y_opciones_no_amplian_alcance(self):
        primera = self.solicitud()
        self.caso.paso_desde += timedelta(seconds=1)
        self.caso.prioridad = Caso.Prioridad.URGENTE
        self.caso.save(update_fields=["paso_desde", "prioridad"])
        segunda = self.solicitud()
        self.client.force_authenticate(self.operador)
        base = {"financiador": self.financiador.pk}
        pagina = self.client.get(self.url, {**base, "page_size": 1})
        self.assertEqual(pagina.data["count"], 2)
        self.assertEqual(pagina.data["results"][0]["id"], primera.pk)
        urgente = self.client.get(self.url, {**base, "urgente": "true"})
        self.assertEqual([r["id"] for r in urgente.data["results"]], [segunda.pk])
        self.assertEqual(urgente.data["opciones"]["instituciones"], [{"id": self.institucion.pk, "nombre": self.institucion.nombre}])
        self.assertEqual(self.client.get(self.url, {**base, "hospital": 999999}).data["count"], 0)
        self.assertEqual(self.client.get(self.url, {**base, "institucion": self.institucion.pk}).status_code, 400)

    @override_settings(DEBUG=False)
    def test_fallo_auditoria_no_entrega_expediente_y_revierte_decision(self):
        obj = self.solicitud()
        self.client.force_authenticate(self.operador)
        self.client.raise_request_exception = False
        with patch("apps.auditoria.mixins.AccesoClinico.objects.bulk_create", side_effect=RuntimeError("Auditoría no disponible")):
            response = self.client.get(f"{self.url}{obj.pk}/", {"financiador": self.financiador.pk})
            self.assertEqual(response.status_code, 500)
            self.assertNotIn(obj.justificacion.encode(), response.content)
            self.assertEqual(self.resolver_http(obj).status_code, 500)
        obj.refresh_from_db()
        self.assertEqual(obj.estado, "pendiente")
        self.assertEqual(obj.historial.count(), 1)

    def test_permiso_y_plazo_se_configuran_explicitos_sin_cambiar_solicitudes(self):
        self.membresia.rol = "admin"
        self.membresia.save(update_fields=["rol"])
        self.client.force_authenticate(self.operador)
        base = f"/api/financiadores/{self.financiador.pk}/"
        creado = self.client.post(base + "usuarios/", {"email": "nuevo-autoriza@test.local", "nombre": "Nuevo operador", "rol": "operador"}, format="json")
        self.assertEqual(creado.status_code, 201)
        self.assertFalse(creado.data["resuelve_autorizaciones"])
        actualizado = self.client.post(base + "usuarios/", {"email": "nuevo-autoriza@test.local", "nombre": "Nuevo operador", "rol": "operador", "resuelve_autorizaciones": True}, format="json")
        self.assertTrue(actualizado.data["resuelve_autorizaciones"])
        self.assertIn("resuelve_autorizaciones=True", m.EventoCobertura.objects.filter(accion="membresia_financiador").latest("pk").motivo)
        obj = self.solicitud()
        plazo = self.client.post(base + "plazo-autorizacion/", {"convenio": self.convenio.pk, "plazo_autorizacion_horas": 48, "motivo": "Plazo acordado"}, format="json")
        self.assertEqual(plazo.status_code, 200, plazo.data)
        obj.refresh_from_db()
        self.assertIsNone(obj.plazo_respuesta)


@skipUnless(connection.vendor == "postgresql", "Los bloqueos requieren PostgreSQL.")
class AutorizacionConcurrenciaTests(AutorizacionSetup, TransactionTestCase):
    def competir(self, funciones):
        barrera = Barrier(len(funciones))

        def ejecutar(funcion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return funcion()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(funciones)) as executor:
            return list(executor.map(ejecutar, funciones))

    def test_dos_respuestas_concurrentes_conservan_una_decision(self):
        obj = self.solicitud()

        def resolver():
            try:
                a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion())
                return "aprobada"
            except ValidationError:
                return "conflicto"

        self.assertCountEqual(self.competir([resolver, resolver]), ["aprobada", "conflicto"])
        self.assertEqual(obj.historial.filter(accion="aprobar").count(), 1)
        self.assertFalse(HechoAtencionCosteable.objects.exists())

    def test_reintentos_concurrentes_comparten_solicitud_y_decision(self):
        clave = uuid4()
        ids = self.competir([lambda: self.solicitud(clave=clave).pk] * 2)
        self.assertEqual(ids[0], ids[1])
        obj = m.SolicitudAutorizacion.objects.get(pk=ids[0])
        datos = self.aprobacion()
        self.competir([lambda: a.resolver(solicitud=obj, usuario=self.operador, **datos)] * 2)
        self.assertEqual(obj.historial.count(), 2)

    def test_anular_y_aprobar_simultaneos_dejan_un_terminal(self):
        obj = self.solicitud()

        def operar(funcion):
            try:
                return funcion().estado
            except ValidationError:
                return "conflicto"

        resultados = self.competir([
            lambda: operar(lambda: a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion())),
            lambda: operar(lambda: a.anular(solicitud=obj, usuario=self.usuario, revision=1, motivo="Orden desistida", clave=uuid4())),
        ])
        self.assertEqual(resultados.count("conflicto"), 1)
        self.assertEqual(obj.historial.count(), 2)
