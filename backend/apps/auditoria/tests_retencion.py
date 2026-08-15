"""
Retención y consentimiento (Ley 25.326).

Lo que más se cuida acá es lo que NO se borra. Un comando de purga que se lleva
puesta una historia clínica hace que el hospital incumpla la Ley 26.529 mientras
creía estar cumpliendo la 25.326, y ese error no se puede deshacer.
"""
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria import retencion
from apps.auditoria.models import AccesoClinico
from apps.casos.models import ItemFila, Notificacion
from apps.instituciones.models import Area, Institucion
from apps.registros.models import (
    Ciudadano, ConsentimientoDatos, EntradaHistoria, HistoriaClinica,
)


class RetencionTests(TestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user("med@test.local", "x")
        Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol="medico", activo=True
        )
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez"
        )
        self.hc = HistoriaClinica.objects.create(ciudadano=self.paciente)

    def _correr(self, *args):
        salida = StringIO()
        call_command("purgar_datos", *args, stdout=salida)
        return salida.getvalue()

    def _viejo(self, modelo, pk, campo, anios=0, dias=0):
        modelo.objects.filter(pk=pk).update(
            **{campo: timezone.now() - timedelta(days=anios * 365 + dias)}
        )

    # --- Lo que NO se borra ---------------------------------------------------- #

    def test_una_historia_clinica_vieja_no_se_borra(self):
        """
        La obligación de conservarla es del hospital. Borrarla «para cumplir con
        protección de datos» lo haría incumplir la otra ley, y no hay vuelta
        atrás.
        """
        e = EntradaHistoria.objects.create(historia=self.hc, titulo="Consulta", firmada=True)
        self._viejo(EntradaHistoria, e.pk, "fecha", anios=15)
        self._correr("--aplicar")
        self.assertTrue(EntradaHistoria.objects.filter(pk=e.pk).exists())

    def test_el_registro_de_accesos_no_se_borra(self):
        """
        Vive lo mismo que la historia que audita: borrarlo antes dejaría esos
        años sin poder decir quién los miró, que es lo que ese registro existe
        para evitar.
        """
        a = AccesoClinico.objects.create(
            usuario=self.user, ciudadano=self.paciente, tipo="detalle", recurso="historiaclinica"
        )
        self._viejo(AccesoClinico, a.pk, "momento", anios=15)
        self._correr("--aplicar")
        self.assertTrue(AccesoClinico.objects.filter(pk=a.pk).exists())

    def test_lo_protegido_igual_aparece_en_el_informe(self):
        """
        Quien audita necesita ver que la historia clínica ESTÁ contemplada y por
        qué no se toca, no que falte de la lista.
        """
        salida = self._correr()
        self.assertIn("historia clínica", salida)
        self.assertIn("NO SE BORRA", salida)

    # --- Lo que sí ------------------------------------------------------------- #

    def test_una_notificacion_leida_y_vieja_se_borra(self):
        n = Notificacion.objects.create(usuario=self.user, titulo="Aviso", leida=True)
        self._viejo(Notificacion, n.pk, "creada", dias=200)
        self._correr("--aplicar")
        self.assertFalse(Notificacion.objects.filter(pk=n.pk).exists())

    def test_una_notificacion_sin_leer_no_se_borra_aunque_sea_vieja(self):
        """Todavía no cumplió su fin: nadie la vio."""
        n = Notificacion.objects.create(usuario=self.user, titulo="Aviso", leida=False)
        self._viejo(Notificacion, n.pk, "creada", dias=200)
        self._correr("--aplicar")
        self.assertTrue(Notificacion.objects.filter(pk=n.pk).exists())

    def test_una_notificacion_reciente_no_se_borra(self):
        n = Notificacion.objects.create(usuario=self.user, titulo="Aviso", leida=True)
        self._correr("--aplicar")
        self.assertTrue(Notificacion.objects.filter(pk=n.pk).exists())

    # --- En seco --------------------------------------------------------------- #

    def test_por_defecto_no_borra_nada(self):
        """
        Un borrado masivo que se dispara sin que nadie lo haya mirado es peor
        que no purgar: lo segundo se arregla corriendo el comando.
        """
        n = Notificacion.objects.create(usuario=self.user, titulo="Aviso", leida=True)
        self._viejo(Notificacion, n.pk, "creada", dias=200)
        salida = self._correr()
        self.assertTrue(Notificacion.objects.filter(pk=n.pk).exists())
        self.assertIn("no se borró nada", salida.lower())

    def test_un_item_de_fila_atendido_sigue_estando_a_los_ocho_meses(self):
        """
        El renglón de la fila es el ÚNICO registro de cuánto esperó y cuánto
        duró la atención: no hay ningún agregado calculado del que puedan salir
        después, el tablero cuenta en vivo y el histórico se saca exportando
        estos ítems. Con el plazo en 180 días, la primera corrida de
        `purgar_datos --aplicar` se llevaba para siempre la demora del año
        pasado, que es contra la que se reporta, y el comando sólo imprime
        cuántas filas borró.
        """
        item = self._item_de_fila()
        self._viejo(ItemFila, item.pk, "ingreso", dias=240)
        self._correr("--aplicar")
        self.assertTrue(ItemFila.objects.filter(pk=item.pk).exists())

    def test_el_ausentismo_de_la_fila_no_dura_menos_que_el_de_los_turnos(self):
        """
        Quien no se presenta sale de la cola con `atendido=True`, así que la
        regla de los ítems se lleva puesto el ausentismo de la guardia. La regla
        de al lado conserva los turnos cancelados un año «porque el ausentismo
        del período se sigue reportando»: con 180 días las dos se contradecían y
        el mismo hecho vivía la mitad de tiempo según por dónde entró el paciente.
        """
        plazos = {r["regla"]: r["dias"] for r in retencion.informe()}
        self.assertGreaterEqual(plazos["ítems de fila"], plazos["turnos cancelados"])

    def _item_de_fila(self):
        """Un paciente que ya pasó por la cola (atendido: es lo que se purga)."""
        from apps.casos.models import Caso, ItemFila
        from apps.flujos.models import Flujo, Nodo, VersionFlujo
        from apps.instituciones.models import Area

        area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        flujo = Flujo.objects.create(institucion=self.inst, area=area, titulo="Guardia")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ESPERA_FILA, titulo="Espera")
        caso = Caso.objects.create(
            institucion=self.inst, version=version, ciudadano=self.paciente, area_actual=area
        )
        return ItemFila.objects.create(caso=caso, nodo=nodo, atendido=True)

    def test_toda_regla_explica_su_plazo(self):
        """
        Una política de retención sin el porqué de cada plazo no se puede
        defender ante nadie, y a los seis meses nadie recuerda si «90 días»
        salió de la ley o de una reunión.
        """
        for r in retencion.informe():
            with self.subTest(regla=r["regla"]):
                self.assertTrue(r["motivo"].strip(), f"{r['regla']} no dice por qué")
                self.assertGreater(len(r["motivo"]), 30)


class ConsentimientoTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.adm = Usuario.objects.create_user("adm@test.local", "x", nombre="Diego")
        Membresia.objects.create(
            usuario=self.adm, institucion=self.inst, rol="administrativo", activo=True
        )
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="30111222"
        )
        self.client.force_authenticate(self.adm)

    def _otorgar(self, otorgado=True, alcance="Atención"):
        return self.client.post("/api/consentimientos/", {
            "ciudadano": self.paciente.id, "otorgado": otorgado,
            "modo": "escrito", "alcance": alcance,
        })

    def test_se_registra_el_consentimiento(self):
        r = self._otorgar()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["otorgado"])

    def test_queda_registrado_quien_lo_tomo(self):
        """Un consentimiento sin responsable no se puede verificar."""
        self._otorgar()
        self.assertEqual(ConsentimientoDatos.objects.get().tomado_por_id, self.adm.id)

    def test_quien_lo_tomo_no_se_puede_falsear_desde_el_cuerpo(self):
        otro = Usuario.objects.create_user("otro@test.local", "x")
        self.client.post("/api/consentimientos/", {
            "ciudadano": self.paciente.id, "otorgado": True,
            "modo": "verbal", "tomado_por": otro.id,
        })
        self.assertEqual(ConsentimientoDatos.objects.get().tomado_por_id, self.adm.id)

    def test_revocar_es_un_registro_nuevo_y_no_pisa_el_anterior(self):
        """
        Lo que vale ante un reclamo no es el estado de hoy sino qué se consintió
        y cuándo.
        """
        self._otorgar()
        self._otorgar(otorgado=False, alcance="Revoca")
        self.assertEqual(ConsentimientoDatos.objects.count(), 2)
        self.assertTrue(ConsentimientoDatos.objects.filter(otorgado=True).exists())

    def test_el_paciente_muestra_el_estado_actual(self):
        self._otorgar()
        r = self.client.get(f"/api/ciudadanos/{self.paciente.id}/")
        self.assertTrue(r.data["consentimiento"]["otorgado"])
        self.assertEqual(r.data["consentimiento"]["modo"], "escrito")

    def test_tras_revocar_el_estado_lo_refleja(self):
        self._otorgar()
        self._otorgar(otorgado=False)
        r = self.client.get(f"/api/ciudadanos/{self.paciente.id}/")
        self.assertFalse(r.data["consentimiento"]["otorgado"])

    def test_sin_registro_no_es_lo_mismo_que_revocado(self):
        """Confundirlos haría creer que el paciente dijo que no."""
        r = self.client.get(f"/api/ciudadanos/{self.paciente.id}/")
        self.assertIsNone(r.data["consentimiento"])

    def test_un_consentimiento_no_se_edita_ni_se_borra(self):
        """Una revocación es un registro nuevo, no una corrección del anterior."""
        cid = self._otorgar().data["id"]
        self.assertEqual(
            self.client.patch(f"/api/consentimientos/{cid}/", {"otorgado": False}).status_code, 405
        )
        self.assertEqual(self.client.delete(f"/api/consentimientos/{cid}/").status_code, 405)
        self.assertTrue(ConsentimientoDatos.objects.get(pk=cid).otorgado)

    def test_consultar_los_consentimientos_queda_auditado(self):
        """Es dato del paciente: mirarlo deja rastro como el resto."""
        self._otorgar()
        AccesoClinico.objects.all().delete()
        self.client.get(f"/api/consentimientos/?ciudadano={self.paciente.id}")
        self.assertTrue(
            AccesoClinico.objects.filter(ciudadano=self.paciente).exists(),
            "consultar consentimientos no dejó rastro",
        )
