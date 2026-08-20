"""
Lo que el diseñador tiene que enterarse ANTES de publicar, y lo que el «Probar»
no puede hacer.

Los dos momentos comparten el mismo riesgo: un flujo que se dibuja hoy se ejecuta
mañana con un paciente adentro. Si `validar_version` calla, el error se descubre
en la guardia; si el ensayo hace de verdad lo que el flujo dice, el error queda
del lado de afuera, donde ningún rollback lo alcanza.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Grupo, Institucion

from . import motor


class BaseFlujo(TestCase):
    """Institución, área y una versión vacía sobre la que dibujar cada grafo."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Atención")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

    def _nodo(self, tipo, titulo, **config):
        return Nodo.objects.create(version=self.ver, tipo=tipo, titulo=titulo, config=config or {})

    def _unir(self, origen, destino, condicion=None):
        return Conexion.objects.create(
            version=self.ver, origen=origen, destino=destino, condicion=condicion or {}
        )

    def _errores(self):
        return [p for p in motor.validar_version(self.ver) if p["sev"] == "error"]


class SalidasAmbiguasTests(BaseFlujo):
    """Un paso que no es Decisión con dos flechas salientes."""

    def test_un_paso_que_no_es_decision_no_puede_tener_dos_salidas(self):
        """
        `_siguiente_nodo` toma la primera conexión que se dibujó y la otra rama
        queda muerta: TODOS los pacientes de ese flujo se internan, o a todos se
        les da el alta, según cuál flecha se trazó antes. Sin este chequeo el
        validador da cero errores, el flujo se publica limpio y hasta el «Probar»
        recorre esa misma rama, así que el ensayo confirma el flujo equivocado.
        """
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        atencion = self._nodo(Nodo.Tipo.ATENCION, "Ver al paciente")
        cama = self._nodo(Nodo.Tipo.CAMA, "Internar")
        fin = self._nodo(Nodo.Tipo.FIN, "Alta")
        self._unir(ini, atencion)
        self._unir(atencion, cama)
        self._unir(atencion, fin)
        self._unir(cama, fin)

        titulos = [p["titulo"] for p in self._errores()]
        self.assertIn("«Ver al paciente» tiene más de una salida y no es una Decisión", titulos)
        self.assertFalse(motor.puede_publicar(self.ver))

    def test_una_decision_si_puede_tener_varias_salidas(self):
        """
        La Decisión es el único nodo que sabe elegir. Si el chequeo la alcanzara,
        no se podría publicar ningún flujo con una bifurcación, que es la mitad
        de para qué existe el diseñador.
        """
        form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        campo = Campo.objects.create(formulario=form, label="Gravedad", tipo="texto_corto", orden=0)
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        nodo_form = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage", formulario=form, config={}
        )
        decision = self._nodo(Nodo.Tipo.DECISION, "¿Grave?")
        cama = self._nodo(Nodo.Tipo.CAMA, "Internar")
        fin = self._nodo(Nodo.Tipo.FIN, "Alta")
        self._unir(ini, nodo_form)
        self._unir(nodo_form, decision)
        self._unir(decision, cama, {"campo": campo.id, "operador": "=", "valor": "Alta"})
        self._unir(decision, fin)  # rama por defecto
        self._unir(cama, fin)

        self.assertEqual(self._errores(), [])
        self.assertTrue(motor.puede_publicar(self.ver))


class GruposResponsablesTests(BaseFlujo):
    def test_un_grupo_inactivo_asignado_a_un_nodo_no_se_puede_publicar(self):
        grupo = Grupo.objects.create(area=self.area, nombre="Turno tarde", activo=False)
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        paso = self._nodo(Nodo.Tipo.ATENCION, "Atender")
        fin = self._nodo(Nodo.Tipo.FIN, "Fin")
        paso.grupos.add(grupo)
        self._unir(ini, paso)
        self._unir(paso, fin)

        titulos = [p["titulo"] for p in self._errores()]

        self.assertIn("Grupo responsable inactivo", titulos)
        self.assertFalse(motor.puede_publicar(self.ver))


