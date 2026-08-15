"""
Editar un campo de un formulario.

Los formularios de un hospital cambian solos: entra una obra social nueva, el
nivel de triage suma una categoría, alguien tipeó «Tensión artrial» y quedó así
en la pantalla que ve el administrativo todo el día. Hasta acá la única llamada a
`/campos/` desde la aplicación era crear y borrar, y el mensaje del borrado
mandaba a «editá la etiqueta o las opciones» — algo que ninguna pantalla ofrecía.
Las dos salidas reales eran crear un campo duplicado («Obra social 2»), con lo
cual las Decisiones que apuntan al viejo dejan de encontrar el dato, o entrar por
el admin de Django.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.casos.models import Caso, ValorCampo
from apps.flujos.models import Flujo, VersionFlujo
from apps.instituciones.models import Institucion

from .models import Campo, Formulario


class EditarCampoTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user(
            email="config@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Admisión")
        self.campo = Campo.objects.create(
            formulario=self.form,
            label="Obra social",
            tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["OSDE", "PAMI"],
            orden=0,
        )

    def _con_un_valor_cargado(self):
        flujo = Flujo.objects.create(institucion=self.inst, titulo="Ingreso")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(institucion=self.inst, version=version)
        ValorCampo.objects.create(caso=caso, campo=self.campo, valor="OSDE")

    def test_se_agrega_una_obra_social_a_las_opciones_sin_rehacer_el_campo(self):
        """Rehacer el campo rompe las Decisiones que lo miran: apuntan al id viejo."""
        r = self.client.patch(
            f"/api/campos/{self.campo.pk}/",
            {"opciones": ["OSDE", "PAMI", "Swiss Medical"]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.opciones, ["OSDE", "PAMI", "Swiss Medical"])

    def test_se_corrige_la_etiqueta_aunque_el_campo_ya_tenga_datos(self):
        """Es justo lo que el error del borrado manda a hacer: no puede estar prohibido."""
        self._con_un_valor_cargado()
        r = self.client.patch(
            f"/api/campos/{self.campo.pk}/", {"label": "Cobertura"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.label, "Cobertura")

    def test_se_reordenan_los_campos(self):
        """El orden es el de la pantalla que completa el administrativo."""
        otro = Campo.objects.create(
            formulario=self.form, label="Documento", tipo=Campo.Tipo.TEXTO_CORTO, orden=1
        )
        self.client.patch(f"/api/campos/{self.campo.pk}/", {"orden": 1}, format="json")
        self.client.patch(f"/api/campos/{otro.pk}/", {"orden": 0}, format="json")
        r = self.client.get(f"/api/formularios/{self.form.pk}/")
        self.assertEqual([c["label"] for c in r.data["campos"]], ["Documento", "Obra social"])

    def test_no_se_le_cambia_el_tipo_a_un_campo_que_ya_tiene_datos(self):
        """Los valores se guardan como texto y quedarían sin significado.

        «Rojo - Emergencia» mostrado en un campo fecha, y las Decisiones que
        comparaban ese campo mandando los casos por la rama que no era.
        """
        self._con_un_valor_cargado()
        r = self.client.patch(
            f"/api/campos/{self.campo.pk}/", {"tipo": "fecha"}, format="json"
        )
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(int(r.data["valores"]), 1)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.tipo, Campo.Tipo.SELECCION_UNICA)

    def test_sin_datos_cargados_el_tipo_todavia_se_puede_cambiar(self):
        """Un campo recién creado con el tipo equivocado no obliga a rehacerlo."""
        r = self.client.patch(
            f"/api/campos/{self.campo.pk}/", {"tipo": "texto_corto"}, format="json"
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.campo.refresh_from_db()
        self.assertEqual(self.campo.tipo, Campo.Tipo.TEXTO_CORTO)

    def test_el_campo_con_datos_no_se_borra_y_dice_cuantos_hay(self):
        """`ValorCampo.campo` es CASCADE: el borrado se llevaría el registro asistencial.

        La pantalla promete lo contrario («los datos ya cargados no se borran»),
        así que este 409 es lo único que sostiene esa promesa.
        """
        self._con_un_valor_cargado()
        r = self.client.delete(f"/api/campos/{self.campo.pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(int(r.data["valores"]), 1)
        self.assertTrue(Campo.objects.filter(pk=self.campo.pk).exists())

    def test_el_serializer_dice_cuantos_valores_cuelgan_del_campo(self):
        """Es el dato con el que la pantalla puede avisar ANTES de ofrecer el borrado."""
        self._con_un_valor_cargado()
        r = self.client.get(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.data["campos"][0]["valores_cargados"], 1)
