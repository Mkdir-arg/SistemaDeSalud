"""Integridad y revocación: probes independientes sobre PostgreSQL ficticio."""
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless
from unittest.mock import patch
import hashlib
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from django.db import connection, transaction, IntegrityError, close_old_connections
from django.db.migrations.executor import MigrationExecutor
from django.core.exceptions import PermissionDenied, ValidationError
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador, BorradorReglaDerechos, EventoCobertura, Plan, Afiliado
from apps.financiadores.derechos_borrador import BorradorDerechos
from apps.financiadores.borradores_derechos import guardar_borradores, consultar_borradores
from apps.financiadores.permisos import requerir_financiador

@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL dedicado.")
class IntegridadBorradoresTests(TransactionTestCase):
    def setUp(self):
        self.org=Financiador.objects.create(nombre="Probe ficticio",tipo="otro")
        self.user=Usuario.objects.create_user("probe@example.invalid")
        self.member=MembresiaFinanciador.objects.create(financiador=self.org,usuario=self.user,rol="admin")
        self.draft=BorradorDerechos("probe",1,"Fuente ficticia",self.org.pk,"dependencia",None,date(2030,1,1))
    def save(self, proposal):
        return guardar_borradores(usuario=self.user,financiador_id=self.org.pk,propuesta=proposal,motivo="Probe ficticio",regimen="dependencia",plan_id=None,fecha=date(2030,1,1))
    def fingerprint(self):
        tables=[Financiador,MembresiaFinanciador,BorradorReglaDerechos,EventoCobertura]
        return hashlib.sha256(repr([list(m.objects.order_by("pk").values()) for m in tables]).encode()).hexdigest()
    def test_rejected_rewrite_exact_hash_and_null_unique_constraint(self):
        self.save((self.draft,))
        before=self.fingerprint()
        with self.assertRaises(ValidationError): self.save(())
        self.assertEqual(self.fingerprint(),before)
        row=BorradorReglaDerechos.objects.get()
        data={f.attname:getattr(row,f.attname) for f in row._meta.fields if f.name not in ("id","creado")}
        with self.assertRaises(IntegrityError):
            with transaction.atomic(): BorradorReglaDerechos.objects.create(**data)
        self.assertEqual(self.fingerprint(),before)
    def test_revocation_during_financier_lock_wait_is_revalidated(self):
        passed=Event()
        def guard(*args,**kwargs):
            result=requerir_financiador(*args,**kwargs)
            passed.set()
            return result
        def worker():
            close_old_connections()
            try:
                with patch("apps.financiadores.borradores_derechos.requerir_financiador",side_effect=guard):
                    try: self.save((self.draft,)); return "allowed"
                    except PermissionDenied: return "denied"
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Financiador.objects.select_for_update().get(pk=self.org.pk)
                future=pool.submit(worker)
                self.assertTrue(passed.wait(10))
                MembresiaFinanciador.objects.filter(pk=self.member.pk).update(activo=False)
            self.assertEqual(future.result(timeout=15),"denied")
        self.assertFalse(BorradorReglaDerechos.objects.exists())
        self.assertFalse(EventoCobertura.objects.exists())
    def test_additive_migration_preserves_existing_rows(self):
        executor=MigrationExecutor(connection)
        finales=executor.loader.graph.leaf_nodes("financiadores")
        executor.migrate([("financiadores","0017_saludpadron_codpar_ostel")])
        try:
            tables=["financiadores_financiador","financiadores_membresiafinanciador"]
            with connection.cursor() as cursor:
                before=[]
                for table in tables:
                    cursor.execute("SELECT * FROM "+table+" ORDER BY id")
                    before.append(cursor.fetchall())
            MigrationExecutor(connection).migrate([("financiadores","0018_borradorregladerechos")])
            with connection.cursor() as cursor:
                after=[]
                for table in tables:
                    cursor.execute("SELECT * FROM "+table+" ORDER BY id")
                    after.append(cursor.fetchall())
            self.assertEqual(after,before)
            MigrationExecutor(connection).migrate(finales)
            self.assertEqual(consultar_borradores(usuario=self.user,financiador_id=self.org.pk),())
        finally:
            MigrationExecutor(connection).migrate(finales)

    def preparar_preview(self):
        plan = Plan.objects.create(financiador=self.org, codigo="FICTICIO", nombre="Plan ficticio")
        client = APIClient()
        client.force_authenticate(self.user)
        url = f"/api/financiadores/{self.org.pk}/borradores-derechos/"
        regla = dict(codigo="literal", version=1, fuente="Fuente ficticia", regimen="dependencia",
                     plan_id=plan.pk, desde="2030-01-01", hasta=None, plazo_dias_corridos=7)
        cuerpo = dict(propuesta=[regla], motivo="Ficticio", regimen="dependencia", plan_id=plan.pk,
                      fecha="2030-01-08")
        self.assertEqual(client.post(url, cuerpo, format="json").status_code, 200)
        return plan, client, url, regla, cuerpo

    def huella_preview(self):
        modelos = (Financiador, MembresiaFinanciador, Plan, Afiliado, BorradorReglaDerechos, EventoCobertura)
        return hashlib.sha256(repr([list(m.objects.order_by("pk").values()) for m in modelos]).encode()).hexdigest()

    def test_preview_no_espera_locks_de_guardado_ni_cambia_datos(self):
        plan, _, url, regla, cuerpo = self.preparar_preview()
        propuesta = cuerpo | {"propuesta": [regla, regla | {"version": 2, "plazo_dias_corridos": 0}]}
        antes = self.huella_preview()
        def consultar():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.user)
                r = client.post(url + "previsualizar/", propuesta, format="json")
                return r.status_code, r.json()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Financiador.objects.select_for_update().get(pk=self.org.pk)
                Plan.objects.select_for_update().get(pk=plan.pk)
                estado, datos = pool.submit(consultar).result(timeout=5)
        self.assertEqual(estado, 200)
        self.assertEqual(set(datos), {"nuevas", "antes", "despues"})
        self.assertEqual(datos["despues"], {"coincidencias": propuesta["propuesta"], "conflicto": True})
        self.assertEqual(self.huella_preview(), antes)

    def test_preview_obsoleto_y_guardado_rechazados_conservan_huella(self):
        _, client, url, regla, cuerpo = self.preparar_preview()
        propuesta = cuerpo | {"propuesta": [regla, regla | {"version": 2}]}
        antes = self.huella_preview()
        self.assertEqual(client.post(url + "previsualizar/", propuesta, format="json").status_code, 200)
        self.assertEqual(self.huella_preview(), antes)
        actual = cuerpo | {"propuesta": [regla, regla | {"version": 3}]}
        self.assertEqual(client.post(url, actual, format="json").status_code, 200)
        antes = self.huella_preview()
        for sufijo in ("previsualizar/", ""):
            self.assertEqual(client.post(url + sufijo, propuesta, format="json").status_code, 400)
            self.assertEqual(self.huella_preview(), antes)
