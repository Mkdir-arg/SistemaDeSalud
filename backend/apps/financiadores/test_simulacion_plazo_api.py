"""Simulación HTTP sobre versiones ficticias; no decide derechos ni escribe."""
from copy import deepcopy
from hashlib import sha256
from datetime import date
from rest_framework.test import APITestCase
from apps.accounts.models import Usuario
from .models import Financiador, MembresiaFinanciador, BorradorReglaDerechos, EventoCobertura, Afiliado, Plan


class SimulacionPlazoAPITests(APITestCase):
    def setUp(self):
        self.org = Financiador.objects.create(nombre="Simulación ficticia", tipo="otro")
        self.user = Usuario.objects.create_user("simulacion-plazo@example.invalid")
        self.member = MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="auditor")
        BorradorReglaDerechos.objects.create(financiador=self.org, codigo="ficticia", version=3,
            fuente="Fuente ficticia persistida", regimen="dependencia", desde=date(2029, 1, 1),
            creado_por=self.user, motivo="Fixture ficticia")
        self.client.force_authenticate(self.user)
        self.url = f"/api/financiadores/{self.org.pk}/borradores-derechos/simular-plazo/"
        self.body = dict(regla=dict(codigo="ficticia", version=3, regimen="dependencia", plan_id=None),
                         dias_corridos=7, fecha="2030-01-08", referencia="2030-01-01", evidencia="REF-FICTICIA")

    def test_miembro_lector_simula_version_real_sin_escrituras(self):
        antes = list(BorradorReglaDerechos.objects.values())
        eventos = list(EventoCobertura.objects.values())
        r = self.client.post(self.url, self.body, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["estado"], r.json()["limite"], r.json()["relacion"]),
                         ("calculado", "2030-01-08", "en"))
        self.assertEqual(r.json()["regla"]["fuente"], "Fuente ficticia persistida")
        self.assertEqual(r.json()["regla"]["version"], 3)
        self.assertEqual(list(BorradorReglaDerechos.objects.values()), antes)
        self.assertEqual(list(EventoCobertura.objects.values()), eventos)


    def test_evidencia_faltante_y_limites_usan_datos_explicitos(self):
        for cambios, estado, limite, relacion in (
            (dict(evidencia=None), "requiere_evidencia", None, None),
            (dict(fecha="2030-01-07"), "calculado", "2030-01-08", "antes"),
            (dict(fecha="2030-01-09"), "calculado", "2030-01-08", "despues"),
            (dict(dias_corridos=0, fecha="2030-01-01"), "calculado", "2030-01-01", "en"),
            (dict(dias_corridos=9), "calculado", "2030-01-10", "antes"),
            (dict(fecha="2028-12-31"), "sin_coincidencia", None, None)):
            with self.subTest(cambios=cambios):
                r = self.client.post(self.url, self.body | cambios, format="json")
                self.assertEqual(r.status_code, 200)
                self.assertEqual((r.json()["estado"], r.json()["limite"], r.json()["relacion"]),
                                 (estado, limite, relacion))
        self.assertEqual(BorradorReglaDerechos.objects.count(), 1)
        self.assertFalse(EventoCobertura.objects.exists())

    def test_rechazos_no_aceptan_fuente_cliente_ni_otro_financiador(self):
        antes = list(BorradorReglaDerechos.objects.values())
        casos = []
        for campo, valor in (("activar", True), ("financiador_id", 99999), ("expresion", "activar()")):
            casos.append(self.body | {campo: valor})
        for cambio in (dict(fuente="Fuente falsa del cliente"), dict(version=999), dict(plan_id=99999)):
            entrada = deepcopy(self.body)
            entrada["regla"].update(cambio)
            casos.append(entrada)
        casos += [self.body | dict(dias_corridos=True), self.body | dict(dias_corridos=-1),
                  self.body | dict(referencia="9999-12-31"), self.body | dict(evidencia=" ")]
        for entrada in casos:
            with self.subTest(entrada=entrada):
                self.assertEqual(self.client.post(self.url, entrada, format="json").status_code, 400)
        ajeno = Financiador.objects.create(nombre="Otro ficticio", tipo="otro")
        url_ajeno = self.url.replace(f"/{self.org.pk}/", f"/{ajeno.pk}/")
        self.assertEqual(self.client.post(url_ajeno, self.body, format="json").status_code, 404)
        self.member.activo = False
        self.member.save()
        self.assertEqual(self.client.post(self.url, self.body, format="json").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url, self.body, format="json").status_code, 401)
        self.assertEqual(list(BorradorReglaDerechos.objects.values()), antes)
        self.assertFalse(EventoCobertura.objects.exists())

    def huella(self):
        tablas = (Financiador, MembresiaFinanciador, Plan, Afiliado, BorradorReglaDerechos, EventoCobertura)
        filas = [list(modelo.objects.order_by("pk").values()) for modelo in tablas]
        return sha256(repr(filas).encode()).hexdigest()

    def test_todos_los_roles_lectores_simulan_sin_cambiar_dominio_o_auditoria(self):
        Afiliado.objects.create(financiador=self.org, numero="FICTICIO", documento="FICTICIO",
                                nombre="Persona ficticia", desde=date(2029, 1, 1))
        for rol in ("admin", "operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = self.huella()
            r = self.client.post(self.url, self.body, format="json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["regla"]["fuente"], "Fuente ficticia persistida")
            self.assertEqual(r.json()["relacion"], "en")
            self.assertEqual(self.huella(), antes)

    def test_identidad_embebida_y_otro_ambito_autorizado_no_modifican_datos(self):
        otro = Financiador.objects.create(nombre="Otro ámbito ficticio", tipo="otro")
        MembresiaFinanciador.objects.create(financiador=otro, usuario=self.user, rol="auditor")
        antes = self.huella()
        for campo in ("fuente", "usuario", "activar", "financiador_id"):
            for anidado in (False, True):
                entrada = deepcopy(self.body)
                (entrada["regla"] if anidado else entrada)[campo] = "Valor cliente ficticio"
                self.assertEqual(self.client.post(self.url, entrada, format="json").status_code, 400)
                self.assertEqual(self.huella(), antes)
        url = self.url.replace(f"/{self.org.pk}/", f"/{otro.pk}/")
        self.assertEqual(self.client.post(url, self.body, format="json").status_code, 400)
        self.assertEqual(self.huella(), antes)

    def test_usa_plazo_configurado_solo_cuando_no_hay_alternativa_explicita(self):
        BorradorReglaDerechos.objects.create(financiador=self.org, codigo="ficticia", version=4,
            fuente="Fuente configurada ficticia", regimen="dependencia", desde=date(2029, 1, 1),
            creado_por=self.user, motivo="Fixture ficticia", plazo_dias_corridos=7)
        entrada = deepcopy(self.body)
        entrada["regla"]["version"] = 4
        entrada.pop("dias_corridos")
        r = self.client.post(self.url, entrada, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["dias_corridos"], r.json()["limite"], r.json()["origen_plazo"]),
                         (7, "2030-01-08", "configurado"))
        r = self.client.post(self.url, entrada | dict(dias_corridos=9), format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["dias_corridos"], r.json()["limite"], r.json()["origen_plazo"]),
                         (9, "2030-01-10", "simulado"))
        self.assertEqual(BorradorReglaDerechos.objects.get(version=4).plazo_dias_corridos, 7)
        self.assertFalse(EventoCobertura.objects.exists())

    def test_legacy_sin_plazo_no_asigna_default_y_null_no_es_omision(self):
        entrada = deepcopy(self.body)
        entrada.pop("dias_corridos")
        self.assertEqual(self.client.post(self.url, entrada, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.url, self.body | dict(dias_corridos=None), format="json").status_code, 400)
        r = self.client.post(self.url, self.body, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["limite"], r.json()["origen_plazo"]), ("2030-01-08", "simulado"))

    def test_plazo_configurado_cero_y_alternativa_cero_no_son_ausencia(self):
        BorradorReglaDerechos.objects.create(financiador=self.org, codigo="ficticia", version=4,
            fuente="Fuente cero ficticia", regimen="dependencia", desde=date(2029, 1, 1),
            creado_por=self.user, motivo="Fixture ficticia", plazo_dias_corridos=0)
        entrada = deepcopy(self.body)
        entrada["regla"]["version"] = 4
        entrada.pop("dias_corridos")
        antes = self.huella()
        for alternativa, origen in (({}, "configurado"), ({"dias_corridos": 0}, "simulado")):
            r = self.client.post(self.url, entrada | alternativa, format="json")
            self.assertEqual(r.status_code, 200)
            self.assertEqual((r.json()["dias_corridos"], r.json()["limite"], r.json()["origen_plazo"]),
                             (0, "2030-01-01", origen))
            self.assertEqual(self.huella(), antes)

    def test_plazo_configurado_y_alternativas_conservan_huella_para_todos_los_roles(self):
        BorradorReglaDerechos.objects.create(financiador=self.org, codigo="ficticia", version=4,
            fuente="Fuente guardada ficticia", regimen="dependencia", desde=date(2029, 1, 1),
            creado_por=self.user, motivo="Fixture ficticia", plazo_dias_corridos=7)
        entrada = deepcopy(self.body)
        entrada["regla"]["version"] = 4
        entrada.pop("dias_corridos")
        for rol in ("admin", "operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = self.huella()
            for alternativa, estado, dias, origen in (
                ({}, 200, 7, "configurado"),
                ({"dias_corridos": 0}, 200, 0, "simulado"),
                ({"dias_corridos": 9}, 200, 9, "simulado"),
                ({"dias_corridos": None}, 400, None, None),
            ):
                r = self.client.post(self.url, entrada | alternativa, format="json")
                self.assertEqual(r.status_code, estado)
                if estado == 200:
                    self.assertEqual((r.json()["dias_corridos"], r.json()["origen_plazo"]), (dias, origen))
                self.assertEqual(self.huella(), antes)
