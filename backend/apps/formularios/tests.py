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


class FormularioEnUsoTests(APITestCase):
    """Editar, duplicar, reordenar y borrar el formulario entero.

    Nada de esto se podía hacer desde la aplicación: el alta pedía sólo el título
    y después quedaba fijo para siempre —la columna «Descripción» del listado sólo
    podía decir «—» y el área nunca se cargaba, aunque el filtro por área exista—,
    no había forma de saber en qué flujos se usaba, y un formulario creado por
    error se quedaba ahí. La única salida era el admin de Django.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.otra = Institucion.objects.create(nombre="Hospital del Norte")
        self.user = Usuario.objects.create_user(
            email="config2@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.c1 = Campo.objects.create(
            formulario=self.form, label="Motivo", tipo=Campo.Tipo.TEXTO_LARGO, orden=0
        )
        self.c2 = Campo.objects.create(
            formulario=self.form, label="Temperatura", tipo=Campo.Tipo.NUMERO,
            unidad="°C", minimo=30, maximo=45, orden=1,
        )
        self.c3 = Campo.objects.create(
            formulario=self.form, label="Documento", tipo=Campo.Tipo.TEXTO_CORTO, orden=2
        )

    def _asignado_a_un_paso(self, estado=VersionFlujo.Estado.PUBLICADA):
        from apps.flujos.models import Nodo

        flujo = Flujo.objects.create(institucion=self.inst, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1, estado=estado)
        nodo = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage inicial",
            formulario=self.form, x=0, y=0,
        )
        return flujo, version, nodo

    # --- metadatos ------------------------------------------------------- #
    def test_se_corrige_el_titulo_y_se_carga_la_descripcion(self):
        """Un «Admision de pacinetes» mal tipeado se ve en cada paso que lo usa."""
        r = self.client.patch(
            f"/api/formularios/{self.form.pk}/",
            {"titulo": "Triage de enfermería", "descripcion": "Clasificación inicial."},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.form.refresh_from_db()
        self.assertEqual(self.form.titulo, "Triage de enfermería")
        self.assertEqual(self.form.descripcion, "Clasificación inicial.")

    def test_el_area_tiene_que_ser_de_la_misma_institucion(self):
        """Un área de otro hospital lo hace aparecer en un filtro que no lo puede usar."""
        from apps.instituciones.models import Area

        ajena = Area.objects.create(institucion=self.otra, nombre="Guardia del Norte")
        r = self.client.patch(
            f"/api/formularios/{self.form.pk}/", {"area": ajena.pk}, format="json"
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.form.refresh_from_db()
        self.assertIsNone(self.form.area_id)

    # --- dónde se usa ---------------------------------------------------- #
    def test_usos_dice_en_que_paso_de_que_flujo_se_pide_y_cuantos_casos_hay_ahi(self):
        """Es lo que faltaba para tocar un campo requerido con criterio: los casos
        parados en ese paso no pueden avanzar hasta que alguien lo complete."""
        flujo, version, nodo = self._asignado_a_un_paso()
        Caso.objects.create(institucion=self.inst, version=version, nodo_actual=nodo)
        Caso.objects.create(
            institucion=self.inst, version=version, nodo_actual=nodo, estado=Caso.Estado.CERRADO
        )

        r = self.client.get(f"/api/formularios/{self.form.pk}/usos/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data["usos"]), 1)
        uso = r.data["usos"][0]
        self.assertEqual(uso["flujo"], "Guardia")
        self.assertEqual(uso["nodo_titulo"], "Triage inicial")
        self.assertEqual(uso["version_estado"], "publicada")
        # El caso cerrado no cuenta: no está esperando que nadie complete nada.
        self.assertEqual(uso["casos_activos"], 1)

    def test_usos_nombra_la_rama_de_decision_que_compara_un_campo(self):
        """Quitar el campo no rompe ninguna FK, así que el servidor no puede
        rechazarlo: la condición queda apuntando a un id que no existe y la rama
        no se cumple nunca. La pantalla tiene que poder decir cuál."""
        from apps.flujos.models import Conexion, Nodo

        flujo, version, nodo = self._asignado_a_un_paso()
        decision = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.DECISION, titulo="¿Fiebre?", x=1, y=1
        )
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Alta", x=2, y=2)
        Conexion.objects.create(
            version=version, origen=decision, destino=fin, etiqueta="con fiebre",
            condicion={"campo": self.c2.pk, "operador": ">", "valor": "38"},
        )

        r = self.client.get(f"/api/formularios/{self.form.pk}/usos/")
        self.assertEqual(
            [(c["campo_id"], c["etiqueta"]) for c in r.data["condiciones"]],
            [(self.c2.pk, "con fiebre")],
        )

    def test_usos_encuentra_la_regla_aunque_este_en_otro_flujo(self):
        """El constructor de reglas ofrece los campos de TODOS los formularios de
        la institución, así que una Decisión de otro flujo puede estar comparando
        un campo de este formulario. Buscar sólo en los flujos que lo piden dejaría
        fuera justo la rama que nadie va a ir a revisar."""
        from apps.flujos.models import Conexion, Nodo

        otro = Flujo.objects.create(institucion=self.inst, titulo="Consultorio")
        version = VersionFlujo.objects.create(
            flujo=otro, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        decision = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.DECISION, titulo="¿Fiebre?", x=0, y=0
        )
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Alta", x=1, y=1)
        Conexion.objects.create(
            version=version, origen=decision, destino=fin, etiqueta="con fiebre",
            condicion={"campo": self.c2.pk, "operador": ">", "valor": "38"},
        )

        r = self.client.get(f"/api/formularios/{self.form.pk}/usos/")
        self.assertEqual(r.data["usos"], [])
        self.assertEqual(
            [(c["campo_id"], c["flujo"]) for c in r.data["condiciones"]],
            [(self.c2.pk, "Consultorio")],
        )

    def test_el_listado_cuenta_en_cuantos_flujos_se_usa(self):
        self._asignado_a_un_paso()
        r = self.client.get(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.data["usos_n"], 1)

    def test_una_version_archivada_no_cuenta_como_uso(self):
        """Es el registro de un circuito que ya no se ejecuta: contarlo haría ver
        como «en uso» a un formulario que ningún flujo vigente pide."""
        self._asignado_a_un_paso(estado=VersionFlujo.Estado.ARCHIVADA)
        r = self.client.get(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.data["usos_n"], 0)
        self.assertEqual(self.client.get(f"/api/formularios/{self.form.pk}/usos/").data["usos"], [])

    # --- reordenar ------------------------------------------------------- #
    def test_reordenar_fija_todos_los_ordenes_en_un_solo_pedido(self):
        """Antes era un PATCH por campo, en serie: si el quinto fallaba el
        formulario quedaba con medio orden nuevo y medio viejo."""
        r = self.client.post(
            f"/api/formularios/{self.form.pk}/reordenar/",
            {"campos": [self.c3.pk, self.c1.pk, self.c2.pk]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            [c["label"] for c in r.data["campos"]], ["Documento", "Motivo", "Temperatura"]
        )
        self.assertEqual(
            [c.orden for c in Campo.objects.filter(formulario=self.form).order_by("orden")],
            [0, 1, 2],
        )

    def test_reordenar_normaliza_los_ordenes_repetidos_de_los_formularios_viejos(self):
        """El alta usaba `campos.length`, así que hay formularios con órdenes
        repetidos: ahí intercambiar dos números no cambiaba nada en pantalla."""
        Campo.objects.filter(formulario=self.form).update(orden=0)
        self.client.post(
            f"/api/formularios/{self.form.pk}/reordenar/",
            {"campos": [self.c2.pk, self.c3.pk, self.c1.pk]},
            format="json",
        )
        self.assertEqual(
            [c.label for c in Campo.objects.filter(formulario=self.form).order_by("orden")],
            ["Temperatura", "Documento", "Motivo"],
        )

    def test_reordenar_con_una_lista_incompleta_se_rechaza(self):
        """Aplicarla dejaría campos sin orden asignado: el cliente venía con una
        vista vieja y lo que corresponde es que recargue."""
        r = self.client.post(
            f"/api/formularios/{self.form.pk}/reordenar/",
            {"campos": [self.c1.pk, self.c2.pk]},
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.c3.refresh_from_db()
        self.assertEqual(self.c3.orden, 2)

    # --- duplicar -------------------------------------------------------- #
    def test_duplicar_copia_todos_los_campos_y_ningun_dato(self):
        r = self.client.post(f"/api/formularios/{self.form.pk}/duplicar/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["titulo"], "Triage (copia)")
        copia = Formulario.objects.get(pk=r.data["id"])
        self.assertEqual(
            [(c.label, c.tipo, c.orden) for c in copia.campos.order_by("orden")],
            [
                ("Motivo", "texto_largo", 0),
                ("Temperatura", "numero", 1),
                ("Documento", "texto_corto", 2),
            ],
        )
        # La unidad y el rango también viajan: sin ellos la copia acepta un dato
        # que el original rechaza.
        temperatura = copia.campos.get(label="Temperatura")
        self.assertEqual(
            (temperatura.unidad, temperatura.minimo, temperatura.maximo), ("°C", 30, 45)
        )
        self.assertEqual(ValorCampo.objects.filter(campo__formulario=copia).count(), 0)

    # --- borrar ---------------------------------------------------------- #
    def test_no_se_borra_un_formulario_que_un_flujo_todavia_pide(self):
        """`Nodo.formulario` es SET_NULL: el paso quedaría «sin formulario» en un
        flujo publicado y el caso que llegue no tiene con qué avanzar."""
        self._asignado_a_un_paso()
        r = self.client.delete(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data["flujos"], ["Guardia"])
        self.assertTrue(Formulario.objects.filter(pk=self.form.pk).exists())

    def test_no_se_borra_un_formulario_con_datos_cargados(self):
        """Formulario → Campo → ValorCampo es CASCADE de punta a punta."""
        flujo = Flujo.objects.create(institucion=self.inst, titulo="Otro")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(institucion=self.inst, version=version)
        ValorCampo.objects.create(caso=caso, campo=self.c1, valor="dolor")

        r = self.client.delete(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(int(r.data["valores"]), 1)
        self.assertTrue(Formulario.objects.filter(pk=self.form.pk).exists())

    def test_se_borra_el_formulario_que_nadie_usa(self):
        """Un formulario creado por error no puede quedar para siempre."""
        r = self.client.delete(f"/api/formularios/{self.form.pk}/")
        self.assertEqual(r.status_code, 204, getattr(r, "data", None))
        self.assertFalse(Formulario.objects.filter(pk=self.form.pk).exists())
        self.assertFalse(Campo.objects.filter(formulario_id=self.form.pk).exists())


class CampoNumericoTests(APITestCase):
    """El tipo Número, y lo que el motor exige al cargarlo.

    Antes «Temperatura» era texto libre y podía quedar con «treinta y ocho» o con
    «386» por un punto que no se tipeó. Eso no falla al guardarse: falla en la
    Decisión «> 38», donde un valor no comparable devuelve False en silencio y el
    paciente febril sigue por el circuito del paciente sin fiebre.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user(
            email="config3@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Signos vitales")

    def _campo(self, **extra):
        datos = {
            "formulario": self.form.pk, "label": "Temperatura", "tipo": "numero",
            "unidad": "°C", "minimo": 30, "maximo": 45, "orden": 0,
        }
        datos.update(extra)
        return self.client.post("/api/campos/", datos, format="json")

    def test_se_define_un_campo_numerico_con_unidad_y_rango(self):
        r = self._campo()
        self.assertEqual(r.status_code, 201, r.data)
        campo = Campo.objects.get(pk=r.data["id"])
        self.assertEqual(
            (campo.tipo, campo.unidad, campo.minimo, campo.maximo), ("numero", "°C", 30, 45)
        )

    def test_un_rango_invertido_se_rechaza(self):
        """Así definido no entraría ningún valor: el campo sería imposible de completar."""
        r = self._campo(minimo=45, maximo=30)
        self.assertEqual(r.status_code, 400, r.data)

    def test_la_unidad_y_el_rango_se_limpian_al_dejar_de_ser_numero(self):
        """Un rango en un campo de texto es una promesa que ninguna capa valida."""
        campo = Campo.objects.get(pk=self._campo().data["id"])
        r = self.client.patch(f"/api/campos/{campo.pk}/", {"tipo": "texto_corto"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        campo.refresh_from_db()
        self.assertEqual((campo.unidad, campo.minimo, campo.maximo), ("", None, None))

    def test_una_seleccion_unica_sin_opciones_se_rechaza(self):
        """Es un desplegable vacío: el administrativo no tiene qué elegir."""
        r = self.client.post(
            "/api/campos/",
            {
                "formulario": self.form.pk, "label": "Cobertura",
                "tipo": "seleccion_unica", "opciones": [],
            },
            format="json",
        )
        self.assertEqual(r.status_code, 400, r.data)

    # --- lo que hace el motor al completar el formulario ------------------ #
    def _caso_parado_en_el_formulario(self):
        from apps.flujos.models import Nodo

        flujo = Flujo.objects.create(institucion=self.inst, titulo="Guardia")
        version = VersionFlujo.objects.create(
            flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        nodo = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.FORMULARIO, titulo="Signos",
            formulario=self.form, x=0, y=0,
        )
        Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Fin", x=1, y=1)
        caso = Caso.objects.create(institucion=self.inst, version=version, nodo_actual=nodo)
        return caso, nodo

    def test_el_motor_rechaza_un_numero_fuera_del_rango(self):
        from apps.casos import motor

        campo = Campo.objects.get(pk=self._campo().data["id"])
        caso, _ = self._caso_parado_en_el_formulario()
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.avanzar(caso, {"valores": {str(campo.pk): "386"}}, autor=self.user)
        self.assertIn("45", str(e.exception))
        self.assertEqual(ValorCampo.objects.filter(caso=caso).count(), 0)

    def test_el_motor_rechaza_lo_que_no_es_un_numero(self):
        from apps.casos import motor

        campo = Campo.objects.get(pk=self._campo().data["id"])
        caso, _ = self._caso_parado_en_el_formulario()
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {"valores": {str(campo.pk): "treinta y ocho"}}, autor=self.user)

    def test_el_motor_guarda_la_coma_decimal_como_punto(self):
        """«36,8» es lo que se tipea sin pensarlo, y guardado con la coma vuelve a
        ser un valor que las Decisiones de orden no pueden comparar."""
        from apps.casos import motor

        campo = Campo.objects.get(pk=self._campo().data["id"])
        caso, _ = self._caso_parado_en_el_formulario()
        motor.avanzar(caso, {"valores": {str(campo.pk): "36,8"}}, autor=self.user)
        self.assertEqual(ValorCampo.objects.get(caso=caso, campo=campo).valor, "36.8")
