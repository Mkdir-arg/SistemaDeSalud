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
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, Notificacion
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Cama, EstadiaCama, Institucion, Subarea
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

    def _caso_en(self, inst, area, titulo, documento=None, nombre="Juan"):
        v = self._flujo_publicado(inst, area, titulo)
        # Documento propio por paciente: dos personas distintas del mismo
        # establecimiento no pueden compartirlo.
        self._doc = getattr(self, "_doc", 30111221) + 1
        c = Ciudadano.objects.create(institucion=inst, nombre=nombre, apellido="Pérez",
                                     documento=str(self._doc) if documento is None else documento)
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

    def test_el_aviso_le_llega_a_la_guardia_medica_y_de_enfermeria(self):
        """
        A las tres de la mañana en el hospital de referencia no hay
        administrativo ni jefe de área: hay médico y enfermería de guardia, que
        tienen la capacidad «trabajo» y son los que deciden si se recibe.
        Dejándolos afuera, el pedido no le suena a nadie que esté en el edificio
        —no hay otro canal: los traslados no aparecen en Inicio ni en
        Supervisión— y queda en «Esperando respuesta» hasta que alguien se
        acuerde de abrir la pantalla, con un paciente esperando del otro lado.
        """
        de_guardia = {}
        for rol in ("medico", "enfermeria"):
            u = Usuario.objects.create_user(f"{rol}@interzonal.gob.ar", "x", nombre=rol.title())
            Membresia.objects.create(usuario=u, institucion=self.centro, rol=rol, activo=True)
            de_guardia[rol] = u

        self._solicitar()
        for rol, u in de_guardia.items():
            with self.subTest(rol=rol):
                self.assertTrue(
                    Notificacion.objects.filter(usuario=u).exists(),
                    f"a {rol} de guardia no le suena nada y es quien decide si se recibe",
                )

    def test_un_destino_atendido_solo_por_la_guardia_recibe_el_aviso(self):
        """
        El agujero completo: un establecimiento cuyos usuarios activos son sólo
        médicos y enfermería no generaba NINGUNA notificación. El pedido entraba
        y del otro lado no se enteraba nadie.
        """
        Membresia.objects.filter(institucion=self.centro).update(rol="enfermeria")
        Notificacion.objects.all().delete()
        self._solicitar()
        self.assertTrue(Notificacion.objects.exists(), "el pedido entró y no le avisó a nadie")

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
        self.assertIsNotNone(nuevo.nodo_actual_id, "el caso tiene que quedar posicionado")

    def test_el_caso_del_destino_cuelga_de_un_paciente_del_destino(self):
        """
        `Ciudadano` tiene FK a institución y toda la API scopea por ahí. Si el
        caso del destino colgara del ciudadano del origen, la UTI que acepta un
        paciente crítico abriría su caso y la ficha le saldría vacía —404 al
        pedir el paciente, cero historias clínicas: sin alergias, sin
        antecedentes, sin estudios— y todo lo que firme su médico se asentaría
        en el legajo del hospital que derivó, que sí lo lee.
        """
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        t.refresh_from_db()
        paciente = t.caso_destino.ciudadano
        self.assertEqual(paciente.institucion_id, self.centro.id)
        self.assertNotEqual(paciente.id, self.caso.ciudadano_id)
        # Es la misma persona, y el traslado guarda las dos puntas para poder
        # seguirla a lo largo de la red.
        self.assertEqual(paciente.documento, self.caso.ciudadano.documento)
        self.assertEqual(t.ciudadano_destino_id, paciente.id)

    def test_si_el_paciente_ya_esta_en_el_destino_se_usa_su_registro(self):
        """
        Duplicarlo partiría su historia en dos legajos del mismo hospital: el
        que ya tenía y el que abre este traslado.
        """
        ya = Ciudadano.objects.create(
            institucion=self.centro, nombre="Juan", apellido="Pérez",
            documento=self.caso.ciudadano.documento,
        )
        t = self._solicitar()
        motor.aceptar(t, autor=self.jefe, area_destino=self.uti)
        t.refresh_from_db()
        self.assertEqual(t.caso_destino.ciudadano_id, ya.id)
        self.assertEqual(
            Ciudadano.objects.filter(institucion=self.centro).count(), 1, "se duplicó el paciente"
        )

    def test_dos_pacientes_sin_documento_no_se_fusionan_en_una_sola_persona(self):
        """
        El NN de guardia es el caso real. Buscar por documento vacío haría que
        el segundo indocumentado que llega herede el legajo del primero: dos
        personas distintas con la misma historia clínica.
        """
        primero = self._caso_en(self.hosp, self.guardia, "NN uno", documento="", nombre="NN1")
        segundo = self._caso_en(self.hosp, self.guardia, "NN dos", documento="", nombre="NN2")
        for caso in (primero, segundo):
            t = motor.solicitar(caso, self.centro, Traslado.Motivo.CAMA, autor=self.med)
            motor.aceptar(t, autor=self.jefe, area_destino=self.uti)

        pacientes = Ciudadano.objects.filter(institucion=self.centro, documento="")
        self.assertEqual(pacientes.count(), 2)

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
        """
        Dos instancias cargadas por separado, que es lo que hay cuando dos
        requests llegan juntos: en el destino el jefe de área y el administrativo
        tienen los dos el botón «Responder» y la pantalla no refresca sola.

        Sin releer la fila con candado adentro de la transacción, el segundo
        chequea el estado sobre su foto vieja y pasa: queda un traslado
        «rechazado» con un caso ya abierto del otro lado —el origen sale a
        buscar otro efector y el destino espera una ambulancia que no sale—,
        y no hay forma de repararlo desde la app.
        """
        t = self._solicitar()
        uno = Traslado.objects.get(pk=t.pk)
        otro = Traslado.objects.get(pk=t.pk)
        motor.aceptar(uno, autor=self.jefe, area_destino=self.uti)
        with self.assertRaises(motor.ErrorTraslado):
            motor.rechazar(otro, "tarde", autor=self.jefe)
        t.refresh_from_db()
        self.assertEqual(t.estado, Traslado.Estado.ACEPTADO)

    def test_dos_aceptaciones_simultaneas_no_abren_dos_casos_por_el_mismo_paciente(self):
        """
        El segundo caso quedaría huérfano —el traslado apunta a uno solo— y
        abierto para siempre en la bandeja del destino, inflando «casos activos»
        e «ingresos» del tablero con el que la región decide a dónde mandar
        recursos.
        """
        t = self._solicitar()
        uno = Traslado.objects.get(pk=t.pk)
        otro = Traslado.objects.get(pk=t.pk)
        motor.aceptar(uno, autor=self.jefe, area_destino=self.uti)
        with self.assertRaises(motor.ErrorTraslado):
            motor.aceptar(otro, autor=self.jefe, area_destino=self.uti)
        self.assertEqual(Caso.objects.filter(institucion=self.centro).count(), 1)

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

    def test_al_cancelar_se_le_avisa_al_que_estaba_esperando_al_paciente(self):
        """
        Del otro lado ya reservaron una cama y avisaron al área. Sin aviso, la
        cama queda bloqueada esperando una ambulancia que no sale y el equipo se
        entera sólo si se le ocurre mirar la pantalla.
        """
        otro = self._caso_en(self.hosp, self.guardia, "Otra guardia")
        t2 = motor.solicitar(otro, self.centro, Traslado.Motivo.CAMA, autor=self.med)
        Notificacion.objects.all().delete()
        motor.cancelar(t2, autor=self.med, motivo="Se consiguió lugar más cerca")
        avisos = Notificacion.objects.filter(usuario=self.jefe)
        self.assertTrue(avisos.exists(), "el destino no se enteró de la baja")
        self.assertTrue(any("Se consiguió lugar" in n.detalle for n in avisos))

    def test_avisa_al_destino_cuando_sale_la_ambulancia(self):
        """
        La marca «Paciente en camino» sólo se asienta en el caso de ORIGEN, que
        el destino no puede leer: sin este aviso, el jefe de UTI que reservó la
        cama no tiene forma de saber si el paciente salió más que el teléfono,
        que es lo que este módulo vino a reemplazar.
        """
        Notificacion.objects.all().delete()
        motor.marcar_en_camino(self.t, movil="Móvil 7", autor=self.med)
        avisos = Notificacion.objects.filter(usuario=self.jefe)
        self.assertTrue(avisos.exists())
        self.assertTrue(any("Móvil 7" in n.detalle for n in avisos), "no dice en qué móvil viene")


