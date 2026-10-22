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
from rest_framework.test import APITestCase

from . import models as m
from . import test_padron_exportacion as base_exportacion


@skipUnless(hasattr(m.Afiliado, "cobertura_habilitada"), "Requiere integrar #186")
class ContrasteIssue184Tests(APITestCase):
    # Reusar exactamente los datos ficticios y controles del exportador existente.
    setUp = base_exportacion.ExportacionPadronTests.setUp
    libro = base_exportacion.ExportacionPadronTests.libro

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
        # Ejecutar el formateador productivo real, no una copia Python de su lógica.
        helper = Path(__file__).resolve().parents[3] / "frontend/src/components/financiadores/padronTablaEstado.js"
        script = """
import { readFileSync } from 'node:fs';
const { COLUMNAS_PADRON, valorColumnaPadron } = await import(process.argv[1]);
const { filas, columnas } = JSON.parse(readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(filas.map(fila => columnas.map(key =>
  valorColumnaPadron(fila, COLUMNAS_PADRON.find(c => c.key === key))))));
"""
        resultado = subprocess.run(
            ["node", "--input-type=module", "-e", script, helper.as_uri()],
            input=json.dumps({"filas": listado.data["results"], "columnas": columnas}),
            text=True, capture_output=True, check=True, encoding="utf-8")
        self.assertEqual(json.loads(resultado.stdout), filas_xlsx)
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
