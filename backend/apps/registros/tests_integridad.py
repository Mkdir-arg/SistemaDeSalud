"""
Sellado de integridad de la historia clínica.

Hasta acá «firmada» era un booleano: alguien con acceso a la base podía editar
el texto de una atención de hace dos años y no quedaba ni rastro. Estos tests
verifican lo único que importa del sellado —que ese cambio se detecte— y que la
cadena entre entradas haga que alterar una vieja no alcance con recalcular su
propio resumen.
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from apps.registros import integridad
from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica


class IntegridadTestCase(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.med = Usuario.objects.create_user("med@test.local", "x", nombre="Ana", apellido="Ruiz")
        m = Membresia.objects.create(
            usuario=self.med, institucion=self.inst, rol="medico", activo=True
        )
        # El motor exige estar asignado al área para poder firmar una atención.
        m.areas.set([self.area])
        LegajoProfesional.objects.create(usuario=self.med, matricula="MP 12345")
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Juan", apellido="Pérez", documento="30111222"
        )
        self.hc = HistoriaClinica.objects.create(ciudadano=self.paciente)

    def _entrada(self, titulo="Consulta", contenido="Todo normal.", firmada=True):
        e = EntradaHistoria.objects.create(
            historia=self.hc, titulo=titulo, contenido=contenido,
            autor=self.med, firmada=firmada, matricula="MP 12345" if firmada else "",
        )
        return integridad.sellar(e)


class SelladoTests(IntegridadTestCase):
    def test_firmar_deja_un_sello(self):
        e = self._entrada()
        self.assertTrue(e.sello)
        self.assertIsNotNone(e.firmada_at)

    def test_una_entrada_sin_firmar_no_se_sella(self):
        """Es un borrador: sellarla daría a entender que alguien se hizo responsable."""
        e = self._entrada(firmada=False)
        self.assertEqual(e.sello, "")

    def test_una_entrada_intacta_se_verifica(self):
        self.assertTrue(integridad.verificar(self._entrada())["ok"])

    def test_cambiar_el_texto_despues_de_firmar_se_detecta(self):
        """
        Es lo único que importa del sellado: sin esto, editar una atención de
        hace dos años no dejaba ni rastro.
        """
        e = self._entrada(contenido="Paciente estable.")
        EntradaHistoria.objects.filter(pk=e.pk).update(contenido="Paciente descompensado.")
        e.refresh_from_db()
        r = integridad.verificar(e)
        self.assertFalse(r["ok"])
        self.assertIn("cambió", r["motivo"])

    def test_cambiar_el_titulo_tambien_se_detecta(self):
        e = self._entrada(titulo="Control")
        EntradaHistoria.objects.filter(pk=e.pk).update(titulo="Alta médica")
        e.refresh_from_db()
        self.assertFalse(integridad.verificar(e)["ok"])

    def test_cambiar_de_autor_se_detecta(self):
        """Atribuirle a otro una atención que no hizo es de lo más grave que puede pasar."""
        otro = Usuario.objects.create_user("otro@test.local", "x")
        e = self._entrada()
        EntradaHistoria.objects.filter(pk=e.pk).update(autor=otro)
        e.refresh_from_db()
        self.assertFalse(integridad.verificar(e)["ok"])

    def test_cambiar_la_matricula_se_detecta(self):
        e = self._entrada()
        EntradaHistoria.objects.filter(pk=e.pk).update(matricula="MP 99999")
        e.refresh_from_db()
        self.assertFalse(integridad.verificar(e)["ok"])

    def test_mover_texto_de_un_campo_a_otro_no_da_el_mismo_sello(self):
        """
        Sin un separador que no pueda aparecer en el contenido, «AB»+«C» y
        «A»+«BC» darían el mismo resumen y se podría mover texto sin romperlo.
        """
        a = self._entrada(titulo="AB", contenido="C")
        b = self._entrada(titulo="A", contenido="BC")
        self.assertNotEqual(a.sello, b.sello)

    def test_una_entrada_anterior_al_sellado_lo_dice_en_vez_de_mentir(self):
        """
        No se puede afirmar que esté intacta ni que esté alterada. Decir
        «intacta» sin poder probarlo es peor que no decir nada.
        """
        e = self._entrada()
        EntradaHistoria.objects.filter(pk=e.pk).update(sello="", sello_previo="")
        e.refresh_from_db()
        r = integridad.verificar(e)
        self.assertIsNone(r["ok"])
        self.assertIn("no verificable", r["motivo"])

    def test_una_entrada_sin_firmar_no_es_un_error(self):
        """Decir «inválida» de algo que nunca se firmó enseña a ignorar las alarmas."""
        self.assertTrue(integridad.verificar(self._entrada(firmada=False))["ok"])


class CadenaTests(IntegridadTestCase):
    """
    La cadena es lo que separa «se puede verificar una entrada» de «se puede
    verificar la historia».
    """

    def test_cada_entrada_se_encadena_con_la_anterior(self):
        a = self._entrada(titulo="Primera")
        b = self._entrada(titulo="Segunda")
        self.assertEqual(a.sello_previo, "")
        self.assertEqual(b.sello_previo, a.sello)

    def test_la_historia_completa_se_verifica(self):
        for i in range(4):
            self._entrada(titulo=f"Control {i}")
        r = integridad.verificar_historia(self.hc)
        self.assertTrue(r["ok"], r["problemas"])
        self.assertEqual(r["firmadas"], 4)
        self.assertEqual(r["selladas"], 4)

    def test_alterar_una_entrada_vieja_marca_la_historia(self):
        a = self._entrada(titulo="Primera", contenido="original")
        self._entrada(titulo="Segunda")
        self._entrada(titulo="Tercera")
        EntradaHistoria.objects.filter(pk=a.pk).update(contenido="alterado")
        r = integridad.verificar_historia(self.hc)
        self.assertFalse(r["ok"])
        self.assertIn(a.id, [p["entrada"] for p in r["problemas"]])

    def test_recalcular_el_sello_propio_no_alcanza_para_tapar_el_cambio(self):
        """
        Éste es el punto de encadenar. Quien altera una entrada y recalcula SU
        resumen deja la cadena rota en la siguiente, y eso queda visible contra
        cualquier respaldo.
        """
        a = self._entrada(titulo="Primera", contenido="original")
        self._entrada(titulo="Segunda")

        # El atacante edita y recalcula el sello de la entrada que tocó.
        EntradaHistoria.objects.filter(pk=a.pk).update(contenido="alterado")
        a.refresh_from_db()
        EntradaHistoria.objects.filter(pk=a.pk).update(sello=integridad.calcular(a))

        r = integridad.verificar_historia(self.hc)
        self.assertFalse(r["ok"], "la cadena tendría que haberlo delatado")
        self.assertTrue(any("cadena" in p["motivo"] for p in r["problemas"]))

    def test_borrar_una_entrada_del_medio_rompe_la_cadena(self):
        self._entrada(titulo="Primera")
        b = self._entrada(titulo="Segunda")
        self._entrada(titulo="Tercera")
        EntradaHistoria.objects.filter(pk=b.pk).delete()
        self.assertFalse(integridad.verificar_historia(self.hc)["ok"])


class EntradaInsertadaPorAfueraTests(IntegridadTestCase):
    """
    La otra forma de alterar una historia: no editar, insertar.

    La cadena encarece editar una entrada vieja. Insertar sigue costando una
    fila, y el resultado es el mismo: una atención que nunca ocurrió dentro de un
    expediente que se presenta como intacto.
    """

    def test_una_entrada_firmada_sin_sello_de_hoy_se_denuncia_en_vez_de_saltearse(self):
        """
        `sello` es `editable=False` y el alta sella en la misma transacción: una
        fila firmada y sin sello no la pudo escribir la aplicación. Antes se
        salteaba —ni se contaba como problema ni cortaba la cadena—, así que la
        jefatura abría el panel de INTEGRIDAD y leía en verde «Sin alteraciones»
        sobre una historia con una atención fabricada, con la pantalla que existe
        para probar lo contrario.
        """
        self._entrada(titulo="Primera")
        fabricada = EntradaHistoria.objects.create(
            historia=self.hc, titulo="Se indicó control en 48 hs y pautas de alarma",
            contenido="Paciente en condiciones de alta.", autor=self.med,
            firmada=True, matricula="MP 12345",
        )

        r = integridad.verificar_historia(self.hc)
        self.assertFalse(r["ok"], "la entrada insertada pasó como «anterior al sellado»")
        self.assertIn(fabricada.id, [p["entrada"] for p in r["problemas"]])

    def test_una_entrada_anterior_al_sellado_sigue_quedando_fuera_y_dice_desde_cuando(self):
        """
        La salvedad tiene que seguir existiendo para las historias que venían de
        antes —decir «alterada» de algo que nunca se pudo sellar es una alarma
        falsa que enseña a ignorar las verdaderas—, pero ahora con una fecha y
        una cantidad, para que se pueda comprobar en vez de invocar.
        """
        vieja = EntradaHistoria.objects.create(
            historia=self.hc, titulo="Control 2019", autor=self.med, firmada=True,
        )
        EntradaHistoria.objects.filter(pk=vieja.pk).update(
            fecha=timezone.now() - timedelta(days=900)
        )
        self._entrada(titulo="Atención de hoy")

        r = integridad.verificar_historia(self.hc)
        self.assertTrue(r["ok"], r["problemas"])
        self.assertEqual(r["fuera_de_alcance"], 1)
        self.assertIsNotNone(r["sella_desde"])

    def test_la_verificacion_por_api_tambien_lo_delata(self):
        """Es la pantalla que se presenta ante un reclamo; si ahí sale verde, da igual el resto."""
        self.client.force_authenticate(self.med)
        self._entrada(titulo="Primera")
        EntradaHistoria.objects.create(
            historia=self.hc, titulo="Alta médica", autor=self.med,
            firmada=True, matricula="MP 12345",
        )
        r = self.client.get(f"/api/historias-clinicas/{self.hc.id}/verificar/")
        self.assertFalse(r.data["ok"])
        self.assertTrue(r.data["problemas"])


class DosAlaVezTests(IntegridadTestCase):
    """
    Dos atenciones simultáneas del mismo paciente.

    Guardia y estudio derivado, o el médico y la enfermera registrando a la vez.
    Si las dos se encadenan al mismo eslabón, `verificar_historia` denuncia «la
    cadena se rompió» sobre una historia que nadie tocó, y no hay forma de
    re-sellar desde la aplicación: el falso positivo queda pegado diez años.
    Es el peor error posible acá —la única prueba que el hospital tiene para
    decir que la historia está intacta pasa a acusarlo—.
    """

    def test_sellar_toma_el_candado_de_la_historia(self):
        """
        Sin el candado, las dos transacciones leen la misma entrada previa antes
        de que la otra commitee. Se mira el SQL porque es lo único que distingue
        «se serializa» de «funciona cuando no hay nadie más».
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._entrada(titulo="Primera")
        with CaptureQueriesContext(connection) as ctx:
            self._entrada(titulo="Segunda")
        sql = " ".join(q["sql"].lower() for q in ctx.captured_queries)
        self.assertIn("registros_historiaclinica", sql)
        self.assertIn("for update", sql)

    def test_dos_entradas_no_se_pueden_encadenar_al_mismo_eslabon(self):
        """
        La red de seguridad debajo del candado: si igual llegaran a encadenarse
        dos veces al mismo sello, falla la segunda en el momento —y se reintenta—
        en vez de dejar la historia marcada como alterada para siempre.
        """
        from django.db import IntegrityError, transaction

        a = self._entrada(titulo="Primera")
        self._entrada(titulo="Segunda")

        gemela = EntradaHistoria.objects.create(
            historia=self.hc, titulo="Simultánea", autor=self.med,
            firmada=True, matricula="MP 12345",
        )
        gemela.sello_previo = a.sello  # lo que dejaría la lectura sin candado
        gemela.sello = integridad.calcular(gemela)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                gemela.save(update_fields=["sello", "sello_previo"])

    def test_dos_atenciones_seguidas_dejan_la_historia_sana(self):
        """El candado no puede volverse una traba: la cadena tiene que cerrar."""
        for i in range(5):
            self._entrada(titulo=f"Atención {i}")
        r = integridad.verificar_historia(self.hc)
        self.assertTrue(r["ok"], r["problemas"])


