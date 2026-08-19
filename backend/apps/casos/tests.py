"""
Tests del motor de ejecución.

Construye un flujo realista y corre un caso de punta a punta verificando las
transiciones, los efectos (estado, derivación, historia clínica, fila) y la
validación previa a publicar.

    Inicio → Formulario(datos) → Decisión(¿prioridad?) →
        ├─ [Alta]    → Derivar(Cardiología) → Estado(Atendido) → Fin
        └─ [default] → Espera(Sala) → Atención(evaluación) → Fin
"""
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Box, Grupo, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria

from . import motor
from .models import Caso, EventoCaso, ItemFila, Notificacion, ValorCampo


class MotorTestCase(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user("op@cauce.local", "x", nombre="Op")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.admision = Area.objects.create(institucion=self.inst, nombre="Admisión")
        self.cardio = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        # self.user opera como médico (puede firmar atenciones en los tests). Firmar
        # exige matrícula cargada en el legajo (`motor._exigir_medico`), así que el
        # legajo es parte del setup mínimo de un médico que firma.
        Membresia.objects.create(usuario=self.user, institucion=self.inst, rol=Membresia.Rol.MEDICO)
        LegajoProfesional.objects.create(usuario=self.user, matricula="MP-10001")

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

    def _hasta_atencion(self):
        """Lleva un caso hasta el nodo de Atención por la rama por defecto."""
        caso = motor.iniciar(self._nuevo_caso(), autor=self.user)
        caso = motor.avanzar(caso, {"valores": {self.campo_prioridad.id: "Normal"}}, autor=self.user)
        return motor.avanzar(caso, {}, autor=self.user)

    def _sin_legajo(self):
        """Borra el legajo y devuelve el usuario recargado.

        Hace falta releerlo: `legajo` es una relación uno-a-uno y queda cacheada en
        la instancia en memoria, así que `self.user.legajo` seguiría devolviendo el
        objeto borrado y el test pasaría por la razón equivocada.
        """
        LegajoProfesional.objects.filter(usuario=self.user).delete()
        return Usuario.objects.get(pk=self.user.pk)

    def test_firmar_sin_matricula_falla(self):
        """Firmar es un acto profesional: exige matrícula cargada en el legajo."""
        autor = self._sin_legajo()
        caso = self._hasta_atencion()
        with self.assertRaises(motor.ErrorMotor):
            motor.avanzar(caso, {"titulo": "Evaluación", "contenido": "OK", "firmada": True}, autor=autor)

    def test_atencion_sin_firmar_no_exige_matricula(self):
        """Registrar la atención sin firmarla sí puede hacerse sin matrícula."""
        autor = self._sin_legajo()
        caso = self._hasta_atencion()
        caso = motor.avanzar(caso, {"titulo": "Evaluación", "contenido": "OK", "firmada": False}, autor=autor)
        self.assertEqual(caso.estado, Caso.Estado.CERRADO)
        entrada = EntradaHistoria.objects.get(caso=caso)
        self.assertFalse(entrada.firmada)
        self.assertEqual(entrada.matricula, "")

    def test_la_firma_asienta_la_matricula(self):
        """La matrícula queda como snapshot en la entrada (puede cambiar después)."""
        caso = self._hasta_atencion()
        caso = motor.avanzar(caso, {"titulo": "Evaluación", "contenido": "OK", "firmada": True}, autor=self.user)
        entrada = EntradaHistoria.objects.get(caso=caso)
        self.assertTrue(entrada.firmada)
        self.assertEqual(entrada.matricula, "MP-10001")

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

    def _flujo_receptor(self, area, titulo="Receptor", origen="ambos"):
        flujo = Flujo.objects.create(institucion=area.institucion, area=area, titulo=titulo)
        version = VersionFlujo.objects.create(
            flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        inicio = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.INICIO, titulo="Inicio", config={"origen": origen}
        )
        atencion = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Atencion")
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=version, origen=inicio, destino=atencion)
        Conexion.objects.create(version=version, origen=atencion, destino=fin)
        return flujo

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

        # Imágenes informa el estudio (con resultado estructurado) y cierra → vuelve al origen.
        motor.avanzar(sub, {"titulo": "Informe", "contenido": "ok", "firmada": True, "resultado": "alterado"}, autor=self.jefe)
        self.caso.refresh_from_db(); sub.refresh_from_db()
        self.assertEqual(sub.estado, Caso.Estado.CERRADO)
        self.assertTrue(sub.estudio.realizado)
        self.assertEqual(sub.estudio.resultado, "alterado")  # resultado cargado
        self.assertFalse(self.caso.esperando)
        self.assertEqual(self.caso.estado, Caso.Estado.EN_EVALUACION)

    def test_interconsulta_round_trip(self):
        # El mismo mecanismo general sirve para interconsultas (sin estudio).
        sub = motor.solicitar_interconsulta(self.caso, self.imagenes, "Descartar foco", autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertTrue(self.caso.esperando)
        self.assertEqual(sub.origen_id, self.caso.id)
        self.assertTrue(sub.bloquea_origen)
        self.assertIsNone(sub.estudio_id)  # interconsulta no crea estudio
        motor.avanzar(sub, {"titulo": "Opinión", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)
        self.assertEqual(self.caso.estado, Caso.Estado.EN_EVALUACION)


    def test_no_deriva_estudio_a_area_de_otra_institucion(self):
        from apps.registros.models import Estudio

        otra = Institucion.objects.create(nombre="Hospital Norte")
        area_ajena = Area.objects.create(institucion=otra, nombre="Imagenes")
        estudios_antes = Estudio.objects.count()

        with self.assertRaises(motor.ErrorMotor):
            motor.solicitar_estudio_derivado(self.caso, "TAC", area_ajena, autor=self.jefe)

        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)
        self.assertEqual(Estudio.objects.count(), estudios_antes)

    def test_interconsulta_no_usa_flujos_solo_manual(self):
        Nodo.objects.filter(
            version__flujo__area=self.imagenes, tipo=Nodo.Tipo.INICIO
        ).update(config={"origen": "manual"})

        with self.assertRaises(motor.ErrorMotor) as err:
            motor.solicitar_interconsulta(self.caso, self.imagenes, "Ver", autor=self.jefe)

        self.assertIn("derivaciones", str(err.exception))

    def test_interconsulta_falla_si_hay_mas_de_un_receptor(self):
        self._flujo_receptor(self.imagenes, titulo="Segundo receptor", origen="derivado")

        with self.assertRaises(motor.ErrorMotor) as err:
            motor.solicitar_interconsulta(self.caso, self.imagenes, "Ver", autor=self.jefe)

        self.assertIn("mas de un flujo receptor", str(err.exception))

    def test_subcaso_cancelado_no_bloquea_el_retorno_del_origen(self):
        sub_cancelado = motor.solicitar_interconsulta(self.caso, self.imagenes, "Primera opinion", autor=self.jefe)
        sub_pendiente = motor.solicitar_interconsulta(self.caso, self.imagenes, "Segunda opinion", autor=self.jefe)

        motor.cancelar_caso(sub_cancelado, autor=self.jefe, motivo="No corresponde")
        self.caso.refresh_from_db()
        self.assertTrue(self.caso.esperando)

        motor.avanzar(sub_pendiente, {"titulo": "Opinion", "contenido": "ok", "firmada": True}, autor=self.jefe)
        self.caso.refresh_from_db()
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

    def _flujo_publicado(self, area, titulo="Destino", origen="ambos"):
        flujo = Flujo.objects.create(institucion=area.institucion, area=area, titulo=titulo)
        version = VersionFlujo.objects.create(
            flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        inicio = Nodo.objects.create(
            version=version, tipo=Nodo.Tipo.INICIO, titulo="Inicio", config={"origen": origen}
        )
        atencion = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Atencion")
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=version, origen=inicio, destino=atencion)
        Conexion.objects.create(version=version, origen=atencion, destino=fin)
        return flujo

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


    def test_no_deriva_a_area_de_otra_institucion(self):
        otra = Institucion.objects.create(nombre="Hospital Norte")
        area_ajena = Area.objects.create(institucion=otra, nombre="Cardiologia")
        nodo = Nodo.objects.get(version=self.vi, tipo=Nodo.Tipo.DERIVAR)
        nodo.config = {"area_destino_id": area_ajena.id}
        nodo.save(update_fields=["config"])

        caso = Caso.objects.create(institucion=self.inst, version=self.vi)
        with self.assertRaises(motor.ErrorMotor):
            motor.iniciar(caso, autor=None)

        caso.refresh_from_db()
        self.assertIsNone(caso.nodo_actual_id)
        self.assertFalse(caso.eventos.exists())

    def test_no_deriva_a_flujo_de_otra_institucion(self):
        otra = Institucion.objects.create(nombre="Hospital Norte")
        area_ajena = Area.objects.create(institucion=otra, nombre="Cardiologia")
        flujo_ajeno = self._flujo_publicado(area_ajena, titulo="Cardio Norte")
        nodo = Nodo.objects.get(version=self.vi, tipo=Nodo.Tipo.DERIVAR)
        nodo.config = {"area_destino_id": self.cardio.id, "flujo_destino_id": flujo_ajeno.id}
        nodo.save(update_fields=["config"])

        caso = Caso.objects.create(institucion=self.inst, version=self.vi)
        with self.assertRaises(motor.ErrorMotor):
            motor.iniciar(caso, autor=None)

        self.assertEqual(Caso.objects.filter(origen=caso).count(), 0)

    def test_no_deriva_a_flujo_solo_manual(self):
        Nodo.objects.filter(
            version__flujo=self.f_cardio, tipo=Nodo.Tipo.INICIO
        ).update(config={"origen": "manual"})

        caso = Caso.objects.create(institucion=self.inst, version=self.vi)
        with self.assertRaises(motor.ErrorMotor) as err:
            motor.iniciar(caso, autor=None)

        self.assertIn("recibir derivaciones", str(err.exception))


class CondicionesTests(TestCase):
    """
    Reglas de rama de una Decisión.

    Se prueban sobre `_cumple` directamente porque es la función que decide por
    dónde sigue un caso: si se equivoca, un paciente toma el circuito
    equivocado. El resto del motor se apoya en ella.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.flujo = Flujo.objects.create(institucion=self.inst, titulo="F")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.caso = Caso.objects.create(institucion=self.inst, version=self.version)
        self.campos = {}

    def _cargar(self, nombre, valor):
        """Crea el campo (si hace falta) y le carga un valor al caso."""
        if nombre not in self.campos:
            self.campos[nombre] = Campo.objects.create(
                formulario=self.form, label=nombre, tipo="texto_corto", orden=len(self.campos)
            )
        ValorCampo.objects.update_or_create(
            caso=self.caso, campo=self.campos[nombre], defaults={"valor": str(valor)}
        )
        return self.campos[nombre].pk

    def _evalua(self, condicion):
        return motor._cumple(condicion, self.caso)

    def _regla(self, nombre, operador, valor=None):
        return {"campo": self.campos[nombre].pk, "operador": operador, "valor": valor}

    # --- Operadores -------------------------------------------------------- #

    def test_orden_compara_como_numero(self):
        self._cargar("edad", 70)
        self.assertTrue(self._evalua(self._regla("edad", ">", "65")))
        self.assertFalse(self._evalua(self._regla("edad", "<", "65")))
        self.assertTrue(self._evalua(self._regla("edad", ">=", "70")))
        self.assertTrue(self._evalua(self._regla("edad", "<=", "70")))

    def test_orden_compara_fechas(self):
        """Antes `>` sobre una fecha daba siempre False, en silencio."""
        self._cargar("ultimo_control", "2026-03-15")
        self.assertTrue(self._evalua(self._regla("ultimo_control", "<", "2026-06-01")))
        self.assertFalse(self._evalua(self._regla("ultimo_control", ">", "2026-06-01")))

    def test_entre_incluye_los_extremos(self):
        self._cargar("edad", 65)
        self.assertTrue(self._evalua(self._regla("edad", "entre", "65,80")))
        self.assertTrue(self._evalua(self._regla("edad", "entre", ["18", "65"])))
        self._cargar("edad", 17)
        self.assertFalse(self._evalua(self._regla("edad", "entre", "18,65")))

    def test_en_lista(self):
        self._cargar("obra", "PAMI")
        self.assertTrue(self._evalua(self._regla("obra", "en", "OSDE, PAMI, Swiss")))
        self.assertFalse(self._evalua(self._regla("obra", "no_en", "OSDE, PAMI")))

    def test_vacio_distingue_sin_cargar_de_cargado(self):
        """
        El caso importante: un campo que nunca se completó.

        `vacio` tiene que responder True ahí, y por eso se resuelve antes del
        descarte general por «valor ausente».
        """
        campo = Campo.objects.create(formulario=self.form, label="alergias", tipo="texto_corto", orden=99)
        sin_cargar = {"campo": campo.pk, "operador": "vacio"}
        self.assertTrue(self._evalua(sin_cargar))
        self.assertFalse(self._evalua({**sin_cargar, "operador": "no_vacio"}))

        ValorCampo.objects.create(caso=self.caso, campo=campo, valor="penicilina")
        self.assertFalse(self._evalua(sin_cargar))
        self.assertTrue(self._evalua({**sin_cargar, "operador": "no_vacio"}))

    def test_una_cadena_vacia_cuenta_como_vacia(self):
        campo = Campo.objects.create(formulario=self.form, label="nota", tipo="texto_corto", orden=98)
        ValorCampo.objects.create(caso=self.caso, campo=campo, valor="   ")
        self.assertTrue(self._evalua({"campo": campo.pk, "operador": "vacio"}))

    def test_no_contiene(self):
        self._cargar("motivo", "Dolor torácico agudo")
        self.assertTrue(self._evalua(self._regla("motivo", "contiene", "torácico")))
        self.assertTrue(self._evalua(self._regla("motivo", "no_contiene", "fractura")))

    # --- Composición ------------------------------------------------------- #

    def test_y_exige_las_dos(self):
        self._cargar("edad", 70)
        self._cargar("motivo", "Dolor torácico")
        regla = {"op": "y", "reglas": [
            self._regla("edad", ">", "65"),
            self._regla("motivo", "contiene", "torácico"),
        ]}
        self.assertTrue(self._evalua(regla))

        self._cargar("edad", 40)
        self.assertFalse(self._evalua(regla))

    def test_o_alcanza_con_una(self):
        self._cargar("edad", 40)
        self._cargar("motivo", "Dolor torácico")
        self.assertTrue(self._evalua({"op": "o", "reglas": [
            self._regla("edad", ">", "65"),
            self._regla("motivo", "contiene", "torácico"),
        ]}))

    def test_anidado_permite_a_y_b_o_c(self):
        """«(mayor de 65 Y con dolor torácico) O urgente» — el caso real."""
        self._cargar("edad", 30)
        self._cargar("motivo", "Fractura")
        self._cargar("triage", "rojo")
        regla = {"op": "o", "reglas": [
            {"op": "y", "reglas": [
                self._regla("edad", ">", "65"),
                self._regla("motivo", "contiene", "torácico"),
            ]},
            self._regla("triage", "=", "rojo"),
        ]}
        self.assertTrue(self._evalua(regla))  # entra por el triage rojo

        self._cargar("triage", "verde")
        self.assertFalse(self._evalua(regla))  # ya no cumple ninguna de las dos

    def test_las_condiciones_viejas_de_una_sola_regla_siguen_funcionando(self):
        """Compatibilidad: es la forma que tienen todas las conexiones guardadas."""
        self._cargar("triage", "rojo")
        self.assertTrue(self._evalua(self._regla("triage", "=", "rojo")))
        self.assertFalse(self._evalua(self._regla("triage", "=", "verde")))

    def test_sin_condicion_es_la_rama_por_defecto(self):
        self.assertTrue(self._evalua({}))
        self.assertTrue(self._evalua(None))
        self.assertTrue(self._evalua({"op": "y", "reglas": []}))

    def test_la_validacion_ve_los_campos_de_una_regla_compuesta(self):
        """
        Sin esto la validación mentía: una regla compuesta no tiene campo arriba
        de todo, así que se salteaba entera y nunca avisaba del campo inexistente.
        """
        c1 = self._cargar("edad", 70)
        anidada = {"op": "o", "reglas": [
            {"op": "y", "reglas": [
                {"campo": c1, "operador": ">", "valor": "65"},
                {"campo": 999, "operador": "=", "valor": "x"},
            ]},
        ]}
        self.assertEqual(motor.campos_de_condicion(anidada), {c1, 999})
        self.assertEqual(motor.campos_de_condicion({"campo": c1}), {c1})
        self.assertEqual(motor.campos_de_condicion({}), set())

    def test_contiene_ignora_tildes_y_mayusculas(self):
        """
        En una admisión se escribe «dolor toracico» tanto como «Dolor Torácico».
        Si la regla sólo matchea con la tilde puesta, el paciente toma el
        circuito equivocado y nadie se entera.
        """
        self._cargar("motivo", "Dolor toracico agudo")
        self.assertTrue(self._evalua(self._regla("motivo", "contiene", "torácico")))
        self.assertTrue(self._evalua(self._regla("motivo", "contiene", "TORACICO")))

        self._cargar("motivo", "Dolor Torácico")
        self.assertTrue(self._evalua(self._regla("motivo", "contiene", "toracico")))

    def test_la_igualdad_sigue_siendo_exacta(self):
        """
        `=` compara tal cual: sus valores salen de una lista cerrada (una
        selección única), donde «Alta» y «alta» pueden ser opciones distintas.
        """
        self._cargar("triage", "Rojo")
        self.assertFalse(self._evalua(self._regla("triage", "=", "rojo")))
        self.assertTrue(self._evalua(self._regla("triage", "=", "Rojo")))


class IntegracionTests(TestCase):
    """
    Nodo de integración: la pieza que hace verdadera la promesa de «se integra
    con los sistemas existentes».

    Lo que más se prueba acá es lo que NO tiene que pasar. El nodo deja que
    alguien con permiso de diseño configure una URL que llama el servidor, así
    que sin lista blanca es un SSRF con formulario.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.flujo = Flujo.objects.create(institucion=self.inst, titulo="F")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.caso = Caso.objects.create(institucion=self.inst, version=self.version)

    def _nodo(self, **config):
        return Nodo.objects.create(
            version=self.version, tipo="integracion", titulo="Padrón", config=config
        )

    # --- Lista blanca ------------------------------------------------------ #

    @override_settings(INTEGRACIONES_PERMITIDAS=[])
    def test_sin_lista_blanca_la_funcion_esta_apagada(self):
        self.assertFalse(motor._host_permitido("https://padron.gob.ar/api"))

    @override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
    def test_solo_pasa_el_host_habilitado_y_sus_subdominios(self):
        self.assertTrue(motor._host_permitido("https://padron.gob.ar/api/x"))
        self.assertTrue(motor._host_permitido("https://api.padron.gob.ar/x"))
        self.assertFalse(motor._host_permitido("https://otro.com/x"))
        # Y no alcanza con que el host TERMINE parecido.
        self.assertFalse(motor._host_permitido("https://malpadron.gob.ar/x"))

    @override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
    def test_no_se_puede_apuntar_a_la_red_interna(self):
        """
        El caso que motiva la lista blanca: alguien con permiso de diseño
        apuntando el backend a un servicio interno o al metadata de la nube.
        """
        for url in [
            "http://localhost:5432/",
            "http://127.0.0.1:8000/api/usuarios/",
            "http://169.254.169.254/latest/meta-data/",
            "http://backend:8000/admin/",
            "file:///etc/passwd",
        ]:
            self.assertFalse(motor._host_permitido(url), url)

    @override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
    def test_solo_http_y_https(self):
        self.assertFalse(motor._host_permitido("ftp://padron.gob.ar/x"))

    # --- Comportamiento ante fallas ---------------------------------------- #

    @override_settings(INTEGRACIONES_PERMITIDAS=[])
    def test_un_destino_no_habilitado_anota_y_el_caso_sigue(self):
        """
        Por defecto el caso NO se traba: un padrón caído no puede dejar a un
        paciente detenido en el circuito.
        """
        nodo = self._nodo(url="https://padron.gob.ar/api")
        motor._aplicar_efecto_entrada(self.caso, nodo)

        evento = EventoCaso.objects.filter(caso=self.caso).last()
        self.assertIn("Integración fallida", evento.titulo)
        self.assertIn("no está habilitado", evento.detalle)

    @override_settings(INTEGRACIONES_PERMITIDAS=[])
    def test_marcado_obligatorio_el_flujo_se_detiene(self):
        """Para los pasos donde seguir sin el dato no tendría sentido."""
        nodo = self._nodo(url="https://padron.gob.ar/api", obligatorio=True)
        with self.assertRaises(motor.ErrorMotor):
            motor._aplicar_efecto_entrada(self.caso, nodo)

    def test_sin_url_configurada_lo_dice(self):
        nodo = self._nodo()
        motor._aplicar_efecto_entrada(self.caso, nodo)
        self.assertIn("no tiene URL", EventoCaso.objects.filter(caso=self.caso).last().detalle)

    @override_settings(INTEGRACIONES_PERMITIDAS=["padron.gob.ar"])
    def test_la_validacion_avisa_del_destino_no_habilitado(self):
        """
        El flujo se dibuja hoy y se ejecuta mañana: enterarse al publicar es
        mucho mejor que descubrirlo con un paciente esperando.
        """
        ini = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        integ = self._nodo(url="https://otro-sistema.com/api")
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=self.version, origen=ini, destino=integ, condicion={})
        Conexion.objects.create(version=self.version, origen=integ, destino=fin, condicion={})

        titulos = [p["titulo"] for p in motor.validar_version(self.version)]
        self.assertIn("Destino de integración no habilitado", titulos)

        # Con el host habilitado, deja de ser un problema.
        integ.config = {"url": "https://padron.gob.ar/api"}
        integ.save()
        titulos = [p["titulo"] for p in motor.validar_version(self.version)]
        self.assertNotIn("Destino de integración no habilitado", titulos)

    def test_la_validacion_avisa_de_la_integracion_sin_url(self):
        ini = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        integ = self._nodo()
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=self.version, origen=ini, destino=integ, condicion={})
        Conexion.objects.create(version=self.version, origen=integ, destino=fin, condicion={})
        self.assertIn("«Padrón» no tiene URL", [p["titulo"] for p in motor.validar_version(self.version)])

    # --- Lectura de la respuesta ------------------------------------------- #

    def test_extraer_sigue_una_ruta_anidada(self):
        datos = {"paciente": {"cobertura": {"plan": "PAMI"}}, "hist": [{"a": 1}, {"a": 2}]}
        self.assertEqual(motor._extraer(datos, "paciente.cobertura.plan"), "PAMI")
        self.assertEqual(motor._extraer(datos, "hist.1.a"), 2)
        self.assertIsNone(motor._extraer(datos, "paciente.no.existe"))
        self.assertEqual(motor._extraer(datos, ""), datos)


