"""El traslado comparte identidad, nunca compromisos de otro hospital."""
from django.test import TestCase
from django.utils import timezone

from apps.financiadores.administrativa import resumenes_administrativos
from apps.financiadores.models import Afiliado, AfiliacionCaso, ConfiguracionHospital, Convenio, Financiador, ReservaCobertura
from apps.registros.models import Ciudadano
from . import motor
from .tests import RedTestCase


class IdentidadTrasladoTests(TestCase):
    def setUp(self):
        from apps.instituciones.models import Institucion
        self.origen = Institucion.objects.create(nombre="Origen")
        self.destino = Institucion.objects.create(nombre="Destino")

    def test_documento_normalizado_preserva_ceros_y_reusa_destino_sin_pisar_declaracion(self):
        origen = Ciudadano.objects.create(institucion=self.origen, documento="00.111.222", obra_social="Anterior")
        destino = Ciudadano.objects.create(institucion=self.destino, documento="00111222", obra_social="Declaración propia")
        self.assertEqual(motor._paciente_en(self.destino, origen).pk, destino.pk)
        destino.refresh_from_db()
        self.assertEqual(destino.obra_social, "Declaración propia")

    def test_nn_no_fusiona_personas_en_destino(self):
        origen = Ciudadano.objects.create(institucion=self.origen, documento="NN", nombre="Sin identificar")
        a = motor._paciente_en(self.destino, origen)
        b = motor._paciente_en(self.destino, origen)
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(a.documento, "")

    def test_documentos_legados_conflictivos_requieren_revision_sin_fusionar(self):
        origen = Ciudadano.objects.create(institucion=self.origen, documento="00.111.222")
        Ciudadano.objects.filter(pk=origen.pk).update(documento="00.111.222")
        origen.refresh_from_db()
        antiguo = Ciudadano.objects.create(institucion=self.destino, documento="LEGADO")
        Ciudadano.objects.filter(pk=antiguo.pk).update(documento="00.111.222")
        Ciudadano.objects.create(institucion=self.destino, documento="00111222")
        with self.assertRaises(motor.ErrorTraslado):
            motor._paciente_en(self.destino, origen)
        self.assertEqual(Ciudadano.objects.filter(institucion=self.destino).count(), 2)


class CoberturaTrasladoTests(RedTestCase):
    def test_caso_destino_reconsulta_convenio_y_no_hereda_seleccion_ni_reservas(self):
        self.paciente = self.caso.ciudadano
        self.paciente.documento = "00111222"
        self.paciente.obra_social = "Declarada antes del traslado"
        self.paciente.save()
        financiador = Financiador.objects.create(nombre="Mutual", tipo="mutual")
        afiliado = Afiliado.objects.create(financiador=financiador, documento="00111222", numero="0007", nombre="Paciente", desde=timezone.localdate())
        AfiliacionCaso.objects.create(caso=self.caso, afiliado=afiliado, estado="verificada", motivo="Ingreso", registrado_por=self.med)
        ConfiguracionHospital.objects.create(institucion=self.centro, activo=True)
        traslado = motor.aceptar(self._solicitar(), autor=self.med, area_destino=self.uti)
        destino = traslado.ciudadano_destino
        resumen = resumenes_administrativos([destino])[destino.pk]
        self.assertEqual(resumen["estado"], "sin_padron")
        self.assertEqual(resumen["declaracion_legada"], self.paciente.obra_social)
        self.assertFalse(AfiliacionCaso.objects.filter(caso=traslado.caso_destino).exists())
        self.assertFalse(ReservaCobertura.objects.filter(caso=traslado.caso_destino).exists())
        Convenio.objects.create(financiador=financiador, institucion=self.centro, estado="activo", creado_por=self.med)
        self.assertEqual(resumenes_administrativos([destino])[destino.pk]["afiliaciones"][0]["id"], afiliado.pk)
        with self.assertRaises(motor.ErrorTraslado):
            motor.aceptar(traslado, autor=self.med, area_destino=self.uti)
        self.assertEqual(traslado.caso_destino.ciudadano_id, destino.pk)
