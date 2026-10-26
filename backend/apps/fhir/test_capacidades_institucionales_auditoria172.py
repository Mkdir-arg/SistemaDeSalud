"""AUD-046: una capacidad en A no habilita datos de la membresía B."""
from urllib.parse import urlsplit

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso
from apps.flujos.models import Flujo, VersionFlujo
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano


class CapacidadesInstitucionalesFHIRTests(APITestCase):
    def setUp(self):
        self.a = Institucion.objects.create(nombre="Institución A")
        self.b = Institucion.objects.create(nombre="Institución B")
        self.usuario = Usuario.objects.create_user("medico-mixto@test.local", "x")
        self.medico_a = Membresia.objects.create(
            usuario=self.usuario, institucion=self.a, rol=Membresia.Rol.MEDICO,
        )
        self.configurador_b = Membresia.objects.create(
            usuario=self.usuario, institucion=self.b, rol=Membresia.Rol.CONFIGURADOR,
        )
        self.pacientes = {}
        self.casos = {}
        for numero, institucion in enumerate((self.a, self.b), start=1):
            flujo = Flujo.objects.create(institucion=institucion, titulo="Circuito sintético")
            version = VersionFlujo.objects.create(flujo=flujo, numero=1)
            pacientes, casos = [], []
            for indice in range(2):
                paciente = Ciudadano.objects.create(
                    institucion=institucion, nombre=f"Paciente {indice}",
                    apellido=f"Institución {numero}", documento=f"90046{numero}{indice}",
                )
                pacientes.append(paciente)
                casos.append(Caso.objects.create(
                    institucion=institucion, version=version, ciudadano=paciente,
                ))
            self.pacientes[institucion.pk] = pacientes
            self.casos[institucion.pk] = casos
        self.client.force_authenticate(self.usuario)

    def recursos(self, institucion):
        return (
            ("Patient", self.pacientes[institucion.pk]),
            ("Encounter", self.casos[institucion.pk]),
        )

    def assert_ambito(self, permitida, denegada):
        for (tipo, propios), (_, ajenos) in zip(self.recursos(permitida), self.recursos(denegada)):
            with self.subTest(tipo=tipo, permitida=permitida.pk):
                for propio in propios:
                    respuesta = self.client.get(f"/fhir/{tipo}/{propio.pk}")
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertEqual(respuesta.json()["id"], str(propio.pk))
                denegado = self.client.get(f"/fhir/{tipo}/{ajenos[0].pk}")
                inexistente = self.client.get(f"/fhir/{tipo}/999999999")
                self.assertEqual(denegado.status_code, 404)
                self.assertEqual(denegado.json(), inexistente.json())

                url = f"/fhir/{tipo}?_count=1"
                recibidos = []
                paginas = 0
                while url:
                    respuesta = self.client.get(url)
                    self.assertEqual(respuesta.status_code, 200)
                    bundle = respuesta.json()
                    self.assertEqual(bundle["total"], len(propios))
                    recibidos.extend(entrada["resource"]["id"] for entrada in bundle["entry"])
                    paginas += 1
                    self.assertLessEqual(paginas, len(propios))
                    siguiente = next((enlace["url"] for enlace in bundle["link"]
                                      if enlace["relation"] == "next"), None)
                    partes = urlsplit(siguiente) if siguiente else None
                    url = f"{partes.path}?{partes.query}" if partes else None
                self.assertCountEqual(recibidos, [str(objeto.pk) for objeto in propios])

    def test_medico_a_configurador_b_solo_lee_a_incluyendo_paginacion(self):
        self.assert_ambito(self.a, self.b)

    def test_roles_invertidos_solo_leen_b(self):
        self.medico_a.rol = Membresia.Rol.CONFIGURADOR
        self.medico_a.save(update_fields=["rol"])
        self.configurador_b.rol = Membresia.Rol.MEDICO
        self.configurador_b.save(update_fields=["rol"])
        self.assert_ambito(self.b, self.a)

    def test_membresia_clinica_inactiva_no_amplia_el_ambito(self):
        self.medico_a.activo = False
        self.medico_a.save(update_fields=["activo"])
        self.configurador_b.rol = Membresia.Rol.MEDICO
        self.configurador_b.save(update_fields=["rol"])
        self.assert_ambito(self.b, self.a)

    def test_membresia_global_no_convierte_configuracion_b_en_acceso_clinico(self):
        Membresia.objects.create(usuario=self.usuario, rol=Membresia.Rol.PLATAFORMA)
        self.assert_ambito(self.a, self.b)

    def test_capacidad_agregada_y_revocada_se_refleja_en_siguiente_solicitud(self):
        clinica_b = Membresia.objects.create(
            usuario=self.usuario, institucion=self.b, rol=Membresia.Rol.MEDICO,
        )
        for tipo in ("Patient", "Encounter"):
            self.assertEqual(self.client.get(f"/fhir/{tipo}").json()["total"], 4)
        clinica_b.activo = False
        clinica_b.save(update_fields=["activo"])
        self.assert_ambito(self.a, self.b)

    def test_filtros_por_identidad_no_devuelven_objetos_sin_capacidad(self):
        paciente = self.pacientes[self.b.pk][0]
        for url in (
            f"/fhir/Patient?identifier={paciente.documento}",
            f"/fhir/Encounter?patient=Patient/{paciente.pk}",
        ):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.json()["total"], 0)
                self.assertEqual(respuesta.json()["entry"], [])
                self.assertFalse(any(enlace["relation"] == "next" for enlace in respuesta.json()["link"]))

    def test_sin_capacidad_en_ninguna_institucion_se_conserva_403(self):
        self.medico_a.rol = Membresia.Rol.CONFIGURADOR
        self.medico_a.save(update_fields=["rol"])
        for tipo, objetos in self.recursos(self.a):
            for url in (f"/fhir/{tipo}", f"/fhir/{tipo}/{objetos[0].pk}"):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_superusuario_conserva_lectura_global(self):
        root = Usuario.objects.create_superuser("root-fhir@test.local", "x")
        self.client.force_authenticate(root)
        for tipo in ("Patient", "Encounter"):
            respuesta = self.client.get(f"/fhir/{tipo}")
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["total"], 4)
        for tipo, objetos in self.recursos(self.b):
            self.assertEqual(self.client.get(f"/fhir/{tipo}/{objetos[0].pk}").status_code, 200)
