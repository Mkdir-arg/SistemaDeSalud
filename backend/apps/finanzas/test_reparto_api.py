from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import ConceptoGasto, ConcesionFinanciera, HechoAtencionCosteable
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
            ],
        ).update(permite_sensibles=True)
        self.configurar()
        hecho = self.crear_hechos(1)[0]
        gasto = registrar_gasto(
            self.concepto, self.institucion, self.area,
            Decimal("25.00"), self.mes, self.admin,
        )
        procesar_reparto_gasto(gasto.id)
        restringido = Usuario.objects.create_user("lector-costos-reparto@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=restringido, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=False,
        )
        self.client.force_authenticate(restringido)

        self.assertEqual(self.client.get(f"/api/hechos-costo/{hecho.id}/").status_code, 404)
