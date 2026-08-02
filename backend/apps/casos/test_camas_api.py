"""
Camas por HTTP: internar, pase, egreso y el tablero de ocupación.

El tablero es el número que alguien mira para decidir si acepta otro paciente.
Un porcentaje mal calculado ahí no se nota —siempre da algo verosímil— y lleva a
decisiones equivocadas, así que tiene más tests que el resto.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, EstadiaCama, Institucion, Subarea
from apps.registros.models import Ciudadano

from . import motor
from .models import Caso


class CamasAPITests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            "jefe@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.uti = Subarea.objects.create(area=self.area, nombre="UTI")
        self.sala = Subarea.objects.create(area=self.area, nombre="Clínica médica")

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.nodo_cama = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.CAMA, titulo="Asignar cama",
            config={"sector": self.sala.id},
        )
        evol = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Evolución")
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Alta")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.nodo_cama)
        Conexion.objects.create(version=self.ver, origen=self.nodo_cama, destino=evol)
        Conexion.objects.create(version=self.ver, origen=evol, destino=fin)

        self.c1 = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        self.c2 = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-B")
        self.u1 = Cama.objects.create(area=self.area, subarea=self.uti, nombre="UTI 1")

    def _internar(self, nombre="Ana"):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.user)
        caso.refresh_from_db()
        return caso

    # --- Internar ----------------------------------------------------------- #

    def test_ofrece_solo_las_camas_del_sector_del_paso(self):
        caso = self._internar()
        r = self.client.get(f"/api/casos/{caso.id}/cama/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({c["nombre"] for c in r.data["camas"]}, {"101-A", "101-B"})

    def test_internar_por_http(self):
        caso = self._internar()
        r = self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["cama"]["nombre"], "101-A")
        self.assertEqual(r.data["cama"]["sector"], "Clínica médica")

    def test_internar_en_una_cama_ocupada_lo_dice(self):
        a = self._internar("Ana")
        self.client.post(f"/api/casos/{a.id}/cama/", {"cama_id": self.c1.id})
        b = self._internar("Beto")
        r = self.client.post(f"/api/casos/{b.id}/cama/", {"cama_id": self.c1.id})
        self.assertEqual(r.status_code, 400)
        self.assertIn("no está libre", r.data["detail"])

    def test_el_detalle_dice_donde_esta_internado(self):
        caso = self._internar()
        self.assertIsNone(self.client.get(f"/api/casos/{caso.id}/").data["cama"])
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.assertEqual(self.client.get(f"/api/casos/{caso.id}/").data["cama"]["nombre"], "101-A")

    # --- Pase y egreso ------------------------------------------------------ #

    def test_pase_de_sector_por_http(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        r = self.client.post(f"/api/casos/{caso.id}/pase/",
                             {"cama_id": self.u1.id, "motivo": "descompensó"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["cama"]["sector"], "UTI")

    def test_egreso_libera_la_cama_sin_cerrar_el_caso(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        r = self.client.post(f"/api/casos/{caso.id}/egreso-cama/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIsNone(r.data["cama"])
        self.assertNotIn(r.data["estado"], ("cerrado", "cancelado"))

    def test_marcar_higienizada_la_devuelve_al_circuito(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.client.post(f"/api/casos/{caso.id}/egreso-cama/")
        r = self.client.post(f"/api/camas/{self.c1.id}/estado/", {"estado": "libre"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["disponible"])

    def test_no_se_puede_marcar_libre_una_cama_ocupada_por_http(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        r = self.client.post(f"/api/camas/{self.c1.id}/estado/", {"estado": "libre"})
        self.assertEqual(r.status_code, 400)

    def test_el_estado_no_se_puede_cambiar_por_patch(self):
        """
        Se mueve junto con la estadía del paciente. Por PATCH se podría marcar
        libre una cama ocupada y dejar a alguien internado en ningún lado.
        """
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.client.patch(f"/api/camas/{self.c1.id}/", {"estado": "libre"})
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.estado, Cama.Estado.OCUPADA)

    # --- Tablero ------------------------------------------------------------ #

    def test_el_tablero_cuenta_por_sector(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        r = self.client.get(f"/api/camas/tablero/?area={self.area.id}")
        self.assertEqual(r.status_code, 200)
        por_sector = {s["sector"]: s for s in r.data["sectores"]}
        self.assertEqual(por_sector["Clínica médica"]["ocupadas"], 1)
        self.assertEqual(por_sector["Clínica médica"]["libres"], 1)
        self.assertEqual(por_sector["Clínica médica"]["ocupacion"], 50)
        self.assertEqual(por_sector["UTI"]["ocupacion"], 0)

    def test_una_cama_fuera_de_servicio_no_infla_la_disponibilidad(self):
        """
        Si contara en el denominador, un sector con la mitad de las camas rotas
        parecería desahogado y alguien aceptaría un paciente que no entra.
        """
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.client.post(f"/api/camas/{self.c2.id}/estado/",
                         {"estado": "bloqueada", "motivo": "pérdida de agua"})
        s = {x["sector"]: x for x in self.client.get("/api/camas/tablero/").data["sectores"]}
        clinica = s["Clínica médica"]
        self.assertEqual(clinica["total"], 2)
        self.assertEqual(clinica["operativas"], 1)
        self.assertEqual(clinica["ocupacion"], 100, "1 de 1 cama en servicio está ocupada")

    def test_una_cama_en_higiene_no_cuenta_como_disponible_ni_como_ocupada(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        self.client.post(f"/api/casos/{caso.id}/egreso-cama/")
        s = {x["sector"]: x for x in self.client.get("/api/camas/tablero/").data["sectores"]}
        clinica = s["Clínica médica"]
        self.assertEqual(clinica["higiene"], 1)
        self.assertEqual(clinica["libres"], 1)
        self.assertEqual(clinica["ocupadas"], 0)

    def test_una_cama_dada_de_baja_no_existe_para_el_tablero(self):
        self.c2.activa = False
        self.c2.save()
        s = {x["sector"]: x for x in self.client.get("/api/camas/tablero/").data["sectores"]}
        self.assertEqual(s["Clínica médica"]["total"], 1)

    def test_los_totales_son_la_suma_de_los_sectores(self):
        caso = self._internar()
        self.client.post(f"/api/casos/{caso.id}/cama/", {"cama_id": self.c1.id})
        d = self.client.get("/api/camas/tablero/").data
        for k in ("total", "ocupadas", "libres", "higiene", "bloqueadas"):
            with self.subTest(k=k):
                self.assertEqual(d["totales"][k], sum(s[k] for s in d["sectores"]))

    def test_un_sector_sin_camas_en_servicio_no_divide_por_cero(self):
        for c in (self.c1, self.c2):
            self.client.post(f"/api/camas/{c.id}/estado/", {"estado": "bloqueada"})
        s = {x["sector"]: x for x in self.client.get("/api/camas/tablero/").data["sectores"]}
        self.assertEqual(s["Clínica médica"]["ocupacion"], 0)

    def test_el_tablero_respeta_el_filtro_de_area(self):
        otra = Area.objects.create(institucion=self.inst, nombre="Otra")
        Cama.objects.create(area=otra, nombre="X1")
        d = self.client.get(f"/api/camas/tablero/?area={self.area.id}").data
        self.assertNotIn("Otra", [s["sector"] for s in d["sectores"]])


class CamasPermisosTests(APITestCase):
    """Crear camas es configurar el hospital; higienizarlas es el día a día."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.cama = Cama.objects.create(area=self.area, nombre="101-A",
                                        estado=Cama.Estado.HIGIENE)
        self.usuarios = {}
        for rol in ("admin", "enfermeria", "configurador"):
            u = Usuario.objects.create_user(f"{rol}@test.local", "x")
            Membresia.objects.create(usuario=u, institucion=self.inst, rol=rol, activo=True)
            self.usuarios[rol] = u

    def _como(self, rol):
        self.client.force_authenticate(self.usuarios[rol])

    def test_enfermeria_marca_una_cama_higienizada(self):
        self._como("enfermeria")
        r = self.client.post(f"/api/camas/{self.cama.id}/estado/", {"estado": "libre"})
        self.assertEqual(r.status_code, 200, r.data)

    def test_enfermeria_no_da_de_alta_camas(self):
        """Eso es configurar el hospital, no operarlo."""
        self._como("enfermeria")
        r = self.client.post("/api/camas/", {"area": self.area.id, "nombre": "999"})
        self.assertEqual(r.status_code, 403)

    def test_el_admin_da_de_alta_camas(self):
        self._como("admin")
        r = self.client.post("/api/camas/", {"area": self.area.id, "nombre": "999"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_el_configurador_no_toca_camas(self):
        """Diseña flujos; la estructura física del hospital no es suya."""
        self._como("configurador")
        self.assertEqual(
            self.client.post("/api/camas/", {"area": self.area.id, "nombre": "999"}).status_code, 403
        )
        self.assertEqual(
            self.client.post(f"/api/camas/{self.cama.id}/estado/", {"estado": "libre"}).status_code, 403
        )
