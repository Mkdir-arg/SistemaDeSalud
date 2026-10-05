"""Preautorizaciones cargadas por el financiador sin caso hospitalario."""
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.casos.models import EventoCaso
from apps.instituciones.models import Institucion
from . import autorizaciones as a, models as m
from .esperas import vencer_autorizaciones
from .test_autorizaciones import AutorizacionSetup


class ManualSetup(AutorizacionSetup):
    def manual(self, **cambios):
        datos = dict(financiador_id=self.financiador.pk, afiliado=self.afiliado,
            institucion=self.institucion, comun=self.comun, usuario=self.operador,
            cantidad=3, justificacion="Orden para prestación futura", clave=uuid4())
        datos.update(cambios)
        return a.solicitar_manual(**datos)

    def datos_http(self, **cambios):
        datos = dict(afiliado=self.afiliado.pk, institucion=self.institucion.pk,
            comun=self.comun.pk, cantidad=3, justificacion="Orden para prestación futura",
            clave=str(uuid4()))
        datos.update(cambios)
        return datos


class ManualApiTests(ManualSetup, APITestCase):
    def crear(self, usuario=None, **cambios):
        self.client.force_authenticate(usuario or self.operador)
        return self.client.post(f"{self.url}manual/?financiador={self.financiador.pk}",
            self.datos_http(**cambios), format="json")

    def test_admin_y_operador_crean_y_otros_roles_no(self):
        self.assertEqual(self.crear().status_code, 201)
        self.membresia.rol = "admin"
        self.membresia.save(update_fields=["rol"])
        otra_comun = m.PrestacionComun.objects.create(codigo="OTRA", nombre="Otra", categoria="consultas")
        self.nueva_regla(prestacion=otra_comun, requiere_autorizacion=True)
        self.assertEqual(self.crear(comun=otra_comun.pk).status_code, 201)
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.crear().status_code, 403)
        self.assertEqual(self.crear(usuario=self.admin).status_code, 403)
        otro = Usuario.objects.create_user("ajeno@manual.local", "x")
        self.assertEqual(self.crear(usuario=otro).status_code, 403)
        self.assertEqual(self.crear(usuario=self.usuario).status_code, 403)
        self.operador.is_superuser = True
        self.operador.save(update_fields=["is_superuser"])
        self.assertEqual(self.crear().status_code, 403)

    def test_validaciones_de_entrada_y_ambito(self):
        for cambios in ({"cantidad": 0}, {"cantidad": 100001}, {"justificacion": "  "}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.crear(**cambios).status_code, 400)
        otra = m.Financiador.objects.create(nombre="Ajeno", tipo="mutual")
        ajeno = m.Afiliado.objects.create(financiador=otra, numero="X", documento="X", nombre="X", desde=self.hoy)
        ajena = self.crear(afiliado=ajeno.pk)
        inexistente = self.crear(afiliado=999999)
        self.assertEqual(ajena.status_code, 404)
        self.assertEqual(ajena.data, inexistente.data)
        self.afiliado.finalizado_en = timezone.now()
        self.afiliado.save(update_fields=["finalizado_en"])
        self.assertEqual(self.crear().status_code, 400)
        self.afiliado.finalizado_en = None
        self.afiliado.desde = self.hoy + timedelta(days=1)
        self.afiliado.save(update_fields=["finalizado_en", "desde"])
        self.assertEqual(self.crear().status_code, 400)
        self.afiliado.desde = self.hoy
        self.afiliado.save(update_fields=["desde"])
        sin_convenio = Institucion.objects.create(nombre="Sin convenio")
        self.assertEqual(self.crear(institucion=sin_convenio.pk).status_code, 400)
        self.regla.requiere_autorizacion = False
        self.regla.save(update_fields=["requiere_autorizacion"])
        self.assertEqual(self.crear().status_code, 400)
        self.regla.requiere_autorizacion = True
        self.regla.save(update_fields=["requiere_autorizacion"])
        self.comun.activo = False
        self.comun.save(update_fields=["activo"])
        self.assertEqual(self.crear().status_code, 400)

    def test_reintento_origen_evento_y_listados(self):
        clave = str(uuid4())
        primera = self.crear(clave=clave)
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(self.crear(clave=clave).data["id"], primera.data["id"])
        self.assertEqual(self.crear(clave=clave, cantidad=2).status_code, 400)
        obj = m.SolicitudAutorizacion.objects.get(pk=primera.data["id"])
        self.assertEqual((obj.origen, obj.estado, obj.caso_id, obj.ciudadano_id, obj.plazo_respuesta),
            ("manual", "pendiente", None, None, None))
        self.assertEqual((obj.historial.get().usuario_id, obj.historial.count()), (self.operador.pk, 1))
        self.assertFalse(EventoCaso.objects.filter(titulo__startswith="Autorización").exists())
        base = f"{self.url}?financiador={self.financiador.pk}"
        self.assertEqual(self.client.get(base + "&origen=manual").data["count"], 1)
        self.assertEqual(self.client.get(base + "&origen=institucion").data["count"], 0)
        self.assertEqual(self.client.get(base + "&origen=manual").data["results"][0]["creado_por_nombre"], self.operador.nombre_completo)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.client.get(self.url, {"institucion": self.institucion.pk}).data["count"], 0)
        self.assertEqual(self.client.get(f"{self.url}{obj.pk}/", {"institucion": self.institucion.pk}).status_code, 404)

    def test_opciones_solo_incluyen_datos_vigentes_y_regla_valida(self):
        self.client.force_authenticate(self.operador)
        respuesta = self.client.get(f"{self.url}opciones-manual/", {"financiador": self.financiador.pk,
            "search": "Ana", "afiliado": self.afiliado.pk, "hospital": self.institucion.pk})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([a["id"] for a in respuesta.data["afiliados"]], [self.afiliado.pk])
        self.assertEqual([p["id"] for p in respuesta.data["prestaciones"]], [self.comun.pk])
        self.assertEqual([i["id"] for i in respuesta.data["instituciones"]], [self.institucion.pk])

    def test_opciones_aceptan_busqueda_vacia_al_abrir_el_formulario(self):
        self.client.force_authenticate(self.operador)
        respuesta = self.client.get(f"{self.url}opciones-manual/", {"financiador": self.financiador.pk, "search": ""})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([i["id"] for i in respuesta.data["instituciones"]], [self.institucion.pk])

    def test_reenviar_y_anular_solo_financiador_admin_u_operador(self):
        obj = self.manual()
        a.resolver(solicitud=obj, usuario=self.operador, revision=1, decision="observar", motivo="Aclarar", clave=uuid4())
        self.client.force_authenticate(self.usuario)
        cuerpo = {"revision": 2, "justificacion": "Aclaración", "clave": str(uuid4())}
        self.assertEqual(self.client.post(f"{self.url}{obj.pk}/reenviar/?institucion={self.institucion.pk}", cuerpo, format="json").status_code, 404)
        self.client.force_authenticate(self.operador)
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.client.post(f"{self.url}{obj.pk}/reenviar/?financiador={self.financiador.pk}", cuerpo, format="json").status_code, 403)
        self.assertEqual(self.client.post(f"{self.url}{obj.pk}/anular/?financiador={self.financiador.pk}",
            {"revision": 2, "motivo": "Cancelada", "clave": str(uuid4())}, format="json").status_code, 403)
        self.membresia.rol = "operador"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.client.post(f"{self.url}{obj.pk}/reenviar/?financiador={self.financiador.pk}", cuerpo, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{self.url}{obj.pk}/anular/?financiador={self.financiador.pk}",
            {"revision": 3, "motivo": "Cancelada", "clave": str(uuid4())}, format="json").status_code, 200)


