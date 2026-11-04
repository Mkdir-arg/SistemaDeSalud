"""API de borradores no operativos con fixtures ficticias."""
from copy import deepcopy
from hashlib import sha256
import json
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase
from rest_framework.test import APIClient
from apps.accounts.models import Usuario
from . import models as m
from .models import Financiador, MembresiaFinanciador, Plan, EventoCobertura, Afiliado, BorradorReglaDerechos


class BorradoresAPITests(APITestCase):
    def preparar_g2a(self):
        """Dos ámbitos con nombres repetidos y valores exclusivamente sintéticos."""
        self.regla.update(fuente="Fuente ficticia A", plazo_dias_corridos=7)
        otra = Financiador.objects.create(nombre="G2a B ficticia", tipo="otro")
        usuario = Usuario.objects.create_user("g2a-b@example.invalid")
        MembresiaFinanciador.objects.create(financiador=otra, usuario=usuario, rol="admin")
        plan = Plan.objects.create(financiador=otra, codigo="FICTICIO", nombre="Plan ficticio B")
        for org in (self.org, otra):
            Afiliado.objects.create(financiador=org, numero="G2A", documento="G2A-FICTICIO",
                nombre="Persona completamente ficticia", desde="2030-01-01", cobertura_habilitada=False)
        entrada = deepcopy(self.entrada)
        entrada["propuesta"][0].update(plan_id=plan.pk, fuente="Fuente ficticia B", plazo_dias_corridos=0)
        entrada["plan_id"] = plan.pk
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente, f"/api/financiadores/{otra.pk}/borradores-derechos/", entrada

    def instantanea_g2a(self):
        tablas = (m.Financiador, m.Plan, m.MembresiaFinanciador, m.Afiliado,
                  m.SaludPadron, m.HistorialAfiliacion, m.Importacion,
                  m.BorradorReglaDerechos, m.EventoCobertura)
        return {tabla.__name__: list(tabla.objects.order_by("pk").values()) for tabla in tablas}

    def test_g2a_mismo_codigo_version_y_plan_no_mezclan_financiadores(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(cliente_b.post(url_b, entrada_b, format="json").status_code, 200)
        antes = self.instantanea_g2a()
        self.assertEqual(self.client.get(self.url).json(), {"borradores": [self.regla]})
        self.assertEqual(cliente_b.get(url_b).json(), {"borradores": entrada_b["propuesta"]})
        for cliente, url, entrada in ((self.client, self.url, self.entrada), (cliente_b, url_b, entrada_b)):
            vista = cliente.post(url + "previsualizar/", entrada, format="json")
            self.assertEqual(vista.status_code, 200, vista.data)
            self.assertEqual(vista.json()["despues"], {"coincidencias": entrada["propuesta"], "conflicto": False})
        self.assertEqual(self.instantanea_g2a(), antes)

    def test_g2a_preview_guardado_y_reintento_preservan_b_y_filas_previas(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        self.assertEqual(cliente_b.post(url_b, entrada_b, format="json").status_code, 200)
        antes = self.instantanea_g2a()
        vista = self.client.post(self.url + "previsualizar/", self.entrada, format="json")
        self.assertEqual(vista.status_code, 200)
        self.assertEqual(self.instantanea_g2a(), antes)
        guardado = self.post()
        self.assertEqual(guardado.status_code, 200)
        self.assertEqual(guardado.json(), vista.json())
        despues = self.instantanea_g2a()
        for tabla, filas in antes.items():
            if tabla not in ("BorradorReglaDerechos", "EventoCobertura"):
                self.assertEqual(despues[tabla], filas, tabla)
                continue
            ids = {fila["id"] for fila in filas}
            self.assertEqual([fila for fila in despues[tabla] if fila["id"] in ids], filas)
            nuevas = [fila for fila in despues[tabla] if fila["id"] not in ids]
            self.assertEqual(len(nuevas), 1, tabla)
            self.assertEqual(nuevas[0]["financiador_id"], self.org.pk)
            if tabla == "EventoCobertura":
                self.assertEqual(nuevas[0]["accion"], "crear_borrador_derechos")
        repetido = self.post()
        self.assertEqual(repetido.status_code, 200)
        self.assertEqual(repetido.json()["nuevas"], [])
        self.assertEqual(self.instantanea_g2a(), despues)
        self.assertEqual(cliente_b.get(url_b).json(), {"borradores": entrada_b["propuesta"]})

    def test_g2a_fecha_tecnica_y_conflicto_no_eligen_ganador(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        antes = self.instantanea_g2a()
        for cliente, url, entrada in ((self.client, self.url, self.entrada), (cliente_b, url_b, entrada_b)):
            for fecha, coincide in (("2030-01-01", True), ("2030-01-31", True), ("2030-02-01", False)):
                vista = cliente.post(url + "previsualizar/", entrada | {"fecha": fecha}, format="json")
                self.assertEqual(vista.status_code, 200)
                self.assertEqual(vista.json()["despues"], {
                    "coincidencias": entrada["propuesta"] if coincide else [], "conflicto": False})
            general = entrada["propuesta"][0] | {"plan_id": None}
            solapada = entrada | {"propuesta": [general, entrada["propuesta"][0]]}
            vista = cliente.post(url + "previsualizar/", solapada, format="json")
            self.assertEqual(vista.status_code, 200)
            self.assertTrue(vista.json()["despues"]["conflicto"])
            self.assertCountEqual(vista.json()["despues"]["coincidencias"], solapada["propuesta"])
        self.assertEqual(self.instantanea_g2a(), antes)

    def test_g2a_simulacion_configurada_y_alternativa_no_mutan_ambitos(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        for cliente, url, entrada in ((self.client, self.url, self.entrada), (cliente_b, url_b, entrada_b)):
            self.assertEqual(cliente.post(url, entrada, format="json").status_code, 200)
        antes = self.instantanea_g2a()
        for cliente, url, entrada, limite, relacion in (
            (self.client, self.url, self.entrada, "2030-01-08", "en"),
            (cliente_b, url_b, entrada_b, "2030-01-01", "despues"),
        ):
            descriptor = entrada["propuesta"][0]
            cuerpo = dict(regla={k: descriptor[k] for k in ("codigo", "version", "regimen", "plan_id")},
                fecha="2030-01-08", referencia="2030-01-01", evidencia="REF-G2A-FICTICIA")
            respuesta = cliente.post(url + "simular-plazo/", cuerpo, format="json")
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual((respuesta.json()["limite"], respuesta.json()["relacion"]), (limite, relacion))
            self.assertEqual(respuesta.json()["regla"]["fuente"], descriptor["fuente"])
            alternativa = cliente.post(url + "simular-plazo/", cuerpo | {"dias_corridos": 0}, format="json")
            self.assertEqual(alternativa.status_code, 200)
            self.assertEqual(alternativa.json()["limite"], "2030-01-01")
            self.assertEqual(self.instantanea_g2a(), antes)

    def test_g2a_rechazos_de_ambito_identidad_y_roles_preservan_huella(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        self.assertEqual(cliente_b.post(url_b, entrada_b, format="json").status_code, 200)
        antes = self.instantanea_g2a()
        self.assertEqual(self.client.get(url_b).status_code, 404)
        self.assertEqual(self.client.post(url_b, self.entrada, format="json").status_code, 404)
        for cambio in ({"plan_id": entrada_b["plan_id"]}, {"financiador_id": 999}):
            entrada = deepcopy(self.entrada)
            entrada["propuesta"][0].update(cambio)
            self.assertEqual(self.post(entrada).status_code, 400)
            self.assertEqual(self.instantanea_g2a(), antes)
        for rol in ("operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = self.instantanea_g2a()
            for sufijo in ("", "previsualizar/"):
                self.assertEqual(self.client.post(self.url + sufijo, self.entrada, format="json").status_code, 403)
                self.assertEqual(self.instantanea_g2a(), antes)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.instantanea_g2a(), antes)

    def test_g2a_historia_rechazada_preserva_ambas_organizaciones(self):
        cliente_b, url_b, entrada_b = self.preparar_g2a()
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(cliente_b.post(url_b, entrada_b, format="json").status_code, 200)
        antes = self.instantanea_g2a()
        for cambio in ({"propuesta": []}, {"propuesta": [self.regla | {"fuente": "Reescrita"}]},
                       {"propuesta": [self.regla | {"plazo_dias_corridos": 0}]}):
            self.assertEqual(self.post(self.entrada | cambio).status_code, 400)
            self.assertEqual(self.instantanea_g2a(), antes)

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

    def test_plazo_guardado_requiere_nueva_version_y_se_conserva_en_consulta(self):
        entrada = deepcopy(self.entrada)
        entrada["propuesta"][0]["plazo_dias_corridos"] = 7
        r = self.post(entrada)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(self.url).json()["borradores"][0]["plazo_dias_corridos"], 7)
        cambiada = deepcopy(entrada)
        cambiada["propuesta"][0]["plazo_dias_corridos"] = 9
        self.assertEqual(self.post(cambiada).status_code, 400)
        self.assertEqual(self.client.get(self.url).json()["borradores"][0]["plazo_dias_corridos"], 7)
        nueva = entrada["propuesta"][0] | {"version": 2, "plazo_dias_corridos": 9}
        self.assertEqual(self.post(entrada | {"propuesta": [*entrada["propuesta"], nueva]}).status_code, 200)
        self.assertEqual([v["plazo_dias_corridos"] for v in self.client.get(self.url).json()["borradores"]], [7, 9])

    def test_plazo_invalido_no_guarda_ni_audita_y_cero_es_explicito(self):
        for valor in (True, -1, 1.5, 3652059):
            entrada = deepcopy(self.entrada)
            entrada["propuesta"][0]["plazo_dias_corridos"] = valor
            with self.subTest(valor=valor):
                self.assertEqual(self.post(entrada).status_code, 400)
                self.assertEqual(self.client.get(self.url).json(), {"borradores": []})
                self.assertFalse(EventoCobertura.objects.exists())
        entrada["propuesta"][0]["plazo_dias_corridos"] = 0
        self.assertEqual(self.post(entrada).status_code, 200)
        self.assertEqual(self.client.get(self.url).json()["borradores"][0]["plazo_dias_corridos"], 0)

    def test_redefiniciones_de_plazo_rechazadas_conservan_huella_completa(self):
        entrada = deepcopy(self.entrada)
        entrada["propuesta"][0]["plazo_dias_corridos"] = 7
        self.assertEqual(self.post(entrada).status_code, 200)
        def huella():
            modelos = (Financiador, MembresiaFinanciador, Plan, Afiliado, BorradorReglaDerechos, EventoCobertura)
            return sha256(repr([list(m.objects.order_by("pk").values()) for m in modelos]).encode()).hexdigest()
        antes = huella()
        for valor in (None, 0, 9, -1, True, 3652059):
            cambiada = deepcopy(entrada)
            cambiada["propuesta"][0]["plazo_dias_corridos"] = valor
            self.assertEqual(self.post(cambiada).status_code, 400)
            self.assertEqual(huella(), antes)
        nueva = entrada["propuesta"][0] | {"version": 2, "plazo_dias_corridos": 0}
        self.assertEqual(self.post(entrada | {"propuesta": [*entrada["propuesta"], nueva]}).status_code, 200)
        self.assertEqual([v["plazo_dias_corridos"] for v in self.client.get(self.url).json()["borradores"]], [7, 0])

    def test_previsualizar_compara_sin_guardar_y_guardado_recalcula(self):
        url = self.url + "previsualizar/"
        antes = self.client.get(self.url).json()
        eventos = list(EventoCobertura.objects.values())
        vista = self.client.post(url, self.entrada, format="json")
        self.assertEqual(vista.status_code, 200)
        self.assertEqual(vista.json(), {"nuevas": [self.regla],
            "antes": {"coincidencias": [], "conflicto": False},
            "despues": {"coincidencias": [self.regla], "conflicto": False}})
        self.assertEqual(self.client.get(self.url).json(), antes)
        self.assertEqual(list(EventoCobertura.objects.values()), eventos)
        self.assertEqual(self.post().json(), vista.json())
        nueva = self.regla | {"version": 2, "plazo_dias_corridos": 7}
        propuesta = self.entrada | {"propuesta": [self.regla, nueva]}
        self.assertEqual(self.client.post(url, propuesta, format="json").status_code, 200)
        intermedia = self.regla | {"version": 3}
        self.assertEqual(self.post(self.entrada | {"propuesta": [self.regla, intermedia]}).status_code, 200)
        self.assertEqual(self.post(propuesta).status_code, 400)
        self.assertEqual(self.client.get(self.url).json(), {"borradores": [self.regla, intermedia]})

    def test_previsualizar_rechaza_ambitos_roles_y_propuestas_invalidas_sin_cambios(self):
        url = self.url + "previsualizar/"
        otro = Financiador.objects.create(nombre="Otro ficticio", tipo="otro")
        ajeno = Plan.objects.create(financiador=otro, codigo="AJENO", nombre="Ajeno")
        def huella():
            modelos = (Financiador, MembresiaFinanciador, Plan, Afiliado, BorradorReglaDerechos, EventoCobertura)
            return sha256(repr([list(m.objects.order_by("pk").values()) for m in modelos]).encode()).hexdigest()
        antes = huella()
        for cambio in ({"plan_id": ajeno.pk}, {"motivo": " "}, {"activar": True},
                       {"propuesta": [self.regla | {"plan_id": ajeno.pk}]},
                       {"propuesta": [self.regla | {"expresion": "activar()"}]},
                       {"propuesta": [self.regla | {"plazo_dias_corridos": True}]}):
            self.assertEqual(self.client.post(url, self.entrada | cambio, format="json").status_code, 400)
            self.assertEqual(huella(), antes)
        for rol in ("operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = huella()
            self.assertEqual(self.client.post(url, self.entrada, format="json").status_code, 403)
            self.assertEqual(huella(), antes)
        self.member.rol = "admin"
        self.member.save()
        self.assertEqual(self.client.post(url.replace(f"/{self.org.pk}/", f"/{otro.pk}/"), self.entrada, format="json").status_code, 404)
        self.member.activo = False
        self.member.save()
        self.assertEqual(self.client.post(url, self.entrada, format="json").status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(url, self.entrada, format="json").status_code, 401)

    def test_previsualizar_expone_conflicto_sin_elegir_ni_reescribir(self):
        self.assertEqual(self.post().status_code, 200)
        nueva = self.regla | {"version": 2, "plazo_dias_corridos": 0}
        entrada = self.entrada | {"propuesta": [self.regla, nueva]}
        antes = self.client.get(self.url).json()
        eventos = list(EventoCobertura.objects.values())
        r = self.client.post(self.url + "previsualizar/", entrada, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["antes"], {"coincidencias": [self.regla], "conflicto": False})
        self.assertEqual(r.json()["despues"], {"coincidencias": [self.regla, nueva], "conflicto": True})
        self.assertEqual(r.json()["nuevas"], [nueva])
        self.assertEqual(self.client.get(self.url).json(), antes)
        self.assertEqual(list(EventoCobertura.objects.values()), eventos)

    def test_historial_consulta_autor_fecha_y_motivo_persistidos_sin_escrituras(self):
        self.assertEqual(self.post().status_code, 200)
        primera = BorradorReglaDerechos.objects.get()
        nueva = self.regla | {"version": 2, "desde": "2030-02-01", "hasta": None, "plazo_dias_corridos": 7}
        motivo_nuevo = "Motivo ficticio de segunda versión"
        otro_autor = Usuario.objects.create_user("otro-autor-ficticio@example.invalid")
        MembresiaFinanciador.objects.create(financiador=self.org, usuario=otro_autor, rol="admin")
        self.client.force_authenticate(otro_autor)
        self.assertEqual(self.post(self.entrada | {"propuesta": [self.regla, nueva], "motivo": motivo_nuevo}).status_code, 200)
        segunda = BorradorReglaDerechos.objects.get(version=2)
        antes = list(EventoCobertura.objects.order_by("pk").values())
        versiones = self.client.get(self.url).json()
        r = self.client.get(self.url + "historial/")
        self.assertEqual(r.status_code, 200)
        filas = r.json()["historial"]
        self.assertEqual([f["regla"] for f in filas], [self.regla, nueva])
        self.assertEqual([f["creado_por_id"] for f in filas], [self.user.pk, otro_autor.pk])
        self.assertEqual([f["motivo"] for f in filas], [self.entrada["motivo"], motivo_nuevo])
        self.assertEqual([f["creado"] for f in filas], [primera.creado.isoformat().replace("+00:00", "Z"), segunda.creado.isoformat().replace("+00:00", "Z")])
        self.assertEqual(set(filas[0]), {"regla", "creado_por_id", "creado", "motivo"})
        self.assertEqual(self.client.get(self.url).json(), versiones)
        self.assertEqual(list(EventoCobertura.objects.order_by("pk").values()), antes)

    def test_historial_aisla_organizacion_y_no_escribe_para_ningun_lector(self):
        self.assertEqual(self.post().status_code, 200)
        url = self.url + "historial/"
        def huella():
            modelos = (Usuario, Financiador, MembresiaFinanciador, Plan, Afiliado, BorradorReglaDerechos, EventoCobertura)
            return sha256(repr([list(m.objects.order_by("pk").values()) for m in modelos]).encode()).hexdigest()
        esperado = self.client.get(url).json()
        for rol in ("admin", "operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            antes = huella()
            self.assertEqual(self.client.get(url).json(), esperado)
            for metodo in (self.client.post, self.client.put, self.client.patch, self.client.delete):
                self.assertEqual(metodo(url, {}, format="json").status_code, 405)
            self.assertEqual(huella(), antes)
        ajeno = Financiador.objects.create(nombre="Otro ámbito ficticio", tipo="otro")
        MembresiaFinanciador.objects.create(financiador=ajeno, usuario=self.user, rol="admin")
        ajeno_url = url.replace(f"/{self.org.pk}/", f"/{ajeno.pk}/")
        self.assertEqual(self.client.get(ajeno_url).json(), {"historial": []})
        self.assertEqual(self.client.get(url).json(), esperado)
        self.member.activo = False
        self.member.save()
        antes = huella()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(huella(), antes)

    def test_historial_no_consulta_perfiles_ni_padron_y_no_cambia_al_renombrar_autor(self):
        general = self.regla | {"plan_id": None}
        propuesta = self.entrada | {"propuesta": [general, self.regla]}
        self.assertEqual(self.post(propuesta).status_code, 200)
        otro_autor = Usuario.objects.create_user("autor-traza-ficticio@example.invalid", nombre="Nombre original ficticio")
        MembresiaFinanciador.objects.create(financiador=self.org, usuario=otro_autor, rol="admin")
        self.client.force_authenticate(otro_autor)
        nueva = general | {"version": 2}
        self.assertEqual(self.post(propuesta | {"propuesta": [general, self.regla, nueva]}).status_code, 200)
        url = self.url + "historial/"
        anterior = self.client.get(url).json()
        otro_autor.nombre = "Nombre cambiado ficticio"
        otro_autor.email = "nombre-cambiado-ficticio@example.invalid"
        otro_autor.save()
        # Autenticación ya resuelta: verificar sólo el acceso de datos del dominio.
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), anterior)
        self.assertEqual([f["regla"] for f in respuesta.json()["historial"]], [self.regla, general, nueva])
        texto = json.dumps(respuesta.json())
        for valor in (otro_autor.nombre, otro_autor.email, self.user.email):
            self.assertNotIn(valor, texto)
        for consulta in consultas.captured_queries:
            sql = consulta["sql"].lower()
            for tabla in ('"accounts_usuario"', '"financiadores_afiliado"', '"financiadores_saludpadron"'):
                self.assertNotIn(tabla, sql)
