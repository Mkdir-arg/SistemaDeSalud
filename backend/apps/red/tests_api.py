"""
Traslados por HTTP.

Lo que más se cuida acá es la frontera: que cada lado pueda hacer sólo lo suyo
—el origen pide, el destino responde— y que un tercero no vea nada.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor as motor_casos
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, Institucion, Subarea
from apps.registros.models import Ciudadano

from .models import Red, Traslado


class TrasladosAPITests(APITestCase):
    def setUp(self):
        self.red = Red.objects.create(nombre="Región VI")
        self.hosp = Institucion.objects.create(nombre="Hospital de Lomas")
        self.centro = Institucion.objects.create(nombre="Hospital Interzonal")
        self.red.instituciones.set([self.hosp, self.centro])

        self.guardia = Area.objects.create(institucion=self.hosp, nombre="Guardia")
        self.uti = Area.objects.create(institucion=self.centro, nombre="UTI")

        self.med = self._usuario("med@lomas.gob.ar", self.hosp, "medico")
        self.jefe = self._usuario("jefe@inter.gob.ar", self.centro, "jefe_area")
        self.ajeno = self._usuario(
            "otro@tercero.gob.ar", Institucion.objects.create(nombre="Tercero"), "medico"
        )

        self.ver_uti = self._flujo(self.centro, self.uti, "Ingreso a UTI")
        self.caso = self._caso()

    def _usuario(self, email, inst, rol):
        u = Usuario.objects.create_user(email, "x")
        Membresia.objects.create(usuario=u, institucion=inst, rol=rol, activo=True)
        return u

    def _flujo(self, inst, area, titulo):
        f = Flujo.objects.create(institucion=inst, area=area, titulo=titulo)
        v = VersionFlujo.objects.create(flujo=f, numero=1, estado=VersionFlujo.Estado.PUBLICADA)
        ini = Nodo.objects.create(version=v, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        at = Nodo.objects.create(version=v, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
        fin = Nodo.objects.create(version=v, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=v, origen=ini, destino=at)
        Conexion.objects.create(version=v, origen=at, destino=fin)
        return v

    def _caso(self):
        v = self._flujo(self.hosp, self.guardia, "Guardia")
        c = Ciudadano.objects.create(institucion=self.hosp, nombre="Juan", apellido="Pérez",
                                     documento="30111222")
        caso = Caso.objects.create(institucion=self.hosp, version=v, ciudadano=c,
                                   area_actual=self.guardia)
        motor_casos.iniciar(caso, autor=self.med)
        caso.refresh_from_db()
        return caso

    def _como(self, u):
        self.client.force_authenticate(u)

    def _solicitar(self):
        self._como(self.med)
        return self.client.post("/api/traslados/solicitar/", {
            "caso": self.caso.id, "destino": self.centro.id,
            "motivo": "complejidad", "detalle": "Requiere UTI",
        })

    # --- Ciclo ---------------------------------------------------------------- #

    def test_las_acciones_existen_donde_las_pide_la_pantalla(self):
        r = self._solicitar()
        t = r.data["id"]
        self._como(self.jefe)
        for ruta in ["aceptar", "rechazar", "cancelar", "en-camino", "recibido"]:
            with self.subTest(accion=ruta):
                self.assertNotEqual(
                    self.client.post(f"/api/traslados/{t}/{ruta}/").status_code, 404,
                    f"{ruta} no existe",
                )

    def test_solicitar_y_aceptar(self):
        r = self._solicitar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["estado"], "solicitado")
        self._como(self.jefe)
        r2 = self.client.post(f"/api/traslados/{r.data['id']}/aceptar/",
                              {"area_destino": self.uti.id})
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data["estado"], "aceptado")
        self.assertIsNotNone(r2.data["caso_destino"])

    def test_el_ciclo_completo_cierra_el_caso_de_origen_al_llegar(self):
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        self.client.post(f"/api/traslados/{t}/aceptar/", {"area_destino": self.uti.id})
        self._como(self.med)
        self.client.post(f"/api/traslados/{t}/en-camino/", {"movil": "Móvil 3"})
        self.caso.refresh_from_db()
        self.assertNotEqual(self.caso.estado, Caso.Estado.DERIVADO, "se cerró antes de llegar")
        self._como(self.jefe)
        r = self.client.post(f"/api/traslados/{t}/recibido/")
        self.assertEqual(r.status_code, 200, r.data)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.DERIVADO)

    # --- Cada lado hace lo suyo ------------------------------------------------ #

    def test_el_origen_no_puede_aceptar_su_propio_traslado(self):
        """Sería obligar al otro hospital a recibir un paciente."""
        t = self._solicitar().data["id"]
        self._como(self.med)
        r = self.client.post(f"/api/traslados/{t}/aceptar/", {"area_destino": self.uti.id})
        self.assertEqual(r.status_code, 403)

    def test_el_destino_no_puede_cancelar_el_pedido_del_otro(self):
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        self.assertEqual(self.client.post(f"/api/traslados/{t}/cancelar/").status_code, 403)

    def test_un_tercero_no_ve_el_traslado(self):
        self._solicitar()
        self._como(self.ajeno)
        self.assertEqual(self.client.get("/api/traslados/").data["count"], 0)

    def test_los_dos_lados_lo_ven_y_saben_de_que_lado_estan(self):
        self._solicitar()
        self._como(self.med)
        mio = self.client.get("/api/traslados/").data["results"][0]
        self.assertTrue(mio["soy_origen"])
        self._como(self.jefe)
        suyo = self.client.get("/api/traslados/").data["results"][0]
        self.assertFalse(suyo["soy_origen"])

    def test_se_filtra_por_lado(self):
        """Quien recibe quiere ver lo que le mandan, no lo que mandó."""
        self._solicitar()
        self._como(self.jefe)
        self.assertEqual(self.client.get("/api/traslados/?lado=entrantes").data["count"], 1)
        self.assertEqual(self.client.get("/api/traslados/?lado=salientes").data["count"], 0)

    def test_el_estado_no_se_cambia_por_patch(self):
        """Cada paso mueve además el caso de alguno de los dos lados."""
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        r = self.client.patch(f"/api/traslados/{t}/", {"estado": "recibido"})
        self.assertIn(r.status_code, (403, 405))
        self.assertEqual(Traslado.objects.get(pk=t).estado, Traslado.Estado.SOLICITADO)

    def test_no_se_solicita_un_traslado_de_un_caso_ajeno(self):
        t = self._solicitar()
        self._como(self.ajeno)
        r = self.client.post("/api/traslados/solicitar/", {
            "caso": self.caso.id, "destino": self.centro.id, "motivo": "cama",
        })
        self.assertEqual(r.status_code, 403)

    def test_el_rechazo_sin_motivo_lo_dice(self):
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        r = self.client.post(f"/api/traslados/{t}/rechazar/", {"motivo": ""})
        self.assertEqual(r.status_code, 400)
        self.assertIn("motivo", r.data["detail"].lower())

    # --- Panorama --------------------------------------------------------------- #

    def test_los_destinos_posibles_son_los_de_la_red(self):
        self._como(self.med)
        r = self.client.get(f"/api/traslados/destinos/?institucion={self.hosp.id}")
        self.assertEqual([d["nombre"] for d in r.data["destinos"]], ["Hospital Interzonal"])

    def test_las_camas_de_la_red_por_establecimiento(self):
        sala = Subarea.objects.create(area=self.uti, nombre="UTI")
        for i in range(4):
            Cama.objects.create(area=self.uti, subarea=sala, nombre=f"U{i}",
                                estado=Cama.Estado.OCUPADA)
        self._como(self.jefe)
        r = self.client.get(f"/api/redes/{self.red.id}/camas/")
        self.assertEqual(r.status_code, 200, r.data)
        por = {e["nombre"]: e for e in r.data["establecimientos"]}
        self.assertEqual(por["Hospital Interzonal"]["ocupacion"], 100)
        self.assertIn("Hospital Interzonal", r.data["saturados"])

    def test_solo_se_ven_las_redes_donde_participa_mi_institucion(self):
        Red.objects.create(nombre="Otra región")
        self._como(self.med)
        self.assertEqual(
            [r["nombre"] for r in self.client.get("/api/redes/").data["results"]], ["Región VI"]
        )
