"""Ensayo opt-in con PostgreSQL local dedicado y datos ficticios.

Ejecutar explícitamente con ``manage.py test apps.financiadores.validacion_volumen
--settings=cauce.settings_financiadores_postgres_test --noinput``. El nombre evita
agregar esta carga a la suite habitual. ``bulk_create`` arma fuentes coherentes
para medir lectura y auditoría; este ensayo NO valida el circuito de creación
clínica. Los tiempos son observaciones locales, no un SLA ni una prueba de carga
con usuarios concurrentes. No se imprimen personas ni sentencias SQL.

Para comparar antes/después ejecutar únicamente el método
``ExportacionVolumenTests.test_medicion_auditoria_por_fases`` en una base
recreada por el runner. Ejecutarlo después del otro ensayo cambia las
condiciones iniciales y no sirve como comparación equivalente.
"""
import csv
import json
from collections import Counter
from contextlib import ExitStack
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from statistics import median, pstdev
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import (
    AccesoFinanciero, AjusteObligacion, HechoAtencionCosteable,
    MovimientoDinero, ObligacionFinanciera,
)
from apps.finanzas.models_cobros import SnapshotCobroAtencion
from apps.registros.models import Ciudadano

from .models import Afiliado, AfiliacionCaso, DistribucionCobro, EventoCobertura, ReservaCobertura
from . import actividad
from .seguimiento_csv import DINERO
from .test_cobertura import CoberturaSetup


