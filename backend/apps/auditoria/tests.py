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

    def test_conducir_en_un_hospital_no_deja_auditar_el_otro(self):
        """
        El portero y el alcance tienen que preguntar lo mismo. Quien es jefe de
        área en un hospital y médico en otro —lo normal en Argentina— entraba
        por el primero y leía entero el registro del segundo: qué pacientes se
        atendieron ahí, con nombre y documento, y qué mira cada colega. Con el
        buscador por documento eso contesta «¿esta persona es paciente de esta
        casa?», que es justo el dato que protege la Ley 25.326.
        """
        otra = Institucion.objects.create(nombre="Otro hospital")
        doble = Usuario.objects.create_user("doble@test.local", "x", nombre="Doble")
        Membresia.objects.create(usuario=doble, institucion=otra, rol="admin", activo=True)
        Membresia.objects.create(usuario=doble, institucion=self.inst, rol="medico", activo=True)

        self.client.force_authenticate(doble)
        r = self.client.get("/api/accesos-clinicos/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data["count"], 0,
            "conduce en el otro hospital: acá es médico y no audita a sus colegas",
        )
        # Y tampoco por el buscador, que es el camino real: se pregunta por un DNI.
        r = self.client.get("/api/accesos-clinicos/?search=30111222")
        self.assertEqual(r.data["count"], 0)

    def test_buscar_al_paciente_por_nombre_y_apellido_lo_encuentra(self):
        """
        Es el gesto del día del reclamo: copiar el nombre que muestra la columna
        «De quién». Sin `ciudadano__nombre` entre los campos de búsqueda, DRF
        exige que cada término matchee algo y «Ana» no matcheaba ninguno: la
        pantalla contestaba «Ningún acceso coincide» sobre accesos que existían,
        y con eso se redacta un descargo que dice que nadie consultó sus datos.
        """
        self.client.force_authenticate(self.jefe)
        for buscado in ("Ana Pérez", "Ana", "Pérez"):
            with self.subTest(buscado=buscado):
                r = self.client.get(f"/api/accesos-clinicos/?search={buscado}")
                self.assertEqual(r.data["count"], 1, f"«{buscado}» no encontró el acceso")

    def test_se_pueden_aislar_los_accesos_de_una_institucion(self):
        """
        Sin el filtro no hay forma de contestar «qué pasó en ESTE hospital», que
        es exactamente lo que se pregunta cuando el reclamo llega de uno solo, y
        cada fila de la lista se lee como si fuera del que figura en pantalla.
        """
        otra = Institucion.objects.create(nombre="Otro hospital")
        ajeno = Ciudadano.objects.create(
            institucion=otra, nombre="Cala", apellido="Díaz", documento="31222333"
        )
        AccesoClinico.objects.create(
            usuario=self.med, ciudadano=ajeno, institucion=otra,
            tipo="detalle", recurso="historiaclinica",
        )
        jefe_de_las_dos = Usuario.objects.create_user("dos@test.local", "x")
        for i in (self.inst, otra):
            Membresia.objects.create(
                usuario=jefe_de_las_dos, institucion=i, rol="admin", activo=True
            )

        self.client.force_authenticate(jefe_de_las_dos)
        self.assertEqual(self.client.get("/api/accesos-clinicos/").data["count"], 2)
        r = self.client.get(f"/api/accesos-clinicos/?institucion={self.inst.id}")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["institucion_nombre"], "Hospital Central")

    def test_de_paciente_contesta_quienes_y_no_solo_cuantas_veces(self):
        """
        La pregunta del art. 14 es «quién», y la respuesta correcta es «tres
        personas, y son estas». Una lista cronológica de 637 eventos en 26
        páginas no se lee en un mostrador, y el número exagera: abrir la historia
        una vez deja más de una fila.
        """
        self.client.get(f"/api/historias-clinicas/{self.hc.id}/")  # segundo acceso del médico
        self.client.force_authenticate(self.jefe)
        self.client.get(f"/api/ciudadanos/{self.paciente.id}/")

        r = self.client.get(f"/api/accesos-clinicos/de-paciente/?ciudadano={self.paciente.id}")
        personas = r.data["personas"]
        self.assertEqual(len(personas), 2, personas)
        self.assertEqual(personas[0]["email"], "med@test.local")
        self.assertEqual(personas[0]["veces"], 2)
        self.assertIsNotNone(personas[0]["primera"])
        self.assertIsNotNone(personas[0]["ultima"])

    def test_un_parametro_basura_no_tumba_el_registro_de_accesos(self):
        """
        El mismo cuidado que ya tenía el lado que ESCRIBE el registro, del lado
        que lo lee. `de-paciente` es con lo que se contesta el art. 14 delante de
        quien lo está preguntando: un link viejo o un `undefined` del frontend lo
        convertían en una pantalla de error, y quien atiende el reclamo no puede
        distinguir «el sistema se rompió» de «nadie miró tu historia».
        """
        self.client.force_authenticate(self.jefe)
        for consulta in (
            "?ciudadano=undefined", "?usuario=Patient%2F12",
            "?desde=ayer", "?hasta=2026-02-31", "?institucion=todas",
        ):
            with self.subTest(consulta=consulta):
                r = self.client.get(f"/api/accesos-clinicos/{consulta}")
                self.assertEqual(r.status_code, 200, r.data)

        r = self.client.get("/api/accesos-clinicos/de-paciente/?ciudadano=undefined")
        self.assertEqual(r.status_code, 400)
        self.assertIn("paciente", r.data["detail"].lower())

    def test_auditor_y_plataforma_tienen_alcance_estatal(self):
        otra = Institucion.objects.create(nombre="Hospital regional")
        ajeno = Ciudadano.objects.create(
            institucion=otra, nombre="Cala", apellido="Diaz", documento="31222333"
        )
        AccesoClinico.objects.create(
            usuario=self.med, ciudadano=ajeno, institucion=otra,
            tipo="detalle", recurso="historiaclinica",
        )
        for rol in (Membresia.Rol.AUDITOR, Membresia.Rol.PLATAFORMA):
            with self.subTest(rol=rol):
                u = self._usuario(f"{rol}@test.local", rol)
                self.client.force_authenticate(u)
                r = self.client.get("/api/accesos-clinicos/")
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(r.data["count"], 2)