class DuracionDeEsperaTests(BaseFlujo):
    """Nodo «Espera por tiempo» con una duración que el motor no interpreta."""

    def _armar(self, **config):
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        self.espera = self._nodo(Nodo.Tipo.ESPERA_TIEMPO, "Control", **config)
        fin = self._nodo(Nodo.Tipo.FIN, "Cierre")
        self._unir(ini, self.espera)
        self._unir(self.espera, fin)

    def test_una_duracion_que_no_se_entiende_no_se_puede_publicar(self):
        """
        Con una duración ilegible el caso queda EN_ESPERA sin vencimiento y no
        vuelve a ninguna bandeja nunca. Como nadie espera que aparezca, nadie lo
        busca: el paciente al que había que controlar a la semana se pierde. El
        editor sólo avisa cuando el campo está VACÍO, así que si esto no falla al
        publicar no falla en ningún lado.
        """
        self._armar(duracion="una semana")
        titulos = [p["titulo"] for p in self._errores()]
        self.assertIn("«Control» tiene una duración que no se entiende", titulos)
        self.assertFalse(motor.puede_publicar(self.ver))

    def test_una_duracion_que_el_motor_entiende_publica(self):
        """«6 horas» sí se agenda: el chequeo no puede trabar lo que funciona."""
        self._armar(duracion="6 horas")
        self.assertEqual(self._errores(), [])
        self.assertTrue(motor.puede_publicar(self.ver))

    def test_un_nodo_de_tiempo_sin_duracion_no_es_un_error_de_publicacion(self):
        """
        Sin duración el caso también espera una reactivación manual, pero eso es
        una decisión posible (un control que se retoma a mano) y el editor ya lo
        marca. El error es para la duración que alguien creyó haber cargado.
        """
        self._armar()
        self.assertEqual(self._errores(), [])


@override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
class CampoDeIntegracionTests(BaseFlujo):
    """Una Decisión sobre el campo que llena una Integración."""

    def setUp(self):
        super().setUp()
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Cobertura")
        self.campo = Campo.objects.create(
            formulario=self.form, label="Plan", tipo="texto_corto", orden=0
        )
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        self.integ = self._nodo(
            Nodo.Tipo.INTEGRACION, "Padrón",
            url="https://padron.gob.ar/api", guardar_en=self.campo.id, ruta="cobertura.plan",
        )
        decision = self._nodo(Nodo.Tipo.DECISION, "¿Tiene cobertura?")
        fin_obra = self._nodo(Nodo.Tipo.FIN, "Circuito obra social")
        fin_publico = self._nodo(Nodo.Tipo.FIN, "Circuito público")
        self._unir(ini, self.integ)
        self._unir(self.integ, decision)
        self._unir(decision, fin_obra, {"campo": self.campo.id, "operador": "no_vacio", "valor": ""})
        self._unir(decision, fin_publico)

    def test_una_decision_sobre_un_campo_que_carga_la_integracion_se_puede_publicar(self):
        """
        Es el circuito que el propio panel recomienda («el dato queda cargado en
        el caso y se puede usar en una Decisión»): consultar la cobertura en el
        padrón y rutear al paciente según el plan. Si `campos_disponibles` mira
        sólo los formularios, publicar devuelve 400 con un detalle que además
        culpa a la causa equivocada, y el único taller posible es agregar un
        formulario decorativo para engañar al validador.
        """
        self.assertEqual(self._errores(), [])
        self.assertTrue(motor.puede_publicar(self.ver))

    def test_un_campo_que_no_carga_nadie_sigue_siendo_un_error(self):
        """La guarda vieja tiene que seguir viva: sin ella una rama no se puede
        evaluar en producción y el paciente queda sin salida."""
        Conexion.objects.filter(condicion__has_key="campo").update(
            condicion={"campo": 999999, "operador": "=", "valor": "PAMI"}
        )
        self.assertIn("Regla con un campo inexistente", [p["titulo"] for p in self._errores()])


@override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
class IntegracionGuardarEnConfigTests(BaseFlujo):
    def setUp(self):
        super().setUp()
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Cobertura")
        self.campo = Campo.objects.create(formulario=self.form, label="Plan", tipo="texto_corto", orden=0)
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        self.integ = self._nodo(
            Nodo.Tipo.INTEGRACION, "Padron",
            url="https://padron.gob.ar/api", guardar_en=self.campo.id, ruta="cobertura.plan",
        )
        fin = self._nodo(Nodo.Tipo.FIN, "Cierre")
        self._unir(ini, self.integ)
        self._unir(self.integ, fin)

    def test_guardar_en_de_integracion_debe_existir_en_la_institucion(self):
        otra = Institucion.objects.create(nombre="Hospital Norte")
        form_ajeno = Formulario.objects.create(institucion=otra, titulo="Cobertura")
        campo_ajeno = Campo.objects.create(formulario=form_ajeno, label="Plan", tipo="texto_corto", orden=0)
        self.integ.config["guardar_en"] = campo_ajeno.id
        self.integ.save(update_fields=["config"])

        self.assertIn("Integracion con campo destino invalido", [p["titulo"] for p in self._errores()])

    def test_guardar_en_de_integracion_debe_ser_un_id(self):
        self.integ.config["guardar_en"] = "plan"
        self.integ.save(update_fields=["config"])

        self.assertIn("Integracion con campo destino invalido", [p["titulo"] for p in self._errores()])


