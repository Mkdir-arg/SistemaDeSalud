"""AUD-007: el cliente real no copia identificadores al log de errores."""
import json
import unittest
from http.client import HTTPException
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from apps.fhir import cliente


class PrivacidadLogFHIRTests(unittest.TestCase):
    def test_fallos_no_registran_url_documento_ni_mensaje_del_proveedor(self):
        marcador = "DOCUMENTO_FICTICIO_PRIVADO"
        base = "https://padron.example.test/ruta-privada"
        casos = (
            (HTTPError(base, 401, marcador, {}, None), "no_autorizado", "401"),
            (HTTPError(base, 503, marcador, {}, None), "sin_conexion", "503"),
            (URLError(marcador), "sin_conexion", "URLError"),
            (TimeoutError(marcador), "sin_conexion", "TimeoutError"),
            (OSError(marcador), "sin_conexion", "OSError"),
            (HTTPException(marcador), "sin_conexion", "HTTPException"),
        )
        for error, esperado, diagnostico in casos:
            with self.subTest(error=type(error).__name__, motivo=esperado):
                with patch.object(cliente, "urlopen", side_effect=error):
                    with self.assertLogs(cliente.log, level="INFO") as registro:
                        self.assertEqual(cliente.buscar_paciente_con_motivo(base, marcador), (None, esperado))
                texto = " ".join(registro.output)
                self.assertNotIn(marcador, texto)
                self.assertNotIn(base, texto)
                self.assertNotIn("identifier", texto)
                self.assertIn(diagnostico, texto)

    def test_json_invalido_no_registra_identificador_ni_contenido(self):
        marcador = "CONTENIDO_FICTICIO_PRIVADO"
        respuesta = MagicMock()
        respuesta.__enter__.return_value.read.return_value = marcador.encode()
        with patch.object(cliente, "urlopen", return_value=respuesta):
            with self.assertLogs(cliente.log, level="INFO") as registro:
                self.assertEqual(
                    cliente.buscar_paciente_con_motivo("https://padron.example.test", marcador),
                    (None, "respuesta_invalida"),
                )
        texto = " ".join(registro.output)
        self.assertNotIn(marcador, texto)
        self.assertNotIn("https://", texto)
        self.assertIn("JSONDecodeError", texto)

    def test_exito_conserva_patient_y_documento_en_consulta_sin_log(self):
        patient = {"resourceType": "Patient", "id": "ficticio"}
        respuesta = MagicMock()
        respuesta.__enter__.return_value.read.return_value = json.dumps(patient).encode()
        with patch.object(cliente, "urlopen", return_value=respuesta) as abrir:
            with patch.object(cliente.log, "info") as log:
                self.assertEqual(
                    cliente.buscar_paciente_con_motivo("https://padron.example.test", "DOC_FICTICIO"),
                    (patient, None),
                )
        self.assertIn("identifier=DOC_FICTICIO", abrir.call_args.args[0].full_url)
        log.assert_not_called()
