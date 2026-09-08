from decimal import Decimal
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, TransactionTestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, connections, close_old_connections, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import AjusteCosto, AjusteGasto, ComponenteEsperadoHecho, ConceptoGasto, ConcesionFinanciera, CorreccionSnapshotCosteo, DefinicionComponente, ExpectativaGasto, Gasto, HechoAtencionCosteable, ImputacionCosto, PendienteCosteo, Prestacion, ValorComponente
from .permisos import tiene_concesion_financiera
from .services import aprobar_gasto, corregir_snapshot_componentes, intentar_costeo_directo, procesar_hecho_atencion, rechazar_gasto, registrar_ajuste_costo, registrar_ajuste_gasto, registrar_atencion_completada, registrar_gasto


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
        hecho.refresh_from_db()
        self.assertEqual(ImputacionCosto.objects.filter(hecho=hecho).count(), 0)
        self.assertIsNotNone(hecho.ultimo_costeo_en)
        self.assertTrue(PendienteCosteo.objects.filter(hecho=hecho, motivo=PendienteCosteo.Motivo.SIN_PRESTACION, resuelto=False).exists())

    def test_una_prestacion_configurada_despues_no_completa_el_hecho_anterior(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("100.00"),
            vigente_desde=hecho.ocurrida_en - timedelta(days=1),
        )

        procesar_hecho_atencion(hecho.id)

        self.assertFalse(ComponenteEsperadoHecho.objects.filter(hecho=hecho).exists())
        self.assertFalse(ImputacionCosto.objects.filter(hecho=hecho).exists())
        self.assertTrue(
            PendienteCosteo.objects.filter(
                hecho=hecho,
                motivo=PendienteCosteo.Motivo.SIN_PRESTACION,
                resuelto=False,
            ).exists()
        )

    def test_un_fallo_al_congelar_componentes_no_revierte_el_hecho(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")

        with patch("apps.finanzas.services._congelar_componentes", side_effect=RuntimeError("catálogo no disponible")):
            hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)

        hecho.refresh_from_db()
        self.assertTrue(hecho.componentes_congelados)
        self.assertTrue(
            PendienteCosteo.objects.filter(
                hecho=hecho,
                motivo="snapshot_incompleto",
                resuelto=False,
            ).exists()
        )

    def test_una_correccion_explicita_recongela_el_snapshot_y_deja_traza(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        with patch("apps.finanzas.services._congelar_componentes", side_effect=RuntimeError("catálogo no disponible")):
            hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("100.00"),
            vigente_desde=hecho.ocurrida_en - timedelta(days=1),
        )
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )

        correccion = corregir_snapshot_componentes(
            hecho.id,
            "Se verificó el catálogo aplicable al hecho.",
            self.usuario,
        )

        self.assertEqual(CorreccionSnapshotCosteo.objects.get(pk=correccion.id).hecho, hecho)
        self.assertTrue(ImputacionCosto.objects.filter(hecho=hecho, componente=componente).exists())
        self.assertTrue(
            PendienteCosteo.objects.get(
                hecho=hecho,
                motivo=PendienteCosteo.Motivo.SNAPSHOT_INCOMPLETO,
            ).resuelto
        )

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
        self.assertEqual(imputacion.unidad, DefinicionComponente.Unidad.ATENCION)
        self.assertEqual(imputacion.base_calculo, DefinicionComponente.BaseCalculo.POR_ATENCION)
        self.assertEqual(imputacion.moneda, ValorComponente.Moneda.ARS)
        esperado = ComponenteEsperadoHecho.objects.get(hecho=hecho, componente=componente)
        self.assertEqual(esperado.unidad, DefinicionComponente.Unidad.ATENCION)
        self.assertEqual(esperado.base_calculo, DefinicionComponente.BaseCalculo.POR_ATENCION)
        with self.assertRaises(ValidationError):
            ImputacionCosto(
                hecho=hecho,
                componente=componente,
                valor=imputacion.valor,
                importe=imputacion.importe,
                moneda="USD",
            ).save()
        self.assertEqual(ImputacionCosto.objects.filter(hecho=hecho).count(), 1)

    def test_un_valor_de_costo_directo_no_admite_otra_moneda_en_v1(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )

        with self.assertRaises(ValidationError):
            ValorComponente(
                componente=componente,
                importe=Decimal("1250.50"),
                moneda="USD",
                vigente_desde=timezone.now(),
            ).full_clean()

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

    def test_un_valor_futuro_sucede_al_abierto_sin_reescribirlo(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ahora = timezone.now()
        anterior = ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("100.00"),
            vigente_desde=ahora,
        )
        siguiente = ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("120.00"),
            vigente_desde=ahora + timedelta(days=30),
            reemplaza=anterior,
        )

        anterior.refresh_from_db()
        self.assertIsNone(anterior.vigente_hasta)
        self.assertEqual(siguiente.reemplaza, anterior)

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

    def test_el_comando_rechaza_un_lote_no_positivo(self):
        with self.assertRaisesMessage(CommandError, "--limite debe ser mayor que cero"):
            call_command("procesar_costos", "--limite", "0")

    def test_el_comando_registra_el_error_recuperable_del_hecho(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        with patch(
            "apps.finanzas.management.commands.procesar_costos.procesar_hecho_atencion",
            side_effect=RuntimeError("fuente temporalmente caída"),
        ):
            call_command("procesar_costos", "--limite", "1", stderr=StringIO())
        self.assertTrue(
            PendienteCosteo.objects.filter(
                hecho=hecho,
                motivo=PendienteCosteo.Motivo.ERROR_RECUPERABLE,
                resuelto=False,
            ).exists()
        )

    def test_un_error_en_el_intento_directo_no_borra_el_hecho_y_queda_pendiente(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        with patch("apps.finanzas.services.procesar_hecho_atencion", side_effect=RuntimeError("fuente temporalmente caída")):
            self.assertFalse(intentar_costeo_directo(hecho.id))
        self.assertTrue(
            PendienteCosteo.objects.filter(
                hecho=hecho,
                motivo=PendienteCosteo.Motivo.ERROR_RECUPERABLE,
                resuelto=False,
            ).exists()
        )
        ValorComponente.objects.create(componente=componente, importe=Decimal("100.00"), vigente_desde=hecho.ocurrida_en - timedelta(days=1))
        procesar_hecho_atencion(hecho.id)
        self.assertTrue(
            PendienteCosteo.objects.get(
                hecho=hecho,
                motivo=PendienteCosteo.Motivo.ERROR_RECUPERABLE,
            ).resuelto
        )

    def test_un_fallo_al_marcar_el_error_no_se_propaga_a_la_atencion(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        with (
            patch("apps.finanzas.services.procesar_hecho_atencion", side_effect=RuntimeError("fuente temporalmente caída")),
            patch("apps.finanzas.services.registrar_error_recuperable", side_effect=RuntimeError("base temporalmente caída")),
        ):
            self.assertFalse(intentar_costeo_directo(hecho.id))
        self.assertTrue(HechoAtencionCosteable.objects.filter(pk=hecho.id).exists())

    def test_un_pendiente_sin_componente_no_se_duplica(self):
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PendienteCosteo.objects.create(hecho=hecho, motivo=PendienteCosteo.Motivo.SIN_PRESTACION)

    def test_la_concesion_financiera_no_une_areas_de_otras_membresias(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Internación")
        financiera = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.MEDICO)
        financiera.areas.add(self.area)
        clinica = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ENFERMERIA)
        clinica.areas.add(otra_area)
        concesion = ConcesionFinanciera.objects.create(membresia=financiera, accion=ConcesionFinanciera.Accion.VER_COSTOS)
        concesion.areas.add(self.area)
        self.assertTrue(tiene_concesion_financiera(self.usuario, ConcesionFinanciera.Accion.VER_COSTOS, self.institucion.id, self.area.id))
        self.assertFalse(tiene_concesion_financiera(self.usuario, ConcesionFinanciera.Accion.VER_COSTOS, self.institucion.id, otra_area.id))

    def test_los_costos_sensibles_y_las_correcciones_exigen_admin_explicito(self):
        miembro = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        miembro.areas.add(self.area)
        with self.assertRaises(ValidationError):
            ConcesionFinanciera.objects.create(
                membresia=miembro,
                accion=ConcesionFinanciera.Accion.VER_COSTOS,
                permite_sensibles=True,
            )

        admin = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=admin,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.assertTrue(
            tiene_concesion_financiera(
                self.usuario,
                concesion.accion,
                self.institucion.id,
                self.area.id,
                sensible=True,
            )
        )

    def test_las_acciones_de_gastos_reutilizan_alcance_y_admin_explicito(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Internación")
        delegado = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        for accion in (
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            ConcesionFinanciera.Accion.CORREGIR_GASTOS,
            ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
        ):
            with self.assertRaises(ValidationError):
                ConcesionFinanciera.objects.create(
                    membresia=delegado,
                    accion=accion,
                    todas_las_areas=True,
                )

        registro = ConcesionFinanciera.objects.create(
            membresia=delegado,
            accion=ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
        )
        registro.areas.add(self.area)
        self.assertTrue(
            tiene_concesion_financiera(
                self.usuario,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
                self.institucion.id,
                self.area.id,
            )
        )
        self.assertFalse(
            tiene_concesion_financiera(
                self.usuario,
                ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
                self.institucion.id,
                otra_area.id,
            )
        )

        admin = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        lectura_sensible = ConcesionFinanciera.objects.create(
            membresia=admin,
            accion=ConcesionFinanciera.Accion.VER_GASTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.assertTrue(
            tiene_concesion_financiera(
                self.usuario,
                lectura_sensible.accion,
                self.institucion.id,
                self.area.id,
                sensible=True,
            )
        )

    def test_ajuste_conserva_la_imputacion_original_y_exige_concesion(self):
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(componente=componente, importe=Decimal("100.00"), vigente_desde=timezone.now() - timedelta(days=1))
        evento = EventoCaso.objects.create(caso=self.caso, nodo=self.nodo, autor=self.usuario, titulo="Atención registrada")
        hecho = registrar_atencion_completada(self.caso, self.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        imputacion = ImputacionCosto.objects.get(hecho=hecho, componente=componente)
        with self.assertRaises(PermissionDenied):
            registrar_ajuste_costo(imputacion, Decimal("-10.00"), "Descuento posterior", self.usuario)
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        ajuste = registrar_ajuste_costo(imputacion, Decimal("-10.00"), "Descuento posterior", self.usuario)
        imputacion.refresh_from_db()
        self.assertEqual(imputacion.importe, Decimal("100.00"))
        self.assertEqual(ajuste.importe, Decimal("-10.00"))
        with self.assertRaises(ValidationError):
            ajuste.delete()


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueo de fila PostgreSQL.")
class CosteoAtencionConcurrentePostgreSQLTests(TransactionTestCase):
    """Verifica el bloqueo que evita duplicar costos ante dos recuperadores."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user("concurrencia@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Paz")
        caso = Caso.objects.create(
            institucion=self.institucion,
            version=version,
            ciudadano=ciudadano,
            area_actual=area,
        )
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        self.componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        ValorComponente.objects.create(
            componente=self.componente,
            importe=Decimal("1250.50"),
            vigente_desde=timezone.now() - timedelta(days=1),
        )
        evento = EventoCaso.objects.create(
            caso=caso,
            nodo=self.nodo,
            autor=self.usuario,
            titulo="Atención registrada",
        )
        self.hecho = registrar_atencion_completada(caso, self.nodo, evento, self.usuario)

    def test_dos_recuperadores_concurrentes_crean_una_sola_imputacion(self):
        inicio = Barrier(2)

        def procesar_en_paralelo():
            close_old_connections()
            try:
                inicio.wait(timeout=5)
                return procesar_hecho_atencion(self.hecho.id).id
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutores:
            resultados = list(ejecutores.map(lambda _indice: procesar_en_paralelo(), range(2)))

        self.assertEqual(resultados, [self.hecho.id, self.hecho.id])
        self.assertEqual(
            ImputacionCosto.objects.filter(hecho=self.hecho, componente=self.componente).count(),
            1,
        )


@skipUnless(connection.vendor == "postgresql", "Requiere bloqueo de fila PostgreSQL.")
class AprobacionGastoConcurrentePostgreSQLTests(TransactionTestCase):
    """La aprobación de una carga delegada conserva un único gasto aprobado."""

    def setUp(self):
        self.admin = Usuario.objects.create_user("aprobar-gasto@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="LIMPIEZA",
            nombre="Limpieza",
        )
        membresia = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.APROBAR_GASTOS,
            todas_las_areas=True,
        )
        self.gasto = Gasto.objects.create(
            concepto=self.concepto,
            institucion=self.institucion,
            area=self.area,
            importe=Decimal("100.00"),
            periodo_economico=date(2026, 8, 1),
            origen=Gasto.Origen.AREA,
            registrado_por=self.admin,
        )

    def test_dos_aprobadores_reintentando_no_duplican_el_gasto(self):
        inicio = Barrier(2)

        def aprobar_en_paralelo():
            close_old_connections()
            try:
                inicio.wait(timeout=5)
                usuario = Usuario.objects.get(pk=self.admin.pk)
                return aprobar_gasto(self.gasto.id, usuario).id
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutores:
            resultados = list(ejecutores.map(lambda _indice: aprobar_en_paralelo(), range(2)))

        self.assertEqual(resultados, [self.gasto.id, self.gasto.id])
        gasto = Gasto.objects.get(pk=self.gasto.id)
        self.assertEqual(gasto.estado, Gasto.Estado.APROBADO)
        self.assertEqual(Gasto.objects.filter(pk=self.gasto.id).count(), 1)


class HechoCostoApiTests(APITestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("admin-finanzas@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Paz")
        caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano, area_actual=self.area)
        evento = EventoCaso.objects.create(caso=caso, nodo=nodo, autor=self.usuario, titulo="Atención registrada")
        self.hecho = registrar_atencion_completada(caso, nodo, evento, self.usuario)
        procesar_hecho_atencion(self.hecho.id)

    def crear_hecho_costeado(self, sensible=False):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.hecho.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
            sensible=sensible,
        )
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("1250.50"),
            vigente_desde=self.hecho.ocurrida_en - timedelta(days=1),
        )
        evento = EventoCaso.objects.create(
            caso=self.hecho.caso,
            nodo=self.hecho.nodo,
            autor=self.usuario,
            titulo="Atención registrada",
        )
        hecho = registrar_atencion_completada(self.hecho.caso, self.hecho.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        return hecho

    def test_sin_concesion_no_expone_costos_del_paciente(self):
        self.client.force_authenticate(self.usuario)
        response = self.client.get("/api/hechos-costo/")
        self.assertEqual(response.status_code, 403)

    def test_concesion_no_sensible_ve_un_costo_no_sensible_de_su_area(self):
        hecho = self.crear_hecho_costeado()
        usuario = Usuario.objects.create_user("finanzas-area@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
        )
        concesion.areas.add(self.area)
        self.client.force_authenticate(usuario)

        response = self.client.get(f"/api/hechos-costo/{hecho.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_conocido"], "1250.50")

    def test_concesion_no_sensible_no_ve_un_costo_sensible(self):
        hecho = self.crear_hecho_costeado(sensible=True)
        usuario_restringido = Usuario.objects.create_user("finanzas-restringida@cauce.local", "x")
        membresia_restringida = Membresia.objects.create(
            usuario=usuario_restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        concesion_restringida = ConcesionFinanciera.objects.create(
            membresia=membresia_restringida,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
        )
        concesion_restringida.areas.add(self.area)
        self.client.force_authenticate(usuario_restringido)

        respuesta_restringida = self.client.get(f"/api/hechos-costo/{hecho.id}/")

        self.assertEqual(respuesta_restringida.status_code, 404)

        usuario_sensible = Usuario.objects.create_user("finanzas-sensible@cauce.local", "x")
        membresia_sensible = Membresia.objects.create(
            usuario=usuario_sensible,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion_sensible = ConcesionFinanciera.objects.create(
            membresia=membresia_sensible,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            permite_sensibles=True,
        )
        concesion_sensible.areas.add(self.area)
        self.client.force_authenticate(usuario_sensible)

        respuesta_sensible = self.client.get(f"/api/hechos-costo/{hecho.id}/")

        self.assertEqual(respuesta_sensible.status_code, 200)

    def test_no_se_puede_crear_un_hecho_de_costo_por_la_api(self):
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.post("/api/hechos-costo/", {}, format="json")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(HechoAtencionCosteable.objects.count(), 1)

    def test_concesion_sensible_muestra_faltantes_sin_convertirlos_en_cero(self):
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.client.force_authenticate(self.usuario)
        response = self.client.get(f"/api/hechos-costo/?ciudadano={self.hecho.ciudadano_id}")
        self.assertEqual(response.status_code, 200)
        fila = response.data["results"][0]
        self.assertIsNone(fila["total_conocido"])
        self.assertFalse(fila["total_directo_es_completo"])
        self.assertFalse(fila["total_es_completo"])
        self.assertEqual(fila["estado_costo"], "pendiente")
        self.assertEqual(fila["faltantes"][0]["motivo"], PendienteCosteo.Motivo.SIN_PRESTACION)
        self.assertEqual(fila["faltantes"][-1]["motivo"], "fuentes_no_integradas")

    def test_concesion_por_area_no_expone_costos_de_otra_area(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Internación")
        otro_flujo = Flujo.objects.create(institucion=self.institucion, area=otra_area, titulo="Internación")
        otra_version = VersionFlujo.objects.create(flujo=otro_flujo, numero=1)
        otro_nodo = Nodo.objects.create(version=otra_version, tipo=Nodo.Tipo.ATENCION, titulo="Pase de sala")
        otro_caso = Caso.objects.create(
            institucion=self.institucion,
            version=otra_version,
            ciudadano=self.hecho.ciudadano,
            area_actual=otra_area,
        )
        otro_evento = EventoCaso.objects.create(
            caso=otro_caso,
            nodo=otro_nodo,
            autor=self.usuario,
            titulo="Atención registrada",
        )
        oculto = registrar_atencion_completada(otro_caso, otro_nodo, otro_evento, self.usuario)
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion = ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            permite_sensibles=True,
        )
        concesion.areas.add(self.area)
        self.client.force_authenticate(self.usuario)

        respuesta_lista = self.client.get("/api/hechos-costo/")
        respuesta_detalle = self.client.get(f"/api/hechos-costo/{oculto.id}/")

        self.assertEqual(respuesta_lista.status_code, 200)
        self.assertEqual([fila["id"] for fila in respuesta_lista.data["results"]], [self.hecho.id])
        self.assertEqual(respuesta_detalle.status_code, 404)

    def test_el_costo_conserva_el_area_de_la_atencion_si_el_caso_se_mueve(self):
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Internación")
        self.hecho.caso.area_actual = otra_area
        self.hecho.caso.save(update_fields=["area_actual"])

        membresia_origen = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion_origen = ConcesionFinanciera.objects.create(
            membresia=membresia_origen,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            permite_sensibles=True,
        )
        concesion_origen.areas.add(self.area)
        self.client.force_authenticate(self.usuario)

        respuesta_origen = self.client.get(f"/api/hechos-costo/{self.hecho.id}/")

        self.assertEqual(respuesta_origen.status_code, 200)
        self.assertEqual(respuesta_origen.data["area"], self.area.id)

        usuario_destino = Usuario.objects.create_user("finanzas-destino@cauce.local", "x")
        membresia_destino = Membresia.objects.create(
            usuario=usuario_destino,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        concesion_destino = ConcesionFinanciera.objects.create(
            membresia=membresia_destino,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            permite_sensibles=True,
        )
        concesion_destino.areas.add(otra_area)
        self.client.force_authenticate(usuario_destino)

        respuesta_destino = self.client.get(f"/api/hechos-costo/{self.hecho.id}/")

        self.assertEqual(respuesta_destino.status_code, 404)

    def test_concesion_sensible_muestra_el_total_directo_cuando_esta_completo(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.hecho.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("1250.50"),
            vigente_desde=self.hecho.ocurrida_en - timedelta(days=1),
        )
        evento = EventoCaso.objects.create(
            caso=self.hecho.caso,
            nodo=self.hecho.nodo,
            autor=self.usuario,
            titulo="Atención registrada",
        )
        hecho = registrar_atencion_completada(self.hecho.caso, self.hecho.nodo, evento, self.usuario)
        procesar_hecho_atencion(hecho.id)
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        registrar_ajuste_costo(
            ImputacionCosto.objects.get(hecho=hecho, componente=componente),
            Decimal("-50.00"),
            "Corrección de importe",
            self.usuario,
        )
        self.client.force_authenticate(self.usuario)
        response = self.client.get(f"/api/hechos-costo/{hecho.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_conocido"], "1200.50")
        self.assertEqual(response.data["moneda"], ValorComponente.Moneda.ARS)
        self.assertTrue(response.data["total_directo_es_completo"])
        self.assertFalse(response.data["total_es_completo"])
        self.assertEqual(response.data["estado_costo"], "parcial")
        self.assertIsNotNone(response.data["actualizado_en"])
        self.assertEqual(response.data["faltantes"][-1]["motivo"], "fuentes_no_integradas")
        self.assertEqual(
            response.data["alcance"]["pendiente_de_integracion"],
            ["gastos_compartidos", "otras_fuentes_de_costo"],
        )
        self.assertEqual(response.data["imputaciones"][0]["ajustes"][0]["importe"], "-50.00")
        self.assertEqual(response.data["imputaciones"][0]["unidad"], DefinicionComponente.Unidad.ATENCION)
        self.assertEqual(
            response.data["imputaciones"][0]["base_calculo"],
            DefinicionComponente.BaseCalculo.POR_ATENCION,
        )
        self.assertEqual(response.data["imputaciones"][0]["moneda"], ValorComponente.Moneda.ARS)
        self.assertEqual(response.data["imputaciones"][0]["ajustes"][0]["moneda"], ValorComponente.Moneda.ARS)

    def test_componentes_congelados_sin_calcular_no_marcan_el_directo_completo(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.hecho.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("1250.50"),
            vigente_desde=self.hecho.ocurrida_en - timedelta(days=1),
        )
        evento = EventoCaso.objects.create(
            caso=self.hecho.caso,
            nodo=self.hecho.nodo,
            autor=self.usuario,
            titulo="Atención registrada",
        )
        hecho = registrar_atencion_completada(self.hecho.caso, self.hecho.nodo, evento, self.usuario)
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.VER_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.get(f"/api/hechos-costo/{hecho.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["total_conocido"])
        self.assertFalse(response.data["total_directo_es_completo"])
        self.assertEqual(response.data["estado_costo"], "pendiente")

    def test_correccion_de_snapshot_requiere_accion_explicita_y_deja_traza(self):
        evento = EventoCaso.objects.create(
            caso=self.hecho.caso,
            nodo=self.hecho.nodo,
            autor=self.usuario,
            titulo="Atención con catálogo no disponible",
        )
        with patch(
            "apps.finanzas.services._congelar_componentes",
            side_effect=RuntimeError("catálogo no disponible"),
        ):
            hecho = registrar_atencion_completada(
                self.hecho.caso, self.hecho.nodo, evento, self.usuario
            )
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.hecho.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        ValorComponente.objects.create(
            componente=componente,
            importe=Decimal("1250.00"),
            vigente_desde=hecho.ocurrida_en - timedelta(days=1),
        )
        membresia = Membresia.objects.create(
            usuario=self.usuario,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        self.client.force_authenticate(self.usuario)

        response = self.client.post(
            f"/api/hechos-costo/{hecho.id}/corregir-snapshot/",
            {"motivo": "Se recuperó el catálogo aplicable"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["hecho"], hecho.id)
        self.assertTrue(
            CorreccionSnapshotCosteo.objects.filter(
                hecho=hecho,
                motivo="Se recuperó el catálogo aplicable",
            ).exists()
        )
        self.assertTrue(
            ImputacionCosto.objects.filter(hecho=hecho, componente=componente).exists()
        )

        repetida = self.client.post(
            f"/api/hechos-costo/{hecho.id}/corregir-snapshot/",
            {"motivo": "Segundo intento"},
            format="json",
        )

        self.assertEqual(repetida.status_code, 400)
        self.assertEqual(CorreccionSnapshotCosteo.objects.filter(hecho=hecho).count(), 1)

    def test_sin_concesion_no_puede_corregir_un_snapshot_pendiente(self):
        evento = EventoCaso.objects.create(
            caso=self.hecho.caso,
            nodo=self.hecho.nodo,
            autor=self.usuario,
            titulo="Atención con catálogo no disponible",
        )
        with patch(
            "apps.finanzas.services._congelar_componentes",
            side_effect=RuntimeError("catálogo no disponible"),
        ):
            hecho = registrar_atencion_completada(
                self.hecho.caso, self.hecho.nodo, evento, self.usuario
            )
        self.client.force_authenticate(self.usuario)

        response = self.client.post(
            f"/api/hechos-costo/{hecho.id}/corregir-snapshot/",
            {"motivo": "No autorizado"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CorreccionSnapshotCosteo.objects.filter(hecho=hecho).exists())


class ConcesionFinancieraApiTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user("admin@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.membresia_admin = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        self.operador = Usuario.objects.create_user("operador@cauce.local", "x")
        self.membresia_operador = Membresia.objects.create(
            usuario=self.operador,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        self.membresia_operador.areas.add(self.area)

    def test_admin_institucional_otorga_concesion_acotada_a_un_area(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/concesiones-financieras/",
            {
                "membresia": self.membresia_operador.id,
                "accion": ConcesionFinanciera.Accion.VER_COSTOS,
                "areas": [self.area.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            ConcesionFinanciera.objects.filter(
                membresia=self.membresia_operador,
                accion=ConcesionFinanciera.Accion.VER_COSTOS,
                areas=self.area,
            ).exists()
        )

    def test_admin_no_puede_otorgar_concesion_en_otra_institucion(self):
        otra = Institucion.objects.create(nombre="Hospital Norte")
        ajena = Membresia.objects.create(
            usuario=self.operador,
            institucion=otra,
            rol=Membresia.Rol.MEDICO,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/concesiones-financieras/",
            {
                "membresia": ajena.id,
                "accion": ConcesionFinanciera.Accion.VER_COSTOS,
                "todas_las_areas": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class CatalogoCostosApiTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user("catalogo@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        membresia = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CONFIGURAR_COMPONENTES,
            todas_las_areas=True,
        )

    def test_configurador_financiero_crea_prestacion_del_nodo_de_su_institucion(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/prestaciones-costo/",
            {
                "institucion": self.institucion.id,
                "nodo": self.nodo.id,
                "codigo": "CONS",
                "nombre": "Consulta",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Prestacion.objects.filter(institucion=self.institucion, codigo="CONS").exists())

    def test_membresia_sin_concesion_no_crea_prestaciones(self):
        sin_concesion = Usuario.objects.create_user("sin-concesion@cauce.local", "x")
        Membresia.objects.create(
            usuario=sin_concesion,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        self.client.force_authenticate(sin_concesion)
        response = self.client.post(
            "/api/prestaciones-costo/",
            {
                "institucion": self.institucion.id,
                "nodo": self.nodo.id,
                "codigo": "CONS",
                "nombre": "Consulta",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_configurador_financiero_agrega_componente_directo_a_su_prestacion(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/componentes-costo/",
            {
                "prestacion": prestacion.id,
                "codigo": "BASE",
                "nombre": "Costo directo",
                "fuente": DefinicionComponente.Fuente.ATENCION_DIRECTA,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["unidad"], DefinicionComponente.Unidad.ATENCION)
        self.assertEqual(
            response.data["base_calculo"],
            DefinicionComponente.BaseCalculo.POR_ATENCION,
        )
        componente = DefinicionComponente.objects.get(prestacion=prestacion, codigo="BASE")
        self.assertEqual(
            self.client.patch(
                f"/api/componentes-costo/{componente.id}/",
                {"codigo": "OTRO"},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/componentes-costo/{componente.id}/",
                {"sensible": True},
                format="json",
            ).status_code,
            200,
        )
        self.assertTrue(DefinicionComponente.objects.get(pk=componente.id).sensible)

    def test_configurador_da_de_baja_logica_prestacion_y_componente(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        self.client.force_authenticate(self.admin)

        baja_prestacion = self.client.patch(
            f"/api/prestaciones-costo/{prestacion.id}/",
            {"activo": False},
            format="json",
        )
        baja_componente = self.client.patch(
            f"/api/componentes-costo/{componente.id}/",
            {"activo": False},
            format="json",
        )

        self.assertEqual(baja_prestacion.status_code, 200)
        self.assertEqual(baja_componente.status_code, 200)
        self.assertFalse(Prestacion.objects.get(pk=prestacion.id).activo)
        self.assertFalse(DefinicionComponente.objects.get(pk=componente.id).activo)

    def test_configurador_financiero_agrega_valor_vigente_que_no_admite_patch(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/valores-componentes/",
            {
                "componente": componente.id,
                "importe": "1250.50",
                "vigente_desde": "2026-09-01T00:00:00Z",
                "fuente": "Resolución interna",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["moneda"], ValorComponente.Moneda.ARS)
        valor = ValorComponente.objects.get(componente=componente)
        self.assertEqual(valor.moneda, ValorComponente.Moneda.ARS)
        self.assertEqual(valor.registrado_por, self.admin)
        self.assertEqual(
            self.client.patch(
                f"/api/valores-componentes/{valor.id}/",
                {"importe": "1300.00"},
                format="json",
            ).status_code,
            405,
        )

    def test_configurador_no_puede_registrar_un_valor_en_otra_moneda_en_v1(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/valores-componentes/",
            {
                "componente": componente.id,
                "importe": "1250.50",
                "moneda": "USD",
                "vigente_desde": "2026-09-01T00:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ValorComponente.objects.filter(componente=componente).exists())

    def test_configurador_sin_habilitacion_sensible_no_ve_ni_registra_valores_sensibles(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo sensible",
            sensible=True,
        )
        valor = ValorComponente.objects.create(
            componente=componente,
            importe="100.00",
            vigente_desde="2026-09-01T00:00:00Z",
        )
        self.client.force_authenticate(self.admin)

        lista = self.client.get("/api/valores-componentes/")
        alta = self.client.post(
            "/api/valores-componentes/",
            {
                "componente": componente.id,
                "importe": "120.00",
                "vigente_desde": "2026-10-01T00:00:00Z",
                "reemplaza": valor.id,
            },
            format="json",
        )

        self.assertEqual(lista.status_code, 200)
        self.assertNotIn(valor.id, [fila["id"] for fila in lista.data["results"]])
        self.assertEqual(alta.status_code, 403)

    def test_corregir_un_valor_requiere_concesion_especifica(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        valor = ValorComponente.objects.create(
            componente=componente,
            importe="100.00",
            vigente_desde="2026-09-01T00:00:00Z",
        )
        datos = {
            "componente": componente.id,
            "importe": "120.00",
            "vigente_desde": "2026-09-01T00:00:00Z",
            "reemplaza": valor.id,
            "motivo_correccion": "Importe cargado por error",
        }
        self.client.force_authenticate(self.admin)
        self.assertEqual(
            self.client.post("/api/valores-componentes/", datos, format="json").status_code,
            403,
        )
        membresia = Membresia.objects.get(usuario=self.admin, institucion=self.institucion)
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
        )
        response = self.client.post("/api/valores-componentes/", datos, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ValorComponente.objects.get(pk=response.data["id"]).reemplaza, valor)

    def test_configurador_programa_un_valor_futuro_sin_permiso_de_correccion(self):
        prestacion = Prestacion.objects.create(
            institucion=self.institucion,
            nodo=self.nodo,
            codigo="CONS",
            nombre="Consulta",
        )
        componente = DefinicionComponente.objects.create(
            prestacion=prestacion,
            codigo="BASE",
            nombre="Costo directo",
        )
        anterior = ValorComponente.objects.create(
            componente=componente,
            importe="100.00",
            vigente_desde="2026-09-01T00:00:00Z",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/valores-componentes/",
            {
                "componente": componente.id,
                "importe": "120.00",
                "vigente_desde": "2026-10-01T00:00:00Z",
                "reemplaza": anterior.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ValorComponente.objects.get(pk=response.data["id"]).reemplaza, anterior)


class AjusteCostoApiTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user("correccion@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.institucion, area=area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Ana", apellido="Paz")
        caso = Caso.objects.create(institucion=self.institucion, version=version, ciudadano=ciudadano, area_actual=area)
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
        ValorComponente.objects.create(componente=componente, importe="100.00", vigente_desde=timezone.now() - timedelta(days=1))
        evento = EventoCaso.objects.create(caso=caso, nodo=nodo, autor=self.admin, titulo="Atención registrada")
        hecho = registrar_atencion_completada(caso, nodo, evento, self.admin)
        procesar_hecho_atencion(hecho.id)
        self.imputacion = ImputacionCosto.objects.get(hecho=hecho, componente=componente)
        membresia = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )

    def test_correccion_autorizada_registra_ajuste_sin_mutar_el_importe_original(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/ajustes-costo/",
            {
                "imputacion": self.imputacion.id,
                "importe": "-10.00",
                "motivo": "Descuento posterior",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.imputacion.refresh_from_db()
        self.assertEqual(self.imputacion.importe, Decimal("100.00"))
        self.assertTrue(AjusteCosto.objects.filter(imputacion=self.imputacion, importe="-10.00").exists())

    def test_correccion_sin_acceso_sensible_no_ajusta_un_costo_del_paciente(self):
        restringido = Usuario.objects.create_user("sin-sensible@cauce.local", "x")
        membresia = Membresia.objects.create(
            usuario=restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia,
            accion=ConcesionFinanciera.Accion.CORREGIR_COSTOS,
            todas_las_areas=True,
        )
        self.client.force_authenticate(restringido)
        response = self.client.post(
            "/api/ajustes-costo/",
            {
                "imputacion": self.imputacion.id,
                "importe": "-10.00",
                "motivo": "Descuento posterior",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)


class ExpectativaGastoTests(TestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="ELECTRICIDAD",
            nombre="Electricidad",
        )

    def crear_expectativa(self, **overrides):
        datos = {
            "concepto": self.concepto,
            "institucion": self.institucion,
            "area": self.area,
            "vigente_desde": date(2026, 9, 1),
        }
        datos.update(overrides)
        return ExpectativaGasto.objects.create(**datos)

    def test_exige_concepto_y_area_del_mismo_ambito_mensual(self):
        otra_institucion = Institucion.objects.create(nombre="Hospital Norte")
        otra_area = Area.objects.create(institucion=otra_institucion, nombre="Clínica")
        otro_concepto = ConceptoGasto.objects.create(
            institucion=otra_institucion,
            codigo="LIMPIEZA",
            nombre="Limpieza",
        )

        with self.assertRaises(ValidationError):
            self.crear_expectativa(area=otra_area)
        with self.assertRaises(ValidationError):
            self.crear_expectativa(concepto=otro_concepto)
        with self.assertRaises(ValidationError):
            self.crear_expectativa(vigente_desde=date(2026, 9, 2))

    def test_congela_sensibilidad_y_no_permite_solapamientos(self):
        self.concepto.sensible = True
        self.concepto.save()
        expectativa = self.crear_expectativa()
        self.concepto.sensible = False
        self.concepto.save()

        expectativa.refresh_from_db()
        self.assertTrue(expectativa.sensible)
        with self.assertRaises(ValidationError):
            self.crear_expectativa(vigente_desde=date(2026, 10, 1))

    def test_correccion_reemplaza_sin_editar_la_expectativa_original(self):
        original = self.crear_expectativa(vigente_hasta=date(2026, 10, 1))

        with self.assertRaises(ValidationError):
            self.crear_expectativa(
                vigente_hasta=date(2026, 10, 1),
                reemplaza=original,
            )
        correccion = self.crear_expectativa(
            vigente_hasta=date(2026, 10, 1),
            reemplaza=original,
            motivo_correccion="Corrección de expectativa",
        )

        self.assertEqual(correccion.reemplaza, original)
        with self.assertRaises(ValidationError):
            original.delete()
        original.vigente_hasta = date(2026, 11, 1)
        with self.assertRaises(ValidationError):
            original.save()


class GastoTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user("gastos@cauce.local", "x")
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="ELECTRICIDAD",
            nombre="Electricidad",
            sensible=True,
        )

    def crear_gasto_central(self, **overrides):
        datos = {
            "concepto": self.concepto,
            "institucion": self.institucion,
            "area": self.area,
            "importe": Decimal("100.00"),
            "periodo_economico": date(2026, 8, 1),
            "origen": Gasto.Origen.CENTRAL,
            "estado": Gasto.Estado.APROBADO,
            "registrado_por": self.usuario,
            "aprobado_por": self.usuario,
            "aprobado_en": timezone.now(),
        }
        datos.update(overrides)
        return Gasto.objects.create(**datos)

    def crear_gasto_area(self, **overrides):
        datos = {
            "concepto": self.concepto,
            "institucion": self.institucion,
            "area": self.area,
            "importe": Decimal("100.00"),
            "periodo_economico": date(2026, 8, 1),
            "origen": Gasto.Origen.AREA,
            "registrado_por": self.usuario,
        }
        datos.update(overrides)
        return Gasto.objects.create(**datos)

    def test_gasto_central_congela_concepto_y_no_edita_su_carga(self):
        gasto = self.crear_gasto_central()
        self.concepto.nombre = "Servicio eléctrico"
        self.concepto.sensible = False
        self.concepto.save()

        gasto.refresh_from_db()
        self.assertEqual(gasto.concepto_codigo, "ELECTRICIDAD")
        self.assertEqual(gasto.concepto_nombre, "Electricidad")
        self.assertTrue(gasto.sensible)
        gasto.importe = Decimal("120.00")
        with self.assertRaises(ValidationError):
            gasto.save()
        with self.assertRaises(ValidationError):
            gasto.delete()

    def test_gasto_de_area_se_decide_una_vez_y_solo_acepta_ajustes_aprobados(self):
        pendiente = self.crear_gasto_area()
        with self.assertRaises(ValidationError):
            AjusteGasto.objects.create(
                gasto=pendiente,
                importe=Decimal("-10.00"),
                motivo="Corrección",
                registrado_por=self.usuario,
            )
        pendiente.estado = Gasto.Estado.APROBADO
        pendiente.aprobado_por = self.usuario
        pendiente.aprobado_en = timezone.now()
        pendiente.save()
        ajuste = AjusteGasto.objects.create(
            gasto=pendiente,
            importe=Decimal("-10.00"),
            motivo="Corrección",
            registrado_por=self.usuario,
        )

        self.assertEqual(ajuste.gasto, pendiente)
        pendiente.estado = Gasto.Estado.RECHAZADO
        pendiente.rechazado_por = self.usuario
        pendiente.rechazado_en = timezone.now()
        pendiente.motivo_rechazo = "Tardío"
        with self.assertRaises(ValidationError):
            pendiente.save()

    def test_reemplazo_no_sobrescribe_rechazado_ni_admite_aprobado(self):
        rechazado = self.crear_gasto_area()
        rechazado.estado = Gasto.Estado.RECHAZADO
        rechazado.rechazado_por = self.usuario
        rechazado.rechazado_en = timezone.now()
        rechazado.motivo_rechazo = "Importe incorrecto"
        rechazado.save()
        sucesor = self.crear_gasto_area(
            importe=Decimal("120.00"),
            reemplaza=rechazado,
        )

        self.assertEqual(sucesor.reemplaza, rechazado)
        with self.assertRaises(ValidationError):
            self.crear_gasto_area(reemplaza=self.crear_gasto_central())


class GastoServiciosTests(TestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="LIMPIEZA",
            nombre="Limpieza",
        )
        self.admin = Usuario.objects.create_user("admin-gastos@cauce.local", "x")
        self.delegado = Usuario.objects.create_user("area-gastos@cauce.local", "x")
        membresia_admin = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        for accion in (
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            ConcesionFinanciera.Accion.CORREGIR_GASTOS,
        ):
            ConcesionFinanciera.objects.create(
                membresia=membresia_admin,
                accion=accion,
                todas_las_areas=True,
                permite_sensibles=True,
            )
        membresia_delegado = Membresia.objects.create(
            usuario=self.delegado,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        concesion_delegado = ConcesionFinanciera.objects.create(
            membresia=membresia_delegado,
            accion=ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
        )
        concesion_delegado.areas.add(self.area)

    def registrar(self, usuario, **overrides):
        datos = {
            "concepto": self.concepto,
            "institucion": self.institucion,
            "area": self.area,
            "importe": Decimal("100.00"),
            "periodo_economico": date(2026, 8, 1),
            "registrado_por": usuario,
        }
        datos.update(overrides)
        return registrar_gasto(**datos)

    def test_central_aprueba_directo_y_area_requiere_aprobacion_idempotente(self):
        central = self.registrar(self.admin)
        pendiente = self.registrar(self.delegado)

        self.assertEqual(central.origen, Gasto.Origen.CENTRAL)
        self.assertEqual(central.estado, Gasto.Estado.APROBADO)
        self.assertEqual(pendiente.origen, Gasto.Origen.AREA)
        self.assertEqual(pendiente.estado, Gasto.Estado.PENDIENTE_APROBACION)
        self.assertEqual(aprobar_gasto(pendiente.id, self.admin).id, pendiente.id)
        self.assertEqual(aprobar_gasto(pendiente.id, self.admin).id, pendiente.id)
        self.assertEqual(Gasto.objects.filter(pk=pendiente.id).count(), 1)
        self.assertEqual(Gasto.objects.get(pk=pendiente.id).estado, Gasto.Estado.APROBADO)

    def test_rechazo_y_reemplazo_no_permiten_aprobar_la_carga_anterior(self):
        pendiente = self.registrar(self.delegado)
        rechazado = rechazar_gasto(pendiente.id, "Importe incorrecto", self.admin)
        sucesor = self.registrar(self.delegado, importe=Decimal("120.00"), reemplaza=rechazado)

        self.assertEqual(sucesor.reemplaza, rechazado)
        with self.assertRaises(ValidationError):
            aprobar_gasto(rechazado.id, self.admin)

    def test_sensibilidad_y_correccion_exigen_la_concesion_correcta(self):
        self.concepto.sensible = True
        self.concepto.save()
        with self.assertRaises(PermissionDenied):
            self.registrar(self.delegado)

        gasto = self.registrar(self.admin)
        ajuste = registrar_ajuste_gasto(
            gasto.id,
            Decimal("-10.00"),
            "Descuento acordado",
            self.admin,
        )
        self.assertEqual(ajuste.gasto, gasto)

    def test_registro_relee_sensibilidad_antes_de_autorizar(self):
        concepto_desactualizado = ConceptoGasto.objects.get(pk=self.concepto.pk)
        ConceptoGasto.objects.filter(pk=self.concepto.pk).update(sensible=True)

        with self.assertRaises(PermissionDenied):
            self.registrar(self.delegado, concepto=concepto_desactualizado)


class ConceptoGastoApiTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.admin = Usuario.objects.create_user("config-gastos@cauce.local", "x")
        self.delegado = Usuario.objects.create_user("carga-gastos@cauce.local", "x")
        self.admin_restringido = Usuario.objects.create_user("sin-sensible-gastos@cauce.local", "x")
        membresia_admin = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia_admin,
            accion=ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            todas_las_areas=True,
            permite_sensibles=True,
        )
        membresia_delegado = Membresia.objects.create(
            usuario=self.delegado,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        concesion_delegado = ConcesionFinanciera.objects.create(
            membresia=membresia_delegado,
            accion=ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
        )
        concesion_delegado.areas.add(self.area)
        membresia_restringido = Membresia.objects.create(
            usuario=self.admin_restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia_restringido,
            accion=ConcesionFinanciera.Accion.CONFIGURAR_GASTOS_ESPERADOS,
            todas_las_areas=True,
        )

    def test_admin_configura_concepto_y_solo_altera_estado_o_sensibilidad(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/conceptos-gasto/",
            {
                "institucion": self.institucion.id,
                "codigo": "ELECTRICIDAD",
                "nombre": "Electricidad",
                "sensible": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        concepto = ConceptoGasto.objects.get(pk=response.data["id"])
        self.assertEqual(concepto.registrado_por, self.admin)
        self.assertTrue(concepto.sensible)
        respuesta_invalida = self.client.patch(
            f"/api/conceptos-gasto/{concepto.id}/",
            {"nombre": "Servicio eléctrico"},
            format="json",
        )
        self.assertEqual(respuesta_invalida.status_code, 400)

    def test_delegado_solo_ve_conceptos_no_sensibles_y_no_configura(self):
        visible = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="LIMPIEZA",
            nombre="Limpieza",
        )
        sensible = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="SUELDOS",
            nombre="Sueldos",
            sensible=True,
        )
        self.client.force_authenticate(self.delegado)

        listado = self.client.get("/api/conceptos-gasto/")
        self.assertEqual(listado.status_code, 200)
        self.assertEqual([fila["id"] for fila in listado.data["results"]], [visible.id])
        detalle_sensible = self.client.get(f"/api/conceptos-gasto/{sensible.id}/")
        self.assertEqual(detalle_sensible.status_code, 404)
        alta = self.client.post(
            "/api/conceptos-gasto/",
            {
                "institucion": self.institucion.id,
                "codigo": "AGUA",
                "nombre": "Agua",
            },
            format="json",
        )
        self.assertEqual(alta.status_code, 403)

    def test_configurador_sin_sensibles_no_crea_concepto_sensible(self):
        self.client.force_authenticate(self.admin_restringido)

        response = self.client.post(
            "/api/conceptos-gasto/",
            {
                "institucion": self.institucion.id,
                "codigo": "SUELDOS",
                "nombre": "Sueldos",
                "sensible": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ConceptoGasto.objects.filter(codigo="SUELDOS").exists())


class GastoApiTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.concepto = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="LIMPIEZA",
            nombre="Limpieza",
        )
        self.sensible = ConceptoGasto.objects.create(
            institucion=self.institucion,
            codigo="SUELDOS",
            nombre="Sueldos",
            sensible=True,
        )
        self.admin = Usuario.objects.create_user("admin-api-gastos@cauce.local", "x")
        self.delegado = Usuario.objects.create_user("delegado-api-gastos@cauce.local", "x")
        self.lector_restringido = Usuario.objects.create_user("lector-api-gastos@cauce.local", "x")

        membresia_admin = Membresia.objects.create(
            usuario=self.admin,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        for accion in (
            ConcesionFinanciera.Accion.VER_GASTOS,
            ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
            ConcesionFinanciera.Accion.APROBAR_GASTOS,
            ConcesionFinanciera.Accion.CORREGIR_GASTOS,
        ):
            ConcesionFinanciera.objects.create(
                membresia=membresia_admin,
                accion=accion,
                todas_las_areas=True,
                permite_sensibles=True,
            )

        membresia_delegado = Membresia.objects.create(
            usuario=self.delegado,
            institucion=self.institucion,
            rol=Membresia.Rol.MEDICO,
        )
        concesion_delegado = ConcesionFinanciera.objects.create(
            membresia=membresia_delegado,
            accion=ConcesionFinanciera.Accion.REGISTRAR_GASTOS,
        )
        concesion_delegado.areas.add(self.area)

        membresia_lector = Membresia.objects.create(
            usuario=self.lector_restringido,
            institucion=self.institucion,
            rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        ConcesionFinanciera.objects.create(
            membresia=membresia_lector,
            accion=ConcesionFinanciera.Accion.VER_GASTOS,
            todas_las_areas=True,
        )

    def carga(self, concepto=None, **overrides):
        datos = {
            "concepto": (concepto or self.concepto).id,
            "institucion": self.institucion.id,
            "area": self.area.id,
            "importe": "100.00",
            "periodo_economico": "2026-08-01",
        }
        datos.update(overrides)
        return datos

    def test_alta_de_area_nace_pendiente_y_aprobacion_es_idempotente(self):
        self.client.force_authenticate(self.delegado)
        alta = self.client.post("/api/gastos/", self.carga(estado="aprobado"), format="json")

        self.assertEqual(alta.status_code, 201)
        self.assertEqual(alta.data["origen"], Gasto.Origen.AREA)
        self.assertEqual(alta.data["estado"], Gasto.Estado.PENDIENTE_APROBACION)
        gasto_id = alta.data["id"]
        self.assertEqual(self.client.get(f"/api/gastos/{gasto_id}/").status_code, 403)

        self.client.force_authenticate(self.admin)
        primera = self.client.post(f"/api/gastos/{gasto_id}/aprobar/", {}, format="json")
        segunda = self.client.post(f"/api/gastos/{gasto_id}/aprobar/", {}, format="json")

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(primera.data["estado"], Gasto.Estado.APROBADO)
        self.assertEqual(primera.data["id"], segunda.data["id"])
        self.assertEqual(Gasto.objects.filter(pk=gasto_id).count(), 1)

    def test_alta_central_y_ajuste_no_crean_hechos_ni_cargos(self):
        self.client.force_authenticate(self.admin)
        alta = self.client.post("/api/gastos/", self.carga(), format="json")

        self.assertEqual(alta.status_code, 201)
        self.assertEqual(alta.data["origen"], Gasto.Origen.CENTRAL)
        self.assertEqual(alta.data["estado"], Gasto.Estado.APROBADO)
        ajuste = self.client.post(
            "/api/ajustes-gasto/",
            {"gasto": alta.data["id"], "importe": "-10.00", "motivo": "Descuento acordado"},
            format="json",
        )

        self.assertEqual(ajuste.status_code, 201)
        self.assertEqual(ajuste.data["importe"], "-10.00")
        self.assertEqual(HechoAtencionCosteable.objects.count(), 0)
        self.assertEqual(AjusteGasto.objects.count(), 1)

    def test_lectura_sensible_exige_concesion_expresa(self):
        self.client.force_authenticate(self.admin)
        alta = self.client.post("/api/gastos/", self.carga(self.sensible), format="json")
        self.assertEqual(alta.status_code, 201)

        self.client.force_authenticate(self.lector_restringido)
        listado = self.client.get("/api/gastos/")
        detalle = self.client.get(f"/api/gastos/{alta.data['id']}/")

        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["count"], 0)
        self.assertEqual(detalle.status_code, 404)
