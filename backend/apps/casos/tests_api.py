"""Tests de la capa API: scope por institución y acciones del motor."""
import hashlib
import shutil
import tempfile

from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.formularios.models import Campo, Formulario
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Box, Grupo, Institucion
from apps.registros.models import ArchivoClinico, Ciudadano
from apps.casos import motor
from apps.casos.models import Caso, EventoCaso, ItemFila, ValorCampo


class ScopeInstitucionTest(APITestCase):
    def setUp(self):
        self.inst_a = Institucion.objects.create(nombre="Hospital A")
        self.inst_b = Institucion.objects.create(nombre="Hospital B")

        def flujo_con_caso(inst):
            f = Flujo.objects.create(institucion=inst, titulo=f"Flujo {inst.nombre}")
            v = VersionFlujo.objects.create(flujo=f, numero=1)
            return Caso.objects.create(institucion=inst, version=v)

        self.caso_a = flujo_con_caso(self.inst_a)
        self.caso_b = flujo_con_caso(self.inst_b)

        # Usuario con membresía solo en A.
        self.user = Usuario.objects.create_user("u@a.com", "x", nombre="U")
        Membresia.objects.create(usuario=self.user, institucion=self.inst_a, rol=Membresia.Rol.ADMINISTRATIVO)

        self.admin = Usuario.objects.create_superuser("admin@x.com", "x", nombre="Admin")

    def test_usuario_solo_ve_su_institucion(self):
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/casos/")
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(self.caso_a.id, ids)
        self.assertNotIn(self.caso_b.id, ids, "no debe ver casos de otra institución")

    def test_usuario_no_accede_a_caso_de_otra_institucion(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(f"/api/casos/{self.caso_b.id}/")
        self.assertEqual(r.status_code, 404)

    def test_superadmin_ve_todo(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/casos/")
        ids = {c["id"] for c in r.data["results"]}
        self.assertIn(self.caso_a.id, ids)
        self.assertIn(self.caso_b.id, ids)

    def test_instituciones_filtradas(self):
        self.client.force_authenticate(self.user)
        r = self.client.get("/api/instituciones/")
        nombres = {i["nombre"] for i in r.data["results"]}
        self.assertEqual(nombres, {"Hospital A"})


class PuestosConMembresiaActivaTests(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user("medico-puesto@test.local", "x", nombre="Medico")
        self.membresia = Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol=Membresia.Rol.MEDICO, activo=True
        )
        self.membresia.areas.add(self.area)
        self.grupo = Grupo.objects.create(area=self.area, nombre="Medicos de guardia")
        self.grupo.miembros.add(self.user)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.version = VersionFlujo.objects.create(
            flujo=self.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        inicio = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.paso = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.ATENCION, titulo="Atencion")
        fin = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=self.version, origen=inicio, destino=self.paso)
        Conexion.objects.create(version=self.version, origen=self.paso, destino=fin)
        self.paso.grupos.add(self.grupo)
        ciudadano = Ciudadano.objects.create(institucion=self.inst, nombre="Ana", apellido="Perez")
        self.caso = Caso.objects.create(
            institucion=self.inst,
            version=self.version,
            ciudadano=ciudadano,
            nodo_actual=self.paso,
            area_actual=self.area,
        )
        self.client.force_authenticate(self.user)

    def test_mis_tareas_no_usa_grupo_con_membresia_inactiva(self):
        activo = self.client.get(f"/api/mis-tareas/?institucion={self.inst.id}")
        self.assertEqual(activo.status_code, 200, activo.data)
        self.assertEqual(len(activo.data["puestos"]), 1)
        self.assertEqual(len(activo.data["tareas"]), 1)

        self.membresia.activo = False
        self.membresia.save(update_fields=["activo"])

        baja = self.client.get(f"/api/mis-tareas/?institucion={self.inst.id}")
        self.assertEqual(baja.status_code, 200, baja.data)
        self.assertEqual(baja.data, {"iniciar": [], "tareas": [], "filas": [], "esperando": []})

    def test_puesto_detalle_requiere_membresia_activa(self):
        activo = self.client.get(f"/api/puestos/{self.paso.id}/")
        self.assertEqual(activo.status_code, 200, activo.data)

        self.membresia.activo = False
        self.membresia.save(update_fields=["activo"])

        baja = self.client.get(f"/api/puestos/{self.paso.id}/")
        self.assertEqual(baja.status_code, 403, baja.data)


class MutacionesDirectasCasoTests(APITestCase):
    """
    Los casos se crean por API, pero su ejecucion se modifica por acciones del
    motor. Estos tests cierran los endpoints genericos que saltean trazabilidad.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.otra = Institucion.objects.create(nombre="Hospital Norte")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.version = VersionFlujo.objects.create(
            flujo=self.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        self.inicio = Nodo.objects.create(version=self.version, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ciudadano = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Perez", documento="30111222"
        )
        self.user = Usuario.objects.create_user("adm@test.local", "x", nombre="Ada")
        Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol=Membresia.Rol.ADMINISTRATIVO, activo=True
        )
        self.client.force_authenticate(self.user)

    def _caso(self):
        return Caso.objects.create(institucion=self.inst, version=self.version, ciudadano=self.ciudadano)

    def test_alta_de_caso_ignora_estado_y_posicion_operativa(self):
        r = self.client.post("/api/casos/", {
            "institucion": self.inst.id,
            "version": self.version.id,
            "ciudadano": self.ciudadano.id,
            "prioridad": Caso.Prioridad.ALTA,
            "estado": Caso.Estado.CERRADO,
            "nodo_actual": self.inicio.id,
            "asignado_a": self.user.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        caso = Caso.objects.get(pk=r.data["id"])
        self.assertEqual(caso.estado, Caso.Estado.RECIBIDO)
        self.assertEqual(caso.prioridad, Caso.Prioridad.ALTA)
        self.assertIsNone(caso.nodo_actual_id)
        self.assertIsNone(caso.asignado_a_id)

    def test_no_se_puede_parchar_un_caso_por_api_generica(self):
        caso = self._caso()
        r = self.client.patch(f"/api/casos/{caso.id}/", {
            "estado": Caso.Estado.CERRADO,
            "nodo_actual": self.inicio.id,
        })
        self.assertEqual(r.status_code, 405)
        caso.refresh_from_db()
        self.assertEqual(caso.estado, Caso.Estado.RECIBIDO)
        self.assertIsNone(caso.nodo_actual_id)

    def test_no_se_puede_crear_caso_sobre_version_no_publicada(self):
        borrador = VersionFlujo.objects.create(flujo=self.flujo, numero=2)
        r = self.client.post("/api/casos/", {
            "institucion": self.inst.id,
            "version": borrador.id,
            "ciudadano": self.ciudadano.id,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("version", r.data)

    def test_no_se_puede_mezclar_institucion_con_version_o_paciente_ajenos(self):
        otro_flujo = Flujo.objects.create(institucion=self.otra, titulo="Otro")
        otra_version = VersionFlujo.objects.create(
            flujo=otro_flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        otro_ciudadano = Ciudadano.objects.create(institucion=self.otra, nombre="Luis", apellido="Diaz")

        r = self.client.post("/api/casos/", {
            "institucion": self.inst.id,
            "version": otra_version.id,
            "ciudadano": self.ciudadano.id,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("version", r.data)

        r = self.client.post("/api/casos/", {
            "institucion": self.inst.id,
            "version": self.version.id,
            "ciudadano": otro_ciudadano.id,
        })
        self.assertEqual(r.status_code, 400)
        self.assertIn("ciudadano", r.data)

    def test_valores_de_campo_son_solo_lectura_en_api(self):
        form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        campo = Campo.objects.create(formulario=form, label="Temperatura", tipo=Campo.Tipo.NUMERO)
        caso = self._caso()
        valor = ValorCampo.objects.create(caso=caso, campo=campo, nodo=self.inicio, valor="36.5")

        r = self.client.post("/api/valores-campo/", {
            "caso": caso.id,
            "campo": campo.id,
            "nodo": self.inicio.id,
            "valor": "39",
        })
        self.assertEqual(r.status_code, 405)

        r = self.client.patch(f"/api/valores-campo/{valor.id}/", {"valor": "39"})
        self.assertEqual(r.status_code, 405)
        valor.refresh_from_db()
        self.assertEqual(valor.valor, "36.5")

    def test_eventos_de_caso_son_solo_lectura_en_api(self):
        caso = self._caso()
        evento = EventoCaso.objects.create(caso=caso, titulo="Creado", detalle="x", nodo=self.inicio)

        r = self.client.post("/api/eventos-caso/", {
            "caso": caso.id,
            "titulo": "Falso cierre",
            "detalle": "sin motor",
        })
        self.assertEqual(r.status_code, 405)

        r = self.client.patch(f"/api/eventos-caso/{evento.id}/", {"titulo": "Editado"})
        self.assertEqual(r.status_code, 405)
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Creado")

    def test_items_de_fila_no_se_crean_por_endpoint_generico(self):
        caso = self._caso()
        r = self.client.post("/api/items-fila/", {
            "caso": caso.id,
            "nodo": self.inicio.id,
            "orden": 99,
        })
        self.assertEqual(r.status_code, 405)
        self.assertFalse(ItemFila.objects.filter(caso=caso).exists())

    def test_motor_no_guarda_campos_ajenos_al_formulario_del_paso(self):
        form = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        campo = Campo.objects.create(formulario=form, label="Temperatura", tipo=Campo.Tipo.NUMERO)
        otro_form = Formulario.objects.create(institucion=self.inst, titulo="Laboratorio")
        campo_ajeno = Campo.objects.create(formulario=otro_form, label="Hemoglobina", tipo=Campo.Tipo.NUMERO)
        nodo = Nodo.objects.create(
            version=self.version, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage", formulario=form
        )
        caso = self._caso()
        caso.nodo_actual = nodo
        caso.save(update_fields=["nodo_actual"])

        r = self.client.post(
            f"/api/casos/{caso.id}/avanzar/",
            {"valores": {str(campo_ajeno.id): "12"}},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("formulario de este paso", r.data["detail"])

        self.assertFalse(ValorCampo.objects.filter(caso=caso, campo=campo_ajeno).exists())
        r = self.client.post(
            f"/api/casos/{caso.id}/avanzar/",
            {"valores": {str(campo.id): "36.5"}},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ValorCampo.objects.get(caso=caso, campo=campo).valor, "36.5")


class ListadoTest(APITestCase):
    """Paginación, orden y búsqueda: lo que necesita la tabla del frontend.

    Se testea porque es contrato con la UI, no adorno: la tabla pagina contra
    `count`, ordena por `?ordering=` y elige el tamaño con `?page_size=`. Si
    alguno deja de funcionar, la pantalla miente en silencio (mostraría los
    primeros 25 y nadie se enteraría).
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital A")
        self.flujo = Flujo.objects.create(institucion=self.inst, titulo="Ingreso")
        self.ver = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

        from apps.registros.models import Ciudadano

        self.quiroga = Ciudadano.objects.create(
            institucion=self.inst, nombre="Rubén", apellido="Quiroga", documento="12345678"
        )
        otro = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="87654321"
        )
        # 30 casos: más de una página con el PAGE_SIZE de 25.
        for i in range(30):
            Caso.objects.create(
                institucion=self.inst, version=self.ver,
                ciudadano=self.quiroga if i == 0 else otro,
                prioridad=Caso.Prioridad.URGENTE if i == 0 else Caso.Prioridad.NORMAL,
            )
        self.admin = Usuario.objects.create_superuser("admin@x.com", "x", nombre="Admin")
        self.client.force_authenticate(self.admin)

    def test_pagina_con_total_y_siguiente(self):
        r = self.client.get("/api/casos/")
        self.assertEqual(r.data["count"], 30)
        self.assertEqual(len(r.data["results"]), 25)
        self.assertIsNotNone(r.data["next"], "debe haber segunda página")

    def test_segunda_pagina_trae_el_resto(self):
        r = self.client.get("/api/casos/?page=2")
        self.assertEqual(len(r.data["results"]), 5)

    def test_page_size_configurable(self):
        # Sin `page_size_query_param` en la clase de paginación, DRF ignora esto
        # y devuelve 25: el selector de «filas por página» no haría nada.
        r = self.client.get("/api/casos/?page_size=10")
        self.assertEqual(len(r.data["results"]), 10)
        self.assertEqual(r.data["count"], 30)

    def test_page_size_tiene_techo(self):
        r = self.client.get("/api/casos/?page_size=99999")
        self.assertLessEqual(len(r.data["results"]), 200)

    def test_ordering_ascendente_y_descendente(self):
        asc = self.client.get("/api/casos/?ordering=id").data["results"]
        desc = self.client.get("/api/casos/?ordering=-id").data["results"]
        self.assertLess(asc[0]["id"], desc[0]["id"])
        self.assertEqual(asc[0]["id"], min(c["id"] for c in asc))

    def test_ordering_invalido_se_ignora(self):
        r = self.client.get("/api/casos/?ordering=; DROP TABLE casos")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 30)

    def test_busqueda_por_apellido_del_paciente(self):
        r = self.client.get("/api/casos/?search=Quiroga")
        self.assertEqual(r.data["count"], 1)

    def test_busqueda_por_documento(self):
        r = self.client.get("/api/casos/?search=12345678")
        self.assertEqual(r.data["count"], 1)

    def test_el_orden_lleva_desempate(self):
        """Con empates en la clave, la paginación tiene que seguir siendo estable.

        Los 30 casos del setUp se crean en el mismo instante, así que `-creado`
        empata en todos: sin una columna única al final, la base puede devolver
        un registro en dos páginas distintas o en ninguna.
        """
        vistos = []
        for pagina in (1, 2):
            r = self.client.get(f"/api/casos/?ordering=-creado&page={pagina}")
            vistos += [c["id"] for c in r.data["results"]]

        self.assertEqual(len(vistos), 30)
        self.assertEqual(len(set(vistos)), 30, "hay casos repetidos entre páginas")

    def test_el_desempate_no_pisa_el_orden_pedido(self):
        asc = [c["id"] for c in self.client.get("/api/casos/?ordering=id").data["results"]]
        self.assertEqual(asc, sorted(asc))

    def test_busqueda_se_combina_con_el_filtro_exacto(self):
        r = self.client.get("/api/casos/?search=Quiroga&prioridad=normal")
        self.assertEqual(r.data["count"], 0, "el caso de Quiroga es urgente")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SubirArchivoTest(APITestCase):
    @classmethod
    def tearDownClass(cls):
        from django.conf import settings

        media_root = settings.MEDIA_ROOT
        super().tearDownClass()
        shutil.rmtree(media_root, ignore_errors=True)

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.otra = Institucion.objects.create(nombre="Hospital Norte")
        self.user = Usuario.objects.create_user("f@x.com", "x", nombre="F")
        Membresia.objects.create(
            usuario=self.user, institucion=self.inst, rol=Membresia.Rol.MEDICO, activo=True
        )
        self.client.force_authenticate(self.user)

    def _archivo(self, nombre="estudio.pdf", contenido=b"%PDF-1.4 demo", content_type="application/pdf"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(nombre, contenido, content_type=content_type)

    def test_subir_archivo_devuelve_url_protegida_y_ruta_interna(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["nombre"], "estudio.pdf")
        self.assertIn(f"/api/archivos/descargar/uploads/{self.inst.id}/", r.data["url"])
        self.assertNotIn("/media/uploads/", r.data["url"])
        self.assertTrue(r.data["ruta"].startswith(f"uploads/{self.inst.id}/"))
        self.assertEqual(r.data["content_type"], "application/pdf")
        self.assertEqual(r.data["tamano"], len(b"%PDF-1.4 demo"))
        self.assertEqual(r.data["sha256"], hashlib.sha256(b"%PDF-1.4 demo").hexdigest())

        meta = ArchivoClinico.objects.get(ruta=r.data["ruta"])
        self.assertEqual(meta.institucion_id, self.inst.id)
        self.assertEqual(meta.nombre_original, "estudio.pdf")
        self.assertEqual(meta.content_type, "application/pdf")
        self.assertEqual(meta.tamano, len(b"%PDF-1.4 demo"))
        self.assertEqual(meta.sha256, r.data["sha256"])
        self.assertEqual(meta.subido_por_id, self.user.id)

    def test_no_sube_tipo_de_archivo_no_permitido(self):
        r = self.client.post(
            "/api/archivos/",
            {
                "archivo": self._archivo("malware.exe", b"MZ", content_type="application/octet-stream"),
                "institucion": self.inst.id,
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(ArchivoClinico.objects.exists())

    def test_no_sube_pdf_con_contenido_incompatible(self):
        r = self.client.post(
            "/api/archivos/",
            {
                "archivo": self._archivo("estudio.pdf", b"MZ ejecutable", content_type="application/pdf"),
                "institucion": self.inst.id,
            },
            format="multipart",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(ArchivoClinico.objects.exists())

    @override_settings(ARCHIVO_CLINICO_MAX_BYTES=8)
    def test_no_sube_archivo_demasiado_grande(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(contenido=b"%PDF-1.4 muy grande"), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(ArchivoClinico.objects.exists())

    def test_descarga_el_archivo_solo_con_permiso_clinico_en_la_institucion(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(contenido=b"%PDF-1.4 resultado"), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201, r.data)

        descarga = self.client.get(r.data["url"])
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(b"".join(descarga.streaming_content), b"%PDF-1.4 resultado")

    def test_no_expone_el_archivo_por_media_uploads(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(contenido=b"%PDF-1.4 privado"), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201, r.data)

        directa = self.client.get(f"/media/{r.data['ruta']}")
        self.assertEqual(directa.status_code, 404)

    def test_no_sube_archivo_sin_institucion(self):
        r = self.client.post("/api/archivos/", {"archivo": self._archivo()}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_no_sube_archivo_con_institucion_inexistente(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(), "institucion": 999999},
            format="multipart",
        )
        self.assertEqual(r.status_code, 400)

    def test_usuario_sin_historia_clinica_no_sube(self):
        administrativo = Usuario.objects.create_user("adm@x.com", "x", nombre="Adm")
        Membresia.objects.create(
            usuario=administrativo, institucion=self.inst, rol=Membresia.Rol.ADMINISTRATIVO, activo=True
        )
        self.client.force_authenticate(administrativo)
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 403)

    def test_no_descarga_archivo_de_otra_institucion(self):
        r = self.client.post(
            "/api/archivos/",
            {"archivo": self._archivo(contenido=b"%PDF-1.4 norte"), "institucion": self.inst.id},
            format="multipart",
        )
        self.assertEqual(r.status_code, 201, r.data)
        medico_otro = Usuario.objects.create_user("otro@x.com", "x", nombre="Otro")
        Membresia.objects.create(
            usuario=medico_otro, institucion=self.otra, rol=Membresia.Rol.MEDICO, activo=True
        )
        self.client.force_authenticate(medico_otro)

        descarga = self.client.get(r.data["url"])
        self.assertEqual(descarga.status_code, 403)

    def test_subir_sin_archivo_da_400(self):
        r = self.client.post("/api/archivos/", {"institucion": self.inst.id}, format="multipart")
        self.assertEqual(r.status_code, 400)


class ExportacionCSVTests(APITestCase):
    """
    Exportación a CSV de los listados.

    Es lo que separa «prototipo» de «producto» para cualquiera que tenga que
    rendir cuentas de su servicio: poder llevarse lo que ve en pantalla.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user(
            email="admin@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)
        self.ciudadano = Ciudadano.objects.create(
            institucion=self.inst, nombre="Ana", apellido="Pérez", documento="30111222"
        )
        self.caso = Caso.objects.create(
            institucion=self.inst, version=self.version, ciudadano=self.ciudadano,
            area_actual=self.area, prioridad=Caso.Prioridad.URGENTE,
        )

    def _csv(self, ruta):
        r = self.client.get(ruta)
        self.assertEqual(r.status_code, 200)
        return b"".join(r.streaming_content).decode("utf-8")

    def test_devuelve_un_archivo_para_descargar(self):
        r = self.client.get("/api/casos/?formato=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(".csv", r["Content-Disposition"])

    def test_trae_encabezados_legibles_y_los_datos(self):
        texto = self._csv("/api/casos/?formato=csv")
        self.assertIn("Paciente", texto)
        self.assertIn("Ana Pérez", texto)
        self.assertIn("Urgente", texto)

    def test_empieza_con_BOM_para_que_excel_no_rompa_los_acentos(self):
        """Sin el BOM, Excel muestra «PÃ©rez» y el usuario dice que está roto."""
        self.assertTrue(self._csv("/api/casos/?formato=csv").startswith("﻿"))

    def test_separa_con_punto_y_coma_salvo_que_pidan_coma(self):
        """
        Excel en configuración regional española abre un CSV con comas metiendo
        todo en una sola columna. Quien exporta lo abre en Excel; quien lo lee
        con pandas puede pedir el estándar.
        """
        self.assertIn(";", self._csv("/api/casos/?formato=csv").splitlines()[0])
        self.assertNotIn(";", self._csv("/api/casos/?formato=csv&sep=,").splitlines()[0])

    def test_respeta_los_filtros_de_la_pantalla(self):
        """
        Un archivo que no coincide con lo que había en pantalla no sirve para
        rendir cuentas, que es justamente para lo que se exporta.
        """
        otro = Ciudadano.objects.create(institucion=self.inst, nombre="Luis", apellido="Gómez")
        Caso.objects.create(
            institucion=self.inst, version=self.version, ciudadano=otro,
            area_actual=self.area, prioridad=Caso.Prioridad.NORMAL,
        )
        texto = self._csv("/api/casos/?formato=csv&prioridad=urgente")
        self.assertIn("Ana Pérez", texto)
        self.assertNotIn("Luis Gómez", texto)

    def test_no_lo_corta_la_paginacion(self):
        """Se exporta TODO lo filtrado, no la página que se está mirando."""
        for i in range(30):
            Caso.objects.create(institucion=self.inst, version=self.version, area_actual=self.area)
        filas = self._csv("/api/casos/?formato=csv").strip().splitlines()
        self.assertEqual(len(filas), 32)  # 31 casos + encabezado

    def test_sin_formato_csv_sigue_siendo_la_lista_paginada_de_siempre(self):
        r = self.client.get("/api/casos/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("results", r.data)

    def test_los_booleanos_salen_en_palabras(self):
        Nodo.objects.create(version=self.version, tipo="espera", titulo="Sala")
        nodo = Nodo.objects.first()
        ItemFila.objects.create(caso=self.caso, nodo=nodo, urgente=True, orden=0)
        texto = self._csv("/api/items-fila/?formato=csv")
        self.assertIn("Sí", texto)

    def test_las_fechas_salen_en_formato_local(self):
        """
        En ISO («2026-08-02T10:14:30-03:00») Excel las deja como texto: no se
        pueden ordenar ni filtrar, que es la mitad de para qué se exporta.
        """
        texto = self._csv("/api/casos/?formato=csv")
        fila = texto.strip().splitlines()[1]
        self.assertRegex(fila, r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}")
        self.assertNotIn("T0", fila)

    def test_el_archivo_se_llama_como_lo_que_trae(self):
        """DRF deriva el basename del modelo y sale en singular («caso.csv»)."""
        r = self.client.get("/api/casos/?formato=csv")
        self.assertIn("casos-", r["Content-Disposition"])

    def test_todas_las_columnas_declaradas_existen_en_su_serializer(self):
        """
        Guarda contra el error silencioso: declarar una columna que el
        serializer no expone da una columna VACÍA, sin ningún aviso. Ya casi
        pasa con los tiempos de la cola.

        Recorre todos los viewsets registrados, así que cubre también los que se
        agreguen después.
        """
        from cauce.api import router

        faltantes = []
        for _, viewset, basename in router.registry:
            columnas = getattr(viewset, "columnas_csv", None)
            if not columnas:
                continue
            # Se pregunta como lo hace el código real: hay viewsets que eligen el
            # serializer según la acción (`get_serializer_class`), y mirar el
            # atributo de la clase devuelve None.
            vista = viewset()
            vista.action = "list"
            expuestos = set(vista.get_serializer_class()().get_fields())
            for clave, encabezado in columnas:
                if clave not in expuestos:
                    faltantes.append(f"{basename}.{clave} («{encabezado}»)")
        self.assertEqual(faltantes, [], "columnas que el serializer no expone")


class OperacionDeFilaAPITests(APITestCase):
    """
    Las acciones de la fila **por HTTP**.

    Los tests del motor las llamaban como funciones, así que no vieron que
    `mover` había quedado declarada en otro viewset: existía
    `/api/notificaciones/<id>/mover/` y la fila daba 404. Un test por endpoint,
    que es lo que el navegador realmente pide.
    """

    def setUp(self):
        self.user = Usuario.objects.create_user(
            "med@test.local", "x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.box = Box.objects.create(area=self.area, nombre="Box 1")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Guardia")
        self.ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
        ini = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio")
        self.ate = Nodo.objects.create(
            version=self.ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención", config={"con_fila": True}
        )
        fin = Nodo.objects.create(version=self.ver, tipo=Nodo.Tipo.FIN, titulo="Cierre")
        Conexion.objects.create(version=self.ver, origen=ini, destino=self.ate)
        Conexion.objects.create(version=self.ver, origen=self.ate, destino=fin)

    def _encolar(self, nombre):
        c = Ciudadano.objects.create(institucion=self.inst, nombre=nombre, apellido="T")
        caso = Caso.objects.create(institucion=self.inst, version=self.ver, ciudadano=c)
        motor.iniciar(caso, autor=self.user)
        caso.refresh_from_db()
        return caso

    def _cola(self):
        r = self.client.get("/api/items-fila/?atendido=false&box=null&ordering=orden")
        return [f["persona"] for f in sorted(r.data["results"], key=lambda f: (not f["urgente"], f["orden"]))]

    def test_marcar_ausente(self):
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.user)
        r = self.client.post(f"/api/casos/{caso.id}/ausente/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["ausente"])
        self.assertEqual(self._cola(), [])

    def test_devolver_a_la_cola(self):
        caso = self._encolar("Ana")
        self._encolar("Beto")
        motor.llamar(caso, box_id=self.box.id, autor=self.user)
        r = self.client.post(f"/api/casos/{caso.id}/devolver/", {"motivo": "lo llamé por error"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._cola(), ["Ana T", "Beto T"])

    def test_mover_en_la_fila(self):
        for n in ("Ana", "Beto", "Caro"):
            self._encolar(n)
        item = ItemFila.objects.get(caso__ciudadano__nombre="Caro")
        r = self.client.post(f"/api/items-fila/{item.id}/mover/", {"posicion": 0})
        self.assertEqual(r.status_code, 200, getattr(r, "data", r.content[:200]))
        self.assertEqual(self._cola(), ["Caro T", "Ana T", "Beto T"])

    def test_mover_sin_posicion_lo_dice(self):
        self._encolar("Ana")
        item = ItemFila.objects.first()
        r = self.client.post(f"/api/items-fila/{item.id}/mover/", {})
        self.assertEqual(r.status_code, 400)

    def test_no_se_puede_dar_por_ausente_a_quien_no_se_llamo(self):
        caso = self._encolar("Ana")
        r = self.client.post(f"/api/casos/{caso.id}/ausente/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("llam", r.data["detail"].lower())

    def test_el_detalle_avisa_que_esta_ausente(self):
        """La pantalla decide con esto si ofrece atender o reencolar."""
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.user)
        self.assertFalse(self.client.get(f"/api/casos/{caso.id}/").data["ausente"])
        self.client.post(f"/api/casos/{caso.id}/ausente/")
        self.assertTrue(self.client.get(f"/api/casos/{caso.id}/").data["ausente"])

    def test_las_acciones_de_fila_existen_donde_dice_el_frontend(self):
        """
        Guarda contra el error que ya pasó: una acción declarada dentro del
        viewset equivocado. Se pide la ruta tal como la arma la pantalla.
        """
        caso = self._encolar("Ana")
        motor.llamar(caso, box_id=self.box.id, autor=self.user)
        item = ItemFila.objects.get(caso=caso)
        for ruta, cuerpo in [
            (f"/api/casos/{caso.id}/devolver/", {}),
            (f"/api/items-fila/{item.id}/mover/", {"posicion": 0}),
            (f"/api/casos/{caso.id}/ausente/", {}),
        ]:
            with self.subTest(ruta=ruta):
                r = self.client.post(ruta, cuerpo)
                self.assertNotEqual(r.status_code, 404, f"{ruta} no existe")
