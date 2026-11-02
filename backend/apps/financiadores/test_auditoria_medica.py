"""Designación explícita para futuras prescripciones; personas ficticias únicamente."""
from rest_framework.test import APITestCase, APIClient
from hashlib import sha256
from unittest import skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import connection, transaction, close_old_connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from apps.accounts.models import Usuario, Membresia
from . import models as m


class AuditoriaMedicaFixture:
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.org = m.Financiador.objects.create(nombre="Auditoría médica ficticia", tipo="otro")
        self.admin = Usuario.objects.create_user("gestion-medica@example.invalid", nombre="Administración ficticia")
        self.admin_miembro = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.admin, rol="admin")
        self.lector = Usuario.objects.create_user("lectura-medica@example.invalid", nombre="Persona ficticia")
        self.miembro = m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.lector, rol="operador")
        self.base = f"/api/financiadores/{self.org.pk}/"
        self.datos = dict(email=self.lector.email, nombre=self.lector.nombre, rol="operador")
        self.client.force_authenticate(self.admin)

    def huella(self):
        modelos = (Usuario, m.Financiador, m.MembresiaFinanciador, m.BajaMembresiaFinanciador, m.EventoCobertura)
        return sha256(repr([list(x.objects.order_by("pk").values()) for x in modelos]).encode()).hexdigest()


