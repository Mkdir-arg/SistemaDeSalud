"""
Camas: que ninguna se pierda del stock y que el tablero no funda dos sectores.

Una cama que figura ocupada y está vacía no la recupera nadie: no se ofrece más,
infla la ocupación del sector de forma permanente y la única salida es entrar a
la base a mano, en producción. Dos sectores distintos con el mismo nombre son
peor todavía: el porcentaje que se lee es de otro servicio.
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Usuario
from apps.casos.models import Caso
from apps.flujos.models import Flujo, Nodo, VersionFlujo

from .models import Area, Cama, EstadiaCama, Institucion, Subarea


class CamaSinPacienteTests(TestCase):
    """Borrar un caso internado no puede dejar la cama inutilizable."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.sala = Subarea.objects.create(area=self.area, nombre="Clínica médica")
        self.cama = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")

    def _internar(self):
        caso = Caso.objects.create(institucion=self.inst, version=self.ver)
        self.cama.estado = Cama.Estado.OCUPADA
        self.cama.caso = caso
        self.cama.save(update_fields=["estado", "caso"])
        EstadiaCama.objects.create(cama=self.cama, caso=caso, desde=timezone.now())
        return caso

    def test_borrar_un_caso_internado_devuelve_la_cama_al_circuito(self):
        """
        Si la cama se queda en «ocupada» sin ocupante, no hay forma de sacarla de
        ahí desde la aplicación: se pierde del stock del sector y la ocupación
        queda inflada para siempre.
        """
        caso = self._internar()
        caso.delete()
        self.cama.refresh_from_db()
        self.assertIsNone(self.cama.caso_id)
        self.assertEqual(self.cama.estado, Cama.Estado.HIGIENE)

    def test_la_cama_liberada_asi_queda_en_higiene_y_no_libre(self):
        """
        Alguien la estuvo usando. Devolverla «libre» la pondría a disposición
        del siguiente paciente sin higienizar, que es exactamente el error que
        el estado «en higiene» existe para evitar.
        """
        self._internar().delete()
        self.cama.refresh_from_db()
        self.assertNotEqual(self.cama.estado, Cama.Estado.LIBRE)
        self.assertFalse(self.cama.disponible)

    def test_borrar_un_caso_no_toca_las_camas_de_otro(self):
        """La reparación es del caso que se borra, no de todo el sector."""
        otra = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-B")
        vecino = Caso.objects.create(institucion=self.inst, version=self.ver)
        otra.estado = Cama.Estado.OCUPADA
        otra.caso = vecino
        otra.save(update_fields=["estado", "caso"])

        self._internar().delete()
        otra.refresh_from_db()
        self.assertEqual(otra.estado, Cama.Estado.OCUPADA)
        self.assertEqual(otra.caso_id, vecino.id)


class CamaHuerfanaAPITests(APITestCase):
    """
    La salida por HTTP para una cama que ya quedó inconsistente.

    La guarda de arriba evita que se generen nuevas, pero las que ya están en la
    base —o las que lleguen por cualquier otro camino— también tienen que poder
    recuperarse sin abrir una consola de Postgres en un hospital.
    """

    def setUp(self):
        self.user = Usuario.objects.create_user(
            "jefe@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internación")
        self.cama = Cama.objects.create(area=self.area, nombre="101-A")

    def _dejar_huerfana(self):
        # El estado exacto que dejaba un caso borrado: ocupada, sin ocupante y
        # sin estadía abierta.
        Cama.objects.filter(pk=self.cama.pk).update(estado=Cama.Estado.OCUPADA, caso=None)

    def test_una_cama_ocupada_sin_paciente_se_puede_liberar(self):
        """
        Sin esto la cama no se recupera nunca: el motor corta en «ocupada», el
        egreso necesita una estadía que no existe y el estado no se escribe por
        PATCH. Queda una cama vacía que el sistema dice ocupada.
        """
        self._dejar_huerfana()
        r = self.client.post(f"/api/camas/{self.cama.id}/estado/", {"estado": "libre"})
        self.assertEqual(r.status_code, 200, r.data)
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, Cama.Estado.LIBRE)

    def test_una_cama_con_paciente_adentro_sigue_sin_poder_liberarse(self):
        """
        La contracara: la reparación no puede convertirse en un atajo para
        marcar libre una cama ocupada de verdad, que dejaría a un paciente
        internado en ningún lado.
        """
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Internación")
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(institucion=self.inst, version=ver)
        self.cama.estado = Cama.Estado.OCUPADA
        self.cama.caso = caso
        self.cama.save(update_fields=["estado", "caso"])
        EstadiaCama.objects.create(cama=self.cama, caso=caso, desde=timezone.now())

        r = self.client.post(f"/api/camas/{self.cama.id}/estado/", {"estado": "libre"})
        self.assertEqual(r.status_code, 400)
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, Cama.Estado.OCUPADA)


