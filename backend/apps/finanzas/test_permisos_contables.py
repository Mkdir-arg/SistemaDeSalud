"""Permisos contables explícitos y lectura institucional derivada del rol."""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.flujos.models import Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Institucion
from .models import ConcesionFinanciera, ConceptoGasto, Gasto, HechoAtencionCosteable, TrabajoReparto
from .permisos import ACCIONES_ADMIN, ACCIONES_SIN_HERENCIA, tiene_concesion_financiera


class PermisosContablesTests(APITestCase):
    def setUp(self):
        self.institucion = Institucion.objects.create(nombre="Hospital propio")
        self.otra = Institucion.objects.create(nombre="Hospital ajeno")
        self.area = Area.objects.create(institucion=self.institucion, nombre="Guardia")
        self.otra_area = Area.objects.create(institucion=self.institucion, nombre="Consultorios")
        self.admin = Usuario.objects.create_user("admin-fin@test.local", "x")
        self.admin_m = Membresia.objects.create(usuario=self.admin, institucion=self.institucion, rol="admin")
        self.contador = Usuario.objects.create_user("contador@test.local", "x")
        self.contador_m = Membresia.objects.create(usuario=self.contador, institucion=self.institucion, rol="administrativo")
        self.client.force_authenticate(self.admin)

    def gasto(self, institucion=None, area=None, sensible=True):
        institucion = institucion or self.institucion
        concepto = ConceptoGasto.objects.create(institucion=institucion, codigo=f"C{ConceptoGasto.objects.count()}", nombre="Concepto", sensible=sensible)
        return Gasto.objects.create(
            concepto=concepto, institucion=institucion, area=area,
            concepto_codigo=concepto.codigo, concepto_nombre=concepto.nombre,
            sensible=sensible, importe=Decimal("100"), periodo_economico=date(2026, 9, 1),
            origen=Gasto.Origen.CENTRAL, estado=Gasto.Estado.APROBADO,
            aprobado_por=self.admin, aprobado_en=timezone.now(),
        )

    def bulk(self, **cambios):
        datos = {"membresia": self.contador_m.pk, "acciones": ["ver_gastos", "aprobar_gastos"],
                 "areas": [self.area.pk], "permite_sensibles": True}
        return self.client.post("/api/concesiones-financieras/otorgar-multiples/", {**datos, **cambios}, format="json")

    def test_admin_hereda_todo_en_su_institucion_y_nada_en_la_ajena(self):
        """La herencia del admin llega hasta el borde de su institución.

        Decisión de `docs/plans/2026-09-18-finanzas-coberturas-usabilidad-diseno.md`:
        el rol hereda todas las acciones financieras, para todas las áreas e
        información sensible, sin crear concesiones. Antes heredaba sólo lectura
        de costos y gastos y este caso afirmaba eso. Lo que la herencia no cruza
        —y es lo que sigue protegido— es la institución ajena.
        """
        propio = self.gasto(area=self.area)
        self.gasto(self.otra)
        for _ in range(2):
            respuesta = self.client.get("/api/gastos/")
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual([g["id"] for g in respuesta.data["results"]], [propio.pk])
        self.assertFalse(ConcesionFinanciera.objects.exists())
        mias = self.client.get("/api/concesiones-financieras/mias/").data["concesiones"]
        self.assertEqual({c["accion"] for c in mias}, set(ACCIONES_ADMIN))
        self.assertTrue(all(c["permite_sensibles"] and c["todas_las_areas"] for c in mias))
        # La herencia no es pareja y conviene que esto quede afirmado, no
        # descubierto: `tiene_concesion_financiera` consulta
        # `instituciones_admin_financiero` y por eso el admin sí opera dinero,
        # cobros y coberturas; en cambio `registrar_gasto` y
        # `PuedeConfigurarRepartos` exigen concesión explícita y no la consultan,
        # así que estas dos altas siguen cerradas para el admin sin concesiones.
        # Si alguna vez se alinean con la decisión, estos 403 pasan a 400: es una
        # decisión de producto, no un detalle a corregir en la prueba.
        self.assertEqual(self.client.post("/api/gastos/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/reglas-reparto/", {}, format="json").status_code, 403)
        # Aprobar y auditar no se heredan: son el control de cuatro ojos.
        for accion in ACCIONES_SIN_HERENCIA:
            self.assertFalse(tiene_concesion_financiera(self.admin, accion, self.institucion.pk), accion)
        self.assertFalse(tiene_concesion_financiera(self.admin, "ver_gastos", self.otra.pk, sensible=True))

    def test_cambio_rol_y_membresia_inactiva_retiran_default_sin_datos_persistidos(self):
        self.admin_m.rol = "administrativo"
        self.admin_m.save()
        self.assertEqual(self.client.get("/api/gastos/").status_code, 403)
        self.assertEqual(self.client.get("/api/concesiones-financieras/mias/").data["concesiones"], [])
        self.admin_m.rol, self.admin_m.activo = "admin", False
        self.admin_m.save()
        self.assertFalse(tiene_concesion_financiera(self.admin, "ver_gastos", self.institucion.pk, sensible=True))

    def test_bulk_otorga_acciones_sensibles_a_contador_solo_en_area(self):
        respuesta = self.bulk()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(len(respuesta.data), 2)
        propio = self.gasto(area=self.area)
        self.gasto(area=self.otra_area)
        self.gasto(self.otra)
        self.client.force_authenticate(self.contador)
        self.assertEqual([g["id"] for g in self.client.get("/api/gastos/").data["results"]], [propio.pk])
        self.assertTrue(tiene_concesion_financiera(self.contador, "aprobar_gastos", self.institucion.pk, self.area.pk, sensible=True))
        self.assertFalse(tiene_concesion_financiera(self.contador, "aprobar_gastos", self.institucion.pk, self.otra_area.pk, sensible=True))
        self.assertEqual(self.bulk(acciones=["corregir_gastos"]).status_code, 403)
        self.contador_m.activo = False
        self.contador_m.save()
        self.assertEqual(self.client.get("/api/gastos/").status_code, 403)

    def test_bulk_rechaza_duplicado_existente_sin_modificar_ni_crear_otros(self):
        self.assertEqual(self.bulk(acciones=["ver_gastos"]).status_code, 201)
        respuesta = self.bulk(acciones=["corregir_gastos", "ver_gastos"], todas_las_areas=True, areas=[])
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(ConcesionFinanciera.objects.count(), 1)
        self.assertFalse(ConcesionFinanciera.objects.get().todas_las_areas)

    def test_bulk_rechaza_fuera_institucion_inactivo_accion_invalida_y_lista_vacia(self):
        ajena = Area.objects.create(institucion=self.otra, nombre="Ajena")
        for cambios in ({"areas": [ajena.pk]}, {"acciones": []}, {"acciones": ["ver_gastos", "invalida"]}, {"acciones": ["ver_gastos", "ver_gastos"]}):
            self.assertEqual(self.bulk(**cambios).status_code, 400)
            self.assertFalse(ConcesionFinanciera.objects.exists())
        miembro_ajeno = Membresia.objects.create(usuario=self.contador, institucion=self.otra, rol="administrativo")
        self.assertEqual(self.bulk(membresia=miembro_ajeno.pk, areas=[], todas_las_areas=True).status_code, 403)
        self.contador_m.activo = False
        self.contador_m.save()
        self.assertEqual(self.bulk().status_code, 400)

    def test_bulk_revierte_primera_alta_si_segunda_falla(self):
        guardar = ConcesionFinanciera.save
        def falla_segunda(instancia, *args, **kwargs):
            if instancia.accion == "aprobar_gastos":
                raise RuntimeError("Falla de persistencia simulada")
            return guardar(instancia, *args, **kwargs)
        with patch.object(ConcesionFinanciera, "save", falla_segunda), self.assertRaises(RuntimeError):
            self.bulk()
        self.assertFalse(ConcesionFinanciera.objects.exists())

    def test_atenciones_disponibles_exige_configuracion_institucional_y_no_expone_grafo(self):
        flujo = Flujo.objects.create(institucion=self.institucion, area=self.area, titulo="Consulta")
        publicada = VersionFlujo.objects.create(flujo=flujo, numero=1, estado="publicada")
        borrador = VersionFlujo.objects.create(flujo=flujo, numero=2)
        nodo = Nodo.objects.create(version=publicada, tipo="atencion", titulo="Consulta", config={"privado": "secreto"})
        Nodo.objects.create(version=borrador, tipo="atencion", titulo="Borrador")
        ruta = "/api/prestaciones-costo/atenciones-disponibles/"
        self.assertEqual(self.client.get(ruta, {"institucion": self.institucion.pk}).status_code, 403)
        self.assertEqual(self.bulk(acciones=["configurar_componentes"], todas_las_areas=True, areas=[]).status_code, 201)
        self.client.force_authenticate(self.contador)
        respuesta = self.client.get(ruta, {"institucion": self.institucion.pk})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([n["id"] for n in respuesta.data], [nodo.pk])
        self.assertNotIn("config", respuesta.data[0])
        self.assertEqual(self.client.get(ruta, {"institucion": self.otra.pk}).status_code, 403)

    def test_filtro_hechos_mes_y_area_nula_conserva_limite_institucional(self):
        for indice, (institucion, area, momento) in enumerate([
            (self.institucion, self.area, datetime(2026, 9, 1)),
            (self.institucion, None, datetime(2026, 9, 30, 23, 59)),
            (self.institucion, None, datetime(2026, 10, 1)),
            (self.otra, None, datetime(2026, 9, 2)),
        ]):
            HechoAtencionCosteable.objects.create(institucion=institucion, area=area, area_origen_id=area.pk if area else None,
                evento_origen_id=indice + 1, caso_origen_id=indice + 1, nodo_origen_id=indice + 1,
                ocurrida_en=timezone.make_aware(momento))
        respuesta = self.client.get("/api/hechos-costo/", {"periodo_economico": "2026-09-01", "area_sin_asignar": "true"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(self.client.get("/api/hechos-costo/", {"periodo_economico": "2026-09-02"}).status_code, 400)

    def test_estado_actualizando_incluye_fuente_nueva_sin_atribuciones_y_respeta_mes(self):
        hecho = HechoAtencionCosteable.objects.create(
            institucion=self.institucion, area=self.area, area_origen_id=self.area.pk,
            evento_origen_id=1, caso_origen_id=1, nodo_origen_id=1,
            ocurrida_en=timezone.make_aware(datetime(2026, 9, 15)),
        )
        gasto = self.gasto(area=self.area)
        trabajo = TrabajoReparto.objects.create(gasto=gasto, reintentar_en=timezone.now())
        ruta = f"/api/hechos-costo/{hecho.pk}/"
        self.assertTrue(self.client.get(ruta).data["reparto_actualizando"])
        self.assertFalse(hecho.atribuciones_reparto.exists())
        trabajo.revision_procesada = trabajo.revision
        trabajo.save()
        self.assertFalse(self.client.get(ruta).data["reparto_actualizando"])
        TrabajoReparto.objects.create(gasto=self.gasto(area=self.otra_area), reintentar_en=timezone.now())
        self.assertFalse(self.client.get(ruta).data["reparto_actualizando"])

    def test_usuario_inactivo_y_membresia_operativa_ajena_no_heredan_admin(self):
        Membresia.objects.create(usuario=self.admin, institucion=self.otra, rol="administrativo")
        self.assertFalse(tiene_concesion_financiera(self.admin, "ver_gastos", self.otra.pk, sensible=True))
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.assertFalse(tiene_concesion_financiera(self.admin, "ver_costos", self.institucion.pk, sensible=True))

    def test_todas_las_acciones_pueden_otorgarse_sin_cambiar_rol(self):
        respuesta = self.bulk(acciones=ConcesionFinanciera.Accion.values)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.contador_m.refresh_from_db()
        self.assertEqual(self.contador_m.rol, "administrativo")
        for accion in ConcesionFinanciera.Accion.values:
            self.assertTrue(tiene_concesion_financiera(self.contador, accion, self.institucion.pk, self.area.pk, sensible=True))
