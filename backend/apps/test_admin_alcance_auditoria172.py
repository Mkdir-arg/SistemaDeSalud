"""AUD-042: Django Admin con alcance institucional (#172).

Un staff que no es superusuario y tiene todos los permisos de modelo solo ve y
modifica objetos de las instituciones donde tiene una pertenencia activa con
`config_institucional`. El superusuario no se limita. Las protecciones propias
de cada Admin (grafos de solo lectura, formularios congelados, firmas,
credenciales) no cambian: acá solo se prueba el alcance.

Requiere el manifest de estáticos (`manage.py collectstatic`) para renderizar.
"""
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.admin_alcance import AlcanceInstitucionalAdmin, AlcanceInstitucionalInline
from apps.auditoria.models import FalloAuditoria
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano, HistoriaClinica
from apps.simulacion.perfiles import DOMINIO

# Admins registrados sin institución propia ni derivable. Quedan fuera del
# alcance a propósito y figuran como hueco en la matriz de permisos.
SIN_INSTITUCION = {
    "auth.group": "Grupos de permisos de Django: son globales, no institucionales.",
    "portal.cuentapaciente": "La cuenta del portal es del paciente, no de una institución (decisión pendiente).",
    "portal.eventoportal": "Eventos de la cuenta del portal: misma situación que la cuenta.",
}


def url(modelo, accion="changelist", pk=None):
    return reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_{accion}",
                   args=[pk] if pk is not None else [])


