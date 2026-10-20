"""La cadena de sellos se arma por topología, no por hora (#172).

Con fechas retroactivas o relojes desfasados entre réplicas, la entrada de
`firmada_at` más reciente puede no ser la cabeza de la cadena. Encadenarse a
ella violaba `entrada_un_solo_eslabon_siguiente` y la firma fallaba.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion

from . import integridad
from .models import Ciudadano, EntradaHistoria, HistoriaClinica


class CadenaSellosAuditoria172Tests(TestCase):
    def setUp(self):
        inst = Institucion.objects.create(nombre="Hospital sintético de sellos")
        self.autor = Usuario.objects.create_user("sellos@example.test", "x", nombre="Autora")
        self.historia = HistoriaClinica.objects.create(ciudadano=Ciudadano.objects.create(institucion=inst, nombre="P"))

    def firmar(self, titulo, firmada_at):
        entrada = EntradaHistoria.objects.create(
            historia=self.historia, autor=self.autor, titulo=titulo, contenido=titulo,
            firmada=True, matricula="MP sintética", firmada_at=firmada_at,
        )
        return integridad.sellar(entrada)

    def test_se_encadena_a_la_cabeza_aunque_otra_tenga_hora_posterior(self):
        ahora = timezone.now()
        primera = self.firmar("primera", ahora + timedelta(hours=2))   # hora "del futuro"
        segunda = self.firmar("segunda", ahora)                        # encadenada a la primera
        self.assertEqual(segunda.sello_previo, primera.sello)
        tercera = self.firmar("tercera", ahora + timedelta(minutes=1))
        self.assertEqual(tercera.sello_previo, segunda.sello)
        self.assertTrue(integridad.verificar_historia(self.historia)["ok"])

    def rotas(self):
        r = integridad.verificar_historia(self.historia)
        return r["ok"], {p["entrada"] for p in r["problemas"]}

    def test_borrar_una_entrada_del_medio_rompe_la_cadena(self):
        ahora = timezone.now()
        primera, segunda, tercera = (self.firmar(t, ahora + timedelta(minutes=i)) for i, t in enumerate("abc"))
        EntradaHistoria.objects.filter(pk=segunda.pk).delete()
        self.assertEqual(self.rotas(), (False, {tercera.pk}))

    def test_una_segunda_raiz_insertada_se_denuncia(self):
        ahora = timezone.now()
        self.firmar("a", ahora)
        self.firmar("b", ahora + timedelta(minutes=1))
        intrusa = EntradaHistoria.objects.create(
            historia=self.historia, autor=self.autor, titulo="fabricada", contenido="x",
            firmada=True, matricula="MP", firmada_at=ahora - timedelta(days=1),
        )
        # Sellada por fuera como si fuera la primera (sello_previo vacío).
        intrusa.sello_version = integridad.VERSION
        intrusa.sello = integridad.calcular(intrusa)
        EntradaHistoria.objects.filter(pk=intrusa.pk).update(sello=intrusa.sello, sello_version=intrusa.sello_version)
        ok, rotas = self.rotas()
        self.assertFalse(ok)
        self.assertTrue(rotas)

    def test_resellar_una_entrada_del_medio_desengancha_las_siguientes(self):
        ahora = timezone.now()
        primera, segunda, tercera = (self.firmar(t, ahora + timedelta(minutes=i)) for i, t in enumerate("abc"))
        EntradaHistoria.objects.filter(pk=segunda.pk).update(contenido="alterado")
        segunda.refresh_from_db()
        EntradaHistoria.objects.filter(pk=segunda.pk).update(sello=integridad.calcular(segunda))
        ok, rotas = self.rotas()
        self.assertFalse(ok)
        self.assertIn(tercera.pk, rotas)
