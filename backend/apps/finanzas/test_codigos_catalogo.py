"""Códigos de catálogo automáticos sin alterar referencias ya existentes."""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion

from .models import ConcesionFinanciera, Prestacion


class CodigosCatalogoTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Institución de prueba")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.usuario = Usuario.objects.create_user("catalogos@example.test", "test-password")
        self.membresia = Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol="configurador",
        )
        for accion in ("configurar_componentes", "configurar_gastos_esperados"):
            ConcesionFinanciera.objects.create(
                membresia=self.membresia, accion=accion, todas_las_areas=True,
            )
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Consultas")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        self.prestacion = Prestacion.objects.create(
            institucion=self.institucion, nodo=self.nodo, codigo="CONS-EXISTENTE", nombre="Consulta",
        )
        self.client.force_authenticate(self.usuario)

    def catalogos(self):
        return (
            ("conceptos-gasto", "GAS", {"institucion": self.institucion.pk, "nombre": "Electricidad"}),
            ("prestaciones-costo", "PRE", {"institucion": self.institucion.pk, "nombre": "Otra consulta"}),
            ("componentes-costo", "CMP", {"prestacion": self.prestacion.pk, "nombre": "Materiales"}),
        )

    def test_codigo_omitido_se_genera_en_los_tres_catalogos(self):
        for recurso, prefijo, datos in self.catalogos():
            with self.subTest(recurso=recurso):
                respuesta = self.client.post(f"/api/{recurso}/", datos, format="json")
                self.assertEqual(respuesta.status_code, 201, respuesta.data)
                self.assertRegex(respuesta.data["codigo"], rf"^{prefijo}-[0-9A-F]{{32}}$")

    def test_codigo_vacio_o_blanco_tambien_es_automatico(self):
        for recurso, prefijo, datos in self.catalogos():
            for codigo in ("", "   "):
                with self.subTest(recurso=recurso, codigo=codigo):
                    respuesta = self.client.post(f"/api/{recurso}/", {**datos, "codigo": codigo}, format="json")
                    self.assertEqual(respuesta.status_code, 201, respuesta.data)
                    self.assertRegex(respuesta.data["codigo"], rf"^{prefijo}-[0-9A-F]{{32}}$")

    def test_nombres_repetidos_no_producen_codigos_repetidos(self):
        for recurso, _, datos in self.catalogos():
            with self.subTest(recurso=recurso):
                respuestas = [self.client.post(f"/api/{recurso}/", datos, format="json") for _ in range(3)]
                self.assertTrue(all(r.status_code == 201 for r in respuestas), [r.data for r in respuestas])
                self.assertEqual(len({r.data["codigo"] for r in respuestas}), 3)

    def test_codigo_manual_se_conserva_y_duplicado_se_rechaza(self):
        for recurso, _, datos in self.catalogos():
            with self.subTest(recurso=recurso):
                datos = {**datos, "codigo": "REFERENCIA-MANUAL"}
                respuesta = self.client.post(f"/api/{recurso}/", datos, format="json")
                self.assertEqual(respuesta.status_code, 201, respuesta.data)
                self.assertEqual(respuesta.data["codigo"], "REFERENCIA-MANUAL")
                repetida = self.client.post(f"/api/{recurso}/", datos, format="json")
                self.assertEqual(repetida.status_code, 400, repetida.data)

    def test_actualizar_sin_codigo_conserva_el_existente(self):
        for recurso, _, datos in self.catalogos():
            with self.subTest(recurso=recurso):
                alta = self.client.post(f"/api/{recurso}/", {**datos, "codigo": "EXISTENTE"}, format="json")
                self.assertEqual(alta.status_code, 201, alta.data)
                actualizada = self.client.patch(f"/api/{recurso}/{alta.data['id']}/", {"activo": False}, format="json")
                self.assertEqual(actualizada.status_code, 200, actualizada.data)
                self.assertEqual(actualizada.data["codigo"], "EXISTENTE")
        self.prestacion.refresh_from_db()
        self.assertEqual(self.prestacion.codigo, "CONS-EXISTENTE")

    def test_autogeneracion_no_otorga_permisos(self):
        self.membresia.concesiones_financieras.all().delete()
        for recurso, _, datos in self.catalogos():
            with self.subTest(recurso=recurso):
                respuesta = self.client.post(f"/api/{recurso}/", datos, format="json")
                self.assertEqual(respuesta.status_code, 403, respuesta.data)
