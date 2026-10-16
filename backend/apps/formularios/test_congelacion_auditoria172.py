"""AUD-012: toda definición usada queda congelada y se duplica para cambiarla."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from importlib import import_module
from types import SimpleNamespace
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Usuario
from apps.casos.models import Caso, ValorCampo
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion

from .models import Campo, Formulario
from .views import CampoViewSet, FormularioViewSet


class EscenarioFormulario:
    def preparar(self):
        self.usuario = Usuario.objects.create_superuser("congelacion@example.test", "x")
        self.inst = Institucion.objects.create(nombre="Formulario sintético")
        self.area = Area.objects.create(institucion=self.inst, nombre="Área sintética")
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Definición sintética")
        self.campo = Campo.objects.create(formulario=self.form, label="Campo sintético", tipo="numero", orden=0)
        self.otro = Campo.objects.create(formulario=self.form, label="Segundo sintético", tipo="texto_corto", orden=1)
        flujo = Flujo.objects.create(institucion=self.inst, titulo="Circuito sintético")
        self.version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        inicio = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        self.nodo = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.FORMULARIO, titulo="Carga", formulario=self.form)
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=self.version, origen=inicio, destino=self.nodo)
        Conexion.objects.create(version=self.version, origen=self.nodo, destino=fin)

    def cliente(self):
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        return cliente

    def publicar(self):
        respuesta = self.cliente().post(f"/api/versiones-flujo/{self.version.pk}/publicar/", {}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)


class CongelacionFormularioAuditoria172Tests(EscenarioFormulario, APITestCase):
    def setUp(self):
        self.preparar()

    def test_publicacion_expone_marca_y_bloquea_todos_los_metadatos(self):
        self.publicar()
        url = f"/api/formularios/{self.form.pk}/"
        respuesta = self.cliente().get(url)
        self.assertTrue(respuesta.data.get("congelado_at"), respuesta.data)
        for cambios in ({"titulo": "Cambio"}, {"descripcion": "Cambio"}, {"area": self.area.pk}):
            with self.subTest(cambios=cambios):
                respuesta = self.cliente().patch(url, cambios, format="json")
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self.cliente().patch(url, {"titulo": self.form.titulo}, format="json").status_code, 200)

    def test_toda_la_definicion_del_campo_se_congela(self):
        seleccion = Campo.objects.create(formulario=self.form, label="Selección sintética",
                                          tipo="seleccion_unica", opciones=["Uno"], orden=2)
        self.publicar()
        for clave, valor in (("label", "Cambio"), ("ayuda", "Ayuda nueva"), ("orden", 4),
                             ("requerido", True), ("unidad", "mg"), ("minimo", 1), ("maximo", 10),
                             ("origen", "historia_clinica"), ("tipo", "texto_largo")):
            with self.subTest(campo=clave):
                respuesta = self.cliente().patch(f"/api/campos/{self.campo.pk}/", {clave: valor}, format="json")
                self.assertEqual(respuesta.status_code, 409, respuesta.data)
        respuesta = self.cliente().patch(f"/api/campos/{seleccion.pk}/", {"opciones": ["Uno", "Dos"]}, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self.cliente().patch(f"/api/campos/{self.campo.pk}/", {"label": self.campo.label}, format="json").status_code, 200)

    def test_congelado_impide_altas_bajas_y_reorden_real_permite_identico(self):
        self.publicar()
        cliente = self.cliente()
        respuesta = cliente.post("/api/campos/", {"formulario": self.form.pk, "label": "Nuevo", "tipo": "texto_corto"}, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(cliente.delete(f"/api/campos/{self.campo.pk}/").status_code, 409)
        self.assertEqual(cliente.delete(f"/api/formularios/{self.form.pk}/").status_code, 409)
        url = f"/api/formularios/{self.form.pk}/reordenar/"
        self.assertEqual(cliente.post(url, {"campos": [self.otro.pk, self.campo.pk]}, format="json").status_code, 409)
        self.assertEqual(cliente.post(url, {"campos": [self.campo.pk, self.otro.pk]}, format="json").status_code, 200)

    def test_duplicar_congelado_copia_definicion_descongelada_con_ids_nuevos(self):
        self.publicar()
        respuesta = self.cliente().post(f"/api/formularios/{self.form.pk}/duplicar/", {}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertIn("congelado_at", respuesta.data)
        self.assertIsNone(respuesta.data["congelado_at"])
        copia = Formulario.objects.get(pk=respuesta.data["id"])
        campos = list(copia.campos.order_by("orden"))
        self.assertEqual([c.label for c in campos], [self.campo.label, self.otro.label])
        self.assertTrue({c.pk for c in campos}.isdisjoint({self.campo.pk, self.otro.pk}))
        self.assertFalse(any(c.valores.exists() for c in campos))
        self.assertEqual(self.cliente().patch(f"/api/formularios/{copia.pk}/", {"titulo": "Nueva definición"}, format="json").status_code, 200)

    def test_marca_no_se_revierte_desde_patch(self):
        self.publicar()
        url = f"/api/formularios/{self.form.pk}/"
        antes = self.cliente().get(url).data.get("congelado_at")
        respuesta = self.cliente().patch(url, {"congelado_at": None}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(antes)
        self.assertEqual(respuesta.data["congelado_at"], antes)


@skipUnless(connection.vendor == "postgresql", "Requiere dos conexiones PostgreSQL")
class CongelacionConcurrenteAuditoria172Tests(EscenarioFormulario, TransactionTestCase):
    def setUp(self):
        self.preparar()

    def test_edicion_validada_antes_de_publicar_no_cambia_campo_despues(self):
        leido, continuar = Event(), Event()
        original, hilo = CampoViewSet.perform_update, {}

        def pausar(view, serializer):
            if get_ident() == hilo.get("id"):
                leido.set()
                if not continuar.wait(10):
                    raise AssertionError("Timeout de edición sintética")
            return original(view, serializer)

        def editar():
            try:
                hilo["id"] = get_ident()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                respuesta = self.cliente().patch(f"/api/campos/{self.campo.pk}/", {"label": "No leído al publicar"}, format="json")
                return respuesta.status_code
            finally:
                connections.close_all()

        with patch.object(CampoViewSet, "perform_update", pausar):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(editar)
                try:
                    self.assertTrue(leido.wait(10))
                    self.publicar()
                finally:
                    continuar.set()
                self.assertEqual(futuro.result(timeout=12), 409)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Campo sintético")


    def test_duplicado_relee_metadatos_y_campos_tras_edicion_concurrente(self):
        leido, continuar = Event(), Event()
        original, hilo = FormularioViewSet.get_object, {}

        def pausar(view):
            objeto = original(view)
            if get_ident() == hilo.get("id"):
                leido.set()
                if not continuar.wait(10):
                    raise AssertionError("Timeout de duplicación sintética")
            return objeto

        def duplicar():
            try:
                hilo["id"] = get_ident()
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '8s'")
                respuesta = self.cliente().post(f"/api/formularios/{self.form.pk}/duplicar/", {}, format="json")
                return respuesta.status_code, respuesta.data
            finally:
                connections.close_all()

        with patch.object(FormularioViewSet, "get_object", pausar):
            with ThreadPoolExecutor(max_workers=1) as pool:
                futuro = pool.submit(duplicar)
                try:
                    self.assertTrue(leido.wait(10))
                    cliente = self.cliente()
                    self.assertEqual(cliente.patch(f"/api/formularios/{self.form.pk}/", {"titulo": "Definición actual"}, format="json").status_code, 200)
                    self.assertEqual(cliente.patch(f"/api/campos/{self.campo.pk}/", {"label": "Campo actual"}, format="json").status_code, 200)
                finally:
                    continuar.set()
                codigo, datos = futuro.result(timeout=12)
        self.assertEqual(codigo, 201, datos)
        self.assertEqual(datos["titulo"], "Definición actual (copia)")
        self.assertEqual(datos["campos"][0]["label"], "Campo actual")


@skipUnless(connection.vendor == "postgresql", "Prueba migración histórica PostgreSQL")
class CongelacionLegacyAuditoria172Tests(TransactionTestCase):
    anterior = ("formularios", "0003_alter_campo_tipo")
    nueva = ("formularios", "0004_formulario_congelado_at")

    def test_backfill_directo_indirecto_y_respuestas_no_altera_definiciones(self):
        institucion = Institucion.objects.create(nombre="Legacy sintético")
        executor = MigrationExecutor(connection)
        executor.migrate([self.anterior])
        FormularioAnterior = executor.loader.project_state([self.anterior]).apps.get_model("formularios", "Formulario")
        CampoAnterior = executor.loader.project_state([self.anterior]).apps.get_model("formularios", "Campo")
        try:
            formularios, campos = {}, {}
            nombres = ("directo", "reemplazado", "archivado", "integracion", "prioridad", "condicion", "respuesta", "borrador", "libre")
            for nombre in nombres:
                form = FormularioAnterior.objects.create(institucion_id=institucion.pk, titulo=nombre)
                formularios[nombre] = form.pk
                campo = CampoAnterior.objects.create(formulario_id=form.pk, label=nombre, tipo="texto_corto")
                campos[nombre] = campo.pk
            flujo = Flujo.objects.create(institucion=institucion, titulo="Legacy circuito")
            versiones = {}
            for numero, estado in enumerate(("publicada", "reemplazada", "archivada", "borrador"), 1):
                versiones[estado] = VersionFlujo.objects.create(flujo=flujo, numero=numero, estado=estado)
            for nombre, estado in (("directo", "publicada"), ("reemplazado", "reemplazada"), ("archivado", "archivada"), ("borrador", "borrador")):
                Nodo.objects.create(version=versiones[estado], tipo=Nodo.Tipo.FORMULARIO, titulo=nombre, formulario_id=formularios[nombre])
            uno = Nodo.objects.create(version=versiones["archivada"], tipo="integracion", titulo="Indirecta",
                                      config={"guardar_en": str(campos["integracion"]), "prioridad_campo": float(campos["prioridad"])})
            dos = Nodo.objects.create(version=versiones["archivada"], tipo="fin", titulo="Fin")
            Conexion.objects.create(version=versiones["archivada"], origen=uno, destino=dos,
                                    condicion={"reglas": [{"reglas": [{"campo": str(campos["condicion"])}]}, None, {"campo": "inválido"}]})
            caso = Caso.objects.create(institucion=institucion, version=versiones["borrador"])
            ValorCampo.objects.create(caso=caso, campo_id=campos["respuesta"], valor="Dato sintético")
            definiciones = list(CampoAnterior.objects.order_by("pk").values())
            respuestas = list(ValorCampo.objects.order_by("pk").values())
            metadatos = list(FormularioAnterior.objects.order_by("pk").values())
            MigrationExecutor(connection).migrate([self.nueva])
            marcados = set(Formulario.objects.filter(congelado_at__isnull=False).values_list("pk", flat=True))
            self.assertEqual(marcados, {pk for nombre, pk in formularios.items() if nombre not in ("borrador", "libre")})
            self.assertEqual(list(CampoAnterior.objects.order_by("pk").values()), definiciones)
            self.assertEqual(list(ValorCampo.objects.order_by("pk").values()), respuestas)
            self.assertEqual(list(FormularioAnterior.objects.order_by("pk").values()), metadatos)
            marcas = list(Formulario.objects.order_by("pk").values_list("pk", "congelado_at"))
            modulo = import_module("apps.formularios.migrations.0004_formulario_congelado_at")
            modulo.congelar_legacy(MigrationExecutor(connection).loader.project_state([self.nueva]).apps,
                                   SimpleNamespace(connection=connection))
            self.assertEqual(list(Formulario.objects.order_by("pk").values_list("pk", "congelado_at")), marcas)
        finally:
            MigrationExecutor(connection).migrate([self.nueva])

    def test_parser_historico_conserva_semantica_de_ids_del_motor(self):
        from .integridad import _campos_condicion, _entero

        modulo = import_module("apps.formularios.migrations.0004_formulario_congelado_at")
        for valor, esperado in ((True, 1), (False, 0), (" 12 ", 12), (12.5, 12), ("12.5", None), (None, None)):
            self.assertEqual(_entero(valor), esperado)
            self.assertEqual(modulo._entero(valor), esperado)
        condicion = {"reglas": [{"campo": True}, {"reglas": [{"campo": "12"}, {"campo": 15.9}]}, None]}
        self.assertEqual(_campos_condicion(condicion), {1, 12, 15})
        self.assertEqual(modulo._campos_condicion(condicion), {1, 12, 15})
