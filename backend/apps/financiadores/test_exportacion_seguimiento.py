"""CSV hospitalario: misma lectura autorizada, archivo íntegro y auditado."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia
from apps.casos.models import Caso, EventoCaso
from apps.finanzas.models import (
    AccesoFinanciero, AjusteObligacion, MovimientoDinero, ObligacionFinanciera,
)
from apps.finanzas.services import registrar_atencion_completada
from apps.instituciones.models import Area

from .cobertura import seleccionar_afiliacion
from .models import DistribucionCobro, ReservaCobertura
from .test_seguimiento import SeguimientoSetup


ENCABEZADOS_DINERO = {
    "importe_original": "Importe original (ARS; coma decimal)",
    "ajustes_aprobados": "Ajustes aprobados (ARS; coma decimal)",
    "obligacion_actual": "Importe actual de la cuenta (ARS; coma decimal)",
    "registrado_neto": "Cobrado neto confirmado (ARS; coma decimal)",
    "pendiente": "Saldo pendiente de cobro (ARS; coma decimal)",
    "saldo_a_devolver": "Saldo a devolver (ARS; coma decimal)",
    "por_aprobar": "Cobros por aprobar (ARS; coma decimal)",
    "reintegros_por_aprobar": "Devoluciones por aprobar (ARS; coma decimal)",
    "ajustes_por_aprobar": "Reducciones por aprobar (ARS; coma decimal)",
}


def literal(valor):
    """Excel recibe texto explícito; el dato original conserva su contenido."""
    return valor[1:] if valor.startswith("'") else valor


class ExportacionSeguimientoSetup(SeguimientoSetup):
    def respuesta_csv(self, **filtros):
        return self.client.get(self.url, {
            "institucion": self.institucion.pk, "formato": "csv", **filtros,
        })

    def exportar(self, **filtros):
        response = self.respuesta_csv(**filtros)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("private", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertFalse(response.streaming)
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        lector = csv.DictReader(StringIO(response.content.decode("utf-8-sig")), delimiter=";")
        filas = list(lector)
        self.assertTrue(lector.fieldnames)
        for fila in filas:
            self.assertNotIn(None, fila, "Una celda escapó las columnas del archivo")
        return response, filas, lector.fieldnames

    def captura_fallida(self):
        caso = self.nuevo_caso()
        evento = EventoCaso.objects.create(caso=caso, nodo=self.nodo, autor=self.usuario, titulo="Atención completada")
        with patch("apps.finanzas.cobros.capturar_cobros_atencion", side_effect=RuntimeError("Captura no disponible")):
            return registrar_atencion_completada(caso, self.nodo, evento, self.usuario)

    def cantidades_financieras(self):
        return tuple(modelo.objects.count() for modelo in (
            ReservaCobertura, DistribucionCobro, ObligacionFinanciera, MovimientoDinero, AjusteObligacion,
        ))


class ExportacionSeguimientoContenidoTests(ExportacionSeguimientoSetup, APITestCase):
    def test_exporta_todas_las_filas_filtradas_en_el_mismo_orden_que_json(self):
        for _ in range(3):
            self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        filtros = {
            "area": self.area.pk, "financiador": self.financiador.pk, "responsable": "financiador",
            "desde": str(self.hoy), "hasta": str(self.hoy), "estado": "pendiente",
            "search": self.prestacion.nombre,
        }
        pagina = self.consultar(page_size=1, **filtros)
        completo = self.consultar(**filtros)
        self.assertEqual(pagina["count"], 3)
        self.assertEqual(len(pagina["results"]), 1)
        _, filas, _ = self.exportar(page=999, page_size=1, **filtros)
        self.assertEqual([int(literal(fila["Cuenta (ID; texto)"])) for fila in filas], [fila["id"] for fila in completo["results"]])
        self.assertEqual(sum(Decimal(fila[ENCABEZADOS_DINERO["pendiente"]].replace(",", ".")) for fila in filas), Decimal(pagina["resumen"]["pendiente"]))
        acceso = AccesoFinanciero.objects.get(recurso="seguimiento-cobros", accion="exportar_cuentas")
        self.assertEqual(acceso.resultados, 3)

    def test_exporta_saldos_exactos_en_ars_sin_cambiar_el_libro_de_dinero(self):
        reserva = self.realizar()
        obligacion = DistribucionCobro.objects.get(reserva=reserva).obligacion_financiador
        cobro = self.movimiento(obligacion, "30.25")
        self.reintegro(cobro, "2.10")
        self.reduccion(obligacion, "5.35")
        self.movimiento(obligacion, "3.40", aprobado=False)
        self.reintegro(cobro, "1.05", aprobado=False)
        self.reduccion(obligacion, "2.20", aprobado=False)
        esperado = {fila["id"]: fila for fila in self.consultar()["results"]}
        cantidades = self.cantidades_financieras()
        _, filas, encabezados = self.exportar()
        self.assertEqual(self.cantidades_financieras(), cantidades)
        self.assertEqual(len(encabezados), 22)
        for fila in filas:
            dato = esperado[int(literal(fila["Cuenta (ID; texto)"]))]
            for campo, titulo in ENCABEZADOS_DINERO.items():
                self.assertEqual(fila[titulo], dato[campo].replace(".", ","), campo)
            self.assertEqual(fila["Hospital (ID; texto)"], f"'{self.institucion.pk}")
            self.assertEqual(fila["Reserva (ID; texto)"], f"'{reserva.pk}")
            self.assertEqual(fila["Caso (ID; texto)"], f"'{reserva.caso_id}")
            self.assertEqual(fila["Área de origen (ID; texto)"], f"'{self.area.pk}")
            self.assertEqual(fila["Financiador de la cobertura (ID; texto)"], f"'{self.financiador.pk}")
            self.assertEqual(fila["Fecha de prestación"], self.hoy.isoformat())
            self.assertEqual(fila["Sensible"], "No")
            self.assertIsNotNone(datetime.fromisoformat(fila["Generado el (ISO 8601)"]).tzinfo)
            self.assertIn(fila["Tipo de responsable"], ("Financiador", "Paciente"))
        fila_financiador = next(fila for fila in filas if fila["Tipo de responsable"] == "Financiador")
        self.assertEqual(fila_financiador[ENCABEZADOS_DINERO["ajustes_aprobados"]], "-5,35")

    def test_pendientes_distinguen_importe_desconocido_de_cero(self):
        pendiente = self.realizar(acepta=False)
        self.politica(importe=None)
        desconocido = self.realizar(acepta=False)
        cantidades = self.cantidades_financieras()
        _, filas, encabezados = self.exportar(vista="pendientes")
        self.assertEqual(self.cantidades_financieras(), cantidades)
        self.assertEqual(len(encabezados), 13)
        filas = {int(literal(fila["Reserva (ID; texto)"])): fila for fila in filas}
        titulo = "Importe administrativo (ARS; coma decimal; vacío = por determinar)"
        estado = "Estado administrativo (no constituye deuda asignada)"
        self.assertEqual(filas[pendiente.pk][titulo], "20,00")
        self.assertEqual(filas[desconocido.pk][titulo], "")
        self.assertEqual(filas[pendiente.pk][estado], "Pendiente de resolución")
        self.assertEqual(filas[desconocido.pk][estado], "Arancel pendiente")
        self.assertNotIn("Responsable del cobro", encabezados)
        self.assertFalse(set(ENCABEZADOS_DINERO.values()) & set(encabezados))

    def test_capturas_no_publican_prestacion_importes_ni_persona_sin_verificar(self):
        hecho = self.captura_fallida()
        cantidades = self.cantidades_financieras()
        _, filas, encabezados = self.exportar(vista="captura")
        self.assertEqual(self.cantidades_financieras(), cantidades)
        self.assertEqual(len(filas), 1)
        self.assertEqual(set(encabezados), {
            "Hospital (ID; texto)", "Generado el (ISO 8601)", "Caso (ID; texto)", "Fecha de prestación",
            "Área de origen (ID; texto)", "Sensible", "Hecho de atención (ID; texto)", "Estado de captura", "Motivo",
        })
        self.assertEqual(filas[0]["Hecho de atención (ID; texto)"], f"'{hecho.pk}")
        self.assertEqual(filas[0]["Estado de captura"], "Captura pendiente")
        self.assertEqual(filas[0]["Sensible"], "Sí")

    def test_limite_admite_archivo_completo_y_rechaza_exceso_sin_parcial(self):
        self.realizar()
        with patch("apps.financiadores.seguimiento_csv.LIMITE_EXPORTACION", 2):
            _, filas, _ = self.exportar()
        self.assertEqual(len(filas), 2)
        self.realizar()
        previos = AccesoFinanciero.objects.filter(accion="exportar_cuentas").count()
        with patch("apps.financiadores.seguimiento_csv.LIMITE_EXPORTACION", 3):
            response = self.respuesta_csv(page_size=1)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Content-Disposition", response)
        self.assertNotIn("text/csv", response["Content-Type"])
        self.assertEqual(AccesoFinanciero.objects.filter(accion="exportar_cuentas").count(), previos)

    def test_json_informa_limite_de_exportacion_y_archivo_vacio_conserva_encabezados(self):
        for vista, columnas in (("cuentas", 22), ("pendientes", 13), ("captura", 9)):
            with self.subTest(vista=vista):
                self.assertEqual(self.consultar(vista=vista)["limite_exportacion"], 5000)
                _, filas, encabezados = self.exportar(vista=vista)
                self.assertEqual(filas, [])
                self.assertEqual(len(encabezados), columnas)
                acceso = AccesoFinanciero.objects.get(recurso="seguimiento-cobros", accion=f"exportar_{vista}")
                self.assertEqual(acceso.resultados, 0)
                self.assertEqual(acceso.institucion_id, self.institucion.pk)
                self.assertIsNone(acceso.area_id)
                self.assertIsNone(acceso.periodo_economico)

    def test_textos_peligrosos_incluyen_espacios_y_controles_unicode(self):
        self.realizar()
        for texto in (
            '=HYPERLINK("https://example.test")', " +SUM(1;2)", "\t@SUM(1;2)",
            "\r-2+3", "\u200b\u202e \t=SUM(1;2)", "\u00a0\u2002+1+2",
        ):
            with self.subTest(texto=texto):
                type(self.prestacion).objects.filter(pk=self.prestacion.pk).update(nombre=texto)
                _, filas, _ = self.exportar()
                self.assertTrue(all(fila["Prestación"].startswith("'") for fila in filas))
                self.assertTrue(all(literal(fila["Prestación"]) == texto for fila in filas))

    def test_separadores_comillas_y_saltos_preservan_celdas_y_nombres_literales(self):
        self.paciente.nombre = "2026-09-16"
        self.paciente.apellido = ""
        self.paciente.save(update_fields=["nombre", "apellido"])
        self.realizar()
        texto = 'Consulta; "control"\nEspecial'
        type(self.prestacion).objects.filter(pk=self.prestacion.pk).update(nombre=texto)
        type(self.financiador).objects.filter(pk=self.financiador.pk).update(nombre="2026-09-16-001")
        _, filas, _ = self.exportar()
        self.assertEqual(len(filas), 2)
        self.assertTrue(all(literal(fila["Prestación"]) == texto for fila in filas))
        self.assertTrue(all(literal(fila["Financiador de la cobertura"]) == "2026-09-16-001" for fila in filas))
        self.assertTrue(all(fila["Financiador de la cobertura"] == "'2026-09-16-001" for fila in filas))
        paciente = next(fila for fila in filas if fila["Tipo de responsable"] == "Paciente")
        self.assertEqual(paciente["Responsable del cobro"], "'2026-09-16")

    def test_identificador_largo_se_exporta_como_texto_sin_notacion_cientifica(self):
        caso = Caso.objects.create(
            pk=10000000000000001, institucion=self.institucion, version=self.caso.version,
            ciudadano=self.paciente, area_actual=self.area,
        )
        seleccionar_afiliacion(caso=caso, usuario=self.admin, afiliado=self.afiliado, motivo="Afiliación verificada")
        self.realizar(caso=caso)
        _, filas, _ = self.exportar()
        self.assertTrue(all(fila["Caso (ID; texto)"] == "'10000000000000001" for fila in filas))

    def test_exportacion_no_incluye_documentos_ni_narrativa_clinica(self):
        reserva = self.realizar()
        EventoCaso.objects.filter(pk=reserva.hecho.evento_id).update(detalle="DIAGNOSTICO_PRIVADO_NO_EXPORTAR")
        response, _, encabezados = self.exportar()
        self.assertNotIn(self.paciente.documento.encode(), response.content)
        self.assertNotIn(b"DIAGNOSTICO_PRIVADO_NO_EXPORTAR", response.content)
        self.assertFalse(any("documento" in titulo.lower() or "aceptaci" in titulo.lower() for titulo in encabezados))


class ExportacionSeguimientoPermisosTests(ExportacionSeguimientoSetup, APITestCase):
    def test_financiador_clinico_y_resolver_sin_lectura_no_descargan(self):
        self.realizar()
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMIN_INSTITUCION)
        self.conceder("resolver_cobertura", sensible=True)
        for usuario in (self.usuario, self.operador):
            self.client.force_authenticate(usuario)
            for vista in ("cuentas", "pendientes", "captura"):
                with self.subTest(usuario=usuario.pk, vista=vista):
                    response = self.respuesta_csv(vista=vista)
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn("Content-Disposition", response)
        self.assertFalse(AccesoFinanciero.objects.filter(accion__startswith="exportar_").exists())

    def test_area_y_sensibilidad_restringen_archivo_y_auditoria(self):
        publica = self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Área reservada")
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        self.politica(sensible=True)
        self.realizar()
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        _, filas, _ = self.exportar()
        self.assertEqual(len(filas), 2)
        self.assertEqual({int(literal(fila["Reserva (ID; texto)"])) for fila in filas}, {publica.pk})
        acceso = AccesoFinanciero.objects.get(usuario=self.usuario, accion="exportar_cuentas")
        self.assertEqual(acceso.area_id, self.area.pk)
        self.assertFalse(acceso.sensible)
        self.assertEqual(acceso.resultados, 2)

    def test_otro_hospital_y_sesion_anonima_no_pueden_descargar(self):
        caso, prestacion = self.otro_hospital()
        self.realizar(caso=caso, prestacion=prestacion)
        self.conceder("ver_dinero", sensible=True)
        self.client.force_authenticate(self.usuario)
        response = self.respuesta_csv(institucion=caso.institucion_id)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Content-Disposition", response)
        self.client.force_authenticate(None)
        response = self.respuesta_csv()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("Content-Disposition", response)

    def test_captura_y_evaluacion_incompleta_siguen_restringidas_por_sensibilidad(self):
        self.captura_fallida()
        self.politica(sensible=True, importe=None)
        self.realizar(acepta=False)
        self.conceder("ver_dinero", area=self.area)
        self.client.force_authenticate(self.usuario)
        for vista in ("captura", "pendientes"):
            with self.subTest(vista=vista):
                _, filas, _ = self.exportar(vista=vista)
                self.assertEqual(filas, [])
                acceso = AccesoFinanciero.objects.get(usuario=self.usuario, accion=f"exportar_{vista}")
                self.assertEqual(acceso.resultados, 0)

    def test_filtros_incompatibles_o_invalidos_no_entregan_archivos(self):
        self.realizar()
        for filtros in (
            {"formato": "xlsx"}, {"formato": "CSV"}, {"vista": "otra"}, {"desde": "31/01/2026"},
            {"desde": str(self.hoy), "hasta": str(self.hoy - timedelta(days=1))},
            {"vista": "captura", "financiador": self.financiador.pk},
            {"vista": "captura", "responsable": "paciente"}, {"vista": "captura", "estado": "pendiente"},
            {"vista": "pendientes", "responsable": "paciente"}, {"estado": "evaluacion_pendiente"},
        ):
            with self.subTest(filtros=filtros):
                response = self.respuesta_csv(**filtros)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("Content-Disposition", response)
        self.assertFalse(AccesoFinanciero.objects.filter(accion__startswith="exportar_").exists())


class ExportacionSeguimientoAuditoriaTests(ExportacionSeguimientoSetup, APITestCase):
    def test_audita_la_lista_exportada_aunque_entren_cargos_durante_la_generacion(self):
        from .seguimiento import fila_seguimiento

        original = self.realizar()
        nuevas = []

        def serializar(objeto, vista):
            if not nuevas:
                # Simula una incorporación posterior a la lectura del archivo.
                nuevas.append(self.realizar())
            return fila_seguimiento(objeto, vista)

        with patch("apps.financiadores.seguimiento_csv.fila_seguimiento", side_effect=serializar):
            _, filas, _ = self.exportar()
        self.assertEqual(ObligacionFinanciera.objects.count(), 4)
        self.assertEqual(len(filas), 2)
        self.assertEqual({int(literal(fila["Reserva (ID; texto)"])) for fila in filas}, {original.pk})
        acceso = AccesoFinanciero.objects.get(recurso="seguimiento-cobros", accion="exportar_cuentas")
        self.assertEqual(acceso.resultados, len(filas))

    def test_grupos_corresponden_a_todas_las_filas_del_archivo(self):
        self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.politica(sensible=True)
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        _, filas, _ = self.exportar(page_size=1)
        self.assertEqual(len(filas), 4)
        accesos = AccesoFinanciero.objects.filter(recurso="seguimiento-cobros", accion="exportar_cuentas")
        self.assertEqual(set(accesos.values_list("institucion_id", "area_id", "sensible", "periodo_economico", "resultados")), {
            (self.institucion.pk, self.area.pk, False, self.hoy.replace(day=1), 2),
            (self.institucion.pk, otra_area.pk, True, self.hoy.replace(day=1), 2),
        })

    def test_fallo_auditoria_impide_entregar_cualquier_csv(self):
        self.realizar(acepta=False)
        self.captura_fallida()
        for vista in ("cuentas", "pendientes", "captura"):
            with self.subTest(vista=vista), patch("apps.finanzas.models.AccesoFinanciero.objects.create", side_effect=RuntimeError("Auditoría no disponible")):
                response = self.respuesta_csv(vista=vista)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("Content-Disposition", response)
                self.assertNotIn("text/csv", response["Content-Type"])
                self.assertNotIn("Hospital (ID; texto)", response.content.decode())
                self.assertIn("no-store", response["Cache-Control"])

    def test_fallo_en_segundo_grupo_revierte_auditoria_incompleta(self):
        self.realizar()
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.realizar(caso=self.nuevo_caso(area=otra_area))
        crear = AccesoFinanciero.objects.create
        intentos = []

        def registrar(**datos):
            intentos.append(datos)
            if len(intentos) == 2:
                raise RuntimeError("No se pudo auditar el segundo grupo")
            return crear(**datos)

        with patch("apps.finanzas.models.AccesoFinanciero.objects.create", side_effect=registrar):
            response = self.respuesta_csv()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Content-Disposition", response)
        self.assertEqual(len(intentos), 2)
        self.assertFalse(AccesoFinanciero.objects.filter(accion="exportar_cuentas").exists())
