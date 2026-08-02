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
        self.assertIn("médico", d["error"]["mensaje"])
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
