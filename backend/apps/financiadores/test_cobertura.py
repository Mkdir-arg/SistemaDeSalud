"""Contratos de cobertura y cargos. SQLite no valida exclusión concurrente."""
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.finanzas.cobros import capturar_cobros_atencion, registrar_politica_cobro
from apps.finanzas.models import HechoAtencionCosteable, ObligacionFinanciera, Prestacion
from apps.finanzas.models_cobros import PendienteCobro, SnapshotCobroAtencion
from apps.finanzas.test_cobros import CobrosSetup
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

from .cobertura import cantidades_periodo, cotizacion, evaluar, liberar, periodo, reservar, seleccionar_afiliacion
from .cobros import completar_pendiente, resolver_saldo
from .models import (
    Afiliado, ArancelConvenio, ConfiguracionHospital, ConsumoExterno, Convenio,
    DistribucionCobro, EventoCobertura, Financiador, MembresiaFinanciador, Plan,
    PrestacionComun, ReglaCobertura, ReservaCobertura, ResolucionSaldo, VinculoPrestacion,
)
from .services import corregir_consumo, registrar_afiliado, registrar_consumo_externo


class CoberturaSetup(CobrosSetup):
    def setUp(self):
        super().setUp()
        self.hoy = timezone.localdate()
        self.paciente.documento = "00111222"
        self.paciente.save(update_fields=["documento"])
        ConfiguracionHospital.objects.create(institucion=self.institucion, activo=True)
        self.financiador = Financiador.objects.create(nombre="Obra social de prueba", tipo="obra_social")
        self.operador = Usuario.objects.create_user("operador@financiador.local", "x")
        self.membresia = MembresiaFinanciador.objects.create(
            financiador=self.financiador, usuario=self.operador, rol="operador",
        )
        self.plan = Plan.objects.create(financiador=self.financiador, codigo="BASE", nombre="Plan base")
        self.comun = PrestacionComun.objects.create(codigo="CONS", nombre="Consulta", categoria="consultas")
        VinculoPrestacion.objects.create(prestacion=self.prestacion, comun=self.comun)
        self.convenio = Convenio.objects.create(
            financiador=self.financiador, institucion=self.institucion,
            estado="activo", propuesto_por="plataforma", creado_por=self.admin,
        )
        self.afiliado = registrar_afiliado(
            financiador=self.financiador, usuario=self.operador, numero="00001",
            documento=self.paciente.documento, nombre="Ana Paz", plan=self.plan, desde=self.hoy,
        )
        self.regla = self.nueva_regla()
        self.politica()
        self.seleccion = seleccionar_afiliacion(
            caso=self.caso, usuario=self.admin, afiliado=self.afiliado, motivo="Afiliación verificada al ingreso",
        )

    def nueva_regla(self, **datos):
        valores = dict(financiador=self.financiador, plan=self.plan, prestacion=self.comun,
                       porcentaje=Decimal("80"), cupo=6, periodo="anio", vigente_desde=self.hoy,
                       creado_por=self.admin)
        valores.update(datos)
        return ReglaCobertura.objects.create(**valores)

    def evaluar(self, **datos):
        valores = dict(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        valores.update(datos)
        return evaluar(**valores)

    def reservar(self, *, acepta=False, usuario=None, **datos):
        valores = dict(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy, cantidad=1)
        valores.update(datos)
        presentada = cotizacion(**valores)
        return reservar(**valores, usuario=usuario or self.admin, clave=uuid4(),
                        firma=presentada["firma"], acepta=acepta)

    def externo(self, cantidad=1, **datos):
        valores = dict(financiador=self.financiador, usuario=self.operador, afiliado=self.afiliado,
                       prestacion=self.comun, fecha=self.hoy, cantidad=cantidad, referencia=str(uuid4()))
        valores.update(datos)
        return registrar_consumo_externo(**valores)

    def otro_hospital(self):
        hospital = Institucion.objects.create(nombre="Hospital vecino")
        area = Area.objects.create(institucion=hospital, nombre="Consultorios")
        flujo = Flujo.objects.create(institucion=hospital, area=area, titulo="Consultas")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        ciudadano = Ciudadano.objects.create(institucion=hospital, nombre="Ana", documento=self.paciente.documento)
        caso = Caso.objects.create(institucion=hospital, version=version, ciudadano=ciudadano, area_actual=area)
        prestacion = Prestacion.objects.create(institucion=hospital, nodo=nodo, codigo="CONS", nombre="Consulta")
        VinculoPrestacion.objects.create(prestacion=prestacion, comun=self.comun)
        ConfiguracionHospital.objects.create(institucion=hospital, activo=True)
        Convenio.objects.create(financiador=self.financiador, institucion=hospital, estado="activo",
                                propuesto_por="plataforma", creado_por=self.admin)
        registrar_politica_cobro(prestacion=prestacion, registrado_por=self.admin, cobrar=True, importe=Decimal("200"))
        seleccionar_afiliacion(caso=caso, usuario=self.admin, afiliado=self.afiliado, motivo="Ingreso en otro hospital")
        return caso, prestacion


class EvaluacionCoberturaTests(CoberturaSetup, TestCase):
    def test_cantidad_no_permite_confirmar_importe_mayor_a_la_precision_del_cargo(self):
        self.politica(importe=Decimal("999999999999.99"))
        dato = self.evaluar(cantidad=2)
        self.assertEqual(dato["estado"], "pendiente_evaluacion")
        self.assertIsNone(dato["importe_total"])
        with self.assertRaises(ValidationError):
            self.reservar(cantidad=2, acepta=True)
        self.assertFalse(ReservaCobertura.objects.exists())

    def test_consultar_no_reserva_y_arancel_general_se_reparte_sin_crear_deuda(self):
        for _ in range(2):
            dato = self.evaluar()
            self.assertEqual(dato["importe_total"], "100.00")
            self.assertEqual(dato["importe_financiador"], "80.00")
            self.assertEqual(dato["importe_paciente"], "20.00")
            self.assertEqual(dato["disponibles"], 6)
        self.assertFalse(ReservaCobertura.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_arancel_excepcional_y_retorno_al_general(self):
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion,
                                       importe=Decimal("150"), vigente_desde=self.hoy, creado_por=self.admin)
        self.assertEqual(self.evaluar()["importe_paciente"], "30.00")
        ArancelConvenio.objects.create(convenio=self.convenio, prestacion=self.prestacion,
                                       importe=None, vigente_desde=self.hoy, creado_por=self.admin)
        self.assertEqual(self.evaluar()["importe_paciente"], "20.00")

    def test_cupo_parcial_discrimina_unidades_y_total_del_paciente(self):
        self.externo(5)
        dato = self.evaluar(cantidad=3)
        self.assertEqual(dato["cubiertas"], 1)
        self.assertEqual(dato["importe_financiador"], "80.00")
        self.assertEqual(dato["importe_paciente"], "220.00")
        self.assertEqual(Decimal(dato["importe_total"]), Decimal(dato["importe_financiador"]) + Decimal(dato["importe_paciente"]))

    def test_exceso_es_no_cubierto_y_no_dispara_deuda(self):
        self.externo(6)
        dato = self.evaluar()
        self.assertEqual(dato["estado"], "no_cubierta")
        self.assertEqual(dato["importe_paciente"], "100.00")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_cupo_compartido_no_depende_del_arancel_del_hospital(self):
        self.externo(5)
        self.reservar()
        caso, prestacion = self.otro_hospital()
        dato = self.evaluar(caso=caso, prestacion=prestacion)
        self.assertEqual(dato["disponibles"], 0)
        self.assertEqual(dato["importe_paciente"], "200.00")

    def test_cambio_plan_conserva_cupo_y_no_reescribe_afiliacion_del_caso(self):
        self.externo(4)
        nuevo = Plan.objects.create(financiador=self.financiador, codigo="PLUS", nombre="Plus")
        self.nueva_regla(plan=nuevo, cupo=10)
        actualizado = registrar_afiliado(financiador=self.financiador, usuario=self.operador,
                                         numero="00002", documento=self.paciente.documento,
                                         nombre="Ana Paz", plan=nuevo, desde=self.hoy)
        self.assertEqual(actualizado.pk, self.afiliado.pk)
        self.assertEqual(self.evaluar()["disponibles"], 2)
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin, afiliado=actualizado, motivo="Corrección expresa al plan vigente")
        self.assertEqual(self.evaluar()["disponibles"], 6)
        self.seleccion.refresh_from_db()
        self.assertEqual(self.seleccion.plan_id, self.plan.pk)

    def test_otro_financiador_tiene_cupo_independiente_y_el_anterior_lo_conserva(self):
        self.externo(4)
        otro = Financiador.objects.create(nombre="Mutual", tipo="mutual")
        plan = Plan.objects.create(financiador=otro, codigo="BASE", nombre="Base")
        afiliado = registrar_afiliado(financiador=otro, usuario=self.admin, numero="00001",
                                     documento=self.paciente.documento, nombre="Ana Paz", plan=plan, desde=self.hoy)
        self.nueva_regla(financiador=otro, plan=plan, cupo=10)
        Convenio.objects.create(financiador=otro, institucion=self.institucion, estado="activo",
                                propuesto_por="plataforma", creado_por=self.admin)
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin, afiliado=afiliado, motivo="Nueva cobertura")
        self.assertEqual(self.evaluar()["disponibles"], 10)
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin, afiliado=self.afiliado, motivo="Regreso a cobertura anterior")
        self.assertEqual(self.evaluar()["disponibles"], 2)

    def test_regla_especifica_prevalece_sobre_default_mas_reciente(self):
        self.nueva_regla(plan=None, porcentaje=Decimal("100"), cupo=20)
        self.assertEqual(self.evaluar()["importe_paciente"], "20.00")

    def test_periodos_calendario_y_consumo_externo_del_anio_anterior(self):
        self.assertEqual(periodo(date(2024, 2, 29), "mes"), (date(2024, 2, 1), date(2024, 3, 1)))
        self.assertEqual(periodo(date(2026, 12, 31), "anio"), (date(2026, 1, 1), date(2027, 1, 1)))
        self.externo(6, fecha=date(self.hoy.year - 1, 12, 31))
        self.assertEqual(self.evaluar()["disponibles"], 6)

    def test_no_cobrar_no_inventa_cargos_pero_si_cuenta_cobertura(self):
        self.politica(cobrar=False)
        reserva = self.reservar()
        self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.cubiertas, 1)
        self.assertEqual(reserva.distribucion.estado, "sin_cobro")
        self.assertFalse(ObligacionFinanciera.objects.exists())
        self.assertEqual(self.evaluar()["disponibles"], 5)

    def test_arancel_pendiente_no_se_convierte_en_deuda_cero_o_privada(self):
        self.politica(importe=None)
        self.assertEqual(self.evaluar()["estado"], "arancel_pendiente")
        hecho = self.atencion()
        self.assertTrue(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.assertEqual(DistribucionCobro.objects.get().estado, "arancel_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_afiliacion_pendiente_no_crea_deuda_al_paciente(self):
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin, declaracion="Credencial pendiente", motivo="Verificación necesaria")
        self.assertEqual(self.evaluar()["estado"], "pendiente_evaluacion")
        self.atencion()
        self.assertEqual(DistribucionCobro.objects.get().estado, "evaluacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())


class ReservasYCargosTests(CoberturaSetup, TestCase):
    def test_hospital_activado_sin_afiliacion_no_cae_al_generador_legado(self):
        self.caso = Caso.objects.create(institucion=self.institucion, version=self.nodo.version,
                                       ciudadano=self.paciente, area_actual=self.area)
        hecho = self.atencion()
        self.assertTrue(hecho.cobertura_contexto)
        self.assertFalse(PendienteCobro.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_arancel_excesivo_sobre_reserva_no_revierte_atencion_ni_emite_deuda(self):
        reserva = self.reservar(cantidad=2, acepta=True)
        self.politica(importe=Decimal("999999999999.99"))
        hecho = self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.hecho_id, hecho.pk)
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.distribucion.estado, "evaluacion_pendiente")
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_reintento_reserva_no_duplica_cupo_y_clave_conflictiva_se_rechaza(self):
        dato = cotizacion(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        argumentos = dict(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy, cantidad=1,
                          usuario=self.admin, firma=dato["firma"], acepta=True, clave=uuid4())
        original = reservar(**argumentos)
        self.assertEqual(reservar(**argumentos).pk, original.pk)
        self.assertEqual(self.evaluar()["disponibles"], 5)
        argumentos["cantidad"] = 2
        with self.assertRaises(ValidationError):
            reservar(**argumentos)
        self.assertEqual(ReservaCobertura.objects.count(), 1)

    def test_dos_cotizaciones_del_ultimo_cupo_no_producen_dos_reservas_cubiertas(self):
        self.externo(5)
        caso, prestacion = self.otro_hospital()
        anterior = cotizacion(caso=caso, prestacion=prestacion, fecha=self.hoy)
        self.reservar()
        with self.assertRaisesMessage(ValidationError, "cambió"):
            reservar(caso=caso, prestacion=prestacion, usuario=self.admin, fecha=self.hoy,
                     cantidad=1, clave=uuid4(), firma=anterior["firma"])
        self.assertEqual(ReservaCobertura.objects.filter(cubiertas=1).count(), 1)

    def test_cotizacion_desactualizada_no_acepta_un_importe_distinto(self):
        dato = cotizacion(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        self.politica(importe=Decimal("200"))
        with self.assertRaisesMessage(ValidationError, "cambió"):
            reservar(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy, cantidad=1,
                     usuario=self.admin, firma=dato["firma"], acepta=True, clave=uuid4())
        self.assertFalse(ReservaCobertura.objects.exists())

    def test_aceptacion_por_prestacion_e_importe_y_captura_idempotente(self):
        reserva = self.reservar(acepta=True)
        hecho = self.atencion()
        capturar_cobros_atencion(hecho.pk)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.aceptacion["prestacion"], self.prestacion.pk)
        distribucion = reserva.distribucion
        self.assertEqual(distribucion.estado, "resuelta")
        self.assertEqual(distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertEqual(distribucion.obligacion_financiador.importe_original, Decimal("80"))
        self.assertEqual(ObligacionFinanciera.objects.filter(hecho=hecho).count(), 2)
        self.assertFalse(PendienteCobro.objects.filter(hecho=hecho).exists())

    def test_sin_aceptacion_solo_financiador_tiene_deuda_y_resto_queda_pendiente(self):
        reserva = self.reservar()
        self.atencion()
        distribucion = reserva.distribucion
        self.assertEqual(distribucion.estado, "pendiente")
        self.assertIsNone(distribucion.obligacion_paciente_id)
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)

    def test_consumo_externo_tardio_preserva_reserva_y_aceptacion(self):
        self.externo(5)
        reserva = self.reservar(acepta=True)
        evaluacion, aceptacion = reserva.evaluacion.copy(), reserva.aceptacion.copy()
        self.externo(1)
        reserva.refresh_from_db()
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(reserva.evaluacion, evaluacion)
        self.assertEqual(reserva.aceptacion, aceptacion)
        self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.cubiertas, 1)
        self.assertEqual(reserva.distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertEqual(self.evaluar()["cubiertas"], 0)

    def test_consumo_tardio_no_modifica_cargos_ya_registrados(self):
        reserva = self.reservar(acepta=True)
        self.atencion()
        original = list(ObligacionFinanciera.objects.values_list("pk", "importe_original"))
        self.externo(6)
        reserva.refresh_from_db()
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(list(ObligacionFinanciera.objects.values_list("pk", "importe_original")), original)

    def test_cambio_de_arancel_antes_de_realizar_invalida_aceptacion_previa(self):
        reserva = self.reservar(acepta=True)
        self.politica(importe=Decimal("200"))
        self.atencion()
        reserva.refresh_from_db()
        self.assertEqual(reserva.aceptacion, {})
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(reserva.distribucion.importe_paciente, Decimal("40"))
        self.assertIsNone(reserva.distribucion.obligacion_paciente_id)

    def test_cambiar_afiliacion_exige_revisar_reserva_abierta(self):
        reserva = self.reservar(acepta=True)
        with self.assertRaises(ValidationError):
            seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                                   particular=True, motivo="La cobertura no corresponde")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "reservada")
        self.assertEqual(reserva.afiliacion_id, self.seleccion.pk)
        liberar(reserva=reserva, usuario=self.admin, motivo="Todavía no se realizó; revisar cobertura", no_realizada=True)
        corregida = seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                                           particular=True, motivo="Atención particular acordada")
        self.assertEqual(corregida.estado, "particular")
        self.assertEqual(self.evaluar()["importe_paciente"], "100.00")

    def test_reserva_antigua_no_expira_y_liberacion_exige_confirmacion(self):
        reserva = self.reservar()
        ReservaCobertura.objects.filter(pk=reserva.pk).update(creado=timezone.now() - timedelta(days=30))
        self.assertEqual(self.evaluar()["disponibles"], 5)
        with self.assertRaises(ValidationError):
            liberar(reserva=reserva, usuario=self.admin, motivo="Revisión", no_realizada=False)
        liberar(reserva=reserva, usuario=self.admin, motivo="El equipo confirmó que no se realizó", no_realizada=True)
        self.assertEqual(self.evaluar()["disponibles"], 6)
        self.assertTrue(EventoCobertura.objects.filter(accion="liberar_reserva", usuario=self.admin).exists())

    def test_no_se_libera_reserva_si_existe_hecho_aunque_falle_captura_financiera(self):
        reserva = self.reservar()
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.assertTrue(HechoAtencionCosteable.objects.filter(pk=hecho.pk).exists())
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        with self.assertRaises(ValidationError):
            liberar(reserva=reserva, usuario=self.admin, motivo="No realizada", no_realizada=True)
        self.assertEqual(self.evaluar()["disponibles"], 5)

    def test_fallo_al_obtener_contexto_no_revierte_hecho_ni_cae_en_cobro_legado(self):
        self.reservar()
        with patch("apps.financiadores.cobros.contexto_cobertura", side_effect=RuntimeError("fallo de captura")):
            hecho = self.atencion()
        self.assertTrue(HechoAtencionCosteable.objects.filter(pk=hecho.pk).exists())
        self.assertFalse(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.assertFalse(PendienteCobro.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_recuperacion_conserva_circuito_y_arancel_del_hecho(self):
        reserva = self.reservar(acepta=True)
        with patch("apps.financiadores.cobros.capturar_cobertura", side_effect=RuntimeError("fallo simulado")):
            hecho = self.atencion()
        self.politica(importe=Decimal("500"))
        ConfiguracionHospital.objects.filter(institucion=self.institucion).update(activo=False)
        capturar_cobros_atencion(hecho.pk)
        reserva.refresh_from_db()
        self.assertEqual(reserva.distribucion.obligacion_paciente.importe_original, Decimal("20"))
        self.assertTrue(SnapshotCobroAtencion.objects.get(hecho=hecho).capturado)
        self.assertFalse(PendienteCobro.objects.exists())

    def test_rechazo_y_asuncion_del_hospital_conservan_historia_sin_deuda_ficticia(self):
        reserva = self.reservar()
        self.atencion()
        reserva.refresh_from_db()
        resolver_saldo(reserva=reserva, usuario=self.admin, decision="rechazar", importe=Decimal("20"), motivo="Requiere revisión", clave=uuid4())
        self.assertEqual(reserva.distribucion.estado, "pendiente")
        resolver_saldo(reserva=reserva, usuario=self.admin, decision="asumir", importe=Decimal("20"), motivo="Hospital asume el saldo", clave=uuid4())
        self.assertEqual(DistribucionCobro.objects.get(reserva=reserva).estado, "resuelta")
        self.assertEqual(ResolucionSaldo.objects.count(), 2)
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)

    def test_acuerdo_posterior_exige_evidencia_y_saldo_completo(self):
        reserva = self.reservar()
        self.atencion()
        reserva.refresh_from_db()
        valores = dict(reserva=reserva, usuario=self.admin, decision="paciente", motivo="Acuerdo expreso", clave=uuid4())
        with self.assertRaises(ValidationError):
            resolver_saldo(**valores, importe=Decimal("20"))
        with self.assertRaises(ValidationError):
            resolver_saldo(**valores, importe=Decimal("10"), evidencia="Acta para esta prestación")
        resolucion = resolver_saldo(**valores, importe=Decimal("20"), evidencia="Acta firmada: consulta, $20")
        repetida = resolver_saldo(**valores, importe=Decimal("20"), evidencia="Acta firmada: consulta, $20")
        self.assertEqual(repetida.pk, resolucion.pk)
        self.assertEqual(ObligacionFinanciera.objects.count(), 2)


class PadronYPermisosTests(CoberturaSetup, TestCase):
    def test_rol_de_lectura_no_amplia_areas_del_rol_clinico(self):
        medico = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="medico")
        medico.areas.add(self.area)
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="reportes")
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Área ajena")
        self.caso.area_actual = otra_area
        self.caso.save(update_fields=["area_actual"])
        with self.assertRaises(PermissionDenied):
            seleccionar_afiliacion(caso=self.caso, usuario=self.usuario,
                                   afiliado=self.afiliado, motivo="No debe operar otra área")

    def test_numero_familiar_no_identifica_a_dos_personas_como_una(self):
        segundo = registrar_afiliado(financiador=self.financiador, usuario=self.operador, numero="00001",
                                     documento="00111333", nombre="Otra persona", plan=self.plan, desde=self.hoy)
        self.assertNotEqual(segundo.pk, self.afiliado.pk)
        self.assertEqual(Afiliado.objects.count(), 2)

    def test_formato_documento_no_crea_segunda_identidad_o_cupo(self):
        actualizado = registrar_afiliado(financiador=self.financiador, usuario=self.operador, numero="00001",
                                         documento="00.111.222", nombre="Ana Paz", plan=self.plan, desde=self.hoy)
        self.assertEqual(actualizado.pk, self.afiliado.pk)
        self.assertEqual(Afiliado.objects.count(), 1)

    def test_auditor_del_financiador_no_modifica_padron_ni_consumo(self):
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        with self.assertRaises(PermissionDenied):
            self.externo()
        with self.assertRaises(PermissionDenied):
            registrar_afiliado(financiador=self.financiador, usuario=self.operador, numero="123",
                              documento="123", nombre="Otra", plan=self.plan, desde=self.hoy)
        self.assertFalse(ConsumoExterno.objects.exists())

    def test_membresia_revocada_no_permite_nuevos_consumos(self):
        self.membresia.activo = False
        self.membresia.save(update_fields=["activo"])
        with self.assertRaises(PermissionDenied):
            self.externo()

    def test_financiador_no_opera_caso_del_hospital(self):
        with self.assertRaises(PermissionDenied):
            seleccionar_afiliacion(caso=self.caso, usuario=self.operador, afiliado=self.afiliado, motivo="Intento ajeno")
        with self.assertRaises(PermissionDenied):
            self.reservar(usuario=self.operador)

    def test_referencia_idempotente_y_conflicto_con_otro_contenido(self):
        original = self.externo(referencia="RX-001")
        repetido = self.externo(referencia="RX-001")
        self.assertEqual(original.pk, repetido.pk)
        with self.assertRaises(ValidationError):
            self.externo(2, referencia="RX-001")
        self.assertEqual(ConsumoExterno.objects.count(), 1)

    def test_posible_duplicado_sin_referencia_requiere_motivo(self):
        self.externo(referencia="")
        with self.assertRaisesMessage(ValidationError, "Posible duplicado"):
            self.externo(referencia="")
        self.externo(referencia="", motivo_duplicado="Dos consultas realizadas ese día")
        self.assertEqual(self.evaluar()["disponibles"], 4)

    def test_correccion_externa_preserva_original_y_restituye_solo_su_cupo(self):
        original = self.externo(5)
        correccion = corregir_consumo(consumo=original, usuario=self.operador, cantidad=2, motivo="Se duplicaron tres unidades")
        original.refresh_from_db()
        self.assertEqual(original.cantidad, 5)
        self.assertEqual(correccion.cantidad, -3)
        self.assertEqual(correccion.corrige_id, original.pk)
        self.assertEqual(self.evaluar()["disponibles"], 4)
        self.assertFalse(HechoAtencionCosteable.objects.exists())
        self.assertFalse(ObligacionFinanciera.objects.exists())

    def test_aceptacion_requiere_permiso_explicito_y_area_correcta(self):
        # Rol sin herencia financiera: lo que se exige acá es el permiso
        # explícito, y el admin de institución hereda las dieciocho acciones.
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        with self.assertRaises(PermissionDenied):
            self.reservar(usuario=self.usuario, acepta=True)
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Otra área")
        concesion = self.conceder("registrar_aceptacion", area=otra_area)
        with self.assertRaises(PermissionDenied):
            self.reservar(usuario=self.usuario, acepta=True)
        concesion.areas.add(self.area)
        self.assertEqual(self.reservar(usuario=self.usuario, acepta=True).aceptacion["usuario"], self.usuario.pk)

    def test_finanzas_no_certifica_no_realizacion_por_su_solo_permiso(self):
        reserva = self.reservar()
        self.conceder("resolver_cobertura", area=self.area)
        with self.assertRaises(PermissionDenied):
            liberar(reserva=reserva, usuario=self.usuario, motivo="Revisión financiera", no_realizada=True)
        membresia = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="medico")
        membresia.areas.add(self.area)
        self.assertEqual(liberar(reserva=reserva, usuario=self.usuario, motivo="Constatación del área", no_realizada=True).estado, "liberada")

    def test_resolucion_necesita_concesion_y_deja_actor_fecha_y_motivo(self):
        reserva = self.reservar()
        self.atencion()
        reserva.refresh_from_db()
        valores = dict(reserva=reserva, usuario=self.usuario, decision="asumir", importe=Decimal("20"), motivo="Excepción autorizada", clave=uuid4())
        with self.assertRaises(PermissionDenied):
            resolver_saldo(**valores)
        self.conceder("resolver_cobertura", area=self.area)
        resolucion = resolver_saldo(**valores)
        self.assertEqual(resolucion.registrado_por_id, self.usuario.pk)
        self.assertIsNotNone(resolucion.creado)
        self.assertEqual(resolucion.motivo, "Excepción autorizada")


