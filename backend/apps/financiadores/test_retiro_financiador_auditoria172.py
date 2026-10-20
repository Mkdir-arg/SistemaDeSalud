"""Retiro durable de pertenencias de financiador (#172, decisión 5 del 19/10).

Misma regla que K2: una baja, un borrado o un cambio de rol en el financiador A
cierra A para las sesiones abiertas antes, aunque después se reactive; el
financiador B, las instituciones y otros usuarios no cambian. Un login nuevo sí
ve A. Se usa login JWT real: `force_authenticate` no pasa por el autenticador
que fija el corte.
"""
from django.core.cache import caches
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion

from . import models as m

CLAVE = "Clave-sintetica-retiro-fin-172!"


class RetiroFinanciadorAuditoria172Tests(APITestCase):
    def setUp(self):
        caches["portal"].clear()
        self.a = m.Financiador.objects.create(nombre="Mutual A sintética", tipo="mutual")
        self.b = m.Financiador.objects.create(nombre="Mutual B sintética", tipo="mutual")
        self.institucion = Institucion.objects.create(nombre="Institución sintética")
        self.usuario = Usuario.objects.create_user("retiro-fin@example.test", CLAVE, nombre="Persona")
        self.en_a = m.MembresiaFinanciador.objects.create(financiador=self.a, usuario=self.usuario, rol="operador")
        m.MembresiaFinanciador.objects.create(financiador=self.b, usuario=self.usuario, rol="operador")
        Membresia.objects.create(usuario=self.usuario, institucion=self.institucion, rol=Membresia.Rol.ADMINISTRATIVO)
        self.admin_a = Usuario.objects.create_user("admin-fin-a@example.test", CLAVE, nombre="Admin A")
        m.MembresiaFinanciador.objects.create(financiador=self.a, usuario=self.admin_a, rol="admin")
        self.client = APIClient()

    def login(self, usuario=None):
        respuesta = self.client.post("/api/auth/token/", {
            "email": (usuario or self.usuario).email, "password": CLAVE,
        }, format="json")
        self.assertEqual(respuesta.status_code, 200)
        return dict(respuesta.data)

    def get(self, par, ruta):
        return self.client.get(ruta, HTTP_AUTHORIZATION=f"Bearer {par['access']}")

    def vistos(self, par):
        """Financiadores según /me, el listado, el detalle y una acción con permiso."""
        me = self.get(par, "/api/usuarios/me/")
        self.assertEqual(me.status_code, 200)
        listado = self.get(par, "/api/financiadores/")
        self.assertEqual(listado.status_code, 200)
        return {
            "me": {f["id"] for f in me.data["financiadores"]},
            "instituciones": set(me.data["roles_por_institucion"]),
            "listado": {f["id"] for f in listado.data["results"]},
            "detalle": {f.pk for f in (self.a, self.b) if self.get(par, f"/api/financiadores/{f.pk}/").status_code == 200},
            "planes": {f.pk for f in (self.a, self.b) if self.get(par, f"/api/financiadores/{f.pk}/planes/").status_code == 200},
        }

    def esperado(self, *financiadores):
        ids = {f.pk for f in financiadores}
        return {"me": ids, "instituciones": {str(self.institucion.pk)}, "listado": ids, "detalle": ids, "planes": ids}

    def designar(self, par, activo, rol="operador"):
        return self.client.post(f"/api/financiadores/{self.a.pk}/usuarios/", {
            "email": self.usuario.email, "nombre": self.usuario.nombre, "rol": rol, "activo": activo,
        }, format="json", HTTP_AUTHORIZATION=f"Bearer {par['access']}")

    def test_reactivar_a_no_rehabilita_la_sesion_anterior_y_b_sigue_disponible(self):
        sesion = self.login()
        admin = self.login(self.admin_a)
        self.assertEqual(self.vistos(sesion), self.esperado(self.a, self.b))

        self.assertEqual(self.designar(admin, False).status_code, 201)
        self.assertEqual(self.designar(admin, True).status_code, 201)
        self.assertEqual(self.vistos(sesion), self.esperado(self.b))

        # Renovar conserva la misma sesión: no recupera A.
        renovada = self.client.post("/api/auth/token/refresh/", {"refresh": sesion["refresh"]}, format="json")
        self.assertEqual(renovada.status_code, 200)
        self.assertEqual(self.vistos(dict(renovada.data)), self.esperado(self.b))

        # Un login nuevo vuelve a ver A; el admin de A nunca perdió su acceso.
        self.assertEqual(self.vistos(self.login()), self.esperado(self.a, self.b))
        me_admin = self.get(admin, "/api/usuarios/me/")
        self.assertEqual({f["id"] for f in me_admin.data["financiadores"]}, {self.a.pk})

    def test_borrar_y_recrear_o_cambiar_rol_tambien_cortan_a(self):
        sesion = self.login()
        self.en_a.delete()
        m.MembresiaFinanciador.objects.create(financiador=self.a, usuario=self.usuario, rol="operador")
        self.assertEqual(self.vistos(sesion), self.esperado(self.b))

        otra = self.login()
        self.assertEqual(self.vistos(otra), self.esperado(self.a, self.b))
        membresia = m.MembresiaFinanciador.objects.get(usuario=self.usuario, financiador=self.a)
        membresia.rol = "auditor"
        membresia.save()
        self.assertEqual(self.vistos(otra), self.esperado(self.b))
        self.assertEqual(self.vistos(self.login()), self.esperado(self.a, self.b))

    def test_baja_anterior_al_login_no_corta_y_el_corte_no_sale_de_la_solicitud(self):
        self.en_a.activo = False
        self.en_a.save()
        self.en_a.activo = True
        self.en_a.save()
        sesion = self.login()
        self.assertEqual(self.vistos(sesion), self.esperado(self.a, self.b))

        self.en_a.activo = False
        self.en_a.save()
        self.en_a.activo = True
        self.en_a.save()
        self.assertEqual(self.vistos(sesion), self.esperado(self.b))
        # Fuera de una solicitud (worker, comando) no queda corte aplicado.
        self.assertEqual(m.MembresiaFinanciador.objects.filter(usuario=self.usuario, activo=True).count(), 2)

    def test_cambios_que_no_retiran_no_registran_bajas(self):
        from .models import BajaMembresiaFinanciador

        sesion = self.login()
        self.en_a.resuelve_autorizaciones = True
        self.en_a.save()
        inactiva = m.MembresiaFinanciador.objects.create(financiador=self.b, usuario=self.admin_a, rol="operador", activo=False)
        inactiva.delete()
        self.assertFalse(BajaMembresiaFinanciador.objects.exists())
        self.assertEqual(self.vistos(sesion), self.esperado(self.a, self.b))
        self.en_a.activo = False
        self.en_a.save()
        self.assertEqual(list(BajaMembresiaFinanciador.objects.values_list("usuario_id", "financiador_id")),
                         [(self.usuario.pk, self.a.pk)])
