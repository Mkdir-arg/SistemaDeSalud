from decimal import Decimal
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .models import AjusteCosto, ComponenteEsperadoHecho, ConcesionFinanciera, DefinicionComponente, HechoAtencionCosteable, ImputacionCosto, PendienteCosteo, Prestacion, ValorComponente
from .permisos import tiene_concesion_financiera
from .services import intentar_costeo_directo, procesar_hecho_atencion, registrar_ajuste_costo, registrar_atencion_completada


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

    def test_el_comando_rechaza_un_lote_no_positivo(self):
        with self.assertRaisesMessage(CommandError, "--limite debe ser mayor que cero"):
            call_command("procesar_costos", "--limite", "0")

    def test_el_comando_registra_el_error_recuperable_del_hecho(self):
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
        prestacion = Prestacion.objects.create(institucion=self.institucion, nodo=self.nodo, codigo="CONS", nombre="Consulta")
        componente = DefinicionComponente.objects.create(prestacion=prestacion, codigo="BASE", nombre="Costo directo")
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
        PendienteCosteo.objects.create(hecho=hecho, motivo=PendienteCosteo.Motivo.SIN_PRESTACION)
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

    def test_sin_concesion_no_expone_costos_del_paciente(self):
        self.client.force_authenticate(self.usuario)
        response = self.client.get("/api/hechos-costo/")
        self.assertEqual(response.status_code, 403)

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
        self.assertFalse(fila["total_es_completo"])
        self.assertEqual(fila["estado_costo"], "pendiente")
        self.assertEqual(fila["faltantes"][0]["motivo"], PendienteCosteo.Motivo.SIN_PRESTACION)

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
        procesar_hecho_atencion(self.hecho.id)
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
            ImputacionCosto.objects.get(hecho=self.hecho, componente=componente),
            Decimal("-50.00"),
            "Corrección de importe",
            self.usuario,
        )
        self.client.force_authenticate(self.usuario)
        response = self.client.get(f"/api/hechos-costo/{self.hecho.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_conocido"], "1200.50")
        self.assertTrue(response.data["total_es_completo"])
        self.assertEqual(response.data["estado_costo"], "disponible")
        self.assertEqual(response.data["faltantes"], [])
        self.assertEqual(response.data["imputaciones"][0]["ajustes"][0]["importe"], "-50.00")


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
        componente = DefinicionComponente.objects.get(prestacion=prestacion, codigo="BASE")
        self.assertEqual(
            self.client.patch(
                f"/api/componentes-costo/{componente.id}/",
                {"codigo": "OTRO"},
                format="json",
            ).status_code,
            405,
        )

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
        valor = ValorComponente.objects.get(componente=componente)
        self.assertEqual(valor.registrado_por, self.admin)
        self.assertEqual(
            self.client.patch(
                f"/api/valores-componentes/{valor.id}/",
                {"importe": "1300.00"},
                format="json",
            ).status_code,
            405,
        )

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
