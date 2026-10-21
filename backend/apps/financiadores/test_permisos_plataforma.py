"""#170: gobierno estatal no concede administración de un financiador."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from apps.casos.models import Caso
from apps.finanzas.models import HechoAtencionCosteable
from apps.simulacion.models import Ambito, OperacionSimulada
from apps.simulacion.preparacion import preparar_cuenta
from apps.simulacion.tests import jwt

from . import models as m
from .test_cobertura import CoberturaSetup
from .test_autorizaciones import AutorizacionSetup
from .cobertura import seleccionar_afiliacion


class PermisosPlataformaTests(APITestCase):
    def setUp(self):
        self.plataforma = Usuario.objects.create_user("gobierno170@example.test")
        Membresia.objects.create(usuario=self.plataforma, rol="plataforma")
        self.org = m.Financiador.objects.create(nombre="Financiador A", tipo="mutual")
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.client.force_authenticate(self.plataforma)

    def test_plataforma_sin_membresia_no_crea_plan(self):
        respuesta = self.client.post(self.base + "planes/", {
            "codigo": "BASE", "nombre": "Plan base",
        }, format="json")
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertFalse(m.Plan.objects.filter(financiador=self.org).exists())
        self.assertFalse(m.EventoCobertura.objects.filter(accion="crear_plan").exists())

    def test_alta_inicial_designa_admin_sin_acceso_general(self):
        respuesta = self.client.post(self.base + "usuarios/", {
            "email": "admin170@example.test", "nombre": "Administración propia",
            "rol": "admin", "activo": True,
        }, format="json")
        self.assertEqual(respuesta.status_code, 201)
        miembro = m.MembresiaFinanciador.objects.get(financiador=self.org)
        self.assertEqual(miembro.rol, "admin")
        self.assertFalse(miembro.resuelve_autorizaciones)
        self.assertFalse(miembro.acceso_padron_salud)
        self.assertFalse(miembro.acceso_padron_cobranza)
        self.assertIn("activacion", respuesta.data)
        evento = m.EventoCobertura.objects.get(accion="membresia_financiador")
        self.assertEqual(evento.usuario, self.plataforma)
        self.assertEqual(self.client.get(self.base + "usuarios/").status_code, 403)
        segunda = self.client.post(self.base + "usuarios/", {
            "email": "otro170@example.test", "nombre": "Otra cuenta", "rol": "admin",
        }, format="json")
        self.assertEqual(segunda.status_code, 403)
        self.assertFalse(Usuario.objects.filter(email="otro170@example.test").exists())

    def test_directorio_no_inventa_rol_y_publica_alta_inicial(self):
        respuesta = self.client.get("/api/financiadores/")
        self.assertEqual(respuesta.status_code, 200)
        fila = respuesta.data["results"][0]
        self.assertIsNone(fila["rol"])
        self.assertTrue(fila["puede_designar_admin_inicial"])

    def test_plataforma_conserva_alta_catalogo_y_directorio_basico(self):
        alta = self.client.post("/api/financiadores/", {"nombre": "Nueva organización", "tipo": "mutual"}, format="json")
        self.assertEqual(alta.status_code, 201)
        self.assertIsNone(alta.data["rol"])
        self.assertEqual(self.client.get(self.base).status_code, 200)
        catalogo = self.client.post("/api/financiadores/catalogo-comun/", {
            "codigo": "CONS170", "nombre": "Consulta común", "categoria": "Consultas",
        }, format="json")
        self.assertEqual(catalogo.status_code, 201)
        self.assertEqual(self.client.get("/api/financiadores/catalogo-comun/").status_code, 200)

    def test_plataforma_no_lee_datos_operativos_ni_escribe_por_rutas_alternativas(self):
        for recurso in ("planes", "reglas", "convenios", "padron", "consumos", "actividad", "resumen", "facturas", "importaciones", "catalogo", "usuarios"):
            with self.subTest(lectura=recurso):
                self.assertEqual(self.client.get(self.base + recurso + "/").status_code, 403)
        for recurso in ("planes", "reglas", "convenios", "padron", "consumos", "facturas", "editar-plan", "corregir-identidad", "finalizar-afiliacion", "reactivar-afiliacion", "aceptar-convenio", "cerrar-convenio", "rechazar-convenio", "plazo-autorizacion", "importaciones", "confirmar-importacion"):
            with self.subTest(escritura=recurso):
                self.assertEqual(self.client.post(self.base + recurso + "/", {}, format="json").status_code, 403)
        self.assertFalse(m.EventoCobertura.objects.exists())

    def test_roles_reales_no_se_elevan_por_combinar_plataforma(self):
        for combinado in (False, True):
            for rol in ("admin", "operador", "auditor"):
                with self.subTest(plataforma=combinado, rol=rol):
                    usuario = self.plataforma if combinado else Usuario.objects.create_user(f"{rol}170@example.test")
                    miembro, _ = m.MembresiaFinanciador.objects.update_or_create(
                        financiador=self.org, usuario=usuario, defaults={"rol": rol, "activo": True},
                    )
                    self.client.force_authenticate(usuario)
                    self.assertEqual(self.client.get(self.base + "planes/").status_code, 200)
                    detalle = self.client.get(self.base)
                    self.assertEqual(detalle.data["rol"], rol)
                    alta = self.client.post(self.base + "planes/", {
                        "codigo": f"{combinado}-{rol}", "nombre": "Plan propio",
                    }, format="json")
                    self.assertEqual(alta.status_code, 201 if rol == "admin" else 403)
                    usuarios = self.client.get(self.base + "usuarios/")
                    self.assertEqual(usuarios.status_code, 200 if rol == "admin" else 403)
                    # Ninguna membresía habilita otra organización.
                    otra = m.Financiador.objects.create(nombre="Otro ámbito", tipo="otro")
                    esperado = 403 if combinado else 404
                    self.assertEqual(self.client.get(f"/api/financiadores/{otra.pk}/padron/").status_code, esperado)
                    self.assertEqual(self.client.get("/api/autorizaciones-cobertura/", {"financiador": otra.pk}).status_code, 403)

    def test_auditor_no_modifica_padron_y_operador_si(self):
        miembro = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.plataforma, rol="auditor")
        entrada = {"numero": "170", "documento": "170001", "nombre": "Persona ficticia", "desde": str(timezone.localdate())}
        self.assertEqual(self.client.post(self.base + "padron/", entrada, format="json").status_code, 403)
        miembro.rol = "operador"
        miembro.save(update_fields=["rol"])
        self.assertEqual(self.client.post(self.base + "padron/", entrada, format="json").status_code, 201)

    def test_membresia_o_financiador_inactivo_no_habilitan_operacion(self):
        miembro = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.plataforma, rol="admin", activo=False)
        self.assertEqual(self.client.get(self.base + "padron/").status_code, 403)
        miembro.activo = True
        miembro.save(update_fields=["activo"])
        self.org.activo = False
        self.org.save(update_fields=["activo"])
        self.assertEqual(self.client.get(self.base + "padron/").status_code, 403)
        self.assertFalse(self.client.get(self.base).data["puede_designar_admin_inicial"])

    def test_alta_inicial_no_concede_designaciones_ni_roles_distintos(self):
        base = {"email": "candidato170@example.test", "nombre": "Candidato", "rol": "admin", "activo": True}
        for cambio in ({"rol": "operador"}, {"rol": "auditor"}, {"activo": False},
                       {"resuelve_autorizaciones": True}, {"acceso_padron_salud": True},
                       {"acceso_padron_cobranza": True}, {"acceso_padron_salud": False},
                       {"email": self.plataforma.email}):
            with self.subTest(cambio=cambio):
                self.assertEqual(self.client.post(self.base + "usuarios/", {**base, **cambio}, format="json").status_code, 403)
        self.assertFalse(m.MembresiaFinanciador.objects.exists())
        self.assertFalse(Usuario.objects.filter(email=base["email"]).exists())
        self.assertFalse(m.EventoCobertura.objects.exists())

    def test_admin_referencia_no_impide_alta_real_y_admin_inactivo_no_la_bloquea(self):
        preparar_cuenta(Ambito.FINANCIADOR, "admin", financiador=self.org)
        inactivo = Usuario.objects.create_user("inactivo170@example.test", is_active=False)
        m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=inactivo, rol="admin")
        self.assertTrue(self.client.get(self.base).data["puede_designar_admin_inicial"])
        respuesta = self.client.post(self.base + "usuarios/", {
            "email": "real170@example.test", "nombre": "Administración real", "rol": "admin",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertFalse(self.client.get(self.base).data["puede_designar_admin_inicial"])

    def test_plataforma_con_operador_puede_alta_inicial_sin_recibir_admin(self):
        m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.plataforma, rol="operador")
        self.assertTrue(self.client.get(self.base).data["puede_designar_admin_inicial"])
        respuesta = self.client.post(self.base + "usuarios/", {
            "email": "admin-combinado170@example.test", "nombre": "Admin real", "rol": "admin",
        }, format="json")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(self.client.get(self.base).data["rol"], "operador")
        self.assertEqual(self.client.get(self.base + "usuarios/").status_code, 403)

    def test_superusuario_conserva_soporte_sin_clinica_ni_designaciones_implicitas(self):
        root = Usuario.objects.create_superuser("soporte170@example.test", password=None)
        self.client.force_authenticate(root)
        detalle = self.client.get(self.base)
        self.assertEqual(detalle.data["rol"], "admin")
        self.assertFalse(detalle.data["consulta_historia_clinica"])
        self.assertFalse(detalle.data["carga_solicitudes_manuales"])
        self.assertFalse(detalle.data["resuelve_autorizaciones"])
        self.assertFalse(detalle.data["acceso_padron_salud"])
        self.assertFalse(detalle.data["acceso_padron_cobranza"])
        self.assertEqual(self.client.post(self.base + "planes/", {"codigo": "SOP", "nombre": "Soporte"}, format="json").status_code, 201)
        self.assertEqual(self.client.post(self.base + "usuarios/", {"email": "soportado170@example.test", "nombre": "Admin", "rol": "admin"}, format="json").status_code, 201)
        self.assertEqual(self.client.get(self.base + "ficha-historia-casos/", {"afiliado": 1}).status_code, 403)

    def test_simulacion_plataforma_no_hereda_admin_y_audita_alta_inicial(self):
        root = Usuario.objects.create_superuser("simula170@example.test", "x")
        self.client.force_authenticate(user=None)
        sesion = self.client.post("/api/simulaciones/", {"ambito": "plataforma", "rol": "plataforma"}, format="json", **jwt(root))
        self.assertEqual(sesion.status_code, 201)
        cabeceras = {**jwt(root), "HTTP_X_PLEXO_SIMULACION": sesion.data["id"]}
        respuesta = self.client.post(self.base + "planes/", {"codigo": "NO", "nombre": "No autorizado"}, format="json", **cabeceras)
        self.assertEqual(respuesta.status_code, 403)
        alta = self.client.post(self.base + "usuarios/", {
            "email": "simulado-admin170@example.test", "nombre": "Admin", "rol": "admin",
        }, format="json", **cabeceras)
        self.assertEqual(alta.status_code, 201)
        evento = m.EventoCobertura.objects.get(accion="membresia_financiador")
        self.assertEqual(evento.usuario_id, root.pk)
        self.assertTrue(OperacionSimulada.objects.filter(sesion_id=sesion.data["id"], ruta=self.base + "usuarios/", estado=201).exists())
        self.assertTrue(OperacionSimulada.objects.filter(sesion_id=sesion.data["id"], ruta=self.base + "planes/", estado=403).exists())

    def test_simulacion_financiador_respeta_roles_y_autoria(self):
        root = Usuario.objects.create_superuser("perfiles170@example.test", "x")
        self.client.force_authenticate(user=None)
        for rol in ("admin", "operador", "auditor"):
            with self.subTest(rol=rol):
                inicio = self.client.post("/api/simulaciones/", {"ambito": "financiador", "rol": rol,
                    "financiador": self.org.pk}, format="json", **jwt(root))
                self.assertEqual(inicio.status_code, 201)
                cabeceras = {**jwt(root), "HTTP_X_PLEXO_SIMULACION": inicio.data["id"]}
                listado = self.client.get("/api/financiadores/", **cabeceras)
                self.assertEqual(listado.data["results"][0]["rol"], rol)
                respuesta = self.client.post(self.base + "planes/", {"codigo": rol, "nombre": "Plan simulado"}, format="json", **cabeceras)
                self.assertEqual(respuesta.status_code, 201 if rol == "admin" else 403)
                if rol == "admin":
                    self.assertEqual(m.EventoCobertura.objects.get(accion="crear_plan").usuario_id, root.pk)
                otra = m.Financiador.objects.create(nombre="Otro financiador", tipo="otro")
                self.assertEqual(self.client.get(f"/api/financiadores/{otra.pk}/padron/", **cabeceras).status_code, 404)


class AltaInicialConcurrenteTests(TransactionTestCase):
    @skipUnless(connection.vendor == "postgresql", "La concurrencia requiere PostgreSQL real.")
    def test_dos_peticiones_solo_designan_un_admin_inicial(self):
        usuario = Usuario.objects.create_user("concurrencia170@example.test")
        Membresia.objects.create(usuario=usuario, rol="plataforma")
        org = m.Financiador.objects.create(nombre="Alta concurrente", tipo="mutual")
        barrera = Barrier(2)

        def invitar(numero):
            close_old_connections()
            try:
                cliente = APIClient()
                cliente.force_authenticate(usuario)
                barrera.wait(timeout=15)
                return cliente.post(f"/api/financiadores/{org.pk}/usuarios/", {
                    "email": f"concurrente{numero}@example.test", "nombre": "Admin", "rol": "admin",
                }, format="json").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            resultados = list(ejecutor.map(invitar, (1, 2)))
        self.assertEqual(sorted(resultados), [201, 403])
        self.assertEqual(m.MembresiaFinanciador.objects.filter(financiador=org, activo=True, rol="admin").count(), 1)
        self.assertEqual(m.EventoCobertura.objects.filter(financiador=org, accion="membresia_financiador").count(), 1)


class RutasPlataformaTests(CoberturaSetup, APITestCase):
    def setUp(self):
        super().setUp()
        self.plataforma = Usuario.objects.create_user("gobierno-rutas170@example.test")
        Membresia.objects.create(usuario=self.plataforma, rol="plataforma")
        self.base = f"/api/financiadores/{self.financiador.pk}/"
        self.client.force_authenticate(self.plataforma)

    def test_soporte_y_medico_autorizado_conservan_acceso_hospitalario(self):
        for usuario in (self.admin, self.plataforma):
            with self.subTest(superusuario=usuario.is_superuser):
                if usuario == self.plataforma:
                    miembro = Membresia.objects.create(usuario=usuario, institucion=self.institucion, rol="medico")
                    miembro.areas.add(self.area)
                self.client.force_authenticate(usuario)
                opciones = self.client.get("/api/coberturas/opciones/", {"institucion": self.institucion.pk})
                self.assertEqual(opciones.status_code, 200)
                self.assertTrue(opciones.data["permisos"]["operar"])
                self.assertEqual([caso["id"] for caso in opciones.data["casos"]], [self.caso.pk])
                afiliados = self.client.get("/api/coberturas/afiliados/", {
                    "institucion": self.institucion.pk, "documento": self.afiliado.documento,
                })
                self.assertEqual(afiliados.status_code, 200)
                self.assertEqual([afiliado["id"] for afiliado in afiliados.data], [self.afiliado.pk])

    def test_clinica_y_bloques_conservan_designaciones_separadas(self):
        self.client.force_authenticate(self.operador)
        self.assertEqual(self.client.get(self.base + "ficha-historia-casos/", {"afiliado": self.afiliado.pk}).status_code, 403)
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.assertEqual(self.client.get(self.base + "ficha-historia-casos/", {"afiliado": self.afiliado.pk}).status_code, 200)
        protegida = self.base + f"padron/{self.afiliado.pk}/"
        self.assertEqual(self.client.get(protegida + "salud/").status_code, 403)
        self.assertEqual(self.client.get(protegida + "cobranza/").status_code, 403)

    def test_plataforma_con_admin_no_amplia_clinica_manual_ni_designaciones(self):
        m.MembresiaFinanciador.objects.create(
            usuario=self.plataforma, financiador=self.financiador, rol="admin",
            resuelve_autorizaciones=True,
        )
        self.assertEqual(self.client.get(self.base + "ficha-historia-casos/", {"afiliado": self.afiliado.pk}).status_code, 403)
        self.assertEqual(self.client.post(f"/api/autorizaciones-cobertura/manual/?financiador={self.financiador.pk}", {}, format="json").status_code, 403)
        protegida = self.base + f"padron/{self.afiliado.pk}/"
        self.assertEqual(self.client.get(protegida + "salud/").status_code, 403)
        # Sólo un admin real de la organización otorga este permiso específico.
        self.membresia.rol = "admin"
        self.membresia.save(update_fields=["rol"])
        self.client.force_authenticate(self.operador)
        concesion = self.client.post(self.base + "usuarios/", {
            "email": self.plataforma.email, "nombre": "Miembro combinado", "rol": "admin", "acceso_padron_salud": True,
        }, format="json")
        self.assertEqual(concesion.status_code, 201)
        self.client.force_authenticate(self.plataforma)
        self.assertEqual(self.client.get(protegida + "salud/").status_code, 200)
        self.assertEqual(self.client.get(protegida + "cobranza/").status_code, 403)
        autoasignacion = self.client.post(self.base + "usuarios/", {
            "email": self.plataforma.email, "nombre": "Miembro combinado", "rol": "admin", "acceso_padron_cobranza": True,
        }, format="json")
        self.assertEqual(autoasignacion.status_code, 403)

    def test_simulacion_plataforma_no_elude_ambito_hospitalario(self):
        self.reservar(acepta=True)
        self.client.force_authenticate(user=None)
        inicio = self.client.post("/api/simulaciones/", {"ambito": "plataforma", "rol": "plataforma"}, format="json", **jwt(self.admin))
        self.assertEqual(inicio.status_code, 201)
        cabeceras = {**jwt(self.admin), "HTTP_X_PLEXO_SIMULACION": inicio.data["id"]}
        self.assertEqual(self.client.get("/api/coberturas/opciones/", {"institucion": self.institucion.pk}, **cabeceras).status_code, 403)
        self.assertEqual(self.client.get("/api/coberturas/afiliados/", {"institucion": self.institucion.pk, "documento": self.afiliado.documento}, **cabeceras).status_code, 404)
        listado = self.client.get("/api/coberturas/", {"institucion": self.institucion.pk}, **cabeceras)
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(listado.data["results"], [])
        self.assertEqual(self.client.get("/api/autorizaciones-cobertura/contexto/", {"caso": self.caso.pk}, **cabeceras).status_code, 404)

    def test_opciones_y_busqueda_hospitalaria_no_eluden_membresia(self):
        opciones = self.client.get("/api/coberturas/opciones/", {"institucion": self.institucion.pk})
        with self.subTest(ruta="opciones"):
            self.assertEqual(opciones.status_code, 403)
        afiliados = self.client.get("/api/coberturas/afiliados/", {
            "institucion": self.institucion.pk, "documento": self.afiliado.documento,
        })
        self.assertEqual(afiliados.status_code, 404)

    def test_listados_hospitalarios_no_devuelven_reservas_ni_recuperables_transversales(self):
        self.reservar(acepta=True)
        HechoAtencionCosteable.objects.create(
            institucion=self.institucion, evento_origen_id=170,
            caso_origen_id=self.caso.pk, nodo_origen_id=self.nodo.pk,
            ocurrida_en=timezone.now(), cobertura_contexto={"pendiente": True},
        )
        listado = self.client.get("/api/coberturas/", {"institucion": self.institucion.pk})
        self.assertEqual(listado.status_code, 200)
        with self.subTest(ruta="reservas"):
            self.assertEqual(listado.data["results"], [])
        recuperables = self.client.get("/api/coberturas/recuperables/", {"institucion": self.institucion.pk})
        self.assertEqual(recuperables.status_code, 200)
        self.assertEqual(recuperables.data, [])

    def test_historial_de_cobertura_combinado_respeta_areas_hospitalarias(self):
        miembro = Membresia.objects.create(usuario=self.plataforma, institucion=self.institucion, rol="medico")
        miembro.areas.add(self.area)
        otra_area = Area.objects.create(institucion=self.institucion, nombre="Área ajena")
        otro_caso = Caso.objects.create(
            institucion=self.institucion, version=self.caso.version,
            ciudadano=self.paciente, area_actual=otra_area,
        )
        seleccionar_afiliacion(caso=otro_caso, usuario=self.admin, particular=True, motivo="Cobertura en otra área")
        respuesta = self.client.get(f"/api/ciudadanos/{self.paciente.pk}/cobertura/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(respuesta.data["results"][0]["caso"], self.caso.pk)

    def test_plataforma_no_consulta_contexto_hospitalario_transversal(self):
        respuesta = self.client.get("/api/autorizaciones-cobertura/contexto/", {"caso": self.caso.pk})
        self.assertEqual(respuesta.status_code, 404, respuesta.data)

    def test_plataforma_con_admin_propone_sin_activar_convenio(self):
        m.MembresiaFinanciador.objects.create(
            financiador=self.financiador, usuario=self.plataforma, rol="admin",
        )
        hospital = Institucion.objects.create(nombre="Hospital contraparte")
        respuesta = self.client.post(self.base + "convenios/", {"institucion": hospital.pk}, format="json")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        convenio = m.Convenio.objects.get(institucion=hospital, financiador=self.financiador)
        self.assertEqual(convenio.estado, "propuesto")

        self.assertEqual(convenio.propuesto_por, "financiador")
        self.assertIsNone(convenio.aceptado_en)

    def test_plataforma_con_admin_no_acepta_su_propia_propuesta(self):
        m.MembresiaFinanciador.objects.create(
            financiador=self.financiador, usuario=self.plataforma, rol="admin",
        )
        hospital = Institucion.objects.create(nombre="Hospital de propuesta")
        convenio = m.Convenio.objects.create(
            financiador=self.financiador, institucion=hospital,
            propuesto_por="financiador", creado_por=self.plataforma,
        )
        respuesta = self.client.post(self.base + "aceptar-convenio/", {"convenio": convenio.pk}, format="json")
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        convenio.refresh_from_db()
        self.assertEqual(convenio.estado, "propuesto")


class AutorizacionesPlataformaTests(AutorizacionSetup, APITestCase):
    def test_combinado_solo_resuelve_con_designacion_y_no_cruza_financiador(self):
        solicitud = self.solicitud()
        Membresia.objects.create(usuario=self.operador, rol="plataforma")
        self.membresia.resuelve_autorizaciones = False
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        self.client.force_authenticate(self.operador)
        ruta = f"{self.url}{solicitud.pk}/resolver/"
        respuesta = self.client.post(f"{ruta}?financiador={self.financiador.pk}", self.aprobacion(), format="json")
        self.assertEqual(respuesta.status_code, 403)
        self.membresia.resuelve_autorizaciones = True
        self.membresia.save(update_fields=["resuelve_autorizaciones"])
        otra = m.Financiador.objects.create(nombre="Otra organización", tipo="otro")
        self.assertEqual(self.client.post(f"{ruta}?financiador={otra.pk}", self.aprobacion(), format="json").status_code, 403)
        aprobada = self.client.post(f"{ruta}?financiador={self.financiador.pk}", self.aprobacion(), format="json")
        self.assertEqual(aprobada.status_code, 200)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "aprobada")
