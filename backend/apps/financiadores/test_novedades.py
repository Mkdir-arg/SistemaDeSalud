"""Novedades administrativas por API: nunca alteran el padrón ni sus efectos."""
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from . import models as m
from .test_cobertura import CoberturaSetup


class NovedadesSetup(CoberturaSetup):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.operador)
        self.base = f"/api/financiadores/{self.financiador.pk}/"
        self.reservar(acepta=True)
        self.externo()
        m.HistorialAfiliacion.objects.create(afiliado=self.afiliado,
            numero=self.afiliado.numero, documento=self.afiliado.documento,
            plan=self.plan, desde=self.hoy, registrado_por=self.operador,
            motivo="Antecedente ficticio de caracterización")

    def entrada(self, **extra):
        return {"clave": str(uuid4()), "afiliado": self.afiliado.pk,
                "fuente": "Fuente ficticia", "referencia": "REF-SINTETICA-1",
                "codigo": "INFORMADO", "fecha_informada": "2030-01-02",
                "descripcion": "Comunicación administrativa ficticia",
                "motivo": "Registrar evidencia sin aplicar efectos", **extra}

    def huella(self):
        return {modelo.__name__: list(modelo.objects.order_by("pk").values())
                for modelo in (m.Afiliado, m.HistorialAfiliacion, m.AfiliacionCaso,
                               m.ReservaCobertura, m.ConsumoExterno)}

    def huella_propuestas_y_auditoria(self):
        return (self.huella(), list(m.Importacion.objects.order_by("pk").values()),
                list(m.EventoCobertura.objects.order_by("pk").values()))

    def crear(self, **extra):
        respuesta = self.client.post(self.base + "novedades/", self.entrada(**extra), format="json")
        self.assertEqual(respuesta.status_code, 201, getattr(respuesta, "data", respuesta.content))
        return respuesta.data

    def decision(self, propuesta, **extra):
        return {"revision": propuesta["revision"],
                "revision_padron": propuesta["persona_actual"]["revision"],
                "accion": "conciliar", "motivo": "Evidencia administrativa revisada",
                "confirmar_conflictos": False, **extra}


