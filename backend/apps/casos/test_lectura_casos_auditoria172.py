"""Leer casos, valores y eventos exige capacidad (#172, AUD-008, decisión del dueño).

Configurador, reportes, auditor y plataforma no ven datos clínicos de casos;
los roles operativos sí. La denegación no enumera: un id inexistente da lo mismo.
"""
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, VersionFlujo
from apps.instituciones.models import Institucion

from .models import Caso


class LecturaCasosAuditoria172Tests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital sintético de lectura")
        flujo = Flujo.objects.create(institucion=self.inst, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.caso = Caso.objects.create(institucion=self.inst, version=version)

    def cliente(self, rol):
        usuario = Usuario.objects.create_user(f"{rol}-lectura@example.test", "x", nombre=rol)
        Membresia.objects.create(usuario=usuario, institucion=self.inst, rol=rol)
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def rutas(self):
        return ["/api/casos/", f"/api/casos/{self.caso.pk}/", f"/api/valores-campo/?caso={self.caso.pk}",
                f"/api/eventos-caso/?caso={self.caso.pk}"]

    def test_roles_sin_capacidad_no_leen_casos_ni_valores_ni_eventos(self):
        for rol in (Membresia.Rol.CONFIGURADOR, Membresia.Rol.REPORTES):
            cliente = self.cliente(rol)
            for ruta in self.rutas() + ["/api/casos/999999999/"]:
                with self.subTest(rol=rol, ruta=ruta):
                    self.assertEqual(cliente.get(ruta).status_code, 403)

    def test_roles_operativos_siguen_leyendo(self):
        for rol in (Membresia.Rol.MEDICO, Membresia.Rol.ADMINISTRATIVO, Membresia.Rol.ENFERMERIA):
            cliente = self.cliente(rol)
            for ruta in self.rutas():
                with self.subTest(rol=rol, ruta=ruta):
                    self.assertEqual(cliente.get(ruta).status_code, 200)
