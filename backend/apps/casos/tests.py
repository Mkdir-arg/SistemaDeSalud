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
from apps.instituciones.models import Area, Box, Grupo, Institucion
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


class AtencionConFilaTests(TestCase):
    """Atención con fila: el paciente espera, se lo llama de un box y recién ahí se atiende."""

    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("jefe@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.box = Box.objects.create(area=self.area, nombre="Box 1")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Atención cardio")
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ate = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención", config={"con_fila": True})
        fin = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=ver, origen=ini, destino=self.ate)
        Conexion.objects.create(version=ver, origen=self.ate, destino=fin)
        self.ciud = Ciudadano.objects.create(institucion=self.inst, nombre="Pac", apellido="Test")
        self.caso = Caso.objects.create(institucion=self.inst, version=ver, ciudadano=self.ciud)

    def test_flujo_espera_llamado_atencion(self):
        motor.iniciar(self.caso, autor=self.jefe)
        self.caso.refresh_from_db()
        # Encolado y en espera, sin box.
        self.assertEqual(self.caso.estado, Caso.Estado.EN_ESPERA)
        self.assertTrue(self.caso.en_filas.filter(atendido=False, box__isnull=True).exists())

        # No se puede atender sin llamar.
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(self.caso, {"titulo": "x", "contenido": "y", "firmada": True}, autor=self.jefe)

        # Llamar desde el box: queda en el mismo nodo, ahora en atención,
        # asignado al médico que llamó.
        motor.llamar(self.caso, box_id=self.box.id, autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.nodo_actual_id, self.ate.id)
        self.assertEqual(self.caso.estado, Caso.Estado.EN_EVALUACION)
        self.assertEqual(self.caso.asignado_a_id, self.jefe.id)
        self.assertTrue(self.caso.en_filas.filter(box=self.box).exists())

        # Ahora sí se atiende y avanza al cierre.
        motor.avanzar(self.caso, {"titulo": "Consulta", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.CERRADO)
        self.assertTrue(EntradaHistoria.objects.filter(historia__ciudadano=self.ciud).exists())

    def test_en_fila_solo_mientras_espera(self):
        from .serializers import CasoSerializer

        motor.iniciar(self.caso, autor=self.jefe)
        self.caso.refresh_from_db()
        # Encolado: en_fila True (se ve solo en la Fila, no en la bandeja).
        self.assertTrue(CasoSerializer(self.caso).data["en_fila"])
        motor.llamar(self.caso, box_id=self.box.id, autor=self.jefe)
        self.caso.refresh_from_db()
        # Llamado: ya no está en la fila.
        self.assertFalse(CasoSerializer(self.caso).data["en_fila"])

    def test_acciones_receta_y_estudio(self):
        from apps.registros.models import Estudio, Receta

        motor.iniciar(self.caso, autor=self.jefe)
        motor.agregar_estudio(self.caso, "Radiografía de tórax", autor=self.jefe)
        motor.agregar_receta(self.caso, "Ibuprofeno 400mg", autor=self.jefe)
        self.assertTrue(Estudio.objects.filter(historia__ciudadano=self.ciud, tipo="Radiografía de tórax").exists())
        self.assertTrue(Receta.objects.filter(historia__ciudadano=self.ciud, detalle="Ibuprofeno 400mg").exists())


class EstudioDerivadoTests(TestCase):
    """Estudio que deriva a otra área y vuelve: el caso espera y se reactiva solo."""

    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("jefe2@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.cardio = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.imagenes = Area.objects.create(institucion=self.inst, nombre="Imágenes")

        # Flujo de Imágenes (destino), publicado: Inicio → Atención → Fin.
        f_img = Flujo.objects.create(institucion=self.inst, area=self.imagenes, titulo="Realizar estudio")
        v_img = VersionFlujo.objects.create(flujo=f_img, numero=1)
        ii = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        ia = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.ATENCION, titulo="Informe")
        iff = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=v_img, origen=ii, destino=ia)
        Conexion.objects.create(version=v_img, origen=ia, destino=iff)
        v_img.estado = VersionFlujo.Estado.PUBLICADA
        v_img.save()

        # Flujo de Cardio (origen): Inicio → Atención → Fin.
        f_card = Flujo.objects.create(institucion=self.inst, area=self.cardio, titulo="Atención cardio")
        v_card = VersionFlujo.objects.create(flujo=f_card, numero=1)
        ci = Nodo.objects.create(version=v_card, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ca = Nodo.objects.create(version=v_card, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
        cf = Nodo.objects.create(version=v_card, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=v_card, origen=ci, destino=self.ca)
        Conexion.objects.create(version=v_card, origen=self.ca, destino=cf)

        self.ciud = Ciudadano.objects.create(institucion=self.inst, nombre="Pac", apellido="Est")
        self.caso = Caso.objects.create(institucion=self.inst, version=v_card, ciudadano=self.ciud)
        motor.iniciar(self.caso, autor=self.jefe)  # queda en la atención

    def test_round_trip(self):
        sub = motor.solicitar_estudio_derivado(self.caso, "Resonancia", self.imagenes, autor=self.jefe)
        self.caso.refresh_from_db()
        # El caso de origen quedó esperando; el sub-caso arrancó en Imágenes.
        self.assertTrue(self.caso.esperando)
        self.assertEqual(sub.origen_id, self.caso.id)
        self.assertTrue(sub.bloquea_origen)
        self.assertIsNotNone(sub.estudio_id)

        # No se puede atender mientras espera.
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(self.caso, {"titulo": "x", "contenido": "y", "firmada": True}, autor=self.jefe)

        # Imágenes informa el estudio y cierra el sub-caso → vuelve al origen.
        motor.avanzar(sub, {"titulo": "Informe", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.caso.refresh_from_db(); sub.refresh_from_db()
        self.assertEqual(sub.estado, Caso.Estado.CERRADO)
        self.assertTrue(sub.estudio.realizado)
        self.assertFalse(self.caso.esperando)
        self.assertEqual(self.caso.estado, Caso.Estado.EN_EVALUACION)


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
