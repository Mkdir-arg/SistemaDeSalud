"""
Tests del motor de ejecución.

Construye un flujo realista y corre un caso de punta a punta verificando las
transiciones, los efectos (estado, derivación, historia clínica, fila) y la
validación previa a publicar.

    Inicio → Formulario(datos) → Decisión(¿prioridad?) →
        ├─ [Alta]    → Derivar(Cardiología) → Estado(Atendido) → Fin
        └─ [default] → Espera(Sala) → Atención(evaluación) → Fin
"""
from django.test import TestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Grupo, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria

from . import motor
from .models import Caso, ItemFila


class MotorTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user("op@cauce.local", "x", nombre="Op")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.admision = Area.objects.create(institucion=self.inst, nombre="Admisión")
        self.cardio = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        # self.user opera como médico (puede firmar atenciones en los tests).
        Membresia.objects.create(usuario=self.user, institucion=self.inst, rol=Membresia.Rol.MEDICO)

        self.form = Formulario.objects.create(institucion=self.inst, titulo="Datos del paciente")
        self.campo_prioridad = Campo.objects.create(
            formulario=self.form, label="Prioridad", tipo=Campo.Tipo.SELECCION_UNICA,
            opciones=["Normal", "Alta"], orden=0,
        )

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.admision, titulo="Ingreso de paciente")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

        N = lambda tipo, titulo, **kw: Nodo.objects.create(version=self.ver, tipo=tipo, titulo=titulo, **kw)
        self.n_inicio = N(Nodo.Tipo.INICIO, "Inicio")
        self.n_form = N(Nodo.Tipo.FORMULARIO, "Datos del paciente", formulario=self.form)
        self.n_dec = N(Nodo.Tipo.DECISION, "¿prioridad?")
        self.n_derivar = N(Nodo.Tipo.DERIVAR, "Cardiología", config={"area_destino_id": self.cardio.id})
        self.n_estado = N(Nodo.Tipo.ESTADO, "Atendido", config={"estado": Caso.Estado.ATENDIDO})
        self.n_espera = N(Nodo.Tipo.ESPERA_FILA, "Sala de admisión")
        self.n_atencion = N(Nodo.Tipo.ATENCION, "Evaluación inicial")
        self.n_fin_alta = N(Nodo.Tipo.FIN, "Fin (alta prioridad)")
        self.n_fin_normal = N(Nodo.Tipo.FIN, "Fin (normal)")

        C = lambda o, d, **kw: Conexion.objects.create(version=self.ver, origen=o, destino=d, **kw)
        C(self.n_inicio, self.n_form)
        C(self.n_form, self.n_dec)
        C(self.n_dec, self.n_derivar, condicion={"campo": self.campo_prioridad.id, "operador": "=", "valor": "Alta"})
        C(self.n_dec, self.n_espera)  # rama por defecto
        C(self.n_derivar, self.n_estado)
        C(self.n_estado, self.n_fin_alta)
        C(self.n_espera, self.n_atencion)
        C(self.n_atencion, self.n_fin_normal)

        self.ciudadano = Ciudadano.objects.create(institucion=self.inst, nombre="María", apellido="González")

    def _nuevo_caso(self, prioridad=Caso.Prioridad.NORMAL):
        return Caso.objects.create(
            institucion=self.inst, version=self.ver, ciudadano=self.ciudadano, prioridad=prioridad
        )

    def test_iniciar_se_detiene_en_formulario(self):
        caso = motor.iniciar(self._nuevo_caso(), autor=self.user)
        # Inicio es automático; debe parar en el primer formulario.
        self.assertEqual(caso.nodo_actual, self.n_form)
        self.assertEqual(caso.estado, Caso.Estado.RECIBIDO)
        self.assertTrue(caso.eventos.filter(titulo="Caso iniciado").exists())

    def test_rama_alta_deriva_y_cierra(self):
        caso = motor.iniciar(self._nuevo_caso(), autor=self.user)
        caso = motor.avanzar(caso, {"valores": {self.campo_prioridad.id: "Alta"}}, autor=self.user)
        # Decisión + Derivar + Estado son automáticos → debe terminar cerrado.
        self.assertEqual(caso.estado, Caso.Estado.CERRADO)
        self.assertEqual(caso.nodo_actual, self.n_fin_alta)
        self.assertEqual(caso.area_actual, self.cardio)
        self.assertTrue(caso.valores.filter(campo=self.campo_prioridad, valor="Alta").exists())
        self.assertTrue(caso.eventos.filter(titulo__icontains="Derivado").exists())

    def test_rama_default_pasa_por_fila_y_atencion(self):
        caso = motor.iniciar(self._nuevo_caso(), autor=self.user)
        caso = motor.avanzar(caso, {"valores": {self.campo_prioridad.id: "Normal"}}, autor=self.user)
        # Debe quedar encolado en la espera de fila.
        self.assertEqual(caso.nodo_actual, self.n_espera)
        self.assertEqual(caso.estado, Caso.Estado.EN_ESPERA)
        self.assertEqual(ItemFila.objects.filter(caso=caso, nodo=self.n_espera, atendido=False).count(), 1)

        # Llamado desde la fila → pasa a Atención.
        caso = motor.avanzar(caso, {}, autor=self.user)
        self.assertEqual(caso.nodo_actual, self.n_atencion)
        self.assertTrue(ItemFila.objects.get(caso=caso, nodo=self.n_espera).atendido)

        # Registrar atención → crea entrada en HC y cierra el caso.
        caso = motor.avanzar(caso, {"titulo": "Evaluación inicial", "contenido": "OK", "firmada": True}, autor=self.user)
        self.assertEqual(caso.estado, Caso.Estado.CERRADO)
        self.assertEqual(caso.nodo_actual, self.n_fin_normal)
        self.assertEqual(EntradaHistoria.objects.filter(caso=caso, firmada=True).count(), 1)

    def test_urgente_entra_a_fila_como_urgente(self):
        caso = motor.iniciar(self._nuevo_caso(prioridad=Caso.Prioridad.URGENTE), autor=self.user)
        caso = motor.avanzar(caso, {"valores": {self.campo_prioridad.id: "Normal"}}, autor=self.user)
        item = ItemFila.objects.get(caso=caso, nodo=self.n_espera)
        self.assertTrue(item.urgente)

    def test_no_se_puede_avanzar_caso_cerrado(self):
        caso = motor.iniciar(self._nuevo_caso(), autor=self.user)
        caso = motor.avanzar(caso, {"valores": {self.campo_prioridad.id: "Alta"}}, autor=self.user)
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {}, autor=self.user)

    def test_validacion_flujo_correcto(self):
        problemas = motor.validar_version(self.ver)
        errores = [p for p in problemas if p["sev"] == "error"]
        self.assertEqual(errores, [], f"No debería haber errores: {errores}")
        self.assertTrue(motor.puede_publicar(self.ver))

    def test_validacion_detecta_derivar_sin_area(self):
        self.n_derivar.config = {}
        self.n_derivar.save()
        problemas = motor.validar_version(self.ver)
        self.assertTrue(any(p["sev"] == "error" and "Derivación" in p["titulo"] for p in problemas))
        self.assertFalse(motor.puede_publicar(self.ver))

    def test_validacion_detecta_decision_con_campo_inexistente(self):
        # Condición que apunta a un campo que no existe en ningún formulario.
        Conexion.objects.filter(origen=self.n_dec, condicion__has_key="campo").update(
            condicion={"campo": 999999, "operador": "=", "valor": "Alta"}
        )
        problemas = motor.validar_version(self.ver)
        self.assertTrue(any("campo inexistente" in p["titulo"] for p in problemas))