class ConfiguracionDeCamasTests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            "root-camas@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.otra = Institucion.objects.create(nombre="Hospital Norte")
        self.area = Area.objects.create(institucion=self.inst, nombre="Internacion")
        self.area_ajena = Area.objects.create(institucion=self.otra, nombre="Internacion")
        self.sala = Subarea.objects.create(area=self.area, nombre="Sala 1")
        self.sala_ajena = Subarea.objects.create(area=self.area_ajena, nombre="Sala 1")

    def test_no_crea_cama_con_sector_de_otra_area(self):
        r = self.client.post("/api/camas/", {
            "area": self.area.pk, "subarea": self.sala_ajena.pk, "nombre": "101-A",
        }, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Cama.objects.filter(nombre="101-A").exists())

    def test_patch_no_mueve_cama_de_area_ni_sector(self):
        cama = Cama.objects.create(area=self.area, subarea=self.sala, nombre="101-A")
        r = self.client.patch(f"/api/camas/{cama.pk}/", {
            "area": self.area_ajena.pk, "subarea": self.sala_ajena.pk,
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        cama.refresh_from_db()
        self.assertEqual((cama.area_id, cama.subarea_id), (self.area.pk, self.sala.pk))

    def test_patch_no_mueve_area_de_institucion(self):
        r = self.client.patch(f"/api/areas/{self.area.pk}/", {
            "institucion": self.otra.pk,
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.area.refresh_from_db()
        self.assertEqual(self.area.institucion_id, self.inst.pk)


class MetricasInstitucionTests(APITestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            "root-metricas@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.version = VersionFlujo.objects.create(flujo=flujo, numero=1)

    def test_los_casos_cancelados_no_cuentan_como_activos(self):
        Caso.objects.create(institucion=self.inst, version=self.version)
        Caso.objects.create(
            institucion=self.inst, version=self.version, estado=Caso.Estado.CERRADO
        )
        Caso.objects.create(
            institucion=self.inst, version=self.version, estado=Caso.Estado.CANCELADO
        )

        r = self.client.get(f"/api/instituciones/{self.inst.pk}/metricas/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["casos_activos"], 1)


class TableroPorSectorTests(APITestCase):
    """
    Dos sectores que se llaman igual son dos sectores.

    `Subarea` es única por área, no por institución: «Sala general» de Clínica
    médica y «Sala general» de Cirugía es una configuración normal de hospital.
    Si el tablero las funde, el jefe de Cirugía lee la ocupación de otro servicio
    y quien busca cama para un post-quirúrgico ve fichas que no son suyas.
    """

    def setUp(self):
        self.user = Usuario.objects.create_user(
            "jefe2@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.clinica = Area.objects.create(institucion=self.inst, nombre="Clínica médica")
        self.cirugia = Area.objects.create(institucion=self.inst, nombre="Cirugía")
        self.sala_clinica = Subarea.objects.create(area=self.clinica, nombre="Sala general")
        self.sala_cirugia = Subarea.objects.create(area=self.cirugia, nombre="Sala general")

    def _tablero(self):
        r = self.client.get("/api/camas/tablero/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_dos_sectores_con_el_mismo_nombre_no_se_funden(self):
        Cama.objects.create(area=self.clinica, subarea=self.sala_clinica, nombre="C1",
                            estado=Cama.Estado.OCUPADA)
        Cama.objects.create(area=self.cirugia, subarea=self.sala_cirugia, nombre="Q1")

        salas = [s for s in self._tablero()["sectores"] if s["sector"] == "Sala general"]
        self.assertEqual(len(salas), 2, "se fundieron dos sectores distintos")
        self.assertEqual({s["sector_id"] for s in salas},
                         {self.sala_clinica.id, self.sala_cirugia.id})
        por_ocupacion = {s["ocupacion"] for s in salas}
        self.assertEqual(por_ocupacion, {0, 100}, "el porcentaje salió combinado")

    def test_cada_sector_dice_de_que_area_es(self):
        """
        Sin el área, la pantalla dibuja dos tarjetas rotuladas igual y no hay
        forma de saber cuál es la propia: es peor que fundirlas, porque se elige
        una al azar creyendo que se eligió bien.
        """
        Cama.objects.create(area=self.clinica, subarea=self.sala_clinica, nombre="C1")
        Cama.objects.create(area=self.cirugia, subarea=self.sala_cirugia, nombre="Q1")

        salas = [s for s in self._tablero()["sectores"] if s["sector"] == "Sala general"]
        self.assertEqual({s["area"] for s in salas}, {"Clínica médica", "Cirugía"})

    def test_un_sector_con_todas_las_camas_de_baja_no_aparece(self):
        """
        Un sector fantasma dibuja una tarjeta vacía con «0 camas libres» y 0 %,
        y suma ruido a la única pantalla que tiene que leerse de un vistazo.
        """
        Cama.objects.create(area=self.clinica, subarea=self.sala_clinica, nombre="C1", activa=False)
        Cama.objects.create(area=self.cirugia, subarea=self.sala_cirugia, nombre="Q1")

        sectores = self._tablero()["sectores"]
        self.assertEqual([s["sector_id"] for s in sectores], [self.sala_cirugia.id])
