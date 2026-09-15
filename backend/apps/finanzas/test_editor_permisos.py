"""El editor reemplaza un bloque explícito, sin fabricar permisos efectivos."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connections
from django.test import TransactionTestCase, skipUnlessDBFeature
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.common import capacidades_de
from apps.instituciones.models import Area, Institucion

from .models import ConcesionFinanciera
from .permisos import tiene_concesion_financiera

RUTA = "/api/concesiones-financieras/editar-membresia/"


class EscenarioEditor:
    def preparar(self):
        self.institucion = Institucion.objects.create(nombre="Hospital de prueba")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Clínica médica")
        self.area_dos = Area.objects.create(institucion=self.institucion, nombre="Cardiología")
        self.otra = Institucion.objects.create(nombre="Otra institución")
        self.area_ajena = Area.objects.create(institucion=self.otra, nombre="Área ajena")
        self.admin = Usuario.objects.create_user("admin@prueba.test", "x")
        Membresia.objects.create(usuario=self.admin, institucion=self.institucion, rol="admin")
        self.usuario = Usuario.objects.create_user("operador@prueba.test", "x")
        self.miembro = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="administrativo")
        self.segunda = Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol="configurador")
        self.ajena = Membresia.objects.create(usuario=self.usuario, institucion=self.otra, rol="medico")
        self.lectura = self.conceder(self.miembro, "ver_gastos", [self.area], False)
        self.registro = self.conceder(self.miembro, "registrar_gastos", [self.area_dos], True)
        self.externa = self.conceder(self.segunda, "ver_gastos", [self.area_dos], True)
        self.conceder(self.ajena, "ver_gastos", [self.area_ajena], True)
        self.client.force_authenticate(self.admin)

    def conceder(self, miembro, accion, areas, sensible):
        fila = ConcesionFinanciera.objects.create(membresia=miembro, accion=accion, permite_sensibles=sensible)
        fila.areas.set(areas)
        return fila

    def consultar(self, miembro=None):
        response = self.client.get(RUTA, {"membresia": (miembro or self.miembro).pk})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def payload(self, estado=None):
        estado = estado or self.consultar()
        return {"membresia": estado["membresia"], "version_esperada": estado["version_esperada"],
                "concesiones": [{k: c[k] for k in ("accion", "todas_las_areas", "permite_sensibles", "areas")} for c in estado["concesiones"]]}


class EditorPermisosApiTests(EscenarioEditor, APITestCase):
    def setUp(self):
        self.preparar()

    def test_consulta_conserva_alcances_y_separa_otra_membresia_sin_filtrar_otra_institucion(self):
        estado = self.consultar()
        filas = {c["accion"]: c for c in estado["concesiones"]}
        self.assertEqual(filas["ver_gastos"]["areas"], [self.area.id])
        self.assertFalse(filas["ver_gastos"]["permite_sensibles"])
        self.assertEqual(filas["registrar_gastos"]["areas"], [self.area_dos.id])
        self.assertTrue(filas["registrar_gastos"]["permite_sensibles"])
        self.assertEqual([c["id"] for c in estado["otras_membresias"]], [self.externa.id])
        self.assertEqual(estado["heredadas"], [])

    def test_guarda_bloque_preservando_ids_otra_membresia_y_capacidades_clinicas(self):
        antes = capacidades_de(self.usuario, self.institucion.id)
        datos = self.payload()
        datos["concesiones"] = [c for c in datos["concesiones"] if c["accion"] != "registrar_gastos"]
        datos["concesiones"].append({"accion": "ver_costos", "todas_las_areas": False,
                                     "permite_sensibles": False, "areas": [self.area.id]})
        response = self.client.put(RUTA, datos, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(ConcesionFinanciera.objects.filter(pk=self.lectura.id).exists())
        self.assertFalse(ConcesionFinanciera.objects.filter(pk=self.registro.id).exists())
        self.assertTrue(ConcesionFinanciera.objects.filter(pk=self.externa.id, permite_sensibles=True).exists())
        self.assertEqual(capacidades_de(self.usuario, self.institucion.id), antes)

    def test_herencia_por_rol_no_borra_concesion_explicita_y_sigue_tras_revocarla(self):
        self.miembro.rol = "admin"
        self.miembro.save(update_fields=["rol"])
        estado = self.consultar()
        self.assertEqual(set(estado["heredadas"]), {"ver_costos", "ver_gastos"})
        self.assertEqual(self.client.put(RUTA, self.payload(estado), format="json").status_code, 200)
        self.assertTrue(ConcesionFinanciera.objects.filter(pk=self.lectura.pk).exists())
        datos = self.payload()
        datos["concesiones"] = []
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 200)
        self.assertTrue(tiene_concesion_financiera(self.usuario, "ver_gastos", self.institucion.pk, sensible=True))
        self.assertTrue(ConcesionFinanciera.objects.filter(pk=self.externa.pk).exists())

    def test_rol_admin_en_otra_membresia_institucional_se_identifica_sin_unir_areas(self):
        self.segunda.rol = "admin"
        self.segunda.save(update_fields=["rol"])
        estado = self.consultar()
        self.assertEqual(set(estado["heredadas"]), {"ver_costos", "ver_gastos"})
        self.assertEqual(next(c for c in estado["concesiones"] if c["accion"] == "ver_gastos")["areas"], [self.area.pk])

    def test_cualquier_fila_invalida_impide_todas_las_altas_revocaciones_y_cambios(self):
        antes = self.consultar()
        datos = self.payload(antes)
        datos["concesiones"] = [{"accion": "ver_costos", "todas_las_areas": False,
                                 "permite_sensibles": False, "areas": [self.area.pk]},
                                {"accion": "aprobar_gastos", "todas_las_areas": False,
                                 "permite_sensibles": True, "areas": [self.area_ajena.pk]}]
        response = self.client.put(RUTA, datos, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(self.consultar()["version_esperada"], antes["version_esperada"])

    def test_fallo_de_persistencia_revierte_revocaciones_y_altas(self):
        antes = self.consultar()
        datos = self.payload(antes)
        datos["concesiones"] = [{"accion": "ver_costos", "todas_las_areas": True,
                                 "permite_sensibles": False, "areas": []}]
        with patch.object(ConcesionFinanciera, "save", side_effect=RuntimeError("fallo simulado")):
            with self.assertRaises(RuntimeError):
                self.client.put(RUTA, datos, format="json")
        self.assertEqual(self.consultar()["version_esperada"], antes["version_esperada"])

    def test_conflicto_por_patch_previo_no_pisa_edicion(self):
        datos = self.payload()
        response = self.client.patch(f"/api/concesiones-financieras/{self.lectura.pk}/", {"permite_sensibles": True}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 409)
        self.lectura.refresh_from_db()
        self.assertTrue(self.lectura.permite_sensibles)

    def test_conflicto_por_revocacion_previa_no_resucita_concesion(self):
        datos = self.payload()
        self.assertEqual(self.client.delete(f"/api/concesiones-financieras/{self.lectura.pk}/").status_code, 204)
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 409)
        self.assertFalse(ConcesionFinanciera.objects.filter(pk=self.lectura.pk).exists())

    def test_conflicto_detecta_cambio_de_rol_o_actividad(self):
        for campo, valor in (("rol", "medico"), ("activo", False)):
            with self.subTest(campo=campo):
                datos = self.payload()
                setattr(self.miembro, campo, valor)
                self.miembro.save(update_fields=[campo])
                self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 409)

    def test_inactiva_permite_conservar_y_revocar_pero_no_otorgar_o_ampliar(self):
        self.miembro.activo = False
        self.miembro.save(update_fields=["activo"])
        datos = self.payload()
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 200)
        datos["concesiones"][0]["todas_las_areas"] = True
        datos["concesiones"][0]["areas"] = []
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 400)
        datos = self.payload()
        datos["concesiones"].append({"accion": "ver_costos", "todas_las_areas": True, "permite_sensibles": False, "areas": []})
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 400)
        datos = self.payload()
        datos["concesiones"] = []
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 200)
        self.assertFalse(ConcesionFinanciera.objects.filter(membresia=self.miembro).exists())

    def test_sin_configuracion_institucional_ni_admin_operativo_ajeno_pueden_editar(self):
        self.client.force_authenticate(self.usuario)
        self.assertEqual(self.client.get(RUTA, {"membresia": self.miembro.pk}).status_code, 403)
        self.client.force_authenticate(self.admin)
        datos = self.payload()
        datos["membresia"] = self.ajena.pk
        Membresia.objects.create(usuario=self.admin, institucion=self.otra, rol="medico")
        self.assertEqual(self.client.get(RUTA, {"membresia": self.ajena.pk}).status_code, 403)
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 403)

    def test_duplicados_y_alcance_vacio_se_rechazan_sin_cambios(self):
        antes = self.consultar()
        datos = self.payload(antes)
        datos["concesiones"].append(datos["concesiones"][0])
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 400)
        datos = self.payload(antes)
        datos["concesiones"][0]["areas"] = []
        self.assertEqual(self.client.put(RUTA, datos, format="json").status_code, 400)
        self.assertEqual(self.consultar()["version_esperada"], antes["version_esperada"])

    def test_alta_simple_y_multiple_revalidan_autorizacion_despues_del_lock(self):
        comunes = {"membresia": self.miembro.pk, "todas_las_areas": True, "areas": []}
        for ruta, extra in (("/api/concesiones-financieras/", {"accion": "ver_costos"}),
                            ("/api/concesiones-financieras/otorgar-multiples/", {"acciones": ["ver_costos"]})):
            with self.subTest(ruta=ruta):
                with patch("apps.finanzas.views.tiene_capacidad", side_effect=[True, False]):
                    response = self.client.post(ruta, {**comunes, **extra}, format="json")
                self.assertEqual(response.status_code, 403, response.data)
                self.assertFalse(ConcesionFinanciera.objects.filter(membresia=self.miembro, accion="ver_costos").exists())

    def test_membresia_que_desaparece_al_adquirir_lock_devuelve_404_sin_escribir(self):
        with patch("apps.finanzas.views.Membresia.objects.select_for_update", return_value=Membresia.objects.none()):
            response = self.client.post("/api/concesiones-financieras/", {
                "membresia": self.miembro.pk, "accion": "ver_costos", "todas_las_areas": True,
            }, format="json")
        self.assertEqual(response.status_code, 404, response.data)
        self.assertFalse(ConcesionFinanciera.objects.filter(membresia=self.miembro, accion="ver_costos").exists())


@skipUnlessDBFeature("has_select_for_update")
class EditorPermisosConcurrentesTests(EscenarioEditor, TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.preparar()

    def test_dos_guardados_simultaneos_solo_aplican_una_version(self):
        original = self.payload()
        barrera = Barrier(2)

        def guardar(accion):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.admin)
                datos = {**original, "concesiones": [{"accion": accion, "todas_las_areas": True,
                          "permite_sensibles": False, "areas": []}]}
                barrera.wait(timeout=10)
                return client.put(RUTA, datos, format="json").status_code
            finally:
                # Las conexiones sanas también deben cerrarse al terminar el
                # hilo para que Django pueda retirar la base temporal.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            estados = list(workers.map(guardar, ("ver_costos", "ver_dinero")))
        self.assertEqual(sorted(estados), [200, 409])
        self.assertEqual(ConcesionFinanciera.objects.filter(membresia=self.miembro).count(), 1)
        self.assertTrue(ConcesionFinanciera.objects.filter(pk=self.externa.pk).exists())
