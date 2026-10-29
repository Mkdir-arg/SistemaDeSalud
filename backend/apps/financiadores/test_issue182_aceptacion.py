"""Aceptación funcional de #182: tamaños del issue, trazabilidad y reintento.

Sólo identidades construidas por el generador sintético. APIClient recorre los
endpoints y ORM reales; no mide HTTP, navegador, SLA ni capacidad productiva.
"""
from copy import deepcopy
from math import ceil
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from django.utils import timezone

from . import ostel_importacion
from .models import Afiliado, EventoCobertura, HistorialAfiliacion, Importacion
from .ostel_synthetic import Lote, _persona, generar_xlsx
from .test_importacion_respuesta import DatosRespuesta


class Aceptacion182Tests(DatosRespuesta, TransactionTestCase):
    def _previsualizar(self, cantidad, *, fuente="base"):
        contenido = generar_xlsx(Lote("aceptacion-ficticia", tuple(
            _persona(n, NUMERO=f"ACEP-{n:05d}") for n in range(1, cantidad + 1))))
        respuesta = self.client.post(f"/api/financiadores/{self.org.pk}/previsualizar-ostel/", {
            "archivo": SimpleUploadedFile("aceptacion-ficticia.xlsx", contenido),
            "clave": str(uuid4()), "fuente": fuente, "cobertura_habilitada": "false",
        }, format="multipart")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["resumen"]["total"], cantidad)
        return respuesta.data

    def _ausente(self):
        obj = Afiliado.objects.create(financiador=self.org, numero="AUSENTE-FICTICIO",
            numero_interno="AUSENTE-FICTICIO", documento="98999999", nombre="PERSONA FICTICIA AUSENTE",
            desde=timezone.localdate(), cobertura_habilitada=True)
        return obj, Afiliado.objects.filter(pk=obj.pk).values().get()

    def _conteos(self, lote):
        return (Afiliado.objects.filter(financiador=self.org).count(),
                HistorialAfiliacion.objects.filter(lote=lote).count(),
                EventoCobertura.objects.filter(financiador=self.org).count())

    def _confirmar(self, actual):
        respuesta = self.client.post(self.url, {"importacion": actual["id"], "modo_respuesta": "cambios",
            **({"huella_lote": actual["huella_lote"]} if actual.get("huella_lote") else {})}, format="json")
        self.assertEqual(respuesta.status_code, 200)
        self.assertLessEqual(respuesta.data["resumen"]["valida"], actual["resumen"]["valida"])
        return respuesta.data

    def _aplicar_volumen(self, cantidad, *, probar_cortes=False):
        ausente, valores_ausente = self._ausente()
        actual = self._previsualizar(cantidad)
        lote = Importacion.objects.get(pk=actual["id"])
        self.assertEqual(self._conteos(lote)[:2], (1, 0))  # Revisar no incorpora personas.
        self.assertEqual(lote.creado_por_id, self.usuario.pk)
        original_ultima = deepcopy(lote.filas[-1]["original"])
        self.assertEqual(len(original_ultima), 40)
        tandas = 0
        while actual["resumen"]["valida"]:
            if probar_cortes and tandas == 2:
                antes = self._conteos(lote)
                resumen = deepcopy(actual["resumen"])
                with patch.object(ostel_importacion, "auditar", side_effect=RuntimeError("Corte ficticio de tanda")):
                    with self.assertRaisesRegex(RuntimeError, "Corte ficticio de tanda"):
                        self._confirmar(actual)
                self.assertEqual(self._conteos(lote), antes)
                lote.refresh_from_db()
                self.assertEqual(lote.resumen, resumen)
            if probar_cortes and tandas == 3:
                # La aplicación termina, pero el cliente no recibe su resultado.
                with patch("apps.financiadores.importacion_respuesta.marcar_respuesta",
                           side_effect=RuntimeError("Respuesta ficticia perdida")):
                    with self.assertRaisesRegex(RuntimeError, "Respuesta ficticia perdida"):
                        self._confirmar(actual)
                tandas += 1
                self.assertEqual(Afiliado.objects.filter(financiador=self.org).count(), 1 + tandas * 100)
            previo = tandas * 100
            nueva = self._confirmar(actual)
            tandas += 1
            self.assertEqual(nueva["resumen"]["aplicada"], min(tandas * 100, cantidad))
            self.assertLessEqual(nueva["resumen"]["aplicada"] - previo, 100)
            self.assertEqual(nueva["modo_respuesta"], "completa" if tandas == 1 or (probar_cortes and tandas == 5) else "cambios")
            if nueva["modo_respuesta"] == "cambios":
                self.assertNotIn("filas", nueva)
                self.assertLessEqual(len(nueva["filas_cambiadas"]), 100)
            actual = nueva
        self.assertEqual(tandas, ceil(cantidad / 100))
        self.assertEqual(Afiliado.objects.filter(financiador=self.org).count(), cantidad + 1)
        self.assertEqual(HistorialAfiliacion.objects.filter(lote=lote).values("afiliado_id").distinct().count(), cantidad)
        self.assertFalse(HistorialAfiliacion.objects.filter(lote=lote).exclude(
            registrado_por=self.usuario, origen="importacion", afiliado__financiador=self.org).exists())
        self.assertEqual(EventoCobertura.objects.filter(financiador=self.org, accion="aplicar_ostel").count(), tandas)
        lote.refresh_from_db()
        self.assertEqual(lote.filas[-1]["original"], original_ultima)
        self.assertTrue(all(f["estado"] == "aplicada" for f in lote.filas))
        self.assertFalse(Afiliado.objects.filter(financiador=self.org).exclude(pk=ausente.pk).filter(cobertura_habilitada=True).exists())
        historial = HistorialAfiliacion.objects.filter(lote=lote).count()
        eventos_cambio = EventoCobertura.objects.filter(financiador=self.org,
            accion__in=("actualizar_padron", "editar_ficha_padron")).count()
        repetida = self._confirmar(actual)
        self.assertEqual(repetida["resumen"], actual["resumen"])
        self.assertEqual(repetida["filas_cambiadas"], [])
        self.assertEqual(Afiliado.objects.filter(financiador=self.org).count(), cantidad + 1)
        self.assertEqual(HistorialAfiliacion.objects.filter(lote=lote).count(), historial)
        self.assertEqual(EventoCobertura.objects.filter(financiador=self.org,
            accion__in=("actualizar_padron", "editar_ficha_padron")).count(), eventos_cambio)
        # Se audita el intento; no hay otro evento de alta/cambio ni otra historia.
        self.assertEqual(EventoCobertura.objects.filter(financiador=self.org, accion="aplicar_ostel").count(), tandas + 1)
        self.assertEqual(Afiliado.objects.filter(pk=ausente.pk).values().get(), valores_ausente)
        self.assertFalse(HistorialAfiliacion.objects.filter(afiliado=ausente).exists())

    def test_5754_filas_con_fallo_de_tanda_respuesta_perdida_y_reintento(self):
        self._aplicar_volumen(5754, probar_cortes=True)

    def test_7486_filas_por_tandas_sin_duplicar_efectos_ni_dar_baja_por_ausencia(self):
        self._aplicar_volumen(7486)

    def test_7486_bajas_son_evidencia_y_no_ordenes_de_aplicacion(self):
        ausente, valores = self._ausente()
        actual = self._previsualizar(7486, fuente="bajas")
        self.assertEqual(actual["resumen"]["valida"], 0)
        self.assertEqual(actual["resumen"]["revision"], 7486)
        respuesta = self._confirmar(actual)
        self.assertEqual(respuesta["resumen"]["aplicada"], 0)
        self.assertEqual(Afiliado.objects.count(), 1)
        self.assertFalse(HistorialAfiliacion.objects.exists())
        self.assertEqual(Afiliado.objects.filter(pk=ausente.pk).values().get(), valores)
        self.assertTrue(all(f["bloqueo_fuente"] and len(f["original"]) == 40 for f in respuesta["filas"]))
