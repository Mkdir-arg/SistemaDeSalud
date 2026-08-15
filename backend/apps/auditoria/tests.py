"""
Auditoría de accesos a datos clínicos (Ley 26.529).

Leer una historia no deja marca en ella: sin este registro, un hospital no puede
contestar «¿quién vio la historia de esta persona?», que es la primera pregunta
cuando alguien denuncia que su información circuló.

Lo que se cuida acá, en orden: que todo acceso clínico deje rastro, que ningún
recurso quede sin auditar por olvido, que el registro no se pueda tocar, y que
registrar nunca impida atender.
"""
from unittest import mock

from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano, EntradaHistoria, HistoriaClinica, Receta

from .models import AccesoClinico


class AuditoriaTestCase(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.med = self._usuario("med@test.local", "medico")
        self.jefe = self._usuario("jefe@test.local", "jefe_area")
        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="30111222"
        )
        self.otro = Ciudadano.objects.create(
            institucion=self.inst, nombre="Beto", apellido="Gómez", documento="30999888"
        )
        self.hc = HistoriaClinica.objects.create(ciudadano=self.paciente)
        self.client.force_authenticate(self.med)

    def _usuario(self, email, rol):
        u = Usuario.objects.create_user(email, "x", nombre=email.split("@")[0])
        Membresia.objects.create(usuario=u, institucion=self.inst, rol=rol, activo=True)
        return u


