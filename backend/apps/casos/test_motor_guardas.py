"""
Guardas del motor: las reglas que sostenían la pantalla y no el servidor.

Todo lo que se prueba acá tiene la misma forma: una regla que la interfaz
respetaba y que nadie volvía a chequear del lado del servidor. Un POST armado a
mano, una integración o un cliente viejo la salteaban sin un solo error, y el
resultado no era un pedido rechazado sino un dato falso —un paciente internado
en un hospital ajeno, un fallecimiento anotado como alta, un triage vacío que
define por dónde sigue la persona—.
"""
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Cama, EstadiaCama, Institucion, Subarea
from apps.registros.models import Ciudadano

from . import motor
from .models import Caso, ValorCampo


class CamasGuardasTests(TestCase):
    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("guarda@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.uti = Subarea.objects.create(area=self.area, nombre="UTI")
        self.sala = Subarea.objects.create(area=self.area, nombre="Clínica médica")

        # Otro hospital de la red: sus camas no son de este caso.
        self.otra_inst = Institucion.objects.create(nombre="Hospital del Norte")
        self.otra_area = Area.objects.create(institucion=self.otra_inst, nombre="Internación")
        self.cama_ajena = Cama.objects.create(area=self.otra_area, nombre="N-1")

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.cama_nodo = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.CAMA, titulo="Asignar cama",
            config={"sector": self.sala.id},
        )
        self.evol = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Evolución")
        self.fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Egreso")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.cama_nodo)
        Conexion.objects.create(version=self.ver, origen=self.cama_nodo, destino=self.evol)
        Conexion.objects.create(version=self.ver, origen=self.evol, destino=self.fin)

        self.c101 = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        self.uti1 = Cama.objects.create(area=self.area, subarea=self.uti, nombre="UTI 1")

    def _internar(self, nombre="Ana"):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.jefe)
        caso.refresh_from_db()
        return caso

    # --- Alcance de la cama -------------------------------------------------- #

    def test_no_se_puede_internar_en_una_cama_de_otro_sector(self):
        """
        El paso declara «Clínica médica». Que la pantalla ofrezca sólo esas camas
        no alcanza: el POST recibe el `cama_id` del cuerpo. Sin esta guarda, un
        cliente mal armado ocupa una cama de UTI desde un paso de sala y el
        sector se queda con una cama menos sin que nadie entienda por qué.
        """
        caso = self._internar()
        with self.assertRaises(motor.ErrorMotor):
            motor.asignar_cama(caso, self.uti1.id, autor=self.jefe)
        self.uti1.refresh_from_db()
        self.assertEqual(self.uti1.estado, Cama.Estado.LIBRE)
        self.assertFalse(EstadiaCama.objects.filter(caso=caso).exists())

    def test_no_se_puede_internar_en_una_cama_de_otro_hospital(self):
        """
        Cauce es multi-institución. Una cama del Hospital del Norte ocupada por
        un caso del Central desaparece del tablero del Norte —figura ocupada por
        alguien que nunca llegó— y ahí nadie puede liberarla, porque el egreso lo
        da el caso del otro hospital.
        """
        caso = self._internar()
        with self.assertRaises(motor.ErrorMotor):
            motor.asignar_cama(caso, self.cama_ajena.id, autor=self.jefe)
        self.cama_ajena.refresh_from_db()
        self.assertIsNone(self.cama_ajena.caso_id)

    def test_el_pase_tampoco_cruza_de_hospital(self):
        """El pase cambia de sector a propósito; de institución, nunca."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor):
            motor.pasar_de_sector(caso, self.cama_ajena.id, autor=self.jefe)
        self.cama_ajena.refresh_from_db()
        self.assertIsNone(self.cama_ajena.caso_id)

    def test_el_pase_a_otro_sector_del_mismo_hospital_sigue_andando(self):
        """La guarda de institución no puede romper el pase de sala a UTI."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe, motivo="descompensó")
        self.uti1.refresh_from_db()
        self.assertEqual(self.uti1.caso_id, caso.id)

    # --- Avanzar no atraviesa la internación --------------------------------- #

    def test_avanzar_no_atraviesa_el_paso_de_cama(self):
        """
        Avanzar sobre el nodo de cama dejaba al paciente internado en ningún
        lado: sin cama ocupada, sin estadía y sin un solo evento que lo dijera.
        El tablero muestra esa cama libre y se la ofrece al próximo que llegue.
        """
        caso = self._internar()
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {}, autor=self.jefe)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, self.cama_nodo.id)
        self.assertFalse(EstadiaCama.objects.filter(caso=caso).exists())

    # --- Motivo del egreso ---------------------------------------------------- #

    def test_un_fallecimiento_no_queda_registrado_como_alta(self):
        """
        Si el egreso por fallecimiento se anota como alta, el recorrido del
        paciente miente —y ese historial es lo que se mira cuando alguien
        reclama—, no se puede contar mortalidad por sector, y la cama sigue el
        circuito de higiene equivocado.
        """
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.dar_de_alta_cama(caso, autor=self.jefe, motivo=EstadiaCama.Egreso.FALLECIMIENTO)
        estadia = EstadiaCama.objects.get(caso=caso)
        self.assertEqual(estadia.motivo_egreso, EstadiaCama.Egreso.FALLECIMIENTO)

    def test_un_motivo_de_egreso_desconocido_se_rechaza_en_vez_de_volverse_alta(self):
        """Un dato falso que nadie sabe que está mal no se corrige nunca."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor):
            motor.dar_de_alta_cama(caso, autor=self.jefe, motivo="fallecio")
        self.assertEqual(EstadiaCama.objects.get(caso=caso).motivo_egreso, "")

    def test_sin_motivo_el_egreso_sigue_siendo_un_alta(self):
        """La pantalla actual postea sin cuerpo: eso no puede empezar a fallar."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.dar_de_alta_cama(caso, autor=self.jefe)
        self.assertEqual(EstadiaCama.objects.get(caso=caso).motivo_egreso, EstadiaCama.Egreso.ALTA)

    def test_cerrar_el_caso_libera_la_cama_sin_afirmar_un_alta(self):
        """
        El cierre por nodo Fin no sabe por qué egresó el paciente. Escribir
        «alta» ahí es afirmar algo que nadie declaró; en blanco se ve que falta.
        """
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.avanzar(caso, {"titulo": "Epicrisis", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.c101.refresh_from_db()
        self.assertIsNone(self.c101.caso_id)
        self.assertEqual(EstadiaCama.objects.get(caso=caso).motivo_egreso, "")

    def test_el_nodo_de_cierre_puede_declarar_el_motivo_del_egreso(self):
        """Un flujo de derivación cierra con «derivación», no con «alta»."""
        self.fin.config = {"motivo_egreso": EstadiaCama.Egreso.DERIVACION}
        self.fin.save(update_fields=["config"])
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        motor.avanzar(caso, {"titulo": "Derivación", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.assertEqual(
            EstadiaCama.objects.get(caso=caso).motivo_egreso, EstadiaCama.Egreso.DERIVACION
        )

    # --- Estado de la cama ---------------------------------------------------- #

    def test_marcar_libre_mira_la_cama_de_ahora_y_no_la_foto_que_tenia_la_pantalla(self):
        """
        Peor resultado posible del módulo: dos pacientes en la misma cama. La
        vista lee la cama antes de abrir la transacción; si entre esa lectura y
        el cambio alguien internó, decidir con la copia vieja deja la cama LIBRE
        con un paciente adentro y el próximo `asignar_cama` la acepta.
        """
        foto_vieja = Cama.objects.get(pk=self.c101.pk)  # la cama estaba libre
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)  # otro la ocupa

        with self.assertRaises(motor.ErrorMotor):
            motor.cambiar_estado_cama(foto_vieja, Cama.Estado.LIBRE, autor=self.jefe)

        self.c101.refresh_from_db()
        self.assertEqual(self.c101.estado, Cama.Estado.OCUPADA)
        self.assertEqual(self.c101.caso_id, caso.id)

    # --- Carreras sobre el mismo paciente ------------------------------------- #

    def test_internar_bloquea_al_caso_y_no_solo_a_la_cama(self):
        """
        Dos operadores que eligen camas DISTINTAS para el mismo paciente bloquean
        filas distintas: sin tomar el bloqueo del caso, ninguno ve la estadía que
        el otro todavía no confirmó y el paciente queda en dos camas a la vez.
        Se mira que el bloqueo se pida, porque el resultado sólo se puede
        observar con dos transacciones simultáneas.
        """
        caso = self._internar()
        with CaptureQueriesContext(connection) as consultas:
            motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        sql = [c["sql"].lower() for c in consultas.captured_queries]
        self.assertTrue(
            any("casos_caso" in s and "for update" in s for s in sql),
            "asignar_cama no bloqueó la fila del caso",
        )

    def test_el_pase_tambien_bloquea_al_caso(self):
        """Dos pases concurrentes cierran la misma estadía y abren dos nuevas."""
        caso = self._internar()
        motor.asignar_cama(caso, self.c101.id, autor=self.jefe)
        caso.refresh_from_db()
        with CaptureQueriesContext(connection) as consultas:
            motor.pasar_de_sector(caso, self.uti1.id, autor=self.jefe)
        sql = [c["sql"].lower() for c in consultas.captured_queries]
        self.assertTrue(
            any("casos_caso" in s and "for update" in s for s in sql),
            "pasar_de_sector no bloqueó la fila del caso",
        )


class CamposRequeridosTests(TestCase):
    """
    «Requerido» se pintaba con un asterisco y no lo exigía ninguna capa.

    Un triage se completaba vacío de un clic y el caso avanzaba igual; la
    Decisión que viene después evalúa sobre un campo vacío y manda al paciente
    por la rama que no era.
    """

    def setUp(self):
        self.user = Usuario.objects.create_superuser("req@cauce.local", "x", nombre="Op")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.nivel = Campo.objects.create(
            formulario=self.form, label="Nivel de triage", tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["Rojo", "Verde"], requerido=True, orden=0,
        )
        self.obs = Campo.objects.create(
            formulario=self.form, label="Observaciones", tipo=Campo.Tipo.TEXTO_LARGO, orden=1,
        )

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.n_form = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage", formulario=self.form
        )
        self.fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.n_form)
        Conexion.objects.create(version=self.ver, origen=self.n_form, destino=self.fin)

    def _caso(self):
        caso = Caso.objects.create(institucion=self.inst, version=self.ver)
        motor.iniciar(caso, autor=self.user)
        caso.refresh_from_db()
        return caso

    def test_un_campo_requerido_vacio_no_deja_avanzar(self):
        """El campo que el hospital declaró obligatorio define por dónde sigue el paciente."""
        caso = self._caso()
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {"valores": {}}, autor=self.user)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, self.n_form.id)

    def test_un_requerido_en_blanco_cuenta_como_vacio(self):
        """Mandar la clave con espacios es la forma más fácil de saltear la regla."""
        caso = self._caso()
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {"valores": {self.nivel.id: "   "}}, autor=self.user)

    def test_el_error_nombra_el_campo_que_falta(self):
        """Un «faltan datos» pelado obliga a adivinar cuál en un formulario de quince campos."""
        caso = self._caso()
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.avanzar(caso, {"valores": {self.obs.id: "sin novedades"}}, autor=self.user)
        self.assertIn("Nivel de triage", str(e.exception))

    def test_con_el_requerido_cargado_el_caso_avanza(self):
        """La guarda no puede trabar el camino normal."""
        caso = self._caso()
        motor.avanzar(caso, {"valores": {self.nivel.id: "Rojo"}}, autor=self.user)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, self.fin.id)

    def test_un_requerido_cargado_en_un_paso_anterior_no_se_vuelve_a_pedir(self):
        """
        Un campo precargado desde la historia clínica, o cargado antes en el
        mismo caso, ya tiene valor: exigir que lo reenvíen convierte la regla en
        un obstáculo y traba un flujo que vuelve sobre el mismo formulario.
        """
        caso = self._caso()
        ValorCampo.objects.create(caso=caso, campo=self.nivel, nodo=self.n_form, valor="Verde")
        motor.avanzar(caso, {"valores": {self.obs.id: "reevaluado"}}, autor=self.user)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, self.fin.id)


