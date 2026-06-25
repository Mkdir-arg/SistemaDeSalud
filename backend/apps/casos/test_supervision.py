"""Poderes del jefe/supervisor de área: reasignar, repriorizar y cancelar.

Ver docs/ROLES-Y-PERMISOS.md (Capa 3).
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso, ItemFila
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano


class SupervisionTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inst = Institucion.objects.create(nombre="Hospital Test", tipo="Hospital")
        cls.area = Area.objects.create(institucion=cls.inst, nombre="Guardia")
        cls.otra = Area.objects.create(institucion=cls.inst, nombre="Cardiología")
        cls.flujo = Flujo.objects.create(institucion=cls.inst, area=cls.area, titulo="F")
        cls.ver = VersionFlujo.objects.create(flujo=cls.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA)
        cls.nodo = Nodo.objects.create(version=cls.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención", config={"con_fila": True})

        R = Membresia.Rol
        cls.jefe = cls._miembro("jefe@test.local", R.JEFE_AREA, cls.area)
        cls.jefe_otra = cls._miembro("jefe2@test.local", R.JEFE_AREA, cls.otra)
        cls.adm = cls._miembro("adm@test.local", R.ADMINISTRATIVO, cls.area)
        cls.med = cls._miembro("med@test.local", R.MEDICO, cls.area)

    @classmethod
    def _miembro(cls, email, rol, area):
        u = Usuario.objects.create_user(email=email, password="x", nombre="N")
        m = Membresia.objects.create(usuario=u, institucion=cls.inst, rol=rol)
        m.areas.add(area)
        return u

    def _caso(self):
        c = Ciudadano.objects.create(institucion=self.inst, nombre="P", documento="1")
        return Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c,
                                   nodo_actual=self.nodo, area_actual=self.area)

    # --- motor -------------------------------------------------------------
    def test_supervisa_su_area_no_otra(self):
        caso = self._caso()
        self.assertTrue(motor.usuario_supervisa(self.jefe, caso))
        self.assertFalse(motor.usuario_supervisa(self.jefe_otra, caso))
        self.assertFalse(motor.usuario_supervisa(self.adm, caso))

    def test_cancelar_saca_de_la_fila(self):
        caso = self._caso()
        item = ItemFila.objects.create(caso=caso, nodo=self.nodo, atendido=False)
        motor.cancelar_caso(caso, autor=self.jefe, motivo="duplicado")
        caso.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.CANCELADO)
        self.assertTrue(item.atendido)

    def test_no_se_cancela_dos_veces(self):
        caso = self._caso()
        motor.cancelar_caso(caso, autor=self.jefe)
        with self.assertRaises(motor.ErrorMotor):
            motor.cancelar_caso(caso, autor=self.jefe)

    # --- API ---------------------------------------------------------------
    def test_api_jefe_cancela(self):
        caso = self._caso()
        self.client.force_authenticate(self.jefe)
        r = self.client.post(f"/api/casos/{caso.id}/cancelar/", {"motivo": "x"})
        self.assertEqual(r.status_code, 200)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.CANCELADO)

    def test_api_administrativo_no_cancela(self):
        caso = self._caso()
        self.client.force_authenticate(self.adm)
        r = self.client.post(f"/api/casos/{caso.id}/cancelar/", {"motivo": "x"})
        self.assertEqual(r.status_code, 403)

    def test_api_jefe_reasigna(self):
        caso = self._caso()
        self.client.force_authenticate(self.jefe)
        r = self.client.post(f"/api/casos/{caso.id}/asignar/", {"usuario_id": self.med.id})
        self.assertEqual(r.status_code, 200)
        caso.refresh_from_db()
        self.assertEqual(caso.asignado_a_id, self.med.id)

    def test_api_jefe_prioriza_y_actualiza_fila(self):
        caso = self._caso()
        item = ItemFila.objects.create(caso=caso, nodo=self.nodo, atendido=False, urgente=False)
        self.client.force_authenticate(self.jefe)
        r = self.client.post(f"/api/casos/{caso.id}/priorizar/", {"prioridad": "urgente"})
        self.assertEqual(r.status_code, 200)
        caso.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(caso.prioridad, "urgente")
        self.assertTrue(item.urgente)

    # --- Notificaciones ----------------------------------------------------
    def test_reasignar_genera_notificacion(self):
        from apps.casos.models import Notificacion
        caso = self._caso()
        self.client.force_authenticate(self.jefe)
        self.client.post(f"/api/casos/{caso.id}/asignar/", {"usuario_id": self.med.id})
        self.assertTrue(Notificacion.objects.filter(usuario=self.med, caso=caso).exists())
        # El médico ve su resumen y luego marca todo leído.
        self.client.force_authenticate(self.med)
        r = self.client.get("/api/notificaciones/resumen/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["no_leidas"], 1)
        self.client.post("/api/notificaciones/leer/", {})
        self.assertEqual(self.client.get("/api/notificaciones/resumen/").data["no_leidas"], 0)

    def test_cancelar_avisa_al_responsable(self):
        from apps.casos.models import Notificacion
        caso = self._caso()
        caso.asignado_a = self.med
        caso.save(update_fields=["asignado_a"])
        motor.cancelar_caso(caso, autor=self.jefe, motivo="duplicado")
        self.assertTrue(Notificacion.objects.filter(usuario=self.med, caso=caso, titulo="Caso cancelado").exists())

    def test_notificaciones_son_privadas(self):
        # Una notificación de un usuario no la ve otro.
        from apps.casos.models import Notificacion
        Notificacion.objects.create(usuario=self.med, titulo="privada")
        self.client.force_authenticate(self.adm)
        self.assertEqual(self.client.get("/api/notificaciones/resumen/").data["no_leidas"], 0)