class DobleCargoTests(AuditoriaTestCase):
    """
    El empleado con cargo en dos hospitales, que en Argentina es lo normal.

    Es el caso que rompía las dos mitades del módulo a la vez: escribiendo,
    porque el acceso quedaba sin institución y no lo veía ningún admin; y
    leyendo, porque el alcance no miraba el rol.
    """

    def setUp(self):
        super().setUp()
        self.otra = Institucion.objects.create(nombre="Otro hospital")
        self.ajeno = Ciudadano.objects.create(
            institucion=self.otra, nombre="Cala", apellido="Díaz", documento="31222333"
        )
        self.admin_dos = Usuario.objects.create_user("dos@test.local", "x", nombre="Doble")
        for i in (self.inst, self.otra):
            Membresia.objects.create(
                usuario=self.admin_dos, institucion=i, rol="admin", activo=True
            )
        self.client.force_authenticate(self.admin_dos)

    def test_la_exportacion_del_padron_se_atribuye_a_cada_institucion(self):
        """
        El CSV del padrón trae documento, fecha de nacimiento, obra social,
        condiciones y alergias: es el evento más grave que este registro tiene
        que poder mostrar. Atribuido a «ninguna institución» no lo ve ningún
        admin —el alcance filtra por institución y NULL nunca matchea—, así que
        el único que se enteraba era el proveedor del software.
        """
        self.assertEqual(self.client.get("/api/ciudadanos/?formato=csv").status_code, 200)
        filas = AccesoClinico.objects.filter(tipo=AccesoClinico.Tipo.EXPORTACION)
        self.assertFalse(
            filas.filter(institucion__isnull=True).exists(),
            "la exportación quedó sin institución: no la puede ver ningún admin",
        )
        self.assertEqual(
            sorted(filas.values_list("institucion_id", "resultados")),
            sorted([(self.inst.id, 2), (self.otra.id, 1)]),
            "cada institución tiene que ver cuántos de SUS pacientes se llevaron",
        )

    def test_el_admin_de_un_hospital_ve_la_exportacion_que_se_llevo_a_su_gente(self):
        self.client.get("/api/ciudadanos/?formato=csv")
        solo_central = Usuario.objects.create_user("solo@test.local", "x")
        Membresia.objects.create(
            usuario=solo_central, institucion=self.inst, rol="admin", activo=True
        )
        self.client.force_authenticate(solo_central)
        r = self.client.get("/api/accesos-clinicos/?tipo=exportacion")
        self.assertEqual(r.data["count"], 1, "el hospital no ve que se bajaron su padrón")
        self.assertEqual(r.data["results"][0]["resultados"], 2)


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
