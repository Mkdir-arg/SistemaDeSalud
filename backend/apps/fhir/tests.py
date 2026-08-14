"""
Fachada FHIR.

Lo que más se cuida acá son dos cosas que no se ven mirando una respuesta:
que leer por esta puerta quede en el registro de accesos igual que por la
pantalla —si no, sería un agujero prolijo a través de toda la Ley 26.529—, y
que el alcance por institución no dependa de lo que pida el cliente.
"""
import json

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, EstadiaCama, Institucion
from apps.registros.models import Ciudadano


class FhirTestCase(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central", cuit="30-1234-5", tipo="Hospital general")
        self.otra = Institucion.objects.create(nombre="Hospital de Villa Sur")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")

        self.user = Usuario.objects.create_user("med@test.local", "x", nombre="Ana", apellido="Ruiz")
        Membresia.objects.create(usuario=self.user, institucion=self.inst, rol="medico", activo=True)

        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Juan", apellido="Pérez", documento="30111222",
            fecha_nacimiento="1980-05-14", obra_social="OSDE", domicilio="Av. Siempreviva 742",
        )
        self.ajeno = Ciudadano.objects.create(
            institucion=self.otra, nombre="Elena", apellido="Acosta", documento="27418305",
        )

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia general")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.ver, ciudadano=self.paciente,
            area_actual=self.area, prioridad=Caso.Prioridad.URGENTE,
        )
        self.client.force_authenticate(self.user)

    def get(self, url):
        r = self.client.get(url)
        return r, (json.loads(r.content) if r.content else {})


class MetadataTests(FhirTestCase):
    def test_el_capability_statement_se_sirve_sin_credenciales(self):
        """
        Es lo primero que pide cualquier cliente FHIR. Que se pueda mirar antes
        de tramitar credenciales es la diferencia entre una prueba de media hora
        y una reunión.
        """
        self.client.force_authenticate(None)
        r, d = self.get("/fhir/metadata")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["resourceType"], "CapabilityStatement")
        self.assertEqual(d["fhirVersion"], "4.0.1")

    def test_declara_exactamente_los_recursos_que_existen(self):
        """
        Anunciar recursos que devuelven cáscaras vacías hace que el otro lado
        escriba código contra algo que no existe, y eso aparece en producción,
        no en la prueba.
        """
        _, d = self.get("/fhir/metadata")
        declarados = {r["type"] for r in d["rest"][0]["resource"]}
        self.assertEqual(declarados, {"Patient", "Encounter", "Organization"})

    def test_no_declara_escritura_en_ningun_recurso(self):
        _, d = self.get("/fhir/metadata")
        for recurso in d["rest"][0]["resource"]:
            codigos = {i["code"] for i in recurso["interaction"]}
            with self.subTest(recurso=recurso["type"]):
                self.assertFalse(codigos & {"create", "update", "delete", "patch"})

    def test_responde_con_el_content_type_de_fhir(self):
        """Un cliente estricto que recibe `application/json` puede rechazarlo."""
        r, _ = self.get("/fhir/metadata")
        self.assertIn("application/fhir+json", r["Content-Type"])


