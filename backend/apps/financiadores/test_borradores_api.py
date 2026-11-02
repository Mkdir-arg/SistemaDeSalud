"""API de borradores no operativos con fixtures ficticias."""
from copy import deepcopy
from rest_framework.test import APITestCase
from apps.accounts.models import Usuario
from .models import Financiador, MembresiaFinanciador, Plan, EventoCobertura


class BorradoresAPITests(APITestCase):
    def setUp(self):
        self.org = Financiador.objects.create(nombre="API ficticia", tipo="obra_social")
        self.user = Usuario.objects.create_user("api-borradores@example.invalid")
        self.member = MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="admin")
        self.plan = Plan.objects.create(financiador=self.org, codigo="FICTICIO", nombre="Ficticio")
        self.client.force_authenticate(self.user)
        self.url = f"/api/financiadores/{self.org.pk}/borradores-derechos/"
        self.regla = dict(codigo="ejemplo", version=1, fuente="Fuente ficticia", regimen="dependencia",
                          plan_id=self.plan.pk, desde="2030-01-01", hasta="2030-02-01")
        self.entrada = dict(propuesta=[self.regla], motivo="Ejemplo ficticio", regimen="dependencia",
                            plan_id=self.plan.pk, fecha="2030-01-15")

    def post(self, entrada=None):
        return self.client.post(self.url, self.entrada if entrada is None else entrada, format="json")

    def test_guardado_consulta_y_reintento_no_activan_ni_duplican(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        respuesta = self.post()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.json()["nuevas"], [self.regla])
        self.assertEqual(respuesta.json()["antes"], {"coincidencias": [], "conflicto": False})
        self.assertEqual(respuesta.json()["despues"], {"coincidencias": [self.regla], "conflicto": False})
        self.assertEqual(self.client.get(self.url).json(), {"borradores": [self.regla]})
        self.assertEqual(self.post().json()["nuevas"], [])
        self.assertEqual(EventoCobertura.objects.filter(accion="crear_borrador_derechos").count(), 1)

    def test_roles_y_aislamiento_no_amplian_acceso(self):
        self.assertEqual(self.post().status_code, 200)
        for rol in ("operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            self.assertEqual(self.client.get(self.url).status_code, 200)
            self.assertEqual(self.post().status_code, 403)
        self.member.activo = False
        self.member.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.post().status_code, 404)
        ajeno = Financiador.objects.create(nombre="Ajeno ficticio", tipo="otro")
        self.assertEqual(self.client.get(f"/api/financiadores/{ajeno.pk}/borradores-derechos/").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_entradas_no_controladas_no_escriben_ni_auditan(self):
        ajeno = Financiador.objects.create(nombre="Plan ajeno ficticio", tipo="otro")
        plan_ajeno = Plan.objects.create(financiador=ajeno, codigo="AJENO", nombre="Ajeno")
        casos = []
        for campo in ("activar", "aprobado", "financiador_id", "expresion"):
            raiz, fila = deepcopy(self.entrada), deepcopy(self.entrada)
            raiz[campo], fila["propuesta"][0][campo] = True, True
            casos.extend([raiz, fila])
        for cambio in (dict(version=True), dict(plan_id=plan_ajeno.pk), dict(regimen="inventado"),
                       dict(hasta="2029-12-31"), dict(fuente=" "), dict(desde="no-fecha")):
            entrada = deepcopy(self.entrada)
            entrada["propuesta"][0].update(cambio)
            casos.append(entrada)
        for entrada in casos:
            with self.subTest(entrada=entrada):
                respuesta = self.post(entrada)
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertEqual(self.client.get(self.url).json(), {"borradores": []})
                self.assertFalse(EventoCobertura.objects.filter(accion="crear_borrador_derechos").exists())

    def test_historia_incompleta_o_reescrita_se_rechaza_sin_cambios(self):
        self.assertEqual(self.post().status_code, 200)
        antes = self.client.get(self.url).json()
        for cambio in (dict(propuesta=[]), dict(propuesta=[self.regla | {"fuente": "Reescrita"}])):
            respuesta = self.post(self.entrada | cambio)
            self.assertEqual(respuesta.status_code, 400, respuesta.data)
            self.assertEqual(self.client.get(self.url).json(), antes)
        nueva = self.regla | {"version": 2, "desde": "2030-02-01", "hasta": None}
        respuesta = self.post(self.entrada | {"propuesta": [nueva, self.regla], "fecha": "2030-02-01"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.json()["nuevas"], [nueva])
        self.assertEqual(respuesta.json()["despues"]["coincidencias"], [nueva])
        self.assertEqual(EventoCobertura.objects.filter(accion="crear_borrador_derechos").count(), 2)