class CompletarPendientesTests(CoberturaSetup, TestCase):
    def pendiente_arancel(self):
        self.politica(importe=None)
        hecho = self.atencion()
        return ReservaCobertura.objects.get(hecho=hecho)

    def test_completar_arancel_exige_ambos_permisos_y_conserva_evaluacion_original(self):
        reserva = self.pendiente_arancel()
        original = reserva.evaluacion.copy()
        valores = dict(reserva=reserva, usuario=self.usuario, motivo="Arancel acordado comprobado", arancel=Decimal("100"))
        with self.assertRaises(PermissionDenied):
            completar_pendiente(**valores)
        self.conceder("resolver_cobertura", area=self.area)
        with self.assertRaises(PermissionDenied):
            completar_pendiente(**valores)
        self.conceder("configurar_cobros")
        distribucion = completar_pendiente(**valores)
        reserva.refresh_from_db()
        self.assertEqual(reserva.evaluacion["evaluacion_original"], original)
        self.assertEqual(reserva.evaluacion["revision"]["usuario"], self.usuario.pk)
        self.assertEqual(distribucion.obligacion_financiador.importe_original, Decimal("80"))
        self.assertEqual(distribucion.importe_paciente, Decimal("20"))
        self.assertEqual(distribucion.estado, "pendiente")
        self.assertIsNone(distribucion.obligacion_paciente_id)

    def test_completar_no_aplica_regla_creada_despues_del_hecho(self):
        reserva = self.pendiente_arancel()
        self.nueva_regla(porcentaje=Decimal("100"))
        distribucion = completar_pendiente(reserva=reserva, usuario=self.admin,
                                           motivo="Arancel previamente omitido", arancel=Decimal("100"))
        self.assertEqual(distribucion.importe_financiador, Decimal("80"))
        self.assertEqual(distribucion.importe_paciente, Decimal("20"))

    def test_repetir_completado_se_rechaza_sin_duplicar_obligaciones(self):
        reserva = self.pendiente_arancel()
        valores = dict(reserva=reserva, usuario=self.admin, motivo="Arancel comprobado", arancel=Decimal("100"))
        completar_pendiente(**valores)
        with self.assertRaises(ValidationError):
            completar_pendiente(**valores)
        self.assertEqual(ObligacionFinanciera.objects.count(), 1)

    def test_correccion_historica_de_afiliacion_no_cambia_la_actual_del_caso(self):
        seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                               declaracion="Credencial por verificar", motivo="Ingreso sin padrón confirmado")
        hecho = self.atencion()
        reserva = ReservaCobertura.objects.get(hecho=hecho)
        actual = seleccionar_afiliacion(caso=self.caso, usuario=self.admin,
                                       particular=True, motivo="Las próximas prestaciones serán particulares")
        distribucion = completar_pendiente(reserva=reserva, usuario=self.admin,
                                           motivo="Credencial de la prestación anterior comprobada", afiliado=self.afiliado)
        reserva.refresh_from_db()
        self.assertEqual(reserva.afiliacion.hecho_revision_id, hecho.pk)
        self.assertEqual(self.evaluar()["afiliacion"], actual.pk)
        self.assertEqual(self.evaluar()["importe_paciente"], "100.00")
        self.assertEqual(distribucion.importe_financiador, Decimal("80"))
        self.assertIsNone(distribucion.obligacion_paciente_id)

    def test_completar_arancel_preserva_cobertura_registrada_ante_consumo_tardio(self):
        reserva = self.pendiente_arancel()
        self.assertEqual(reserva.cubiertas, 1)
        self.externo(6)
        distribucion = completar_pendiente(reserva=reserva, usuario=self.admin,
                                           motivo="Arancel original comprobado", arancel=Decimal("100"))
        reserva.refresh_from_db()
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(reserva.cubiertas, 1)
        self.assertEqual(distribucion.importe_financiador, Decimal("80"))
        self.assertEqual(distribucion.importe_paciente, Decimal("20"))