class ExportacionVolumenTests(CoberturaSetup, APITestCase):
    """Mide ambos CSV reales con sus permisos, cálculos y escrituras de auditoría."""

    cantidad = 5000

    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql", "Este ensayo requiere PostgreSQL local dedicado.")
        super().setUp()
        self.conceder("ver_dinero")
        self.regla.porcentaje = Decimal("100")
        self.regla.save(update_fields=["porcentaje"])
        inicio = perf_counter()
        self.crear_fuentes()
        print(json.dumps({
            "ensayo": "preparacion_ficticia", "personas": self.cantidad + 1,
            "cuentas": self.cantidad + 1, "segundos": round(perf_counter() - inicio, 3),
        }), flush=True)

    def crear_fuentes(self):
        n = self.cantidad + 1
        fechas = [self.hoy] * self.cantidad + [self.hoy - timedelta(days=1)]
        ciudadanos = Ciudadano.objects.bulk_create([
            Ciudadano(institucion=self.institucion, nombre="Persona ficticia",
                      apellido=str(i), documento=str(90000000 + i))
            for i in range(n)
        ], batch_size=500)
        afiliados = Afiliado.objects.bulk_create([
            Afiliado(financiador=self.financiador, numero=f"VOL-{i:05}",
                     documento=persona.documento, nombre=f"Persona ficticia {i}",
                     plan=self.plan, desde=self.hoy - timedelta(days=1))
            for i, persona in enumerate(ciudadanos)
        ], batch_size=500)
        casos = Caso.objects.bulk_create([
            Caso(institucion=self.institucion, version=self.caso.version,
                 ciudadano=persona, area_actual=self.area, estado="atendido")
            for persona in ciudadanos
        ], batch_size=500)
        afiliaciones = AfiliacionCaso.objects.bulk_create([
            AfiliacionCaso(caso=caso, afiliado=afiliado, plan=self.plan,
                           estado="verificada", motivo="Fixture de volumen",
                           registrado_por=self.admin)
            for caso, afiliado in zip(casos, afiliados)
        ], batch_size=500)
        eventos = EventoCaso.objects.bulk_create([
            EventoCaso(caso=caso, nodo=self.nodo, autor=self.usuario,
                       titulo="Atención ficticia del ensayo de volumen")
            for caso in casos
        ], batch_size=500)
        hechos = HechoAtencionCosteable.objects.bulk_create([
            HechoAtencionCosteable(
                institucion=self.institucion, evento=evento, evento_origen_id=evento.pk,
                caso=caso, caso_origen_id=caso.pk, ciudadano=persona,
                ciudadano_origen_id=persona.pk, nodo=self.nodo, nodo_origen_id=self.nodo.pk,
                area=self.area, area_origen_id=self.area.pk, autor=self.usuario,
                ocurrida_en=timezone.make_aware(datetime.combine(fecha, time(12))),
            )
            for evento, caso, persona, fecha in zip(eventos, casos, ciudadanos, fechas)
        ], batch_size=500)
        SnapshotCobroAtencion.objects.bulk_create([
            SnapshotCobroAtencion(hecho=hecho, capturado=True) for hecho in hechos
        ], batch_size=500)
        reservas = ReservaCobertura.objects.bulk_create([
            ReservaCobertura(
                caso=caso, afiliacion=afiliacion, afiliado=afiliado, prestacion=self.prestacion,
                comun=self.comun, fecha=fecha, cantidad=1, cubiertas=1, estado="realizada",
                evaluacion={"importe_total": "100.00", "importe_financiador": "100.00",
                            "importe_paciente": "0.00", "sensible": False},
                hecho=hecho, creado_por=self.usuario, cerrado_por=self.usuario,
                cerrado_en=hecho.ocurrida_en,
            )
            for caso, afiliacion, afiliado, hecho, fecha in zip(casos, afiliaciones, afiliados, hechos, fechas)
        ], batch_size=500)
        obligaciones = ObligacionFinanciera.objects.bulk_create([
            ObligacionFinanciera(
                tipo="cobrar", hecho=hecho, institucion=self.institucion, area=self.area,
                importe_original=Decimal("100.00"), periodo_economico=fecha.replace(day=1),
                contraparte_nombre=self.financiador.nombre,
                contraparte_referencia=f"financiador:{self.financiador.pk}",
                clave=uuid4(), creado_por=self.admin,
            )
            for hecho, fecha in zip(hechos, fechas)
        ], batch_size=500)
        DistribucionCobro.objects.bulk_create([
            DistribucionCobro(reserva=reserva, importe_financiador=Decimal("100.00"),
                              importe_paciente=0, estado="resuelta", obligacion_financiador=obligacion)
            for reserva, obligacion in zip(reservas, obligaciones)
        ], batch_size=500)
        cobros = self.crear_movimientos(obligaciones, "30.25")
        self.crear_movimientos(obligaciones, "10.10")
        self.crear_movimientos(obligaciones, "2.05", originales=cobros)
        self.crear_movimientos(obligaciones, "3.45", estado="pendiente_aprobacion")
        self.crear_movimientos(obligaciones, "1.20", originales=cobros, estado="pendiente_aprobacion")
        AjusteObligacion.objects.bulk_create([
            AjusteObligacion(
                obligacion=obligacion, institucion=self.institucion, importe=Decimal(importe),
                motivo="Ajuste ficticio", clave=uuid4(), autor=self.admin, estado=estado,
                aprobado_por=self.admin if estado == "aprobado" else None,
                aprobado_en=timezone.now() if estado == "aprobado" else None,
            )
            for obligacion in obligaciones
            for importe, estado in (("-5.15", "aprobado"), ("-2.30", "pendiente_aprobacion"))
        ], batch_size=500)

    def crear_movimientos(self, obligaciones, importe, *, originales=None, estado="aprobado"):
        return MovimientoDinero.objects.bulk_create([
            MovimientoDinero(
                obligacion=obligacion, institucion=self.institucion,
                tipo="reintegro" if originales else "cobro",
                original=originales[i] if originales else None,
                importe=Decimal(importe), fecha=self.hoy, referencia="VOLUMEN-FICTICIO",
                motivo="Ensayo ficticio", clave=uuid4(), autor=self.admin, estado=estado,
                aprobado_por=self.admin if estado == "aprobado" else None,
                aprobado_en=timezone.now() if estado == "aprobado" else None,
            )
            for i, obligacion in enumerate(obligaciones)
        ], batch_size=500)

    def medir(self, nombre, url, parametros):
        sentencias = Counter()

        def contar(ejecutar, sql, params, many, context):
            sentencias[sql.lstrip().split(None, 1)[0].upper()] += 1
            return ejecutar(sql, params, many, context)

        inicio = perf_counter()
        with connection.execute_wrapper(contar):
            response = self.client.get(url, parametros)
        self.ultimas_sentencias = sentencias
        print(json.dumps({
            "ensayo": nombre, "estado_http": response.status_code,
            "segundos": round(perf_counter() - inicio, 3), "bytes": len(response.content),
            "sentencias": sum(sentencias.values()), "por_tipo": dict(sentencias),
        }, sort_keys=True), flush=True)
        return response

    def filas_csv(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(response.streaming)
        filas = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(filas), self.cantidad)
        self.assertTrue(all(None not in fila for fila in filas))
        return filas

    def test_exportaciones_completas_y_rechazo_de_exceso(self):
        self.client.force_authenticate(self.usuario)
        filtros = {"institucion": self.institucion.pk, "formato": "csv", "desde": self.hoy.isoformat()}
        filas = self.filas_csv(self.medir("hospital_5000", "/api/seguimiento-cobros/", filtros))
        esperados = {
            "importe_original": "100.00", "ajustes_aprobados": "-5.15",
            "obligacion_actual": "94.85", "registrado_neto": "38.30", "pendiente": "56.55",
            "saldo_a_devolver": "0.00", "por_aprobar": "3.45",
            "reintegros_por_aprobar": "1.20", "ajustes_por_aprobar": "2.30",
        }
        for campo, titulo in DINERO:
            valores = [Decimal(fila[titulo].replace(",", ".")) for fila in filas]
            self.assertEqual(set(valores), {Decimal(esperados[campo])}, campo)
            self.assertEqual(sum(valores), Decimal(esperados[campo]) * self.cantidad, campo)
        self.assertEqual(len({fila["Cuenta (ID; texto)"] for fila in filas}), self.cantidad)
        auditados = AccesoFinanciero.objects.filter(recurso="seguimiento-cobros", accion="exportar_cuentas")
        self.assertEqual(auditados.count(), 1)
        self.assertEqual(auditados.get().resultados, self.cantidad)

        self.client.force_authenticate(self.operador)
        url = f"/api/financiadores/{self.financiador.pk}/actividad/"
        filas = self.filas_csv(self.medir("financiador_5000_personas", url, filtros))
        self.assertEqual(self.ultimas_sentencias["INSERT"], 11)  # Diez lotes de 500 y el evento.
        importe = "Importe asignado original (sin descontar pagos ni ajustes; coma decimal)"
        self.assertEqual({fila[importe] for fila in filas}, {"100,00"})
        self.assertEqual(sum(Decimal(fila[importe].replace(",", ".")) for fila in filas), Decimal("500000.00"))
        self.assertEqual(len({fila["Documento (texto)"] for fila in filas}), self.cantidad)
        accesos = AccesoClinico.objects.filter(recurso="financiadores-actividad-csv")
        self.assertEqual(accesos.count(), self.cantidad)
        self.assertEqual(accesos.values("ciudadano_id").distinct().count(), self.cantidad)
        self.assertEqual(accesos.aggregate(total=Sum("resultados"))["total"], self.cantidad)
        por_reserva = {acceso.objeto_id: acceso for acceso in accesos}
        originales = ReservaCobertura.objects.filter(fecha=self.hoy).values_list("pk", "hecho__ciudadano_id")
        for reserva_id, ciudadano_id in originales:
            acceso = por_reserva[str(reserva_id)]
            self.assertEqual(acceso.ciudadano_id, ciudadano_id)
            self.assertEqual(acceso.institucion_id, self.institucion.pk)
            self.assertEqual(acceso.usuario_id, self.operador.pk)
            self.assertEqual(acceso.tipo, AccesoClinico.Tipo.FINANCIADOR)
            self.assertEqual(acceso.resultados, 1)
            self.assertEqual(acceso.detalle, f"financiador={self.financiador.pk} reservas={reserva_id}")
            self.assertEqual(acceso.ip, "127.0.0.1")
            self.assertIsNotNone(acceso.momento)
        self.assertEqual(EventoCobertura.objects.filter(accion="exportar_actividad").count(), 1)

        filtros.pop("desde")
        for nombre, destino, usuario in (
            ("hospital_5001_rechazado", "/api/seguimiento-cobros/", self.usuario),
            ("financiador_5001_rechazado", url, self.operador),
        ):
            with self.subTest(endpoint=nombre):
                self.client.force_authenticate(usuario)
                response = self.medir(nombre, destino, filtros)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("Content-Disposition", response)
                self.assertNotIn("text/csv", response["Content-Type"])
        self.assertEqual(auditados.count(), 1)
        self.assertEqual(accesos.count(), self.cantidad)
        self.assertEqual(EventoCobertura.objects.filter(accion="exportar_actividad").count(), 1)
        self.assertEqual(ObligacionFinanciera.objects.count(), self.cantidad + 1)
        self.assertEqual(MovimientoDinero.objects.count(), (self.cantidad + 1) * 5)
        self.assertEqual(AjusteObligacion.objects.count(), (self.cantidad + 1) * 2)

    def test_medicion_auditoria_por_fases(self):
        """Cinco repeticiones por tamaño, mismas fuentes, sin conservar sus accesos.

        Instrumentación exclusiva del ensayo. Consulta incluye preparación y
        evaluación; serialización incluye filas, celdas y CSV; auditoría incluye
        accesos y evento. El total también incluye permisos y respuesta HTTP.
        No se almacena SQL ni información personal. No hay umbrales temporales.
        """
        self.client.force_authenticate(self.operador)
        url = f"/api/financiadores/{self.financiador.pk}/actividad/"
        ids = list(ReservaCobertura.objects.order_by("pk").values_list("pk", flat=True))
        dinero_antes = (
            ObligacionFinanciera.objects.count(), MovimientoDinero.objects.count(),
            AjusteObligacion.objects.count(),
        )
        ReservaCobertura.objects.filter(pk__in=ids[100:1000]).update(fecha=self.hoy - timedelta(days=1))
        ReservaCobertura.objects.filter(pk__in=ids[1000:5000]).update(fecha=self.hoy - timedelta(days=2))
        ReservaCobertura.objects.filter(pk=ids[-1]).update(fecha=self.hoy - timedelta(days=3))
        for cantidad, dias in ((100, 0), (1000, 1), (5000, 2)):
            muestras = []
            contenido_esperado = None
            for repeticion in range(5):
                fases = Counter()
                sentencias = Counter()
                marcas = {}

                def medir_fase(funcion, fase):
                    def ejecutar(*args, **kwargs):
                        inicio = perf_counter()
                        if fase == "accesos":
                            fases["serializacion"] = inicio - marcas["fin_consulta"]
                        resultado = funcion(*args, **kwargs)
                        fases[fase] += perf_counter() - inicio
                        if funcion is list:
                            marcas["fin_consulta"] = perf_counter()
                        return resultado
                    return ejecutar

                def contar(ejecutar, sql, params, many, context):
                    sentencias[sql.lstrip().split(None, 1)[0].upper()] += 1
                    return ejecutar(sql, params, many, context)

                # Revierte sólo la auditoría sintética de esta repetición.
                with transaction.atomic():
                    with ExitStack() as stack:
                        for nombre in ("actividad_visible", "filtrar_actividad", "con_importes"):
                            stack.enter_context(patch.object(actividad, nombre, medir_fase(getattr(actividad, nombre), "consulta")))
                        stack.enter_context(patch.object(actividad, "list", medir_fase(list, "consulta"), create=True))
                        stack.enter_context(patch.object(actividad, "auditar_actividad", medir_fase(actividad.auditar_actividad, "accesos")))
                        stack.enter_context(patch.object(actividad, "auditar", medir_fase(actividad.auditar, "evento")))
                        stack.enter_context(connection.execute_wrapper(contar))
                        inicio = perf_counter()
                        response = self.client.get(url, {"formato": "csv", "desde": str(self.hoy - timedelta(days=dias))})
                        fases["total"] = perf_counter() - inicio
                    self.assertEqual(response.status_code, 200)
                    filas = list(csv.DictReader(StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
                    self.assertEqual(len(filas), cantidad)
                    if contenido_esperado is None:
                        contenido_esperado = response.content
                    self.assertEqual(response.content, contenido_esperado)
                    accesos = AccesoClinico.objects.filter(recurso="financiadores-actividad-csv")
                    self.assertEqual(accesos.count(), cantidad)
                    self.assertEqual(accesos.values("ciudadano_id").distinct().count(), cantidad)
                    self.assertEqual(accesos.aggregate(total=Sum("resultados"))["total"], cantidad)
                    self.assertEqual(EventoCobertura.objects.filter(accion="exportar_actividad").count(), 1)
                    transaction.set_rollback(True)
                muestra = {"repeticion": repeticion + 1, "personas": cantidad,
                           "segundos": dict(fases), "por_tipo": dict(sentencias)}
                muestras.append(muestra)
                print(json.dumps(muestra, sort_keys=True), flush=True)
            print(json.dumps({
                "ensayo": "resumen_fases", "personas": cantidad,
                "fases": {fase: {"mediana": median(m["segundos"][fase] for m in muestras),
                                  "desvio_poblacional": pstdev(m["segundos"][fase] for m in muestras),
                                  "min": min(m["segundos"][fase] for m in muestras),
                                  "max": max(m["segundos"][fase] for m in muestras)} for fase in fases},
            }, sort_keys=True), flush=True)
        self.assertEqual(dinero_antes, (
            ObligacionFinanciera.objects.count(), MovimientoDinero.objects.count(),
            AjusteObligacion.objects.count(),
        ))
