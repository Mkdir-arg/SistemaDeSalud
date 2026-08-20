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
        for ruta in ["aceptar", "rechazar", "cancelar", "en-camino", "recibido", "no-llego"]:
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

    def test_los_abiertos_y_los_resueltos_se_piden_por_separado(self):
        """
        La pantalla existe para responder pedidos y no puede depender de cuántos
        traslados viejos haya: trayendo el histórico entero para partirlo en el
        cliente, un pedido de hace diez minutos se cae de la página y del otro
        lado hay un paciente esperando una respuesta que no va a llegar.
        """
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        self.client.post(f"/api/traslados/{t}/rechazar/", {"motivo": "Sin camas"})
        self._solicitar()
        self._como(self.jefe)
        self.assertEqual(self.client.get("/api/traslados/?abiertos=true").data["count"], 1)
        self.assertEqual(self.client.get("/api/traslados/?abiertos=false").data["count"], 1)

    # --- Más de un establecimiento --------------------------------------------- #

    def test_quien_tiene_los_dos_efectores_ve_el_traslado_desde_donde_esta_parado(self):
        """
        La dirección de una red y las regiones sanitarias son justamente quienes
        tienen más de un efector. Resolviendo el lado contra el conjunto de
        membresías, aparecían como origen en TODOS los traslados: la pestaña
        «Nos derivan» se quedaba sin «Responder» ni «Llegó» y el paciente seguía
        esperando en la otra guardia.
        """
        Membresia.objects.create(
            usuario=self.med, institucion=self.centro, rol="jefe_area", activo=True
        )
        self._solicitar()
        self._como(self.med)
        parado_en_destino = self.client.get(
            f"/api/traslados/?institucion={self.centro.id}"
        ).data["results"][0]
        self.assertFalse(parado_en_destino["soy_origen"])
        parado_en_origen = self.client.get(
            f"/api/traslados/?institucion={self.hosp.id}"
        ).data["results"][0]
        self.assertTrue(parado_en_origen["soy_origen"])

    def test_desde_el_establecimiento_que_recibe_no_se_cancela_el_pedido_del_otro(self):
        """
        Es el botón que le quedaba a mano en la fila que lee como «me están
        derivando»: un clic anulaba de verdad el pedido del otro hospital.
        """
        Membresia.objects.create(
            usuario=self.med, institucion=self.centro, rol="jefe_area", activo=True
        )
        t = self._solicitar().data["id"]
        self._como(self.med)
        r = self.client.post(f"/api/traslados/{t}/cancelar/", {"institucion": self.centro.id})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Traslado.objects.get(pk=t).estado, Traslado.Estado.SOLICITADO)

    def test_el_traslado_que_no_llego_lo_registran_los_dos_lados(self):
        """
        Al que falleció en la ambulancia lo sabe el origen; al que se desvió,
        cualquiera de los dos. Sin esto el caso de origen queda congelado.
        """
        t = self._solicitar().data["id"]
        self._como(self.jefe)
        self.client.post(f"/api/traslados/{t}/aceptar/", {"area_destino": self.uti.id})
        self._como(self.ajeno)
        self.assertEqual(
            self.client.post(f"/api/traslados/{t}/no-llego/", {"motivo": "x"}).status_code, 404,
            "un tercero no tiene por qué tocar este traslado",
        )
        self._como(self.med)
        r = self.client.post(f"/api/traslados/{t}/no-llego/", {"motivo": "Falleció en el traslado"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["estado"], "fallido")
        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)

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

    def test_un_rol_sin_capacidad_operativa_no_puede_pedir_un_traslado(self):
        """
        `solicitar` es una acción de LISTA: el permiso por capacidad sólo valida
        `create` y las acciones de detalle, así que sin chequearlo acá el rol de
        sólo diseño —el del proveedor, el consultor, quien arma los flujos—
        deriva un paciente real. El caso queda EN_ESPERA, el destino reserva una
        cama, y después ese mismo usuario recibe 403 al cancelarlo (las acciones
        de detalle sí se validan): quien tiene «trabajo» se come «Ese caso ya
        tiene un traslado en curso» hasta que alguien dé de baja el pedido falso.
        """
        conf = self._usuario("conf@lomas.gob.ar", self.hosp, "configurador")
        self._como(conf)
        r = self.client.post("/api/traslados/solicitar/", {
            "caso": self.caso.id, "destino": self.centro.id, "motivo": "complejidad",
        })
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(Traslado.objects.exists(), "quedó un pedido que su autor no puede deshacer")
        self.caso.refresh_from_db()
        self.assertNotEqual(self.caso.estado, Caso.Estado.EN_ESPERA)

    def test_no_se_responde_un_traslado_en_el_establecimiento_donde_no_se_opera(self):
        """
        La capacidad se resolvía contra la UNIÓN de las membresías: quien es jefe
        de área en un hospital y configurador en otro aceptaba traslados en el
        segundo —comprometiendo una cama y abriendo un caso clínico— donde no
        tiene ninguna capacidad operativa.
        """
        mixto = self._usuario("mixto@lomas.gob.ar", self.hosp, "jefe_area")
        Membresia.objects.create(
            usuario=mixto, institucion=self.centro, rol="configurador", activo=True
        )
        t = self._solicitar().data["id"]
        self._como(mixto)
        r = self.client.post(f"/api/traslados/{t}/aceptar/", {
            "area_destino": self.uti.id, "institucion": self.centro.id,
        })
        self.assertEqual(r.status_code, 403, r.data)
        self.assertEqual(Traslado.objects.get(pk=t).estado, Traslado.Estado.SOLICITADO)

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

    def test_el_saturado_se_marca_por_establecimiento_y_no_por_nombre(self):
        """
        `Institucion.nombre` no es único, y en una región sanitaria los
        homónimos son comunes: «Hospital Municipal», «Centro de Salud N° 1».
        Comparando por texto, el que tiene camas libres queda marcado SATURADO y
        el orden lo manda al fondo del desplegable: la ambulancia sale media
        hora más lejos por un dato que miente en silencio.
        """
        lleno = Institucion.objects.create(nombre="Hospital Municipal")
        vacio = Institucion.objects.create(nombre="Hospital Municipal")
        self.red.instituciones.add(lleno, vacio)
        for inst, estado in ((lleno, Cama.Estado.OCUPADA), (vacio, Cama.Estado.LIBRE)):
            area = Area.objects.create(institucion=inst, nombre="Internación")
            sala = Subarea.objects.create(area=area, nombre="Sala")
            for i in range(4):
                Cama.objects.create(area=area, subarea=sala, nombre=f"{inst.id}-{i}",
                                    estado=estado)

        self._como(self.med)
        r = self.client.get(f"/api/traslados/destinos/?institucion={self.hosp.id}")
        por_id = {d["id"]: d for d in r.data["destinos"]}
        self.assertTrue(por_id[lleno.id]["saturado"])
        self.assertFalse(por_id[vacio.id]["saturado"],
                         "marcó saturado al homónimo que tiene camas libres")

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

    def test_las_redes_se_pueden_pedir_por_establecimiento(self):
        """
        Un hospital está en su región sanitaria y además en las redes de
        patología (trauma, perinatal, quemados), y quien tiene varios efectores
        ve las redes de todos. Sin poder filtrar, la pantalla sólo puede quedarse
        con la primera por orden alfabético: el panorama que se mira para decidir
        a dónde mandar recursos es el de otra red, y nada avisa que falten.
        """
        trauma = Red.objects.create(nombre="Aa Red de trauma")
        trauma.instituciones.add(self.centro)
        Membresia.objects.create(
            usuario=self.med, institucion=self.centro, rol="jefe_area", activo=True
        )
        self._como(self.med)
        todas = [r["nombre"] for r in self.client.get("/api/redes/").data["results"]]
        self.assertEqual(todas[0], "Aa Red de trauma", "sin filtro decide el orden alfabético")
        de_lomas = self.client.get(f"/api/redes/?instituciones={self.hosp.id}").data["results"]
        self.assertEqual([r["nombre"] for r in de_lomas], ["Región VI"])

    def test_un_admin_institucional_no_crea_redes_sanitarias(self):
        admin = self._usuario("admin-red@lomas.gob.ar", self.hosp, "admin")
        self._como(admin)
        r = self.client.post("/api/redes/", {
            "nombre": "Red creada por hospital",
            "instituciones": [self.hosp.id, self.centro.id],
        }, format="json")
        self.assertEqual(r.status_code, 403, r.data)
        self.assertFalse(Red.objects.filter(nombre="Red creada por hospital").exists())

    def test_plataforma_crea_y_ve_todas_las_redes(self):
        base = Institucion.objects.create(nombre="Direccion provincial")
        plataforma = self._usuario("plataforma-red@gob.ar", base, Membresia.Rol.PLATAFORMA)
        Red.objects.create(nombre="Red sin mis efectores")

        self._como(plataforma)
        r = self.client.post("/api/redes/", {
            "nombre": "Red provincial",
            "instituciones": [self.hosp.id, self.centro.id],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)

        listado = self.client.get("/api/redes/?page_size=100")
        self.assertEqual(listado.status_code, 200, listado.data)
        nombres = {red["nombre"] for red in listado.data["results"]}
        self.assertIn("Red sin mis efectores", nombres)
        self.assertIn("Red provincial", nombres)