class NovedadesTests(NovedadesSetup, TestCase):
    def test_evidencia_textual_conserva_codigos_y_espacios_originales(self):
        entrada = {"fuente": " Fuente ficticia ", "referencia": " REF-0007 ",
                   "codigo": " 0007 ", "descripcion": "  Nota original\ncon contexto.  "}
        propuesta = self.crear(**entrada)
        for campo, valor in entrada.items():
            self.assertEqual(propuesta["original"][campo], valor)


    def test_registro_consulta_y_reintento_conservan_original_y_padron(self):
        anterior = self.huella()
        entrada = self.entrada()
        respuesta = self.client.post(self.base + "novedades/", entrada, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        propuesta = respuesta.data
        self.assertEqual(propuesta["estado"], "pendiente")
        self.assertEqual(propuesta["original"]["fecha_informada"], "2030-01-02")
        self.assertFalse(propuesta["efectos_aplicados"])
        repetida = self.client.post(self.base + "novedades/", entrada, format="json")
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(repetida.data["id"], propuesta["id"])
        self.assertEqual(len(repetida.data["historia"]), 1)
        conflicto = self.client.post(self.base + "novedades/", {**entrada, "codigo": "OTRO"}, format="json")
        self.assertEqual(conflicto.status_code, 400, conflicto.data)
        detalle = self.client.get(self.base + f"novedades/{propuesta['id']}/")
        self.assertEqual(detalle.status_code, 200, detalle.data)
        self.assertEqual(detalle.data["original"], propuesta["original"])
        listado = self.client.get(self.base + "novedades/", {"estado": "pendiente"})
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual([p["id"] for p in listado.data["results"]], [propuesta["id"]])
        self.assertEqual(self.huella(), anterior)

    def test_rutas_legacy_no_listan_ni_aplican_propuestas_de_novedades(self):
        propuesta = self.crear()
        anterior = list(m.Importacion.objects.order_by("pk").values())
        huella = self.huella()
        self.client.raise_request_exception = False
        listado = self.client.get(self.base + "importaciones/")
        self.assertEqual(listado.status_code, 200, getattr(listado, "data", listado.content))
        self.assertEqual(listado.data, {"count": 0, "next": None, "previous": None, "results": []})
        for tipo in ("padron", "consumos", "novedades"):
            filtrada = self.client.get(self.base + "importaciones/", {"tipo": tipo})
            self.assertEqual(filtrada.status_code, 200, filtrada.data)
            self.assertEqual(filtrada.data, listado.data)
        confirmada = self.client.post(self.base + "confirmar-importacion/",
            {"importacion": propuesta["id"]}, format="json")
        self.assertEqual(confirmada.status_code, 400, getattr(confirmada, "data", confirmada.content))
        subsanada = self.client.post(self.base + "subsanar-importacion/", {
            "importacion": propuesta["id"], "fila": 1, "revision": 1,
            "motivo": "Intento por ruta legacy", "accion": "omitir",
        }, format="json")
        self.assertEqual(subsanada.status_code, 400, getattr(subsanada, "data", subsanada.content))
        self.assertEqual(list(m.Importacion.objects.order_by("pk").values()), anterior)
        self.assertEqual(self.huella(), huella)
        self.assertEqual(m.Importacion.objects.filter(tipo="novedades").count(), 1)
        self.assertEqual(m.EventoCobertura.objects.filter(accion="crear_novedad").count(), 1)

    def test_conflicto_rectificacion_y_decisiones_conservan_antecedente_y_padron(self):
        anterior = self.huella()
        original = self.crear()
        rectificada = self.crear(rectifica=original["id"], codigo="RECTIFICADO")
        self.assertIn("referencia_repetida", rectificada["conflictos"])
        url = self.base + f"novedades/{rectificada['id']}/resolver/"
        entrada = self.decision(rectificada)
        rechazada = self.client.post(url, entrada, format="json")
        self.assertEqual(rechazada.status_code, 400, getattr(rechazada, "data", rechazada.content))
        self.assertEqual(len(m.Importacion.objects.get(pk=rectificada["id"]).filas[0]["historia"]), 1)
        entrada["confirmar_conflictos"] = True
        decidida = self.client.post(url, entrada, format="json")
        self.assertEqual(decidida.status_code, 200, decidida.data)
        self.assertEqual(decidida.data["estado"], "conciliada")
        self.assertFalse(decidida.data["efectos_aplicados"])
        self.assertEqual(len(decidida.data["historia"]), 2)
        repetida = self.client.post(url, entrada, format="json")
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(repetida.data["historia"], decidida.data["historia"])
        incompatible = self.client.post(url, {**entrada, "accion": "descartar"}, format="json")
        self.assertEqual(incompatible.status_code, 400, incompatible.data)
        previo = self.client.get(self.base + f"novedades/{original['id']}/").data
        self.assertEqual(previo["estado"], "pendiente")
        self.assertEqual(previo["original"], original["original"])
        descartada = self.client.post(self.base + f"novedades/{original['id']}/resolver/",
            self.decision(previo, accion="descartar"), format="json")
        self.assertEqual(descartada.status_code, 200, descartada.data)
        self.assertEqual(descartada.data["estado"], "descartada")
        self.assertEqual(self.huella(), anterior)

    def test_revision_desactualizada_requiere_comparar_nuevamente(self):
        propuesta = self.crear()
        url = self.base + f"novedades/{propuesta['id']}/resolver/"
        editada = self.client.patch(self.base + f"padron/{self.afiliado.pk}/", {
            "revision": self.afiliado.revision, "motivo": "Edición ficticia posterior",
            "nombre": "Persona ficticia actualizada",
        }, format="json")
        self.assertEqual(editada.status_code, 200, editada.data)
        anterior = self.huella()
        rechazada = self.client.post(url, self.decision(propuesta), format="json")
        self.assertEqual(rechazada.status_code, 400, getattr(rechazada, "data", rechazada.content))
        actual = self.client.get(self.base + f"novedades/{propuesta['id']}/").data
        self.assertIn("padron_modificado", actual["conflictos"])
        self.assertEqual(len(actual["historia"]), 1)
        decidida = self.client.post(url, self.decision(actual, confirmar_conflictos=True), format="json")
        self.assertEqual(decidida.status_code, 200, decidida.data)
        self.assertEqual(decidida.data["original"], propuesta["original"])
        self.assertEqual(self.huella(), anterior)

    def test_permisos_ambitos_y_campos_no_admitidos_no_modifican_propuestas(self):
        propuesta = self.crear()
        otra = m.Financiador.objects.create(nombre="Financiador sintético B", tipo="obra_social")
        ajeno = m.Afiliado.objects.create(financiador=otra, numero="00001",
            documento=self.afiliado.documento, nombre="Persona sintética B", desde=self.hoy)
        anterior = self.huella()
        filas = list(m.Importacion.objects.order_by("pk").values())
        for extra in ({"financiador_id": otra.pk}, {"cobertura_habilitada": True},
                      {"motivo": " "}, {"fecha_informada": "no-fecha"}):
            respuesta = self.client.post(self.base + "novedades/", self.entrada(**extra), format="json")
            self.assertEqual(respuesta.status_code, 400, respuesta.data)
        extranjero = self.client.post(self.base + "novedades/", self.entrada(afiliado=ajeno.pk), format="json")
        self.assertEqual(extranjero.status_code, 404, extranjero.data)
        base_b = f"/api/financiadores/{otra.pk}/"
        self.assertEqual(self.client.get(base_b + "novedades/").status_code, 404)
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.client.get(self.base + f"novedades/{propuesta['id']}/").status_code, 200)
        self.assertEqual(self.client.post(self.base + "novedades/", self.entrada(), format="json").status_code, 403)
        url = self.base + f"novedades/{propuesta['id']}/resolver/"
        self.assertEqual(self.client.post(url, self.decision(propuesta), format="json").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.base + "novedades/").status_code, 401)
        self.assertEqual(self.huella(), anterior)
        self.assertEqual(list(m.Importacion.objects.order_by("pk").values()), filas)

    def test_misma_clave_en_otro_financiador_no_comparte_evidencia(self):
        entrada = self.entrada()
        a = self.client.post(self.base + "novedades/", entrada, format="json")
        self.assertEqual(a.status_code, 201, a.data)
        otra = m.Financiador.objects.create(nombre="Financiador sintético B", tipo="obra_social")
        m.MembresiaFinanciador.objects.create(financiador=otra, usuario=self.operador, rol="operador")
        ajeno = m.Afiliado.objects.create(financiador=otra, numero="00001",
            documento=self.afiliado.documento, nombre="Persona sintética B", desde=self.hoy)
        base_b = f"/api/financiadores/{otra.pk}/"
        b = self.client.post(base_b + "novedades/", {**entrada, "afiliado": ajeno.pk}, format="json")
        self.assertEqual(b.status_code, 201, b.data)
        self.assertNotEqual(a.data["id"], b.data["id"])
        self.assertEqual(b.data["coincidencias"], [])
        self.assertEqual(self.client.get(base_b + f"novedades/{a.data['id']}/").status_code, 404)
        self.assertEqual(self.client.post(base_b + "novedades/",
            {**entrada, "clave": str(uuid4()), "afiliado": ajeno.pk, "rectifica": a.data["id"]},
            format="json").status_code, 404)

    def test_decisiones_invalidas_no_modifican_propuesta_ni_auditoria(self):
        propuesta = self.crear()
        anterior = self.huella_propuestas_y_auditoria()
        for entrada in ([], None, {"accion": "conciliar"},
                        self.decision(propuesta, financiador=123), self.decision(propuesta, revision=2)):
            with self.subTest(entrada=entrada):
                respuesta = self.client.post(self.base + f"novedades/{propuesta['id']}/resolver/",
                    entrada, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertEqual(self.huella_propuestas_y_auditoria(), anterior)

    def test_rectificacion_de_otra_persona_y_decision_ajena_no_escriben(self):
        propuesta = self.crear()
        persona = m.Afiliado.objects.create(financiador=self.financiador, numero="FICTICIA-2",
            documento="90000002", nombre="Otra persona ficticia", desde=self.hoy)
        otra = m.Financiador.objects.create(nombre="Otro financiador ficticio", tipo="obra_social")
        m.MembresiaFinanciador.objects.create(financiador=otra, usuario=self.operador, rol="operador")
        anterior = self.huella_propuestas_y_auditoria()
        respuesta = self.client.post(self.base + "novedades/",
            self.entrada(afiliado=persona.pk, rectifica=propuesta["id"]), format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        ajena = self.client.post(f"/api/financiadores/{otra.pk}/novedades/{propuesta['id']}/resolver/",
            self.decision(propuesta), format="json")
        self.assertEqual(ajena.status_code, 404, ajena.data)
        self.assertEqual(self.huella_propuestas_y_auditoria(), anterior)

    def test_membresia_revocada_impide_consulta_y_reintento_exacto(self):
        entrada = self.entrada()
        propuesta = self.client.post(self.base + "novedades/", entrada, format="json").data
        self.membresia.activo = False
        self.membresia.save(update_fields=["activo"])
        anterior = self.huella_propuestas_y_auditoria()
        self.assertEqual(self.client.get(self.base + f"novedades/{propuesta['id']}/").status_code, 404)
        self.assertEqual(self.client.post(self.base + "novedades/", entrada, format="json").status_code, 404)
        self.assertEqual(self.huella_propuestas_y_auditoria(), anterior)

    def test_otras_rutas_legacy_rechazan_propuesta_sin_crear_eventos(self):
        propuesta = self.crear()
        anterior = self.huella_propuestas_y_auditoria()
        rutas = [
            ("get", f"rechazos/?importacion={propuesta['id']}", None),
            ("post", "subsanar-ostel/", {"importacion": propuesta["id"], "fila": 1,
                "revision": 1, "datos": {}, "motivo": "Intento ficticio"}),
            ("post", "confirmar-importacion/", {"importacion": propuesta["id"],
                "modo_respuesta": "cambios", "huella_lote": "x" * 64}),
        ]
        for metodo, ruta, datos in rutas:
            with self.subTest(ruta=ruta):
                respuesta = getattr(self.client, metodo)(self.base + ruta, datos, format="json")
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertEqual(self.huella_propuestas_y_auditoria(), anterior)


@skipUnless(connection.vendor == "postgresql", "Los locks de Novedades requieren PostgreSQL.")
class NovedadesConcurrenciaTests(NovedadesSetup, TransactionTestCase):
    def paralelo(self, url, entradas):
        barrera = Barrier(2)

        def solicitar(entrada):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(self.operador)
                barrera.wait(timeout=10)
                respuesta = cliente.post(url, entrada, format="json")
                return respuesta.status_code, respuesta.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(solicitar, entradas))

    def test_registro_simultaneo_misma_clave_crea_una_propuesta(self):
        anterior = self.huella()
        entrada = self.entrada()
        respuestas = self.paralelo(self.base + "novedades/", [entrada, entrada])
        self.assertEqual(sorted(estado for estado, _ in respuestas), [200, 201], respuestas)
        self.assertEqual(len({datos["id"] for _, datos in respuestas}), 1)
        self.assertEqual(m.Importacion.objects.filter(tipo="novedades").count(), 1)
        self.assertEqual(m.EventoCobertura.objects.filter(accion="crear_novedad").count(), 1)
        self.assertEqual(self.huella(), anterior)

    def test_reintento_simultaneo_resuelve_una_vez(self):
        propuesta = self.crear()
        anterior = self.huella()
        entrada = self.decision(propuesta)
        respuestas = self.paralelo(self.base + f"novedades/{propuesta['id']}/resolver/", [entrada, entrada])
        self.assertEqual([estado for estado, _ in respuestas], [200, 200], respuestas)
        self.assertTrue(all(len(datos["historia"]) == 2 for _, datos in respuestas))
        self.assertEqual(m.EventoCobertura.objects.filter(accion="resolver_novedad").count(), 1)
        self.assertEqual(self.huella(), anterior)

    def test_decisiones_simultaneas_incompatibles_no_sobrescriben_historia(self):
        propuesta = self.crear()
        anterior = self.huella()
        respuestas = self.paralelo(self.base + f"novedades/{propuesta['id']}/resolver/", [
            self.decision(propuesta), self.decision(propuesta, accion="descartar")])
        self.assertEqual(sorted(estado for estado, _ in respuestas), [200, 400], respuestas)
        self.assertEqual(len(m.Importacion.objects.get(pk=propuesta["id"]).filas[0]["historia"]), 2)
        self.assertEqual(m.EventoCobertura.objects.filter(accion="resolver_novedad").count(), 1)
        self.assertEqual(self.huella(), anterior)