class AuditoriaMedicaTests(AuditoriaMedicaFixture, APITestCase):
    def test_designacion_explicita_auditada_omision_y_revocacion_sin_otras_concesiones(self):
        self.client.force_authenticate(self.lector)
        self.assertFalse(self.client.get(self.base).data.get("consulta_prescripciones", True))
        self.client.force_authenticate(self.admin)
        r = self.client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["auditoria_medica"])
        self.assertIn("auditoria_medica=True", m.EventoCobertura.objects.latest("pk").motivo)
        self.assertTrue(self.client.post(self.base + "usuarios/", self.datos, format="json").data["auditoria_medica"])
        self.client.force_authenticate(self.lector)
        org = self.client.get(self.base).data
        self.assertTrue(org["consulta_prescripciones"])
        for campo in ("resuelve_autorizaciones", "consulta_historia_clinica", "acceso_padron_salud", "acceso_padron_cobranza"):
            self.assertFalse(org[campo])
        self.client.force_authenticate(self.admin)
        filas = self.client.get(self.base + "usuarios/").data
        self.assertTrue(next(f for f in filas if f["id"] == self.miembro.pk)["auditoria_medica"])
        self.assertEqual(self.client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": False}, format="json").status_code, 201)
        self.assertIn("auditoria_medica=False", m.EventoCobertura.objects.latest("pk").motivo)
        self.client.force_authenticate(self.lector)
        self.assertFalse(self.client.get(self.base).data["consulta_prescripciones"])

    def test_plataforma_no_autodesigna_y_admin_no_otorga_clinica_a_plataforma(self):
        root = Usuario.objects.create_superuser("plataforma-medica@example.invalid", "clave-ficticia")
        m.MembresiaFinanciador.objects.create(financiador=self.org, usuario=root, rol="admin")
        self.client.force_authenticate(root)
        self.assertFalse(self.client.get(self.base).data["consulta_prescripciones"])
        datos = dict(email=root.email, nombre="Plataforma ficticia", rol="admin", auditoria_medica=True)
        antes = self.huella()
        self.assertEqual(self.client.post(self.base + "usuarios/", datos, format="json").status_code, 403)
        self.assertEqual(self.huella(), antes)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(self.base + "usuarios/", datos, format="json").status_code, 400)
        self.assertEqual(self.huella(), antes)

    def test_roles_y_designaciones_previas_no_heredan_acceso_medico(self):
        from .permisos import puede_consultar_prescripciones, requerir_consultar_prescripciones
        from django.core.exceptions import PermissionDenied
        from django.contrib.auth.models import AnonymousUser
        for rol in ("admin", "operador", "auditor"):
            self.miembro.rol = rol
            self.miembro.resuelve_autorizaciones = rol != "auditor"
            self.miembro.acceso_padron_salud = self.miembro.acceso_padron_cobranza = True
            self.miembro.auditoria_medica = False
            self.miembro.save()
            self.assertFalse(puede_consultar_prescripciones(self.lector, self.org.pk))
            with self.assertRaises(PermissionDenied):
                requerir_consultar_prescripciones(self.lector, self.org.pk)
            self.client.force_authenticate(self.admin)
            self.assertEqual(self.client.post(self.base + "usuarios/", self.datos | {"rol": rol, "auditoria_medica": True}, format="json").status_code, 201)
            self.assertTrue(puede_consultar_prescripciones(self.lector, self.org.pk))
        self.assertFalse(puede_consultar_prescripciones(AnonymousUser(), self.org.pk))
        for identificador in (True, False, 0, -1, "1", None):
            self.assertFalse(puede_consultar_prescripciones(self.lector, identificador))
        otro = m.Financiador.objects.create(nombre="Otro ámbito ficticio", tipo="otro")
        m.MembresiaFinanciador.objects.create(financiador=otro, usuario=self.lector, rol="admin")
        self.assertFalse(puede_consultar_prescripciones(self.lector, otro.pk))
        self.miembro.activo = False
        self.miembro.save()
        self.assertFalse(puede_consultar_prescripciones(self.lector, self.org.pk))
        self.miembro.activo = True
        self.miembro.save()
        self.org.activo = False
        self.org.save()
        self.assertFalse(puede_consultar_prescripciones(self.lector, self.org.pk))
        self.org.activo = True
        self.org.save()
        Usuario.objects.filter(pk=self.lector.pk).update(is_active=False)
        self.assertFalse(puede_consultar_prescripciones(self.lector, self.org.pk))

    def test_lectores_e_entradas_invalidas_no_designan_ni_auditan(self):
        for rol in ("operador", "auditor"):
            self.miembro.rol = rol
            self.miembro.save()
            self.client.force_authenticate(self.lector)
            antes = self.huella()
            self.assertEqual(self.client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": True}, format="json").status_code, 403)
            self.assertEqual(self.huella(), antes)
        self.client.force_authenticate(self.admin)
        for valor in (None, "no-es-booleana", []):
            antes = self.huella()
            self.assertEqual(self.client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": valor}, format="json").status_code, 400)
            self.assertEqual(self.huella(), antes)

    def test_admin_inicial_no_recibe_medico_ni_toma_membresia_especial(self):
        gobierno = Usuario.objects.create_user("gobierno-medico@example.invalid")
        Membresia.objects.create(usuario=gobierno, rol="plataforma")
        vacio = m.Financiador.objects.create(nombre="Alta inicial ficticia", tipo="otro")
        url = f"/api/financiadores/{vacio.pk}/usuarios/"
        self.client.force_authenticate(gobierno)
        datos = self.datos | {"rol": "admin"}
        antes = self.huella()
        self.assertEqual(self.client.post(url, datos | {"auditoria_medica": False}, format="json").status_code, 403)
        self.assertEqual(self.huella(), antes)
        self.assertEqual(self.client.post(url, datos, format="json").status_code, 201)
        miembro = m.MembresiaFinanciador.objects.get(financiador=vacio, usuario=self.lector)
        self.assertFalse(miembro.auditoria_medica)
        miembro.activo, miembro.auditoria_medica = False, True
        miembro.save()
        antes = self.huella()
        self.assertEqual(self.client.post(url, datos, format="json").status_code, 403)
        self.assertEqual(self.huella(), antes)


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL ficticio dedicado.")
class MigracionAuditoriaMedicaTests(TransactionTestCase):
    def test_membresias_previas_y_escritor_anterior_no_reciben_designacion(self):
        org = m.Financiador.objects.create(nombre="Migración médica ficticia", tipo="otro")
        usuario = Usuario.objects.create_user("previo-medico@example.invalid")
        otro = Usuario.objects.create_user("escritor-previo-medico@example.invalid")
        executor = MigrationExecutor(connection)
        finales = executor.loader.graph.leaf_nodes("financiadores")
        previo = [("financiadores", "0019_borrador_plazo_dias")]
        executor.migrate(previo)
        try:
            historica = executor.loader.project_state(previo).apps.get_model("financiadores", "MembresiaFinanciador")
            fila = historica.objects.create(financiador_id=org.pk, usuario_id=usuario.pk, rol="admin",
                resuelve_autorizaciones=True, acceso_padron_salud=True, acceso_padron_cobranza=True)
            antes = historica.objects.values().get(pk=fila.pk)
            MigrationExecutor(connection).migrate(finales)
            despues = m.MembresiaFinanciador.objects.values().get(pk=fila.pk)
            self.assertFalse(despues.pop("auditoria_medica"))
            self.assertEqual(despues, antes)
            # El modelo histórico omite la nueva columna: comprobar default de DB.
            nueva = historica.objects.create(financiador_id=org.pk, usuario_id=otro.pk, rol="auditor")
            self.assertFalse(m.MembresiaFinanciador.objects.get(pk=nueva.pk).auditoria_medica)
            from .permisos import puede_consultar_prescripciones
            self.assertFalse(puede_consultar_prescripciones(usuario, org.pk))
            self.assertFalse(puede_consultar_prescripciones(otro, org.pk))
        finally:
            MigrationExecutor(connection).migrate(finales)


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL ficticio dedicado.")
class IntegridadAuditoriaMedicaTests(AuditoriaMedicaFixture, TransactionTestCase):
    def test_fallo_de_auditoria_revierte_designacion_y_conserva_huella(self):
        antes = self.huella()
        self.client.raise_request_exception = False
        with patch("apps.financiadores.views.auditar", side_effect=RuntimeError("Auditoría ficticia no disponible")):
            r = self.client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": True}, format="json")
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.huella(), antes)

    def test_admin_revocado_mientras_espera_lock_no_concede_designacion(self):
        from .permisos import requerir_financiador
        autorizado = Event()
        def guard(*args, **kwargs):
            resultado = requerir_financiador(*args, **kwargs)
            if kwargs.get("admin"):
                autorizado.set()
            return resultado
        def consultar():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.admin)
                with patch("apps.financiadores.views.requerir_financiador", side_effect=guard):
                    return client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": True}, format="json").status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                m.Financiador.objects.select_for_update(no_key=True).get(pk=self.org.pk)
                resultado = pool.submit(consultar)
                self.assertTrue(autorizado.wait(10))
                m.MembresiaFinanciador.objects.filter(pk=self.admin_miembro.pk).update(rol="operador")
                antes = self.huella()
            self.assertEqual(resultado.result(timeout=15), 403)
        self.assertEqual(self.huella(), antes)

    def test_simulacion_de_plataforma_no_consume_ni_concede_designacion(self):
        from apps.simulacion.models import SesionSimulacion
        from apps.simulacion.tests import jwt
        root = Usuario.objects.create_superuser("simulacion-medica@example.invalid", "x")
        client = APIClient()
        inicio = client.post("/api/simulaciones/", dict(ambito="financiador", rol="admin", financiador=self.org.pk), format="json", **jwt(root))
        self.assertEqual(inicio.status_code, 201)
        referencia = SesionSimulacion.objects.get(pk=inicio.data["id"]).cuenta
        m.MembresiaFinanciador.objects.filter(financiador=self.org, usuario=referencia).update(auditoria_medica=True)
        headers = {**jwt(root), "HTTP_X_PLEXO_SIMULACION": inicio.data["id"]}
        antes = self.huella()
        consulta = client.get(self.base, **headers)
        self.assertEqual(consulta.status_code, 200)
        self.assertFalse(consulta.data["consulta_prescripciones"])
        self.assertEqual(client.post(self.base + "usuarios/", self.datos | {"auditoria_medica": True}, format="json", **headers).status_code, 403)
        self.assertEqual(self.huella(), antes)

    def test_usuario_cacheado_desactivado_en_db_pierde_capacidad(self):
        from .permisos import puede_consultar_prescripciones
        m.MembresiaFinanciador.objects.filter(pk=self.miembro.pk).update(auditoria_medica=True)
        self.assertTrue(puede_consultar_prescripciones(self.lector, self.org.pk))
        Usuario.objects.filter(pk=self.lector.pk).update(is_active=False)
        self.assertTrue(self.lector.is_active)
        self.assertFalse(puede_consultar_prescripciones(self.lector, self.org.pk))
