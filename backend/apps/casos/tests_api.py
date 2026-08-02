"""Tests de la capa API: scope por institución y acciones del motor."""
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, VersionFlujo
from apps.flujos.models import Nodo
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano
from apps.casos.models import Caso, ItemFila


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


class SubirArchivoTest(APITestCase):
    def test_subir_archivo_devuelve_nombre_y_url(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        user = Usuario.objects.create_user("f@x.com", "x", nombre="F")
        self.client.force_authenticate(user)
        archivo = SimpleUploadedFile("estudio.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
        r = self.client.post("/api/archivos/", {"archivo": archivo}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["nombre"], "estudio.pdf")
        self.assertIn("/media/uploads/", r.data["url"])

    def test_subir_sin_archivo_da_400(self):
        user = Usuario.objects.create_user("g@x.com", "x", nombre="G")
        self.client.force_authenticate(user)
        r = self.client.post("/api/archivos/", {}, format="multipart")
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
