"""Auditoría financiera por API, separada de la lectura clínica."""
from datetime import date
from unittest.mock import patch

from django.db import DatabaseError
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano
from .models import AccesoFinanciero, ConceptoGasto, ConcesionFinanciera, ExpectativaGasto
from .services import registrar_gasto


class AuditoriaFinancieraTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.usuario = Usuario.objects.create_user("auditoria-financiera@test.local", "x")
        self.membresia = Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol="admin",
        )
        for accion in ("registrar_gastos", "ver_gastos", "configurar_gastos_esperados"):
            ConcesionFinanciera.objects.create(
                membresia=self.membresia, accion=accion, todas_las_areas=True, permite_sensibles=True,
            )
        concepto = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo="LUZ", nombre="Electricidad",
        )
        self.gasto = registrar_gasto(
            concepto=concepto, institucion=self.institucion, area=self.area,
            importe="8500.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario,
        )
        self.client.force_authenticate(self.usuario)

    def habilitar_auditoria(self, sensible=False, area=None):
        permiso = ConcesionFinanciera.objects.create(
            membresia=self.membresia, accion="auditar_finanzas",
            todas_las_areas=area is None, permite_sensibles=sensible,
        )
        if area is not None:
            permiso.areas.add(area)
        return permiso

    def test_detalle_registra_metadatos_y_exige_permiso_para_auditarlos(self):
        respuesta = self.client.get(f"/api/gastos/{self.gasto.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.client.get("/api/accesos-financieros/").status_code, 403)
        self.habilitar_auditoria()
        auditoria = self.client.get("/api/accesos-financieros/")
        self.assertEqual(auditoria.status_code, 200)
        self.assertEqual(auditoria.data["count"], 1)
        acceso = auditoria.data["results"][0]
        self.assertEqual(acceso["usuario"], self.usuario.pk)
        self.assertEqual(acceso["institucion"], self.institucion.pk)
        self.assertEqual(acceso["area"], self.area.pk)
        self.assertEqual(acceso["recurso"], "gasto")
        self.assertEqual(acceso["accion"], "retrieve")
        self.assertEqual(acceso["objeto_id"], self.gasto.pk)
        self.assertEqual(acceso["resultados"], 1)
        self.assertNotIn("8500", str(acceso))
        self.assertNotIn("Electricidad", str(acceso))

    def test_listas_calendario_e_historial_auditan_la_pagina_real_sin_filtros_libres(self):
        self.habilitar_auditoria()
        expectativa = ExpectativaGasto.objects.create(
            concepto=self.gasto.concepto, institucion=self.institucion,
            area=self.area, vigente_desde=date(2026, 8, 1),
        )
        consultas = [
            ("/api/gastos/?page_size=1", "gasto", "list", 1),
            ("/api/conceptos-gasto/", "conceptogasto", "list", 1),
            (f"/api/conceptos-gasto/{self.gasto.concepto_id}/", "conceptogasto", "retrieve", 1),
            ("/api/expectativas-gasto/", "expectativagasto", "list", 1),
            (f"/api/expectativas-gasto/{expectativa.pk}/", "expectativagasto", "retrieve", 1),
            ("/api/expectativas-gasto/calendario/?periodo_economico=2026-08-01", "expectativagasto", "calendario", 1),
            (f"/api/expectativas-gasto/{expectativa.pk}/indicaciones/", "expectativagasto", "indicaciones", 0),
        ]
        for numero, (url, recurso, accion, cantidad) in enumerate(consultas, start=1):
            with self.subTest(url=url):
                separador = "&" if "?" in url else "?"
                respuesta = self.client.get(url + separador + "texto=SECRETO_NO_COPIAR")
                self.assertEqual(respuesta.status_code, 200)
                auditoria = self.client.get("/api/accesos-financieros/")
                self.assertEqual(auditoria.data["count"], numero)
                acceso = auditoria.data["results"][0]
                self.assertEqual(acceso["recurso"], recurso)
                self.assertEqual(acceso["accion"], accion)
                self.assertEqual(acceso["resultados"], cantidad)
                self.assertEqual(acceso["institucion"], self.institucion.pk)
                self.assertNotIn("SECRETO_NO_COPIAR", str(acceso))

    def test_fallo_de_persistencia_no_entrega_datos_ni_bloquea_lectura_clinica(self):
        paciente = Ciudadano.objects.create(
            institucion=self.institucion, nombre="Ana", apellido="Prueba",
        )
        expectativa = ExpectativaGasto.objects.create(
            concepto=self.gasto.concepto, institucion=self.institucion,
            area=self.area, vigente_desde=date(2026, 8, 1),
        )
        with patch.object(AccesoFinanciero.objects, "create", side_effect=DatabaseError("importe privado")):
            for url in (
                f"/api/gastos/{self.gasto.pk}/", "/api/gastos/", "/api/conceptos-gasto/",
                "/api/expectativas-gasto/",
                "/api/expectativas-gasto/calendario/?periodo_economico=2026-08-01",
                f"/api/expectativas-gasto/{expectativa.pk}/indicaciones/",
            ):
                with self.subTest(url=url), self.assertLogs("apps.finanzas.auditoria", level="ERROR") as logs:
                    respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 503)
                self.assertEqual(set(respuesta.data), {"detail"})
                self.assertNotIn("8500", str(respuesta.data))
                self.assertNotIn("importe privado", str(logs.output))
            clinica = self.client.get(f"/api/ciudadanos/{paciente.pk}/")
        self.assertEqual(clinica.status_code, 200)
        self.habilitar_auditoria()
        self.assertEqual(self.client.get("/api/accesos-financieros/").data["count"], 0)

    def test_fallo_del_segundo_ambito_revierte_el_registro_completo(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Cirugía")
        registrar_gasto(
            concepto=self.gasto.concepto, institucion=self.institucion, area=otra_area,
            importe="100.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario,
        )
        crear = AccesoFinanciero.objects.create
        llamadas = 0

        def fallar_segunda_escritura(**datos):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise DatabaseError("Escritura no disponible")
            return crear(**datos)

        with patch.object(AccesoFinanciero.objects, "create", side_effect=fallar_segunda_escritura):
            with self.assertLogs("apps.finanzas.auditoria", level="ERROR"):
                respuesta = self.client.get("/api/gastos/")
        self.assertEqual(respuesta.status_code, 503)
        self.habilitar_auditoria()
        self.assertEqual(self.client.get("/api/accesos-financieros/").data["count"], 0)
        self.assertEqual(self.client.get("/api/gastos/?page_size=1").status_code, 200)
        pagina = self.client.get("/api/accesos-financieros/").data
        self.assertEqual(pagina["count"], 1)
        self.assertEqual(pagina["results"][0]["resultados"], 1)

    def test_auditoria_respeta_institucion_area_y_sensible_en_la_misma_concesion(self):
        restringida = self.habilitar_auditoria(area=self.area)
        sensible = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo="SUELDOS", nombre="Sueldos", sensible=True,
        )
        registrar_gasto(
            concepto=sensible, institucion=self.institucion, area=self.area,
            importe="300.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario,
        )
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        registrar_gasto(
            concepto=self.gasto.concepto, institucion=self.institucion, area=otra_area,
            importe="200.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario,
        )
        otra = Institucion.objects.create(nombre="Otro hospital")
        miembro_otra = Membresia.objects.create(usuario=self.usuario, institucion=otra, rol="admin")
        for accion in ("registrar_gastos", "ver_gastos", "auditar_finanzas"):
            ConcesionFinanciera.objects.create(
                membresia=miembro_otra, accion=accion, todas_las_areas=True, permite_sensibles=True,
            )
        concepto_otra = ConceptoGasto.objects.create(institucion=otra, codigo="OTRO", nombre="Otro")
        registrar_gasto(
            concepto=concepto_otra, institucion=otra, area=None,
            importe="100.00", periodo_economico=date(2026, 8, 1), registrado_por=self.usuario,
        )
        lectura = self.client.get("/api/gastos/")
        self.assertEqual(lectura.status_code, 200)
        self.assertEqual(lectura.data["count"], 4)
        visibles = self.client.get("/api/accesos-financieros/").data
        self.assertEqual(visibles["count"], 2)
        self.assertEqual(
            {(r["institucion"], r["area"], r["sensible"]) for r in visibles["results"]},
            {(self.institucion.pk, self.area.pk, False), (otra.pk, None, False)},
        )
        restringida.permite_sensibles = True
        restringida.save()
        ampliada = self.client.get("/api/accesos-financieros/").data
        oculta = next(r for r in ampliada["results"] if r["sensible"])
        restringida.permite_sensibles = False
        restringida.save()
        self.assertEqual(self.client.get(f"/api/accesos-financieros/{oculta['id']}/").status_code, 404)
        self.membresia.activo = False
        self.membresia.save()
        restantes = self.client.get("/api/accesos-financieros/").data
        self.assertEqual(restantes["count"], 1)
        self.assertEqual(restantes["results"][0]["institucion"], otra.pk)

    def test_registro_inmutable_y_referencias_conservadas(self):
        self.habilitar_auditoria()
        self.client.get(f"/api/gastos/{self.gasto.pk}/")
        anterior = self.client.get("/api/accesos-financieros/").data["results"][0]
        url = f"/api/accesos-financieros/{anterior['id']}/"
        self.assertEqual(self.client.patch(url, {"resultados": 0}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertEqual(self.client.post("/api/accesos-financieros/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.get(url).data, anterior)
        acceso = AccesoFinanciero.objects.get(pk=anterior["id"])
        with self.assertRaises(ValidationError):
            acceso.save()
        with self.assertRaises(ValidationError):
            acceso.delete()
        with self.assertRaises(ProtectedError) as error:
            self.usuario.delete()
        self.assertIn(acceso, error.exception.protected_objects)

    def test_no_concede_auditoria_al_demover_o_suspender_membresia(self):
        self.habilitar_auditoria(sensible=True)
        self.client.get(f"/api/gastos/{self.gasto.pk}/")
        self.membresia.rol = "medico"
        self.membresia.save()
        self.assertEqual(self.client.get("/api/accesos-financieros/").status_code, 403)
        self.membresia.rol = "admin"
        self.membresia.activo = False
        self.membresia.save()
        self.assertEqual(self.client.get("/api/accesos-financieros/").status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/accesos-financieros/").status_code, 401)

    def test_lista_vacia_y_errores_no_inventan_accesos_a_otra_institucion(self):
        self.habilitar_auditoria()
        ajena = Institucion.objects.create(nombre="Institución ajena")
        self.assertEqual(self.client.get("/api/gastos/", {"institucion": ajena.pk}).status_code, 200)
        # Sin datos ni pertenencia no se atribuye la consulta al hospital ajeno.
        self.assertEqual(self.client.get("/api/accesos-financieros/").data["count"], 0)
        self.assertEqual(self.client.get("/api/gastos/", {
            "institucion": self.institucion.pk, "periodo_economico": "2025-01-01",
        }).status_code, 200)
        visible = self.client.get("/api/accesos-financieros/").data
        self.assertEqual(visible["count"], 1)
        self.assertEqual(visible["results"][0]["resultados"], 0)
        self.assertIsNone(visible["results"][0]["area"])
        self.assertEqual(self.client.get("/api/gastos/999999/").status_code, 404)
        self.assertEqual(self.client.get("/api/expectativas-gasto/calendario/").status_code, 400)
        self.assertEqual(self.client.get("/api/accesos-financieros/").data["count"], 1)