class DesdeElMotorTests(IntegridadTestCase):
    """Firmar una atención desde el flujo tiene que sellar igual."""

    def setUp(self):
        super().setUp()
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.at = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención")
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.at)
        Conexion.objects.create(version=self.ver, origen=self.at, destino=fin)
        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.ver, ciudadano=self.paciente,
            area_actual=self.area,
        )
        motor.iniciar(self.caso, autor=self.med)
        self.caso.refresh_from_db()

    def test_una_atencion_firmada_queda_sellada(self):
        motor.avanzar(self.caso, {
            "titulo": "Consulta", "contenido": "Paciente estable.", "firmada": True,
        }, autor=self.med)
        e = EntradaHistoria.objects.get()
        self.assertTrue(e.sello)
        self.assertTrue(integridad.verificar(e)["ok"])

    def test_una_atencion_sin_firmar_no_se_sella(self):
        motor.avanzar(self.caso, {
            "titulo": "Consulta", "contenido": "Borrador.", "firmada": False,
        }, autor=self.med)
        self.assertEqual(EntradaHistoria.objects.get().sello, "")


class APITests(IntegridadTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.med)

    def test_el_detalle_dice_si_la_entrada_esta_intacta(self):
        e = self._entrada()
        r = self.client.get(f"/api/entradas-historia/{e.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["integra"])
        self.assertTrue(r.data["sello"])

    def test_el_detalle_avisa_cuando_no_lo_esta(self):
        e = self._entrada()
        EntradaHistoria.objects.filter(pk=e.pk).update(contenido="otra cosa")
        self.assertFalse(self.client.get(f"/api/entradas-historia/{e.id}/").data["integra"])

    def test_el_sello_no_se_puede_mandar_desde_afuera(self):
        """Poder mandarlo permitiría sellar contenido alterado."""
        e = self._entrada()
        self.client.patch(f"/api/entradas-historia/{e.id}/", {"sello": "a" * 64})
        e.refresh_from_db()
        self.assertNotEqual(e.sello, "a" * 64)

    def test_se_puede_verificar_la_historia_entera(self):
        """
        Es lo que se presenta ante un reclamo: sin esto, «está firmada» es una
        afirmación que nadie puede comprobar.
        """
        for i in range(3):
            self._entrada(titulo=f"Control {i}")
        r = self.client.get(f"/api/historias-clinicas/{self.hc.id}/verificar/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["ok"])
        self.assertEqual(r.data["firmadas"], 3)

    def test_la_verificacion_delata_una_historia_alterada(self):
        a = self._entrada(titulo="Primera")
        self._entrada(titulo="Segunda")
        EntradaHistoria.objects.filter(pk=a.pk).update(contenido="alterado")
        r = self.client.get(f"/api/historias-clinicas/{self.hc.id}/verificar/")
        self.assertFalse(r.data["ok"])
        self.assertTrue(r.data["problemas"])
