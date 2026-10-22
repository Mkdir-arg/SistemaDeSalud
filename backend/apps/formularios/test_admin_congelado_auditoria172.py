"""AUD-012: Admin no altera definiciones congeladas, ni por inlines/cascadas."""
from copy import copy

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Institucion
from .integridad import congelar_formularios
from .models import Campo, Formulario


class AdminDefinicionCongeladaAuditoria172Tests(TestCase):
    def setUp(self):
        self.actor = Usuario.objects.create_superuser("admin-formulario-sintetico@example.test", "x")
        self.client.force_login(self.actor)
        self.request = RequestFactory().post("/admin/")
        self.request.user = self.actor
        self.institucion = Institucion.objects.create(nombre="Institución sintética definición")
        self.formulario = Formulario.objects.create(institucion=self.institucion, titulo="Formulario sintético")
        self.campo = Campo.objects.create(formulario=self.formulario, label="Dato sintético", tipo="texto_corto")
        self.flujo = Flujo.objects.create(institucion=self.institucion, titulo="Flujo sintético")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.nodo = Nodo.objects.create(version=self.version, tipo="form", titulo="Paso", formulario=self.formulario)

    def congelar(self):
        with transaction.atomic():
            congelar_formularios([self.formulario.pk])
        self.formulario.refresh_from_db()

    def url(self, modelo, accion="change", pk=None):
        return reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_{accion}", args=[pk] if pk else [])

    def datos_formulario(self, **extra):
        return {"institucion": self.institucion.pk, "titulo": "Titulo cambiado", "descripcion": "",
                "campos-TOTAL_FORMS": "0", "campos-INITIAL_FORMS": "0", **extra}

    def test_formulario_borrador_sigue_editable_en_admin(self):
        respuesta = self.client.post(self.url(Formulario, pk=self.formulario.pk), self.datos_formulario())
        self.assertEqual(respuesta.status_code, 302)
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.titulo, "Titulo cambiado")
        self.assertIsNone(self.formulario.congelado_at)

    def test_formulario_congelado_y_flag_no_cambian_con_post_forjado(self):
        self.congelar()
        marca = self.formulario.congelado_at
        respuesta = self.client.post(self.url(Formulario, pk=self.formulario.pk), self.datos_formulario(congelado_at=""))
        self.assertIn(respuesta.status_code, (200, 302, 403))
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.titulo, "Formulario sintético")
        self.assertEqual(self.formulario.congelado_at, marca)

    def test_save_model_congelado_relee_y_admite_solo_noop(self):
        previo = copy(self.formulario)
        self.congelar()
        model_admin = admin.site._registry[Formulario]
        model_admin.save_model(self.request, previo, None, True)
        self.formulario.refresh_from_db()
        self.assertIsNotNone(self.formulario.congelado_at)
        previo.titulo = "Cambio denegado"
        with self.assertRaises(PermissionDenied):
            model_admin.save_model(self.request, previo, None, True)
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.titulo, "Formulario sintético")

    def test_campo_congelado_no_se_edita_directamente(self):
        self.congelar()
        self.campo.label = "Cambio denegado"
        with self.assertRaises(PermissionDenied):
            admin.site._registry[Campo].save_model(self.request, self.campo, None, True)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Dato sintético")

    def test_campo_borrador_sigue_editable(self):
        self.campo.label = "Cambio permitido"
        admin.site._registry[Campo].save_model(self.request, self.campo, None, True)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Cambio permitido")

    def test_congelados_no_se_borran_individual_ni_bulk(self):
        self.congelar()
        for modelo, objeto in ((Formulario, self.formulario), (Campo, self.campo)):
            with self.subTest(modelo=modelo.__name__):
                model_admin = admin.site._registry[modelo]
                with self.assertRaises(PermissionDenied):
                    model_admin.delete_model(self.request, objeto)
                with self.assertRaises(PermissionDenied):
                    model_admin.delete_queryset(self.request, modelo.objects.filter(pk=objeto.pk))
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())

    def test_inline_congelado_no_edita_borra_ni_agrega_campos(self):
        self.congelar()
        datos = self.datos_formulario(**{
            "campos-TOTAL_FORMS": "2", "campos-INITIAL_FORMS": "1", "campos-0-id": str(self.campo.pk),
            "campos-0-formulario": str(self.formulario.pk), "campos-0-label": "Alterado", "campos-0-tipo": "numero",
            "campos-0-DELETE": "on", "campos-1-label": "Agregado", "campos-1-tipo": "texto_corto",
        })
        respuesta = self.client.post(self.url(Formulario, pk=self.formulario.pk), datos)
        self.assertIn(respuesta.status_code, (200, 302, 403))
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Dato sintético")
        self.assertEqual(Campo.objects.filter(formulario=self.formulario).count(), 1)

    def test_inline_abierto_antes_de_congelar_revalida_en_clean(self):
        from .admin import CampoInline

        formset_tipo = CampoInline(Formulario, admin.site).get_formset(self.request, obj=self.formulario)
        datos = {"campos-TOTAL_FORMS": "1", "campos-INITIAL_FORMS": "1", "campos-0-id": self.campo.pk,
                 "campos-0-formulario": self.formulario.pk, "campos-0-label": "Edición obsoleta",
                 "campos-0-tipo": "texto_corto", "campos-0-orden": "0", "campos-0-opciones": "[]"}
        formset = formset_tipo(data=datos, instance=self.formulario)
        self.congelar()
        self.assertFalse(formset.is_valid())
        self.assertIn("congelada", str(formset.non_form_errors()))
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Dato sintético")

    def test_campo_no_se_reasigna_para_eludir_congelacion(self):
        self.congelar()
        otro = Formulario.objects.create(institucion=self.institucion, titulo="Otro borrador")
        self.campo.formulario = otro
        with self.assertRaises(PermissionDenied):
            admin.site._registry[Campo].save_model(self.request, self.campo, None, True)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.formulario_id, self.formulario.pk)

    def test_graph_admin_solo_lectura_aun_borrador_y_superusuario(self):
        for modelo, objeto in ((Flujo, self.flujo), (VersionFlujo, self.version), (Nodo, self.nodo)):
            with self.subTest(modelo=modelo.__name__):
                model_admin = admin.site._registry[modelo]
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request, objeto))
                self.assertFalse(model_admin.has_delete_permission(self.request, objeto))
                self.assertNotIn("delete_selected", model_admin.get_actions(self.request))
                self.assertEqual(self.client.get(self.url(modelo, pk=objeto.pk)).status_code, 200)
                respuesta = self.client.post(self.url(modelo, pk=objeto.pk), {"estado": "borrador", "titulo": "Forjado"})
                self.assertEqual(respuesta.status_code, 403)
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())

    def test_graph_admin_no_acepta_borrado_bulk_ni_cascada(self):
        for modelo, objeto in ((Flujo, self.flujo), (VersionFlujo, self.version), (Nodo, self.nodo)):
            with self.subTest(modelo=modelo.__name__):
                respuesta = self.client.post(self.url(modelo, "changelist"), {
                    "action": "delete_selected", "_selected_action": [str(objeto.pk)], "post": "yes",
                })
                self.assertIn(respuesta.status_code, (200, 302, 403))
                with self.assertRaises(PermissionDenied):
                    admin.site._registry[modelo].delete_queryset(self.request, modelo.objects.filter(pk=objeto.pk))
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())
