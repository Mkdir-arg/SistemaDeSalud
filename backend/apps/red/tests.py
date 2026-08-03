"""
Traslados entre establecimientos.

Dos cosas se cuidan por encima del resto:

1. **Que el paciente nunca quede sin dueño.** Mientras el traslado no se
   concreta, el caso de origen sigue abierto y en su bandeja. Cerrarlo al pedir
   —o al aceptar— dejaría a una persona sin responsable justo en el momento más
   delicado.
2. **Que un hospital no vea los datos del otro.** Lo único compartido es el
   traslado; el caso de cada lado es de su dueño.
"""
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, Notificacion
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, Institucion, Subarea
from apps.registros.models import Ciudadano

from . import motor
from .models import Red, Traslado


class RedTestCase(TestCase):
    def setUp(self):
        self.red = Red.objects.create(nombre="Región Sanitaria VI")
        self.hosp = Institucion.objects.create(nombre="Hospital de Lomas")
        self.centro = Institucion.objects.create(nombre="Hospital Interzonal")
        self.ajeno = Institucion.objects.create(nombre="Clínica sin red")
        self.red.instituciones.set([self.hosp, self.centro])

        self.guardia = Area.objects.create(institucion=self.hosp, nombre="Guardia")
        self.uti = Area.objects.create(institucion=self.centro, nombre="Terapia intensiva")

        self.med = Usuario.objects.create_user("med@lomas.gob.ar", "x", nombre="Ana")
        Membresia.objects.create(usuario=self.med, institucion=self.hosp, rol="medico", activo=True)
        self.jefe = Usuario.objects.create_user("jefe@interzonal.gob.ar", "x", nombre="Beto")
        Membresia.objects.create(
            usuario=self.jefe, institucion=self.centro, rol="jefe_area", activo=True
        )

        # Flujo de la guardia de origen y flujo publicado en la UTI de destino.
        self.caso = self._caso_en(self.hosp, self.guardia, "Ingreso a Guardia")
        self._flujo_publicado(self.centro, self.uti, "Ingreso a UTI")

    def _flujo_publicado(self, inst, area, titulo):
        f = Flujo.objects.create(institucion=inst, area=area, titulo=titulo)
        v = VersionFlujo.objects.create(flujo=f, numero=1, estado=VersionFlujo.Estado.PUBLICADA)
        ini = Nodo.objects.create(version=v, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        aten = Nodo.objects.create(version=v, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
        fin = Nodo.objects.create(version=v, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=v, origen=ini, destino=aten)
        Conexion.objects.create(version=v, origen=aten, destino=fin)
        return v

    def _caso_en(self, inst, area, titulo):
        v = self._flujo_publicado(inst, area, titulo)
        c = Ciudadano.objects.create(institucion=inst, nombre="Juan", apellido="Pérez",
                                     documento="30111222")
        caso = Caso.objects.create(institucion=inst, version=v, ciudadano=c, area_actual=area)
        from apps.casos import motor as motor_casos
        motor_casos.iniciar(caso, autor=self.med)
        caso.refresh_from_db()
        return caso

    def _solicitar(self, **kw):
        return motor.solicitar(
            self.caso, self.centro, Traslado.Motivo.COMPLEJIDAD,
            detalle="Requiere UTI", autor=self.med, **kw,
        )


class DestinosTests(RedTestCase):
    def test_solo_se_deriva_dentro_de_la_red(self):
        """
        Sin esto, «derivar» sería una lista con todas las instituciones del
        sistema, incluidas las que no tienen ninguna relación con ésta.
        """
        destinos = set(motor.destinos_posibles(self.hosp).values_list("nombre", flat=True))
        self.assertEqual(destinos, {"Hospital Interzonal"})

    def test_no_se_deriva_a_una_institucion_fuera_de_la_red(self):
        with self.assertRaises(motor.ErrorTraslado):
            motor.solicitar(self.caso, self.ajeno, Traslado.Motivo.COMPLEJIDAD, autor=self.med)

    def test_no_se_deriva_a_si_mismo(self):
        with self.assertRaises(motor.ErrorTraslado):
            motor.solicitar(self.caso, self.hosp, Traslado.Motivo.COMPLEJIDAD, autor=self.med)


class SolicitudTests(RedTestCase):
    def test_solicitar_deja_el_caso_esperando_y_no_cerrado(self):
        """
        El paciente sigue siendo responsabilidad de quien lo tiene hasta que el
        traslado se concrete. Cerrarlo al pedir lo dejaría sin dueño.
        """
        self._solicitar()
        self.caso.refresh_from_db()
        self.assertTrue(self.caso.esperando)
        self.assertEqual(self.caso.estado, Caso.Estado.EN_ESPERA)
        self.assertNotIn(self.caso.estado, (Caso.Estado.CERRADO, Caso.Estado.DERIVADO))

    def test_no_se_crea_el_caso_de_destino_hasta_que_acepten(self):
        """
        Crear un caso en un hospital que todavía no dijo que sí es meterle
        trabajo en la bandeja por algo que puede rechazar.
        """
        t = self._solicitar()
        self.assertIsNone(t.caso_destino_id)
        self.assertEqual(Caso.objects.filter(institucion=self.centro).count(), 0)

    def test_avisa_a_quien_puede_resolverlo_en_el_destino(self):
        """Un traslado que nadie mira es un paciente esperando."""
        self._solicitar()
        self.assertTrue(Notificacion.objects.filter(usuario=self.jefe).exists())

    def test_no_se_piden_dos_traslados_del_mismo_caso(self):
        self._solicitar()
        with self.assertRaises(motor.ErrorTraslado):
            self._solicitar()

    def test_un_caso_cerrado_no_se_traslada(self):
        self.caso.estado = Caso.Estado.CERRADO
        self.caso.save()
        with self.assertRaises(motor.ErrorTraslado):
            self._solicitar()


class RespuestaTests(RedTestCase):
    def test_aceptar_abre_el_caso_del_lado_del_destino(self):
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        t.refresh_from_db()
        self.assertEqual(t.estado, Traslado.Estado.ACEPTADO)
        nuevo = t.caso_destino
        self.assertIsNotNone(nuevo)
        self.assertEqual(nuevo.institucion_id, self.centro.id)
        self.assertEqual(nuevo.ciudadano_id, self.caso.ciudadano_id)
        self.assertIsNotNone(nuevo.nodo_actual_id, "el caso tiene que quedar posicionado")

    def test_el_caso_de_origen_sigue_abierto_despues_de_aceptar(self):
        """Mientras el paciente no llegó, sigue siendo del que lo tiene."""
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        self.caso.refresh_from_db()
        self.assertNotEqual(self.caso.estado, Caso.Estado.CERRADO)

    def test_rechazar_destraba_el_caso_de_origen(self):
        """El paciente vuelve a ser responsabilidad de quien lo tiene."""
        t = self._solicitar()
        motor.rechazar(t, "No hay camas de UTI disponibles", autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)
        self.assertNotEqual(self.caso.estado, Caso.Estado.EN_ESPERA)

    def test_un_rechazo_necesita_motivo(self):
        """
        Sin él, quien deriva no sabe si insistir, buscar otro hospital o
        esperar.
        """
        t = self._solicitar()
        with self.assertRaises(motor.ErrorTraslado):
            motor.rechazar(t, "   ", autor=self.jefe)

    def test_el_motivo_del_rechazo_le_llega_al_origen(self):
        t = self._solicitar()
        motor.rechazar(t, "No hay camas de UTI", autor=self.jefe)
        avisos = Notificacion.objects.filter(usuario=self.med)
        self.assertTrue(any("No hay camas" in n.detalle for n in avisos))

    def test_no_se_responde_dos_veces(self):
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        t.refresh_from_db()
        with self.assertRaises(motor.ErrorTraslado):
            motor.rechazar(t, "tarde", autor=self.jefe)

    def test_sin_flujo_publicado_en_el_area_lo_dice(self):
        vacia = Area.objects.create(institucion=self.centro, nombre="Sin flujo")
        t = self._solicitar()
        with self.assertRaises(motor.ErrorTraslado) as e:
            motor.aceptar(t, autor=self.jefe, area_destino=vacia)
        self.assertIn("publicado", str(e.exception))

    def test_no_se_acepta_hacia_un_area_de_otro_establecimiento(self):
        t = self._solicitar()
        with self.assertRaises(motor.ErrorTraslado):
            motor.aceptar(t, autor=self.jefe, area_destino=self.guardia)


class ViajeTests(RedTestCase):
    def setUp(self):
        super().setUp()
        self.t = self._solicitar()
        motor.aceptar(self.t, autor=self.jefe, area_destino=self.uti)
        self.t.refresh_from_db()

    def test_el_caso_de_origen_se_cierra_recien_cuando_el_paciente_llega(self):
        """
        Mientras está en la ambulancia sigue siendo responsabilidad de quien lo
        mandó, y un caso cerrado desaparece de su bandeja.
        """
        motor.marcar_en_camino(self.t, movil="Móvil 3", autor=self.med)
        self.caso.refresh_from_db()
        self.assertNotEqual(self.caso.estado, Caso.Estado.DERIVADO)

        self.t.refresh_from_db()
        motor.marcar_recibido(self.t, autor=self.jefe)
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Caso.Estado.DERIVADO)
        self.assertFalse(self.caso.esperando)

    def test_se_miden_los_tiempos_del_traslado(self):
        """Es el indicador que una región le pide a su red."""
        motor.marcar_en_camino(self.t, autor=self.med)
        self.t.refresh_from_db()
        motor.marcar_recibido(self.t, autor=self.jefe)
        self.t.refresh_from_db()
        self.assertIsNotNone(self.t.demora_min)
        self.assertIsNotNone(self.t.traslado_min)

    def test_no_sale_un_traslado_que_no_fue_aceptado(self):
        otro = self._caso_en(self.hosp, self.guardia, "Otra guardia")
        t2 = motor.solicitar(otro, self.centro, Traslado.Motivo.CAMA, autor=self.med)
        with self.assertRaises(motor.ErrorTraslado):
            motor.marcar_en_camino(t2, autor=self.med)

    def test_no_se_cancela_uno_que_el_destino_ya_aceptó(self):
        """Ya hay un caso abierto del otro lado: hay que resolverlo allá."""
        with self.assertRaises(motor.ErrorTraslado):
            motor.cancelar(self.t, autor=self.med)

    def test_cancelar_antes_de_la_respuesta_destraba_el_origen(self):
        otro = self._caso_en(self.hosp, self.guardia, "Otra guardia")
        t2 = motor.solicitar(otro, self.centro, Traslado.Motivo.CAMA, autor=self.med)
        motor.cancelar(t2, autor=self.med, motivo="Mejoró")
        otro.refresh_from_db()
        self.assertFalse(otro.esperando)


class VisibilidadTests(RedTestCase):
    """
    Lo único que cruza la frontera entre instituciones es el traslado.
    """

    def test_los_dos_lados_ven_el_traslado(self):
        self._solicitar()
        self.assertEqual(motor.visibles_para(self.med).count(), 1)
        self.assertEqual(motor.visibles_para(self.jefe).count(), 1)

    def test_un_tercero_no_lo_ve(self):
        self._solicitar()
        ajeno = Usuario.objects.create_user("otro@ajeno.gob.ar", "x")
        Membresia.objects.create(
            usuario=ajeno, institucion=self.ajeno, rol="medico", activo=True
        )
        self.assertEqual(motor.visibles_para(ajeno).count(), 0)

    def test_el_traslado_no_arrastra_el_caso_del_otro_lado(self):
        """
        Cada institución sigue siendo dueña de sus casos: lo que se comparte es
        el pedido, no la historia clínica.
        """
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        t.refresh_from_db()
        # El caso de destino existe pero pertenece al otro establecimiento.
        self.assertEqual(t.caso_destino.institucion_id, self.centro.id)
        self.assertEqual(t.caso_origen.institucion_id, self.hosp.id)


class PanoramaTests(RedTestCase):
    def setUp(self):
        super().setUp()
        sala = Subarea.objects.create(area=self.uti, nombre="UTI")
        for i in range(10):
            Cama.objects.create(area=self.uti, subarea=sala, nombre=f"U{i}")

    def test_muestra_la_ocupacion_de_cada_establecimiento(self):
        """
        Sin esto, quien deriva llama por teléfono a preguntar si hay lugar y
        muchas veces manda la ambulancia a un hospital que ya está lleno.
        """
        Cama.objects.filter(area=self.uti).update(estado=Cama.Estado.OCUPADA)
        panorama = {c["institucion"].nombre: c for c in motor.camas_en_red(self.red)}
        self.assertEqual(panorama["Hospital Interzonal"]["ocupacion"], 100)
        self.assertEqual(panorama["Hospital de Lomas"]["total"], 0)

    def test_la_ocupacion_se_calcula_igual_que_en_el_tablero_de_cada_hospital(self):
        """
        Un criterio distinto en la red que en la casa haría que los dos números
        se contradigan y no se pueda confiar en ninguno: las fuera de servicio
        no van en el denominador.
        """
        camas = list(Cama.objects.filter(area=self.uti))
        for c in camas[:5]:
            c.estado = Cama.Estado.OCUPADA
            c.save()
        for c in camas[5:]:
            c.estado = Cama.Estado.BLOQUEADA
            c.save()
        panorama = {c["institucion"].nombre: c for c in motor.camas_en_red(self.red)}
        self.assertEqual(panorama["Hospital Interzonal"]["operativas"], 5)
        self.assertEqual(panorama["Hospital Interzonal"]["ocupacion"], 100)

    def test_avisa_de_los_establecimientos_saturados(self):
        Cama.objects.filter(area=self.uti).update(estado=Cama.Estado.OCUPADA)
        nombres = [c["institucion"].nombre for c in motor.saturadas(self.red, umbral=90)]
        self.assertEqual(nombres, ["Hospital Interzonal"])

    def test_un_establecimiento_sin_camas_no_figura_saturado(self):
        """Cero de cero no es 100 %: es que no tiene internación."""
        self.assertNotIn(
            "Hospital de Lomas", [c["institucion"].nombre for c in motor.saturadas(self.red)]
        )
