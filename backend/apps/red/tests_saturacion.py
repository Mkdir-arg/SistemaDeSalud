"""
Aviso de saturación.

El panorama de camas ya existía, pero había que ir a mirarlo. Lo que se cuida
acá es que el aviso llegue a quien puede hacer algo con él y que no se repita:
un aviso cada media hora sobre lo mismo se termina ignorando, y con él se
ignoran los que sí son nuevos.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Notificacion
from apps.instituciones.models import Area, Cama, Institucion, Subarea

from .models import Red


class SaturacionTests(TestCase):
    def setUp(self):
        self.red = Red.objects.create(nombre="Región VI")
        self.lleno = Institucion.objects.create(nombre="Hospital Interzonal")
        self.otro = Institucion.objects.create(nombre="Hospital de Lomas")
        self.red.instituciones.set([self.lleno, self.otro])

        uti = Area.objects.create(institucion=self.lleno, nombre="UTI")
        sala = Subarea.objects.create(area=uti, nombre="UTI")
        for i in range(10):
            Cama.objects.create(area=uti, subarea=sala, nombre=f"U{i}",
                                estado=Cama.Estado.OCUPADA)

        self.jefe_lleno = self._usuario("jefe@lleno.gob.ar", self.lleno, "jefe_area")
        self.jefe_otro = self._usuario("jefe@otro.gob.ar", self.otro, "jefe_area")
        self.medico_otro = self._usuario("med@otro.gob.ar", self.otro, "medico")

    def _usuario(self, email, inst, rol):
        u = Usuario.objects.create_user(email, "x")
        Membresia.objects.create(usuario=u, institucion=inst, rol=rol, activo=True)
        return u

    def _correr(self, *args):
        salida, errores = StringIO(), StringIO()
        call_command("alertar_saturacion", *args, stdout=salida, stderr=errores)
        return salida.getvalue(), errores.getvalue()

    def test_avisa_a_los_otros_establecimientos_de_la_red(self):
        self._correr()
        self.assertTrue(Notificacion.objects.filter(usuario=self.jefe_otro).exists())

    def test_no_le_avisa_al_que_esta_saturado(self):
        """Ya lo sabe: lo está viviendo. Sumarle un aviso es ruido en el peor momento."""
        self._correr()
        self.assertFalse(Notificacion.objects.filter(usuario=self.jefe_lleno).exists())

    def test_el_aviso_dice_cuantas_camas_quedan_y_que_hacer(self):
        self._correr()
        n = Notificacion.objects.filter(usuario=self.jefe_otro).first()
        self.assertIn("Hospital Interzonal", n.titulo)
        self.assertIn("0 libres de 10", n.detalle)
        self.assertIn("derivar a otro", n.detalle)

    def test_no_repite_el_mismo_aviso(self):
        """Un aviso cada media hora sobre lo mismo se termina ignorando."""
        self._correr()
        antes = Notificacion.objects.count()
        self._correr()
        self.assertEqual(Notificacion.objects.count(), antes)

    def test_no_avisa_si_nadie_esta_saturado(self):
        Cama.objects.all().update(estado=Cama.Estado.LIBRE)
        self._correr()
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_un_establecimiento_sin_camas_no_cuenta_como_saturado(self):
        """Cero de cero no es 100 %: es que no tiene internación."""
        Cama.objects.all().delete()
        self._correr()
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_en_seco_no_avisa(self):
        self._correr("--seco")
        self.assertEqual(Notificacion.objects.count(), 0)

    def test_una_red_sin_otro_efector_lo_dice_en_vez_de_callarlo(self):
        """
        Si no hay a quién avisarle, la alerta no sirve. Callarlo deja buscando
        por qué «no anda».
        """
        self.red.instituciones.set([self.lleno])
        _, errores = self._correr()
        self.assertIn("no hay a quién avisarle", errores)

    def test_el_umbral_se_puede_ajustar(self):
        Cama.objects.all().update(estado=Cama.Estado.LIBRE)
        for c in Cama.objects.all()[:5]:
            c.estado = Cama.Estado.OCUPADA
            c.save()
        self._correr("--umbral", "90")
        self.assertEqual(Notificacion.objects.count(), 0, "50 % no debería disparar con umbral 90")
        self._correr("--umbral", "40")
        self.assertTrue(Notificacion.objects.exists())


class TableroRedTests(TestCase):
    """
    Indicadores comparados: una región usa esto para decidir a dónde mandar
    recursos, así que lo que se cuida es que los números signifiquen lo mismo en
    todos los establecimientos.
    """

    def setUp(self):
        from apps.casos import motor as motor_casos
        from apps.casos.models import Caso
        from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
        from apps.red import motor as motor_red
        from apps.registros.models import Ciudadano

        self.red = Red.objects.create(nombre="Región VI")
        self.chico = Institucion.objects.create(nombre="Municipal")
        self.grande = Institucion.objects.create(nombre="Interzonal")
        self.red.instituciones.set([self.chico, self.grande])
        self.guardia = Area.objects.create(institucion=self.chico, nombre="Guardia")
        self.uti = Area.objects.create(institucion=self.grande, nombre="UTI")

        def flujo(inst, area, titulo):
            f = Flujo.objects.create(institucion=inst, area=area, titulo=titulo)
            v = VersionFlujo.objects.create(flujo=f, numero=1,
                                            estado=VersionFlujo.Estado.PUBLICADA)
            ini = Nodo.objects.create(version=v, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
            at = Nodo.objects.create(version=v, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
            fin = Nodo.objects.create(version=v, tipo=Nodo.Tipo.FIN, titulo="Cierre")
            Conexion.objects.create(version=v, origen=ini, destino=at)
            Conexion.objects.create(version=v, origen=at, destino=fin)
            return v

        v_chico = flujo(self.chico, self.guardia, "Guardia")
        flujo(self.grande, self.uti, "UTI")
        self.med = self._usuario("m@chico.gob.ar", self.chico, "medico")
        self.jefe = self._usuario("j@grande.gob.ar", self.grande, "jefe_area")

        sala = Subarea.objects.create(area=self.uti, nombre="UTI")
        for i in range(8):
            Cama.objects.create(area=self.uti, subarea=sala, nombre=f"U{i}")

        self.motor_red = motor_red
        for i in range(5):
            c = Ciudadano.objects.create(institucion=self.chico, nombre=f"P{i}", apellido="T")
            caso = Caso.objects.create(institucion=self.chico, version=v_chico, ciudadano=c,
                                       area_actual=self.guardia)
            motor_casos.iniciar(caso, autor=self.med)
            caso.refresh_from_db()
            t = motor_red.solicitar(caso, self.grande, "complejidad", autor=self.med)
            if i < 3:
                motor_red.aceptar(t, autor=self.jefe, area_destino=self.uti)
            elif i == 3:
                motor_red.rechazar(t, "Sin camas", autor=self.jefe)

    def _usuario(self, email, inst, rol):
        u = Usuario.objects.create_user(email, "x")
        Membresia.objects.create(usuario=u, institucion=inst, rol=rol, activo=True)
        return u

    def test_los_traslados_se_cuentan_por_quien_derivo(self):
        """«Cuántos derivó» mide lo que ese efector no pudo resolver."""
        d = self.motor_red.tablero(self.red)
        por = {f["institucion"].nombre: f for f in d["establecimientos"]}
        self.assertEqual(por["Municipal"]["derivo"], 5)
        self.assertEqual(por["Municipal"]["recibio"], 0)
        self.assertEqual(por["Interzonal"]["recibio"], 5)

    def test_el_rechazo_se_calcula_sobre_los_resueltos(self):
        """
        Incluir los que nadie contestó haría que el porcentaje mejore solo por
        dejar pedidos sin responder.
        """
        d = self.motor_red.tablero(self.red)
        # 4 resueltos (3 aceptados + 1 rechazado), 1 pendiente → 25 %.
        self.assertEqual(d["totales"]["rechazo_pct"], 25)
        self.assertEqual(d["totales"]["pendientes"], 1)

    def test_muestra_cuanto_tarda_cada_uno_en_responder(self):
        """
        Un hospital que tarda seis horas en decir que sí es, en la práctica, un
        hospital que no recibe.
        """
        d = self.motor_red.tablero(self.red)
        por = {f["institucion"].nombre: f for f in d["establecimientos"]}
        self.assertIsNotNone(por["Interzonal"]["demora_respuesta_min"])
        self.assertIsNone(por["Municipal"]["demora_respuesta_min"], "no recibió ninguno")

    def test_la_ocupacion_es_la_misma_definicion_que_en_cada_hospital(self):
        camas = list(Cama.objects.filter(area=self.uti).order_by("id"))
        for c in camas[:4]:
            c.estado = Cama.Estado.BLOQUEADA
            c.save()
        for c in camas[4:6]:
            c.estado = Cama.Estado.OCUPADA
            c.save()
        d = self.motor_red.tablero(self.red)
        por = {f["institucion"].nombre: f for f in d["establecimientos"]}
        self.assertEqual(por["Interzonal"]["camas_operativas"], 4, "las fuera de servicio no cuentan")
        self.assertEqual(por["Interzonal"]["ocupacion"], 50)
