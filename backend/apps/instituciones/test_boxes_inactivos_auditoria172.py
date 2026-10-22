"""Boxes olvidados: aviso y liberación confirmada (#172, AUD-048).

Decisión del dueño: tras 3 h sin actividad con pacientes esperando se avisa al
jefe del área y a los admins; ellos liberan con confirmación y se le avisa al
profesional. Nada se libera solo. Datos sintéticos.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, ItemFila, Notificacion
from apps.flujos.models import Flujo, Nodo, VersionFlujo

from . import boxes
from .models import Area, Box, Institucion


class BoxesInactivosAuditoria172Tests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital sintético de boxes")
        self.guardia = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.clinica = Area.objects.create(institucion=self.inst, nombre="Clínica")
        self.box = Box.objects.create(area=self.guardia, nombre="Box 1")
        self.medico = self.usuario("medico-box@example.test", Membresia.Rol.MEDICO, self.guardia)
        self.jefe = self.usuario("jefe-box@example.test", Membresia.Rol.JEFE_AREA, self.guardia)
        self.jefe_otra = self.usuario("jefe-otra@example.test", Membresia.Rol.JEFE_AREA, self.clinica)
        self.admin = self.usuario("admin-box@example.test", Membresia.Rol.ADMIN_INSTITUCION)
        self.colega = self.usuario("colega-box@example.test", Membresia.Rol.MEDICO, self.guardia)
        flujo = Flujo.objects.create(institucion=self.inst, area=self.guardia, titulo="Guardia")
        self.version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.ESPERA_FILA, titulo="Fila")
        self.ocupar_hace(timedelta(hours=4))

    def usuario(self, email, rol, area=None):
        usuario = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        membresia = Membresia.objects.create(usuario=usuario, institucion=self.inst, rol=rol)
        if area is not None:
            membresia.areas.add(area)
        return usuario

    def ocupar_hace(self, hace):
        Box.objects.filter(pk=self.box.pk).update(
            ocupado_por=self.medico, ocupado_desde=timezone.now() - hace, aviso_inactividad_at=None,
        )
        self.box.refresh_from_db()

    def paciente_esperando(self, **campos):
        caso = Caso.objects.create(institucion=self.inst, version=self.version)
        return ItemFila.objects.create(caso=caso, nodo=self.nodo, **campos)

    def avisados(self):
        return set(Notificacion.objects.filter(titulo__startswith="Box Box 1").values_list("usuario_id", flat=True))

    def test_avisa_una_vez_al_jefe_del_area_y_al_admin(self):
        self.paciente_esperando()
        call_command("revisar_boxes", stdout=StringIO())
        self.assertEqual(self.avisados(), {self.jefe.pk, self.admin.pk})
        self.box.refresh_from_db()
        self.assertIsNotNone(self.box.aviso_inactividad_at)
        self.assertEqual(self.box.ocupado_por_id, self.medico.pk)
        call_command("revisar_boxes", stdout=StringIO())
        self.assertEqual(Notificacion.objects.filter(titulo__startswith="Box Box 1").count(), 2)

    def test_no_avisa_con_actividad_reciente_ni_sin_pacientes_esperando(self):
        call_command("revisar_boxes", stdout=StringIO())
        self.assertEqual(self.avisados(), set())
        atendido = self.paciente_esperando(box=self.box, llamado_at=timezone.now() - timedelta(hours=1))
        atendido.atendido = True
        atendido.save(update_fields=["atendido"])
        self.paciente_esperando()
        self.assertEqual(boxes.revisar(), 0)
        self.ocupar_hace(timedelta(hours=1))
        self.assertEqual(boxes.revisar(), 0)
        self.assertEqual(self.avisados(), set())

    def liberar(self, usuario, **datos):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente.post(f"/api/boxes/{self.box.pk}/liberar/", datos, format="json")

    def test_liberar_ajeno_exige_supervision_y_confirmacion_y_avisa_al_profesional(self):
        self.assertEqual(self.liberar(self.colega, confirmar=True).status_code, 403)
        self.assertEqual(self.liberar(self.jefe_otra, confirmar=True).status_code, 403)
        self.assertEqual(self.liberar(self.jefe).status_code, 400)
        self.box.refresh_from_db()
        self.assertEqual(self.box.ocupado_por_id, self.medico.pk)
        self.assertEqual(self.liberar(self.jefe, confirmar=True).status_code, 200)
        self.box.refresh_from_db()
        self.assertIsNone(self.box.ocupado_por_id)
        self.assertTrue(Notificacion.objects.filter(usuario=self.medico, titulo="Liberaron tu box Box 1").exists())

    def test_admin_libera_y_ocupar_de_nuevo_reinicia_el_aviso(self):
        self.paciente_esperando()
        boxes.revisar()
        self.assertEqual(self.liberar(self.admin, confirmar=True).status_code, 200)
        self.box.refresh_from_db()
        self.assertIsNone(self.box.aviso_inactividad_at)
        cliente = APIClient()
        cliente.force_authenticate(self.colega)
        self.assertEqual(cliente.post(f"/api/boxes/{self.box.pk}/ocupar/").status_code, 200)
        self.box.refresh_from_db()
        self.assertEqual((self.box.ocupado_por_id, self.box.aviso_inactividad_at), (self.colega.pk, None))

    def test_el_propio_profesional_sigue_liberando_sin_confirmar(self):
        self.assertEqual(self.liberar(self.medico).status_code, 200)
        self.assertFalse(Notificacion.objects.filter(usuario=self.medico).exists())
