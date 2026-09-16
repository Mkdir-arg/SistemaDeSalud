"""Reportes del pagador: importes asignados, alcance y entrega CSV auditada."""
import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.auditoria.models import AccesoClinico
from apps.casos.models import EventoCaso
from apps.finanzas.dinero import reducir_obligacion
from apps.finanzas.services import registrar_atencion_completada
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

from .cobertura import liberar, seleccionar_afiliacion
from .cobros import resolver_saldo
from .models import (
    Afiliado, DistribucionCobro, EventoCobertura, Financiador,
    MembresiaFinanciador, Plan, PrestacionComun, ReservaCobertura,
)
from .test_vigencias import VigenciasApiSetup


class ActividadReporteTests(VigenciasApiSetup, APITestCase):
    def nueva_reserva(self, **datos):
        caso = self.nuevo_caso()
        seleccionar_afiliacion(
            caso=caso, usuario=self.admin, afiliado=self.afiliado,
            motivo="Afiliación verificada para otra atención",
        )
        return self.reservar(caso=caso, **datos)

    def realizar_reserva(self, reserva):
        evento = EventoCaso.objects.create(
            caso=reserva.caso, nodo=reserva.prestacion.nodo, autor=self.usuario,
            titulo="Atención registrada para el reporte",
        )
        registrar_atencion_completada(
            reserva.caso, reserva.prestacion.nodo, evento, self.usuario,
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, "realizada")
        return reserva

    def exportar(self, **filtros):
        response = self.client.get(self.base + "actividad/", {"formato": "csv", **filtros})
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        return response, list(csv.reader(StringIO(response.content.decode("utf-8-sig")), delimiter=";"))

    def test_totales_incluyen_todas_las_paginas_y_separan_reservas_de_cargos(self):
        primera = self.realizar_reserva(self.nueva_reserva())
        segunda = self.realizar_reserva(self.nueva_reserva())
        resolver_saldo(
            reserva=segunda, usuario=self.admin, decision="financiador", importe=Decimal("20"),
            motivo="Cobertura de la diferencia", evidencia="Acuerdo documentado", clave=uuid4(),
        )
        self.nueva_reserva(cantidad=2)
        liberada = self.nueva_reserva()
        liberar(reserva=liberada, usuario=self.admin, motivo="No se realizó", no_realizada=True)
        ReservaCobertura.objects.filter(pk=primera.pk).update(discrepancia=True)

        primera_pagina = self.actividad(page_size=1)
        segunda_pagina = self.actividad(page_size=1, page=2)
        self.assertEqual(ReservaCobertura.objects.count(), 4)
        self.assertEqual(primera_pagina["count"], 4, primera_pagina)
        self.assertEqual(len(primera_pagina["results"]), 1)
        self.assertEqual(primera_pagina["resumen"], segunda_pagina["resumen"])
        self.assertEqual(primera_pagina["resumen"], {
            "registros": 4, "reservadas": 1, "realizadas": 2, "liberadas": 1,
            "cantidad_realizada": 2, "cubiertas_realizadas": 2, "discrepancias": 1,
            "importes_pendientes": 0, "importe_asignado": "180.00",
        })
        self.assertIsNone(primera_pagina["results"][0]["importe_asignado"])
        self.assertEqual(primera_pagina["limite_exportacion"], 5000)
        self.assertTrue(primera_pagina["generado_en"])

    def test_importe_incluye_acuerdo_del_pagador_sin_sumar_rechazos_o_asuncion_hospital(self):
        propia = self.realizar_reserva(self.nueva_reserva())
        otra = self.realizar_reserva(self.nueva_reserva())
        for reserva, decision in [(propia, "financiador"), (otra, "rechazar"), (otra, "asumir")]:
            resolver_saldo(
                reserva=reserva, usuario=self.admin, decision=decision, importe=Decimal("20"),
                motivo="Revisión administrativa documentada", evidencia="Acuerdo firmado", clave=uuid4(),
            )
        filas = {fila["id"]: fila for fila in self.actividad()["results"]}
        self.assertEqual((filas[propia.pk]["importe_financiador"], filas[propia.pk]["importe_acuerdos"], filas[propia.pk]["importe_asignado"]), ("80.00", "20.00", "100.00"))
        self.assertEqual((filas[otra.pk]["importe_acuerdos"], filas[otra.pk]["importe_asignado"]), ("0.00", "80.00"))
        _, exportadas = self.exportar()
        propia_csv = next(fila for fila in exportadas[1:] if fila[0] == str(propia.pk))
        self.assertEqual(propia_csv[13:16], ["80,00", "20,00", "100,00"])

    def test_cargos_originales_no_se_presentan_como_saldo_tras_cobro_o_ajuste(self):
        reserva = self.realizada(acepta=True)
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        self.cobrar(obligacion)
        reducir_obligacion(
            obligacion=obligacion, importe=Decimal("10"), motivo="Reducción acordada",
            clave=uuid4(), usuario=self.admin, aprobado=True,
        )
        resultado = self.actividad()
        self.assertEqual(resultado["resumen"]["importe_asignado"], "80.00", resultado)
        self.assertEqual(resultado["results"][0]["importe_asignado"], "80.00")

    def test_importe_desconocido_no_se_convierte_en_cero_ni_suma_reservas(self):
        self.politica(importe=None)
        pendiente = self.realizada()
        self.politica()
        self.nueva_reserva()
        resultado = self.actividad()
        fila = next(fila for fila in resultado["results"] if fila["id"] == pendiente.pk)
        self.assertIsNone(fila["importe_financiador"])
        self.assertIsNone(fila["importe_asignado"])
        self.assertEqual(resultado["resumen"]["importes_pendientes"], 1)
        self.assertEqual(resultado["resumen"]["importe_asignado"], "0.00")

    def test_prestacion_sin_cobro_es_cero_conocido(self):
        self.politica(cobrar=False)
        self.realizada()
        resultado = self.actividad()
        self.assertEqual(resultado["results"][0]["importe_asignado"], "0.00")
        self.assertEqual(resultado["resumen"]["importes_pendientes"], 0)

    def test_filtro_fecha_es_inclusivo_y_totales_corresponden_al_periodo(self):
        anterior = self.nueva_reserva()
        actual = self.nueva_reserva()
        posterior = self.nueva_reserva()
        ReservaCobertura.objects.filter(pk=anterior.pk).update(fecha=self.hoy - timedelta(days=1))
        ReservaCobertura.objects.filter(pk=posterior.pk).update(fecha=self.hoy + timedelta(days=1))
        resultado = self.actividad(desde=str(self.hoy), hasta=str(self.hoy))
        self.assertEqual([fila["id"] for fila in resultado["results"]], [actual.pk])
        self.assertEqual(resultado["resumen"]["registros"], 1)
        self.assertEqual(self.actividad(hasta=str(self.hoy))["count"], 2)
        self.assertEqual(self.actividad(desde=str(self.hoy))["count"], 2)

    def test_filtros_invalidos_no_entregan_actividad_ni_csv(self):
        self.reservar()
        filtros = [
            {"desde": "31/01/2026"}, {"hasta": "2026-02-30"},
            {"desde": str(self.hoy + timedelta(days=1)), "hasta": str(self.hoy)},
            {"institucion": "otra"}, {"plan": "-1"}, {"prestacion": "0"},
            {"estado": "pagada"}, {"discrepancia": "quizás"},
            {"sin_plan": "quizás"}, {"sin_plan": "true", "plan": self.plan.pk},
        ]
        for filtro in filtros:
            for formato in ({}, {"formato": "csv"}):
                with self.subTest(filtro=filtro, formato=formato):
                    response = self.client.get(self.base + "actividad/", {**filtro, **formato})
                    self.assertEqual(response.status_code, 400)
        self.assertFalse(AccesoClinico.objects.filter(tipo="financiador").exists())

    def test_filtro_plan_y_opciones_usan_la_afiliacion_capturada(self):
        reserva = self.reservar()
        nuevo_plan = Plan.objects.create(financiador=self.financiador, codigo="NUEVO", nombre="Plan actual")
        Afiliado.objects.filter(pk=self.afiliado.pk).update(plan=nuevo_plan)
        Plan.objects.filter(pk=self.plan.pk).update(activo=False)
        resultado = self.actividad(plan=self.plan.pk)
        self.assertEqual([fila["id"] for fila in resultado["results"]], [reserva.pk])
        self.assertEqual(resultado["results"][0]["plan"], self.plan.nombre)
        self.assertEqual(resultado["opciones"]["planes"], [{"id": self.plan.pk, "nombre": self.plan.nombre}])
        self.assertEqual(self.actividad(plan=nuevo_plan.pk)["count"], 0)

    def test_sin_plan_filtra_la_afiliacion_capturada_y_no_el_padron_actual(self):
        con_plan = self.reservar()
        self.afiliado.plan = None
        self.afiliado.save(update_fields=["plan"])
        sin_plan = self.nueva_reserva()
        self.assertEqual(self.actividad()["count"], 2)
        resultado = self.actividad(sin_plan="true")
        self.assertEqual([fila["id"] for fila in resultado["results"]], [sin_plan.pk])
        self.assertIsNone(resultado["results"][0]["plan"])
        self.assertEqual([fila["id"] for fila in self.actividad(sin_plan="false")["results"]], [con_plan.pk])

    def test_filtro_institucion_usa_hospital_original_del_hecho(self):
        reserva = self.realizada()
        destino = Institucion.objects.create(nombre="Hospital de traslado")
        self.caso.institucion = destino
        self.caso.save(update_fields=["institucion"])
        resultado = self.actividad(institucion=self.institucion.pk)
        self.assertEqual([fila["id"] for fila in resultado["results"]], [reserva.pk])
        self.assertEqual(resultado["results"][0]["hospital"], self.institucion.nombre)
        self.assertEqual(resultado["opciones"]["instituciones"], [{"id": self.institucion.pk, "nombre": self.institucion.nombre}])
        self.assertEqual(self.actividad(institucion=destino.pk)["count"], 0)

    def test_catalogo_comun_filtra_prestaciones_locales_de_distintos_hospitales(self):
        primera = self.reservar()
        caso, prestacion = self.otro_hospital()
        segunda = self.reservar(caso=caso, prestacion=prestacion)
        otro_codigo = PrestacionComun.objects.create(codigo="SINUSO", nombre="Sin actividad")
        resultado = self.actividad(prestacion=self.comun.pk)
        self.assertEqual({fila["id"] for fila in resultado["results"]}, {primera.pk, segunda.pk})
        self.assertEqual(resultado["opciones"]["prestaciones"], [{"id": self.comun.pk, "nombre": self.comun.nombre, "codigo": self.comun.codigo}])
        self.assertEqual(self.actividad(prestacion=otro_codigo.pk)["count"], 0)

    def test_estado_y_discrepancia_se_combinan_y_no_recortan_las_opciones(self):
        primera = self.reservar()
        caso, prestacion = self.otro_hospital()
        segunda = self.reservar(caso=caso, prestacion=prestacion)
        liberar(reserva=segunda, usuario=self.admin, motivo="Atención cancelada", no_realizada=True)
        ReservaCobertura.objects.filter(pk=segunda.pk).update(discrepancia=True)
        resultado = self.actividad(estado="liberada", discrepancia="true", institucion=caso.institucion_id)
        self.assertEqual([fila["id"] for fila in resultado["results"]], [segunda.pk])
        self.assertEqual(resultado["resumen"]["discrepancias"], 1)
        self.assertEqual({opcion["id"] for opcion in resultado["opciones"]["instituciones"]}, {self.institucion.pk, caso.institucion_id})
        self.assertEqual([fila["id"] for fila in self.actividad(discrepancia="false")["results"]], [primera.pk])

    def test_busqueda_por_nombre_documento_numero_y_codigo_no_amplia_puntuacion(self):
        reserva = self.reservar()
        for termino in ("Ana Paz", "00.111.222", "00001", "CONS"):
            with self.subTest(termino=termino):
                resultado = self.actividad(search=termino)
                self.assertEqual([fila["id"] for fila in resultado["results"]], [reserva.pk])
        self.assertEqual(self.actividad(search="...---")["count"], 0)

    def test_organizacion_ajena_no_filtra_datos_por_totales_opciones_o_exportacion(self):
        self.realizada()
        otra = Financiador.objects.create(nombre="Mutual independiente", tipo="mutual")
        MembresiaFinanciador.objects.create(financiador=otra, usuario=self.operador, rol="auditor")
        self.base = f"/api/financiadores/{otra.pk}/"
        resultado = self.actividad()
        self.assertEqual(resultado["resumen"]["registros"], 0)
        self.assertEqual(resultado["resumen"]["importe_asignado"], "0.00")
        self.assertEqual(resultado["opciones"], {"instituciones": [], "planes": [], "prestaciones": []})
        response, filas = self.exportar()
        self.assertEqual(len(filas), 1)
        self.assertNotIn(self.afiliado.documento.encode(), response.content)
        self.assertFalse(AccesoClinico.objects.filter(tipo="financiador").exists())

    def test_sin_membresia_no_puede_obtener_exportacion(self):
        self.reservar()
        self.client.force_authenticate(self.usuario)
        for filtros in ({}, {"formato": "csv"}):
            with self.subTest(filtros=filtros):
                self.assertIn(self.client.get(self.base + "actividad/", filtros).status_code, (403, 404))
        self.assertFalse(AccesoClinico.objects.filter(tipo="financiador").exists())

    def test_cierre_conserva_solo_pendientes_en_filtrado_totales_opciones_y_csv(self):
        pendiente = self.realizada(acepta=True)
        caso, prestacion = self.otro_hospital()
        saldada = self.realizar_reserva(self.reservar(caso=caso, prestacion=prestacion, acepta=True))
        self.cobrar(DistribucionCobro.objects.get(reserva=saldada).obligacion_financiador)
        self.finalizar()
        resultado = self.actividad()
        self.assertEqual([fila["id"] for fila in resultado["results"]], [pendiente.pk])
        self.assertEqual(resultado["resumen"]["importe_asignado"], "80.00")
        self.assertEqual(resultado["opciones"]["instituciones"], [{"id": self.institucion.pk, "nombre": self.institucion.nombre}])
        self.assertEqual(self.actividad(institucion=caso.institucion_id)["resumen"]["registros"], 0)
        _, filas = self.exportar()
        self.assertEqual([int(fila[0]) for fila in filas[1:]], [pendiente.pk])

    def test_csv_exporta_todo_el_resultado_filtrado_ordenado_ignorando_paginacion(self):
        anterior = self.nueva_reserva()
        ReservaCobertura.objects.filter(pk=anterior.pk).update(fecha=self.hoy - timedelta(days=1))
        primera = self.nueva_reserva()
        segunda = self.nueva_reserva()
        response, filas = self.exportar(desde=str(self.hoy), page_size=1, page=2)
        self.assertEqual([int(fila[0]) for fila in filas[1:]], [segunda.pk, primera.pk])
        self.assertIn("no-store", response["Cache-Control"])
        acceso = AccesoClinico.objects.get(recurso="financiadores-actividad-csv")
        self.assertEqual(acceso.resultados, 2)
        self.assertEqual(acceso.institucion_id, self.institucion.pk)
        self.assertTrue(EventoCobertura.objects.filter(accion="exportar_actividad", financiador=self.financiador, usuario=self.operador).exists())

    def test_csv_respeta_limite_sin_descargar_un_archivo_parcial(self):
        self.nueva_reserva()
        self.nueva_reserva()
        with patch("apps.financiadores.actividad.LIMITE_EXPORTACION", 1):
            response = self.client.get(self.base + "actividad/", {"formato": "csv"})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Content-Disposition", response)
        self.assertFalse(AccesoClinico.objects.filter(recurso="financiadores-actividad-csv").exists())
        self.assertFalse(EventoCobertura.objects.filter(accion="exportar_actividad").exists())

    def test_csv_preserva_ceros_quotes_y_saltos_sin_inyeccion_de_formulas(self):
        self.reservar()
        nombres = ["=HYPERLINK(\"https://example.test\")", " +SUM(1;2)", "\t@SUM(1;2)", "\r-2+3"]
        for nombre in nombres:
            with self.subTest(nombre=nombre):
                Afiliado.objects.filter(pk=self.afiliado.pk).update(nombre=nombre)
                _, filas = self.exportar()
                self.assertIn("'" + nombre, filas[1])
                self.assertIn("'00111222", filas[1])
                self.assertIn("'00001", filas[1])
        nombre_literal = 'Ana; "Marta"\nPaz'
        Afiliado.objects.filter(pk=self.afiliado.pk).update(nombre=nombre_literal)
        _, filas = self.exportar()
        self.assertEqual(len(filas), 2)
        self.assertIn(nombre_literal, filas[1])

    def test_numero_afiliado_parecido_a_fecha_se_exporta_sin_transformarlo(self):
        self.reservar()
        numero = "2026-09-16-001"
        Afiliado.objects.filter(pk=self.afiliado.pk).update(numero=numero)
        _, filas = self.exportar()
        self.assertIn("'" + numero, filas[1])

    def test_csv_audita_todos_los_identificadores_sin_truncar_grupos_grandes(self):
        reservas = set()
        for numero in range(25):
            reserva = self.nueva_reserva()
            # Con IDs largos, un único detalle por persona excedería sus 300 caracteres.
            identificador = 10**15 + numero
            ReservaCobertura.objects.filter(pk=reserva.pk).update(id=identificador)
            reservas.add(identificador)
        self.exportar()
        accesos = AccesoClinico.objects.filter(recurso="financiadores-actividad-csv")
        ids_auditados = set()
        for acceso in accesos:
            self.assertLessEqual(len(acceso.detalle), 300)
            ids_auditados.update(int(valor) for valor in acceso.detalle.split("reservas=", 1)[1].split(","))
        self.assertEqual(ids_auditados, reservas)
        self.assertEqual(sum(acceso.resultados for acceso in accesos), 25)

    def test_csv_audita_cada_hospital_y_paciente_original_antes_de_entregar(self):
        self.realizada()
        caso, prestacion = self.otro_hospital()
        self.reservar(caso=caso, prestacion=prestacion)
        nuevo = Ciudadano.objects.create(institucion=self.institucion, nombre="Paciente corregido", documento="99999")
        self.caso.ciudadano = nuevo
        self.caso.save(update_fields=["ciudadano"])
        self.exportar(page_size=1)
        accesos = AccesoClinico.objects.filter(recurso="financiadores-actividad-csv")
        self.assertEqual(set(accesos.values_list("institucion_id", "ciudadano_id")), {
            (self.institucion.pk, self.paciente.pk), (caso.institucion_id, caso.ciudadano_id),
        })

    @override_settings(DEBUG=False)
    def test_fallo_auditoria_clinica_no_entrega_csv(self):
        self.reservar()
        self.client.raise_request_exception = False
        with patch("apps.auditoria.mixins.AccesoClinico.objects.create", side_effect=RuntimeError("Auditoría no disponible")):
            response = self.client.get(self.base + "actividad/", {"formato": "csv"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("Content-Disposition", response)
        self.assertNotIn(self.afiliado.documento.encode(), response.content)
        self.assertFalse(EventoCobertura.objects.filter(accion="exportar_actividad").exists())

    @override_settings(DEBUG=False)
    def test_fallo_auditoria_administrativa_no_entrega_csv(self):
        self.reservar()
        self.client.raise_request_exception = False
        with patch("apps.financiadores.services.EventoCobertura.objects.create", side_effect=RuntimeError("Auditoría no disponible")):
            response = self.client.get(self.base + "actividad/", {"formato": "csv"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("Content-Disposition", response)
        self.assertNotIn(self.afiliado.documento.encode(), response.content)
        self.assertFalse(AccesoClinico.objects.filter(recurso="financiadores-actividad-csv").exists())

    @override_settings(DEBUG=False)
    def test_fallo_en_segundo_acceso_revierte_la_auditoria_incompleta(self):
        self.reservar()
        caso, prestacion = self.otro_hospital()
        self.reservar(caso=caso, prestacion=prestacion)
        crear_acceso = AccesoClinico.objects.create
        intentos = []

        def crear_o_fallar(**datos):
            intentos.append(datos["institucion_id"])
            if len(intentos) == 2:
                raise RuntimeError("Auditoría interrumpida")
            return crear_acceso(**datos)

        self.client.raise_request_exception = False
        with patch("apps.auditoria.mixins.AccesoClinico.objects.create", side_effect=crear_o_fallar):
            response = self.client.get(self.base + "actividad/", {"formato": "csv"})
        self.assertEqual(len(intentos), 2)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(AccesoClinico.objects.filter(recurso="financiadores-actividad-csv").exists())
        self.assertFalse(EventoCobertura.objects.filter(accion="exportar_actividad").exists())