class PatientTests(FhirTestCase):
    def test_devuelve_el_paciente_como_patient(self):
        r, d = self.get(f"/fhir/Patient/{self.paciente.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["resourceType"], "Patient")
        self.assertEqual(d["name"][0]["family"], "Pérez")
        self.assertEqual(d["birthDate"], "1980-05-14")

    def test_el_documento_va_con_el_sistema_que_le_corresponde(self):
        """Sin `system`, el otro lado no sabe en qué padrón está ese número."""
        _, d = self.get(f"/fhir/Patient/{self.paciente.id}")
        dni = [i for i in d["identifier"] if i["value"] == "30111222"]
        self.assertTrue(dni)
        self.assertIn("renaper", dni[0]["system"])

    def test_un_paciente_sin_documento_igual_se_puede_referenciar(self):
        """Si no, su propio Encounter apuntaría a un Patient sin identificador."""
        sin_dni = Ciudadano.objects.create(institucion=self.inst, nombre="NN")
        _, d = self.get(f"/fhir/Patient/{sin_dni.id}")
        self.assertTrue(d["identifier"])

    def test_no_inventa_el_genero(self):
        """
        Cauce no lo guarda. Mandar «unknown» afirmaría que se preguntó y no se
        sabe, cuando nunca se preguntó.
        """
        _, d = self.get(f"/fhir/Patient/{self.paciente.id}")
        self.assertNotIn("gender", d)

    def test_la_obra_social_no_se_disfraza_de_dato_codificado(self):
        """
        Es texto escrito a mano. Bajo un `system` de cobertura parecería
        codificado y del otro lado alguien lo procesaría como si lo estuviera.
        """
        _, d = self.get(f"/fhir/Patient/{self.paciente.id}")
        self.assertEqual(d["extension"][0]["valueString"], "OSDE")
        self.assertNotIn("Coverage", json.dumps(d))

    def test_se_busca_por_documento_con_el_formato_de_fhir(self):
        _, d = self.get("/fhir/Patient?identifier=http://www.renaper.gob.ar/dni|30111222")
        self.assertEqual(d["resourceType"], "Bundle")
        self.assertEqual(d["total"], 1)
        self.assertEqual(d["entry"][0]["resource"]["name"][0]["family"], "Pérez")

    def test_tambien_se_busca_con_el_documento_pelado(self):
        """Exigir el sistema haría fallar consultas correctas por una formalidad."""
        _, d = self.get("/fhir/Patient?identifier=30111222")
        self.assertEqual(d["total"], 1)

    def test_una_busqueda_sin_resultados_devuelve_un_bundle_vacio(self):
        """«Ninguno» es un resultado válido; un 404 acá rompe clientes sanos."""
        r, d = self.get("/fhir/Patient?identifier=00000000")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["resourceType"], "Bundle")
        self.assertEqual(d["total"], 0)
        self.assertEqual(d["entry"], [])

    def test_un_paciente_de_otra_institucion_no_aparece(self):
        _, d = self.get("/fhir/Patient?family=Acosta")
        self.assertEqual(d["total"], 0)

    def test_pedir_un_paciente_de_otra_institucion_da_404_y_no_403(self):
        """
        «Existe pero no podés verlo» confirma que esa persona está registrada,
        que ya es información sobre ella.
        """
        r, _ = self.get(f"/fhir/Patient/{self.ajeno.id}")
        self.assertEqual(r.status_code, 404)

    def test_sin_credenciales_no_se_leen_pacientes(self):
        self.client.force_authenticate(None)
        r, _ = self.get(f"/fhir/Patient/{self.paciente.id}")
        self.assertIn(r.status_code, (401, 403))


class EncounterTests(FhirTestCase):
    def test_el_caso_se_expone_como_encounter(self):
        r, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(d["resourceType"], "Encounter")
        self.assertEqual(d["subject"]["reference"], f"Patient/{self.paciente.id}")
        self.assertEqual(d["serviceType"]["text"], "Guardia general")

    def test_un_caso_derivado_sigue_abierto(self):
        """
        Para el paciente el episodio no terminó, sólo cambió de área. Marcarlo
        `finished` haría que el otro lado cerrara el registro de alguien que
        todavía está siendo atendido.
        """
        Caso.objects.filter(pk=self.caso.pk).update(estado=Caso.Estado.DERIVADO)
        _, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertEqual(d["status"], "in-progress")

    def test_un_caso_abierto_no_declara_fecha_de_fin(self):
        """Un `end` puesto por las dudas haría creer cerrado un caso abierto."""
        _, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertNotIn("end", d["period"])

    def test_un_caso_cerrado_sí_la_declara(self):
        Caso.objects.filter(pk=self.caso.pk).update(estado=Caso.Estado.CERRADO)
        _, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertEqual(d["status"], "finished")
        self.assertTrue(d["period"]["end"])

    def test_la_prioridad_usa_la_tabla_estandar(self):
        """Es de lo poco que un sistema externo puede accionar sin conocer Cauce."""
        _, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertEqual(d["priority"]["coding"][0]["code"], "EM")

    def test_un_caso_con_cama_se_marca_como_internacion(self):
        cama = Cama.objects.create(area=self.area, nombre="C-1")
        EstadiaCama.objects.create(cama=cama, caso=self.caso, desde="2026-08-01T10:00:00Z")
        _, d = self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertEqual(d["class"]["code"], "IMP")

    def test_se_buscan_los_episodios_de_un_paciente(self):
        _, d = self.get(f"/fhir/Encounter?patient={self.paciente.id}")
        self.assertEqual(d["total"], 1)

    def test_tambien_con_la_referencia_completa(self):
        _, d = self.get(f"/fhir/Encounter?patient=Patient/{self.paciente.id}")
        self.assertEqual(d["total"], 1)

    def test_el_filtro_por_estado_traduce_desde_fhir(self):
        """
        Varios estados de Cauce caen en `in-progress`: filtrar por el texto
        crudo no encontraría nada aunque haya casos que corresponden.
        """
        Caso.objects.filter(pk=self.caso.pk).update(estado=Caso.Estado.EN_ESPERA)
        _, d = self.get("/fhir/Encounter?status=in-progress")
        self.assertEqual(d["total"], 1)


