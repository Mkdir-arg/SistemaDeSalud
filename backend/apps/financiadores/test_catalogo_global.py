from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.financiadores.models import PrestacionComun


class CatalogoGlobalTests(APITestCase):
    url = "/api/financiadores/catalogo-comun/"

    def test_plataforma_administra_catalogo_sin_financiadores(self):
        admin = Usuario.objects.create_superuser("plataforma-catalogo@test.local", "clave")
        self.client.force_authenticate(admin)
        vacio = self.client.get(self.url)
        self.assertEqual(vacio.status_code, 200, vacio.data)
        self.assertEqual(vacio.data["count"], 0)
        alta = self.client.post(self.url, {
            "codigo": "PRE-1", "nombre": "Consulta", "categoria": "Atención",
        }, format="json")
        self.assertEqual(alta.status_code, 201, alta.data)
        self.assertEqual(PrestacionComun.objects.count(), 1)
        self.assertEqual(self.client.get(self.url).data["count"], 1)

    def test_usuario_comun_no_consulta_ni_crea_catalogo_global(self):
        usuario = Usuario.objects.create_user("usuario-catalogo@test.local", "clave")
        self.client.force_authenticate(usuario)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {
            "codigo": "PRE-1", "nombre": "Consulta", "categoria": "Atención",
        }, format="json").status_code, 403)