class PrioridadDesdeFormularioConfigTests(BaseFlujo):
    def setUp(self):
        super().setUp()
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.nivel = Campo.objects.create(
            formulario=self.form, label="Nivel", tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["Rojo", "Verde"], orden=0,
        )
        self.texto = Campo.objects.create(
            formulario=self.form, label="Observaciones", tipo=Campo.Tipo.TEXTO_CORTO, orden=1
        )

    def _armar(self, campo_id):
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        form = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage", formulario=self.form,
            config={"prioridad_campo": campo_id, "prioridad_mapa": {"Rojo": "urgente"}},
        )
        fin = self._nodo(Nodo.Tipo.FIN, "Cierre")
        self._unir(ini, form)
        self._unir(form, fin)

    def test_prioridad_campo_valido_publica(self):
        self._armar(self.nivel.id)
        self.assertEqual(self._errores(), [])

    def test_prioridad_campo_de_otro_formulario_falla(self):
        otro_form = Formulario.objects.create(institucion=self.inst, titulo="Otro")
        otro_campo = Campo.objects.create(
            formulario=otro_form, label="Nivel", tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["Rojo"], orden=0,
        )
        self._armar(otro_campo.id)
        self.assertIn("Prioridad con campo invalido", [p["titulo"] for p in self._errores()])

    def test_prioridad_campo_no_seleccionable_falla(self):
        self._armar(self.texto.id)
        self.assertIn("Prioridad con campo no seleccionable", [p["titulo"] for p in self._errores()])


class _RespuestaFalsa:
    """Lo mínimo que `_llamar_externo` le pide a `urlopen`: un context manager
    con `read`. Sin esto el mock devuelve otro mock y el motor falla por el
    andamiaje del test en vez de por lo que se está probando."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=None):
        return b'{"cobertura": {"plan": "PAMI"}}'


@override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
class EnsayoSinRedTests(BaseFlujo):
    """El botón «Probar» no puede tocar sistemas de afuera."""

    def setUp(self):
        super().setUp()
        form = Formulario.objects.create(institucion=self.inst, titulo="Cobertura")
        campo = Campo.objects.create(formulario=form, label="Plan", tipo="texto_corto", orden=0)
        ini = self._nodo(Nodo.Tipo.INICIO, "Inicio")
        integ = self._nodo(
            Nodo.Tipo.INTEGRACION, "Crear el turno en el HIS",
            url="https://padron.gob.ar/turnos", metodo="POST",
            cuerpo={"paciente": "x"}, guardar_en=campo.id,
        )
        fin = self._nodo(Nodo.Tipo.FIN, "Cierre")
        self._unir(ini, integ)
        self._unir(integ, fin)

    def test_el_ensayo_no_llama_al_servicio_externo(self):
        """
        `ensayar` deshace la transacción, pero un POST ya emitido no vuelve
        atrás: probar un circuito de seis pasos dejaba seis órdenes en el sistema
        externo, para un caso de prueba sin paciente y sin ningún rastro de este
        lado que las explicara. Y el panel reenvía todos los pasos en cada
        avance, así que se repetía una vez por clic.
        """
        with patch("apps.casos.motor.urlopen", return_value=_RespuestaFalsa()) as llamada:
            r = motor.ensayar(self.ver, [{}], autor=None)

        self.assertEqual(llamada.call_count, 0, "el ensayo salió a la red")
        # Y el ensayo sigue sirviendo: atravesó la integración y llegó al Fin.
        self.assertTrue(r["termino"])
        self.assertIsNone(r["error"])

    def test_fuera_del_ensayo_la_integracion_sigue_saliendo_a_la_red(self):
        """
        La marca es del ensayo, no del nodo. Si apagara también la ejecución
        real, ningún flujo consultaría nunca un padrón y el módulo de
        integraciones no serviría para nada.
        """
        from apps.casos.models import Caso

        caso = Caso.objects.create(institucion=self.inst, version=self.ver)
        integ = self.ver.nodos.get(tipo=Nodo.Tipo.INTEGRACION)
        with patch("apps.casos.motor.urlopen", return_value=_RespuestaFalsa()) as llamada:
            motor._aplicar_efecto_entrada(caso, integ)
        self.assertEqual(llamada.call_count, 1)
