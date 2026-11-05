"""Borradores persistidos sólo sobre fixtures completamente ficticios."""
from dataclasses import replace
from datetime import date
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from apps.accounts.models import Usuario
from .models import Financiador, MembresiaFinanciador, Plan, EventoCobertura, BorradorReglaDerechos, Afiliado
from .derechos_borrador import BorradorDerechos
from .borradores_derechos import consultar_borradores, guardar_borradores


class BorradoresPersistidosTests(TestCase):
    def setUp(self):
        self.org = Financiador.objects.create(nombre="Financiador ficticio", tipo="obra_social")
        self.user = Usuario.objects.create_user("borradores@example.invalid")
        self.member = MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="admin")
        self.plan = Plan.objects.create(financiador=self.org, codigo="FICTICIO", nombre="Plan ficticio")

    def borrador(self, version=1, **cambios):
        datos = dict(codigo="ejemplo", version=version, fuente="Fuente ficticia",
                     financiador_id=self.org.pk, regimen="dependencia", plan_id=self.plan.pk,
                     desde=date(2030, 1, 1), hasta=date(2030, 2, 1))
        return BorradorDerechos(**(datos | cambios))

    def guardar(self, propuesta, **cambios):
        datos = dict(usuario=self.user, financiador_id=self.org.pk, propuesta=propuesta,
                     motivo="Prueba ficticia", regimen="dependencia", plan_id=self.plan.pk,
                     fecha=date(2030, 1, 15))
        return guardar_borradores(**(datos | cambios))

    def test_guarda_y_consulta_con_autoria_sin_activar(self):
        regla = self.borrador()
        resultado = self.guardar((regla,))
        self.assertEqual(resultado.nuevas, (regla,))
        self.assertEqual(consultar_borradores(usuario=self.user, financiador_id=self.org.pk), (regla,))
        evento = EventoCobertura.objects.get(accion="crear_borrador_derechos")
        self.assertEqual((evento.usuario_id, evento.financiador_id, evento.motivo),
                         (self.user.pk, self.org.pk, "Prueba ficticia"))
        self.assertEqual(self.guardar((regla,)).nuevas, ())
        self.assertEqual(EventoCobertura.objects.filter(accion="crear_borrador_derechos").count(), 1)

    def test_contexto_identificador_estricto(self):
        with self.assertRaises(ValidationError):
            consultar_borradores(usuario=self.user, financiador_id=True)

    def test_roles_aislamiento_y_rechazos_no_cambian_historia(self):
        regla = self.borrador()
        self.guardar((regla,))
        for rol in ("operador", "auditor"):
            self.member.rol = rol
            self.member.save()
            self.assertEqual(consultar_borradores(usuario=self.user, financiador_id=self.org.pk), (regla,))
            with self.assertRaises(PermissionDenied):
                self.guardar((regla, self.borrador(2)))
        self.member.activo = False
        self.member.save()
        with self.assertRaises(PermissionDenied):
            consultar_borradores(usuario=self.user, financiador_id=self.org.pk)
        self.member.activo, self.member.rol = True, "admin"
        self.member.save()
        ajeno = Financiador.objects.create(nombre="Otro ficticio", tipo="otro")
        plan_ajeno = Plan.objects.create(financiador=ajeno, codigo="OTRO", nombre="Otro")
        for cambio in (dict(plan_id=plan_ajeno.pk), dict(regimen="inventado"),
                       dict(fuente="x" * 256), dict(financiador_id=ajeno.pk)):
            with self.subTest(cambio=cambio), self.assertRaises(ValidationError):
                self.guardar((regla, self.borrador(2, **cambio)))
        for propuesta in ((), (replace(regla, fuente="Reescritura"),), (regla, regla)):
            with self.subTest(propuesta=propuesta), self.assertRaises(ValidationError):
                self.guardar(propuesta)
        with self.assertRaises(ValidationError):
            self.guardar((regla,), motivo=" ")
        with self.assertRaises(PermissionDenied):
            consultar_borradores(usuario=self.user, financiador_id=ajeno.pk)
        self.assertEqual(consultar_borradores(usuario=self.user, financiador_id=self.org.pk), (regla,))
        self.assertEqual(EventoCobertura.objects.filter(accion="crear_borrador_derechos").count(), 1)

    def test_historia_autoria_y_ausencia_de_efectos_prestacionales(self):
        afiliado = Afiliado.objects.create(financiador=self.org, numero="FICTICIO", documento="FICTICIO",
                                          nombre="Persona ficticia", desde=date(2029, 1, 1))
        antes = Afiliado.objects.values().get(pk=afiliado.pk)
        primera = self.borrador(plan_id=None)
        segunda = self.borrador(2, plan_id=None, desde=date(2030, 2, 1), hasta=None)
        self.guardar((primera,))
        self.guardar((segunda, primera))
        self.assertEqual(consultar_borradores(usuario=self.user, financiador_id=self.org.pk), (primera, segunda))
        filas = list(BorradorReglaDerechos.objects.values_list("creado_por_id", "motivo"))
        self.assertEqual(filas, [(self.user.pk, "Prueba ficticia")] * 2)
        self.assertEqual(Afiliado.objects.values().get(pk=afiliado.pk), antes)
        with self.assertRaises(ValidationError):
            self.guardar((primera, self.borrador(3, plan_id=None)))

    def test_fallo_auditoria_revierte_todas_las_versiones_de_propuesta(self):
        original = EventoCobertura.objects.create
        llamadas = 0
        def fallo_segundo(**datos):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise RuntimeError("Fallo ficticio")
            return original(**datos)
        with patch("apps.financiadores.services.EventoCobertura.objects.create", side_effect=fallo_segundo):
            with self.assertRaises(RuntimeError):
                self.guardar((self.borrador(), self.borrador(2)))
        self.assertEqual(consultar_borradores(usuario=self.user, financiador_id=self.org.pk), ())
        self.assertFalse(EventoCobertura.objects.filter(accion="crear_borrador_derechos").exists())