class DecisionSinRamaPorDefectoTests(TestCase):
    """
    Una Decisión donde ninguna rama se cumple deja el caso PARADO en un nodo
    automático: no aparece en ninguna bandeja, no tiene responsable y «avanzar»
    le responde que ese nodo no espera una acción manual. El único camino es
    cancelar el caso. Se detecta al publicar porque en ejecución ya es tarde.
    """

    def setUp(self):
        self.user = Usuario.objects.create_superuser("dec@cauce.local", "x", nombre="Dis")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.campo = Campo.objects.create(
            formulario=self.form, label="Color", tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["Rojo", "Verde"], orden=0,
        )
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.n_form = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage", formulario=self.form
        )
        self.dec = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.DECISION, titulo="¿color?")
        self.fin_rojo = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Shock room")
        self.fin_verde = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Consultorio")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.n_form)
        Conexion.objects.create(version=self.ver, origen=self.n_form, destino=self.dec)
        Conexion.objects.create(version=self.ver, origen=self.dec, destino=self.fin_rojo,
                                condicion={"campo": self.campo.id, "operador": "=", "valor": "Rojo"})
        Conexion.objects.create(version=self.ver, origen=self.dec, destino=self.fin_verde,
                                condicion={"campo": self.campo.id, "operador": "=", "valor": "Verde"})

    def test_una_decision_sin_si_no_no_se_puede_publicar(self):
        """Publicarla sin un aviso es dejar el callejón sin salida servido."""
        titulos = [p["titulo"] for p in motor.validar_version(self.ver) if p["sev"] == "error"]
        self.assertIn("Decisión sin rama por defecto", titulos)
        self.assertFalse(motor.puede_publicar(self.ver))

    def test_con_la_rama_por_defecto_el_flujo_se_publica(self):
        """Agregar el «si no» es exactamente lo que el aviso pide."""
        Conexion.objects.create(version=self.ver, origen=self.dec, destino=self.fin_verde)
        titulos = [p["titulo"] for p in motor.validar_version(self.ver)]
        self.assertNotIn("Decisión sin rama por defecto", titulos)
        self.assertTrue(motor.puede_publicar(self.ver))

    def test_un_caso_trabado_en_la_decision_no_ofrece_un_boton_que_siempre_falla(self):
        """
        Ofrecer «avanzar» sobre un nodo automático es peor que no ofrecer nada:
        el motor lo rechaza siempre y la persona prueba una y otra vez el único
        camino visible, en vez de ver que hay que resolverlo de otra manera.
        """
        caso = Caso.objects.create(institucion=self.inst, version=self.ver)
        motor.iniciar(caso, autor=self.user)
        caso.refresh_from_db()
        motor.avanzar(caso, {"valores": {self.campo.id: "Azul"}}, autor=self.user)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, self.dec.id)  # quedó parado en la decisión
        self.assertEqual(motor._acciones_posibles(caso, caso.nodo_actual), [])
