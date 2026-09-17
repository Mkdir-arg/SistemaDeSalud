from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import AccesoFinanciero, AjusteGasto, ComponenteEsperadoHecho, ConceptoGasto, ConcesionFinanciera, DefinicionComponente, HechoAtencionCosteable, Prestacion
from .services import procesar_reparto_gasto, registrar_gasto


class RepartoActividadApiTests(APITestCase):
    def setUp(self):
        self.mes = timezone.localdate().replace(day=1)
        self.institucion = Institucion.objects.create(nombre="Hospital API")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.otra_area = Area.objects.create(institucion=self.institucion, nombre="Clínica")
        self.admin = Usuario.objects.create_user("admin-repartos-api@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        for accion in (
            ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            ConcesionFinanciera.Accion.VER_GASTOS,
            ConcesionFinanciera.Accion.VER_COSTOS,
        ):
            ConcesionFinanciera.objects.create(
                membresia=membresia,
                accion=accion,
                todas_las_areas=True,
            )
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="LUZ",
            nombre="Electricidad",
        )
        self.client.force_authenticate(self.admin)

    def configurar(self):
        cobertura = self.client.post(
            "/api/coberturas-actividad/",
            {
                "institucion": self.institucion.id,
                "area": self.area.id,
                "vigente_desde": self.mes.isoformat(),
                "confirmacion_operativa": True,
            },
            format="json",
        )
        regla = self.client.post(
            "/api/reglas-reparto/",
            {
                "concepto": self.concepto.id,
                "institucion": self.institucion.id,
                "area": self.area.id,
                "vigente_desde": self.mes.isoformat(),
            },
            format="json",
        )
        self.assertEqual(cobertura.status_code, 201, cobertura.data)
        self.assertEqual(regla.status_code, 201, regla.data)

    def crear_hechos(self, cantidad=3):
        momento = timezone.make_aware(datetime.combine(self.mes, datetime.min.time()))
        inicio = HechoAtencionCosteable.objects.count()
        return [
            HechoAtencionCosteable.objects.create(
                institucion=self.institucion,
                area=self.area,
                area_origen_id=self.area.id,
                evento_origen_id=5000 + inicio + indice,
                caso_origen_id=4000 + inicio + indice,
                nodo_origen_id=3000 + inicio + indice,
                ocurrida_en=momento,
            )
            for indice in range(cantidad)
        ]

    def test_atribuciones_filtradas_conservan_totales_y_control_de_alcance(self):
        self.configurar()
        hechos = self.crear_hechos(3)
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        url = f"/api/repartos-gasto/{reparto.pk}/atribuciones/"
        respuesta = self.client.get(url, {"ordering": "-importe_centavos", "page_size": 1})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 3)
        self.assertEqual(len(respuesta.data["results"]), 1)
        self.assertEqual(respuesta.data["results"][0]["importe_centavos"], 3334)
        respuesta = self.client.get(url, {"search": str(hechos[0].pk)})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(respuesta.data["importe_atribuido_centavos"], 10001)
        self.assertEqual(respuesta.data["saldo_no_atribuido_centavos"], 0)
        # Buscar una atención visible nunca debe ocultar otra fuera del alcance
        # y convertir un reparto parcialmente autorizado en un detalle completo.
        prestacion = Prestacion.objects.create(institucion=self.institucion, codigo="AT", nombre="Atención")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="HON", nombre="Honorarios", sensible=True)
        ComponenteEsperadoHecho.objects.create(hecho=hechos[1], componente=componente, sensible=True)
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        self.assertEqual(self.client.get(url, {"search": str(hechos[0].pk)}).status_code, 403)

    def test_configurar_despierta_gastos_existentes_y_reporte_no_multiplica_centavos(self):
        from .models import TrabajoReparto
        from .procesamiento import procesar_siguiente
        from .services import registrar_ajuste_gasto
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        self.assertEqual(TrabajoReparto.objects.get(gasto=gasto).revision, 1)
        self.configurar()
        self.assertEqual(TrabajoReparto.objects.get(gasto=gasto).revision, 3)
        self.crear_hechos(3)
        self.assertTrue(procesar_siguiente())
        parametros = {"institucion": self.institucion.pk, "periodo_economico": self.mes.isoformat()}
        reporte = self.client.get("/api/reportes-finanzas/", parametros)
        self.assertEqual(reporte.status_code, 200, reporte.data)
        self.assertEqual((reporte.data["aprobados"], reporte.data["distribuido"], reporte.data["sin_distribuir"]), ("100.01", "100.01", "0.00"))
        ConcesionFinanciera.objects.create(
            membresia=self.admin.membresias.get(institucion=self.institucion),
            accion=ConcesionFinanciera.Accion.CORREGIR_GASTOS, todas_las_areas=True,
        )
        registrar_ajuste_gasto(gasto.pk, Decimal("-200.02"), "Reversión", self.admin)
        self.assertIsNone(self.client.get("/api/reportes-finanzas/", parametros).data["distribuido"])
        self.assertTrue(procesar_siguiente())
        reporte = self.client.get("/api/reportes-finanzas/", parametros)
        self.assertEqual((reporte.data["aprobados"], reporte.data["distribuido"], reporte.data["sin_distribuir"]), ("-100.01", "-100.01", "0.00"))
        self.assertEqual(reporte.data["agrupaciones"][0]["distribuido"], "-100.01")

    def test_enlace_al_caso_exige_capacidad_clinica_en_la_institucion(self):
        self.configurar()
        hecho = self.crear_hechos(1)[0]
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Consulta")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Prueba")
        caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano, area_actual=self.area)
        HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(caso=caso, caso_origen_id=caso.pk)
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        url = f"/api/repartos-gasto/{reparto.pk}/atribuciones/"
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["results"][0]["caso_navegable"], caso.pk)
        self.assertEqual(respuesta.data["results"][0]["caso_descripcion"], "Consulta")
        self.assertNotIn("ciudadano", respuesta.data["results"][0])
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta kinesiológica")
        actual = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Control posterior")
        Caso.objects.filter(pk=caso.pk).update(nodo_actual=actual)
        HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(nodo=nodo)
        self.assertEqual(self.client.get(url).data["results"][0]["caso_descripcion"], "Consulta kinesiológica")

        # Conserva exactamente las concesiones financieras; cambia sólo el rol
        # clínico. Un rol habilitado en otro hospital tampoco alcanza.
        membresia = self.admin.membresias.get(institucion=self.institucion)
        membresia.rol = "reportes"
        membresia.save(update_fields=["rol"])
        otra = Institucion.objects.create(nombre="Otro hospital")
        Membresia.objects.create(usuario=self.admin, institucion=otra, rol=Membresia.Rol.ADMIN_INSTITUCION)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIsNone(respuesta.data["results"][0]["caso_navegable"])
        self.assertIsNone(respuesta.data["results"][0]["caso_descripcion"])
        self.assertEqual(respuesta.data["results"][0]["importe_centavos"], 10001)

        membresia.rol = Membresia.Rol.ADMIN_INSTITUCION
        membresia.save(update_fields=["rol"])
        # Una referencia histórica sin relación viva no se convierte en enlace.
        HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(caso=None)
        self.assertIsNone(self.client.get(url).data["results"][0]["caso_navegable"])
        self.assertIsNone(self.client.get(url).data["results"][0]["caso_descripcion"])
        HechoAtencionCosteable.objects.filter(pk=hecho.pk).update(caso=caso)
        Caso.objects.filter(pk=caso.pk).update(institucion=otra)
        self.assertIsNone(self.client.get(url).data["results"][0]["caso_navegable"])
        self.assertIsNone(self.client.get(url).data["results"][0]["caso_descripcion"])

    def test_configura_explica_y_muestra_la_atribucion_vigente_en_el_hecho(self):
        self.configurar()
        hechos = self.crear_hechos()
        gasto = registrar_gasto(
            self.concepto,
            self.institucion,
            self.area,
            Decimal("100.00"),
            self.mes,
            self.admin,
        )
        reparto = procesar_reparto_gasto(gasto.id)

        listado = self.client.get("/api/repartos-gasto/")
        detalle = self.client.get(f"/api/hechos-costo/{hechos[0].id}/")

        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado.data["count"], 1)
        self.assertEqual(listado.data["results"][0]["id"], reparto.id)
        self.assertEqual(listado.data["results"][0]["concepto_nombre"], "Electricidad")
        self.assertEqual(listado.data["results"][0]["area_nombre"], "Guardia")
        self.assertEqual(listado.data["results"][0]["atribuciones"], 3)
        self.assertTrue(listado.data["results"][0]["vigente"])
        self.assertEqual(detalle.status_code, 200, detalle.data)
        self.assertEqual(detalle.data["total_compartido_conocido"], "33.34")
        self.assertEqual(detalle.data["repartos_compartidos"][0]["concepto"], "Electricidad")

    def test_atribuciones_paginadas_conservan_total_exacto_y_auditan_el_reparto(self):
        self.configurar()
        self.crear_hechos(201)
        gasto = registrar_gasto(
            self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin,
        )
        reparto = procesar_reparto_gasto(gasto.pk)
        url = f"/api/repartos-gasto/{reparto.pk}/atribuciones/"
        primera = self.client.get(url, {"page_size": 1000})
        segunda = self.client.get(url, {"page_size": 1000, "page": 2})
        self.assertEqual(primera.status_code, 200, primera.data)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(primera.data["count"], 201)
        self.assertEqual(len(primera.data["results"]), 200)
        self.assertEqual(len(segunda.data["results"]), 1)
        filas = primera.data["results"] + segunda.data["results"]
        self.assertEqual(len({fila["atencion"] for fila in filas}), 201)
        self.assertEqual(sum(fila["importe_centavos"] for fila in filas), 10001)
        self.assertEqual(primera.data["importe_atribuido_centavos"], 10001)
        self.assertEqual(primera.data["saldo_no_atribuido_centavos"], 0)
        self.assertEqual(set(filas[0]), {
            "id", "atencion", "referencia_atencion", "ocurrida_en", "area", "area_nombre", "importe_centavos", "caso_navegable", "caso_descripcion",
        })
        self.assertIsNone(filas[0]["caso_navegable"])
        acceso = AccesoFinanciero.objects.filter(accion="atribuciones").latest("id")
        self.assertEqual(acceso.recurso, "repartogasto")
        self.assertEqual(acceso.objeto_id, reparto.pk)
        self.assertEqual(acceso.area_id, self.area.pk)
        self.assertEqual(acceso.periodo_economico, self.mes)
        self.assertEqual(acceso.resultados, 1)

    def test_detalle_requiere_costos_del_area_y_no_expone_parcial_con_hechos_sensibles(self):
        self.configurar()
        self.crear_hechos(3)
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        url = f"/api/repartos-gasto/{reparto.pk}/atribuciones/"
        lector = Usuario.objects.create_user("lector-atribuciones@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=lector, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia, accion=ConcesionFinanciera.Accion.VER_GASTOS, todas_las_areas=True,
        )
        self.client.force_authenticate(lector)
        self.assertEqual(self.client.get(url).status_code, 403)
        permiso = ConcesionFinanciera.objects.create(membresia=membresia, accion=ConcesionFinanciera.Accion.VER_COSTOS)
        permiso.areas.add(self.otra_area)
        self.assertEqual(self.client.get(url).status_code, 403)
        permiso.areas.add(self.area)
        self.assertEqual(self.client.get(url).status_code, 200)
        # Otro reparto sensible sobre los mismos hechos vuelve sensible el
        # hecho entero, incluso al consultar este gasto no sensible.
        self.client.force_authenticate(self.admin)
        concepto_sensible = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo="HON", nombre="Honorarios", sensible=True,
        )
        ConcesionFinanciera.objects.filter(membresia__usuario=self.admin).update(permite_sensibles=True)
        regla = self.client.post("/api/reglas-reparto/", {
            "concepto": concepto_sensible.pk, "institucion": self.institucion.pk,
            "area": self.area.pk, "vigente_desde": self.mes.isoformat(),
        }, format="json")
        self.assertEqual(regla.status_code, 201, regla.data)
        sensible = registrar_gasto(concepto_sensible, self.institucion, self.area, Decimal("30"), self.mes, self.admin)
        procesar_reparto_gasto(sensible.pk)
        self.client.force_authenticate(lector)
        bloqueada = self.client.get(url)
        self.assertEqual(bloqueada.status_code, 403)
        self.assertNotIn("results", bloqueada.data)
        permiso.permite_sensibles = True
        permiso.save()
        self.assertEqual(self.client.get(url).status_code, 200)
        ConcesionFinanciera.objects.filter(membresia=membresia, accion=ConcesionFinanciera.Accion.VER_GASTOS).delete()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_repartos_orden_y_rangos_globales_no_multiplican_atribuciones(self):
        self.configurar()
        self.crear_hechos(3)
        repartos = []
        for monto in ("10.02", "10.01", "10.03"):
            gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal(monto), self.mes, self.admin)
            repartos.append(procesar_reparto_gasto(gasto.pk))
        respuesta = self.client.get("/api/repartos-gasto/", {
            "ordering": "saldo_centavos", "page_size": 1, "page": 2,
            "cantidad_atribuciones_min": 3, "cantidad_atribuciones_max": 3,
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 3)
        self.assertEqual(respuesta.data["results"][0]["id"], repartos[0].pk)
        self.assertEqual(respuesta.data["results"][0]["atribuciones"], 3)
        filtrada = self.client.get("/api/repartos-gasto/", {"saldo_centavos_min": 1003})
        self.assertEqual(filtrada.data["count"], 1)
        self.assertEqual(filtrada.data["results"][0]["saldo_centavos"], 1003)

    def test_filtro_institucional_y_orden_con_empates_no_mezclan_areas_ni_paginas(self):
        esperados = []
        for area in (self.area, None, None, None):
            gasto = registrar_gasto(self.concepto, self.institucion, area, Decimal("10.01"), self.mes, self.admin)
            reparto = procesar_reparto_gasto(gasto.pk)
            if area is None:
                esperados.append(reparto.pk)
        recibidos = []
        for pagina in (1, 2, 3):
            respuesta = self.client.get("/api/repartos-gasto/", {
                "gasto__area": "null", "ordering": "saldo_centavos", "page_size": 1, "page": pagina,
            })
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(respuesta.data["count"], 3)
            self.assertIsNone(respuesta.data["results"][0]["area"])
            recibidos.append(respuesta.data["results"][0]["id"])
        self.assertEqual(recibidos, sorted(esperados, reverse=True))

    def test_detalle_pendiente_no_presenta_importes_como_atribuidos(self):
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        self.assertEqual(reparto.estado, "pendiente")
        respuesta = self.client.get(f"/api/repartos-gasto/{reparto.pk}/atribuciones/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 0)
        self.assertEqual(respuesta.data["results"], [])
        self.assertEqual(respuesta.data["saldo_centavos"], 10001)
        self.assertEqual(respuesta.data["importe_atribuido_centavos"], 0)
        self.assertEqual(respuesta.data["saldo_no_atribuido_centavos"], 10001)

    def test_listado_filtra_y_ordena_saldo_sin_distribuir_incluso_versiones_anteriores(self):
        primero = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        segundo = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("200.02"), self.mes, self.admin)
        r1 = procesar_reparto_gasto(primero.pk)
        r2 = procesar_reparto_gasto(segundo.pk)
        # Las versiones guardadas antes de esta corrección usan cero cuando
        # están pendientes: se deben leer correctamente sin reescribirlas.
        from .models import RepartoGasto
        RepartoGasto.objects.filter(pk__in=[r1.pk, r2.pk]).update(saldo_no_atribuido_centavos=0)
        respuesta = self.client.get("/api/repartos-gasto/", {"ordering": "-saldo_no_atribuido_centavos"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([fila["saldo_no_atribuido_centavos"] for fila in respuesta.data["results"]], [20002, 10001])
        filtrada = self.client.get("/api/repartos-gasto/", {"saldo_no_atribuido_centavos_min": 15000})
        self.assertEqual([fila["id"] for fila in filtrada.data["results"]], [r2.pk])

    def test_filtro_sin_distribuir_conserva_negativos_excluye_ceros_y_no_aprobados(self):
        from .models import Gasto
        positivo = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        negativo = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.00"), self.mes, self.admin)
        cero = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.00"), self.mes, self.admin)
        AjusteGasto.objects.create(gasto=negativo, importe=Decimal("-150.00"), motivo="Corrección", registrado_por=self.admin)
        AjusteGasto.objects.create(gasto=cero, importe=Decimal("-100.00"), motivo="Corrección", registrado_por=self.admin)
        pendiente = Gasto.objects.create(concepto=self.concepto, institucion=self.institucion, area=self.area,
            importe=Decimal("75.00"), periodo_economico=self.mes, origen=Gasto.Origen.AREA, registrado_por=self.admin)
        for gasto in (positivo, negativo, cero, pendiente):
            procesar_reparto_gasto(gasto.pk)
        respuesta = self.client.get("/api/repartos-gasto/", {"sin_distribuir": "true", "vigente": "true"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual({fila["gasto"] for fila in respuesta.data["results"]}, {positivo.pk, negativo.pk})
        self.assertEqual(sum(fila["saldo_no_atribuido_centavos"] for fila in respuesta.data["results"]), 5001)
        self.assertEqual(self.client.get("/api/repartos-gasto/", {"sin_distribuir": "invalido"}).status_code, 400)

    def test_totales_del_detalle_sin_actividad_y_negativos_conservan_el_saldo(self):
        self.configurar()
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("10.00"), self.mes, self.admin)
        sin_actividad = procesar_reparto_gasto(gasto.pk)
        AjusteGasto.objects.create(gasto=gasto, importe=Decimal("-20.01"), motivo="Corrección", registrado_por=self.admin)
        sin_actividad_negativo = procesar_reparto_gasto(gasto.pk)
        self.crear_hechos(3)
        distribuido_negativo = procesar_reparto_gasto(gasto.pk)
        for reparto, estado, atribuido, sin_atribuir in (
            (sin_actividad, "sin_actividad", 0, 1000),
            (sin_actividad_negativo, "sin_actividad", 0, -1001),
            (distribuido_negativo, "distribuido", -1001, 0),
        ):
            self.assertEqual(reparto.estado, estado)
            respuesta = self.client.get(f"/api/repartos-gasto/{reparto.pk}/atribuciones/")
            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            self.assertEqual(respuesta.data["importe_atribuido_centavos"], atribuido)
            self.assertEqual(respuesta.data["saldo_no_atribuido_centavos"], sin_atribuir)
            self.assertEqual(respuesta.data["saldo_centavos"], atribuido + sin_atribuir)
            self.assertEqual(sum(fila["importe_centavos"] for fila in respuesta.data["results"]), atribuido)

    def test_detalle_no_elude_sensibilidad_de_componentes_directos(self):
        self.configurar()
        hechos = self.crear_hechos(2)
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("10"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        prestacion = Prestacion.objects.create(institucion=self.institucion, codigo="AT", nombre="Atención")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="HON", nombre="Honorarios", sensible=True)
        ComponenteEsperadoHecho.objects.create(hecho=hechos[1], componente=componente, sensible=True)
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        respuesta = self.client.get(f"/api/repartos-gasto/{reparto.pk}/atribuciones/", {"page_size": 1})
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn("results", respuesta.data)
        self.assertEqual(self.client.get(f"/api/hechos-costo/{hechos[1].pk}/").status_code, 404)

    def test_detalle_conserva_sensibles_explicitos_al_cambiar_rol_y_revoca_al_quitar_permiso(self):
        self.configurar()
        hecho = self.crear_hechos(1)[0]
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("10"), self.mes, self.admin)
        reparto = procesar_reparto_gasto(gasto.pk)
        prestacion = Prestacion.objects.create(institucion=self.institucion, codigo="AT", nombre="Atención")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="HON", nombre="Honorarios", sensible=True)
        ComponenteEsperadoHecho.objects.create(hecho=hecho, componente=componente, sensible=True)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.VER_COSTOS,
        ).update(permite_sensibles=True)
        url = f"/api/repartos-gasto/{reparto.pk}/atribuciones/"
        self.assertEqual(self.client.get(url).status_code, 200)
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.MEDICO)
        self.assertEqual(self.client.get(url).status_code, 200)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.VER_COSTOS,
        ).update(permite_sensibles=False)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(f"/api/hechos-costo/{hecho.pk}/").status_code, 404)

    def test_configuracion_respeta_el_area_de_la_misma_concesion(self):
        restringido = Usuario.objects.create_user("repartos-restringido@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        )
        concesion.areas.add(self.area)
        self.client.force_authenticate(restringido)

        respuesta = self.client.post(
            "/api/coberturas-actividad/",
            {
                "institucion": self.institucion.id,
                "area": self.otra_area.id,
                "vigente_desde": self.mes.isoformat(),
                "confirmacion_operativa": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_permiso_exclusivo_de_repartos_puede_consultar_el_catalogo(self):
        restringido = Usuario.objects.create_user("solo-repartos@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
            todas_las_areas=True,
        )
        self.client.force_authenticate(restringido)

        respuesta = self.client.get(
            f"/api/conceptos-gasto/?institucion={self.institucion.id}"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([item["id"] for item in respuesta.data["results"]], [self.concepto.id])

    def test_verificacion_explica_diferencia_y_ambos_totales(self):
        hechos = self.crear_hechos(2)
        registrar_gasto(
            self.concepto, self.institucion, self.area,
            Decimal("100.01"), self.mes, self.admin,
        )

        respuesta = self.client.get(
            "/api/coberturas-actividad/verificacion/",
            {
                "institucion": self.institucion.id,
                "area": self.area.id,
                "periodo_economico": self.mes.isoformat(),
                "concepto": self.concepto.id,
            },
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(respuesta.data["integridad_tecnica"])
        self.assertEqual(respuesta.data["diferencias"], 0)
        self.assertEqual(respuesta.data["atenciones_registradas"], len(hechos))
        self.assertEqual(respuesta.data["importe_total_centavos"], 10001)
        self.assertEqual(respuesta.data["importe_estimado_por_atencion_centavos"], 5000)

    def test_verificacion_no_revela_resumen_con_solo_configuracion(self):
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.VER_GASTOS,
        ).delete()
        respuesta = self.client.get("/api/coberturas-actividad/verificacion/", {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": self.mes.isoformat(),
        })
        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn("importe_total_centavos", respuesta.data)
        self.assertNotIn("atenciones_registradas", respuesta.data)

    def test_verificacion_audita_incluso_un_resumen_sin_gastos(self):
        respuesta = self.client.get("/api/coberturas-actividad/verificacion/", {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": self.mes.isoformat(),
        })
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["importe_total_centavos"], 0)
        accesos = AccesoFinanciero.objects.filter(accion="verificacion")
        self.assertEqual(accesos.count(), 1)
        acceso = accesos.get()
        self.assertEqual(acceso.usuario_id, self.admin.pk)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
        self.assertEqual(acceso.area_id, self.area.pk)
        self.assertEqual(acceso.periodo_economico, self.mes)
        self.assertEqual(acceso.recurso, "coberturaactividadcosteable")
        self.assertIsNone(acceso.objeto_id)
        self.assertFalse(acceso.sensible)
        self.assertEqual(acceso.resultados, 1)

    def test_verificacion_no_entrega_datos_si_falla_la_auditoria(self):
        with patch("apps.finanzas.auditoria.AccesoFinanciero.objects.create", side_effect=RuntimeError):
            respuesta = self.client.get("/api/coberturas-actividad/verificacion/", {
                "institucion": self.institucion.pk, "area": self.area.pk,
                "periodo_economico": self.mes.isoformat(),
            })
        self.assertEqual(respuesta.status_code, 503)
        self.assertNotIn("importe_total_centavos", respuesta.data)
        self.assertNotIn("atenciones_registradas", respuesta.data)
        self.assertFalse(AccesoFinanciero.objects.filter(accion="verificacion").exists())

    def test_verificacion_exige_ambos_permisos_en_la_misma_area(self):
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        parametros = {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": self.mes.isoformat(),
        }
        for accion in (ConcesionFinanciera.Accion.VER_GASTOS, ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS):
            with self.subTest(accion=accion):
                permiso = ConcesionFinanciera.objects.get(membresia__usuario=self.admin, accion=accion)
                permiso.todas_las_areas = False
                permiso.save()
                permiso.areas.set([self.otra_area])
                respuesta = self.client.get("/api/coberturas-actividad/verificacion/", parametros)
                self.assertEqual(respuesta.status_code, 403)
                permiso.areas.set([self.area])
                respuesta = self.client.get("/api/coberturas-actividad/verificacion/", parametros)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        ).delete()
        self.assertEqual(self.client.get("/api/coberturas-actividad/verificacion/", parametros).status_code, 403)

    def test_configurador_sin_lectura_verifica_actividad_sin_importes(self):
        self.configurar()
        registrar_gasto(self.concepto, self.institucion, self.area, Decimal("123.45"), self.mes, self.admin)
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.VER_GASTOS,
        ).delete()
        configurador = ConcesionFinanciera.objects.get(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
        )
        configurador.todas_las_areas = False
        configurador.save()
        configurador.areas.set([self.area])
        parametros = {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": str(self.mes), "incluir_importes": "false",
        }
        respuesta = self.client.get("/api/coberturas-actividad/verificacion/", parametros)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(respuesta.data["integridad_tecnica"])
        self.assertFalse(respuesta.data["incluye_importes"])
        for campo in ("importe_total_centavos", "importe_pendiente_centavos", "importe_estimado_por_atencion_centavos"):
            self.assertIsNone(respuesta.data[campo])
        self.assertEqual(self.client.get("/api/coberturas-actividad/verificacion/", {
            **parametros, "incluir_importes": "true",
        }).status_code, 403)
        self.assertEqual(self.client.get("/api/coberturas-actividad/verificacion/", {
            **parametros, "area": self.otra_area.pk,
        }).status_code, 403)

    def test_verificacion_no_combina_lectura_de_otra_institucion(self):
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin, accion=ConcesionFinanciera.Accion.VER_GASTOS,
        ).delete()
        otra = Institucion.objects.create(nombre="Otro hospital")
        membresia = Membresia.objects.create(
            usuario=self.admin, institucion=otra, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia, accion=ConcesionFinanciera.Accion.VER_GASTOS, todas_las_areas=True,
        )
        respuesta = self.client.get("/api/coberturas-actividad/verificacion/", {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": self.mes.isoformat(),
        })
        self.assertEqual(respuesta.status_code, 403)

    def test_verificacion_sensible_requiere_ambos_permisos_y_audita_el_alcance(self):
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin,
            accion__in=[ConcesionFinanciera.Accion.REGISTRAR_GASTOS, ConcesionFinanciera.Accion.APROBAR_GASTOS],
        ).update(permite_sensibles=True)
        sensible = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo="SUELDOS", nombre="Sueldos", sensible=True,
        )
        for concepto, importe in ((self.concepto, "100.01"), (sensible, "200.02")):
            gasto = registrar_gasto(concepto, self.institucion, self.area, Decimal(importe), self.mes, self.admin)
            self.assertTrue(gasto.aprobado, "La verificación de lectura requiere una fuente ya aprobada.")
        Membresia.objects.filter(usuario=self.admin).update(rol=Membresia.Rol.ADMINISTRATIVO)
        parametros = {
            "institucion": self.institucion.pk, "area": self.area.pk,
            "periodo_economico": self.mes.isoformat(),
        }
        for configura, lee in ((True, False), (False, True), (False, False), (True, True)):
            with self.subTest(configura=configura, lee=lee):
                for accion, permitido in (
                    (ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS, configura),
                    (ConcesionFinanciera.Accion.VER_GASTOS, lee),
                ):
                    ConcesionFinanciera.objects.filter(membresia__usuario=self.admin, accion=accion).update(
                        permite_sensibles=permitido,
                    )
                respuesta = self.client.get("/api/coberturas-actividad/verificacion/", parametros)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data["importe_total_centavos"], 30003 if configura and lee else 10001)
                acceso = AccesoFinanciero.objects.filter(accion="verificacion").latest("id")
                self.assertEqual(acceso.sensible, configura and lee)
                explicito = self.client.get("/api/coberturas-actividad/verificacion/", {
                    **parametros, "concepto": sensible.pk,
                })
                self.assertEqual(explicito.status_code, 200 if configura and lee else 403)
                if configura and lee:
                    self.assertEqual(explicito.data["importe_total_centavos"], 20002)

    def test_no_habilita_una_cobertura_si_el_control_tecnico_encuentra_diferencias(self):
        flujo = Flujo.objects.create(
            institucion=self.institucion, area=self.otra_area, titulo="Clínica",
        )
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(
            institucion=self.institucion, nombre="Ana", apellido="Prueba",
        )
        caso = Caso.objects.create(
            institucion=self.institucion, version=version, ciudadano=ciudadano,
            area_actual=self.otra_area,
        )
        EventoCaso.objects.create(
            caso=caso, nodo=nodo, autor=self.admin,
            titulo="Atención «Consulta» registrada",
        )

        respuesta = self.client.post(
            "/api/coberturas-actividad/",
            {
                "institucion": self.institucion.id,
                "area": self.otra_area.id,
                "vigente_desde": self.mes.isoformat(),
                "confirmacion_operativa": True,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("actividad está incompleta", str(respuesta.data).lower())

    def test_actividad_completa_que_vuelve_a_incompleta_no_reutiliza_historial(self):
        from .procesamiento import solicitar_reparto, procesar_siguiente
        from .services import registrar_atencion_completada

        self.configurar()
        gasto = registrar_gasto(self.concepto, self.institucion, self.area, Decimal("100.01"), self.mes, self.admin)
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Consulta")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Prueba", apellido="Reparto")
        caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano, area_actual=self.area)
        evento = EventoCaso.objects.create(caso=caso, nodo=nodo, autor=self.admin, titulo="Atención «Consulta» registrada")
        self.assertTrue(procesar_siguiente())
        url = "/api/repartos-gasto/"
        filtros = {"gasto": gasto.pk, "vigente": "true"}
        primero = self.client.get(url, filtros).data["results"][0]
        self.assertEqual((primero["estado"], primero["version"]), ("pendiente", 1))
        registrar_atencion_completada(caso, nodo, evento, self.admin)
        solicitar_reparto(gasto.pk)
        self.assertTrue(procesar_siguiente())
        segundo = self.client.get(url, filtros).data["results"][0]
        self.assertEqual((segundo["estado"], segundo["version"]), ("distribuido", 2))
        EventoCaso.objects.create(caso=caso, nodo=nodo, autor=self.admin, titulo="Atención «Consulta» registrada")
        solicitar_reparto(gasto.pk)
        self.assertTrue(procesar_siguiente())
        tercero = self.client.get(url, filtros).data["results"][0]
        self.assertEqual((tercero["estado"], tercero["version"]), ("pendiente", 3))
        self.assertFalse(tercero["actualizando"])
        reporte = self.client.get("/api/reportes-finanzas/", {
            "institucion": self.institucion.pk, "periodo_economico": str(self.mes),
        }).data
        self.assertEqual((reporte["aprobados"], reporte["distribuido"], reporte["sin_distribuir"]), ("100.01", "0.00", "100.01"))
        solicitar_reparto(gasto.pk)
        self.assertTrue(procesar_siguiente())
        self.assertEqual(self.client.get(url, filtros).data["results"][0]["id"], tercero["id"])
        self.assertEqual(self.client.get(url, {"gasto": gasto.pk}).data["count"], 3)

    def test_listado_separa_vigente_de_historial(self):
        self.configurar()
        self.crear_hechos(1)
        gasto = registrar_gasto(
            self.concepto, self.institucion, self.area,
            Decimal("20.00"), self.mes, self.admin,
        )
        primera = procesar_reparto_gasto(gasto.id)
        self.crear_hechos(2)
        vigente = procesar_reparto_gasto(gasto.id)

        actuales = self.client.get("/api/repartos-gasto/?vigente=true")
        historicos = self.client.get("/api/repartos-gasto/?vigente=false")
        coberturas = self.client.get("/api/coberturas-actividad/?vigente=true")
        reglas = self.client.get("/api/reglas-reparto/?vigente=true")

        self.assertEqual([item["id"] for item in actuales.data["results"]], [vigente.id])
        self.assertEqual([item["id"] for item in historicos.data["results"]], [primera.id])
        self.assertEqual(coberturas.status_code, 200, coberturas.data)
        self.assertEqual(coberturas.data["count"], 1)
        self.assertEqual(reglas.status_code, 200, reglas.data)
        self.assertEqual(reglas.data["count"], 1)

    def test_no_permite_editar_ni_borrar_configuracion_o_resultados(self):
        self.configurar()
        gasto = registrar_gasto(
            self.concepto, self.institucion, self.area,
            Decimal("10.00"), self.mes, self.admin,
        )
        reparto = procesar_reparto_gasto(gasto.id)

        self.assertEqual(self.client.patch("/api/coberturas-actividad/1/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete("/api/reglas-reparto/1/").status_code, 405)
        self.assertEqual(self.client.post("/api/repartos-gasto/", {}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(f"/api/repartos-gasto/{reparto.id}/").status_code, 405)

    def test_reparto_sensible_exige_lectura_sensible_del_hecho(self):
        self.concepto.sensible = True
        self.concepto.save()
        ConcesionFinanciera.objects.filter(
            membresia__usuario=self.admin,
            accion__in=[
                ConcesionFinanciera.Accion.CONFIGURAR_REPARTOS,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
                ConcesionFinanciera.Accion.APROBAR_GASTOS,
            ],
        ).update(permite_sensibles=True)
        self.configurar()
        hecho = self.crear_hechos(1)[0]
        gasto = registrar_gasto(
            self.concepto, self.institucion, self.area,
            Decimal("25.00"), self.mes, self.admin,
        )
        self.assertTrue(gasto.aprobado, "La lectura sensible se prueba sobre un gasto apto para repartir.")
        procesar_reparto_gasto(gasto.id)
        restringido = Usuario.objects.create_user("lector-costos-reparto@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=restringido, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=False,
        )
        self.client.force_authenticate(restringido)

        self.assertEqual(self.client.get(f"/api/hechos-costo/{hecho.id}/").status_code, 404)
