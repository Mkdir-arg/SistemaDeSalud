from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion

from .models import (
    AccesoFinanciero,
    AjusteCosto,
    AtribucionReparto,
    ComponenteEsperadoHecho,
    ConceptoGasto,
    ConcesionFinanciera,
    DefinicionComponente,
    Gasto,
    HechoAtencionCosteable,
    ImputacionCosto,
    PendienteCosteo,
    Prestacion,
    RepartoGasto,
    TrabajoReparto,
    ValorComponente,
)


class ReporteCostosTests(APITestCase):
    """El resumen agrega las mismas fuentes del listado, sin sumar el gasto dos veces."""

    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital costos")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.otra = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.usuario = Usuario.objects.create_user("costos@demo.local", "x")
        self.membresia = Membresia.objects.create(
            usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        self.mes = timezone.localdate().replace(day=1)
        self.momento = timezone.make_aware(datetime.combine(self.mes, datetime.min.time())) + timezone.timedelta(hours=10)
        self.parametros = {"institucion": self.institucion.pk, "periodo_economico": str(self.mes)}
        self.secuencia = 0
        self.client.force_authenticate(self.usuario)

    def prestacion(self, codigo="CONS", nombre="Consulta", sensible=False):
        prestacion = Prestacion.objects.create(institucion=self.institucion, codigo=codigo, nombre=nombre)
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion, codigo=f"{codigo}-MAT", nombre="Materiales", sensible=sensible,
        )
        valor = ValorComponente.objects.create(
            componente=componente, importe=Decimal("100.00"), vigente_desde=self.momento - timezone.timedelta(days=30),
        )
        return prestacion, componente, valor

    def hecho(self, area=None, momento=None):
        self.secuencia += 1
        return HechoAtencionCosteable.objects.create(
            institucion=self.institucion, area=area, area_origen_id=area.pk if area else None,
            evento_origen_id=self.secuencia, caso_origen_id=self.secuencia, nodo_origen_id=self.secuencia,
            ocurrida_en=momento or self.momento,
        )

    def costear(self, hecho, componente, valor, importe="100.00"):
        ComponenteEsperadoHecho.objects.create(hecho=hecho, componente=componente, sensible=componente.sensible)
        return ImputacionCosto.objects.create(hecho=hecho, componente=componente, valor=valor, importe=Decimal(importe))

    def gasto(self, area=None, importe="300.00"):
        self.secuencia += 1
        concepto = ConceptoGasto.objects.create(
            institucion=self.institucion, codigo=f"C{self.secuencia}", nombre=f"Concepto {self.secuencia}",
        )
        return Gasto.objects.create(
            institucion=self.institucion, area=area or self.area, concepto=concepto, importe=Decimal(importe),
            periodo_economico=self.mes, origen=Gasto.Origen.CENTRAL, registrado_por=self.usuario,
            estado=Gasto.Estado.APROBADO, aprobado_por=self.usuario, aprobado_en=timezone.now(),
        )

    def atribuir(self, hecho, centavos, gasto=None, reemplazado=False):
        gasto = gasto or self.gasto(area=hecho.area)
        reparto = RepartoGasto.objects.create(
            gasto=gasto, version=1, huella_insumos=f"h{gasto.pk}", importe_fuente_centavos=centavos,
            importe_ajustes_centavos=0, saldo_centavos=centavos, estado=RepartoGasto.Estado.DISTRIBUIDO,
        )
        if reemplazado:
            RepartoGasto.objects.create(
                gasto=gasto, version=2, huella_insumos=f"h{gasto.pk}b", importe_fuente_centavos=centavos,
                importe_ajustes_centavos=0, saldo_centavos=centavos, estado=RepartoGasto.Estado.DISTRIBUIDO,
                reemplaza=reparto,
            )
        return AtribucionReparto.objects.create(reparto=reparto, hecho=hecho, importe_centavos=centavos)

    def consultar(self, **filtros):
        return self.client.get("/api/reportes-costos/", {**self.parametros, **filtros})

    def test_totales_separan_directo_de_compartido_y_agrupan_por_area_y_prestacion(self):
        prestacion, componente, valor = self.prestacion()
        uno, dos = self.hecho(self.area), self.hecho(self.otra)
        self.costear(uno, componente, valor)
        self.costear(dos, componente, valor, "50.00")
        AjusteCosto.objects.create(
            imputacion=uno.imputaciones.get(), importe=Decimal("10.00"), motivo="Corrección",
            registrado_por=self.usuario, estado="aprobado",
            aprobado_por=self.usuario, aprobado_en=timezone.now(),
        )
        AjusteCosto.objects.create(
            imputacion=dos.imputaciones.get(), importe=Decimal("-5.00"), motivo="En revisión",
            registrado_por=self.usuario, estado="pendiente_aprobacion",
        )
        self.atribuir(uno, 3334)
        respuesta = self.consultar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        datos = respuesta.data
        # 110 + 50: el ajuste pendiente no modifica el directo conocido.
        self.assertEqual((datos["directo_conocido"], datos["compartido_conocido"]), ("160.00", "33.34"))
        self.assertEqual((datos["atenciones"], datos["ajustes_pendientes"]), (2, 1))
        por_area = {fila["nombre"]: fila for fila in datos["agrupaciones"]["area"]}
        self.assertEqual(por_area["Consultorios"]["directo_conocido"], "110.00")
        self.assertEqual(por_area["Consultorios"]["compartido_conocido"], "33.34")
        self.assertEqual(por_area["Guardia"]["compartido_conocido"], "0.00")
        prestaciones = datos["agrupaciones"]["prestacion"]
        self.assertEqual([(f["prestacion"], f["directo_conocido"], f["atenciones"]) for f in prestaciones],
                         [(prestacion.pk, "160.00", 2)])
        self.assertTrue(AccesoFinanciero.objects.filter(usuario=self.usuario, recurso="hechoatencioncosteable").exists())

    def test_reparto_reemplazado_y_mes_ajeno_no_entran_en_el_compartido(self):
        _, componente, valor = self.prestacion()
        dentro = self.hecho(self.area)
        fuera = self.hecho(self.area, self.momento - timezone.timedelta(days=40))
        self.costear(dentro, componente, valor)
        self.costear(fuera, componente, valor)
        self.atribuir(dentro, 1000, reemplazado=True)
        self.atribuir(dentro, 2500)
        datos = self.consultar().data
        self.assertEqual(datos["atenciones"], 1)
        self.assertEqual(datos["directo_conocido"], "100.00")
        self.assertEqual(datos["compartido_conocido"], "25.00")

    def test_incompletas_cuentan_pendientes_y_atenciones_sin_configuracion(self):
        _, componente, valor = self.prestacion()
        completa = self.hecho(self.area)
        self.costear(completa, componente, valor)
        con_pendiente = self.hecho(self.area)
        self.costear(con_pendiente, componente, valor)
        PendienteCosteo.objects.create(hecho=con_pendiente, motivo=PendienteCosteo.Motivo.SIN_VALOR)
        sin_configurar = self.hecho(self.otra)
        datos = self.consultar().data
        self.assertEqual((datos["atenciones"], datos["atenciones_incompletas"]), (3, 2))
        por_area = {fila["nombre"]: fila for fila in datos["agrupaciones"]["area"]}
        self.assertEqual(por_area["Consultorios"]["incompletas"], 1)
        self.assertEqual(por_area["Guardia"]["incompletas"], 1)
        sin_prestacion = [f for f in datos["agrupaciones"]["prestacion"] if f["prestacion"] is None]
        self.assertEqual(sin_prestacion[0]["nombre"], "Sin prestación configurada")
        self.assertEqual(sin_prestacion[0]["atenciones"], 1)
        self.assertEqual(sin_configurar.area, self.otra)

    def test_reparto_en_actualizacion_se_informa_sin_ocultar_lo_conocido(self):
        _, componente, valor = self.prestacion()
        hecho = self.hecho(self.area)
        self.costear(hecho, componente, valor)
        gasto = self.gasto()
        TrabajoReparto.objects.create(gasto=gasto, reintentar_en=timezone.now())
        self.assertTrue(self.consultar().data["reparto_actualizando"])
        self.assertFalse(self.consultar(area=self.otra.pk).data["reparto_actualizando"])
        TrabajoReparto.objects.filter(gasto=gasto).update(revision_procesada=1)
        self.assertFalse(self.consultar().data["reparto_actualizando"])

    def test_sin_alcance_de_costos_no_se_devuelven_importes(self):
        _, componente, valor = self.prestacion(sensible=True)
        hecho = self.hecho(self.area)
        self.costear(hecho, componente, valor)
        limitado = Usuario.objects.create_user("limitado@demo.local", "x")
        membresia = Membresia.objects.create(
            usuario=limitado, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO,
        )
        self.client.force_authenticate(limitado)
        self.assertEqual(self.consultar().status_code, 403)
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia, accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True, permite_sensibles=False,
        )
        # Autorizado en la institución, pero el componente sensible queda fuera.
        datos = self.consultar().data
        self.assertEqual((datos["atenciones"], datos["directo_conocido"]), (0, "0.00"))
        self.assertEqual(datos["agrupaciones"]["area"], [])
        concesion.permite_sensibles = True
        concesion.save(update_fields=["permite_sensibles"])
        self.assertEqual(self.consultar().data["directo_conocido"], "100.00")
        self.assertEqual(self.consultar(area=self.otra.pk).status_code, 200)

    def test_area_sin_asignar_y_periodo_invalido_se_validan(self):
        _, componente, valor = self.prestacion()
        self.costear(self.hecho(None), componente, valor)
        self.costear(self.hecho(self.area), componente, valor, "70.00")
        datos = self.consultar(area_sin_asignar="true").data
        self.assertEqual(datos["directo_conocido"], "100.00")
        self.assertEqual(datos["agrupaciones"]["area"][0]["nombre"], "Institucional — sin área asignada")
        self.assertEqual(self.consultar(area_sin_asignar="true", area=self.area.pk).status_code, 400)
        self.assertEqual(self.client.get("/api/reportes-costos/", {
            "institucion": self.institucion.pk, "periodo_economico": str(self.mes.replace(day=2)),
        }).status_code, 400)
