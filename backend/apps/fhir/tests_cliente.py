"""
Consulta a un padrón FHIR externo desde un paso del flujo.

Acá lo que se cuida es que el padrón NO pueda romper nada: ni pisar datos que
alguien verificó en persona, ni trabar a un paciente porque un servidor ajeno no
contesta, ni traer a la persona equivocada cuando hay dudas.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso, EventoCaso
from apps.fhir import cliente
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano

PADRON = "https://padron.test.gob.ar/fhir"


def _patient(**extra):
    base = {
        "resourceType": "Patient",
        "id": "9",
        "name": [{"use": "official", "family": "Pérez", "given": ["Juan", "Carlos"]}],
        "birthDate": "1980-05-14",
        "address": [{"text": "Av. Siempreviva 742"}],
    }
    base.update(extra)
    return base


def _bundle(*pacientes):
    return {
        "resourceType": "Bundle", "type": "searchset", "total": len(pacientes),
        "entry": [{"resource": p} for p in pacientes],
    }


class TraduccionTests(TestCase):
    def test_traduce_nombre_apellido_y_fecha(self):
        d = cliente.a_ciudadano(_patient())
        self.assertEqual(d["nombre"], "Juan Carlos")
        self.assertEqual(d["apellido"], "Pérez")
        self.assertEqual(d["fecha_nacimiento"], "1980-05-14")

    def test_prefiere_el_nombre_oficial(self):
        p = _patient(name=[
            {"use": "nickname", "family": "X", "given": ["Juancito"]},
            {"use": "official", "family": "Pérez", "given": ["Juan"]},
        ])
        self.assertEqual(cliente.a_ciudadano(p)["apellido"], "Pérez")

    def test_un_nombre_suelto_no_se_parte_en_dos(self):
        """
        Partirlo es adivinar dónde termina el nombre y empieza el apellido, y un
        apellido mal cortado se propaga a la historia clínica.
        """
        d = cliente.a_ciudadano(_patient(name=[{"text": "Juan Carlos Pérez"}]))
        self.assertEqual(d["nombre"], "Juan Carlos Pérez")
        self.assertNotIn("apellido", d)

    def test_arma_el_domicilio_cuando_viene_en_partes(self):
        p = _patient(address=[{"line": ["Calle Falsa 123"], "city": "Rosario"}])
        self.assertEqual(cliente.a_ciudadano(p)["domicilio"], "Calle Falsa 123, Rosario")

    def test_una_respuesta_que_no_es_un_patient_no_rompe(self):
        self.assertEqual(cliente.a_ciudadano({"resourceType": "OperationOutcome"}), {})
        self.assertEqual(cliente.a_ciudadano(None), {})

    def test_un_given_que_viene_como_texto_no_se_guarda_letra_por_letra(self):
        """
        Hay padrones que mandan `"given": "Juan"` en vez de `["Juan"]`. Iterarlo
        recorre caracteres y el paciente queda anotado «J u a n» en su historia
        clínica; como `completar` nunca pisa un campo con contenido, esa basura
        queda blindada y la próxima consulta ya no la toca.
        """
        d = cliente.a_ciudadano(_patient(name=[
            {"use": "official", "family": "Pérez", "given": "Juan"},
        ]))
        self.assertEqual(d["nombre"], "Juan")

    def test_un_family_que_viene_como_lista_no_rompe_el_caso(self):
        """
        Sin normalizar el tipo es un AttributeError que no atrapa nadie: sube
        hasta el `@transaction.atomic` del motor y el ingreso contesta 500 con el
        caso sin nodo y sin un solo evento que lo explique.
        """
        d = cliente.a_ciudadano(_patient(name=[
            {"use": "official", "family": ["Pérez"], "given": ["Juan"]},
        ]))
        self.assertEqual(d["apellido"], "Pérez")

    def test_una_fecha_parcial_del_padron_no_se_guarda_como_fecha(self):
        """
        `1985` y `1985-03` son birthDate válidas en FHIR R4 y frecuentes en
        padrones; el DateField de Cauce no las admite. Copiarlas tal cual levanta
        ValidationError dentro de la transacción del motor y el ingreso se cae
        entero. Una fecha que Cauce no puede representar es mejor vacía.
        """
        for parcial in ("1985", "1985-03", "no sé", "1985-02-30"):
            with self.subTest(parcial=parcial):
                self.assertNotIn("fecha_nacimiento", cliente.a_ciudadano(_patient(birthDate=parcial)))

    def test_un_nombre_larguisimo_se_recorta_al_largo_de_la_columna(self):
        """
        Un `family` de 300 caracteres da DataError y ABORTA la transacción de
        Postgres: se lleva puesto el ingreso, no sólo el apellido.
        """
        d = cliente.a_ciudadano(_patient(name=[{"use": "official", "family": "X" * 300}]))
        self.assertEqual(len(d["apellido"]), 120)


def _responder(datos):
    """Simula al servidor externo. No se sale a la red en un test."""
    cuerpo = __import__("json").dumps(datos).encode()

    class Respuesta:
        def read(self, _n=None): return cuerpo
        def __enter__(self): return self
        def __exit__(self, *a): return False

    return patch("apps.fhir.cliente.urlopen", return_value=Respuesta())


class BusquedaTests(TestCase):
    def _responder(self, datos):
        return _responder(datos)

    def test_encuentra_a_la_persona(self):
        with self._responder(_bundle(_patient())):
            p = cliente.buscar_paciente(PADRON, "30111222")
        self.assertEqual(p["name"][0]["family"], "Pérez")

    def test_acepta_el_recurso_pelado_ademas_del_bundle(self):
        """
        Algunos servidores contestan el Patient directo cuando hubo un solo
        resultado. Rechazarlo sería descartar una respuesta correcta por forma.
        """
        with self._responder(_patient()):
            self.assertIsNotNone(cliente.buscar_paciente(PADRON, "30111222"))

    def test_dos_personas_con_el_mismo_documento_no_devuelve_ninguna(self):
        """
        Elegir la primera completaría la historia de alguien con los datos de
        otro. Cargarlo a mano cuesta un minuto; descubrir dentro de un año que
        dos pacientes se mezclaron no se arregla.
        """
        with self._responder(_bundle(_patient(), _patient(id="10"))):
            self.assertIsNone(cliente.buscar_paciente(PADRON, "30111222"))

    def test_sin_resultados_devuelve_nada(self):
        with self._responder(_bundle()):
            self.assertIsNone(cliente.buscar_paciente(PADRON, "30111222"))

    def test_sin_documento_ni_se_consulta(self):
        with patch("apps.fhir.cliente.urlopen") as u:
            self.assertIsNone(cliente.buscar_paciente(PADRON, ""))
            u.assert_not_called()

    def test_si_el_padron_no_responde_no_explota(self):
        with patch("apps.fhir.cliente.urlopen", side_effect=TimeoutError()):
            self.assertIsNone(cliente.buscar_paciente(PADRON, "30111222"))

    def test_una_respuesta_que_no_es_json_no_explota(self):
        class Basura:
            def read(self, _n=None): return b"<html>error</html>"
            def __enter__(self): return self
            def __exit__(self, *a): return False

        with patch("apps.fhir.cliente.urlopen", return_value=Basura()):
            self.assertIsNone(cliente.buscar_paciente(PADRON, "30111222"))

    def test_manda_el_documento_con_el_sistema_cuando_se_configura(self):
        with patch("apps.fhir.cliente.urlopen", side_effect=TimeoutError()) as u:
            cliente.buscar_paciente(PADRON, "30111222", sistema="urn:dni")
        self.assertIn("urn:dni|30111222", u.call_args[0][0].full_url)

    def test_un_documento_con_espacios_no_tumba_el_ingreso(self):
        """
        «30 111 222» es lo que alguien tipea en un mostrador. Sin codificar,
        `http.client` levanta InvalidURL, que hereda de HTTPException y NO de
        OSError: se escapaba del except y subía hasta la transacción del motor,
        dejando el caso sin nodo, sin eventos y con un 500 en el ingreso.
        """
        # Puerto cerrado: el pedido sale de verdad y falla en la conexión, que es
        # lo que prueba que la URL quedó bien armada.
        self.assertIsNone(cliente.buscar_paciente("http://127.0.0.1:1/fhir", "30 111 222", timeout=1))

    def test_un_numeral_en_el_documento_no_consulta_por_otra_persona(self):
        """
        urllib trata el `#` como fragmento y lo descarta: `12345678#x` se
        consultaba como `12345678`, o sea por alguien que no es quien se pidió.
        """
        with patch("apps.fhir.cliente.urlopen", side_effect=TimeoutError()) as u:
            cliente.buscar_paciente(PADRON, "12345678#x")
        pedido = u.call_args[0][0]
        self.assertNotIn("#", pedido.selector)
        self.assertIn("%23x", pedido.selector)


class MotivoTests(TestCase):
    """
    Por qué falló el padrón, no sólo que falló.

    Un único texto para las cuatro fallas afirma dos cosas que casi siempre son
    mentira: que el padrón contestó y que el problema es el documento de esta
    persona. Si el padrón provincial se cae un martes, la Trazabilidad de los 80
    ingresos de esa mañana dice, uno por uno, que el paciente estaba mal
    identificado, y después nadie puede reconstruir que fue una caída.
    """

    def _motivo(self, **kw):
        return cliente.buscar_paciente_con_motivo(PADRON, "30111222", **kw)[1]

    def test_un_padron_caido_no_se_confunde_con_un_documento_que_no_esta(self):
        from urllib.error import HTTPError

        casos = {
            "sin_conexion": TimeoutError(),
            "no_autorizado": HTTPError(PADRON, 401, "no", {}, None),
        }
        for esperado, error in casos.items():
            with self.subTest(esperado=esperado):
                with patch("apps.fhir.cliente.urlopen", side_effect=error):
                    self.assertEqual(self._motivo(), esperado)

    def test_cero_resultados_y_mas_de_uno_son_motivos_distintos(self):
        """
        Sólo «más de uno» justifica que alguien mire el DNI del paciente; las
        otras son para sistemas.
        """
        with _responder(_bundle()):
            self.assertEqual(self._motivo(), "sin_resultados")
        with _responder(_bundle(_patient(), _patient(id="10"))):
            self.assertEqual(self._motivo(), "ambiguo")

    def test_sin_documento_el_motivo_lo_dice_y_no_se_consulta(self):
        with patch("apps.fhir.cliente.urlopen") as u:
            _, motivo = cliente.buscar_paciente_con_motivo(PADRON, "")
        u.assert_not_called()
        self.assertEqual(motivo, "sin_documento")

    def test_cuando_encuentra_a_la_persona_no_hay_motivo(self):
        with _responder(_bundle(_patient())):
            patient, motivo = cliente.buscar_paciente_con_motivo(PADRON, "30111222")
        self.assertIsNotNone(patient)
        self.assertIsNone(motivo)

    def test_cada_motivo_tiene_un_texto_para_mostrar(self):
        """
        Sin texto, el motivo muere en el log del servidor, que es donde no llega
        nadie que atienda pacientes.
        """
        posibles = {
            "sin_documento", "sin_conexion", "no_autorizado",
            "respuesta_invalida", "sin_resultados", "ambiguo",
        }
        self.assertEqual(set(cliente.MOTIVOS), posibles)
        self.assertTrue(all(cliente.MOTIVOS.values()))


class CompletarTests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")

    def _ciudadano(self, **campos):
        return Ciudadano.objects.create(institucion=self.inst, documento="30111222", **campos)

    def test_completa_los_campos_vacios(self):
        c = self._ciudadano(nombre="")
        completados = cliente.completar(c, _patient())
        c.refresh_from_db()
        self.assertEqual(c.apellido, "Pérez")
        self.assertEqual(str(c.fecha_nacimiento), "1980-05-14")
        self.assertIn("apellido", completados)

    def test_no_pisa_lo_que_alguien_cargo(self):
        """
        Lo que una persona dijo en el mostrador vale más que un padrón con
        domicilios de hace quince años.
        """
        c = self._ciudadano(nombre="Juana", apellido="Gómez")
        cliente.completar(c, _patient())
        c.refresh_from_db()
        self.assertEqual(c.apellido, "Gómez")

    def test_completa_solo_lo_que_falta(self):
        c = self._ciudadano(nombre="Juan", apellido="")
        completados = cliente.completar(c, _patient())
        c.refresh_from_db()
        self.assertEqual(c.nombre, "Juan")
        self.assertEqual(c.apellido, "Pérez")
        self.assertIn("apellido", completados)
        self.assertNotIn("nombre", completados)

    def test_nunca_toca_el_documento(self):
        """Es lo que se usó para buscar: pisarlo con el resultado es circular."""
        c = self._ciudadano(nombre="")
        cliente.completar(c, _patient(identifier=[{"value": "99999999"}]))
        c.refresh_from_db()
        self.assertEqual(c.documento, "30111222")

    def test_si_no_falta_nada_no_escribe(self):
        c = self._ciudadano(nombre="Juan", apellido="Pérez", domicilio="X", fecha_nacimiento="1980-05-14")
        self.assertEqual(cliente.completar(c, _patient()), [])


@override_settings(INTEGRACIONES_PERMITIDAS=["padron.test.gob.ar"])
class DesdeElFlujoTests(TestCase):
    """El paso del flujo que consulta el padrón."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.med = Usuario.objects.create_user("med@test.local", "x", nombre="Ana")
        m = Membresia.objects.create(
            usuario=self.med, institucion=self.inst, rol="medico", activo=True
        )
        m.areas.set([self.area])
        LegajoProfesional.objects.create(usuario=self.med, matricula="MP 1")

        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="", documento="30111222"
        )
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.paso = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.INTEGRACION, titulo="Consulta al padrón",
            config={"fhir": "Patient", "url": PADRON},
        )
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.paso)
        Conexion.objects.create(version=self.ver, origen=self.paso, destino=fin)

        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.ver, ciudadano=self.paciente,
            area_actual=self.area,
        )

    def _correr(self, resultado=None, error=None):
        objetivo = "apps.fhir.cliente.buscar_paciente"
        kw = {"side_effect": error} if error else {"return_value": resultado}
        with patch(objetivo, **kw):
            motor.iniciar(self.caso, autor=self.med)
        self.caso.refresh_from_db()
        self.paciente.refresh_from_db()

    def _eventos(self):
        return list(EventoCaso.objects.filter(caso=self.caso).values_list("titulo", "detalle"))

    def test_el_paso_completa_al_paciente(self):
        self._correr(resultado=_patient())
        self.assertEqual(self.paciente.apellido, "Pérez")

    def test_queda_en_la_linea_de_tiempo_qué_se_completó(self):
        """Un dato que aparece solo sin decir de dónde vino no se puede auditar."""
        self._correr(resultado=_patient())
        detalles = " ".join(d for _, d in self._eventos())
        self.assertIn("se completó", detalles)
        self.assertIn("apellido", detalles)

    def test_si_el_padron_no_encuentra_a_nadie_el_caso_sigue(self):
        """
        Un padrón que no contesta no puede dejar a un paciente trabado en el
        circuito. Se anota y se sigue.
        """
        self._correr(resultado=None)
        self.assertNotEqual(self.caso.nodo_actual_id, self.paso.id)
        self.assertTrue(any("fallida" in t.lower() for t, _ in self._eventos()))

    def test_un_paciente_sin_documento_se_anota_y_no_traba(self):
        Ciudadano.objects.filter(pk=self.paciente.pk).update(documento="")
        # El caso trae al paciente cacheado desde el setUp: sin recargarlo, el
        # test corre contra el documento viejo y no prueba nada.
        self.caso = Caso.objects.get(pk=self.caso.pk)
        self._correr(resultado=_patient())
        detalles = " ".join(d for _, d in self._eventos())
        self.assertIn("documento", detalles)

    def test_un_destino_fuera_de_la_lista_blanca_no_se_consulta(self):
        """
        Misma restricción que el modo genérico: sin esto, quien diseña un flujo
        podría hacer que el servidor consulte un servicio interno.
        """
        Nodo.objects.filter(pk=self.paso.pk).update(
            config={"fhir": "Patient", "url": "https://interno.local/fhir"}
        )
        with patch("apps.fhir.cliente.buscar_paciente") as buscar:
            motor.iniciar(self.caso, autor=self.med)
        buscar.assert_not_called()
        self.assertTrue(any("habilitado" in d for _, d in self._eventos()))