class RegistroDeAccesoTests(AuditoriaTestCase):
    def test_abrir_la_historia_de_alguien_queda_registrado(self):
        self.client.get(f"/api/historias-clinicas/{self.hc.id}/")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.usuario_id, self.med.id)
        self.assertEqual(a.ciudadano_id, self.paciente.id)
        self.assertEqual(a.tipo, AccesoClinico.Tipo.DETALLE)

    def test_abrir_la_ficha_de_un_paciente_queda_registrado(self):
        self.client.get(f"/api/ciudadanos/{self.paciente.id}/")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.ciudadano_id, self.paciente.id)

    def test_una_receta_se_registra_a_nombre_del_paciente(self):
        """
        La ley pregunta por la PERSONA, no por el objeto: «quién vio mi
        historia», no «quién vio la receta 4812».
        """
        r = Receta.objects.create(historia=self.hc, detalle="Ibuprofeno")
        self.client.get(f"/api/recetas/{r.id}/")
        self.assertEqual(AccesoClinico.objects.get().ciudadano_id, self.paciente.id)

    def test_una_entrada_de_historia_tambien(self):
        e = EntradaHistoria.objects.create(historia=self.hc, titulo="Consulta", contenido="ok")
        self.client.get(f"/api/entradas-historia/{e.id}/")
        self.assertEqual(AccesoClinico.objects.get().ciudadano_id, self.paciente.id)

    def test_un_listado_deja_UNA_linea_y_no_una_por_resultado(self):
        """
        Un padrón de 200 pacientes generaría 200 filas que esconden los accesos
        que sí importan.
        """
        self.client.get("/api/ciudadanos/")
        self.assertEqual(AccesoClinico.objects.count(), 1)
        a = AccesoClinico.objects.get()
        self.assertEqual(a.tipo, AccesoClinico.Tipo.LISTADO)
        self.assertEqual(a.resultados, 2)
        self.assertIsNone(a.ciudadano_id)

    def test_un_listado_filtrado_a_una_persona_se_registra_a_su_nombre(self):
        """
        Si no, buscar por `?ciudadano=X` sería una forma de leer una historia
        sin dejar rastro a nombre de esa persona.
        """
        self.client.get(f"/api/entradas-historia/?historia__ciudadano={self.paciente.id}")
        self.assertEqual(AccesoClinico.objects.get().ciudadano_id, self.paciente.id)

    def test_queda_registrado_con_que_se_busco(self):
        """Distingue «buscó a una persona» de «abrió el padrón entero»."""
        self.client.get("/api/ciudadanos/?search=30111222")
        self.assertIn("search=30111222", AccesoClinico.objects.get().detalle)

    def test_una_exportacion_se_marca_como_tal(self):
        """Llevarse el padrón en un archivo no es lo mismo que mirarlo."""
        self.client.get("/api/ciudadanos/?formato=csv")
        self.assertEqual(AccesoClinico.objects.get().tipo, AccesoClinico.Tipo.EXPORTACION)

    def test_una_exportacion_dice_cuanta_gente_se_llevo(self):
        """
        Sin la cantidad, el registro no distingue la descarga de tres pacientes
        de la del hospital entero, que es la diferencia que importa cuando
        alguien denuncia una filtración. La exportación se transmite fila por
        fila y no tiene `.data`, así que contar sobre la respuesta da 0 siempre.
        """
        self.client.get("/api/ciudadanos/?formato=csv")
        a = AccesoClinico.objects.get()
        self.assertEqual(a.tipo, AccesoClinico.Tipo.EXPORTACION)
        self.assertEqual(a.resultados, 2)

    def test_un_listado_sin_paciente_igual_se_atribuye_a_una_institucion(self):
        """
        Un acceso sin institución no lo puede ver ningún admin de institución
        (el queryset filtra por las suyas). Sin esto, la exportación del padrón
        —el evento más grave del registro— quedaba visible sólo para el
        proveedor del software, y el hospital que responde ante el paciente
        leía «no hubo exportaciones».
        """
        self.client.get("/api/ciudadanos/")
        a = AccesoClinico.objects.get()
        self.assertIsNone(a.ciudadano_id)
        self.assertEqual(a.institucion_id, self.inst.id)

    def test_un_parametro_basura_no_tumba_el_listado_clinico(self):
        """
        La regla de oro del módulo: registrar no puede hacer fallar la lectura.
        Un `?ciudadano=undefined` —un bug del frontend, un link viejo, un
        integrador que manda `Patient/12`— buscaba ese valor como id DESPUÉS de
        que la respuesta ya estaba armada y devolvía 500: el padrón de pacientes
        dejaba de abrir en medio de una guardia por culpa de la auditoría.
        """
        r = self.client.get("/api/ciudadanos/?ciudadano=undefined")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/entradas-historia/?historia__ciudadano=Patient%2F12")
        self.assertEqual(r.status_code, 200)
        # Y la lectura igual queda registrada: el guarda no puede convertirse en
        # una forma silenciosa de leer sin dejar rastro.
        self.assertEqual(AccesoClinico.objects.count(), 2)

    def test_guarda_desde_dónde_se_consultó(self):
        self.client.get(f"/api/historias-clinicas/{self.hc.id}/")
        self.assertIsNotNone(AccesoClinico.objects.get().ip)

    def test_una_lectura_denegada_no_ensucia_el_registro(self):
        """
        Registrar un acceso que no ocurrió haría dudar de todo el registro.
        """
        sin_permiso = Usuario.objects.create_user("nadie@test.local", "x")
        self.client.force_authenticate(sin_permiso)
        r = self.client.get(f"/api/historias-clinicas/{self.hc.id}/")
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(AccesoClinico.objects.count(), 0)


