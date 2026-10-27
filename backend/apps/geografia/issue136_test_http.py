"""Rutas, permisos y cuerpos HTTP con DB sintética; no abre sockets ni usa JWT reales."""
from datetime import date
from io import BytesIO
from unittest.mock import patch

from openpyxl import load_workbook
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.financiadores.models import Afiliado, Financiador, MembresiaFinanciador
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano
from .models import Lugar
from .servicios import ambito, resolver


class GeografiaHTTPTest(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Institución HTTP ficticia")
        self.otra = Institucion.objects.create(nombre="Otra institución HTTP ficticia")
        self.usuario = Usuario.objects.create_user("http136@example.invalid")
        self.membresia = Membresia.objects.create(usuario=self.usuario, institucion=self.inst, rol="medico")
        self.fin = Financiador.objects.create(nombre="Financiador HTTP ficticio", tipo="mutual")
        self.otro_fin = Financiador.objects.create(nombre="Otro financiador HTTP ficticio", tipo="mutual")
        self.miembro_fin = MembresiaFinanciador.objects.create(usuario=self.usuario, financiador=self.fin, rol="operador")
        self.geo = resolver({"localidad": {"manual": "Lugar privado HTTP ficticio"}}, dueno=ambito(institucion_id=self.inst.pk))
        self.paciente = Ciudadano.objects.create(institucion=self.inst, nombre="Paciente HTTP ficticio",
            documento="99900136", domicilio="Calle ficticia 136", geografia=self.geo)
        self.client.force_authenticate(self.usuario)

    def test_consulta_manual_autenticada_aislada_y_revocada(self):
        url = "/api/geografia/lugares/"
        params = {"tipo": "localidad", "ambito": "institucion", "organizacion": self.inst.pk}
        self.assertEqual(self.client.get(url, params).data["results"][0]["id"], self.geo.localidad_id)
        self.assertEqual(self.client.get(url, {**params, "organizacion": self.otra.pk}).status_code, 403)
        self.membresia.activo = False
        self.membresia.save()
        self.assertEqual(self.client.get(url, params).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url, params).status_code, 403)

    def test_guardado_y_reapertura_rechazan_referencias_manuales_ajenas(self):
        ajena = resolver({"localidad": {"manual": "Lugar ajeno ficticio"}}, dueno=ambito(institucion_id=self.otra.pk))
        url = f"/api/ciudadanos/{self.paciente.pk}/"
        respuesta = self.client.patch(url, {"geografia": {"localidad": {"id": ajena.localidad_id}}}, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.paciente.refresh_from_db()
        self.assertEqual(self.paciente.geografia_id, self.geo.pk)
        respuesta = self.client.patch(url, {"geografia": {"localidad": {"manual": "Otro lugar propio ficticio"}}}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        lectura = self.client.get(url)
        self.assertEqual(lectura.status_code, 200, lectura.data)
        self.assertEqual(lectura.data["geografia"]["localidad"]["origen"], "manual")
        self.assertEqual(lectura.data["geografia"]["localidad"]["nombre"], "Otro lugar propio ficticio")
        self.assertIn("no-store", lectura["Cache-Control"])
        listado = self.client.get("/api/ciudadanos/", {"institucion": self.inst.pk})
        self.assertNotIn("geografia", listado.data["results"][0])
        self.assertNotIn("Calle ficticia", str(listado.data))

    def test_csv_identificado_con_motivo_y_minimizado_sin_geografia(self):
        url = "/api/ciudadanos/exportar/"
        entrada = {"institucion": self.inst.pk, "variante": "identificado", "motivo": "Prueba sintética de exportación geográfica"}
        respuesta = self.client.post(url, entrada, format="json")
        self.assertEqual(respuesta.status_code, 200, getattr(respuesta, "data", ""))
        csv = b"".join(respuesta.streaming_content).decode("utf-8-sig")
        self.assertIn("Lugar privado HTTP ficticio (Manual · sin verificar)", csv)
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertTrue(AccesoClinico.objects.filter(usuario=self.usuario, tipo="exportacion", variante="identificado").exists())
        minimizada = self.client.post(url, {**entrada, "variante": "minimizado"}, format="json")
        self.assertEqual(minimizada.status_code, 200)
        contenido = b"".join(minimizada.streaming_content).decode("utf-8-sig")
        self.assertNotIn("Lugar privado", contenido)
        self.assertNotIn("Calle ficticia", contenido)
        self.membresia.rol = "administrativo"
        self.membresia.save()
        self.assertEqual(self.client.post(url, entrada, format="json").status_code, 403)
        self.assertEqual(self.client.post(url, {**entrada, "institucion": self.otra.pk}, format="json").status_code, 403)

    def test_fallo_auditoria_no_entrega_csv(self):
        with patch("apps.registros.views.registrar_acceso", side_effect=RuntimeError("Falla sintética")):
            respuesta = self.client.post("/api/ciudadanos/exportar/", {"institucion": self.inst.pk,
                "variante": "identificado", "motivo": "Prueba sintética de auditoría fallida"}, format="json")
        self.assertEqual(respuesta.status_code, 503)
        self.assertFalse(respuesta.streaming)
        self.assertNotIn("Lugar privado", str(respuesta.data))

    def test_fhir_conserva_procedencia_y_scope_institucional(self):
        url = f"/fhir/Patient/{self.paciente.pk}"
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertIn("Manual · sin verificar", respuesta.json()["address"][0]["text"])
        ajeno = Usuario.objects.create_user("ajeno136@example.invalid")
        Membresia.objects.create(usuario=ajeno, institucion=self.otra, rol="medico")
        self.client.force_authenticate(ajeno)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_xlsx_manual_filtrado_y_auditor_sin_escritura(self):
        geo = resolver({"localidad": {"manual": "Localidad financiador ficticia"}}, dueno=ambito(financiador_id=self.fin.pk))
        afiliado = Afiliado.objects.create(financiador=self.fin, numero="00136", documento="99900137",
            nombre="Persona HTTP ficticia", desde=date(2026, 1, 1), localidad="Localidad financiador ficticia", geografia=geo)
        url = f"/api/financiadores/{self.fin.pk}/padron/"
        respuesta = self.client.get(url + "exportar/", {"columnas": "nombre,numero,localidad", "search": "Persona HTTP"})
        self.assertEqual(respuesta.status_code, 200, getattr(respuesta, "data", ""))
        filas = list(load_workbook(BytesIO(respuesta.content))["Padrón"].values)
        self.assertEqual(filas[1:], [("Persona HTTP ficticia", "00136", "Localidad financiador ficticia · Manual · sin verificar")])
        self.assertIn("no-store", respuesta["Cache-Control"])
        self.assertEqual(self.client.get(f"/api/financiadores/{self.otro_fin.pk}/padron/exportar/").status_code, 404)
        self.miembro_fin.rol = "auditor"
        self.miembro_fin.save()
        respuesta = self.client.patch(url + f"{afiliado.pk}/", {"revision": afiliado.revision,
            "motivo": "Prueba sintética de permisos", "geografia": {"localidad": {"manual": "No debe crearse"}}}, format="json")
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertFalse(Lugar.objects.filter(nombre="No debe crearse").exists())


class TrasladoGeografiaHTTPTest(APITestCase):
    # Reutiliza el fixture y constructores de la prueba HTTP existente, sin heredar sus tests.
    from apps.red.tests_api import TrasladosAPITests as _Base
    _usuario = _Base._usuario
    _flujo = _Base._flujo
    _caso = _Base._caso
    _como = _Base._como
    _solicitar = _Base._solicitar

    def setUp(self):
        self._Base.setUp(self)
        paciente = self.caso.ciudadano
        paciente.geografia = resolver({"localidad": {"manual": "Lugar privado del origen ficticio"}}, dueno=ambito(institucion_id=self.hosp.pk))
        paciente.domicilio = "Calle de traslado ficticia"
        paciente.save()

    def test_ciclo_completo_preserva_procedencia_sin_compartir_sugerencias(self):
        from apps.red.models import Traslado
        from apps.casos.models import Caso

        respuesta = self._solicitar()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        pk = respuesta.data["id"]
        self._como(self.med)
        self.assertEqual(self.client.post(f"/api/traslados/{pk}/aceptar/").status_code, 403)
        self._como(self.jefe)
        aceptada = self.client.post(f"/api/traslados/{pk}/aceptar/", {"area_destino": self.uti.pk})
        self.assertEqual(aceptada.status_code, 200, aceptada.data)
        traslado = Traslado.objects.get(pk=pk)
        destino = traslado.caso_destino.ciudadano
        self.assertIsNone(destino.geografia.localidad_id)
        self.assertEqual(destino.geografia.datos()["localidad"]["origen"], "manual")
        self.assertEqual(destino.domicilio, "Calle de traslado ficticia")
        self.assertFalse(Lugar.objects.filter(origen="manual", institucion=self.centro).exists())
        self._como(self.med)
        salida = self.client.post(f"/api/traslados/{pk}/en-camino/", {"movil": "Móvil ficticio 136"})
        self.assertEqual(salida.status_code, 200, salida.data)
        self._como(self.jefe)
        llegada = self.client.post(f"/api/traslados/{pk}/recibido/")
        self.assertEqual(llegada.status_code, 200, llegada.data)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.DERIVADO)