class AlcanceYAuditoriaTests(FhirTestCase):
    """
    Si la fachada FHIR no auditara, sería un agujero prolijo a través de todo lo
    que se construyó para la Ley 26.529: bastaría con pedir los datos por la
    otra puerta.
    """

    def test_leer_un_patient_queda_registrado_a_nombre_del_paciente(self):
        self.get(f"/fhir/Patient/{self.paciente.id}")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.ciudadano_id, self.paciente.id)
        self.assertEqual(a.usuario_id, self.user.id)
        self.assertEqual(a.tipo, AccesoClinico.Tipo.DETALLE)

    def test_buscar_por_documento_se_anota_a_nombre_de_quien_apareció(self):
        """
        Si no, consultar por documento sería la forma de mirar a alguien sin
        dejar rastro suyo.
        """
        self.get("/fhir/Patient?identifier=30111222")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.ciudadano_id, self.paciente.id)
        self.assertEqual(a.tipo, AccesoClinico.Tipo.DETALLE)

    def test_un_listado_abierto_se_anota_como_listado_con_la_cantidad(self):
        self.get("/fhir/Patient")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.tipo, AccesoClinico.Tipo.LISTADO)
        self.assertEqual(a.resultados, 1)
        self.assertIsNone(a.ciudadano_id)

    def test_leer_un_encounter_tambien_queda_registrado(self):
        self.get(f"/fhir/Encounter/{self.caso.id}")
        self.assertTrue(AccesoClinico.objects.filter(ciudadano=self.paciente).exists())

    def test_el_registro_dice_que_vino_por_fhir(self):
        """Sin eso, no se puede responder «¿esto salió por la integración?»."""
        self.get(f"/fhir/Patient/{self.paciente.id}")
        self.assertIn("fhir", AccesoClinico.objects.get().detalle)

    def test_un_404_por_alcance_no_deja_rastro_a_nombre_de_nadie(self):
        """Anotarlo diría que se accedió a datos que no se entregaron."""
        self.get(f"/fhir/Patient/{self.ajeno.id}")
        self.assertFalse(AccesoClinico.objects.filter(ciudadano=self.ajeno).exists())

    def test_mirar_una_organization_no_ensucia_el_registro(self):
        """Una institución no es dato clínico: taparía las lecturas que importan."""
        self.get(f"/fhir/Organization/{self.inst.id}")
        self.assertEqual(AccesoClinico.objects.count(), 0)


class SoloLecturaTests(FhirTestCase):
    """
    Escribir por acá metería datos clínicos salteándose el motor: sin flujo, sin
    línea de tiempo y sin el sellado de integridad de la historia.
    """

    def test_no_se_puede_crear_un_patient(self):
        r = self.client.post("/fhir/Patient", {"resourceType": "Patient"}, format="json")
        self.assertEqual(r.status_code, 405)

    def test_no_se_puede_modificar_ni_borrar_un_encounter(self):
        self.assertEqual(self.client.put(f"/fhir/Encounter/{self.caso.id}").status_code, 405)
        self.assertEqual(self.client.delete(f"/fhir/Encounter/{self.caso.id}").status_code, 405)

    def test_el_rechazo_viene_en_formato_fhir_y_explica_el_camino(self):
        """
        Un 405 pelado manda a alguien a buscar el endpoint correcto; lo que
        necesita saber es que no existe y por qué.
        """
        r = self.client.post("/fhir/Observation", {}, format="json")
        d = json.loads(r.content)
        self.assertEqual(d["resourceType"], "OperationOutcome")
        self.assertIn("integración", d["issue"][0]["diagnostics"])

    def test_un_recurso_no_implementado_dice_cuales_si_estan(self):
        r, d = self.get("/fhir/Observation")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(d["resourceType"], "OperationOutcome")
        self.assertIn("Patient", d["issue"][0]["diagnostics"])