class NoSePuedeTocarTests(AuditoriaTestCase):
    """Un registro de auditoría reescribible es lo primero que alguien tocaría."""

    def setUp(self):
        super().setUp()
        self.client.get(f"/api/historias-clinicas/{self.hc.id}/")
        self.acceso = AccesoClinico.objects.get()
        self.client.force_authenticate(self.jefe)

    def test_no_se_crea_por_la_api(self):
        r = self.client.post("/api/accesos-clinicos/", {
            "usuario": self.med.id, "recurso": "inventado", "tipo": "detalle",
        })
        self.assertEqual(r.status_code, 405)

    def test_guarda_el_nombre_del_modelo_y_no_el_de_la_url(self):
        """Una ruta se puede renombrar; el registro tiene que decir lo mismo dentro de diez años."""
        self.assertEqual(self.acceso.recurso, "historiaclinica")

    def test_no_se_edita(self):
        r = self.client.patch(f"/api/accesos-clinicos/{self.acceso.id}/", {"recurso": "otro"})
        self.assertEqual(r.status_code, 405)
        self.acceso.refresh_from_db()
        self.assertEqual(self.acceso.recurso, "historiaclinica")

    def test_no_se_borra(self):
        r = self.client.delete(f"/api/accesos-clinicos/{self.acceso.id}/")
        self.assertEqual(r.status_code, 405)
        self.assertEqual(AccesoClinico.objects.count(), 1)

    def test_borrar_al_usuario_no_se_lleva_su_rastro(self):
        """El registro tiene que sobrevivir a la baja de quien lo generó."""
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.med.delete()


class QuienLoPuedeVerTests(AuditoriaTestCase):
    def setUp(self):
        super().setUp()
        self.client.get(f"/api/historias-clinicas/{self.hc.id}/")

    def test_un_medico_no_audita_a_sus_colegas(self):
        """
        El registro dice quién miró la historia de quién: es tan sensible como
        lo que audita.
        """
        self.client.force_authenticate(self.med)
        self.assertEqual(self.client.get("/api/accesos-clinicos/").status_code, 403)

    def test_el_jefe_de_area_lo_ve(self):
        self.client.force_authenticate(self.jefe)
        r = self.client.get("/api/accesos-clinicos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)

    def test_cada_institucion_audita_lo_suyo(self):
        otra = Institucion.objects.create(nombre="Otro hospital")
        ajeno = Usuario.objects.create_user("ajeno@test.local", "x")
        Membresia.objects.create(usuario=ajeno, institucion=otra, rol="admin", activo=True)
        self.client.force_authenticate(ajeno)
        self.assertEqual(self.client.get("/api/accesos-clinicos/").data["count"], 0)

    def test_se_puede_pedir_quien_consulto_a_una_persona(self):
        """Es el derecho concreto que da la ley: el paciente puede pedir la lista."""
        self.client.force_authenticate(self.jefe)
        r = self.client.get(f"/api/accesos-clinicos/de-paciente/?ciudadano={self.paciente.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["usuario_email"], "med@test.local")

    def test_de_paciente_sin_paciente_lo_dice(self):
        self.client.force_authenticate(self.jefe)
        self.assertEqual(
            self.client.get("/api/accesos-clinicos/de-paciente/").status_code, 400
        )


class CoberturaTests(AuditoriaTestCase):
    """
    El agujero que este módulo puede tener sin que nadie lo note.
    """

    def test_todo_recurso_clinico_esta_auditado(self):
        """
        Agregar un recurso que expone la historia de alguien SIN auditarlo deja
        un camino por el que se puede leer sin dejar rastro. Los que declaran
        `protege_lectura` son exactamente los recursos clínicos.
        """
        from apps.auditoria.mixins import AuditaLecturaClinica
        from cauce.api import router

        sin_auditar = [
            prefijo for prefijo, viewset, _ in router.registry
            if getattr(viewset, "protege_lectura", False)
            and not issubclass(viewset, AuditaLecturaClinica)
        ]
        self.assertEqual(
            sin_auditar, [],
            "estos recursos exponen datos clínicos y no registran quién los mira: "
            "sumales el mixin AuditaLecturaClinica",
        )

    def test_si_falla_el_registro_la_atencion_no_se_detiene(self):
        """
        Perder una línea de auditoría es malo; que un médico no pueda ver la
        historia del paciente que tiene delante es peor.
        """
        with mock.patch.object(
            AccesoClinico.objects, "create", side_effect=RuntimeError("base caída")
        ):
            r = self.client.get(f"/api/historias-clinicas/{self.hc.id}/")
        self.assertEqual(r.status_code, 200)
