"""Alcance y auditoría de la historia clínica del financiador."""
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.auditoria.models import AccesoClinico
from apps.registros.models import ArchivoClinico, EntradaHistoria, Estudio, HistoriaClinica, Receta

from .models import Afiliado, AfiliacionCaso, EventoCobertura, Financiador, MembresiaFinanciador
from .test_vigencias import VigenciasApiSetup


class HistoriaFinanciadorTests(VigenciasApiSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.historia = HistoriaClinica.objects.create(ciudadano=self.paciente, alergias="ALERGIA_SECRETA", condiciones="CONDICION_SECRETA")

    def casos(self, afiliado=None):
        return self.client.get(self.base + "ficha-historia-casos/", {"afiliado": afiliado or self.afiliado.pk})

    def evoluciones(self, caso=None, motivo="Auditoría médica del convenio", afiliado=None):
        return self.client.post(self.base + "ficha-historia-evoluciones/", {
            "afiliado": afiliado or self.afiliado.pk, "caso": caso or self.caso.pk, "motivo": motivo,
        }, format="json")

    def entrada(self, titulo, *, caso=None, firmada=True, historia=None):
        return EntradaHistoria.objects.create(historia=historia or self.historia, caso=self.caso if caso is None else caso or None,
            titulo=titulo, contenido=f"Texto {titulo}", autor=self.admin, firmada=firmada, matricula="MN 123")

    def test_designado_ve_solo_evoluciones_firmadas_y_ambas_auditorias(self):
        visible = self.entrada("EVOLUCION_VISIBLE")
        self.entrada("BORRADOR_SECRETO", firmada=False)
        self.entrada("SIN_CASO_SECRETO", caso=False)
        Estudio.objects.create(historia=self.historia, tipo="ESTUDIO_SECRETO", fecha=self.hoy)
        Receta.objects.create(historia=self.historia, detalle="RECETA_SECRETA")
        ArchivoClinico.objects.create(institucion=self.institucion, ruta="test/secreto", nombre_original="ARCHIVO_SECRETO",
            content_type="text/plain", tamano=1, sha256="0" * 64)
        otro, _ = self.otro_hospital()
        otra_historia = HistoriaClinica.objects.create(ciudadano=otro.ciudadano)
        self.entrada("OTRO_CASO_SECRETO", caso=otro, historia=otra_historia)
        listado = self.casos()
        self.assertEqual(listado.status_code, 200, listado.data)
        self.assertEqual(listado["Cache-Control"], "private, no-store")
        self.assertEqual({fila["id"] for fila in listado.data["results"]}, {self.caso.pk, otro.pk})
        self.assertEqual(next(fila for fila in listado.data["results"] if fila["id"] == self.caso.pk)["evoluciones_firmadas"], 1)
        acceso_casos = AccesoClinico.objects.filter(recurso="financiadores-historia-casos")
        self.assertEqual(set(acceso_casos.values_list("objeto_id", "institucion_id")),
                         {(str(self.caso.pk), self.institucion.pk), (str(otro.pk), otro.institucion_id)})
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_historia_clinica_casos").exists())
        response = self.evoluciones()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([fila["id"] for fila in response.data], [visible.pk])
        self.assertEqual(response.data[0]["matricula"], "MN 123")
        contenido = str(response.data) + str(listado.data)
        for secreto in ("BORRADOR_SECRETO", "SIN_CASO_SECRETO", "OTRO_CASO_SECRETO", "ALERGIA_SECRETA", "CONDICION_SECRETA", "ESTUDIO_SECRETO", "RECETA_SECRETA", "ARCHIVO_SECRETO"):
            self.assertNotIn(secreto, contenido)
        acceso = AccesoClinico.objects.get(recurso="financiadores-evoluciones-caso")
        self.assertEqual((acceso.institucion_id, acceso.objeto_id), (self.institucion.pk, str(self.caso.pk)))
        self.assertIn("motivo=Auditoría médica del convenio", acceso.detalle)
        self.assertIn(f"entradas={visible.pk}", acceso.detalle)
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_historia_clinica", motivo="Auditoría médica del convenio").exists())

    def test_permisos_y_motivo_no_dejan_acceso(self):
        self.membresia.rol = "operador"
        self.membresia.resuelve_autorizaciones = False
        self.membresia.save(update_fields=["rol", "resuelve_autorizaciones"])
        for llamada in (self.casos, self.evoluciones):
            self.assertEqual(llamada().status_code, 403)
        self.membresia.rol = "auditor"
        self.membresia.save(update_fields=["rol"])
        self.assertEqual(self.casos().status_code, 403)
        self.assertEqual(self.evoluciones().status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.casos().status_code, 403)
        self.assertEqual(self.evoluciones().status_code, 403)
        MembresiaFinanciador.objects.create(financiador=self.financiador, usuario=self.admin,
                                            rol="admin", resuelve_autorizaciones=True)
        self.assertEqual(self.casos().status_code, 403)
        self.assertEqual(self.evoluciones().status_code, 403)
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.casos().status_code, 404)
        self.assertEqual(self.evoluciones().status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())
        self.client.force_authenticate(self.operador)
        self.membresia.rol = "operador"
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["rol", "resuelve_autorizaciones"])
        for motivo in ("", "  corto  "):
            self.assertEqual(self.evoluciones(motivo=motivo).status_code, 400)
        self.assertFalse(AccesoClinico.objects.exists())

    def test_admin_del_financiador_consulta_sin_designacion(self):
        # #93 R6: el admin de la organización ve la historia aunque no resuelva autorizaciones.
        self.membresia.rol = "admin"
        self.membresia.resuelve_autorizaciones = False
        self.membresia.save(update_fields=["rol", "resuelve_autorizaciones"])
        self.entrada("EVOLUCION_ADMIN")
        organizacion = next(o for o in self.client.get("/api/financiadores/").data["results"] if o["id"] == self.financiador.pk)
        self.assertTrue(organizacion["consulta_historia_clinica"])
        self.assertFalse(organizacion["resuelve_autorizaciones"])
        self.assertEqual(self.casos().status_code, 200)
        response = self.evoluciones()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([fila["titulo"] for fila in response.data], ["EVOLUCION_ADMIN"])
        self.assertTrue(AccesoClinico.objects.filter(recurso="financiadores-evoluciones-caso", usuario=self.operador).exists())
        self.membresia.rol = "operador"
        self.membresia.save(update_fields=["rol"])
        organizacion = next(o for o in self.client.get("/api/financiadores/").data["results"] if o["id"] == self.financiador.pk)
        self.assertFalse(organizacion["consulta_historia_clinica"])
        self.assertEqual(self.casos().status_code, 403)

    def test_correccion_particular_y_convenio_cerrado_recortan_casos(self):
        otro = Financiador.objects.create(nombre="Otro", tipo="mutual")
        ajeno = Afiliado.objects.create(financiador=otro, numero="2", documento="22222222", nombre="Ajeno", desde=self.hoy)
        self.assertEqual(self.casos(afiliado=ajeno.pk).status_code, 404)
        self.assertEqual(self.evoluciones(afiliado=ajeno.pk).status_code, 404)
        self.cerrar()
        self.assertEqual(self.casos().data["results"], [])
        self.assertEqual(self.evoluciones().status_code, 404)
        self.assertFalse(AccesoClinico.objects.exists())
        # Reabrir el convenio sólo para aislar la selección actual del caso.
        self.convenio.estado = "activo"
        self.convenio.cerrado_en = None
        self.convenio.save(update_fields=["estado", "cerrado_en"])
        AfiliacionCaso.objects.create(caso=self.caso, estado="particular", motivo="Corrección", registrado_por=self.admin)
        self.assertEqual(self.casos().data["results"], [])
        self.assertEqual(self.evoluciones().status_code, 404)
        self.assertTrue(EventoCobertura.objects.filter(accion="consultar_historia_clinica_casos").exists())
        self.assertFalse(AccesoClinico.objects.exists())

    def test_reserva_historica_pendiente_habilita_solo_su_caso(self):
        self.reservar()
        self.cerrar()
        response = self.casos()
        self.assertEqual([fila["id"] for fila in response.data["results"]], [self.caso.pk])
        self.assertEqual(response.data["results"][0]["acceso"], "pendiente_historico")

    def test_sin_convenio_o_correccion_a_otro_financiador_no_expone_caso(self):
        otro_caso, _ = self.otro_hospital()
        convenio_vecino = type(self.convenio).objects.get(financiador=self.financiador, institucion=otro_caso.institucion)
        convenio_vecino.estado = "finalizado"
        convenio_vecino.cerrado_en = timezone.now()
        convenio_vecino.save(update_fields=["estado", "cerrado_en"])
        self.assertNotIn(otro_caso.pk, [fila["id"] for fila in self.casos().data["results"]])
        self.assertEqual(self.evoluciones(caso=otro_caso.pk).status_code, 404)
        otro = Financiador.objects.create(nombre="Cobertura corregida", tipo="mutual")
        ajeno = Afiliado.objects.create(financiador=otro, numero="33", documento=self.afiliado.documento,
                                       nombre=self.afiliado.nombre, desde=self.hoy)
        AfiliacionCaso.objects.create(caso=self.caso, afiliado=ajeno, estado="verificada",
                                      motivo="Corrección a otra cobertura", registrado_por=self.admin)
        self.assertEqual(self.casos().data["results"], [])
        self.assertEqual(self.evoluciones().status_code, 404)

    def test_motivo_largo_parte_ids_sin_truncarlos(self):
        entradas = [self.entrada(f"Evolución {i}") for i in range(60)]
        response = self.evoluciones(motivo="M" * 200)
        self.assertEqual(response.status_code, 200, response.data)
        accesos = list(AccesoClinico.objects.filter(recurso="financiadores-evoluciones-caso"))
        self.assertGreater(len(accesos), 1)
        self.assertTrue(all(len(acceso.detalle) <= 300 and acceso.detalle.startswith("motivo=" + "M" * 200) for acceso in accesos))
        ids = {int(valor) for acceso in accesos for valor in acceso.detalle.split("entradas=")[1].split(",") if valor}
        self.assertEqual(ids, {entrada.pk for entrada in entradas})

    @override_settings(DEBUG=False)
    def test_fallo_auditoria_no_entrega_contenido_ni_evento(self):
        self.entrada("EVOLUCION_SECRETA")
        self.client.raise_request_exception = False
        with patch("apps.financiadores.views.registrar_accesos", side_effect=RuntimeError("Auditoría no disponible")):
            response = self.evoluciones()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"EVOLUCION_SECRETA", response.content)
        self.assertFalse(EventoCobertura.objects.filter(accion="consultar_historia_clinica").exists())
