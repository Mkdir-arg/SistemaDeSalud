"""JWT, comando periódico y migración sobre datos anteriores enteramente ficticios."""
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import caches
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano
from .contrato import validar_catalogo
from .issue136_test_puros import catalogo_ficticio
from .models import Catalogo, Lugar
from .servicios import ambito, resolver
from .sincronizacion import sincronizar


class GeografiaJWTTest(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.clave = uuid4().hex
        self.usuario = Usuario.objects.create_user("jwt136@example.invalid", self.clave)
        self.inst = Institucion.objects.create(nombre="Institución JWT ficticia")
        self.otra = Institucion.objects.create(nombre="Otra institución JWT ficticia")
        self.miembro = Membresia.objects.create(usuario=self.usuario, institucion=self.inst, rol="medico")
        self.paciente = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente JWT ficticio")

    def login(self):
        respuesta = self.client.post("/api/auth/token/", {"email": self.usuario.email, "password": self.clave}, format="json")
        # No incluir tokens ni credenciales en mensajes de fallo.
        self.assertEqual(respuesta.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + respuesta.data["access"])
        return respuesta.data

    def test_login_guardado_reapertura_y_logout_revoca_access(self):
        par = self.login()
        url = f"/api/ciudadanos/{self.paciente.pk}/"
        respuesta = self.client.patch(url, {"geografia": {"localidad": {"manual": "Lugar JWT ficticio"}}}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        lectura = self.client.get(url)
        self.assertEqual(lectura.status_code, 200)
        self.assertEqual(lectura.data["geografia"]["localidad"]["origen"], "manual")
        salida = self.client.post("/api/auth/logout/", {"refresh": par["refresh"]}, format="json")
        self.assertEqual(salida.status_code, 204)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get("/api/geografia/estado/").status_code, 401)

    def test_jwt_no_habilita_referencia_manual_de_otra_organizacion(self):
        ajena = resolver({"localidad": {"manual": "Lugar JWT privado ajeno"}}, dueno=ambito(institucion_id=self.otra.pk))
        self.login()
        respuesta = self.client.patch(f"/api/ciudadanos/{self.paciente.pk}/",
            {"geografia": {"localidad": {"id": ajena.localidad_id}}}, format="json")
        self.assertEqual(respuesta.status_code, 400)
        self.paciente.refresh_from_db()
        self.assertIsNone(self.paciente.geografia_id)

    def test_baja_y_reactivacion_no_rehabilitan_la_sesion_anterior(self):
        self.login()
        params = {"tipo": "localidad", "ambito": "institucion", "organizacion": self.inst.pk}
        url = "/api/geografia/lugares/"
        self.assertEqual(self.client.get(url, params).status_code, 200)
        self.miembro.activo = False
        self.miembro.save()
        self.assertEqual(self.client.get(url, params).status_code, 403)
        self.miembro.activo = True
        self.miembro.save()
        self.assertEqual(self.client.get(url, params).status_code, 403)
        self.login()
        self.assertEqual(self.client.get(url, params).status_code, 200)


class WorkerGeografiaTest(TestCase):
    modulo = "apps.geografia.management.commands.sincronizar_geografia"

    def test_carga_inicial_periodica_publica_y_espera_fuera_de_transaccion(self):
        # TestCase abre una transacción externa: se verifica que el comando no
        # deja un atomic propio abierto al llegar a su espera, comparando profundidad.
        profundidad = len(connection.atomic_blocks)
        def esperar(segundos):
            self.assertEqual(segundos, 3600)
            self.assertEqual(len(connection.atomic_blocks), profundidad)
            raise KeyboardInterrupt
        def cargar(**kwargs):
            return sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()), **kwargs)
        salida = StringIO()
        with patch(self.modulo + ".sincronizar", side_effect=cargar), patch(self.modulo + ".time.sleep", side_effect=esperar):
            with self.assertRaises(KeyboardInterrupt):
                call_command("sincronizar_geografia", periodico=True, stdout=salida)
        self.assertEqual(Catalogo.objects.get(pk=1).version, 1)
        self.assertEqual(Lugar.objects.filter(activo=True).count(), 4)
        self.assertIn("publicado=True", salida.getvalue())

    def test_catalogo_reciente_no_se_descarga_de_nuevo(self):
        sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()))
        with patch(self.modulo + ".sincronizar") as cargar, patch(self.modulo + ".time.sleep", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                call_command("sincronizar_geografia", periodico=True, stdout=StringIO())
        cargar.assert_not_called()

    def test_fallo_periodico_conserva_catalogo_y_no_reintenta_cada_hora(self):
        sincronizar(descargar_fn=lambda: validar_catalogo(catalogo_ficticio()))
        Catalogo.objects.filter(pk=1).update(actualizado=timezone.now() - timedelta(days=8), intento=None)
        def fallar():
            raise ValueError("Falla sintética de origen")
        def cargar(**kwargs):
            return sincronizar(descargar_fn=fallar, **kwargs)
        errores = StringIO()
        with patch(self.modulo + ".sincronizar", side_effect=cargar) as intento, patch(self.modulo + ".time.sleep", side_effect=[None, KeyboardInterrupt]):
            with self.assertRaises(KeyboardInterrupt):
                call_command("sincronizar_geografia", periodico=True, stderr=errores, stdout=StringIO())
        self.assertEqual(intento.call_count, 1)
        self.assertEqual(Catalogo.objects.get(pk=1).version, 1)
        self.assertTrue(Catalogo.objects.get(pk=1).error)
        self.assertEqual(Lugar.objects.filter(activo=True).count(), 4)
        self.assertIn("se conserva el catálogo anterior", errores.getvalue())


class MigracionLegadoGeografiaTest(TransactionTestCase):
    def test_migraciones_aditivas_preservan_textos_y_coordenadas_sin_backfill(self):
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes()
        anteriores = [("geografia", None), ("instituciones", "0011_box_aviso_inactividad"),
            ("registros", "0012_archivo_clinico_dueno"), ("financiadores", "0015_codigo_financiador")]
        try:
            executor.migrate(anteriores)
            # La app inexistente se excluye al calcular el estado histórico.
            estado = executor.loader.project_state([n for n in anteriores if n[1] is not None]).apps
            InstitucionAnterior = estado.get_model("instituciones", "Institucion")
            PacienteAnterior = estado.get_model("registros", "Ciudadano")
            FinanciadorAnterior = estado.get_model("financiadores", "Financiador")
            AfiliadoAnterior = estado.get_model("financiadores", "Afiliado")
            inst = InstitucionAnterior.objects.create(nombre="Institución legado ficticia", direccion="Dirección legado ficticia",
                latitud=-34.12345678, longitud=-58.87654321)
            paciente = PacienteAnterior.objects.create(institucion_id=inst.pk, nombre="Paciente legado ficticio", domicilio="Domicilio legado ficticio")
            fin = FinanciadorAnterior.objects.create(nombre="Financiador legado ficticio", tipo="mutual")
            afiliado = AfiliadoAnterior.objects.create(financiador_id=fin.pk, numero="00136", documento="99900136",
                nombre="Afiliado legado ficticio", desde=date(2026, 1, 1), provincia="Provincia legado",
                partido="Partido legado", localidad="Localidad legado", domicilio_laboral="Trabajo legado")
            MigrationExecutor(connection).migrate(finales)
            from apps.financiadores.models import Afiliado
            inst_actual = Institucion.objects.get(pk=inst.pk)
            paciente_actual = Ciudadano.objects.get(pk=paciente.pk)
            afiliado_actual = Afiliado.objects.get(pk=afiliado.pk)
            self.assertEqual(inst_actual.direccion, "Dirección legado ficticia")
            self.assertEqual((inst_actual.latitud, inst_actual.longitud), (-34.12345678, -58.87654321))
            self.assertEqual(paciente_actual.domicilio, "Domicilio legado ficticio")
            self.assertEqual((afiliado_actual.numero, afiliado_actual.provincia, afiliado_actual.partido,
                afiliado_actual.localidad, afiliado_actual.domicilio_laboral),
                ("00136", "Provincia legado", "Partido legado", "Localidad legado", "Trabajo legado"))
            for obj in (inst_actual, paciente_actual, afiliado_actual):
                self.assertIsNone(obj.geografia_id)
            self.assertIsNone(afiliado_actual.geografia_laboral_id)
            self.assertFalse(Lugar.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(finales)