class NotificacionNodoTests(TestCase):
    """Nodo de notificación: avisar a un equipo desde el propio flujo."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Médicos de guardia")
        self.medico = Usuario.objects.create_user(email="med@test.local", password="x")
        self.grupo.miembros.add(self.medico)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="F")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.ciudadano = Ciudadano.objects.create(institucion=self.inst, nombre="Ana", apellido="Pérez")
        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.version, ciudadano=self.ciudadano
        )

    def test_avisa_a_los_integrantes_del_grupo_responsable(self):
        nodo = Nodo.objects.create(
            version=self.version, tipo="notificar", titulo="Avisar a guardia",
            config={"titulo": "Paciente crítico", "detalle": "{paciente} necesita atención"},
        )
        nodo.grupos.add(self.grupo)

        motor._aplicar_efecto_entrada(self.caso, nodo)

        aviso = Notificacion.objects.get(usuario=self.medico)
        self.assertEqual(aviso.titulo, "Paciente crítico")
        # {paciente} se reemplaza: un aviso que dice a quién se refiere sirve.
        self.assertEqual(aviso.detalle, "Ana Pérez necesita atención")
        self.assertEqual(aviso.caso_id, self.caso.pk)

    def test_puede_avisar_solo_a_quien_tiene_el_caso(self):
        self.caso.asignado_a = self.medico
        self.caso.save()
        nodo = Nodo.objects.create(
            version=self.version, tipo="notificar", titulo="Recordatorio",
            config={"titulo": "Pendiente", "a": "asignado"},
        )
        motor._aplicar_efecto_entrada(self.caso, nodo)
        self.assertEqual(Notificacion.objects.filter(usuario=self.medico).count(), 1)

    def test_el_motor_lo_atraviesa_solo(self):
        """Es un nodo automático: el caso no se detiene ahí."""
        self.assertIn("notificar", motor.TIPOS_AUTOMATICOS)
        self.assertIn("integracion", motor.TIPOS_AUTOMATICOS)


class TiemposTests(TestCase):
    """
    Esperas programadas y SLA.

    Hasta acá la duración de una «espera por tiempo» era un rótulo: el caso
    entraba y no volvía nunca. Y no había forma de decir «si tarda más de X,
    avisá», que es lo primero que pide quien dirige un servicio.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Médicos")
        self.medico = Usuario.objects.create_user(email="med@t.local", password="x")
        self.jefe = Usuario.objects.create_user(email="jefe@t.local", password="x")
        self.grupo.miembros.add(self.medico)
        m = Membresia.objects.create(
            usuario=self.jefe, institucion=self.inst, rol=Membresia.Rol.JEFE_AREA, activo=True
        )
        m.areas.add(self.area)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="F")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

    # --- Interpretación de la duración ------------------------------------- #

    def test_entiende_la_duracion_escrita_a_mano(self):
        """
        El texto libre ya está guardado en los flujos existentes: la duración
        nació como rótulo. Migrarlo no aportaría nada; interpretarlo alcanza.
        """
        casos = [
            ({"duracion": "6 horas"}, 360),
            ({"duracion": "30 minutos"}, 30),
            ({"duracion": "2 días"}, 2880),
            ({"duracion": "1 mes"}, 43200),
            ({"duracion": "1,5 horas"}, 90),
            ({"minutos": 15}, 15),
            # Los minutos explícitos le ganan al texto.
            ({"minutos": 5, "duracion": "3 horas"}, 5),
        ]
        for config, esperado in casos:
            self.assertEqual(motor.minutos_de_espera(config), esperado, config)

    def test_una_duracion_que_no_se_entiende_no_inventa_un_plazo(self):
        """Mejor que quede en reactivación manual a que se reactive cuando no toca."""
        for config in [{}, {"duracion": ""}, {"duracion": "cuando el médico diga"}, {"minutos": 0}]:
            self.assertIsNone(motor.minutos_de_espera(config))

    # --- Reactivación ------------------------------------------------------- #

    def _flujo_con_espera(self, config):
        ini = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        esp = Nodo.objects.create(version=self.version, tipo="tiempo", titulo="Observación", config=config)
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Alta")
        Conexion.objects.create(version=self.version, origen=ini, destino=esp, condicion={})
        Conexion.objects.create(version=self.version, origen=esp, destino=fin, condicion={})
        caso = Caso.objects.create(institucion=self.inst, version=self.version, area_actual=self.area)
        motor.iniciar(caso)
        return caso, esp, fin

    def test_al_entrar_a_la_espera_queda_agendado_el_vencimiento(self):
        caso, esp, _ = self._flujo_con_espera({"duracion": "6 horas"})
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, esp.pk)
        self.assertIsNotNone(caso.reactivar_en)
        faltan = (caso.reactivar_en - timezone.now()).total_seconds() / 60
        self.assertAlmostEqual(faltan, 360, delta=2)

    def test_el_proceso_reactiva_el_caso_vencido(self):
        caso, esp, fin = self._flujo_con_espera({"duracion": "6 horas"})
        # Se adelanta el reloj poniendo el vencimiento en el pasado.
        Caso.objects.filter(pk=caso.pk).update(reactivar_en=timezone.now() - timedelta(minutes=1))

        call_command("correr_tiempos", verbosity=0)

        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, fin.pk)
        self.assertIsNone(caso.reactivar_en)

    def test_no_toca_una_espera_que_todavia_no_vencio(self):
        caso, esp, _ = self._flujo_con_espera({"duracion": "6 horas"})
        call_command("correr_tiempos", verbosity=0)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, esp.pk)

    def test_una_espera_sin_duracion_entendible_no_se_reactiva_sola(self):
        caso, esp, _ = self._flujo_con_espera({"duracion": "hasta que el médico lo indique"})
        caso.refresh_from_db()
        self.assertIsNone(caso.reactivar_en)
        call_command("correr_tiempos", verbosity=0)
        caso.refresh_from_db()
        self.assertEqual(caso.nodo_actual_id, esp.pk)

    # --- SLA ---------------------------------------------------------------- #

    def _flujo_con_sla(self, config):
        ini = Nodo.objects.create(version=self.version, tipo="inicio", titulo="Inicio")
        paso = Nodo.objects.create(version=self.version, tipo="form", titulo="Triage", config=config)
        Conexion.objects.create(version=self.version, origen=ini, destino=paso, condicion={})
        paso.grupos.add(self.grupo)
        caso = Caso.objects.create(institucion=self.inst, version=self.version, area_actual=self.area)
        motor.iniciar(caso)
        return caso, paso

    def test_avisa_al_grupo_cuando_el_paso_se_pasa_del_plazo(self):
        caso, paso = self._flujo_con_sla({"sla_minutos": 20})
        Caso.objects.filter(pk=caso.pk).update(paso_desde=timezone.now() - timedelta(minutes=25))

        call_command("correr_tiempos", verbosity=0)

        aviso = Notificacion.objects.filter(usuario=self.medico).last()
        self.assertEqual(aviso.titulo, "Paso demorado")
        self.assertIn("Triage", aviso.detalle)

    def test_no_repite_el_aviso_en_cada_pasada(self):
        """Molestar cada cinco minutos consigue que se ignoren todos los avisos."""
        caso, _ = self._flujo_con_sla({"sla_minutos": 20})
        Caso.objects.filter(pk=caso.pk).update(paso_desde=timezone.now() - timedelta(minutes=25))

        call_command("correr_tiempos", verbosity=0)
        call_command("correr_tiempos", verbosity=0)
        call_command("correr_tiempos", verbosity=0)

        self.assertEqual(
            Notificacion.objects.filter(usuario=self.medico, titulo="Paso demorado").count(), 1
        )

    def test_escalar_avisa_tambien_al_jefe_del_area(self):
        caso, _ = self._flujo_con_sla({"sla_minutos": 20, "sla_accion": "escalar"})
        Caso.objects.filter(pk=caso.pk).update(paso_desde=timezone.now() - timedelta(minutes=25))

        call_command("correr_tiempos", verbosity=0)

        self.assertTrue(Notificacion.objects.filter(usuario=self.jefe).exists())

    def test_sin_sla_declarado_no_avisa_nada(self):
        caso, _ = self._flujo_con_sla({})
        Caso.objects.filter(pk=caso.pk).update(paso_desde=timezone.now() - timedelta(days=3))
        call_command("correr_tiempos", verbosity=0)
        self.assertFalse(Notificacion.objects.filter(titulo="Paso demorado").exists())

    def test_el_reloj_del_paso_se_reinicia_al_avanzar(self):
        """
        Sin esto el SLA mediría desde que empezó el caso y avisaría de demoras
        que no existen.
        """
        caso, paso = self._flujo_con_sla({"sla_minutos": 20})
        Caso.objects.filter(pk=caso.pk).update(
            paso_desde=timezone.now() - timedelta(minutes=25), sla_avisado=True
        )
        fin = Nodo.objects.create(version=self.version, tipo="fin", titulo="Fin")
        Conexion.objects.create(version=self.version, origen=paso, destino=fin, condicion={})

        caso.refresh_from_db()
        motor.avanzar(caso, {"valores": {}})

        caso.refresh_from_db()
        self.assertLess((timezone.now() - caso.paso_desde).total_seconds(), 5)
        self.assertFalse(caso.sla_avisado)


