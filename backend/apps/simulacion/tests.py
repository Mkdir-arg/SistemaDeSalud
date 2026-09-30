"""
Simulación de perfiles: el servidor aplica los límites de la cuenta simulada.

Estas pruebas fijan cinco cosas:
- Solo un superusuario abre una simulación, y un encabezado inválido nunca cae
  en el acceso total.
- En lecturas y escrituras manda la cuenta de referencia: su institución, su
  rol y su organización de financiador.
- Lo que se escribe queda a nombre del superusuario y la simulación queda
  registrada por separado.
- Cada FK a `Usuario` está clasificada como autoría u operativa.
- Una cuenta alterada no simula con permisos ampliados.
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.core.management import CommandError, call_command
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso, EventoCaso
from apps.financiadores.models import EventoCobertura, Financiador, HistorialAfiliacion, ReglaCobertura, PrestacionComun
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Grupo, Institucion
from apps.registros.models import Ciudadano, HistoriaClinica

from . import contexto
from .models import CuentaReferencia, OperacionSimulada, SesionSimulacion


def jwt(usuario):
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(usuario).access_token}"}


class EscenarioSimulacion:
    """Dos hospitales y dos financiadores; cuentas preparadas para A y para F."""

    @classmethod
    def setUpTestData(cls):
        cls.root = Usuario.objects.create_superuser("root@salud.local", "x", nombre="Root")
        cls.a = Institucion.objects.create(nombre="Hospital A")
        cls.b = Institucion.objects.create(nombre="Hospital B")
        cls.guardia_a = Area.objects.create(institucion=cls.a, nombre="Guardia")
        cls.guardia_b = Area.objects.create(institucion=cls.b, nombre="Guardia")
        cls.admin_a = Usuario.objects.create_user("admin@a.local", "x", nombre="Admin A")
        Membresia.objects.create(usuario=cls.admin_a, institucion=cls.a, rol="admin")
        cls.enfermera = Usuario.objects.create_user("enfermera@a.local", "x", nombre="Enfermera")
        m = Membresia.objects.create(usuario=cls.enfermera, institucion=cls.a, rol="enfermeria")
        m.areas.add(cls.guardia_a)
        cls.triage = Grupo.objects.create(area=cls.guardia_a, nombre="Triage")
        cls.triage.miembros.add(cls.enfermera)
        cls.paciente_a = Ciudadano.objects.create(institucion=cls.a, nombre="Ana", apellido="A", documento="1")
        cls.paciente_b = Ciudadano.objects.create(institucion=cls.b, nombre="Beto", apellido="B", documento="2")
        cls.hc_a = HistoriaClinica.objects.get_or_create(ciudadano=cls.paciente_a)[0]
        cls.hc_b = HistoriaClinica.objects.get_or_create(ciudadano=cls.paciente_b)[0]
        cls.f = Financiador.objects.create(nombre="Obra F", tipo="obra_social")
        cls.g = Financiador.objects.create(nombre="Obra G", tipo="obra_social")
        cls.prestacion = PrestacionComun.objects.create(codigo="C1", nombre="Consulta", categoria="Consultas")
        call_command(
            "preparar_cuentas_referencia", institucion=[cls.a.pk], financiador=[cls.f.pk],
            ancla_estatal=cls.a.pk, stdout=StringIO(),
        )

    def cuenta(self, rol, **ambito):
        return CuentaReferencia.objects.get(rol=rol, **ambito).usuario

    def simular(self, rol, ambito="institucion", **destino):
        cuerpo = {"ambito": ambito, "rol": rol, **destino}
        if ambito == "institucion" and not destino:
            cuerpo["institucion"] = self.a.pk
        if ambito == "financiador" and not destino:
            cuerpo["financiador"] = self.f.pk
        r = self.client.post("/api/simulaciones/", cuerpo, format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        self.sesion = SesionSimulacion.objects.get(pk=r.data["id"])
        return {**jwt(self.root), "HTTP_X_HEN_SIMULACION": r.data["id"]}


class AccesoExclusivoTests(EscenarioSimulacion, APITestCase):
    def test_otro_usuario_no_abre_ni_consulta_simulaciones(self):
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "medico", "institucion": self.a.pk},
                             format="json", **jwt(self.admin_a))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/simulaciones/catalogo/", **jwt(self.admin_a)).status_code, 403)
        self.assertFalse(SesionSimulacion.objects.exists())

    def test_el_encabezado_no_sirve_con_el_token_de_otro_usuario(self):
        encabezados = self.simular("medico")
        r = self.client.get("/api/ciudadanos/", **{**encabezados, **jwt(self.admin_a)})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["simulacion"], "rechazada")

    def test_sin_token_el_encabezado_no_cae_en_la_sesion_de_django(self):
        encabezados = self.simular("medico")
        self.client.force_login(self.root)
        r = self.client.get("/api/instituciones/", HTTP_X_HEN_SIMULACION=encabezados["HTTP_X_HEN_SIMULACION"])
        self.assertEqual(r.status_code, 403)

    def test_una_simulacion_terminada_no_vuelve_al_acceso_total(self):
        encabezados = self.simular("medico")
        r = self.client.post(f"/api/simulaciones/{self.sesion.pk}/finalizar/", {}, format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/instituciones/", **encabezados)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["simulacion"], "rechazada")
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fin, SesionSimulacion.Fin.SALIDA)

    def test_una_simulacion_vencida_se_cierra_y_rechaza(self):
        encabezados = self.simular("medico")
        SesionSimulacion.objects.filter(pk=self.sesion.pk).update(vence=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get("/api/ciudadanos/", **encabezados).status_code, 403)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fin, SesionSimulacion.Fin.VENCIMIENTO)

    def test_un_id_invalido_se_rechaza(self):
        r = self.client.get("/api/ciudadanos/", HTTP_X_HEN_SIMULACION="no-es-un-uuid", **jwt(self.root))
        self.assertEqual(r.status_code, 403)

    def test_encabezado_vacio_no_recupera_el_acceso_total(self):
        r = self.client.get("/api/instituciones/", HTTP_X_HEN_SIMULACION="", **jwt(self.root))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["simulacion"], "rechazada")
        self.assertEqual(self.client.get("/api/health/", HTTP_X_HEN_SIMULACION="", **jwt(self.root)).status_code, 403)

    def test_desde_una_simulacion_no_se_abre_otra(self):
        encabezados = self.simular("medico")
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "admin", "institucion": self.a.pk},
                             format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_iniciar_otra_cierra_la_anterior(self):
        self.simular("medico")
        anterior = self.sesion
        self.simular("admin")
        anterior.refresh_from_db()
        self.assertEqual(anterior.fin, SesionSimulacion.Fin.REEMPLAZO)

    def test_una_ruta_que_no_autentica_con_simulacion_rechaza_el_encabezado(self):
        encabezados = self.simular("medico")
        self.assertEqual(self.client.get("/api/health/", **encabezados).status_code, 403)

    def test_la_cuenta_de_referencia_no_inicia_sesion_por_su_cuenta(self):
        cuenta = self.cuenta("medico", institucion=self.a)
        cuenta.set_password("una-clave-larga-123")
        cuenta.save()
        r = self.client.post("/api/auth/token/", {"email": cuenta.email, "password": "una-clave-larga-123"}, format="json")
        self.assertEqual(r.status_code, 401)
        r = self.client.post("/api/auth/token/refresh/", {"refresh": str(RefreshToken.for_user(cuenta))}, format="json")
        self.assertEqual(r.status_code, 401)


class CatalogoTests(EscenarioSimulacion, APITestCase):
    def test_el_catalogo_sale_de_los_roles_de_hen(self):
        r = self.client.get(f"/api/simulaciones/catalogo/?institucion={self.a.pk}", **jwt(self.root))
        self.assertEqual({p["rol"] for p in r.data["perfiles"]},
                         set(Membresia.Rol.values) - {"plataforma", "auditor"})
        self.assertTrue(all(p["disponible"] for p in r.data["perfiles"]))
        plataforma = self.client.get("/api/simulaciones/catalogo/", **jwt(self.root)).data
        self.assertEqual({p["rol"] for p in plataforma["perfiles"]}, {"plataforma", "auditor"})
        financiador = self.client.get(f"/api/simulaciones/catalogo/?financiador={self.f.pk}", **jwt(self.root)).data
        self.assertEqual({p["rol"] for p in financiador["perfiles"]}, {"admin", "operador", "auditor"})

    def test_el_catalogo_no_escribe_y_el_primer_uso_prepara_solo_el_perfil_elegido(self):
        r = self.client.get(f"/api/simulaciones/catalogo/?institucion={self.b.pk}", **jwt(self.root))
        self.assertTrue(r.data["perfiles"])
        self.assertTrue(all(not p["disponible"] and "Falta preparar" in p["motivo"] for p in r.data["perfiles"]))
        self.assertFalse(CuentaReferencia.objects.filter(ambito="institucion", institucion=self.b).exists())
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "medico", "institucion": self.b.pk},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CuentaReferencia.objects.filter(ambito="institucion", institucion=self.b).count(), 1)
        self.assertEqual(self.cuenta("medico", institucion=self.b).membresias.get().rol, "medico")

    def test_el_primer_uso_prepara_un_financiador_sin_preparar_otros_perfiles(self):
        r = self.client.post("/api/simulaciones/", {"ambito": "financiador", "rol": "operador", "financiador": self.g.pk},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CuentaReferencia.objects.filter(ambito="financiador", financiador=self.g).count(), 1)
        self.assertFalse(self.cuenta("operador", financiador=self.g).has_usable_password())

    def test_el_primer_uso_prepara_un_perfil_estatal_sin_institucion(self):
        self.cuenta("auditor", ambito="plataforma").delete()
        r = self.client.post("/api/simulaciones/", {"ambito": "plataforma", "rol": "auditor"},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        ref = CuentaReferencia.objects.get(ambito="plataforma", rol="auditor")
        self.assertIsNone(ref.institucion_id)
        self.assertEqual(list(ref.usuario.membresias.filter(activo=True).values_list("institucion_id", "rol")),
                         [(None, "auditor")])

    def test_un_perfil_estatal_antiguo_pierde_el_ancla_al_elegirlo(self):
        ref = CuentaReferencia.objects.get(ambito="plataforma", rol="auditor")
        ref.institucion = self.a
        ref.save(update_fields=["institucion"])
        membresia = ref.usuario.membresias.get(activo=True)
        membresia.institucion = self.a
        membresia.save(update_fields=["institucion"])
        r = self.client.post("/api/simulaciones/", {"ambito": "plataforma", "rol": "auditor"},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        ref.refresh_from_db()
        self.assertIsNone(ref.institucion_id)
        self.assertEqual(list(ref.usuario.membresias.filter(activo=True).values_list("institucion_id", "rol")),
                         [(None, "auditor")])

    def test_un_correo_ocupado_no_se_convierte_en_cuenta_automatica(self):
        email = f"medico.i{self.b.pk}@referencia.hen.invalid"
        ajena = Usuario.objects.create_user(email, "clave-123", nombre="Ajena")
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "medico", "institucion": self.b.pk},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 400)
        ajena.refresh_from_db()
        self.assertTrue(ajena.check_password("clave-123"))
        self.assertFalse(CuentaReferencia.objects.filter(ambito="institucion", institucion=self.b).exists())

    def test_un_ambito_inactivo_no_crea_cuentas(self):
        self.b.activa = False
        self.b.save(update_fields=["activa"])
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "medico", "institucion": self.b.pk},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(CuentaReferencia.objects.filter(ambito="institucion", institucion=self.b).exists())

    def test_la_api_de_membresias_sigue_exigiendo_institucion(self):
        r = self.client.post("/api/membresias/", {"usuario": self.admin_a.pk, "rol": "auditor"},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Membresia.objects.filter(usuario=self.admin_a, institucion__isnull=True).exists())

    def test_una_cuenta_alterada_no_simula_con_permisos_ampliados(self):
        encabezados = self.simular("enfermeria")
        Membresia.objects.create(usuario=self.sesion.cuenta, institucion=self.b, rol="admin")
        r = self.client.get("/api/ciudadanos/", **encabezados)
        self.assertEqual(r.status_code, 403)
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fin, SesionSimulacion.Fin.INVALIDA)
        catalogo = self.client.get(f"/api/simulaciones/catalogo/?institucion={self.a.pk}", **jwt(self.root)).data
        enfermeria = next(p for p in catalogo["perfiles"] if p["rol"] == "enfermeria")
        self.assertFalse(enfermeria["disponible"])

    def test_nuevas_areas_y_grupos_de_pares_exigen_preparar_de_nuevo(self):
        encabezados = self.simular("enfermeria")
        nueva_area = Area.objects.create(institucion=self.a, nombre="Pediatría")
        self.enfermera.membresias.get(institucion=self.a).areas.add(nueva_area)
        r = self.client.get("/api/ciudadanos/", **encabezados)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["simulacion"], "rechazada")
        self.sesion.refresh_from_db()
        self.assertEqual(self.sesion.fin, SesionSimulacion.Fin.INVALIDA)
        with self.assertRaises(CommandError):
            call_command("preparar_cuentas_referencia", institucion=[self.a.pk], verificar=True, stdout=StringIO())
        catalogo = self.client.get(f"/api/simulaciones/catalogo/?institucion={self.a.pk}", **jwt(self.root)).data
        enfermeria = next(p for p in catalogo["perfiles"] if p["rol"] == "enfermeria")
        self.assertFalse(enfermeria["disponible"])
        call_command("preparar_cuentas_referencia", institucion=[self.a.pk], stdout=StringIO())
        self.assertIn(nueva_area, self.cuenta("enfermeria", institucion=self.a).membresias.get().areas.all())
        grupo = Grupo.objects.create(area=nueva_area, nombre="Sala")
        grupo.miembros.add(self.enfermera)
        r = self.client.post("/api/simulaciones/", {"ambito": "institucion", "rol": "enfermeria", "institucion": self.a.pk},
                             format="json", **jwt(self.root))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIn(self.cuenta("enfermeria", institucion=self.a), grupo.miembros.all())
        self.assertIn("están listas", self._verificar_cuentas())

    def _verificar_cuentas(self):
        salida = StringIO()
        call_command("preparar_cuentas_referencia", institucion=[self.a.pk], verificar=True, stdout=salida)
        return salida.getvalue()

    def test_me_devuelve_la_cuenta_simulada_y_quien_simula(self):
        encabezados = self.simular("enfermeria")
        me = self.client.get("/api/usuarios/me/", **encabezados).data
        self.assertEqual(me["id"], self.sesion.cuenta_id)
        self.assertFalse(me["is_superuser"])
        self.assertEqual(set(me["capacidades_por_institucion"]), {str(self.a.pk)})
        self.assertEqual(me["simulacion"]["superusuario"]["id"], self.root.pk)
        self.assertEqual(me["simulacion"]["institucion"]["id"], self.a.pk)
        self.assertNotIn("simulacion", self.client.get("/api/usuarios/me/", **jwt(self.root)).data)


class PlataformaSinInstitucionesTests(APITestCase):
    def test_el_auditor_estatal_se_prepara_sin_hospitales(self):
        root = Usuario.objects.create_superuser("root@test.local", "x")
        r = self.client.post("/api/simulaciones/", {"ambito": "plataforma", "rol": "auditor"},
                             format="json", **jwt(root))
        self.assertEqual(r.status_code, 201, r.data)
        ref = CuentaReferencia.objects.get(ambito="plataforma", rol="auditor")
        self.assertIsNone(ref.institucion_id)
        self.assertEqual(list(ref.usuario.membresias.values_list("institucion_id", "rol")), [(None, "auditor")])
        from apps.demo.trabajo import trabajo_por_usuario
        fila = next(f for f in trabajo_por_usuario() if f["email"] == ref.usuario.email)
        self.assertEqual(fila["donde"], "toda la plataforma")


class AlcancePorPerfilTests(EscenarioSimulacion, APITestCase):
    """Una acción permitida y una denegada por perfil representativo."""

    def test_cada_perfil_recibe_las_capacidades_de_su_rol_y_nada_mas(self):
        """El catálogo no define permisos propios: son los de `ROL_CAPACIDADES`."""
        from apps.common import ROL_CAPACIDADES, ROL_CAPACIDADES_UI

        for rol in Membresia.Rol.values:
            ambito = "plataforma" if rol in ("plataforma", "auditor") else "institucion"
            with self.subTest(rol=rol):
                me = self.client.get("/api/usuarios/me/", **self.simular(rol, ambito=ambito)).data
                esperadas = sorted(ROL_CAPACIDADES[rol] | ROL_CAPACIDADES_UI.get(rol, set()))
                clave = "global" if ambito == "plataforma" else str(self.a.pk)
                self.assertEqual(me["capacidades_por_institucion"], {clave: esperadas})
                self.assertEqual(me["roles_por_institucion"], {clave: [rol]})
                self.assertEqual(me["financiadores"], [])
                if "config_institucional" not in esperadas:
                    r = self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": f"X {rol}"},
                                         format="json", **self.simular(rol, ambito=ambito))
                    self.assertEqual(r.status_code, 403)
        for rol in ("admin", "operador", "auditor"):
            with self.subTest(financiador=rol):
                me = self.client.get("/api/usuarios/me/", **self.simular(rol, ambito="financiador")).data
                self.assertEqual(me["capacidades_por_institucion"], {})
                self.assertEqual([(f["id"], f["rol"]) for f in me["financiadores"]], [(self.f.pk, rol)])

    def ids(self, respuesta):
        datos = respuesta.data
        return {fila["id"] for fila in (datos["results"] if isinstance(datos, dict) else datos)}

    def test_enfermeria_lee_la_historia_de_su_institucion_y_no_configura(self):
        encabezados = self.simular("enfermeria")
        self.assertEqual(self.ids(self.client.get("/api/ciudadanos/", **encabezados)), {self.paciente_a.pk})
        self.assertEqual(self.client.get(f"/api/historias-clinicas/{self.hc_a.pk}/", **encabezados).status_code, 200)
        self.assertEqual(self.client.get(f"/api/historias-clinicas/{self.hc_b.pk}/", **encabezados).status_code, 404)
        r = self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "Nueva"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_el_superusuario_sin_simular_si_ve_las_dos_instituciones(self):
        self.assertEqual(self.ids(self.client.get("/api/ciudadanos/", **jwt(self.root))),
                         {self.paciente_a.pk, self.paciente_b.pk})

    def test_administrativo_admite_pacientes_pero_no_lee_historia_clinica(self):
        encabezados = self.simular("administrativo")
        self.assertEqual(self.client.get("/api/ciudadanos/", **encabezados).status_code, 200)
        self.assertEqual(self.client.get(f"/api/historias-clinicas/{self.hc_a.pk}/", **encabezados).status_code, 403)

    def test_admin_configura_su_institucion_y_no_otra(self):
        encabezados = self.simular("admin")
        r = self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "Pediatría"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post("/api/areas/", {"institucion": self.b.pk, "nombre": "Pediatría"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_jefe_area_supervisa_su_area_y_no_configura(self):
        jefa = Usuario.objects.create_user("jefa@a.local", "x", nombre="Jefa")
        membresia = Membresia.objects.create(usuario=jefa, institucion=self.a, rol="jefe_area")
        membresia.areas.add(self.guardia_a)
        call_command("preparar_cuentas_referencia", institucion=[self.a.pk], stdout=StringIO())
        flujo = Flujo.objects.create(institucion=self.a, area=self.guardia_a, titulo="Supervisión")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Evaluar")
        caso = Caso.objects.create(institucion=self.a, version=version, nodo_actual=nodo, area_actual=self.guardia_a)

        encabezados = self.simular("jefe_area")
        respuesta = self.client.get("/api/casos/?supervisables=true", **encabezados)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self.ids(respuesta), {caso.pk})
        self.assertEqual(self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "X"},
                                          format="json", **encabezados).status_code, 403)

    def test_el_espejo_de_grupos_permite_tomar_solo_el_nodo_responsable(self):
        flujo = Flujo.objects.create(institucion=self.a, area=self.guardia_a, titulo="Grupos")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        nodo_propio = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Triage")
        nodo_ajeno = Nodo.objects.create(version=version, tipo=Nodo.Tipo.ATENCION, titulo="Otra guardia")
        nodo_propio.grupos.add(self.triage)
        nodo_ajeno.grupos.add(Grupo.objects.create(area=self.guardia_a, nombre="Otro equipo"))
        propio = Caso.objects.create(institucion=self.a, version=version, nodo_actual=nodo_propio,
                                    area_actual=self.guardia_a)
        ajeno = Caso.objects.create(institucion=self.a, version=version, nodo_actual=nodo_ajeno,
                                   area_actual=self.guardia_a)

        encabezados = self.simular("enfermeria")
        respuesta = self.client.get("/api/casos/?tomables=true", **encabezados)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self.ids(respuesta), {propio.pk})
        self.assertEqual(self.client.post(f"/api/casos/{ajeno.pk}/tomar/", {}, format="json",
                                          **encabezados).status_code, 403)
        respuesta = self.client.post(f"/api/casos/{propio.pk}/tomar/", {}, format="json", **encabezados)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        propio.refresh_from_db()
        self.assertEqual(propio.asignado_a_id, self.sesion.cuenta_id)

    def test_lectura_financiera_simulada_exige_concesion_y_respeta_la_institucion(self):
        from apps.finanzas.models import AccesoFinanciero, ConcesionFinanciera, ConceptoGasto, Gasto

        gastos = []
        for institucion in (self.a, self.b):
            concepto = ConceptoGasto.objects.create(institucion=institucion, codigo="L", nombre="Luz")
            gastos.append(Gasto.objects.create(
                concepto=concepto, institucion=institucion, concepto_codigo="L", concepto_nombre="Luz",
                importe=Decimal("100"), periodo_economico=timezone.localdate().replace(day=1),
                origen=Gasto.Origen.CENTRAL, estado=Gasto.Estado.APROBADO,
                aprobado_por=self.root, aprobado_en=timezone.now(),
            ))

        encabezados = self.simular("administrativo")
        self.assertEqual(self.client.get("/api/gastos/", **encabezados).status_code, 403)
        ConcesionFinanciera.objects.create(
            membresia=self.sesion.cuenta.membresias.get(), accion="ver_gastos", todas_las_areas=True,
        )
        respuesta = self.client.get("/api/gastos/", **encabezados)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self.ids(respuesta), {gastos[0].pk})
        self.assertTrue(AccesoFinanciero.objects.filter(usuario=self.root, simulacion=self.sesion).exists())

    def test_reportes_conserva_solo_lectura(self):
        encabezados = self.simular("reportes")
        self.assertEqual(self.client.get("/api/instituciones/", **encabezados).status_code, 200)
        r = self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "X"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)
        r = self.client.post("/api/ciudadanos/", {"institucion": self.a.pk, "nombre": "X"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_configurador_disena_pero_no_lee_historia(self):
        encabezados = self.simular("configurador")
        r = self.client.post("/api/flujos/", {"institucion": self.a.pk, "titulo": "Guardia"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.get(f"/api/historias-clinicas/{self.hc_a.pk}/", **encabezados).status_code, 403)

    def test_autoridad_estatal_gobierna_la_plataforma_sin_acceso_clinico(self):
        encabezados = self.simular("plataforma", ambito="plataforma")
        r = self.client.post("/api/instituciones/", {"nombre": "Hospital C"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.client.get(f"/api/historias-clinicas/{self.hc_b.pk}/", **encabezados).status_code, 403)

    def test_auditor_estatal_audita_y_no_administra(self):
        encabezados = self.simular("auditor", ambito="plataforma")
        self.assertEqual(self.client.get("/api/accesos-clinicos/", **encabezados).status_code, 200)
        r = self.client.post("/api/instituciones/", {"nombre": "Hospital C"}, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_admin_de_financiador_configura_reglas_solo_de_su_organizacion(self):
        encabezados = self.simular("admin", ambito="financiador")
        self.assertEqual(self.ids(self.client.get("/api/financiadores/", **encabezados)), {self.f.pk})
        regla = {"prestacion": self.prestacion.pk, "porcentaje": "80", "periodo": "mes",
                 "vigente_desde": timezone.localdate().isoformat()}
        r = self.client.post(f"/api/financiadores/{self.f.pk}/reglas/", regla, format="json", **encabezados)
        self.assertEqual(r.status_code, 201, r.data)
        r = self.client.post(f"/api/financiadores/{self.g.pk}/reglas/", regla, format="json", **encabezados)
        self.assertEqual(r.status_code, 404)
        creada = ReglaCobertura.objects.get(financiador=self.f)
        self.assertEqual(creada.creado_por, self.root)
        self.assertEqual(EventoCobertura.objects.get(accion="version_regla").usuario, self.root)

    def test_operador_de_financiador_mantiene_padron_pero_no_reglas(self):
        encabezados = self.simular("operador", ambito="financiador")
        afiliado = {"numero": "100", "documento": "30111222", "nombre": "Afiliada", "desde": timezone.localdate().isoformat()}
        r = self.client.post(f"/api/financiadores/{self.f.pk}/padron/", afiliado, format="json", **encabezados)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(HistorialAfiliacion.objects.get().registrado_por, self.root)
        regla = {"prestacion": self.prestacion.pk, "porcentaje": "80", "periodo": "mes",
                 "vigente_desde": timezone.localdate().isoformat()}
        r = self.client.post(f"/api/financiadores/{self.f.pk}/reglas/", regla, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)

    def test_auditor_de_financiador_consulta_sin_escribir(self):
        encabezados = self.simular("auditor", ambito="financiador")
        self.assertEqual(self.client.get(f"/api/financiadores/{self.f.pk}/padron/", **encabezados).status_code, 200)
        afiliado = {"numero": "100", "documento": "30111222", "nombre": "Afiliada", "desde": timezone.localdate().isoformat()}
        r = self.client.post(f"/api/financiadores/{self.f.pk}/padron/", afiliado, format="json", **encabezados)
        self.assertEqual(r.status_code, 403)


class AutoriaYRegistroTests(EscenarioSimulacion, APITestCase):
    def test_el_evento_del_motor_conserva_la_autoria_real(self):
        flujo = Flujo.objects.create(institucion=self.a, area=self.guardia_a, titulo="Avance")
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        formulario = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FORMULARIO, titulo="Triage")
        fin = Nodo.objects.create(version=version, tipo=Nodo.Tipo.FIN, titulo="Fin")
        Conexion.objects.create(version=version, origen=formulario, destino=fin)
        caso = Caso.objects.create(institucion=self.a, version=version, nodo_actual=formulario,
                                  area_actual=self.guardia_a)

        encabezados = self.simular("medico")
        respuesta = self.client.post(f"/api/casos/{caso.pk}/avanzar/", {"valores": {}},
                                     format="json", **encabezados)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        evento = EventoCaso.objects.get(caso=caso, titulo__contains="Formulario")
        self.assertEqual(evento.autor, self.root)
        self.assertTrue(OperacionSimulada.objects.filter(sesion=self.sesion, ruta=f"/api/casos/{caso.pk}/avanzar/").exists())

    def test_la_escritura_es_del_superusuario_y_la_simulacion_queda_registrada(self):
        encabezados = self.simular("medico")
        r = self.client.patch(f"/api/historias-clinicas/{self.hc_a.pk}/", {"alergias": "Penicilina"},
                              format="json", **encabezados)
        self.assertEqual(r.status_code, 200, r.data)
        self.hc_a.refresh_from_db()
        self.assertEqual(self.hc_a.antecedentes_por, self.root)
        operacion = OperacionSimulada.objects.get(sesion=self.sesion)
        self.assertEqual((operacion.metodo, operacion.estado), ("PATCH", 200))
        self.assertEqual(operacion.ruta, f"/api/historias-clinicas/{self.hc_a.pk}/")

    def test_la_escritura_rechazada_tambien_queda_registrada(self):
        encabezados = self.simular("reportes")
        self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "X"}, format="json", **encabezados)
        self.assertEqual(OperacionSimulada.objects.get(sesion=self.sesion).estado, 403)

    def test_si_falla_el_registro_se_revierte_la_escritura(self):
        encabezados = self.simular("admin")
        with patch("apps.simulacion.middleware.OperacionSimulada.objects.create", side_effect=RuntimeError("sin registro")), \
             patch("apps.simulacion.middleware.log.exception"):
            r = self.client.post("/api/areas/", {"institucion": self.a.pk, "nombre": "Sin registro"},
                                 format="json", **encabezados)
        self.assertEqual(r.status_code, 503)
        self.assertFalse(Area.objects.filter(institucion=self.a, nombre="Sin registro").exists())
        self.assertFalse(OperacionSimulada.objects.filter(sesion=self.sesion).exists())

    def test_el_acceso_clinico_es_del_superusuario_con_la_simulacion_aparte(self):
        encabezados = self.simular("enfermeria")
        self.client.get(f"/api/historias-clinicas/{self.hc_a.pk}/", **encabezados)
        acceso = AccesoClinico.objects.get(tipo=AccesoClinico.Tipo.DETALLE)
        self.assertEqual(acceso.usuario, self.root)
        self.assertEqual(acceso.simulacion, self.sesion)
        self.assertEqual(acceso.institucion_id, self.a.pk)
        self.client.force_authenticate(self.root)
        fila = self.client.get("/api/accesos-clinicos/").data["results"][0]
        self.assertEqual(fila["simulacion"]["cuenta"], self.sesion.cuenta.email)

    def test_la_asignacion_operativa_queda_en_la_cuenta(self):
        """Tomar un box es estado del recorrido, no una firma: sigue siendo del perfil."""
        from apps.instituciones.models import Box

        box = Box.objects.create(area=self.guardia_a, nombre="Box 1")
        encabezados = self.simular("medico")
        r = self.client.post(f"/api/boxes/{box.pk}/ocupar/", {}, format="json", **encabezados)
        self.assertEqual(r.status_code, 200, r.data)
        box.refresh_from_db()
        self.assertEqual(box.ocupado_por_id, self.sesion.cuenta_id)

    def test_las_decisiones_por_update_tambien_son_del_superusuario(self):
        """`decidir_ajuste` escribe con `QuerySet.update()`, que no pasa por `pre_save`."""
        from apps.finanzas.models import AjusteGasto, ConceptoGasto, ConcesionFinanciera
        from apps.finanzas.services import decidir_ajuste, registrar_ajuste_gasto, registrar_gasto

        concepto = ConceptoGasto.objects.create(institucion=self.a, codigo="LUZ", nombre="Electricidad")
        mes = timezone.localdate().replace(day=1)
        gasto = registrar_gasto(concepto, self.a, self.guardia_a, Decimal("100"), mes, self.root, aprobado=True)
        ajuste = registrar_ajuste_gasto(gasto.pk, Decimal("-10"), "Nota de crédito", self.root, aprobado=False)
        self.simular("administrativo")
        cuenta = self.sesion.cuenta
        ConcesionFinanciera.objects.create(
            membresia=cuenta.membresias.get(), accion="aprobar_gastos", todas_las_areas=True,
        )
        contexto.activar(self.sesion, self.root)
        try:
            decidir_ajuste(ajuste.pk, modelo=AjusteGasto, usuario=cuenta, aprobar=True)
        finally:
            contexto.limpiar()
        ajuste.refresh_from_db()
        self.assertEqual(ajuste.aprobado_por, self.root)

    def test_fuera_de_una_simulacion_la_autoria_no_cambia(self):
        cuenta = self.cuenta("medico", institucion=self.a)
        self.assertIs(contexto.autor_real(cuenta), cuenta)
        HistoriaClinica.objects.filter(pk=self.hc_a.pk).update(antecedentes_por=None)
        self.hc_a.antecedentes_por = cuenta
        self.hc_a.save()
        self.hc_a.refresh_from_db()
        self.assertEqual(self.hc_a.antecedentes_por, cuenta)


class ClasificacionDeCamposTests(APITestCase):
    def test_cada_fk_a_usuario_esta_clasificada(self):
        """Un campo nuevo que apunte a Usuario tiene que decidir si es autoría."""
        clasificados = {(m, c) for m, campos in contexto.CAMPOS_AUTORIA.items() for c in campos}
        operativos = {(m, c) for m, campos in contexto.CAMPOS_OPERATIVOS.items() for c in campos}
        self.assertFalse(clasificados & operativos)
        encontrados = set()
        for modelo in apps.get_models():
            for campo in modelo._meta.get_fields():
                if campo.auto_created or not campo.is_relation or campo.related_model is not Usuario:
                    continue
                if campo.concrete or campo.many_to_many:
                    encontrados.add((modelo._meta.label, campo.name))
        self.assertEqual(encontrados - clasificados - operativos, set(), "FK a Usuario sin clasificar")
        self.assertEqual((clasificados | operativos) - encontrados, set(), "clasificación de campos que no existen")