@skipUnless(connection.vendor == "postgresql", "Requiere PostgreSQL dedicado para locks reales.")
class ConcurrenciaBorradoresTests(TransactionTestCase):
    def setUp(self):
        self.org = Financiador.objects.create(nombre="Concurrencia ficticia", tipo="otro")
        self.user = Usuario.objects.create_user("carrera-borradores@example.invalid")
        MembresiaFinanciador.objects.create(financiador=self.org, usuario=self.user, rol="admin")

    def carrera(self, fuentes):
        barrera = Barrier(2)
        def guardar(fuente):
            close_old_connections()
            try:
                borrador = BorradorDerechos("ejemplo", 1, fuente, self.org.pk,
                                           "dependencia", None, date(2030, 1, 1))
                barrera.wait(timeout=10)
                try:
                    guardar_borradores(usuario=self.user, financiador_id=self.org.pk,
                        propuesta=(borrador,), motivo="Carrera ficticia", regimen="dependencia",
                        plan_id=None, fecha=date(2030, 1, 1))
                    return "aceptado"
                except ValidationError:
                    return "rechazado"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futuros = [pool.submit(guardar, fuente) for fuente in fuentes]
            resultados = [f.result(timeout=20) for f in futuros]
        self.assertEqual(BorradorReglaDerechos.objects.count(), 1)
        self.assertEqual(EventoCobertura.objects.filter(accion="crear_borrador_derechos").count(), 1)
        self.assertEqual(len(consultar_borradores(usuario=self.user, financiador_id=self.org.pk)), 1)
        return resultados

    def test_propuestas_contradictorias_no_reescriben_version(self):
        self.assertCountEqual(self.carrera(("Fuente ficticia A", "Fuente ficticia B")),
                              ["aceptado", "rechazado"])

    def test_reintento_identico_no_duplica_version_ni_auditoria(self):
        self.assertEqual(self.carrera(("Fuente ficticia", "Fuente ficticia")),
                         ["aceptado", "aceptado"])
