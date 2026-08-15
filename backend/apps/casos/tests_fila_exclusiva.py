"""
Que dos boxes no se peleen al mismo paciente, y que el llamado se escuche.

Salió de una auditoría por módulo. Los dos primeros son el mismo episodio visto
de los dos lados y es el peor de la guardia: el paciente camina a un consultorio
mientras el médico que lo llamó primero lo espera en otro, y el sistema lo deja
firmar con su matrícula la atención de alguien a quien nunca vio.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso, ItemFila
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Box, Grupo, Institucion
from apps.registros.models import Ciudadano


class FilaTestCase(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.box1 = Box.objects.create(area=self.area, nombre="Box 1")
        self.box2 = Box.objects.create(area=self.area, nombre="Box 2")

        self.grupo = Grupo.objects.create(area=self.area, nombre="Médicos de guardia")
        self.med1 = self._medico("uno@test.local", "Ana", "Ruiz", "MP 1")
        self.med2 = self._medico("dos@test.local", "Beto", "Sosa", "MP 2")

        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        # Publicada: «Mi trabajo» sólo mira flujos publicados, así que sin esto
        # la mitad de los tests compara dos listas vacías y pasa sin probar nada.
        self.ver = VersionFlujo.objects.create(
            flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ate = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención",
            config={"con_fila": True},
        )
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.ate)
        Conexion.objects.create(version=self.ver, origen=self.ate, destino=fin)
        self.ate.grupos.set([self.grupo])

    def _medico(self, email, nombre, apellido, matricula):
        u = Usuario.objects.create_user(email, "x", nombre=nombre, apellido=apellido)
        m = Membresia.objects.create(
            usuario=u, institucion=self.inst, rol="medico", activo=True
        )
        m.areas.set([self.area])
        u.grupos.set([self.grupo])
        LegajoProfesional.objects.create(usuario=u, matricula=matricula)
        return u

    def _encolar(self, nombre="Juan"):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="Pérez")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.med1)
        caso.refresh_from_db()
        return caso


class LlamadoExclusivoTests(FilaTestCase):
    def test_otro_box_no_puede_robarse_un_paciente_ya_llamado(self):
        """
        Dos médicos con la Fila abierta llaman al mismo. Antes el segundo pisaba
        el box y el caso quedaba asignado a él: el paciente entraba al Box 2 y el
        del Box 1 lo esperaba sin saber que ya no lo tenía.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.llamar(caso, box_id=self.box2.id, autor=self.med2)
        self.assertIn("Box 1", str(e.exception))

    def test_el_error_dice_quién_lo_tiene_y_qué_hacer(self):
        """
        «No se puede» deja al segundo médico sin saber si el paciente está
        caminando hacia otro box o si el sistema falló.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.llamar(caso, box_id=self.box2.id, autor=self.med2)
        self.assertIn("Ana Ruiz", str(e.exception))
        self.assertIn("devolverlo a la cola", str(e.exception))

    def test_el_caso_sigue_con_quien_lo_llamó_primero(self):
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        try:
            motor.llamar(caso, box_id=self.box2.id, autor=self.med2)
        except motor.ErrorMotor:
            pass
        caso.refresh_from_db()
        self.assertEqual(caso.asignado_a_id, self.med1.id)
        self.assertEqual(caso.en_filas.first().box_id, self.box1.id)

    def test_llamar_de_nuevo_al_mismo_box_sigue_funcionando(self):
        """El que llamó puede reintentar; el candado es contra el robo, no contra él."""
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)  # no explota

    def test_después_de_devolverlo_a_la_cola_otro_box_sí_puede_llamarlo(self):
        """
        Es la salida que el error propone. Si no funcionara, un paciente quedaría
        atrapado con el médico que se fue a su casa.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        motor.devolver_a_la_cola(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.llamar(caso, box_id=self.box2.id, autor=self.med2)
        caso.refresh_from_db()
        self.assertEqual(caso.en_filas.first().box_id, self.box2.id)


class AtencionDelQuePerdioElLlamadoTests(FilaTestCase):
    """
    La otra mitad del mismo episodio: que el médico que se quedó sin el paciente
    no pueda registrar su atención.
    """

    def test_no_se_puede_registrar_la_atención_de_un_paciente_que_atiende_otro(self):
        """
        Un acto firmado con matrícula en la historia clínica de alguien a quien
        no se vio. Es lo más grave que puede salir de acá.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        caso.refresh_from_db()
        with self.assertRaises(motor.ErrorMotor) as e:
            motor.avanzar(caso, {"titulo": "Consulta", "contenido": "x", "firmada": True},
                          autor=self.med2)
        self.assertIn("Ana Ruiz", str(e.exception))

    def test_el_que_lo_llamó_sí_puede_registrarla(self):
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        caso.refresh_from_db()
        motor.avanzar(caso, {"titulo": "Consulta", "contenido": "x", "firmada": True},
                      autor=self.med1)  # no explota

    def test_un_caso_sin_asignar_no_bloquea_a_nadie(self):
        """
        El candado es «lo atiende otro», no «no está asignado a vos». Sin esta
        distinción, una atención con fila que nadie tomó quedaría intocable.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        Caso.objects.filter(pk=caso.pk).update(asignado_a=None)
        caso.refresh_from_db()
        motor.avanzar(caso, {"titulo": "Consulta", "contenido": "x", "firmada": True},
                      autor=self.med2)  # no explota


class RellamadoQueSeEscuchaTests(FilaTestCase):
    """
    Volver a llamar a alguien que había vuelto a la cola era MUDO: el médico veía
    «Llamaste a Ana», y en la sala de espera no pasaba nada.
    """

    def _ultimo_llamado(self, caso):
        it = caso.en_filas.order_by("-id").first()
        return it.rellamado_at or it.llamado_at

    def test_volver_a_llamar_después_de_devolver_a_la_cola_se_anuncia(self):
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        primero = self._ultimo_llamado(caso)

        motor.devolver_a_la_cola(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        caso.refresh_from_db()

        self.assertGreater(self._ultimo_llamado(caso), primero)

    def test_volver_a_llamar_a_un_ausente_que_reapareció_se_anuncia(self):
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        primero = self._ultimo_llamado(caso)
        motor.marcar_ausente(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.devolver_a_la_cola(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        caso.refresh_from_db()
        self.assertGreater(self._ultimo_llamado(caso), primero)

    def test_el_primer_llamado_no_se_pisa(self):
        """
        `llamado_at` mide la espera hasta el primer llamado, y esa espera
        ocurrió. Reiniciarlo dejaría el indicador de demora del servicio más bajo
        cuanto peor se opera la cola.
        """
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        primero = caso.en_filas.first().llamado_at
        motor.devolver_a_la_cola(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        self.assertEqual(caso.en_filas.first().llamado_at, primero)

    def test_se_cuenta_cuántas_veces_se_lo_llamó(self):
        caso = self._encolar()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        motor.devolver_a_la_cola(caso, autor=self.med1)
        caso.refresh_from_db()
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        self.assertEqual(caso.en_filas.first().veces_llamado, 2)


class PantallaDeSalaTests(FilaTestCase):
    """El televisor de la sala de espera, que corre sin autenticación."""

    def setUp(self):
        super().setUp()
        self.ate.pantalla_token = "tok-de-prueba"
        self.ate.save(update_fields=["pantalla_token"])

    def _pantalla(self):
        from rest_framework.test import APIClient

        return APIClient().get("/api/pantalla/tok-de-prueba/").data

    def test_muestra_el_llamado_de_recién(self):
        caso = self._encolar("Juan")
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        self.assertEqual(len(self._pantalla()["llamados"]), 1)

    def test_no_muestra_el_llamado_de_anoche(self):
        """
        A las 7 de la mañana el televisor anunciaba al paciente llamado a las
        23:40 y lo mandaba a un box que ahora ocupa otro. Y dejaba su nombre y
        apellido colgado toda la noche en una pantalla pública.
        """
        caso = self._encolar("Juan")
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        viejo = timezone.now() - timedelta(hours=12)
        ItemFila.objects.filter(caso=caso).update(llamado_at=viejo, rellamado_at=None)
        self.assertEqual(self._pantalla()["llamados"], [])

    def test_un_rellamado_revive_un_llamado_viejo(self):
        """Si se lo vuelve a llamar, tiene que volver a aparecer."""
        caso = self._encolar("Juan")
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        ItemFila.objects.filter(caso=caso).update(
            llamado_at=timezone.now() - timedelta(hours=12), rellamado_at=timezone.now()
        )
        self.assertEqual(len(self._pantalla()["llamados"]), 1)


class ApiDeLaColaTests(APITestCase):
    """
    La cola se lee por la API y se OPERA por el motor. Los dos agujeros que había
    salteaban el motor: uno cambiaba el orden sin permiso, el otro editaba y
    borraba sin dejar rastro.
    """

    def setUp(self):
        base = FilaTestCase()
        base.setUp()
        self.__dict__.update({k: v for k, v in base.__dict__.items() if not k.startswith("_")})
        self.caso = base._encolar("Juan")
        self.item = self.caso.en_filas.first()
        self.ajeno = Usuario.objects.create_user("ajeno@test.local", "x", nombre="Carla")
        Membresia.objects.create(
            usuario=self.ajeno, institucion=self.inst, rol="administrativo", activo=True
        )

    def test_reordenar_exige_ser_del_grupo_responsable(self):
        """
        El orden de la cola es quién se atiende primero. Era el único punto de la
        fila sin este control: cualquiera que cambiara el selector de área podía
        adelantar a alguien en una guardia ajena.
        """
        self.client.force_authenticate(self.ajeno)
        r = self.client.post(f"/api/items-fila/{self.item.id}/mover/", {"posicion": 0})
        self.assertEqual(r.status_code, 403)

    def test_quien_es_del_grupo_sí_puede_reordenar(self):
        self.client.force_authenticate(self.med1)
        r = self.client.post(f"/api/items-fila/{self.item.id}/mover/", {"posicion": 0})
        self.assertEqual(r.status_code, 200, r.data)

    def test_no_se_puede_editar_un_ítem_de_la_cola_por_la_api(self):
        """
        Un PATCH cambiaba orden, box o «atendido» sin registrar un evento. La
        línea de tiempo del caso es la trazabilidad del episodio.
        """
        self.client.force_authenticate(self.med1)
        r = self.client.patch(f"/api/items-fila/{self.item.id}/", {"orden": 99})
        self.assertEqual(r.status_code, 405)
        self.item.refresh_from_db()
        self.assertNotEqual(self.item.orden, 99)

    def test_no_se_puede_borrar_un_ítem_de_la_cola_por_la_api(self):
        """Sacaba a un paciente de la cola sin dejar rastro de que existió."""
        self.client.force_authenticate(self.med1)
        self.assertEqual(
            self.client.delete(f"/api/items-fila/{self.item.id}/").status_code, 405
        )
        self.assertTrue(ItemFila.objects.filter(pk=self.item.pk).exists())

    def test_la_cola_se_sigue_pudiendo_leer(self):
        """El recorte es sobre la escritura: la pantalla de Fila lee de acá."""
        self.client.force_authenticate(self.med1)
        self.assertEqual(self.client.get("/api/items-fila/").status_code, 200)


class UnSoloOrdenDeColaTests(FilaTestCase):
    """
    «El siguiente» tiene que ser la misma persona en todas las pantallas.

    Había dos ordenamientos: «Mi trabajo» por prioridad del caso, «Filas de
    espera» por el reordenamiento manual. La enfermera de triage adelantaba a
    alguien que empeoró esperando, el médico llamaba desde la otra pantalla, y
    llamaba a otro. El adelantamiento manual es LA herramienta de la guardia
    para el que se descompensa en la sala.
    """

    def _cola_de_la_api(self):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(self.med1)
        r = c.get("/api/items-fila/?atendido=false&box=null&page_size=50")
        return [f["persona"] for f in r.data["results"]]

    def _cola_de_mi_trabajo(self):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(self.med1)
        filas = c.get("/api/mis-tareas/").data["filas"]
        return [x["ciudadano_nombre"] for f in filas for x in f["casos"]]

    def test_las_dos_pantallas_dan_el_mismo_siguiente(self):
        for n in ("Ana", "Beto", "Cira"):
            self._encolar(n)
        self.assertEqual(self._cola_de_la_api()[0], self._cola_de_mi_trabajo()[0])

    def test_adelantar_a_mano_se_respeta_en_las_dos(self):
        """El caso que motivó todo: el que empeoró esperando."""
        casos = [self._encolar(n) for n in ("Ana", "Beto", "Cira")]
        item = casos[2].en_filas.first()
        motor.mover_en_fila(item, 0, autor=self.med1)

        self.assertEqual(self._cola_de_la_api()[0], "Cira Pérez")
        self.assertEqual(self._cola_de_mi_trabajo()[0], "Cira Pérez")

    def test_la_prioridad_del_caso_se_respeta_en_las_dos(self):
        """
        Al revés también fallaba: un caso «urgente» iba primero en «Mi trabajo»
        y en «Filas de espera» no se distinguía de uno normal.
        """
        self._encolar("Ana")
        urgente = self._encolar("Beto")
        Caso.objects.filter(pk=urgente.pk).update(prioridad=Caso.Prioridad.URGENTE)

        self.assertEqual(self._cola_de_la_api()[0], "Beto Pérez")
        self.assertEqual(self._cola_de_mi_trabajo()[0], "Beto Pérez")

    def test_el_urgente_del_item_también_manda(self):
        """
        El triage marca `urgente` en el ítem y una decisión del flujo marca la
        prioridad del caso: dicen lo mismo por dos caminos y cualquiera de los
        dos tiene que mandar al frente.
        """
        self._encolar("Ana")
        segundo = self._encolar("Beto")
        ItemFila.objects.filter(caso=segundo).update(urgente=True)
        self.assertEqual(self._cola_de_la_api()[0], "Beto Pérez")
        self.assertEqual(self._cola_de_mi_trabajo()[0], "Beto Pérez")


class LoQueLasPantallasNecesitanSaberTests(FilaTestCase):
    """
    Datos que la API no daba y por eso la pantalla mentía o escondía.
    """

    def _mis_tareas(self):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(self.med1)
        return c.get("/api/mis-tareas/").data

    def _puesto(self):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(self.med1)
        return c.get(f"/api/puestos/{self.ate.id}/").data

    def test_la_espera_se_mide_desde_el_paso_y_no_desde_el_ingreso(self):
        """
        El semáforo (ámbar 15 min, rojo 30) se apagaba solo: contaba desde el
        ingreso al hospital, así que todo lo que está más adelante del flujo
        salía en rojo. El color dejaba de significar algo y se ignoraba.
        """
        caso = self._encolar()
        viejo = timezone.now() - timedelta(hours=5)
        Caso.objects.filter(pk=caso.pk).update(creado=viejo)

        fila = self._puesto()["casos"][0]
        self.assertIn("espera_desde", fila)
        # Entró a la cola recién: la espera del paso es de segundos, no de 5 h.
        self.assertGreater(fila["espera_desde"], viejo)
        self.assertLess(
            (timezone.now() - fila["espera_desde"]).total_seconds(), 60,
            "está midiendo desde el ingreso al hospital, no desde el paso",
        )

    def test_mi_trabajo_dice_quién_está_en_mi_box(self):
        """
        «Salir del box» no lo sabía: el médico se iba en un cambio de turno con
        el paciente adentro, el box quedaba libre y otro llamaba a alguien más al
        mismo consultorio.
        """
        caso = self._encolar("Juan")
        from apps.instituciones.models import Box

        Box.objects.filter(pk=self.box1.pk).update(ocupado_por=self.med1)
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)

        fila = self._mis_tareas()["filas"][0]
        self.assertIsNotNone(fila["mi_paciente"])
        self.assertEqual(fila["mi_paciente"]["persona"], "Juan Pérez")

    def test_con_el_box_vacío_no_inventa_un_paciente(self):
        from apps.instituciones.models import Box

        Box.objects.filter(pk=self.box1.pk).update(ocupado_por=self.med1)
        self._encolar("Juan")  # esperando, no llamado
        self.assertIsNone(self._mis_tareas()["filas"][0]["mi_paciente"])

    def test_los_ausentes_se_pueden_listar(self):
        """
        Salen de la cola con `atendido=True` y desaparecían de todas las
        pantallas: el que salió a fumar y vuelve no tenía cómo ser reencolado.
        """
        from rest_framework.test import APIClient

        caso = self._encolar("Juan")
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        motor.marcar_ausente(caso, autor=self.med1)
        # Uno que SÍ está esperando: sin él, el filtro puede no existir y el test
        # pasa igual porque devolver «todos» y devolver «los ausentes» coincide.
        self._encolar("Rosa")

        c = APIClient()
        c.force_authenticate(self.med1)
        r = c.get("/api/items-fila/?ausente=true")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["persona"], "Juan Pérez")

    def test_el_ausente_no_ensucia_la_cola_de_los_que_esperan(self):
        """No está esperando: va aparte, no mezclado con la fila."""
        from rest_framework.test import APIClient

        caso = self._encolar("Juan")
        motor.llamar(caso, box_id=self.box1.id, autor=self.med1)
        motor.marcar_ausente(caso, autor=self.med1)

        c = APIClient()
        c.force_authenticate(self.med1)
        r = c.get("/api/items-fila/?atendido=false&box=null")
        self.assertEqual(r.data["count"], 0)