class ManualCircuitoTests(ManualSetup, TestCase):
    def test_restricciones_sql_impiden_incoherencia_y_duplicado(self):
        obj = self.manual()
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.SolicitudAutorizacion.objects.filter(pk=obj.pk).update(caso_id=self.caso.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            m.SolicitudAutorizacion.objects.create(origen="manual", institucion=self.institucion,
                financiador=self.financiador, convenio=self.convenio, afiliado=self.afiliado,
                comun=self.comun, cantidad_solicitada=1, justificacion="Duplicada", creado_por=self.operador)

    def test_solicitud_institucional_no_bloquea_manual(self):
        self.solicitud()
        self.assertEqual(self.manual().origen, "manual")

    def test_duplicado_abierto_y_terminales_permiten_nueva(self):
        for decision in ("aprobar", "rechazar", "anular"):
            obj = self.manual()
            with self.assertRaises(ValidationError):
                self.manual()
            if decision == "anular":
                a.anular(solicitud=obj, usuario=self.operador, revision=1, motivo="Desistida", clave=uuid4())
            elif decision == "aprobar":
                a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion())
            else:
                a.resolver(solicitud=obj, usuario=self.operador, revision=1, decision="rechazar",
                    motivo="Incompleta", clave=uuid4())
        self.assertEqual(self.manual().estado, "pendiente")

    def test_autorresolucion_y_vigencia_futura(self):
        obj = self.manual()
        self.assertEqual(a.resolver(solicitud=obj, usuario=self.operador, revision=1,
            decision="observar", motivo="Aclarar", clave=uuid4()).estado, "observada")
        a.reenviar(solicitud=obj, usuario=self.operador, revision=2, justificacion="Aclaración", clave=uuid4())
        with self.assertRaises(ValidationError):
            a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion(
                revision=3, vigencia_desde=self.hoy-timedelta(days=1)))
        self.assertEqual(a.resolver(solicitud=obj, usuario=self.operador,
            **self.aprobacion(revision=3)).estado, "aprobada")
        self.assertEqual(obj.historial.last().usuario_id, self.operador.pk)

    def test_aprobada_se_consume_solo_en_institucion_elegida(self):
        obj = self.manual()
        a.resolver(solicitud=obj, usuario=self.operador, **self.aprobacion())
        otro, prestacion = self.otro_hospital()
        self.assertIsNone(self.evaluar(caso=otro, prestacion=prestacion)["autorizacion"])
        reserva = self.reservar(acepta=True)
        self.assertEqual(m.UsoAutorizacion.objects.get(reserva=reserva).solicitud_id, obj.pk)
        hecho = self.atencion()
        uso = m.UsoAutorizacion.objects.get(reserva=reserva)
        self.assertEqual((uso.estado, uso.hecho_id), ("consumido", hecho.pk))

    def test_vencimiento_sin_caso_ignora_pendiente_y_vence_aprobada(self):
        pendiente = self.manual()
        otra_comun = m.PrestacionComun.objects.create(codigo="SEG", nombre="Segunda", categoria="consultas")
        self.nueva_regla(prestacion=otra_comun, requiere_autorizacion=True)
        aprobada = self.manual(comun=otra_comun)
        a.resolver(solicitud=aprobada, usuario=self.operador, **self.aprobacion())
        m.SolicitudAutorizacion.objects.filter(pk=aprobada.pk).update(
            vigencia_desde=self.hoy-timedelta(days=2), vigencia_hasta=self.hoy-timedelta(days=1))
        self.assertEqual(vencer_autorizaciones(ahora=timezone.now()), 1)
        pendiente.refresh_from_db()
        aprobada.refresh_from_db()
        self.assertEqual((pendiente.estado, aprobada.estado), ("pendiente", "vencida"))