class ResponsabilidadTests(TestCase):
    """`usuario_puede_tomar`: quién puede ejecutar el paso según los grupos del nodo."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Turno mañana")
        self.miembro = Usuario.objects.create_user("m@cauce.local", "x", nombre="Miembro")
        self.ajeno = Usuario.objects.create_user("a@cauce.local", "x", nombre="Ajeno")
        self.jefe = Usuario.objects.create_superuser("j@cauce.local", "x", nombre="Jefe")
        self.grupo.miembros.add(self.miembro)

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Triage")
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.ATENCION, titulo="Evaluar")
        self.caso = Caso.objects.create(institucion=self.inst, version=ver, nodo_actual=self.nodo)

    def test_paso_abierto_sin_grupos(self):
        self.assertTrue(motor.usuario_puede_tomar(self.ajeno, self.caso))

    def test_solo_integrantes_del_grupo(self):
        self.nodo.grupos.add(self.grupo)
        self.assertTrue(motor.usuario_puede_tomar(self.miembro, self.caso))
        self.assertFalse(motor.usuario_puede_tomar(self.ajeno, self.caso))

    def test_superusuario_siempre_puede(self):
        self.nodo.grupos.add(self.grupo)
        self.assertTrue(motor.usuario_puede_tomar(self.jefe, self.caso))


class DerivacionEntreFlujosTests(TestCase):
    """Un nodo `derivar` con `flujo_destino_id` instancia y arranca un caso allí."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.guardia = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.cardio = Area.objects.create(institucion=self.inst, nombre="Cardiología")

        # Flujo destino (Cardiología), publicado: Inicio → Atención → Fin.
        self.f_cardio = Flujo.objects.create(institucion=self.inst, area=self.cardio, titulo="Atención cardiológica")
        vc = VersionFlujo.objects.create(flujo=self.f_cardio, numero=1)
        ci = Nodo.objects.create(version=vc, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        ca = Nodo.objects.create(version=vc, tipo=Nodo.Tipo.ATENCION, titulo="Consulta")
        cf = Nodo.objects.create(version=vc, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=vc, origen=ci, destino=ca)
        Conexion.objects.create(version=vc, origen=ca, destino=cf)
        vc.estado = VersionFlujo.Estado.PUBLICADA
        vc.save()

        # Flujo de ingreso: Inicio → Derivar(a Cardiología) → Fin.
        self.f_ing = Flujo.objects.create(institucion=self.inst, area=self.guardia, titulo="Ingreso a Guardia")
        self.vi = VersionFlujo.objects.create(flujo=self.f_ing, numero=1)
        ii = Nodo.objects.create(version=self.vi, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        idd = Nodo.objects.create(version=self.vi, tipo=Nodo.Tipo.DERIVAR, titulo="Derivar a Cardiología",
                                  config={"area_destino_id": self.cardio.id, "flujo_destino_id": self.f_cardio.id})
        iff = Nodo.objects.create(version=self.vi, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.vi, origen=ii, destino=idd)
        Conexion.objects.create(version=self.vi, origen=idd, destino=iff)

    def test_derivar_instancia_caso_en_destino(self):
        caso = Caso.objects.create(institucion=self.inst, version=self.vi)
        motor.iniciar(caso, autor=None)

        derivados = Caso.objects.filter(version__flujo=self.f_cardio)
        self.assertEqual(derivados.count(), 1)
        d = derivados.first()
        self.assertEqual(d.origen_id, caso.id)            # vínculo de trazabilidad
        self.assertEqual(d.area_actual_id, self.cardio.id)  # área del flujo destino
        # El caso derivado arrancó y se detuvo en la Atención.
        self.assertEqual(d.nodo_actual.tipo, Nodo.Tipo.ATENCION)
        # El caso origen quedó marcado como derivado en su recorrido.
        self.assertTrue(caso.eventos.filter(titulo="Derivado a otro flujo").exists())