class AdminAlcanceInstitucionalAuditoria172Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Institucion.objects.create(nombre="Hospital Alfa sintetico")
        cls.b = Institucion.objects.create(nombre="Hospital Beta sintetico")
        cls.root = Usuario.objects.create_superuser("root-alcance@example.test", "x", nombre="Root")
        cls.staff = Usuario.objects.create_user("staff-alcance@example.test", "x", nombre="Staff", is_staff=True)
        cls.staff.user_permissions.add(*Permission.objects.all())
        Membresia.objects.create(usuario=cls.staff, institucion=cls.a, rol="admin")

        cls.medico_a = Usuario.objects.create_user("medico-a@example.test", "x", nombre="MedicoAlfa")
        cls.medico_b = Usuario.objects.create_user("medico-b@example.test", "x", nombre="MedicoBeta")
        cls.compartido = Usuario.objects.create_user("compartido@example.test", "x", nombre="Compartido")
        cls.memb_a = Membresia.objects.create(usuario=cls.medico_a, institucion=cls.a, rol="medico")
        cls.memb_b = Membresia.objects.create(usuario=cls.medico_b, institucion=cls.b, rol="medico")
        cls.memb_comp_a = Membresia.objects.create(usuario=cls.compartido, institucion=cls.a, rol="medico")
        cls.memb_comp_b = Membresia.objects.create(usuario=cls.compartido, institucion=cls.b, rol="medico")
        cls.legajo_b = LegajoProfesional.objects.create(usuario=cls.medico_b, matricula="MB-1")

        cls.area_a = Area.objects.create(institucion=cls.a, nombre="Guardia Alfa")
        cls.area_b = Area.objects.create(institucion=cls.b, nombre="Guardia Beta")
        cls.ciu_a = Ciudadano.objects.create(institucion=cls.a, nombre="Paciente", apellido="Alfa")
        cls.ciu_b = Ciudadano.objects.create(institucion=cls.b, nombre="Paciente", apellido="Beta")
        cls.hc_a = HistoriaClinica.objects.create(ciudadano=cls.ciu_a)
        cls.hc_b = HistoriaClinica.objects.create(ciudadano=cls.ciu_b)
        cls.form_a = Formulario.objects.create(institucion=cls.a, titulo="Formulario Alfa")
        cls.form_b = Formulario.objects.create(institucion=cls.b, titulo="Formulario Beta")
        cls.campo_a = Campo.objects.create(formulario=cls.form_a, label="Dato Alfa", tipo="texto_corto")
        cls.campo_b = Campo.objects.create(formulario=cls.form_b, label="Dato Beta", tipo="texto_corto")
        cls.flujo_a = Flujo.objects.create(institucion=cls.a, titulo="Flujo Alfa")
        cls.flujo_b = Flujo.objects.create(institucion=cls.b, titulo="Flujo Beta")
        cls.ver_a = VersionFlujo.objects.create(flujo=cls.flujo_a, numero=1)
        cls.ver_b = VersionFlujo.objects.create(flujo=cls.flujo_b, numero=1)
        cls.caso_a = Caso.objects.create(institucion=cls.a, version=cls.ver_a, ciudadano=cls.ciu_a)
        cls.caso_b = Caso.objects.create(institucion=cls.b, version=cls.ver_b, ciudadano=cls.ciu_b)
        cls.evento_a = EventoCaso.objects.create(caso=cls.caso_a, titulo="Evento Alfa")
        cls.evento_b = EventoCaso.objects.create(caso=cls.caso_b, titulo="Evento Beta")
        cls.fallo_a = FalloAuditoria.objects.create(tipo="detalle", recurso="ciudadano", institucion=cls.a, error="X")
        cls.fallo_b = FalloAuditoria.objects.create(tipo="detalle", recurso="ciudadano", institucion=cls.b, error="X")

    def pares(self):
        return [
            (Institucion, self.a, self.b), (Area, self.area_a, self.area_b),
            (Ciudadano, self.ciu_a, self.ciu_b), (HistoriaClinica, self.hc_a, self.hc_b),
            (Formulario, self.form_a, self.form_b), (Campo, self.campo_a, self.campo_b),
            (Flujo, self.flujo_a, self.flujo_b), (VersionFlujo, self.ver_a, self.ver_b),
            (Caso, self.caso_a, self.caso_b), (EventoCaso, self.evento_a, self.evento_b),
            (Membresia, self.memb_a, self.memb_b), (Usuario, self.medico_a, self.medico_b),
            (FalloAuditoria, self.fallo_a, self.fallo_b),
        ]

    def lista(self, modelo):
        respuesta = self.client.get(url(modelo))
        self.assertEqual(respuesta.status_code, 200, modelo)
        return set(respuesta.context["cl"].queryset.values_list("pk", flat=True))

    def form(self, modelo, accion="add", pk=None):
        respuesta = self.client.get(url(modelo, accion, pk))
        self.assertEqual(respuesta.status_code, 200, modelo)
        return respuesta.context["adminform"].form

    # --- Lista ----------------------------------------------------------------

    def test_listas_del_staff_solo_muestran_su_institucion(self):
        self.client.force_login(self.staff)
        for modelo, de_a, de_b in self.pares():
            with self.subTest(modelo=modelo._meta.label):
                pks = self.lista(modelo)
                self.assertIn(de_a.pk, pks)
                self.assertNotIn(de_b.pk, pks)
        with self.subTest(modelo="LegajoProfesional"):
            self.assertNotIn(self.legajo_b.pk, self.lista(LegajoProfesional))

    def test_filtros_laterales_no_enumeran_otras_instituciones(self):
        self.client.force_login(self.staff)
        for modelo in (Area, Ciudadano, Formulario, Membresia):
            with self.subTest(modelo=modelo._meta.label):
                respuesta = self.client.get(url(modelo))
                self.assertContains(respuesta, "Hospital Alfa sintetico")
                self.assertNotContains(respuesta, "Hospital Beta sintetico")

    def test_cuentas_de_referencia_quedan_fuera_como_en_la_api(self):
        referencia = Usuario.objects.create_user(f"medico-a@{DOMINIO}", None, nombre="Referencia")
        memb = Membresia.objects.create(usuario=referencia, institucion=self.a, rol="medico")
        self.client.force_login(self.staff)
        self.assertNotIn(referencia.pk, self.lista(Usuario))
        self.assertNotIn(memb.pk, self.lista(Membresia))
        self.client.force_login(self.root)
        self.assertIn(referencia.pk, self.lista(Usuario))

    def test_staff_sin_config_institucional_no_ve_nada(self):
        operador = Usuario.objects.create_user("operador-staff@example.test", "x", nombre="Op", is_staff=True)
        operador.user_permissions.add(*Permission.objects.all())
        Membresia.objects.create(usuario=operador, institucion=self.a, rol="medico")
        self.client.force_login(operador)
        for modelo, de_a, _ in self.pares():
            with self.subTest(modelo=modelo._meta.label):
                self.assertEqual(self.lista(modelo), set())

    def test_superusuario_ve_ambas_instituciones(self):
        self.client.force_login(self.root)
        for modelo, de_a, de_b in self.pares():
            with self.subTest(modelo=modelo._meta.label):
                self.assertLessEqual({de_a.pk, de_b.pk}, self.lista(modelo))

    # --- Cambio y borrado de objetos de B --------------------------------------

    def test_detalle_de_b_no_se_abre(self):
        self.client.force_login(self.staff)
        for modelo, _, de_b in self.pares():
            for accion in ("change", "delete", "history"):
                with self.subTest(modelo=modelo._meta.label, accion=accion):
                    self.assertNotEqual(self.client.get(url(modelo, accion, de_b.pk)).status_code, 200)

    def test_post_de_cambio_sobre_b_no_modifica(self):
        self.client.force_login(self.staff)
        self.client.post(url(Area, "change", self.area_b.pk), {
            "institucion": self.a.pk, "nombre": "Robada", "activa": "on",
            "subareas-TOTAL_FORMS": "0", "subareas-INITIAL_FORMS": "0",
        })
        self.client.post(url(Ciudadano, "change", self.ciu_b.pk), {
            "institucion": self.b.pk, "nombre": "Cambiado", "apellido": "Beta",
        })
        self.area_b.refresh_from_db()
        self.ciu_b.refresh_from_db()
        self.assertEqual((self.area_b.nombre, self.area_b.institucion_id), ("Guardia Beta", self.b.pk))
        self.assertEqual(self.ciu_b.nombre, "Paciente")

    def test_post_de_borrado_sobre_b_no_borra(self):
        self.client.force_login(self.staff)
        for modelo, objeto in ((Membresia, self.memb_b), (Formulario, self.form_b), (Area, self.area_b)):
            with self.subTest(modelo=modelo._meta.label):
                self.client.post(url(modelo, "delete", objeto.pk), {"post": "yes"})
                self.assertTrue(modelo.objects.filter(pk=objeto.pk).exists())

    def test_acciones_bulk_ignoran_objetos_de_b(self):
        self.client.force_login(self.staff)
        self.client.post(url(Membresia), {
            "action": "delete_selected", "_selected_action": [self.memb_a.pk, self.memb_b.pk], "post": "yes",
        })
        self.assertFalse(Membresia.objects.filter(pk=self.memb_a.pk).exists())
        self.assertTrue(Membresia.objects.filter(pk=self.memb_b.pk).exists())
        self.client.post(url(FalloAuditoria), {
            "action": "marcar_revisado", "_selected_action": [self.fallo_a.pk, self.fallo_b.pk],
        })
        self.fallo_a.refresh_from_db()
        self.fallo_b.refresh_from_db()
        self.assertIsNotNone(self.fallo_a.revisado_at)
        self.assertIsNone(self.fallo_b.revisado_at)

    # --- Choices de FK y POST forjado -------------------------------------------

    def test_choices_de_fk_solo_de_su_institucion(self):
        self.client.force_login(self.staff)
        self.assertEqual(set(self.form(Area).fields["institucion"].queryset), {self.a})
        caso = self.form(Caso, "change", self.caso_a.pk).fields
        self.assertEqual(set(caso["version"].queryset), {self.ver_a})
        self.assertEqual(set(caso["ciudadano"].queryset), {self.ciu_a})
        self.assertNotIn(self.medico_b, set(caso["asignado_a"].queryset))
        self.assertIn(self.medico_a, set(caso["asignado_a"].queryset))
        self.assertEqual(set(caso["area_actual"].queryset), {self.area_a})
        membresia = self.form(Membresia).fields
        self.assertEqual(set(membresia["institucion"].queryset), {self.a})
        self.assertNotIn(self.medico_b, set(membresia["usuario"].queryset))
        self.assertEqual(set(membresia["areas"].queryset), {self.area_a})
        roles = {valor for valor, _ in membresia["rol"].choices}
        self.assertNotIn("plataforma", roles)
        self.assertNotIn("auditor", roles)
        self.assertIn("medico", roles)

    def test_post_forjado_hacia_b_se_rechaza(self):
        self.client.force_login(self.staff)
        antes = Area.objects.count()
        respuesta = self.client.post(url(Area, "add"), {
            "institucion": self.b.pk, "nombre": "Forjada", "activa": "on",
            "subareas-TOTAL_FORMS": "0", "subareas-INITIAL_FORMS": "0",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Area.objects.count(), antes)
        self.client.post(url(Area, "change", self.area_a.pk), {
            "institucion": self.b.pk, "nombre": "Guardia Alfa", "activa": "on",
            "subareas-TOTAL_FORMS": "0", "subareas-INITIAL_FORMS": "0",
        })
        self.area_a.refresh_from_db()
        self.assertEqual(self.area_a.institucion_id, self.a.pk)
        respuesta = self.client.post(url(Membresia, "add"), {
            "usuario": self.medico_a.pk, "institucion": self.a.pk, "rol": "plataforma", "activo": "on",
        })
        self.assertFalse(Membresia.objects.filter(usuario=self.medico_a, rol="plataforma").exists())

    def test_staff_no_crea_instituciones(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url(Institucion, "add")).status_code, 403)

    # --- Usuarios -----------------------------------------------------------------

    def test_usuario_compartido_con_otra_institucion_es_solo_lectura(self):
        self.client.force_login(self.staff)
        respuesta = self.client.get(url(Usuario, "change", self.compartido.pk))
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["has_change_permission"])
        self.assertFalse(respuesta.context["has_delete_permission"])
        inline = respuesta.context["inline_admin_formsets"][0].formset
        self.assertEqual(set(inline.queryset), {self.memb_comp_a})
        self.client.post(url(Usuario, "change", self.compartido.pk), {
            "nombre": "Pisado", "apellido": "", "membresias-TOTAL_FORMS": "0",
            "membresias-INITIAL_FORMS": "0", "_save": "Guardar",
        })
        self.client.post(url(Usuario, "delete", self.compartido.pk), {"post": "yes"})
        self.compartido.refresh_from_db()
        self.assertEqual(self.compartido.nombre, "Compartido")
        self.assertTrue(self.compartido.is_active)

    def test_usuario_propio_sigue_administrable(self):
        self.client.force_login(self.staff)
        respuesta = self.client.post(url(Usuario, "change", self.medico_a.pk), {
            "nombre": "MedicoAlfa", "apellido": "Editado", "is_active": "on",
            "membresias-TOTAL_FORMS": "1", "membresias-INITIAL_FORMS": "1",
            "membresias-MIN_NUM_FORMS": "0", "membresias-MAX_NUM_FORMS": "1000",
            "membresias-0-id": self.memb_a.pk, "membresias-0-usuario": self.medico_a.pk,
            "membresias-0-institucion": self.a.pk, "membresias-0-rol": "medico", "membresias-0-activo": "on",
            "_save": "Guardar",
        })
        self.assertEqual(respuesta.status_code, 302)
        self.medico_a.refresh_from_db()
        self.assertEqual(self.medico_a.apellido, "Editado")


class AdminAlcanceCoberturaAuditoria172Tests(TestCase):
    def test_todo_admin_registrado_declara_alcance_o_exencion(self):
        sin_alcance = []
        for modelo, model_admin in admin.site._registry.items():
            etiqueta = modelo._meta.label_lower
            if etiqueta in SIN_INSTITUCION:
                continue
            if not isinstance(model_admin, AlcanceInstitucionalAdmin):
                sin_alcance.append(etiqueta)
            for inline in model_admin.inlines:
                if not issubclass(inline, AlcanceInstitucionalInline):
                    sin_alcance.append(f"{etiqueta} inline {inline.__name__}")
        self.assertEqual(sin_alcance, [])
