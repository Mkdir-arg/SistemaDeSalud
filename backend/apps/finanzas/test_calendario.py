from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from .models import ConceptoGasto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto
from .services import registrar_gasto


class CalendarioGastoApiTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.otra_area = Area.objects.create(institucion=self.institucion, nombre="Clínica")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo="LUZ", nombre="Electricidad"
        )
        self.admin = Usuario.objects.create_user("calendario@cauce.local", "x")
        self.miembro = Membresia.objects.create(
            usuario=self.admin, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION
        )
        for accion in (
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            ConcesionFinanciera.Accion.VER_GASTOS,
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
        ):
            ConcesionFinanciera.objects.create(
                membresia=self.miembro, accion=accion, todas_las_areas=True, permite_sensibles=True
            )
        self.client.force_authenticate(self.admin)
        self.expectativa = self.crear_expectativa(self.area)

    def crear_expectativa(self, area, **datos):
        return ExpectativaGasto.objects.create(
            concepto=self.concepto, institucion=self.institucion, area=area,
            vigente_desde=date(2026, 8, 1), **datos
        )

    def calendario(self, mes="2026-08-01", **filtros):
        respuesta = self.client.get(
            "/api/expectativas-gasto/calendario/", {"periodo_economico": mes, **filtros}
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data

    def indicar(self, estado, expectativa=None, mes="2026-08-01"):
        return self.client.post(
            f"/api/expectativas-gasto/{(expectativa or self.expectativa).id}/indicar/",
            {"periodo_economico": mes, "estado": estado}, format="json"
        )

    def test_flujo_faltante_carga_parcial_indicacion_y_dato_tardio(self):
        fila = self.calendario()["results"][0]
        self.assertEqual(fila["estado_carga"], "falta_cargar")
        self.assertIsNone(fila["indicacion_id"])
        self.assertNotIn("importe", fila)
        delegado = Usuario.objects.create_user("delegado-cal@cauce.local", "x")
        miembro = Membresia.objects.create(
            usuario=delegado, institucion=self.institucion, rol=Membresia.Rol.MEDICO
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=miembro, accion=ConcesionFinanciera.Accion.REGISTRAR_GASTOS
        )
        concesion.areas.add(self.area)
        pendiente = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), date(2026, 8, 1), delegado)
        registrar_gasto(self.concepto, self.institucion, self.area, Decimal("120"), date(2026, 8, 1), delegado, reemplaza=pendiente)
        parcial = self.calendario()["results"][0]
        self.assertEqual(parcial["estado_carga"], "falta_cargar")
        self.assertEqual(parcial["gastos_pendientes"], 1)
        completa = self.indicar("carga_completa")
        self.assertEqual(completa.status_code, 201, completa.data)
        fila = self.calendario()["results"][0]
        self.assertEqual(fila["estado_carga"], "carga_completa")
        self.assertEqual(fila["gastos_pendientes"], 1)
        self.assertEqual(fila["gastos_aprobados"], 0)
        registrar_gasto(self.concepto, self.institucion, self.area, Decimal("20"), date(2026, 8, 1), self.admin)
        self.assertEqual(self.indicar("falta_cargar").status_code, 201)
        fila = self.calendario()["results"][0]
        self.assertEqual(fila["gastos_aprobados"], 1)
        self.assertEqual(fila["estado_carga"], "falta_cargar")
        historia = self.client.get(f"/api/expectativas-gasto/{self.expectativa.id}/indicaciones/")
        self.assertEqual(historia.status_code, 200)
        self.assertEqual([r["estado"] for r in historia.data["results"]], ["falta_cargar", "carga_completa"])

    def test_no_corresponde_no_crea_gasto_y_no_completa_otras_areas(self):
        otra = self.crear_expectativa(self.otra_area)
        self.assertEqual(self.indicar("no_corresponde").status_code, 201)
        filas = {f["id"]: f for f in self.calendario()["results"]}
        self.assertEqual(filas[self.expectativa.id]["estado_carga"], "no_corresponde")
        self.assertEqual(filas[otra.id]["estado_carga"], "falta_cargar")
        self.assertFalse(Gasto.objects.exists())

    def test_vigencias_con_sucesor_futuro_conservan_mes_anterior(self):
        sucesor = ExpectativaGasto.objects.create(
            concepto=self.concepto, institucion=self.institucion, area=self.area,
            vigente_desde=date(2026, 9, 1), vigente_hasta=date(2026, 10, 1), reemplaza=self.expectativa
        )
        self.assertEqual([f["id"] for f in self.calendario()["results"]], [self.expectativa.id])
        self.assertEqual([f["id"] for f in self.calendario("2026-09-01")["results"]], [sucesor.id])
        self.assertEqual(self.calendario("2026-10-01")["results"], [])
        self.assertEqual(self.indicar("carga_completa").status_code, 201)
        self.assertEqual(self.indicar("carga_completa", mes="2026-09-01").status_code, 400)
        self.assertEqual(self.calendario("2026-07-01")["results"], [])

    def test_conteos_respetan_area_e_institucion(self):
        institucional = self.crear_expectativa(None)
        otra = self.crear_expectativa(self.otra_area)
        registrar_gasto(self.concepto, self.institucion, None, Decimal("100"), date(2026, 8, 1), self.admin)
        registrar_gasto(self.concepto, self.institucion, self.area, Decimal("20"), date(2026, 8, 1), self.admin)
        filas = {f["id"]: f for f in self.calendario()["results"]}
        self.assertEqual(filas[institucional.id]["gastos_aprobados"], 1)
        self.assertEqual(filas[self.expectativa.id]["gastos_aprobados"], 1)
        self.assertEqual(filas[otra.id]["gastos_aprobados"], 0)

    def test_version_por_api_conserva_historial_y_rechaza_reenvio(self):
        self.assertEqual(self.indicar("carga_completa").status_code, 201)
        datos = {
            "concepto": self.concepto.id, "institucion": self.institucion.id,
            "area": self.area.id, "vigente_desde": "2026-09-01",
            "vigente_hasta": "2026-10-01", "reemplaza": self.expectativa.id,
            "motivo_correccion": "Servicio previsto hasta septiembre",
        }
        nueva = self.client.post("/api/expectativas-gasto/", datos, format="json")
        self.assertEqual(nueva.status_code, 201, nueva.data)
        self.assertEqual(self.client.post("/api/expectativas-gasto/", datos, format="json").status_code, 400)
        self.assertEqual(ExpectativaGasto.objects.count(), 2)
        anterior = self.calendario()["results"][0]
        self.assertEqual(anterior["id"], self.expectativa.id)
        self.assertEqual(anterior["estado_carga"], "carga_completa")
        septiembre = self.calendario("2026-09-01")["results"][0]
        self.assertEqual(septiembre["id"], nueva.data["id"])
        self.assertIsNone(septiembre["indicacion_id"])
        self.assertEqual(septiembre["estado_carga"], "falta_cargar")
        self.assertEqual(self.calendario("2026-10-01")["results"], [])
        versiones = self.client.get("/api/expectativas-gasto/", {
            "institucion": self.institucion.id, "concepto": self.concepto.id,
            "area": self.area.id, "ordering": "-vigente_desde,-id",
        })
        self.assertEqual(versiones.status_code, 200)
        self.assertEqual([f["id"] for f in versiones.data["results"]], [nueva.data["id"], self.expectativa.id])
        historial = self.client.get(f"/api/expectativas-gasto/{self.expectativa.id}/indicaciones/")
        self.assertEqual(historial.status_code, 200)
        self.assertEqual(historial.data["results"][0]["estado"], "carga_completa")
        self.assertFalse(Gasto.objects.exists())

    def test_version_por_api_no_cambia_ambito_ni_omite_permiso_anterior(self):
        datos = {
            "concepto": self.concepto.id, "institucion": self.institucion.id,
            "area": self.otra_area.id, "vigente_desde": "2026-09-01",
            "reemplaza": self.expectativa.id, "motivo_correccion": "Cambio inválido",
        }
        self.assertEqual(self.client.post("/api/expectativas-gasto/", datos, format="json").status_code, 400)
        # Aunque el catálogo ya no sea sensible, el permiso sobre la versión
        # histórica sigue siendo necesario para reemplazarla.
        ExpectativaGasto.objects.filter(pk=self.expectativa.pk).update(sensible=True)
        ConcesionFinanciera.objects.filter(membresia=self.miembro).update(permite_sensibles=False)
        datos["area"] = self.area.id
        self.assertEqual(self.client.post("/api/expectativas-gasto/", datos, format="json").status_code, 403)
        self.assertEqual(ExpectativaGasto.objects.count(), 1)

    def test_permisos_por_area_sensibilidad_institucion_y_accion(self):
        self.crear_expectativa(self.otra_area)
        self.crear_expectativa(None)
        ajena = Institucion.objects.create(nombre="Otra institución")
        concepto_ajeno = ConceptoGasto.objects.create(institucion=ajena, codigo="LUZ", nombre="Luz")
        ExpectativaGasto.objects.create(concepto=concepto_ajeno, institucion=ajena, vigente_desde=date(2026, 8, 1))
        lector = Usuario.objects.create_user("lector-cal@cauce.local", "x")
        miembro = Membresia.objects.create(usuario=lector, institucion=self.institucion, rol=Membresia.Rol.MEDICO)
        concesion = ConcesionFinanciera.objects.create(membresia=miembro, accion=ConcesionFinanciera.Accion.VER_GASTOS)
        concesion.areas.add(self.area)
        self.client.force_authenticate(lector)
        self.assertEqual([f["id"] for f in self.calendario()["results"]], [self.expectativa.id])
        self.assertEqual(self.indicar("carga_completa").status_code, 403)
        self.assertEqual(self.calendario(institucion=ajena.id)["results"], [])
        # Cambio posterior del catálogo: un gasto sensible no se filtra a través
        # del conteo de una expectativa histórica no sensible.
        self.concepto.sensible = True
        self.concepto.save()
        registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), date(2026, 8, 1), self.admin)
        self.assertEqual(self.calendario()["results"][0]["gastos_aprobados"], 0)
        sensible = self.crear_expectativa(self.otra_area, reemplaza=ExpectativaGasto.objects.get(area=self.otra_area), motivo_correccion="Sensibilidad")
        self.client.force_authenticate(self.admin)
        ConcesionFinanciera.objects.filter(membresia=self.miembro).update(permite_sensibles=False)
        self.assertNotIn(sensible.id, [f["id"] for f in self.calendario()["results"]])
        self.assertEqual(self.client.get(f"/api/expectativas-gasto/{sensible.id}/").status_code, 404)
        self.assertEqual(self.indicar("carga_completa", sensible).status_code, 404)

    def test_api_alta_y_correccion_inmutables_y_periodo_invalido(self):
        datos = {"concepto": self.concepto.id, "institucion": self.institucion.id,
                 "area": self.otra_area.id, "vigente_desde": "2026-08-01"}
        alta = self.client.post("/api/expectativas-gasto/", datos, format="json")
        self.assertEqual(alta.status_code, 201, alta.data)
        original = alta.data["id"]
        self.assertEqual(self.client.patch(f"/api/expectativas-gasto/{original}/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/expectativas-gasto/{original}/").status_code, 405)
        datos.update(reemplaza=original, motivo_correccion="Confirmación de ámbito")
        correccion = self.client.post("/api/expectativas-gasto/", datos, format="json")
        self.assertEqual(correccion.status_code, 201, correccion.data)
        self.assertNotIn(original, [f["id"] for f in self.calendario()["results"]])
        for entrada in ({}, {"periodo_economico": "2026-08-02"}, {"periodo_economico": "inválido"}):
            self.assertEqual(self.client.get("/api/expectativas-gasto/calendario/", entrada).status_code, 400)
        self.assertFalse(IndicacionCargaGasto.objects.exists())
