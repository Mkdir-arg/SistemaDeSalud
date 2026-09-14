from datetime import date
from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from .models import AjusteGasto, ConceptoGasto, ConcesionFinanciera, ExpectativaGasto, Gasto, IndicacionCargaGasto
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

    def test_conteos_navegan_a_gastos_vigentes_del_area_exacta_incluido_nulo(self):
        institucional = self.crear_expectativa(None)
        for area in (self.area, None):
            original = Gasto.objects.create(
                concepto=self.concepto, institucion=self.institucion, area=area,
                concepto_codigo="LUZ", concepto_nombre="Electricidad", importe="10.00",
                periodo_economico=date(2026, 8, 1), estado=Gasto.Estado.PENDIENTE_APROBACION,
                origen=Gasto.Origen.AREA,
            )
            Gasto.objects.create(
                concepto=self.concepto, institucion=self.institucion, area=area,
                concepto_codigo="LUZ", concepto_nombre="Electricidad", importe="20.00",
                periodo_economico=date(2026, 8, 1), estado=Gasto.Estado.PENDIENTE_APROBACION,
                reemplaza=original, origen=Gasto.Origen.AREA,
            )
            registrar_gasto(self.concepto, self.institucion, area, Decimal("30"), date(2026, 8, 1), self.admin)
        filas = {fila["id"]: fila for fila in self.calendario()["results"]}
        for expectativa in (self.expectativa, institucional):
            for estado, columna in (("aprobado", "gastos_aprobados"), ("pendiente_aprobacion", "gastos_pendientes")):
                respuesta = self.client.get("/api/gastos/", {
                    "institucion": self.institucion.pk,
                    "area": expectativa.area_id if expectativa.area_id else "null",
                    "concepto": self.concepto.pk, "periodo_economico": "2026-08-01",
                    "estado_operativo": estado,
                })
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data["count"], filas[expectativa.pk][columna])
                self.assertEqual(respuesta.data["count"], 1)
                self.assertEqual(respuesta.data["results"][0]["area"], expectativa.area_id)
                self.assertIsNone(respuesta.data["results"][0]["reemplazado_por"])
        reemplazados = self.client.get("/api/gastos/", {"estado_operativo": "reemplazado"})
        self.assertEqual(reemplazados.data["count"], 2)

    def test_orden_y_rangos_de_calendario_y_gastos_se_aplican_antes_de_paginar(self):
        self.crear_expectativa(self.otra_area)
        for area, cantidad in ((self.area, 2), (self.otra_area, 1)):
            for indice in range(cantidad):
                registrar_gasto(self.concepto, self.institucion, area, Decimal(10 + indice), date(2026, 8, 1), self.admin)
        pagina = self.calendario(ordering="-gastos_aprobados", page_size=1, page=2)
        self.assertEqual(pagina["count"], 2)
        self.assertEqual(pagina["results"][0]["area"], self.otra_area.pk)
        filtrado = self.calendario(gastos_aprobados_min=2, estado_carga="falta_cargar")
        self.assertEqual(filtrado["count"], 1)
        self.assertEqual(filtrado["results"][0]["area"], self.area.pk)
        gasto = Gasto.objects.filter(area=self.otra_area).get()
        for valor in (Decimal("0.01"), Decimal("0.02")):
            AjusteGasto.objects.create(gasto=gasto, importe=valor, motivo="Centavos", registrado_por=self.admin)
        resultado = self.client.get("/api/gastos/", {
            "ordering": "-importe_resultante", "page_size": 1, "page": 2,
        })
        self.assertEqual(resultado.status_code, 200, resultado.data)
        self.assertEqual(resultado.data["count"], 3)
        self.assertEqual(resultado.data["results"][0]["id"], gasto.pk)
        self.assertEqual(resultado.data["results"][0]["total_ajustes"], "0.03")
        self.assertEqual(resultado.data["results"][0]["importe_resultante"], "10.03")
        filtrado = self.client.get("/api/gastos/", {
            "importe_resultante_min": "10.03", "importe_resultante_max": "10.03",
            "total_ajustes_min": "0.03", "importe_max": "10.00",
        })
        self.assertEqual(filtrado.data["count"], 1)
        self.assertEqual(filtrado.data["results"][0]["id"], gasto.pk)

    def test_empates_del_calendario_y_gastos_tienen_desempate_unico_entre_paginas(self):
        otras = [self.crear_expectativa(self.otra_area), self.crear_expectativa(None)]
        gastos = [registrar_gasto(
            self.concepto, self.institucion, area, Decimal("10.01"), date(2026, 8, 1), self.admin,
        ) for area in (self.area, self.otra_area, None)]
        recibidos_calendario, recibidos_gastos = [], []
        for pagina in (1, 2, 3):
            calendario = self.calendario(ordering="concepto__nombre", page_size=1, page=pagina)
            recibidos_calendario.append(calendario["results"][0]["id"])
            respuesta = self.client.get("/api/gastos/", {
                "ordering": "importe_resultante", "page_size": 1, "page": pagina,
            })
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            recibidos_gastos.append(respuesta.data["results"][0]["id"])
        self.assertEqual(recibidos_calendario, sorted([self.expectativa.pk, *[fila.pk for fila in otras]], reverse=True))
        self.assertEqual(recibidos_gastos, sorted([gasto.pk for gasto in gastos], reverse=True))

    def test_filtros_de_columna_invalidos_responden_400(self):
        for ruta, datos in (
            ("/api/gastos/", {"importe_min": "NaN"}),
            ("/api/gastos/", {"registrado_desde": "ayer"}),
            ("/api/gastos/", {"estado_operativo": "inexistente"}),
            ("/api/expectativas-gasto/calendario/", {"periodo_economico": "2026-08-01", "gastos_aprobados_min": "x"}),
        ):
            respuesta = self.client.get(ruta, datos)
            self.assertEqual(respuesta.status_code, 400, respuesta.data)

    def test_lector_solo_recibe_conceptos_usados_en_su_area_y_no_puede_escribir(self):
        oculto = ConceptoGasto.objects.create(institucion=self.institucion, codigo="OTRO", nombre="Otra área")
        sin_uso = ConceptoGasto.objects.create(institucion=self.institucion, codigo="NUEVO", nombre="Sin uso")
        sensible = ConceptoGasto.objects.create(institucion=self.institucion, codigo="HON", nombre="Honorarios", sensible=True)
        registrar_gasto(oculto, self.institucion, self.otra_area, Decimal("20"), date(2026, 8, 1), self.admin)
        registrar_gasto(sensible, self.institucion, self.area, Decimal("30"), date(2026, 8, 1), self.admin)
        lector = Usuario.objects.create_user("lector-filtros@cauce.local", "x")
        membresia = Membresia.objects.create(usuario=lector, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        permiso = ConcesionFinanciera.objects.create(membresia=membresia, accion=ConcesionFinanciera.Accion.VER_GASTOS)
        permiso.areas.add(self.area)
        self.client.force_authenticate(lector)
        lista = self.client.get("/api/conceptos-gasto/")
        self.assertEqual(lista.status_code, 200, lista.data)
        self.assertEqual([fila["id"] for fila in lista.data["results"]], [self.concepto.pk])
        for concepto in (oculto, sensible, sin_uso):
            self.assertEqual(self.client.get(f"/api/conceptos-gasto/{concepto.pk}/").status_code, 404)
        self.assertEqual(self.client.post("/api/conceptos-gasto/", {
            "institucion": self.institucion.pk, "codigo": "SIN", "nombre": "Sin permiso",
        }, format="json").status_code, 403)

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
        # Las restricciones explícitas se prueban con contador, no con lectura
        # sensible predeterminada del rol administrador.
        self.miembro.rol = Membresia.Rol.ADMINISTRATIVO
        self.miembro.save()
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

    def test_referencia_compara_neto_aprobado_sin_cerrar_carga_ni_sumar_otras_areas(self):
        respuesta = self.client.post("/api/expectativas-gasto/", {
            "concepto": self.concepto.pk, "institucion": self.institucion.pk,
            "area": self.area.pk, "vigente_desde": "2026-08-01",
            "reemplaza": self.expectativa.pk, "motivo_correccion": "Incluir referencia",
            "monto_referencia": "90.00",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), date(2026, 8, 1), self.admin)
        AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-10"), motivo="Corrección", registrado_por=self.admin)
        registrar_gasto(self.concepto, self.institucion, self.otra_area, Decimal("999"), date(2026, 8, 1), self.admin)
        registrar_gasto(self.concepto, self.institucion, None, Decimal("999"), date(2026, 8, 1), self.admin)
        fila = self.calendario()["results"][0]
        self.assertEqual(fila["importe_aprobado"], "90.00")
        self.assertEqual(fila["diferencia_referencia"], "0.00")
        self.assertEqual(fila["estado_carga"], "falta_cargar")
        self.assertFalse(IndicacionCargaGasto.objects.exists())
        original = self.client.get(f"/api/expectativas-gasto/{self.expectativa.pk}/").data
        self.assertIsNone(original["monto_referencia"])

    def test_referencia_opcional_rechaza_negativos_y_preserva_centavos(self):
        self.assertIsNone(self.calendario()["results"][0]["diferencia_referencia"])
        datos = {"concepto": self.concepto.pk, "institucion": self.institucion.pk,
                 "area": self.otra_area.pk, "vigente_desde": "2026-08-01"}
        for importe in ("-0.01", "0.001"):
            respuesta = self.client.post("/api/expectativas-gasto/", {**datos, "monto_referencia": importe}, format="json")
            self.assertEqual(respuesta.status_code, 400)
        respuesta = self.client.post("/api/expectativas-gasto/", {**datos, "monto_referencia": "0.01"}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        fila = self.calendario(area=self.otra_area.pk)["results"][0]
        self.assertEqual(fila["monto_referencia"], "0.01")
        self.assertEqual(fila["importe_aprobado"], "0.00")
        self.assertEqual(fila["diferencia_referencia"], "0.01")
        self.assertEqual(self.calendario(monto_referencia_min="0.02")["results"], [])
        self.assertEqual(len(self.calendario(diferencia_referencia_min="0.01")["results"]), 1)
        self.assertEqual(self.client.get("/api/expectativas-gasto/calendario/", {
            "periodo_economico": "2026-08-01", "importe_aprobado_min": "NaN",
        }).status_code, 400)

    def test_aprobado_suma_fuentes_iguales_una_vez_y_omite_pendientes(self):
        for _ in range(2):
            gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), date(2026, 8, 1), self.admin)
            AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-10"), motivo="Ajuste uno", registrado_por=self.admin)
            AjusteGasto.objects.create(gasto=gasto, importe=Decimal("5"), motivo="Ajuste dos", registrado_por=self.admin)
        Gasto.objects.create(
            concepto=self.concepto, institucion=self.institucion, area=self.area,
            concepto_codigo=self.concepto.codigo, concepto_nombre=self.concepto.nombre,
            importe="999", periodo_economico=date(2026, 8, 1), origen=Gasto.Origen.AREA,
        )
        fila = self.calendario()["results"][0]
        self.assertEqual(fila["importe_aprobado"], "190.00")
        self.assertEqual(fila["gastos_aprobados"], 2)
        self.assertEqual(fila["gastos_pendientes"], 1)
