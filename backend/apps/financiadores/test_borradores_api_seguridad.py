"""Probes independientes de la API sobre PostgreSQL completamente ficticio."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless
from unittest.mock import patch
import hashlib
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections,connection
from rest_framework.test import APIClient
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador,MembresiaFinanciador,BorradorReglaDerechos,EventoCobertura,Plan
from apps.financiadores.permisos import requerir_financiador

@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL dedicado.")
class SeguridadBorradoresAPITests(TransactionTestCase):
    def setUp(self):
        self.org=Financiador.objects.create(nombre="Probe API ficticio",tipo="otro")
        self.other=Financiador.objects.create(nombre="Ajeno ficticio",tipo="otro")
        self.user=Usuario.objects.create_user("probe-api@example.invalid")
        self.member=MembresiaFinanciador.objects.create(financiador=self.org,usuario=self.user,rol="admin")
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.url=f"/api/financiadores/{self.org.pk}/borradores-derechos/"
        self.draft=dict(codigo="probe",version=1,fuente="Fuente ficticia",regimen="dependencia",plan_id=None,desde="2030-01-01",hasta=None)
        self.body=dict(propuesta=[self.draft],motivo="Probe ficticio",regimen="dependencia",plan_id=None,fecha="2030-01-01")
    def fingerprint(self):
        return hashlib.sha256(repr([list(m.objects.order_by("pk").values()) for m in (Financiador,MembresiaFinanciador,Plan,BorradorReglaDerechos,EventoCobertura)]).encode()).hexdigest()
    def test_unknown_identity_fields_and_unsupported_methods_preserve_hash(self):
        self.assertEqual(self.client.post(self.url,self.body,format="json").status_code,200)
        before=self.fingerprint()
        for field,value in [("usuario",self.user.pk),("rol","admin"),("creado_por",self.user.pk),("financiador_id",self.other.pk)]:
            for nested in (False,True):
                body=deepcopy(self.body)
                (body["propuesta"][0] if nested else body)[field]=value
                with self.subTest(field=field,nested=nested):
                    self.assertEqual(self.client.post(self.url,body,format="json").status_code,400)
                    self.assertEqual(self.fingerprint(),before)
        for method in ("put","patch","delete"):
            self.assertEqual(getattr(self.client,method)(self.url,self.body,format="json").status_code,405)
            self.assertEqual(self.fingerprint(),before)
    def test_request_url_and_authenticated_role_override_body(self):
        before=self.fingerprint()
        otherurl=f"/api/financiadores/{self.other.pk}/borradores-derechos/"
        self.assertEqual(self.client.post(otherurl,self.body|dict(financiador_id=self.org.pk),format="json").status_code,404)
        self.member.rol="operador";self.member.save()
        before=self.fingerprint()
        self.assertEqual(self.client.post(self.url,self.body|dict(rol="admin"),format="json").status_code,403)
        self.assertEqual(self.fingerprint(),before)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url,self.body,format="json").status_code,401)
        self.assertEqual(self.fingerprint(),before)
    def test_post_rechecks_revocation_after_financier_wait(self):
        passed=Event()
        def guard(*args,**kwargs):
            result=requerir_financiador(*args,**kwargs);passed.set();return result
        def worker():
            close_old_connections()
            try:
                client=APIClient();client.force_authenticate(self.user)
                with patch("apps.financiadores.borradores_derechos.requerir_financiador",side_effect=guard):
                    return client.post(self.url,self.body,format="json").status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Financiador.objects.select_for_update().get(pk=self.org.pk)
                result=pool.submit(worker)
                self.assertTrue(passed.wait(10))
                MembresiaFinanciador.objects.filter(pk=self.member.pk).update(activo=False)
            self.assertEqual(result.result(timeout=15),403)
        self.assertFalse(BorradorReglaDerechos.objects.exists())
        self.assertFalse(EventoCobertura.objects.exists())
