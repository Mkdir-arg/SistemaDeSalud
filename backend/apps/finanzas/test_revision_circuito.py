"""Regresiones de navegación económica y avance del recuperador."""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion
from .models import (
    ComponenteEsperadoHecho, ConcesionFinanciera, DefinicionComponente,
    HechoAtencionCosteable, ImputacionCosto, Prestacion, ValorComponente,
)
from .test_dinero import DatosDinero
from .services import procesar_hecho_atencion


class NavegacionCuentaGastoTests(DatosDinero, APITestCase):
    def setUp(self):
        self.preparar()
        self.client.force_authenticate(self.usuario)

    def test_gasto_permite_abrir_su_cuenta_existente_sin_crear_otra(self):
        detalle = self.client.get(f"/api/gastos/{self.gasto.pk}/")
        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(detalle.data.get("cuenta_por_pagar"), self.obligacion.pk)
        listado = self.client.get("/api/gastos/", {"institucion": self.institucion.pk})
        self.assertEqual(listado.data["results"][0]["cuenta_por_pagar"], self.obligacion.pk)

    def test_lectura_de_gastos_no_revela_cuenta_sin_permiso_de_dinero(self):
        lector = Usuario.objects.create_user("lector-gastos-revision@test.local", "x")
        membresia = Membresia.objects.create(
            usuario=lector, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        self.client.force_authenticate(lector)
        respuesta = self.client.get(f"/api/gastos/{self.gasto.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("cuenta_por_pagar", respuesta.data)
        self.assertIsNone(respuesta.data["cuenta_por_pagar"])
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia, accion="ver_dinero", todas_las_areas=False,
        )
        self.assertIsNone(self.client.get(f"/api/gastos/{self.gasto.pk}/").data["cuenta_por_pagar"])
        concesion.areas.add(self.area)
        self.assertEqual(
            self.client.get(f"/api/gastos/{self.gasto.pk}/").data["cuenta_por_pagar"], self.obligacion.pk,
        )

    def test_cuenta_sensible_requiere_permiso_sensible_aunque_el_gasto_no_lo_sea(self):
        lector = Usuario.objects.create_user("lector-cuenta-sensible@test.local", "x")
        membresia = Membresia.objects.create(
            usuario=lector, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia, accion="ver_dinero", todas_las_areas=True,
        )
        type(self.obligacion).objects.filter(pk=self.obligacion.pk).update(sensible=True)
        self.client.force_authenticate(lector)
        self.assertIsNone(self.client.get(f"/api/gastos/{self.gasto.pk}/").data["cuenta_por_pagar"])
        concesion.permite_sensibles = True
        concesion.save(update_fields=["permite_sensibles"])
        self.assertEqual(
            self.client.get(f"/api/gastos/{self.gasto.pk}/").data["cuenta_por_pagar"], self.obligacion.pk,
        )

    def test_permiso_de_dinero_en_otra_institucion_no_revela_la_cuenta(self):
        lector = Usuario.objects.create_user("lector-cuenta-otra-institucion@test.local", "x")
        Membresia.objects.create(
            usuario=lector, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        otra = Institucion.objects.create(nombre="Otro hospital")
        membresia = Membresia.objects.create(
            usuario=lector, institucion=otra, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia, accion="ver_dinero", todas_las_areas=True, permite_sensibles=True,
        )
        self.client.force_authenticate(lector)
        respuesta = self.client.get(f"/api/gastos/{self.gasto.pk}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["cuenta_por_pagar"])


class AvanceRecuperadorCostosTests(TestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital revisión")
        prestacion = Prestacion.objects.create(
            institucion=self.institucion, codigo="CONS", nombre="Consulta",
        )
        self.sin_valor = DefinicionComponente.objects.create(
            prestacion=prestacion, codigo="SIN-VALOR", nombre="Falta configurar valor",
        )
        self.con_valor = DefinicionComponente.objects.create(
            prestacion=prestacion, codigo="CON-VALOR", nombre="Valor disponible",
        )
        self.inicio = timezone.now() - timedelta(hours=1)
        ValorComponente.objects.create(
            componente=self.con_valor, importe=Decimal("100.00"),
            vigente_desde=self.inicio - timedelta(days=1),
        )

    def hecho(self, numero, componente):
        hecho = HechoAtencionCosteable.objects.create(
            institucion=self.institucion, evento_origen_id=numero,
            caso_origen_id=numero, nodo_origen_id=1,
            ocurrida_en=self.inicio + timedelta(seconds=numero), componentes_congelados=True,
        )
        ComponenteEsperadoHecho.objects.create(hecho=hecho, componente=componente)
        return hecho

    def test_cien_hechos_sin_valor_no_bloquean_el_siguiente_recuperable(self):
        for numero in range(1, 101):
            self.hecho(numero, self.sin_valor)
        recuperable = self.hecho(101, self.con_valor)
        call_command("procesar_costos", limite=100, stdout=StringIO())
        self.assertFalse(ImputacionCosto.objects.filter(hecho=recuperable).exists())
        call_command("procesar_costos", limite=100, stdout=StringIO())
        self.assertEqual(
            ImputacionCosto.objects.get(hecho=recuperable).importe, Decimal("100.00"),
        )

    def test_error_persistente_no_monopoliza_el_lote_siguiente(self):
        fallido = self.hecho(1, self.sin_valor)
        recuperable = self.hecho(2, self.con_valor)

        def fuente_temporalmente_no_disponible(hecho_id):
            if hecho_id == fallido.pk:
                raise RuntimeError("Fuente no disponible")
            return procesar_hecho_atencion(hecho_id)

        with patch(
            "apps.finanzas.management.commands.procesar_costos.procesar_hecho_atencion",
            side_effect=fuente_temporalmente_no_disponible,
        ):
            for _ in range(2):
                call_command("procesar_costos", limite=1, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(
            ImputacionCosto.objects.get(hecho=recuperable).importe, Decimal("100.00"),
        )
        self.assertTrue(fallido.pendientes.filter(motivo="error_recuperable", resuelto=False).exists())

    def test_modo_seco_no_modifica_la_prioridad_de_revision(self):
        hecho = self.hecho(1, self.con_valor)
        call_command("procesar_costos", seco=True, limite=1, stdout=StringIO())
        hecho.refresh_from_db()
        self.assertIsNone(hecho.ultimo_costeo_en)
        self.assertFalse(hecho.imputaciones.exists())
        self.assertFalse(hecho.pendientes.exists())
