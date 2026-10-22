"""AUD-005 parcial: transporte real no sigue redirects, sin red externa."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.casos import motor
from apps.casos.models import Caso, EventoCaso
from apps.fhir import cliente
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano


@override_settings(INTEGRACIONES_PERMITIDAS=["127.0.0.1"], INTEGRACIONES_TIMEOUT=2)
class RedireccionesIntegracionAuditoria172Tests(TestCase):
    def setUp(self):
        self.destinos = []
        self.origenes = []
        self.codigo = 200
        prueba = self
        paciente = {"resourceType": "Patient", "id": "paciente-sintetico"}
        cuerpo = json.dumps(paciente).encode()

        class Silencioso(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

        class Destino(Silencioso):
            def do_GET(self):
                prueba.destinos.append((self.command, self.path))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(cuerpo)

            do_POST = do_GET

        destino = ThreadingHTTPServer(("127.0.0.1", 0), Destino)
        self.location = f"http://localhost:{destino.server_port}/destino?dato=PII_SINTETICA"

        class Origen(Silencioso):
            def do_GET(self):
                longitud = int(self.headers.get("Content-Length", 0))
                if longitud:
                    self.rfile.read(longitud)
                prueba.origenes.append((self.command, self.path))
                self.send_response(prueba.codigo)
                if prueba.codigo != 200:
                    self.send_header("Location", prueba.location)
                self.end_headers()
                if prueba.codigo == 200:
                    self.wfile.write(cuerpo)

            do_POST = do_GET

        origen = ThreadingHTTPServer(("127.0.0.1", 0), Origen)
        for servidor in (destino, origen):
            hilo = Thread(target=servidor.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
            hilo.start()
            self.addCleanup(hilo.join, 3)
            self.addCleanup(servidor.server_close)
            self.addCleanup(servidor.shutdown)
        self.url = f"http://127.0.0.1:{origen.server_port}/origen?dato=PII_ORIGEN"
        ambiente = patch.dict(os.environ, {"no_proxy": "127.0.0.1,localhost", "NO_PROXY": "127.0.0.1,localhost"})
        ambiente.start()
        self.addCleanup(ambiente.stop)
        institucion = Institucion.objects.create(nombre="Institución integración sintética")
        flujo = Flujo.objects.create(institucion=institucion, titulo="Flujo sintético")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        paciente = Ciudadano.objects.create(institucion=institucion, nombre="Paciente", documento="12345678")
        self.caso = Caso.objects.create(institucion=institucion, version=version, ciudadano=paciente)

    def nodo(self, **config):
        return Nodo.objects.create(version=self.caso.version, tipo="integracion", titulo="Consulta sintética", config=config)

    def test_generico_get_y_post_no_contactan_destino_en_cinco_redirects(self):
        self.assertTrue(motor._host_permitido(self.url))
        self.assertFalse(motor._host_permitido(self.location))
        for metodo in ("GET", "POST"):
            for codigo in (301, 302, 303, 307, 308):
                with self.subTest(metodo=metodo, codigo=codigo):
                    self.destinos.clear()
                    self.codigo = codigo
                    nodo = self.nodo(url=self.url, metodo=metodo, cuerpo={"dato": "CUERPO_SINTETICO"})
                    antes = len(self.origenes)
                    motor._llamar_externo(self.caso, nodo)
                    self.assertEqual(len(self.origenes), antes + 1)
                    self.assertEqual(self.destinos, [])
                    evento = EventoCaso.objects.filter(caso=self.caso).last()
                    self.assertIn("Integración fallida", evento.titulo)
                    for privado in (self.url, self.location, "PII_", "CUERPO_SINTETICO"):
                        self.assertNotIn(privado, evento.detalle)

    def test_fhir_no_contacta_destino_y_no_loguea_url_ni_location(self):
        for codigo in (301, 302, 303, 307, 308):
            with self.subTest(codigo=codigo):
                self.destinos.clear()
                self.codigo = codigo
                with self.assertLogs("apps.fhir.cliente", level="INFO") as mensajes:
                    paciente, motivo = cliente.buscar_paciente_con_motivo(self.url, "DNI_SINTETICO")
                self.assertIsNone(paciente)
                self.assertEqual(motivo, "sin_conexion")
                self.assertEqual(self.destinos, [])
                texto = " ".join(mensajes.output)
                for privado in (self.url, self.location, "DNI_SINTETICO", "PII_"):
                    self.assertNotIn(privado, texto)

    def test_modo_fhir_motor_pasa_allowlist_pero_rechaza_redirect(self):
        self.codigo = 302
        motor._llamar_externo(self.caso, self.nodo(url=self.url, fhir="Patient"))
        self.assertEqual(len(self.origenes), 1)
        self.assertEqual(self.destinos, [])
        self.assertIn("Integración fallida", EventoCaso.objects.filter(caso=self.caso).last().titulo)

    def test_respuestas_200_legitimas_generica_y_fhir_siguen_funcionando(self):
        for metodo in ("GET", "POST"):
            motor._llamar_externo(self.caso, self.nodo(url=self.url, metodo=metodo, cuerpo={"dato": "sintético"}))
            self.assertEqual(EventoCaso.objects.filter(caso=self.caso).last().detalle, "consulta realizada")
        paciente, motivo = cliente.buscar_paciente_con_motivo(self.url, "DNI_SINTETICO")
        self.assertEqual(paciente["resourceType"], "Patient")
        self.assertIsNone(motivo)
        self.assertEqual(len(self.origenes), 3)
        self.assertEqual(self.destinos, [])

    def test_redirect_obligatorio_conserva_error_controlado_y_no_contacta_destino(self):
        self.codigo = 302
        with self.assertRaises(motor.ErrorMotor):
            motor._llamar_externo(self.caso, self.nodo(url=self.url, obligatorio=True))
        self.assertEqual(self.destinos, [])

    def test_handler_cierra_origen_y_no_conserva_datos_en_excepcion(self):
        from urllib.error import HTTPError
        from urllib.request import Request
        from apps.http_seguro import _SinRedirecciones

        class Respuesta:
            cerrada = False

            def close(self):
                self.cerrada = True

        for codigo in (301, 302, 303, 307, 308):
            with self.subTest(codigo=codigo):
                respuesta = Respuesta()
                handler = getattr(_SinRedirecciones(), f"http_error_{codigo}")
                with self.assertRaises(HTTPError) as error:
                    handler(Request(self.url), respuesta, codigo, "PII_RAZON",
                            {"Location": self.location, "X-Dato": "PII_HEADER"})
                self.assertTrue(respuesta.cerrada)
                self.assertEqual(error.exception.code, codigo)
                self.assertEqual(error.exception.url, "")
                self.assertIsNone(error.exception.headers)
                self.assertNotIn("PII_", str(error.exception))
                self.assertNotIn(self.location, str(error.exception))
