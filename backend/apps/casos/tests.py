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

from apps.accounts.models import Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria

from . import motor
from .models import Caso, ItemFila


class MotorTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user("op@cauce.local", "x", nombre="Op")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.admision = Area.objects.create(institucion=self.inst, nombre="Admisión")
        self.cardio = Area.objects.create(institucion=self.inst, nombre="Cardiología")

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