class RecepcionTests(RedTestCase):
    """
    Lo que el origen tiene que soltar cuando el paciente llega al otro hospital.

    `marcar_recibido` es el ÚNICO final del sistema que no pasa por el nodo FIN
    ni por `cancelar_caso`, que son los dos que liberan camas y colas. Si no lo
    hace acá, no lo hace nadie: nada libera una cama sola.
    """

    def setUp(self):
        super().setUp()
        from apps.casos import motor as motor_casos

        self.internacion = Area.objects.create(institucion=self.hosp, nombre="Internación")
        f = Flujo.objects.create(
            institucion=self.hosp, area=self.internacion, titulo="Internación"
        )
        v = VersionFlujo.objects.create(
            flujo=f, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        ini = Nodo.objects.create(version=v, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        cama_nodo = Nodo.objects.create(version=v, tipo=Nodo.Tipo.CAMA, titulo="Asignar cama")
        espera = Nodo.objects.create(
            version=v, tipo=Nodo.Tipo.ESPERA_FILA, titulo="Espera del pase"
        )
        fin = Nodo.objects.create(version=v, tipo=Nodo.Tipo.FIN, titulo="Egreso")
        Conexion.objects.create(version=v, origen=ini, destino=cama_nodo)
        Conexion.objects.create(version=v, origen=cama_nodo, destino=espera)
        Conexion.objects.create(version=v, origen=espera, destino=fin)

        sala = Subarea.objects.create(area=self.internacion, nombre="Sala general")
        self.cama = Cama.objects.create(area=self.internacion, subarea=sala, nombre="101-A")

        paciente = Ciudadano.objects.create(
            institucion=self.hosp, nombre="Rosa", apellido="Díaz", documento="27888111"
        )
        self.caso = Caso.objects.create(
            institucion=self.hosp, version=v, ciudadano=paciente, area_actual=self.internacion
        )
        motor_casos.iniciar(self.caso, autor=self.med)
        self.caso.refresh_from_db()
        motor_casos.asignar_cama(self.caso, self.cama.id, autor=self.med)
        self.caso.refresh_from_db()

        self.t = self._solicitar()
        motor.aceptar(self.t, autor=self.jefe, area_destino=self.uti)
        self.t.refresh_from_db()

    def test_al_llegar_al_otro_hospital_se_libera_la_cama_del_origen(self):
        """
        El paciente se fue en la ambulancia. Si la cama no se suelta acá no se
        suelta nunca: queda OCUPADA con su nombre, con la estadía abierta, y el
        sector se queda sin camas sin que nadie entienda por qué. En red es peor:
        esa ocupación falsa es la que alimentan `camas_en_red`, `saturadas` y el
        desplegable de destinos, así que el efector que deriva se muestra más
        lleno de lo que está y la red le deja de mandar pacientes.
        """
        motor.marcar_recibido(self.t, autor=self.jefe)
        self.cama.refresh_from_db()
        self.assertEqual(self.cama.estado, Cama.Estado.HIGIENE)
        self.assertIsNone(self.cama.caso_id)
        estadia = EstadiaCama.objects.get(caso=self.caso)
        self.assertIsNotNone(estadia.hasta, "la estadía queda abierta para siempre")
        self.assertEqual(
            estadia.motivo_egreso, EstadiaCama.Egreso.DERIVACION,
            "«derivación» existe justamente para este egreso y este camino nunca lo escribía",
        )

    def test_la_cama_liberada_vuelve_a_contarse_en_el_panorama_de_la_red(self):
        """
        Es el daño que se propaga: con la cama trabada, el hospital que deriva
        figura lleno, cruza el umbral, se marca SATURADO y cae al fondo de la
        lista de derivación de todos los demás. Cada traslado que sale bien
        empeoraba la información con la que la red decide a dónde va la próxima
        ambulancia.
        """
        antes = {c["institucion"].id: c for c in motor.camas_en_red(self.red)}[self.hosp.id]
        self.assertEqual(antes["ocupacion"], 100)
        motor.marcar_recibido(self.t, autor=self.jefe)
        despues = {c["institucion"].id: c for c in motor.camas_en_red(self.red)}[self.hosp.id]
        self.assertEqual(despues["ocupacion"], 0)
        self.assertEqual(despues["higiene"], 1, "la cama tiene que quedar esperando limpieza")

    def test_el_caso_derivado_sale_de_las_colas_del_origen(self):
        """
        Un paciente internado en otro hospital no puede seguir esperando que lo
        llamen de un box de éste: queda en la fila adelante de gente que sí está
        en el edificio, y ahí no lo saca nadie.
        """
        self.assertTrue(self.caso.en_filas.filter(atendido=False).exists())
        motor.marcar_recibido(self.t, autor=self.jefe)
        self.assertFalse(self.caso.en_filas.filter(atendido=False).exists())


class TableroTests(RedTestCase):
    """
    El panorama con el que una región decide a dónde mandar recursos.
    """

    def test_los_pedidos_sin_responder_no_se_recortan_por_el_periodo(self):
        """
        «Sin responder» es el estado de AHORA, no un hecho del período.
        Contándolo sobre la ventana, elegir «7 días» hacía desaparecer al pedido
        que lleva nueve sin respuesta —el peor de todos, con un paciente
        esperando en otra guardia— y la cifra ámbar bajaba sola, sin que nada lo
        explicara.
        """
        t = self._solicitar()
        Traslado.objects.filter(pk=t.pk).update(
            solicitado_at=timezone.now() - timedelta(days=9)
        )
        d = motor.tablero(self.red, dias=7)
        por = {f["institucion"].nombre: f for f in d["establecimientos"]}
        self.assertEqual(por["Hospital Interzonal"]["pendientes"], 1)
        self.assertEqual(d["totales"]["pendientes"], 1)
        self.assertIsNotNone(
            por["Hospital Interzonal"]["pendiente_mas_viejo"],
            "sin la antigüedad del más viejo, «4 sin responder» no dice si hay que llamar",
        )

    def test_cada_indicador_se_cuenta_del_lado_que_corresponde(self):
        """
        Guarda de la agregación: «derivó» va por origen y «recibió», «rechazó» y
        «responde en» por destino. Cruzados, la región lee que el hospital
        desbordado es el que recibe y le manda recursos al que no los necesita.
        """
        t = self._solicitar()
        motor.rechazar(t, "No hay camas de UTI", autor=self.jefe)
        d = motor.tablero(self.red, dias=30)
        por = {f["institucion"].nombre: f for f in d["establecimientos"]}
        self.assertEqual(por["Hospital de Lomas"]["derivo"], 1)
        self.assertEqual(por["Hospital de Lomas"]["recibio"], 0)
        self.assertEqual(por["Hospital Interzonal"]["recibio"], 1)
        self.assertEqual(por["Hospital Interzonal"]["rechazados"], 1)
        self.assertIsNotNone(por["Hospital Interzonal"]["demora_respuesta_min"])
        self.assertEqual(por["Hospital de Lomas"]["casos_activos"], 1)
        self.assertEqual(d["totales"]["traslados"], 1)
        self.assertEqual(d["totales"]["rechazo_pct"], 100)


class NoLlegoTests(RedTestCase):
    """
    El traslado que sale mal: el paciente se descompensa y fallece en la
    ambulancia, la familia se lo lleva, el móvil lo desvía a otro efector.

    Sin un desenlace para eso, el caso de origen queda EN_ESPERA para siempre
    —no avanza ni cierra— con el paciente muchas veces todavía ahí.
    """

    def setUp(self):
        super().setUp()
        self.t = self._solicitar()
        motor.aceptar(self.t, autor=self.jefe, area_destino=self.uti)
        self.t.refresh_from_db()

    def test_un_traslado_que_no_llego_destraba_el_caso_de_origen(self):
        motor.no_llego(self.t, "Falleció en el traslado", autor=self.med)
        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)
        self.assertNotEqual(self.caso.estado, Caso.Estado.EN_ESPERA)
        self.assertNotEqual(self.caso.estado, Caso.Estado.CANCELADO,
                            "cancelar el caso entero le libera la cama a alguien que sigue ahí")

    def test_cierra_el_caso_que_el_destino_habia_abierto(self):
        """Es una cama comprometida y trabajo en la bandeja por alguien que no va a llegar."""
        motor.no_llego(self.t, "Lo retiró la familia", autor=self.jefe)
        self.t.refresh_from_db()
        self.assertEqual(self.t.caso_destino.estado, Caso.Estado.CANCELADO)
        self.assertEqual(self.t.estado, Traslado.Estado.FALLIDO)
        self.assertFalse(self.t.abierto, "sigue apareciendo como en curso en las dos bandejas")

    def test_no_se_da_por_no_llegado_sin_motivo(self):
        """«Falleció en el traslado» y «lo retiró la familia» no son lo mismo para la región."""
        with self.assertRaises(motor.ErrorTraslado):
            motor.no_llego(self.t, "   ", autor=self.med)

    def test_tambien_se_puede_registrar_con_el_movil_ya_en_la_calle(self):
        motor.marcar_en_camino(self.t, movil="Móvil 3", autor=self.med)
        self.t.refresh_from_db()
        motor.no_llego(self.t, "Desviado a un efector más cercano", autor=self.med)
        self.caso.refresh_from_db()
        self.assertFalse(self.caso.esperando)

    def test_el_motivo_le_llega_a_los_dos_lados(self):
        Notificacion.objects.all().delete()
        motor.no_llego(self.t, "Falleció en el traslado", autor=self.med)
        for quien, lado in ((self.med, "origen"), (self.jefe, "destino")):
            with self.subTest(lado=lado):
                avisos = Notificacion.objects.filter(usuario=quien)
                self.assertTrue(any("Falleció" in n.detalle for n in avisos))

    def test_un_traslado_ya_recibido_no_se_da_por_no_llegado(self):
        """El paciente ya está internado del otro lado: deshacerlo sería inventar."""
        motor.marcar_recibido(self.t, autor=self.jefe)
        self.t.refresh_from_db()
        with self.assertRaises(motor.ErrorTraslado):
            motor.no_llego(self.t, "tarde", autor=self.med)


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

    def test_las_camas_en_higiene_se_ven_y_los_estados_cierran(self):
        """
        Una cama en higiene no es ni libre ni ocupada, y sin exponerla
        desaparecía de la red: la fracción «15/27» de la tabla invita a restar y
        da 44 % de ocupación al lado de una columna que dice 33 %, y quien mira
        deja de confiar en las dos. Son además las que se liberan con un llamado
        a limpieza: la diferencia entre «no hay lugar» y «hay lugar en veinte
        minutos».
        """
        camas = list(Cama.objects.filter(area=self.uti))
        for c in camas[:4]:
            Cama.objects.filter(pk=c.pk).update(estado=Cama.Estado.OCUPADA)
        for c in camas[4:6]:
            Cama.objects.filter(pk=c.pk).update(estado=Cama.Estado.HIGIENE)

        c = {x["institucion"].nombre: x for x in motor.camas_en_red(self.red)}["Hospital Interzonal"]
        self.assertEqual(c["higiene"], 2)
        self.assertEqual(
            c["libres"] + c["ocupadas"] + c["higiene"], c["operativas"],
            "hay camas que no están en ninguno de los números que muestra la pantalla",
        )

    def test_avisa_de_los_establecimientos_saturados(self):
        Cama.objects.filter(area=self.uti).update(estado=Cama.Estado.OCUPADA)
        nombres = [c["institucion"].nombre for c in motor.saturadas(self.red, umbral=90)]
        self.assertEqual(nombres, ["Hospital Interzonal"])

    def test_un_establecimiento_sin_camas_no_figura_saturado(self):
        """Cero de cero no es 100 %: es que no tiene internación."""
        self.assertNotIn(
            "Hospital de Lomas", [c["institucion"].nombre for c in motor.saturadas(self.red)]
        )
