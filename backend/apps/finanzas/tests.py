from decimal import Decimal
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import ComponenteEsperadoHecho, DefinicionComponente, HechoAtencionCosteable, ImputacionCosto, PendienteCosteo, Prestacion, ValorComponente
from .services import procesar_hecho_atencion, registrar_atencion_completada


class CosteoAtencionTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("finanzas@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Paz")
        self.caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano, area_actual=self.area)

    def test_sin_prestacion_deja_faltante_y_no_inventa_cero(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        self.assertEqual(ImputacionCosto.objects.filter(hecho=hecho).count(), 0)
        self.assertTrue(PendienteCosteo.objects.filter(hecho=hecho, motivo=PendienteCosteo.Motivo.SIN_PRESTACION, resuelto=False).exists())

    def test_valor_vigente_genera_una_sola_imputacion_al_reintentar(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(componente=componente, importe=Decimal("1250.50"), vigente_desde=timezone.now() - timedelta(days=1), fuente="Resolución interna")
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        procesar_hecho_atencion(hecho.id)
        imputacion = ImputacionCosto.objects.get(hecho=hecho, componente=componente)
        self.assertEqual(imputacion.importe, Decimal("1250.50"))
        self.assertEqual(ImputacionCosto.objects.filter(hecho=hecho).count(), 1)

    def test_el_hecho_sobrevive_al_borrado_del_caso_y_no_se_edita(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        self.assertEqual(registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario).id, hecho.id)
        caso_origen_id = self.caso.id
        self.caso.delete()
        hecho.refresh_from_db()
        self.assertIsNone(hecho.caso)
        self.assertEqual(hecho.caso_origen_id, caso_origen_id)
        hecho.nodo_origen_id = 999
        with self.assertRaises(ValidationError):
            hecho.save()

    def test_un_componente_agregado_despues_no_recostea_un_hecho_completo(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        base = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(componente=base, importe=Decimal("100.00"), vigente_desde=timezone.now() - timedelta(days=1))
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        adicional = DefinicionComponente.objects.create(prestacion=prestacion, codigo="ADIC", nombre="Componente agregado")
        ValorComponente.objects.create(componente=adicional, importe=Decimal("50.00"), vigente_desde=timezone.now() - timedelta(days=1))
        procesar_hecho_atencion(hecho.id)
        self.assertEqual(ImputacionCosto.objects.filter(hecho=hecho).count(), 1)
        self.assertEqual(ComponenteEsperadoHecho.objects.filter(hecho=hecho).count(), 1)

    def test_un_valor_solapado_exige_correccion_explicita(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        desde = timezone.now() - timedelta(days=1)
        valor = ValorComponente.objects.create(componente=componente, importe=Decimal("100.00"), vigente_desde=desde)
        with self.assertRaises(ValidationError):
            ValorComponente.objects.create(componente=componente, importe=Decimal("120.00"), vigente_desde=desde)
        correccion = ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("120.00"),
            vigente_desde=desde,
            reemplaza=valor,
            motivo_correccion="Valor cargado por error",
        )
        self.assertEqual(correccion.reemplaza, valor)

    def test_el_comando_recupera_un_hecho_pendiente_sin_tocar_la_atencion(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(componente=componente, importe=Decimal("100.00"), vigente_desde=timezone.now() - timedelta(days=1))
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        salida = StringIO()
        call_command("procesar_costos", "--limite", "1", stdout=salida)
        self.assertTrue(ImputacionCosto.objects.filter(hecho=hecho, componente=componente).exists())
        self.assertIn("1 hecho(s) procesado(s)", salida.getvalue())
