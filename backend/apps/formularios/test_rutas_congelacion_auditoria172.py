"""AUD-012: publicación, respuestas y cascadas conservan la definición."""
import json
from unittest.mock import MagicMock, patch

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.forms.models import inlineformset_factory
from django.test import RequestFactory, override_settings
from rest_framework.test import APITestCase

from apps.casos import motor
from apps.casos.admin import CasoAdmin
from apps.casos.models import Caso, ValorCampo
from apps.instituciones.admin import AreaAdmin
from apps.instituciones.models import Area

from .integridad import congelar_formularios
from .models import Campo, Formulario
from .test_congelacion_auditoria172 import EscenarioFormulario


class RutasCongelacionAuditoria172Tests(EscenarioFormulario, APITestCase):
    def setUp(self):
        self.preparar()
        self.caso = Caso.objects.create(institucion=self.inst, version=self.version, nodo_actual=self.nodo)

    def test_guardar_respuesta_congela_y_eliminar_el_caso_no_descongela(self):
        motor._guardar_valores(self.caso, self.nodo, {str(self.campo.pk): "12"})
        self.form.refresh_from_db()
        marca = self.form.congelado_at
        self.assertIsNotNone(marca)
        self.assertEqual(ValorCampo.objects.get(caso=self.caso, campo=self.campo).valor, "12")
        self.caso.delete()
        self.form.refresh_from_db()
        self.assertEqual(self.form.congelado_at, marca)
        respuesta = self.cliente().patch(f"/api/campos/{self.campo.pk}/", {"label": "Distinto"}, format="json")
        self.assertEqual(respuesta.status_code, 409, respuesta.data)

    def test_respuesta_invalida_no_deja_marca_ni_respuesta(self):
        with self.assertRaises(motor.ErrorMotor):
            motor._guardar_valores(self.caso, self.nodo, {"-1": "Dato inválido"})
        self.form.refresh_from_db()
        self.assertIsNone(self.form.congelado_at)
        self.assertFalse(ValorCampo.objects.filter(caso=self.caso).exists())

    @override_settings(INTEGRACIONES_PERMITIDAS=["servicio.example.test"])
    def test_integracion_congela_su_destino_antes_de_guardar_respuesta(self):
        self.nodo.tipo = "integracion"
        self.nodo.formulario = None
        self.nodo.config = {"url": "https://servicio.example.test/resultado", "guardar_en": self.campo.pk, "ruta": "resultado"}
        self.nodo.save()
        respuesta = MagicMock()
        respuesta.__enter__.return_value.read.return_value = json.dumps({"resultado": "12"}).encode()
        with patch.object(motor, "urlopen", return_value=respuesta):
            motor._llamar_externo(self.caso, self.nodo)
        self.form.refresh_from_db()
        self.assertIsNotNone(self.form.congelado_at)
        self.assertEqual(ValorCampo.objects.get(caso=self.caso, campo=self.campo).valor, "12")

    @override_settings(INTEGRACIONES_PERMITIDAS=["servicio.example.test"])
    def test_publicacion_congela_formulario_referido_solo_por_integracion(self):
        self.nodo.tipo = "integracion"
        self.nodo.formulario = None
        self.nodo.config = {"url": "https://servicio.example.test/resultado", "guardar_en": self.campo.pk}
        self.nodo.save()
        self.publicar()
        self.form.refresh_from_db()
        self.assertIsNotNone(self.form.congelado_at)
        self.assertFalse(ValorCampo.objects.exists())

    def test_inline_de_respuestas_admin_congela_definicion(self):
        fabrica = inlineformset_factory(Caso, ValorCampo, fields=("campo", "nodo", "valor"), extra=1)
        formset = fabrica({"valores-TOTAL_FORMS": "1", "valores-INITIAL_FORMS": "0",
                           "valores-0-campo": str(self.campo.pk), "valores-0-nodo": str(self.nodo.pk),
                           "valores-0-valor": "12"}, instance=self.caso, prefix="valores")
        self.assertTrue(formset.is_valid(), formset.errors)
        request = RequestFactory().post("/admin/casos/caso/")
        request.user = self.usuario
        CasoAdmin(Caso, admin.site).save_formset(request, None, formset, True)
        self.assertTrue(ValorCampo.objects.filter(caso=self.caso, campo=self.campo).exists())
        self.form.refresh_from_db()
        self.assertIsNotNone(self.form.congelado_at)

    def test_borrado_area_api_no_modifica_formulario_congelado(self):
        Formulario.objects.filter(pk=self.form.pk).update(area=self.area)
        self.publicar()
        respuesta = self.cliente().delete(f"/api/areas/{self.area.pk}/")
        self.assertEqual(respuesta.status_code, 409, getattr(respuesta, "data", None))
        self.form.refresh_from_db()
        self.assertEqual(self.form.area_id, self.area.pk)
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())

    def test_borrado_area_admin_individual_y_bulk_conserva_formulario(self):
        Formulario.objects.filter(pk=self.form.pk).update(area=self.area)
        congelar_formularios([self.form.pk])
        request = RequestFactory().post("/admin/instituciones/area/")
        request.user = self.usuario
        administrador = AreaAdmin(Area, admin.site)
        for bulk in (False, True):
            with self.subTest(bulk=bulk), self.assertRaises(PermissionDenied):
                if bulk:
                    administrador.delete_queryset(request, Area.objects.filter(pk=self.area.pk))
                else:
                    administrador.delete_model(request, self.area)
        self.form.refresh_from_db()
        self.assertEqual(self.form.area_id, self.area.pk)

    def test_borrador_se_reasigna_antes_de_eliminar_su_area(self):
        Formulario.objects.filter(pk=self.form.pk).update(area=self.area)
        respuesta = self.cliente().delete(f"/api/areas/{self.area.pk}/")
        self.assertEqual(respuesta.status_code, 409, getattr(respuesta, "data", None))
        respuesta = self.cliente().patch(f"/api/formularios/{self.form.pk}/", {"area": None}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        respuesta = self.cliente().delete(f"/api/areas/{self.area.pk}/")
        self.assertEqual(respuesta.status_code, 204, getattr(respuesta, "data", None))

    def test_borrado_area_admin_http_conserva_definicion(self):
        Formulario.objects.filter(pk=self.form.pk).update(area=self.area)
        congelar_formularios([self.form.pk])
        self.client.force_login(self.usuario)
        respuesta = self.client.post(f"/admin/instituciones/area/{self.area.pk}/delete/", {"post": "yes"})
        self.assertEqual(respuesta.status_code, 403)
        self.form.refresh_from_db()
        self.assertEqual(self.form.area_id, self.area.pk)
