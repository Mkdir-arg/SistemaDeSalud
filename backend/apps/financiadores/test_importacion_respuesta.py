"""Contrato HTTP, persistencia y recuperación de confirmaciones OSTEL."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Usuario
from . import ostel_importacion
from .importacion_respuesta import huella_lote
from .models import Afiliado, EventoCobertura, Financiador, HistorialAfiliacion, Importacion, MembresiaFinanciador
from .ostel_synthetic import Lote, _persona, generar_xlsx


class DatosRespuesta:
    def setUp(self):
        self.org = Financiador.objects.create(nombre="Respuesta OSTEL ficticia", tipo="obra_social")
        self.usuario = Usuario.objects.create_user("respuesta-182@example.invalid", nombre="Operador ficticio")
        self.membresia = MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.usuario, rol="operador")
        self.client = APIClient()
        self.client.force_authenticate(self.usuario)
        self.url = f"/api/financiadores/{self.org.pk}/confirmar-importacion/"

    def preview(self, cantidad=1, cambios=None):
        filas = tuple(_persona(n, NUMERO=f"RESP-{n:05d}", **(cambios or {}).get(n, {}))
                      for n in range(1, cantidad + 1))
        return ostel_importacion.previsualizar(financiador=self.org, usuario=self.usuario,
            archivo=BytesIO(generar_xlsx(Lote("respuesta-ficticia", filas))), clave=uuid4(),
            cobertura_habilitada=False)

    def confirmar(self, lote, **datos):
        return self.client.post(self.url, {"importacion": lote.pk, **datos}, format="json")


class RespuestaImportacionTests(DatosRespuesta, TestCase):
    def test_openapi_real_publica_ambas_respuestas_sin_exigir_huella_tradicional(self):
        from drf_spectacular.generators import SchemaGenerator

        schema = SchemaGenerator().get_schema(public=True)
        operation = next(value["post"] for path, value in schema["paths"].items()
                         if path.endswith("/confirmar-importacion/"))
        components = schema["components"]["schemas"]
        response = operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(response["$ref"].split("/")[-1], "ConfirmacionImportacionRespuesta")
        variants = components["ConfirmacionImportacionRespuesta"]["oneOf"]
        self.assertEqual(len(variants), 2)
        completa, cambios = [components[item["$ref"].split("/")[-1]] for item in variants]
        self.assertIn("filas", completa["required"])
        self.assertNotIn("huella_lote", completa["required"])
        self.assertNotIn("modo_respuesta", completa["required"])
        self.assertNotIn("filas", cambios["properties"])
        for campo in ("huella_lote", "base_huella", "modo_respuesta", "filas_cambiadas"):
            self.assertIn(campo, cambios["required"])
        request = operation["requestBody"]["content"]["application/json"]["schema"]
        cuerpo = components[request["$ref"].split("/")[-1]]
        self.assertEqual(cuerpo["properties"]["modo_respuesta"]["default"], "completa")
        self.assertNotIn("huella_lote", cuerpo["required"])

    def test_respuesta_tradicional_y_reintento_conservan_contrato_e_historial(self):
        lote = self.preview()
        respuesta = self.confirmar(lote)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(set(respuesta.data), {"id", "tipo", "version", "estado", "resumen", "filas", "creado", "columnas"})
        historial = HistorialAfiliacion.objects.count()
        self.confirmar(lote)
        self.assertEqual(Afiliado.objects.count(), 1)
        self.assertFalse(Afiliado.objects.get().cobertura_habilitada)
        self.assertEqual(HistorialAfiliacion.objects.count(), historial)

    def test_primera_tanda_completa_y_siguiente_solo_cambios(self):
        lote = self.preview(102)
        original = deepcopy(lote.filas[-1]["original"])
        primera = self.confirmar(lote, modo_respuesta="cambios")
        self.assertEqual(primera.status_code, 200, primera.data)
        self.assertEqual(primera.data["modo_respuesta"], "completa")
        self.assertEqual(primera.data["resumen"]["aplicada"], 100)
        segunda = self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera.data["huella_lote"])
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(segunda.data["modo_respuesta"], "cambios")
        self.assertNotIn("filas", segunda.data)
        self.assertEqual(segunda.data["base_huella"], primera.data["huella_lote"])
        self.assertEqual([f["fila"] for f in segunda.data["filas_cambiadas"]], [101, 102])
        self.assertEqual(segunda.data["filas_cambiadas"][-1]["original"], original)
        self.assertEqual(segunda["Cache-Control"], "private, no-store")
        self.assertEqual(Afiliado.objects.count(), 102)

    def test_respuesta_perdida_recupera_lote_completo_sin_repetir_efectos(self):
        lote = self.preview(101)
        primera = self.confirmar(lote, modo_respuesta="cambios").data
        self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"])
        historial = HistorialAfiliacion.objects.count()
        recuperada = self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"])
        self.assertEqual(recuperada.status_code, 200, recuperada.data)
        self.assertEqual(recuperada.data["modo_respuesta"], "completa")
        self.assertEqual(recuperada.data["resumen"]["aplicada"], 101)
        self.assertTrue(all(f["estado"] == "aplicada" for f in recuperada.data["filas"]))
        self.assertEqual(Afiliado.objects.count(), 101)
        self.assertEqual(HistorialAfiliacion.objects.count(), historial)

    def test_cambios_conservan_columnas_errores_advertencias_y_exclusion(self):
        from datetime import date
        from .serializers import ImportacionSerializer

        lote = self.preview(104, cambios={102: {"EMAIL1": "correo-invalido"},
            103: {"CUIL": "123"}, 104: {"FECBAJ": date(2020, 1, 1)}})
        fila = lote.filas[100]
        ostel_importacion.subsanar(importacion=lote, usuario=self.usuario, fila=fila["fila"],
            revision=fila["revision"], datos=fila["datos"], motivo="Exclusión ficticia verificada", accion="omitir")
        primera = self.confirmar(lote, modo_respuesta="cambios").data
        segunda = self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"]).data
        self.assertEqual(segunda["modo_respuesta"], "cambios")
        self.assertEqual(segunda["columnas"], primera["columnas"])
        self.assertEqual(len(segunda["columnas"]), 40)
        self.assertEqual([f["fila"] for f in segunda["filas_cambiadas"]], [102])
        advertida = segunda["filas_cambiadas"][0]
        self.assertIn("email", advertida["advertidos"])
        self.assertTrue(advertida["advertencias"])
        self.assertEqual(advertida["original"]["EMAIL1"], "correo-invalido")
        self.assertEqual(len(advertida["original"]), 40)
        self.assertEqual(primera["filas"][100]["estado"], "omitida")
        self.assertIn("CUIL", primera["filas"][102]["columnas_error"])
        self.assertIn("FECBAJ", primera["filas"][103]["columnas_bloqueo"])
        cambiadas = {f["fila"]: f for f in segunda["filas_cambiadas"]}
        reconstruido = {**segunda, "filas": [cambiadas.get(f["fila"], f) for f in primera["filas"]]}
        lote.refresh_from_db()
        esperado = ImportacionSerializer(lote).data
        self.assertEqual({k: reconstruido[k] for k in esperado}, esperado)

    def test_subsanacion_ajena_invalida_base_y_preserva_motivo_y_original(self):
        lote = self.preview(101)
        primera = self.confirmar(lote, modo_respuesta="cambios").data
        fila = primera["filas"][-1]
        ostel_importacion.subsanar(importacion=lote, usuario=self.usuario, fila=fila["fila"],
            revision=fila["revision"], datos=fila["datos"], motivo="Exclusión ficticia verificada", accion="omitir")
        actual = self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"])
        self.assertEqual(actual.status_code, 200, actual.data)
        self.assertEqual(actual.data["modo_respuesta"], "completa")
        ultima = actual.data["filas"][-1]
        self.assertEqual(ultima["estado"], "omitida")
        self.assertEqual(ultima["original"], fila["original"])
        self.assertEqual(ultima["correcciones"][-1]["motivo"], "Exclusión ficticia verificada")
        self.assertEqual(Afiliado.objects.count(), 100)

    def test_error_tecnico_revierte_tanda_y_reintento_es_seguro(self):
        lote = self.preview(2)
        registrar = ostel_importacion.registrar_afiliado
        intentos = []

        def falla_segunda(**datos):
            intentos.append(datos["documento"])
            if len(intentos) == 2:
                raise RuntimeError("Corte ficticio antes de confirmar tanda")
            return registrar(**datos)

        with patch.object(ostel_importacion, "registrar_afiliado", side_effect=falla_segunda):
            with self.assertRaises(RuntimeError):
                self.confirmar(lote, modo_respuesta="cambios")
        self.assertEqual(Afiliado.objects.count(), 0)
        self.assertEqual(HistorialAfiliacion.objects.count(), 0)
        lote.refresh_from_db()
        self.assertEqual(lote.resumen["aplicada"], 0)
        self.assertEqual(self.confirmar(lote, modo_respuesta="cambios").data["resumen"]["aplicada"], 2)

    def test_fallo_auditoria_revierte_solo_ultima_tanda(self):
        lote = self.preview(101)
        primera = self.confirmar(lote, modo_respuesta="cambios").data
        historial = HistorialAfiliacion.objects.count()
        with patch.object(ostel_importacion, "auditar", side_effect=RuntimeError("Auditoría ficticia fallida")):
            with self.assertRaises(RuntimeError):
                self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"])
        self.assertEqual(Afiliado.objects.count(), 100)
        self.assertEqual(HistorialAfiliacion.objects.count(), historial)
        lote.refresh_from_db()
        self.assertEqual(lote.resumen["aplicada"], 100)
        final = self.confirmar(lote, modo_respuesta="cambios", huella_lote=primera["huella_lote"])
        self.assertEqual(final.data["resumen"]["aplicada"], 101)
        self.assertEqual(len(final.data["filas_cambiadas"]), 1)

    def test_error_al_formatear_no_desmiente_commit_y_se_recupera(self):
        lote = self.preview(2)
        with patch("apps.financiadores.importacion_respuesta.marcar_respuesta", side_effect=RuntimeError("Corte de respuesta ficticio")):
            with self.assertRaises(RuntimeError):
                self.confirmar(lote, modo_respuesta="cambios")
        self.assertEqual(Afiliado.objects.count(), 2)
        recuperada = self.confirmar(lote, modo_respuesta="cambios")
        self.assertEqual(recuperada.data["modo_respuesta"], "completa")
        self.assertEqual(recuperada.data["resumen"]["aplicada"], 2)

    def test_permisos_ambito_y_entrada_invalida_no_aplican(self):
        lote = self.preview()
        for cuerpo in ({"modo_respuesta": "desconocido"}, {"modo_respuesta": "cambios", "huella_lote": "invalida"}):
            self.assertEqual(self.confirmar(lote, **cuerpo).status_code, 400)
        ajena = Financiador.objects.create(nombre="Otra ficticia", tipo="mutual")
        respuesta = self.client.post(f"/api/financiadores/{ajena.pk}/confirmar-importacion/",
            {"importacion": lote.pk, "modo_respuesta": "cambios"}, format="json")
        self.assertEqual(respuesta.status_code, 404)
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.confirmar(lote, modo_respuesta="cambios").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.confirmar(lote, modo_respuesta="cambios").status_code, 401)
        self.assertFalse(Afiliado.objects.exists())
        self.assertFalse(EventoCobertura.objects.filter(accion="aplicar_ostel").exists())

    def test_formato_generico_no_admite_modo_delta(self):
        lote = self.preview()
        lote.version = 2
        lote.save(update_fields=["version"])
        self.assertEqual(self.confirmar(lote, modo_respuesta="cambios").status_code, 400)
        self.assertFalse(Afiliado.objects.exists())


@skipUnless(connection.vendor == "postgresql", "El control de locks exige PostgreSQL.")
class RespuestaConcurrenteTests(DatosRespuesta, TransactionTestCase):
    def test_dos_clientes_con_misma_base_aplican_una_vez_y_resincronizan(self):
        lote = self.preview(2)
        base = huella_lote(lote)
        barrera = Barrier(2)

        def confirmar():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(Usuario.objects.get(pk=self.usuario.pk))
                barrera.wait(timeout=15)
                respuesta = client.post(self.url, {"importacion": lote.pk, "modo_respuesta": "cambios",
                                                  "huella_lote": base}, format="json")
                return respuesta.status_code, respuesta.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as procesos:
            tareas = [procesos.submit(confirmar) for _ in range(2)]
            resultados = [tarea.result(timeout=45) for tarea in tareas]
        self.assertEqual([status for status, _ in resultados], [200, 200])
        self.assertEqual({data["modo_respuesta"] for _, data in resultados}, {"completa", "cambios"})
        self.assertTrue(all(data["resumen"]["aplicada"] == 2 for _, data in resultados))
        self.assertEqual(Afiliado.objects.count(), 2)
        historial = HistorialAfiliacion.objects.count()
        self.confirmar(lote, modo_respuesta="cambios")
        self.assertEqual(HistorialAfiliacion.objects.count(), historial)
