from django.test import TestCase
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.casos.models import Caso, EventoCaso
from apps.formularios.models import Campo, Formulario

from apps.instituciones.models import Area, Box, Grupo, Institucion, Subarea

from .models import Conexion, Flujo, Nodo, VersionFlujo
from .serializers import NodoSerializer


class FlujoAmbitoTests(TestCase):
    """Un flujo puede ser de la institución, de un área o de una sub-área."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Cardiología")
        self.subarea = Subarea.objects.create(area=self.area, nombre="Hemodinamia")

    def test_flujo_de_institucion(self):
        f = Flujo.objects.create(institucion=self.inst, titulo="Ingreso general")
        self.assertEqual(f.ambito, "institucion")

    def test_flujo_de_area(self):
        f = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Proceso de área")
        self.assertEqual(f.ambito, "area")

    def test_flujo_de_subarea_deriva_area(self):
        # Fijar sólo la sub-área debe completar el área padre automáticamente.
        f = Flujo.objects.create(institucion=self.inst, subarea=self.subarea, titulo="Proceso específico")
        self.assertEqual(f.ambito, "subarea")
        self.assertEqual(f.area_id, self.area.id)


class NodoGruposTests(TestCase):
    """Un nodo puede declarar qué grupos son responsables de ejecutarlo."""

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Turno mañana")
        flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Triage")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        self.nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Evaluar")

    def test_asignar_grupo_y_serializar_detalle(self):
        s = NodoSerializer(self.nodo, data={"grupos": [self.grupo.id]}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        s.save()
        data = NodoSerializer(self.nodo).data
        self.assertEqual(data["grupos"], [self.grupo.id])
        self.assertEqual(data["grupos_detalle"][0]["nombre"], "Turno mañana")
        self.assertEqual(data["grupos_detalle"][0]["area_nombre"], "Guardia")


class FiltroEstadoVigenteTests(APITestCase):
    """`?estado=` filtra por la versión VIGENTE, que no es un campo del flujo.

    «Vigente» es la publicada si existe y, si no, la última por número. La regla
    es sutil —un flujo con v1 publicada y v2 borrador cuenta como PUBLICADO, no
    como borrador— y antes vivía sólo en el frontend, donde además se aplicaba
    sobre los 25 flujos de la primera página.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user(
            email="admin@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

    def _flujo(self, titulo, *estados):
        """Crea un flujo con una versión por estado (v1, v2, …)."""
        f = Flujo.objects.create(institucion=self.inst, titulo=titulo)
        for i, estado in enumerate(estados, start=1):
            VersionFlujo.objects.create(flujo=f, numero=i, estado=estado)
        return f

    def _titulos(self, estado):
        r = self.client.get(f"/api/flujos/?estado={estado}")
        self.assertEqual(r.status_code, 200)
        return {f["titulo"] for f in r.data["results"]}

    def test_publicada_gana_aunque_haya_un_borrador_mas_nuevo(self):
        self._flujo("Con publicada y borrador nuevo", "publicada", "borrador")
        self.assertIn("Con publicada y borrador nuevo", self._titulos("publicada"))
        self.assertNotIn("Con publicada y borrador nuevo", self._titulos("borrador"))

    def test_sin_publicada_manda_la_ultima(self):
        self._flujo("Sólo borradores", "borrador", "borrador")
        self._flujo("Terminó archivado", "borrador", "archivada")

        self.assertIn("Sólo borradores", self._titulos("borrador"))
        self.assertIn("Terminó archivado", self._titulos("archivada"))
        # La v1 borrador no lo hace aparecer como borrador: manda la última.
        self.assertNotIn("Terminó archivado", self._titulos("borrador"))

    def test_flujo_sin_versiones_no_aparece_en_ningun_estado(self):
        Flujo.objects.create(institucion=self.inst, titulo="Recién creado")
        for estado in ("publicada", "borrador", "archivada"):
            self.assertNotIn("Recién creado", self._titulos(estado))

    def test_sin_estado_devuelve_todos(self):
        self._flujo("Uno", "publicada")
        self._flujo("Dos", "borrador")
        r = self.client.get("/api/flujos/")
        self.assertEqual({f["titulo"] for f in r.data["results"]}, {"Uno", "Dos"})


class VersionPublicadaCongeladaTests(APITestCase):
    """
    Publicar CONGELA la versión: el grafo deja de ser editable.

    Lo que se rompe si esto falla: el configurador que a las once de la mañana
    agrega o borra un paso lo está haciendo abajo de los pacientes que ya están
    adentro del circuito. `Caso.version` apunta a esta fila, así que el cambio es
    instantáneo para los casos en curso; y borrar un nodo se lleva puesta la fila
    de espera (ItemFila es CASCADE) y deja a cada caso con `nodo_actual` en NULL,
    o sea sin lugar en el recorrido.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user(
            email="config@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.pub = VersionFlujo.objects.create(
            flujo=self.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        self.ini = Nodo.objects.create(version=self.pub, tipo="inicio", titulo="Inicio", x=80, y=220)
        self.fin = Nodo.objects.create(version=self.pub, tipo="fin", titulo="Cierre", x=400, y=220)
        self.conex = Conexion.objects.create(version=self.pub, origen=self.ini, destino=self.fin)

    def test_no_se_puede_mover_un_nodo_de_una_version_publicada(self):
        r = self.client.patch(f"/api/nodos/{self.ini.pk}/", {"x": 999}, format="json")
        self.assertEqual(r.status_code, 409, r.data)
        self.ini.refresh_from_db()
        self.assertEqual(self.ini.x, 80)

    def test_no_se_puede_borrar_un_nodo_de_una_version_publicada(self):
        """El borrado es el que vacía la sala de espera y traba a los casos."""
        r = self.client.delete(f"/api/nodos/{self.ini.pk}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertTrue(Nodo.objects.filter(pk=self.ini.pk).exists())

    def test_no_se_puede_agregar_un_nodo_a_una_version_publicada(self):
        r = self.client.post(
            "/api/nodos/", {"version": self.pub.pk, "tipo": "form", "titulo": "Nuevo"}, format="json"
        )
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(self.pub.nodos.count(), 2)

    def test_no_se_puede_tocar_una_conexion_de_una_version_publicada(self):
        self.assertEqual(
            self.client.patch(f"/api/conexiones/{self.conex.pk}/", {"etiqueta": "x"}, format="json").status_code,
            409,
        )
        self.assertEqual(self.client.delete(f"/api/conexiones/{self.conex.pk}/").status_code, 409)
        self.assertTrue(Conexion.objects.filter(pk=self.conex.pk).exists())

    def test_sobre_un_borrador_se_edita_como_siempre(self):
        """La guarda no puede convertir al diseñador en un visor: el borrador se edita."""
        borrador = VersionFlujo.objects.create(flujo=self.flujo, numero=2)
        nodo = Nodo.objects.create(version=borrador, tipo="inicio", titulo="Inicio")
        self.assertEqual(
            self.client.patch(f"/api/nodos/{nodo.pk}/", {"x": 40}, format="json").status_code, 200
        )
        self.assertEqual(
            self.client.post(
                "/api/nodos/", {"version": borrador.pk, "tipo": "fin", "titulo": "Cierre"}, format="json"
            ).status_code,
            201,
        )
        self.assertEqual(self.client.delete(f"/api/nodos/{nodo.pk}/").status_code, 204)

    def test_la_pantalla_de_llamados_se_sigue_generando(self):
        """Generar la URL del televisor no cambia el grafo: no puede quedar trabada."""
        r = self.client.post(f"/api/nodos/{self.fin.pk}/pantalla/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["token"])


class NuevaVersionTests(APITestCase):
    """
    «Nueva versión» clona el grafo en un borrador y deja correr lo que ya está.

    Sin esto, la única forma de cambiar un circuito publicado era editarlo en
    vivo. Si el clon pierde condiciones, grupos o configuración, el configurador
    publica una v2 que rutea distinto que la v1 sin haber tocado nada.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Turno mañana")
        self.user = Usuario.objects.create_user(
            email="config@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.formulario = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        self.campo = Campo.objects.create(
            formulario=self.formulario, label="Temperatura", tipo="texto_corto", orden=0
        )
        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.v1 = VersionFlujo.objects.create(
            flujo=self.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        self.form = Nodo.objects.create(
            version=self.v1, tipo="form", titulo="Triage", formulario=self.formulario,
            config={"sla_minutos": 30}, x=80, y=100,
        )
        self.form.grupos.set([self.grupo])
        self.dec = Nodo.objects.create(version=self.v1, tipo="decision", titulo="¿Fiebre?")
        self.fin = Nodo.objects.create(version=self.v1, tipo="fin", titulo="Cierre")
        # El flujo del escenario es PUBLICABLE: tiene Inicio y la Decisión tiene
        # rama por defecto.
        #
        # Antes no los tenía y se publicaba igual, porque la validación no
        # miraba ninguna de las dos cosas. Cuando pasó a mirarlas, este escenario
        # —que existe para probar el versionado, no la validación— se volvió un
        # flujo inválido y el test empezó a fallar por algo que no está probando.
        self.inicio = Nodo.objects.create(version=self.v1, tipo="inicio", titulo="Inicio")
        Conexion.objects.create(version=self.v1, origen=self.inicio, destino=self.form)
        Conexion.objects.create(version=self.v1, origen=self.form, destino=self.dec)
        Conexion.objects.create(
            version=self.v1, origen=self.dec, destino=self.fin, etiqueta="con fiebre",
            condicion={"campo": self.campo.pk, "operador": ">", "valor": "38"},
        )
        # La rama «si no»: sin ella, un caso que no cumple ninguna condición
        # queda trabado en la decisión sin salida.
        Conexion.objects.create(
            version=self.v1, origen=self.dec, destino=self.fin, etiqueta="si no",
        )

    def _nueva(self):
        return self.client.post(f"/api/versiones-flujo/{self.v1.pk}/nueva-version/", {}, format="json")

    def test_clona_nodos_conexiones_condiciones_grupos_y_config(self):
        r = self._nueva()
        self.assertEqual(r.status_code, 201, r.data)
        v2 = VersionFlujo.objects.get(pk=r.data["id"])
        self.assertEqual((v2.numero, v2.estado), (2, VersionFlujo.Estado.BORRADOR))

        self.assertEqual(v2.nodos.count(), 4)
        form2 = v2.nodos.get(tipo="form")
        self.assertEqual(form2.formulario_id, self.formulario.pk)
        self.assertEqual(form2.config, {"sla_minutos": 30})
        self.assertEqual([g.pk for g in form2.grupos.all()], [self.grupo.pk])

        conex2 = v2.conexiones.get(etiqueta="con fiebre")
        self.assertEqual(conex2.condicion, {"campo": self.campo.pk, "operador": ">", "valor": "38"})
        # Las conexiones apuntan a los nodos NUEVOS, no a los de la v1.
        self.assertEqual(conex2.origen.version_id, v2.pk)
        self.assertEqual(conex2.destino.version_id, v2.pk)

    def test_no_copia_el_token_de_la_pantalla_de_llamados(self):
        """Dos nodos con el mismo token hacen que un televisor muestre la fila del otro."""
        self.form.pantalla_token = "abc123"
        self.form.save(update_fields=["pantalla_token"])
        v2 = VersionFlujo.objects.get(pk=self._nueva().data["id"])
        self.assertEqual(v2.nodos.get(tipo="form").pantalla_token, "")

    def test_los_casos_en_curso_siguen_con_su_version(self):
        caso = Caso.objects.create(institucion=self.inst, version=self.v1, nodo_actual=self.form)
        self._nueva()
        caso.refresh_from_db()
        self.assertEqual(caso.version_id, self.v1.pk)
        self.assertEqual(caso.nodo_actual_id, self.form.pk)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, VersionFlujo.Estado.PUBLICADA)

    def test_no_saca_dos_borradores_del_mismo_flujo(self):
        """Con dos borradores compitiendo se termina publicando el equivocado."""
        primera = self._nueva()
        self.assertEqual(primera.status_code, 201)
        segunda = self._nueva()
        self.assertEqual(segunda.status_code, 409, segunda.data)
        self.assertEqual(segunda.data["borrador"], primera.data["id"])
        self.assertEqual(self.flujo.versiones.count(), 2)

    def test_publicar_la_nueva_degrada_a_la_anterior(self):
        v2 = VersionFlujo.objects.get(pk=self._nueva().data["id"])
        r = self.client.post(f"/api/versiones-flujo/{v2.pk}/publicar/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.estado, VersionFlujo.Estado.REEMPLAZADA)
        self.assertEqual(
            self.flujo.versiones.filter(estado=VersionFlujo.Estado.PUBLICADA).count(), 1
        )


class EstadoDeVersionNoEsUnCampoTests(APITestCase):
    """
    Publicar es una transición con reglas, no un campo que se escribe.

    Si el estado se puede escribir por PATCH, el único control que impide que una
    definición rota llegue a producción —`validar_version`, que corre sólo en la
    acción `publicar`— se saltea entero: una versión sin nodo Inicio queda con el
    badge verde «Publicado» y cada caso nuevo muere en `iniciar()`.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.user = Usuario.objects.create_user(
            email="config@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)
        self.flujo = Flujo.objects.create(institucion=self.inst, titulo="Ingreso")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1)

    def test_un_patch_no_publica_una_version_sin_inicio(self):
        r = self.client.patch(
            f"/api/versiones-flujo/{self.version.pk}/", {"estado": "publicada"}, format="json"
        )
        self.assertIn(r.status_code, (200, 400), r.data)
        self.version.refresh_from_db()
        self.assertEqual(self.version.estado, VersionFlujo.Estado.BORRADOR)

    def test_la_puerta_es_publicar_y_valida_el_grafo(self):
        Nodo.objects.create(version=self.version, tipo="derivar", titulo="Derivar")  # sin área
        r = self.client.post(f"/api/versiones-flujo/{self.version.pk}/publicar/", {}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        self.version.refresh_from_db()
        self.assertEqual(self.version.estado, VersionFlujo.Estado.BORRADOR)

    def test_un_patch_no_mueve_la_version_de_flujo_ni_la_renumera(self):
        """Renumerarla o cambiarle el flujo deja a los casos corriendo otro proceso."""
        otro = Flujo.objects.create(institucion=self.inst, titulo="Otro")
        r = self.client.patch(
            f"/api/versiones-flujo/{self.version.pk}/",
            {"flujo": otro.pk, "numero": 7},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.version.refresh_from_db()
        self.assertEqual((self.version.flujo_id, self.version.numero), (self.flujo.pk, 1))


class DuplicarFlujoTests(APITestCase):
    """
    Duplicar copia el proceso, no sólo el título.

    Es la acción con la que una red replica un circuito de 25 nodos en otro
    hospital. Si copia un lienzo vacío, el flujo resultante pasa la validación
    igual (falta de Fin y nodo sin salida son avisos), se puede publicar y elegir
    como destino de una derivación: los casos derivados ahí quedan parados en
    Inicio con el evento «Caso sin salida».
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.grupo = Grupo.objects.create(area=self.area, nombre="Turno mañana")
        self.user = Usuario.objects.create_user(
            email="config@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.v1 = VersionFlujo.objects.create(
            flujo=self.flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
        )
        ini = Nodo.objects.create(version=self.v1, tipo="inicio", titulo="Inicio")
        aten = Nodo.objects.create(
            version=self.v1, tipo="atencion", titulo="Atención", config={"con_fila": True}
        )
        aten.grupos.set([self.grupo])
        fin = Nodo.objects.create(version=self.v1, tipo="fin", titulo="Cierre")
        Conexion.objects.create(version=self.v1, origen=ini, destino=aten)
        Conexion.objects.create(version=self.v1, origen=aten, destino=fin, etiqueta="listo")

    def test_la_copia_trae_el_grafo_completo(self):
        r = self.client.post(f"/api/flujos/{self.flujo.pk}/duplicar/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        copia = Flujo.objects.get(pk=r.data["id"])
        self.assertEqual(copia.titulo, "Ingreso (copia)")

        version = copia.versiones.get()
        self.assertEqual((version.numero, version.estado), (1, VersionFlujo.Estado.BORRADOR))
        self.assertEqual(version.nodos.count(), 3)
        self.assertEqual(version.conexiones.count(), 2)
        aten = version.nodos.get(tipo="atencion")
        self.assertEqual(aten.config, {"con_fila": True})
        self.assertEqual([g.pk for g in aten.grupos.all()], [self.grupo.pk])
        self.assertEqual(version.conexiones.get(etiqueta="listo").destino.titulo, "Cierre")

    def test_la_copia_no_comparte_nodos_con_el_original(self):
        """Si compartieran nodos, tocar la copia cambiaría el flujo que está corriendo."""
        copia = Flujo.objects.get(pk=self.client.post(f"/api/flujos/{self.flujo.pk}/duplicar/", {}, format="json").data["id"])
        ids_originales = set(self.v1.nodos.values_list("pk", flat=True))
        ids_copia = set(copia.versiones.get().nodos.values_list("pk", flat=True))
        self.assertFalse(ids_originales & ids_copia)

    def test_un_flujo_vacio_se_duplica_con_su_nodo_inicio(self):
        vacio = Flujo.objects.create(institucion=self.inst, titulo="Sin nada")
        r = self.client.post(f"/api/flujos/{vacio.pk}/duplicar/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        version = Flujo.objects.get(pk=r.data["id"]).versiones.get()
        self.assertEqual([n.tipo for n in version.nodos.all()], ["inicio"])


class VolumenDelDisenoTests(APITestCase):
    """
    Ni el listado de flujos ni el mapa pueden hacer más consultas con más flujos.

    Es la propiedad de `apps/casos/tests_volumen.py` aplicada a las dos pantallas
    que quedaban afuera. `/api/flujos/` no lo abre sólo el diseñador: lo piden
    también las bandejas y el detalle de caso, que son pantallas de ejecución
    abiertas todo el día. Con un N+1 acá, la institución que llevó el sistema a
    diez áreas ve la pantalla tardar y nadie sabe por qué.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user(
            email="admin@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

    def _poblar(self, cuantos):
        for i in range(cuantos):
            flujo = Flujo.objects.create(
                institucion=self.inst, area=self.area, titulo=f"Proceso {i}"
            )
            v1 = VersionFlujo.objects.create(
                flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
            )
            VersionFlujo.objects.create(flujo=flujo, numero=2)
            ini = Nodo.objects.create(
                version=v1, tipo="inicio", titulo="Inicio", config={"origen": "ambos"}
            )
            der = Nodo.objects.create(
                version=v1, tipo="derivar", titulo="Derivar", config={"flujo_destino_id": flujo.pk}
            )
            Conexion.objects.create(version=v1, origen=ini, destino=der)
            Caso.objects.create(institucion=self.inst, version=v1, nodo_actual=der)

    def _consultas(self, url, cuantos):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._poblar(cuantos)
        self.client.get(url)  # calienta lo que se cachea por proceso
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.data)
        return len(ctx.captured_queries)

    def _no_escala(self, url):
        pocas = self._consultas(url, 3)
        muchas = self._consultas(url, 27)  # 3 + 27 = 30
        self.assertEqual(
            pocas, muchas,
            f"{url} hace {pocas} consultas con 3 flujos y {muchas} con 30: hay un N+1.",
        )

    def test_listado_de_flujos(self):
        self._no_escala("/api/flujos/?page_size=100")

    def test_mapa_de_flujos(self):
        self._no_escala("/api/flujos/mapa/")

    def test_el_conteo_de_casos_activos_sigue_siendo_el_correcto(self):
        """La anotación reemplaza a un `count()` por fila: tiene que dar lo mismo."""
        flujo = Flujo.objects.create(institucion=self.inst, titulo="Ingreso")
        v1 = VersionFlujo.objects.create(flujo=flujo, numero=1)
        v2 = VersionFlujo.objects.create(flujo=flujo, numero=2)
        Caso.objects.create(institucion=self.inst, version=v1)
        Caso.objects.create(institucion=self.inst, version=v2)
        Caso.objects.create(institucion=self.inst, version=v1, estado=Caso.Estado.CERRADO)

        r = self.client.get(f"/api/flujos/{flujo.pk}/")
        self.assertEqual(r.data["casos_activos"], 2)


class EnsayoTests(APITestCase):
    """
    «Probar» un flujo corre el motor REAL y no deja nada en la base.

    Es el reemplazo del simulador que vivía en el navegador espejando a
    `motor.py`. Lo que se prueba acá es justo lo que aquel no podía dar: que el
    recorrido sea el del motor de verdad, y que probarlo no ensucie los datos.
    """

    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")
        self.user = Usuario.objects.create_user(
            email="admin@test.local", password="x", is_superuser=True, is_staff=True
        )
        self.client.force_authenticate(self.user)

        self.flujo = Flujo.objects.create(institucion=self.inst, area=self.area, titulo="Ingreso")
        self.version = VersionFlujo.objects.create(flujo=self.flujo, numero=1, estado="borrador")

    def _nodo(self, tipo, titulo, **extra):
        return Nodo.objects.create(version=self.version, tipo=tipo, titulo=titulo, **extra)

    def _unir(self, origen, destino, condicion=None):
        # `condicion` vacía = rama por defecto. El campo no admite null: el vacío
        # se representa con {}.
        return Conexion.objects.create(
            version=self.version, origen=origen, destino=destino, condicion=condicion or {}
        )

    def _ensayo(self, pasos=None):
        r = self.client.post(
            f"/api/versiones-flujo/{self.version.pk}/ensayo/",
            {"pasos": pasos or []},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_recorre_los_automaticos_y_se_detiene_en_el_formulario(self):
        ini = self._nodo("inicio", "Inicio")
        form = self._nodo("form", "Datos del paciente")
        self._unir(ini, form)

        d = self._ensayo()
        self.assertEqual([p["nodo"] for p in d["camino"]], [ini.pk, form.pk])
        self.assertEqual(d["parada"]["nodo"], form.pk)
        self.assertFalse(d["termino"])

    def test_no_deja_rastro_en_la_base(self):
        ini = self._nodo("inicio", "Inicio")
        fin = self._nodo("fin", "Cierre")
        self._unir(ini, fin)

        antes = (Caso.objects.count(), EventoCaso.objects.count())
        self._ensayo()
        self._ensayo()  # dos veces, por si la primera dejaba algo
        self.assertEqual((Caso.objects.count(), EventoCaso.objects.count()), antes)

    def test_la_decision_toma_la_rama_segun_el_dato_cargado(self):
        formulario = Formulario.objects.create(institucion=self.inst, titulo="Triage")
        campo = Campo.objects.create(formulario=formulario, label="Edad", tipo="texto_corto", orden=0)

        ini = self._nodo("inicio", "Inicio")
        form = self._nodo("form", "Triage", formulario=formulario)
        dec = self._nodo("decision", "¿Mayor de 65?")
        mayor = self._nodo("fin", "Circuito adulto mayor")
        resto = self._nodo("fin", "Circuito general")
        self._unir(ini, form)
        self._unir(form, dec)
        self._unir(dec, mayor, condicion={"campo": campo.pk, "operador": ">", "valor": "65"})
        self._unir(dec, resto)  # rama por defecto

        con_70 = self._ensayo([{"valores": {str(campo.pk): "70"}}])
        self.assertEqual(con_70["parada"]["nodo"], mayor.pk)
        self.assertTrue(con_70["termino"])

        con_30 = self._ensayo([{"valores": {str(campo.pk): "30"}}])
        self.assertEqual(con_30["parada"]["nodo"], resto.pk)

    def test_un_limite_del_motor_se_informa_con_el_nodo_donde_pasa(self):
        """
        Lo que el simulador del navegador no sabía hacer.

        Una Atención sólo la puede registrar un médico. Si prueba alguien que no
        lo es, el ensayo tiene que DECIRLO y señalar el nodo, en vez de dibujar
        un recorrido feliz que en producción no va a ocurrir.
        """
        otro = Usuario.objects.create_user(email="config@test.local", password="x")
        Membresia.objects.create(
            usuario=otro, institucion=self.inst, rol=Membresia.Rol.CONFIGURADOR, activo=True
        )
        self.client.force_authenticate(otro)

        ini = self._nodo("inicio", "Inicio")
        aten = self._nodo("atencion", "Consulta")
        fin = self._nodo("fin", "Cierre")
        self._unir(ini, aten)
        self._unir(aten, fin)

        d = self._ensayo([{"titulo": "Consulta", "contenido": "ok"}])
        self.assertIsNotNone(d["error"])
        # El mensaje dice QUIÉN puede registrar el paso, no sólo que no se puede.
        self.assertIn("médico", d["error"]["mensaje"].lower())
        self.assertEqual(d["error"]["nodo"], aten.pk)
        # Y no miente diciendo que terminó.
        self.assertFalse(d["termino"])

    def test_un_ciclo_automatico_se_reporta_en_vez_de_colgarse(self):
        a = self._nodo("inicio", "Inicio")
        b = self._nodo("accion", "Vuelta")
        self._unir(a, b)
        self._unir(b, a)

        d = self._ensayo()
        self.assertIsNotNone(d["error"])
        self.assertIn("Ciclo", d["error"]["mensaje"])

    def test_una_atencion_con_fila_pide_llamar_antes_de_atender(self):
        """
        La secuencia real de una guardia: primero se llama al paciente desde un
        box, recién después se registra la atención. El simulador del navegador
        no sabía nada de esto y atravesaba el nodo de largo.
        """
        Box.objects.create(area=self.area, nombre="Box 1")
        ini = self._nodo("inicio", "Inicio")
        sala = self._nodo("atencion", "Sala de espera", config={"con_fila": True})
        fin = self._nodo("fin", "Egreso")
        self._unir(ini, sala)
        self._unir(sala, fin)

        # Parado en la sala, lo que toca es llamar — no avanzar.
        d = self._ensayo()
        self.assertEqual(d["parada"]["acciones"], ["llamar"])

        # Y avanzar sin llamar es justamente lo que el motor rechaza.
        directo = self._ensayo([{"titulo": "x", "contenido": "y", "firmada": False}])
        self.assertIsNotNone(directo["error"])
        self.assertIn("llamar", directo["error"]["mensaje"])

        # Llamando primero, el recorrido sigue hasta el final.
        completo = self._ensayo([
            {"accion": "llamar"},
            {"titulo": "Consulta", "contenido": "ok", "firmada": False},
        ])
        self.assertIsNone(completo["error"])
        self.assertTrue(completo["termino"])
        self.assertEqual(completo["parada"]["nodo"], fin.pk)
