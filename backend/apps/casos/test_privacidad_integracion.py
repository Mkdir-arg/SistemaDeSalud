"""AUD-008: persistir respuesta funcional sin copiarla a trazabilidad general."""
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.casos import motor
from apps.casos.models import Caso, EventoCaso, ValorCampo
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Institucion


@override_settings(INTEGRACIONES_PERMITIDAS=["servicio.example.test"])
class PrivacidadEventoIntegracionTests(TestCase):
    def test_valor_recibido_se_guarda_sin_copiarse_al_evento(self):
        institucion = Institucion.objects.create(nombre="Hospital ficticio")
        flujo = Flujo.objects.create(institucion=institucion, titulo="Integración ficticia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(institucion=institucion, version=version)
        formulario = Formulario.objects.create(institucion=institucion, titulo="Datos")
        campo = Campo.objects.create(formulario=formulario, label="Resultado", tipo="texto_largo")
        nodo = Nodo.objects.create(
            version=version, tipo="integracion", titulo="Consultar resultado",
            config={"url": "https://servicio.example.test/resultado", "guardar_en": campo.pk, "ruta": "resultado"},
        )
        for valor in ("DIAGNOSTICO_FICTICIO_PRIVADO", {"dato": "DATOS_FICTICIOS_PRIVADOS"}, None):
            with self.subTest(tipo=type(valor).__name__):
                respuesta = MagicMock()
                respuesta.__enter__.return_value.read.return_value = json.dumps({"resultado": valor}).encode()
                with patch.object(motor, "urlopen", return_value=respuesta):
                    motor._llamar_externo(caso, nodo)
                guardado = ValorCampo.objects.get(caso=caso, campo=campo)
                self.assertEqual(guardado.valor, "" if valor is None else str(valor))
                evento = EventoCaso.objects.filter(caso=caso).last()
                self.assertEqual(evento.detalle, f"dato recibido para campo #{campo.pk}")
                self.assertEqual(evento.nodo_id, nodo.pk)
                self.assertEqual(evento.titulo, nodo.titulo)
                if valor is not None:
                    self.assertNotIn(str(valor), evento.detalle)