class FirmaConfigurableTests(TestCase):
    """
    Quién puede registrar una atención lo declara el NODO.

    Estaba clavado en el código: sólo rol `medico`, siempre con matrícula. Eso
    bloquea media docena de procesos reales de un hospital —una consulta de
    enfermería, una entrevista de trabajo social, una admisión administrativa—
    donde el acto lo firma otra persona.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="F")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.version, area_actual=self.area
        )

    def _persona(self, email, rol, matricula=None):
        u = Usuario.objects.create_user(email=email, password="x")
        m = Membresia.objects.create(usuario=u, institucion=self.inst, rol=rol, activo=True)
        m.areas.add(self.area)
        if matricula is not None:
            LegajoProfesional.objects.create(usuario=u, matricula=matricula)
        return u

    def _nodo(self, **config):
        return Nodo.objects.create(
            version=self.version, tipo="atencion", titulo="Consulta", config=config
        )

    # --- Compatibilidad ----------------------------------------------------- #

    def test_sin_configurar_se_comporta_como_antes(self):
        """
        Los flujos ya publicados no tienen esta config y su semántica no puede
        cambiar sola: siguen siendo médico + matrícula.
        """
        self.assertEqual(motor.quien_firma(self._nodo()), (["medico"], True))

        enfermera = self._persona("enf@t.local", Membresia.Rol.ENFERMERIA)
        with self.assertRaises(motor.ErrorMotor):
            motor._exigir_firmante(self.caso, self._nodo(), enfermera)

    # --- Rol declarado por el nodo ------------------------------------------ #

    def test_un_paso_puede_declarar_que_lo_firma_enfermeria(self):
        nodo = self._nodo(firma_roles=["enfermeria"])
        enfermera = self._persona("enf@t.local", Membresia.Rol.ENFERMERIA, matricula="E-100")

        self.assertEqual(motor._exigir_firmante(self.caso, nodo, enfermera), "E-100")

    def test_puede_declarar_varios_roles(self):
        nodo = self._nodo(firma_roles=["medico", "enfermeria"])
        medico = self._persona("med@t.local", Membresia.Rol.MEDICO, matricula="M-1")
        enfermera = self._persona("enf@t.local", Membresia.Rol.ENFERMERIA, matricula="E-1")

        self.assertEqual(motor._exigir_firmante(self.caso, nodo, medico), "M-1")
        self.assertEqual(motor._exigir_firmante(self.caso, nodo, enfermera), "E-1")

    def test_quien_no_tiene_el_rol_declarado_no_firma(self):
        nodo = self._nodo(firma_roles=["enfermeria"])
        medico = self._persona("med@t.local", Membresia.Rol.MEDICO, matricula="M-1")

        with self.assertRaises(motor.ErrorMotor) as e:
            motor._exigir_firmante(self.caso, nodo, medico)
        # El mensaje dice QUIÉN puede, no sólo que no se puede.
        self.assertIn("Enfermería", str(e.exception))

    # --- Matrícula ---------------------------------------------------------- #

    def test_un_paso_administrativo_puede_no_exigir_matricula(self):
        """
        Una admisión la registra un administrativo, que no tiene matrícula: sin
        esto ese paso era imposible de modelar.
        """
        nodo = self._nodo(firma_roles=["administrativo"], firma_matricula=False)
        admin = self._persona("adm@t.local", Membresia.Rol.ADMINISTRATIVO)

        self.assertEqual(motor._exigir_firmante(self.caso, nodo, admin), "")

    def test_con_matricula_exigida_y_sin_legajo_no_firma(self):
        nodo = self._nodo(firma_roles=["enfermeria"])
        enfermera = self._persona("enf@t.local", Membresia.Rol.ENFERMERIA)

        with self.assertRaises(motor.ErrorMotor) as e:
            motor._exigir_firmante(self.caso, nodo, enfermera)
        self.assertIn("matrícula", str(e.exception))

    def test_sin_firmar_no_hace_falta_matricula(self):
        """La matrícula la exige el acto FIRMADO, no cargar la evolución."""
        nodo = self._nodo(firma_roles=["enfermeria"])
        enfermera = self._persona("enf@t.local", Membresia.Rol.ENFERMERIA)

        self.assertEqual(
            motor._exigir_firmante(self.caso, nodo, enfermera, requiere_matricula=False), ""
        )

    # --- Área --------------------------------------------------------------- #

    def test_hay_que_estar_asignado_al_area_del_caso(self):
        nodo = self._nodo(firma_roles=["medico"])
        otra = Area.objects.create(institucion=self.inst, nombre="Laboratorio")
        u = Usuario.objects.create_user(email="ajeno@t.local", password="x")
        m = Membresia.objects.create(
            usuario=u, institucion=self.inst, rol=Membresia.Rol.MEDICO, activo=True
        )
        m.areas.add(otra)
        LegajoProfesional.objects.create(usuario=u, matricula="M-9")

        with self.assertRaises(motor.ErrorMotor) as e:
            motor._exigir_firmante(self.caso, nodo, u)
        self.assertIn("Guardia", str(e.exception))

    def test_el_super_admin_firma_siempre(self):
        nodo = self._nodo(firma_roles=["enfermeria"])
        root = Usuario.objects.create_user(
            email="root@t.local", password="x", is_superuser=True, is_staff=True
        )
        self.assertEqual(motor._exigir_firmante(self.caso, nodo, root), "")

    def test_una_config_rota_cae_en_el_default_en_vez_de_abrir_el_paso(self):
        """
        Si `firma_roles` viene vacío o con basura, se vuelve a médico. Lo
        contrario —dejar pasar a cualquiera— sería un agujero abierto por un
        error de tipeo en el diseñador.
        """
        for config in [{"firma_roles": []}, {"firma_roles": "medico"}, {"firma_roles": None}]:
            self.assertEqual(motor.quien_firma(self._nodo(**config))[0], ["medico"])


class OperacionDeFilaTests(TestCase):
    """
    Lo que pasa en una cola de verdad además de llamar y atender: el paciente no
    aparece, lo llamaron por error, o empeoró esperando y hay que adelantarlo.
    """

    def setUp(self):
        self.jefe = Usuario.objects.create_superuser("jefe@cauce.local", "x", nombre="Jefe")
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.box = Box.objects.create(area=self.area, nombre="Box 1")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ate = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención", config={"con_fila": True}
        )
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.ate)
        Conexion.objects.create(version=self.ver, origen=self.ate, destino=fin)

    def _encolar(self, nombre):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.jefe)
        caso.refresh_from_db()
        return caso

    def _cola(self):
        """La cola tal como la pide la pantalla."""
        return list(
            ItemFila.objects.filter(nodo=self.ate, atendido=False, box__isnull=True)
            .order_by("-urgente", "orden", "ingreso")
            .values_list("caso__ciudadano__nombre", flat=True)
        )

    # --- No se presentó ---------------------------------------------------- #

    def test_el_ausente_sale_de_la_cola(self):
        """
        Antes quedaba llamado para siempre: ocupaba el box en la pantalla y
        contaba como si lo estuvieran atendiendo.
        """
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(caso, autor=self.jefe)
        self.assertEqual(self._cola(), [])

    def test_el_ausente_libera_el_box_y_al_profesional(self):
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        self.assertEqual(caso.en_filas.first().box_id, self.box.id)
        motor.marcar_ausente(caso, autor=self.jefe)
        caso.refresh_from_db()
        self.assertIsNone(caso.en_filas.first().box_id)
        self.assertIsNone(caso.asignado_a_id)

    def test_el_ausente_no_baja_el_promedio_de_atencion(self):
        """
        Si el ausente contara como atendido con duración cero, el indicador de
        tiempo de atención del servicio MEJORARÍA cuanta más gente se va sin ser
        atendida. `atendido_at` queda nulo, que es lo que mira la métrica.
        """
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(caso, autor=self.jefe)
        item = caso.en_filas.first()
        self.assertTrue(item.ausente)
        self.assertIsNone(item.atendido_at)

    def test_la_espera_del_ausente_si_cuenta(self):
        """Esperó de verdad hasta que lo llamaron; esa demora fue real."""
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(caso, autor=self.jefe)
        self.assertIsNotNone(caso.en_filas.first().llamado_at)

    def test_no_se_puede_dar_por_ausente_a_quien_no_se_llamo(self):
        caso = self._encolar("Ana")
        with self.assertRaises(motor.ErrorMotor):
            motor.marcar_ausente(caso, autor=self.jefe)

    # --- Vuelve a la cola --------------------------------------------------- #

    def test_devuelto_por_error_conserva_su_lugar(self):
        """La demora no fue suya: ya esperó una vez."""
        a, b, c = self._encolar("Ana"), self._encolar("Beto"), self._encolar("Caro")
        motor.llamar(a, box_id=self.box.id, autor=self.jefe)
        self.assertEqual(self._cola(), ["Beto", "Caro"])
        motor.devolver_a_la_cola(a, autor=self.jefe, motivo="lo llamé por error")
        self.assertEqual(self._cola(), ["Ana", "Beto", "Caro"])

    def test_el_ausente_que_reaparece_va_al_final(self):
        """Perdió el turno: adelantarlo sería castigar al que sí estaba."""
        a, b, c = self._encolar("Ana"), self._encolar("Beto"), self._encolar("Caro")
        motor.llamar(a, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(a, autor=self.jefe)
        motor.devolver_a_la_cola(a, autor=self.jefe)
        self.assertEqual(self._cola(), ["Beto", "Caro", "Ana"])

    def test_el_urgente_que_reaparece_sigue_yendo_primero(self):
        """
        Va al final del ORDEN, pero la urgencia manda sobre el lugar: un urgente
        que aparece tarde no espera detrás de los que no lo son. Perder el turno
        es una regla de convivencia; la prioridad clínica no se negocia.
        """
        self._encolar("Ana")
        self._encolar("Beto")
        urg = self._encolar("Caro")
        urg.en_filas.update(urgente=True)
        motor.llamar(urg, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(urg, autor=self.jefe)
        motor.devolver_a_la_cola(urg, autor=self.jefe)
        item = ItemFila.objects.get(caso=urg)
        self.assertEqual(item.orden, max(
            ItemFila.objects.filter(nodo=self.ate, atendido=False).values_list("orden", flat=True)
        ), "no quedó al final del orden")
        self.assertEqual(self._cola()[0], "Caro", "la urgencia dejó de mandar")

    def test_devolver_no_borra_la_espera_ya_acumulada(self):
        """
        Si `llamado_at` se reiniciara, el indicador de demora del servicio
        mejoraría cuanto PEOR se opere la cola: llamar y devolver borraría la
        espera. Se conserva a propósito.
        """
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        llamado = caso.en_filas.first().llamado_at
        motor.devolver_a_la_cola(caso, autor=self.jefe)
        self.assertEqual(caso.en_filas.first().llamado_at, llamado)

    def test_devolver_deja_al_caso_esperando_y_sin_dueno(self):
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        motor.devolver_a_la_cola(caso, autor=self.jefe)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.EN_ESPERA)
        self.assertIsNone(caso.asignado_a_id)
        self.assertIsNone(caso.en_filas.first().box_id)

    def test_no_se_puede_devolver_a_quien_nunca_se_llamo(self):
        caso = self._encolar("Ana")
        with self.assertRaises(motor.ErrorMotor):
            motor.devolver_a_la_cola(caso, autor=self.jefe)

    # --- Reordenar ---------------------------------------------------------- #

    def test_adelantar_a_alguien_que_empeoro_esperando(self):
        for n in ("Ana", "Beto", "Caro", "Dani"):
            self._encolar(n)
        item = ItemFila.objects.get(caso__ciudadano__nombre="Dani")
        motor.mover_en_fila(item, 1, autor=self.jefe)
        self.assertEqual(self._cola(), ["Ana", "Dani", "Beto", "Caro"])

    def test_reordenar_deja_la_cola_sin_posiciones_repetidas(self):
        for n in ("Ana", "Beto", "Caro"):
            self._encolar(n)
        motor.mover_en_fila(ItemFila.objects.get(caso__ciudadano__nombre="Caro"), 0, autor=self.jefe)
        ordenes = sorted(ItemFila.objects.filter(nodo=self.ate, atendido=False, box__isnull=True).values_list("orden", flat=True))
        self.assertEqual(ordenes, [0, 1, 2])

    def test_una_posicion_fuera_de_rango_no_rompe_la_cola(self):
        for n in ("Ana", "Beto"):
            self._encolar(n)
        motor.mover_en_fila(ItemFila.objects.get(caso__ciudadano__nombre="Ana"), 99, autor=self.jefe)
        self.assertEqual(self._cola(), ["Beto", "Ana"])

    def test_los_urgentes_siguen_yendo_primero(self):
        """Reordenar mueve dentro de la cola; no saltea la prioridad clínica."""
        for n in ("Ana", "Beto"):
            self._encolar(n)
        urg = self._encolar("Caro")
        urg.en_filas.update(urgente=True)
        motor.mover_en_fila(ItemFila.objects.get(caso__ciudadano__nombre="Ana"), 0, autor=self.jefe)
        self.assertEqual(self._cola()[0], "Caro")

    def test_dos_personas_no_comparten_lugar_cuando_alguien_sale_de_la_cola(self):
        """
        El orden se asignaba con `count()` de los que esperan: si alguien salía,
        el contador bajaba y el siguiente que llegaba repetía un número ya usado.
        """
        a, b, c = self._encolar("Ana"), self._encolar("Beto"), self._encolar("Caro")
        motor.llamar(a, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(a, autor=self.jefe)
        self._encolar("Dani")
        ordenes = list(ItemFila.objects.filter(nodo=self.ate, atendido=False).values_list("orden", flat=True))
        self.assertEqual(len(ordenes), len(set(ordenes)), f"lugares repetidos en la cola: {ordenes}")

    # --- Lo que ve la pantalla ---------------------------------------------- #

    def test_las_acciones_ofrecidas_siguen_el_estado_real(self):
        caso = self._encolar("Ana")
        self.assertEqual(motor._acciones_posibles(caso, self.ate), ["llamar"])
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        caso.refresh_from_db()
        self.assertEqual(motor._acciones_posibles(caso, self.ate), ["avanzar", "devolver", "ausente"])
        motor.marcar_ausente(caso, autor=self.jefe)
        caso.refresh_from_db()
        self.assertEqual(motor._acciones_posibles(caso, self.ate), ["devolver"])

    def test_queda_registrado_en_la_historia_del_caso(self):
        """Un turno que se mueve o alguien que se va sin atenderse tiene que
        poder reconstruirse: es la mitad de para qué existe la trazabilidad."""
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.jefe)
        motor.marcar_ausente(caso, autor=self.jefe)
        motor.devolver_a_la_cola(caso, autor=self.jefe)
        titulos = list(caso.eventos.values_list("titulo", flat=True))
        self.assertIn("No se presentó", titulos)
        self.assertIn("Vuelve a la cola (reapareció)", titulos)
