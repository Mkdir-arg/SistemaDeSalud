"""Regresiones de identidad, trazabilidad y cuentas técnicas del issue 111."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.accounts.serializers import MembresiaSerializer
from apps.auditoria.models import AccesoClinico
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica
from apps.registros.serializers import EntradaHistoriaSerializer
from apps.simulacion.models import Ambito
from apps.simulacion.perfiles import problema_de_cuenta
from apps.simulacion.preparacion import preparar_cuenta

from . import models as m
from apps.finanzas.test_cobros import CobrosSetup
from .test_autorizaciones_manuales import ManualSetup


class SolicitudesRegresionTests(ManualSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.operador)

    def ficha(self):
        return self.client.get(f"/api/financiadores/{self.financiador.pk}/ficha-afiliado-autorizaciones/",
                               {"afiliado": self.afiliado.pk})

    def test_ficha_manual_y_auditoria_de_la_persona(self):
        solicitud = self.manual()
        response = self.ficha()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["results"][0]["prestacion_nombre"], self.comun.nombre)
        acceso = AccesoClinico.objects.get(recurso="financiadores-ficha-afiliado")
        self.assertEqual(acceso.ciudadano_id, self.paciente.pk)
        self.assertIn(f"afiliado={self.afiliado.pk}", acceso.detalle)
        self.assertIn(f"financiador={self.financiador.pk}", acceso.detalle)
        self.assertEqual(acceso.objeto_id, str(solicitud.pk))
        response = self.client.get(self.url, {"financiador": self.financiador.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccesoClinico.objects.get(recurso="solicitudautorizacion").ciudadano_id, self.paciente.pk)

    def test_hospital_ve_traza_manual_sin_recibir_solicitud_en_bandeja(self):
        solicitud = self.manual()
        self.assertEqual(self.ficha().status_code, 200)
        auditor = Usuario.objects.create_user("auditor-hospital-111@example.test", "x")
        Membresia.objects.create(usuario=auditor, institucion=self.institucion, rol="admin")
        self.client.force_authenticate(auditor)
        response = self.client.get("/api/accesos-clinicos/", {"institucion": self.institucion.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["results"][0]["objeto_id"], str(solicitud.pk))
        response = self.client.get(self.url, {"institucion": self.institucion.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 0)

    def test_documento_se_compara_normalizado_sin_inventar_personas(self):
        self.afiliado.documento = "00.111.222"
        self.afiliado.save(update_fields=["documento"])
        self.manual()
        antes = Ciudadano.objects.count()
        self.assertEqual(self.ficha().status_code, 200)
        self.assertEqual(AccesoClinico.objects.latest("pk").ciudadano_id, self.paciente.pk)
        self.afiliado.documento = ""
        self.afiliado.save(update_fields=["documento"])
        self.assertEqual(self.ficha().status_code, 200)
        self.assertIsNone(AccesoClinico.objects.latest("pk").ciudadano_id)
        self.assertEqual(Ciudadano.objects.count(), antes)

    def test_identidad_ausente_o_nn_no_se_infiere_de_otro_hospital(self):
        otra = Institucion.objects.create(nombre="Otro hospital")
        Ciudadano.objects.create(institucion=otra, nombre="Otra", documento=self.afiliado.documento)
        self.paciente.documento = "DISTINTO"
        self.paciente.save(update_fields=["documento"])
        self.manual()
        self.assertEqual(self.ficha().status_code, 200)
        self.assertIsNone(AccesoClinico.objects.latest("pk").ciudadano_id)
        self.afiliado.documento = "NN"
        self.afiliado.save(update_fields=["documento"])
        self.paciente.documento = "NN"
        self.paciente.save(update_fields=["documento"])
        self.assertEqual(self.ficha().status_code, 200)
        self.assertIsNone(AccesoClinico.objects.latest("pk").ciudadano_id)

    def test_reenvio_no_se_ofrece_con_convenio_futuro_o_plazo_vencido(self):
        solicitud = self.manual()
        solicitud.estado = "observada"
        solicitud.save(update_fields=["estado"])
        self.convenio.aceptado_en = timezone.now() + timedelta(days=1)
        self.convenio.save(update_fields=["aceptado_en"])
        # Consultar el serializer directamente: un convenio futuro recorta también el listado.
        from .api_autorizaciones import consulta_solicitudes, SolicitudAutorizacionSerializer
        def puede():
            obj = consulta_solicitudes().get(pk=solicitud.pk)
            return SolicitudAutorizacionSerializer(obj, context={"puede_cargar_manual": True}).data["puede_reenviar"]
        self.assertFalse(puede())
        self.convenio.aceptado_en = timezone.now() - timedelta(days=1)
        self.convenio.save(update_fields=["aceptado_en"])
        self.assertTrue(puede())
        solicitud.plazo_respuesta = timezone.now() - timedelta(seconds=1)
        solicitud.save(update_fields=["plazo_respuesta"])
        self.assertFalse(puede())

    def test_serializer_rechaza_caso_ajeno_en_creacion_y_patch(self):
        historia = HistoriaClinica.objects.create(ciudadano=self.paciente)
        otro = Ciudadano.objects.create(institucion=self.institucion, nombre="Otro", documento="888")
        ajena = HistoriaClinica.objects.create(ciudadano=otro)
        datos = {"historia": ajena.pk, "caso": self.caso.pk, "titulo": "Ajena", "contenido": "Texto"}
        serializer = EntradaHistoriaSerializer(data=datos)
        self.assertFalse(serializer.is_valid())
        self.assertIn("caso", serializer.errors)
        entrada = EntradaHistoria.objects.create(historia=ajena, titulo="Sin caso", contenido="Texto")
        serializer = EntradaHistoriaSerializer(entrada, data={"caso": self.caso.pk}, partial=True)
        self.assertFalse(serializer.is_valid())
        serializer = EntradaHistoriaSerializer(data={**datos, "historia": historia.pk})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer = EntradaHistoriaSerializer(entrada, data={"caso": None}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class CuentasReferenciaTests(CobrosSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.org = m.Financiador.objects.create(nombre="Mutual", tipo="mutual")
        self.operador = Usuario.objects.create_user("admin@financiador.test", "x")
        self.membresia = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.operador, rol="admin")
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.client.force_authenticate(self.operador)

    def post(self, action, data):
        return self.client.post(self.base + action + "/", data, format="json")

    def test_referencia_no_se_lista_edita_ni_cuenta_como_admin(self):
        preparar_cuenta(Ambito.FINANCIADOR, "admin", financiador=self.org)
        ref = m.MembresiaFinanciador.objects.get(financiador=self.org, usuario__cuenta_referencia__isnull=False)
        response = self.client.get(self.base + "usuarios/")
        self.assertEqual([f["email"] for f in response.data], [self.operador.email])
        self.assertEqual(self.post("usuarios", {"email": ref.usuario.email, "nombre": "Técnica", "rol": "operador"}).status_code, 400)
        self.assertEqual(self.post("usuarios", {"email": self.operador.email, "nombre": "Admin", "rol": "operador"}).status_code, 400)
        self.membresia.refresh_from_db()
        ref.refresh_from_db()
        self.assertEqual(self.membresia.rol, "admin")
        self.assertEqual(ref.rol, "admin")

    def test_alteracion_de_capacidades_invalida_referencia(self):
        preparar_cuenta(Ambito.FINANCIADOR, "operador", financiador=self.org)
        ref = m.MembresiaFinanciador.objects.get(financiador=self.org, usuario__cuenta_referencia__isnull=False).usuario.cuenta_referencia
        self.assertIsNone(problema_de_cuenta(ref))
        m.MembresiaFinanciador.objects.filter(usuario=ref.usuario).update(resuelve_autorizaciones=False)
        self.assertIsNotNone(problema_de_cuenta(ref))

    def test_membresia_institucional_tecnica_no_es_editable(self):
        preparar_cuenta(Ambito.INSTITUCION, "admin", institucion=self.institucion)
        ref = Membresia.objects.get(institucion=self.institucion, usuario__cuenta_referencia__isnull=False)
        serializer = MembresiaSerializer(ref, data={"activo": False}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("usuario", serializer.errors)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.patch(f"/api/membresias/{ref.pk}/", {"activo": False}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/membresias/{ref.pk}/").status_code, 404)

        # La cuenta técnica sí necesita leer su propia membresía para la selección de áreas.
        self.client.force_authenticate(ref.usuario)
        response = self.client.get("/api/membresias/", {"usuario": ref.usuario_id})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([fila["id"] for fila in response.data["results"]], [ref.pk])


@skipUnless(connection.vendor == "postgresql", "Requiere conexiones independientes de PostgreSQL.")
class ConcurrenciaInicioTests(ManualSetup, TransactionTestCase):
    def test_lecturas_paralelas_del_inicio_persisten_todas_las_auditorias(self):
        self.manual(urgente=True)
        barrera = Barrier(6)
        filtros = [{"urgente": "true"}, {"estado": "pendiente"}, {"grupo": "resueltas"}] * 2

        def consultar(filtro):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(Usuario.objects.get(pk=self.operador.pk))
                barrera.wait(timeout=15)
                respuesta = cliente.get(self.url, {"financiador": self.financiador.pk, **filtro})
                return respuesta.status_code
            finally:
                close_old_connections()

        antes = m.EventoCobertura.objects.filter(accion="consultar_autorizaciones").count()
        with ThreadPoolExecutor(max_workers=6) as pool:
            resultados = list(pool.map(consultar, filtros))
        self.assertEqual(resultados, [200] * 6)
        self.assertEqual(m.EventoCobertura.objects.filter(accion="consultar_autorizaciones").count(), antes + 6)
        self.assertEqual(AccesoClinico.objects.filter(recurso="solicitudautorizacion").count(), 4)

    def test_degradaciones_paralelas_preservan_un_admin_real(self):
        self.membresia.rol = "admin"
        self.membresia.save(update_fields=["rol"])
        otro = Usuario.objects.create_user("otro-admin@financiador.test", "x")
        m.MembresiaFinanciador.objects.create(usuario=otro, financiador=self.financiador, rol="admin")
        preparar_cuenta(Ambito.FINANCIADOR, "admin", financiador=self.financiador)
        barrera = Barrier(2)

        def degradar(pk):
            close_old_connections()
            try:
                user = Usuario.objects.get(pk=pk)
                cliente = APIClient()
                cliente.force_authenticate(user)
                barrera.wait(timeout=15)
                return cliente.post(f"/api/financiadores/{self.financiador.pk}/usuarios/",
                    {"email": user.email, "nombre": "Admin", "rol": "operador"}, format="json").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(degradar, [self.operador.pk, otro.pk]))
        self.assertEqual(sorted(resultados), [201, 400])
        self.assertEqual(m.MembresiaFinanciador.objects.filter(financiador=self.financiador,
            activo=True, rol="admin", usuario__cuenta_referencia__isnull=True).count(), 1)
