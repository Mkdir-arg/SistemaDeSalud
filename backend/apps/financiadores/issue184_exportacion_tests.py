"""Contraste de proyección UI/XLSX con datos ficticios; requiere #186 y Node.

Ejecutar explícitamente con manage.py test apps.financiadores.issue184_exportacion_tests.
No se conecta a servicios externos. ISSUE184_ARTIFACT_DIR permite guardar el XLSX
ficticio para revisión humana cuando se ejecuta en un entorno de pruebas aislado.
"""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
from unittest import skipUnless

from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from . import models as m
from . import test_padron_exportacion as base_exportacion


@skipUnless(hasattr(m.Afiliado, "cobertura_habilitada"), "Requiere integrar #186")
class ContrasteIssue184Tests(APITestCase):
    # Reusar exactamente los datos ficticios y controles del exportador existente.
    setUp = base_exportacion.ExportacionPadronTests.setUp
    libro = base_exportacion.ExportacionPadronTests.libro

    def proyeccion_ui(self, filas, columnas):
        respuesta_planes = self.client.get(f"/api/financiadores/{self.org.pk}/planes/")
        self.assertEqual(respuesta_planes.status_code, 200)
        planes = respuesta_planes.data["results"]
        # Ejecutar el formateador productivo real, no una copia Python de su lógica.
        helper = Path(__file__).resolve().parents[3] / "frontend/src/components/financiadores/padronTablaEstado.js"
        script = """
import { readFileSync } from 'node:fs';
const { COLUMNAS_PADRON, valorColumnaPadron } = await import(process.argv[1]);
const { filas, columnas, planes } = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(filas.map(fila => columnas.map(key =>
  valorColumnaPadron(fila, COLUMNAS_PADRON.find(c => c.key === key), planes)))));
"""
        resultado = subprocess.run(
            ["node", "--input-type=module", "-e", script, helper.as_uri()],
            input=json.dumps({"filas": filas, "columnas": columnas, "planes": planes}),
            text=True, capture_output=True, check=True, encoding="utf-8")
        return json.loads(resultado.stdout)

    def test_estados_y_habilitacion_coinciden_entre_proyeccion_ui_y_xlsx(self):
        hoy = timezone.localdate()
        m.Afiliado.objects.filter(pk=self.a.pk).update(
            nombre="Administrativa ficticia", cobertura_habilitada=False)
        for numero, nombre, extra in [
            ("00026", "Vigente ficticia", {"estado_tramite": "completo"}),
            ("00027", "Futura ficticia", {"desde": hoy + timedelta(days=30)}),
            ("00028", "Finalizada ficticia", {"finalizado_en": timezone.now(), "cobertura_habilitada": False}),
        ]:
            datos = {"financiador": self.org, "numero": numero, "documento": numero,
                     "nombre": nombre, "desde": hoy, **extra}
            m.Afiliado.objects.create(**datos)
        columnas = ["nombre", "numero", "derecho", "estado_administrativo", "cobertura_habilitada"]
        params = {"estado": "todos", "ordering": "numero", "columnas": ",".join(columnas)}
        listado = self.client.get(f"/api/financiadores/{self.org.pk}/padron/", params)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["count"], 4)
        filas_xlsx = [list(row) for row in list(self.libro(params)["Padrón"].values)[1:]]
        self.assertEqual(self.proyeccion_ui(listado.data["results"], columnas), filas_xlsx)
        self.assertEqual([row[2] for row in filas_xlsx],
                         ["Sólo administrativa", "Vigente", "Aún no vigente", "Finalizada"])
        directorio = os.environ.get("ISSUE184_ARTIFACT_DIR")
        if directorio:
            destino = Path(directorio)
            destino.mkdir(parents=True, exist_ok=True)
            respuesta = self.client.get(self.url, params)
            self.assertEqual(respuesta.status_code, 200)
            (destino / "issue184-padron-ficticio.xlsx").write_bytes(respuesta.content)

    def test_filtro_administrativo_exporta_solo_la_misma_seleccion(self):
        m.Afiliado.objects.filter(pk=self.a.pk).update(cobertura_habilitada=False)
        params = {"estado": "administrativas", "flt_cobertura_habilitada": "false",
                  "columnas": "nombre,numero,derecho", "ordering": "numero"}
        listado = self.client.get(f"/api/financiadores/{self.org.pk}/padron/", params)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual([row["id"] for row in listado.data["results"]], [self.a.pk])
        filas = list(self.libro(params)["Padrón"].values)[1:]
        self.assertEqual(filas, [(self.a.nombre, self.a.numero, "Sólo administrativa")])


    def test_columnas_administrativas_existentes_coinciden_sin_inferir_derechos(self):
        hoy = timezone.localdate()
        plan = m.Plan.objects.create(financiador=self.org, codigo="FICTICIO184", nombre="Plan ficticio administrativo", tipo="base")
        titular = m.Afiliado.objects.create(financiador=self.org, numero="T00001", documento="99018401", nombre="Titular ficticio ya vinculado", desde=hoy)
        m.Afiliado.objects.filter(pk=self.a.pk).update(
            nombre="Caso administrativo ficticio #184", numero_interno="000184", plan=plan, titular=titular,
            parentesco="hijo", desde=hoy - timedelta(days=90),
            alta_administrativa=hoy - timedelta(days=95),
            baja_efectiva=hoy - timedelta(days=1), causa_baja="otra",
            motivo_baja="Evidencia administrativa ficticia; sin corte de derechos",
            fin_prestacional_informado=hoy + timedelta(days=5))
        claves = {"nombre", "numero_interno", "numero", "titular_nombre", "plan", "derecho", "cobertura_habilitada", "estado_administrativo", "desde", "alta_administrativa", "baja_efectiva", "causa_baja", "motivo_baja", "fin_prestacional_informado", "titular", "parentesco"}
        columnas = [key for key in base_exportacion.COLUMNAS_PADRON if key in claves]
        params = {"estado": "todos", "search": "Caso administrativo ficticio", "ordering": "numero", "columnas": ",".join(columnas)}
        listado = self.client.get(f"/api/financiadores/{self.org.pk}/padron/", params)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["count"], 1)
        hoja = self.libro(params)["Padrón"]
        self.assertEqual(list(hoja.values)[0], tuple(base_exportacion.COLUMNAS_PADRON[key]["label"] for key in columnas))
        fila_xlsx = list(hoja.values)[1]
        # Las fechas de calendario conservan el día, aunque Excel las tipa.
        esperada = [valor.strftime("%d/%m/%Y") if hasattr(valor, "strftime") else str(valor) for valor in fila_xlsx]
        self.assertEqual(self.proyeccion_ui(listado.data["results"], columnas), [esperada])
        por_columna = dict(zip(columnas, esperada))
        self.assertEqual(por_columna["derecho"], "Vigente")
        self.assertEqual(por_columna["estado_administrativo"], "Baja administrativa")
        self.assertEqual(por_columna["numero"], "00025")
        self.assertEqual(por_columna["numero_interno"], "000184")
        self.assertEqual(por_columna["titular_nombre"], titular.nombre)
        self.assertEqual(por_columna["titular"], str(titular.pk))
        self.assertEqual(por_columna["parentesco"], "Hijo")
        self.assertEqual(hoja.cell(2, columnas.index("numero") + 1).data_type, "s")


    def test_vista_inicial_aprobada_y_busqueda_por_numero_individual(self):
        from .padron_consulta import validar_columnas_padron
        columnas = validar_columnas_padron()
        self.assertEqual(list(columnas), ["nombre", "numero_interno", "numero", "documento", "plan", "derecho", "estado_administrativo", "alta_administrativa", "baja_efectiva", "motivo_baja", "titular_nombre"])
        m.Afiliado.objects.filter(pk=self.a.pk).update(numero_interno="000184")
        params = {"search": "000184", "estado": "todos"}
        listado = self.client.get(f"/api/financiadores/{self.org.pk}/padron/", params)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["count"], 1)
        fila = listado.data["results"][0]
        self.assertEqual((fila["numero_interno"], fila["numero"]), ("000184", "00025"))
        hoja = self.libro(params)["Padrón"]
        self.assertEqual(hoja.cell(2, 2).value, "000184")
        self.assertEqual(hoja.cell(2, 2).data_type, "s")
        self.assertEqual(hoja.cell(2, 3).value, "00025")
        self.assertIsNone(fila["titular_nombre"])
        self.assertIsNone(hoja.cell(2, 11).value)
        # Las selecciones anteriores conservan únicamente las columnas pedidas.
        self.assertEqual(list(self.libro({**params, "columnas": "nombre,numero"})["Padrón"].values)[0], ("Afiliado", "N.º de afiliado"))

    def test_titular_registrado_coincide_y_vinculo_ajeno_no_expone_nombre(self):
        titular = m.Afiliado.objects.create(financiador=self.org, numero="T184", documento="99018402", nombre="Titular ficticio 184", desde=timezone.localdate())
        m.Afiliado.objects.filter(pk=self.a.pk).update(titular=titular)
        params = {"columnas": "nombre,numero,titular_nombre", "flt_titular_nombre": "Titular ficticio", "ordering": "titular_nombre", "estado": "todos"}
        url = f"/api/financiadores/{self.org.pk}/padron/"
        listado = self.client.get(url, params)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["count"], 1)
        self.assertEqual(listado.data["results"][0]["titular_nombre"], titular.nombre)
        self.assertEqual(self.proyeccion_ui(listado.data["results"], ["nombre", "numero", "titular_nombre"]), [list(list(self.libro(params)["Padrón"].values)[1])])
        # Simula un FK legado inconsistente; no se deduce ni corrige parentesco.
        ajeno = m.Afiliado.objects.get(financiador=self.otra)
        m.Afiliado.objects.filter(pk=self.a.pk).update(titular=ajeno)
        params["flt_titular_nombre"] = ajeno.nombre
        self.assertEqual(self.client.get(url, params).data["count"], 0)
        params.pop("flt_titular_nombre")
        listado = self.client.get(url, params)
        propia = next(f for f in listado.data["results"] if f["id"] == self.a.pk)
        self.assertIsNone(propia["titular_nombre"])
        self.assertNotIn(ajeno.nombre, str(listado.data))
        self.assertNotIn(ajeno.nombre, str(list(self.libro(params)["Padrón"].values)))

    def test_titular_nombre_solo_lectura_y_sin_consulta_por_fila(self):
        from .padron_consulta import consultar_padron
        from .serializers import AfiliadoSerializer
        titular = m.Afiliado.objects.create(financiador=self.org, numero="T185", documento="99018403", nombre="Titular ficticio común", desde=timezone.localdate())
        m.Afiliado.objects.filter(pk=self.a.pk).update(titular=titular)
        for i in range(4):
            m.Afiliado.objects.create(financiador=self.org, numero=f"H184{i}", documento=f"9901841{i}", nombre=f"Integrante ficticio {i}", titular=titular, desde=timezone.localdate())
        qs = consultar_padron(financiador=self.org, parametros={"estado": "todos"})
        with CaptureQueriesContext(connection) as consultas:
            filas = AfiliadoSerializer(qs, many=True).data
        self.assertEqual(len(consultas), 1)
        self.assertEqual(sum(f["titular_nombre"] == titular.nombre for f in filas), 5)
        serializer = AfiliadoSerializer(self.a, data={"titular_nombre": "No escribir", "numero_interno": "No renumerar"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("titular_nombre", serializer.validated_data)
        self.assertNotIn("numero_interno", serializer.validated_data)
