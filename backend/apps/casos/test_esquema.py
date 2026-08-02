"""
El esquema OpenAPI de la API.

Un esquema que existe pero miente es peor que no tenerlo: quien integra escribe
contra lo que dice el documento y descubre la diferencia en producción. Estos
tests no revisan que el esquema sea lindo, sino que sea CIERTO y que no se
degrade solo cuando alguien agregue un endpoint.
"""
import io

from django.core.management import call_command
from django.test import TestCase, override_settings
from drf_spectacular.drainage import GENERATOR_STATS
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario


class EsquemaTests(TestCase):
    def _generar(self):
        """
        Genera el esquema y devuelve (yaml, problemas).

        Los avisos NO salen por el stderr del comando —drf-spectacular los junta
        en su propio acumulador y los imprime aparte—, así que leerlos de ahí
        daba siempre vacío y el test pasaba con el esquema roto. Se lee el
        acumulador, que es donde realmente están.
        """
        salida = io.StringIO()
        GENERATOR_STATS.reset()
        call_command("spectacular", stdout=salida, stderr=io.StringIO())
        problemas = (
            [f"aviso: {m}" for m in GENERATOR_STATS._warn_cache]
            + [f"error: {m}" for m in GENERATOR_STATS._error_cache]
        )
        return salida.getvalue(), problemas

    def test_se_genera_sin_errores_ni_avisos(self):
        """
        Guarda contra la degradación silenciosa.

        Un `SerializerMethodField` sin anotar se documenta como texto: un
        booleano anunciado como string hace que del otro lado escriban
        `if resp["puede_tomar"] == "true"`, que con un booleano de verdad es
        siempre falso. Y una vista que arma su respuesta a mano queda
        directamente AFUERA del esquema, sin que nada avise.
        """
        _, problemas = self._generar()
        self.assertEqual(problemas, [], "el esquema se generó con problemas")

    def test_documenta_la_api_entera(self):
        yaml, _ = self._generar()
        for ruta in [
            "/api/casos/",
            "/api/casos/{id}/llamar/",
            "/api/casos/{id}/ausente/",
            "/api/casos/{id}/devolver/",
            "/api/items-fila/{id}/mover/",
            "/api/flujos/",
            "/api/ciudadanos/",
            "/api/pantalla/{token}/",   # la arma a mano: se documenta aparte
            "/api/mis-tareas/",
        ]:
            with self.subTest(ruta=ruta):
                self.assertIn(f"  {ruta}:", yaml, f"{ruta} no está en el esquema")

    def test_dice_que_hace_falta_un_token(self):
        yaml, _ = self._generar()
        self.assertIn("jwtAuth", yaml)
        self.assertIn("bearerFormat: JWT", yaml)

    def test_la_pantalla_de_sala_figura_como_publica(self):
        """
        Corre en un televisor: no hay quien inicie sesión ahí. El esquema tiene
        que decirlo, porque es lo único que explica por qué ese endpoint no pide
        token — y que el token de la URL es lo único que lo protege.

        El esquema no declara `security` a nivel raíz: lo pone operación por
        operación. Entonces «esta operación es pública» se escribe omitiéndolo,
        no con un `security: []`. Se verifica las dos mitades: que no haya
        default global (si lo hubiera, la omisión significaría lo contrario) y
        que esta operación no exija token.
        """
        yaml, _ = self._generar()
        self.assertNotIn("\nsecurity:", yaml, "hay un security global: revisar este test")
        i = yaml.index("/api/pantalla/{token}/")
        bloque = yaml[i:yaml.index("\n  /api/", i + 1)]
        self.assertNotIn("jwtAuth", bloque, "el esquema dice que la pantalla de sala pide token")
        self.assertIn("Sin autenticación", bloque)

    def test_el_resto_de_la_api_si_exige_token(self):
        """La contracara: que «público» sea la excepción y no el descuido."""
        yaml, _ = self._generar()
        for ruta in ["/api/casos/", "/api/ciudadanos/", "/api/usuarios/"]:
            with self.subTest(ruta=ruta):
                i = yaml.index(f"  {ruta}:")
                self.assertIn("jwtAuth", yaml[i:yaml.index("\n  /api/", i + 1)])


class DocsTests(APITestCase):
    """Las dos URLs que se le pasan a quien tiene que integrar."""

    def setUp(self):
        self.client.force_authenticate(
            Usuario.objects.create_user("dev@test.local", "x", is_superuser=True, is_staff=True)
        )

    def test_en_produccion_no_se_sirve_a_cualquiera(self):
        """
        El esquema no tiene datos, pero sí el mapa completo de la API. Dárselo a
        cualquiera que llegue al servidor le ahorra medio trabajo a quien busque
        por dónde entrar, y no le sirve a nadie más: quien integra tiene
        credenciales. En desarrollo queda abierto a propósito.
        """
        self.client.force_authenticate(None)
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get("/api/esquema/").status_code, 401)
            self.assertEqual(self.client.get("/api/docs/").status_code, 401)

    def test_el_esquema_se_sirve(self):
        r = self.client.get("/api/esquema/")
        self.assertEqual(r.status_code, 200)

    def test_el_visor_se_sirve(self):
        r = self.client.get("/api/docs/")
        self.assertEqual(r.status_code, 200)
