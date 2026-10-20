"""AUD-043/045: formatos sin ambigüedad y una transición por suspensión."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone as tz
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import SimpleTestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.instituciones.models import Institucion
from . import integridad
from .models import Ciudadano, EntradaHistoria, HistoriaClinica, Receta
from .views import RecetaViewSet


class FormatoCanonicoAuditoria172Tests(SimpleTestCase):
    def entrada(self, **cambios):
        datos = dict(sello_version="", historia_id=17,
                     historia=SimpleNamespace(ciudadano_id=23), titulo="Consulta",
                     contenido="Síntoma\nUnicode 🩺", autor_id=31, matricula="MP 42",
                     fecha=datetime(2026, 10, 15, 12, 0, tzinfo=tz.utc),
                     sello_previo="", firmada=True, sello="")
        datos.update(cambios)
        return SimpleNamespace(**datos)

    def test_control_no_permite_trasladar_frontera_entre_campos_nuevos(self):
        a = self.entrada(titulo="A\x1fB", contenido="C")
        b = self.entrada(titulo="A", contenido="B\x1fC")
        self.assertNotEqual(integridad._canonico(a), integridad._canonico(b))
        self.assertNotEqual(integridad.calcular(a), integridad.calcular(b))

    def test_nuevas_firmas_declaran_formato_v2(self):
        self.assertEqual(integridad.VERSION, "salud-sha256-v2")

    def test_bytes_legacy_conservados_y_limite_explicito(self):
        for version in ("salud-sha256-v1", "cauce-sha256-v1"):
            with self.subTest(version=version):
                e = self.entrada(sello_version=version)
                legado = "\x1f".join([version, "17", "23", "Consulta", "Síntoma\nUnicode 🩺",
                                      "31", "MP 42", "2026-10-15T12:00:00+00:00", ""])
                self.assertEqual(integridad._canonico(e), legado)
                e.sello = hashlib.sha256(legado.encode("utf-8")).hexdigest()
                resultado = integridad.verificar(e)
                self.assertIs(resultado["ok"], True)
                self.assertIn("legado", resultado["motivo"].lower())
                self.assertEqual(e.sello_version, version)

    def test_version_desconocida_no_se_declara_intacta(self):
        e = self.entrada(sello_version="formato-no-soportado", sello="a" * 64)
        resultado = integridad.verificar(e)
        self.assertIs(resultado["ok"], False)
        self.assertIn("versión", resultado["motivo"].lower())

    def test_unicode_controles_y_fecha_mismo_instante(self):
        e = self.entrada(contenido="\x00\x1f\n\t\"\\ñ🩺")
        original = integridad.calcular(e)
        self.assertEqual(json.loads(integridad._canonico(e))[4], e.contenido)
        self.assertNotEqual(original, integridad.calcular(self.entrada(contenido="\x00\x1f\n\t\"\\n🩺")))
        self.assertEqual(original, integridad.calcular(self.entrada(contenido=e.contenido,
                         fecha=datetime.fromisoformat("2026-10-15T09:00:00-03:00"))))


@skipUnless(connection.vendor == "postgresql", "Reservas clínicas requieren PostgreSQL real")
class SuspensionConcurrenteAuditoria172Tests(TransactionTestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Clínica sintética suspensión")
        self.usuario = Usuario.objects.create_user("suspension-sintetica@example.test", "x")
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="medico")
        LegajoProfesional.objects.create(usuario=self.usuario, matricula="MP sintética 172")
        ciudadano = Ciudadano.objects.create(institucion=self.institucion, nombre="Paciente sintético")
        self.historia = HistoriaClinica.objects.create(ciudadano=ciudadano)
        self.receta = Receta.objects.create(historia=self.historia, detalle="Tratamiento sintético", autor=self.usuario)

    def cliente(self):
        cliente = APIClient()
        cliente.force_authenticate(Usuario.objects.get(pk=self.usuario.pk))
        return cliente

    def test_api_expone_version_del_sello_sin_permitir_elegirla(self):
        cliente = self.cliente()
        respuesta = cliente.post("/api/entradas-historia/", {
            "historia": self.historia.pk, "titulo": "Entrada sintética",
            "contenido": "Texto sintético", "firmada": True,
            "sello_version": "cauce-sha256-v1",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        url = f"/api/entradas-historia/{respuesta.data['id']}/"
        leida = cliente.get(url)
        self.assertEqual(leida.status_code, 200, leida.data)
        self.assertEqual(leida.data["sello_version"], "salud-sha256-v2")
        borrador = cliente.post("/api/entradas-historia/", {
            "historia": self.historia.pk, "titulo": "Borrador sintético",
            "contenido": "Texto sintético", "firmada": False,
            "sello_version": "salud-sha256-v2",
        }, format="json")
        self.assertEqual(borrador.status_code, 201, borrador.data)
        self.assertEqual(borrador.data["sello_version"], "")
        editada = cliente.patch(f"/api/entradas-historia/{borrador.data['id']}/", {
            "titulo": "Borrador corregido", "sello_version": "cauce-sha256-v1",
            "revision_esperada": borrador.data["revision"],
        }, format="json")
        self.assertEqual(editada.status_code, 200, editada.data)
        self.assertEqual(editada.data["sello_version"], "")

    def test_dos_suspensiones_concurrentes_solo_una_transicion_y_motivo(self):
        for motivos in (("Mismo motivo", "Mismo motivo"), ("Primer motivo", "Segundo motivo")):
            with self.subTest(motivos=motivos):
                self.receta.activa = True
                self.receta.save(update_fields=["activa"])
                EntradaHistoria.objects.all().delete()
                ambos_leidos = Barrier(2)
                original = RecetaViewSet.get_object

                def leer(view):
                    receta = original(view)
                    ambos_leidos.wait(timeout=10)
                    return receta

                def solicitar(motivo):
                    connections.close_all()
                    try:
                        r = self.cliente().post(f"/api/recetas/{self.receta.pk}/suspender/", {"motivo": motivo})
                        return r.status_code, motivo
                    finally:
                        connections.close_all()

                with patch.object(RecetaViewSet, "get_object", leer):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futuros = [pool.submit(solicitar, motivo) for motivo in motivos]
                        resultados = [f.result(timeout=25) for f in futuros]
                self.assertEqual(sorted(codigo for codigo, _ in resultados), [200, 400])
                self.receta.refresh_from_db()
                self.assertFalse(self.receta.activa)
                entradas = list(EntradaHistoria.objects.filter(historia=self.historia))
                self.assertEqual(len(entradas), 1)
                ganadora = next(m for codigo, m in resultados if codigo == 200)
                self.assertEqual(entradas[0].contenido, f"Tratamiento sintético\nMotivo: {ganadora}")
                self.assertTrue(integridad.verificar(entradas[0])["ok"])

    def test_fallo_sellado_revierte_estado_y_asiento(self):
        with patch.object(integridad, "sellar", side_effect=RuntimeError("Fallo sintético")):
            with self.assertRaises(RuntimeError):
                self.cliente().post(f"/api/recetas/{self.receta.pk}/suspender/", {"motivo": "Motivo sintético"})
        self.receta.refresh_from_db()
        self.assertTrue(self.receta.activa)
        self.assertFalse(EntradaHistoria.objects.filter(historia=self.historia).exists())

    def test_repeticion_no_sobrescribe_motivo_ni_sello(self):
        cliente = self.cliente()
        url = f"/api/recetas/{self.receta.pk}/suspender/"
        self.assertEqual(cliente.post(url, {"motivo": "Motivo inicial"}).status_code, 200)
        entrada = EntradaHistoria.objects.get(historia=self.historia)
        antes = (entrada.contenido, entrada.sello, entrada.sello_previo, entrada.sello_version)
        self.assertEqual(cliente.post(url, {"motivo": "Motivo diferente"}).status_code, 400)
        entrada.refresh_from_db()
        self.assertEqual(EntradaHistoria.objects.filter(historia=self.historia).count(), 1)
        self.assertEqual((entrada.contenido, entrada.sello, entrada.sello_previo, entrada.sello_version), antes)

    def test_desaparicion_tras_lectura_responde_404_sin_asiento(self):
        original = RecetaViewSet.get_object
        for borrar_historia in (False, True):
            with self.subTest(borrar_historia=borrar_historia):
                historia = HistoriaClinica.objects.create(ciudadano=Ciudadano.objects.create(
                    institucion=self.institucion, nombre="Paciente desaparición sintético"))
                receta = Receta.objects.create(historia=historia, detalle="Tratamiento", autor=self.usuario)

                def leer_y_borrar(view):
                    cargada = original(view)
                    if borrar_historia:
                        HistoriaClinica.objects.filter(pk=historia.pk).delete()
                    else:
                        Receta.objects.filter(pk=receta.pk).delete()
                    return cargada

                with patch.object(RecetaViewSet, "get_object", leer_y_borrar):
                    respuesta = self.cliente().post(f"/api/recetas/{receta.pk}/suspender/", {"motivo": "Motivo"})
                self.assertEqual(respuesta.status_code, 404)
                self.assertFalse(EntradaHistoria.objects.filter(historia_id=historia.pk).exists())