@skipUnless(connection.vendor == "postgresql", "La exclusión concurrente requiere PostgreSQL.")
class CoberturaConcurrenciaTests(CoberturaSetup, TransactionTestCase):
    """Conexiones independientes, transacciones y bloqueos reales; sin mocks."""

    def paralelo(self, *operaciones):
        barrera = Barrier(len(operaciones))

        def ejecutar(operacion):
            close_old_connections()
            try:
                barrera.wait(timeout=10)
                return operacion()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(operaciones)) as pool:
            futuros = [pool.submit(ejecutar, operacion) for operacion in operaciones]
            return [futuro.result(timeout=30) for futuro in futuros]

    def confirmar(self, caso, prestacion, firma):
        try:
            reserva = reservar(caso=caso, prestacion=prestacion, usuario=self.admin,
                               fecha=self.hoy, cantidad=1, clave=uuid4(), firma=firma, acepta=True)
        except ValidationError as error:
            if getattr(error, "code", None) != "evaluacion_cambio":
                raise
            return "cambio", None
        return "reservada", reserva.pk

    def test_dos_hospitales_compiten_por_la_ultima_unidad(self):
        self.externo(5)
        otro_caso, otra_prestacion = self.otro_hospital()
        primera = cotizacion(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        segunda = cotizacion(caso=otro_caso, prestacion=otra_prestacion, fecha=self.hoy)
        resultados = self.paralelo(
            lambda: self.confirmar(self.caso, self.prestacion, primera["firma"]),
            lambda: self.confirmar(otro_caso, otra_prestacion, segunda["firma"]),
        )
        self.assertCountEqual([estado for estado, _ in resultados], ["reservada", "cambio"])
        self.assertEqual(ReservaCobertura.objects.filter(estado="reservada", cubiertas=1).count(), 1)
        inicio, fin = periodo(self.hoy, "anio")
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, inicio, fin), 6)

    def test_consumo_externo_compite_con_confirmacion_sin_revocar_compromiso(self):
        self.externo(5)
        presentada = cotizacion(caso=self.caso, prestacion=self.prestacion, fecha=self.hoy)
        resultado, consumo_id = self.paralelo(
            lambda: self.confirmar(self.caso, self.prestacion, presentada["firma"]),
            lambda: self.externo(referencia="concurrente").pk,
        )
        self.assertTrue(ConsumoExterno.objects.filter(pk=consumo_id).exists())
        self.assertEqual(self.evaluar()["disponibles"], 0)
        if resultado[0] == "reservada":
            reserva = ReservaCobertura.objects.get(pk=resultado[1])
            self.assertTrue(reserva.discrepancia)
            self.assertEqual(reserva.cubiertas, 1)
            self.assertEqual(reserva.aceptacion["importe"], "20.00")
        else:
            self.assertEqual(resultado[0], "cambio")
            self.assertFalse(ReservaCobertura.objects.exists())

    def test_realizacion_y_consumo_externo_simultaneos_no_duplican_consumo_reservado(self):
        self.externo(5)
        reserva = self.reservar(acepta=True)
        hecho_id, consumo_id = self.paralelo(
            lambda: self.atencion().pk,
            lambda: self.externo(referencia="durante-atencion").pk,
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "realizada")
        self.assertEqual(reserva.hecho_id, hecho_id)
        self.assertTrue(reserva.discrepancia)
        self.assertEqual(reserva.cubiertas, 1)
        self.assertTrue(ConsumoExterno.objects.filter(pk=consumo_id).exists())
        inicio, fin = periodo(self.hoy, "anio")
        self.assertEqual(cantidades_periodo(self.afiliado, self.comun, inicio, fin), 7)
        self.assertEqual(ObligacionFinanciera.objects.filter(hecho_id=hecho_id).count(), 2)
