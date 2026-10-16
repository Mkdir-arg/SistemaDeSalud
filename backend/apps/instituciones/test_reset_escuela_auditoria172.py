"""Regresiones sintéticas de la contención de AUD-047."""
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Membresia, Usuario
from apps.auditoria.models import AccesoClinico
from apps.casos.models import Caso
from apps.farmacia.models import Deposito, Existencia, Insumo, Movimiento
from apps.finanzas.models import AccesoFinanciero
from apps.flujos.models import Flujo, VersionFlujo
from apps.registros.models import Ciudadano

from .models import Area, Institucion


@override_settings(ENTORNO="demo")
class ResetEscuelaAuditoria172Tests(APITestCase):
    def setUp(self):
        self.escuela = Institucion.objects.create(nombre="Hospital Escuela Salud")
        self.otra = Institucion.objects.create(nombre="Institución ajena")
        self.area = Area.objects.create(institucion=self.escuela, nombre="Práctica")
        self.admin = Usuario.objects.create_superuser("reset-admin@test.local", "x")
        self.client.force_authenticate(self.admin)
        self.url = f"/api/instituciones/{self.escuela.pk}/reset-escuela/"

    def usuario(self, email, institucion=None, **atributos):
        usuario = Usuario.objects.create_user(email, "x", **atributos)
        if institucion:
            Membresia.objects.create(
                usuario=usuario, institucion=institucion, rol=Membresia.Rol.MEDICO,
            )
        return usuario

    def test_produccion_y_desarrollo_rechazan_sin_borrar(self):
        for entorno in ("produccion", "desarrollo"):
            with self.subTest(entorno=entorno), override_settings(ENTORNO=entorno):
                respuesta = self.client.post(self.url)
                self.assertEqual(respuesta.status_code, 403, respuesta.data)
                self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())
                self.assertTrue(Institucion.objects.filter(pk=self.escuela.pk).exists())

    def test_protect_revierte_todos_los_borrados_previos(self):
        paciente = Ciudadano.objects.create(
            institucion=self.escuela, nombre="Paciente", apellido="Sintético",
            documento="90017201",
        )
        acceso = AccesoClinico.objects.create(
            usuario=self.admin, ciudadano=paciente, institucion=self.escuela,
        )
        practica = self.usuario("escuela.rollback@salud.local", self.escuela)
        membresia = practica.membresias.get()
        flujo = Flujo.objects.create(
            institucion=self.escuela, area=self.area, titulo="Práctica sintética",
        )
        version = VersionFlujo.objects.create(flujo=flujo, numero=1)
        caso = Caso.objects.create(
            institucion=self.escuela, version=version, ciudadano=paciente,
            area_actual=self.area, asignado_a=practica,
        )
        insumo = Insumo.objects.create(
            institucion=self.escuela, nombre="Insumo sintético", requiere_lote=False,
        )
        deposito = Deposito.objects.create(
            institucion=self.escuela, area=self.area, nombre="Depósito sintético",
        )
        existencia = Existencia.objects.create(
            deposito=deposito, insumo=insumo, cantidad=7,
        )
        movimiento = Movimiento.objects.create(
            tipo=Movimiento.Tipo.INGRESO, insumo=insumo, destino=deposito,
            cantidad=7, caso=caso, autor=practica, motivo="Fixture sintético AUD-047",
        )
        protegido = AccesoFinanciero.objects.create(
            usuario=self.admin, institucion=self.escuela, recurso="prueba", accion="leer",
        )
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        for modelo, pk in (
            (Institucion, self.escuela.pk), (Area, self.area.pk),
            (Ciudadano, paciente.pk), (AccesoClinico, acceso.pk),
            (Usuario, practica.pk), (Membresia, membresia.pk),
            (AccesoFinanciero, protegido.pk),
            (Flujo, flujo.pk), (VersionFlujo, version.pk), (Caso, caso.pk),
            (Insumo, insumo.pk), (Deposito, deposito.pk),
            (Existencia, existencia.pk), (Movimiento, movimiento.pk),
        ):
            self.assertTrue(modelo.objects.filter(pk=pk).exists(), modelo._meta.label)
        caso.refresh_from_db()
        movimiento.refresh_from_db()
        existencia.refresh_from_db()
        self.assertEqual(caso.version_id, version.pk)
        self.assertEqual(caso.ciudadano_id, paciente.pk)
        self.assertEqual(caso.asignado_a_id, practica.pk)
        self.assertEqual(movimiento.caso_id, caso.pk)
        self.assertEqual(movimiento.autor_id, practica.pk)
        self.assertEqual(movimiento.insumo_id, insumo.pk)
        self.assertEqual(movimiento.destino_id, deposito.pk)
        self.assertEqual(movimiento.cantidad, 7)
        self.assertEqual(existencia.cantidad, movimiento.cantidad)
        self.assertEqual(existencia.insumo_id, insumo.pk)
        self.assertEqual(existencia.deposito_id, deposito.pk)

    def test_prefijo_no_borra_cuentas_ajenas_compartidas_o_privilegiadas(self):
        ajeno = self.usuario("escuela.ajeno@salud.local", self.otra)
        sin_membresia = self.usuario("escuela.sin-membresia@salud.local")
        compartido = self.usuario("escuela.compartido@salud.local", self.escuela)
        Membresia.objects.create(
            usuario=compartido, institucion=self.otra, rol=Membresia.Rol.MEDICO,
        )
        staff = self.usuario("escuela.staff@salud.local", self.escuela, is_staff=True)
        global_ = self.usuario("escuela.global@salud.local", self.escuela)
        Membresia.objects.create(usuario=global_, rol=Membresia.Rol.AUDITOR)
        privilegiado = self.usuario("escuela.admin@salud.local", self.escuela)
        Membresia.objects.create(
            usuario=privilegiado, institucion=self.escuela, rol=Membresia.Rol.ADMIN_INSTITUCION,
        )
        practica = self.usuario("escuela.practica@salud.local", self.escuela)
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(Usuario.objects.filter(pk=practica.pk).exists())
        for usuario in (ajeno, sin_membresia, compartido, staff, global_, privilegiado):
            self.assertTrue(Usuario.objects.filter(pk=usuario.pk).exists(), usuario.email)
        self.assertTrue(compartido.membresias.filter(institucion=self.otra).exists())

    def test_cuenta_compartida_con_acceso_ajeno_no_pierde_auditoria(self):
        compartido = self.usuario("escuela.lectura@salud.local", self.escuela)
        Membresia.objects.create(
            usuario=compartido, institucion=self.otra, rol=Membresia.Rol.MEDICO,
        )
        acceso = AccesoClinico.objects.create(usuario=compartido, institucion=self.otra)
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertTrue(AccesoClinico.objects.filter(pk=acceso.pk).exists())

    def test_acceso_ajeno_de_candidato_a_borrado_provoca_rollback(self):
        practica = self.usuario("escuela.auditada@salud.local", self.escuela)
        acceso = AccesoClinico.objects.create(usuario=practica, institucion=self.otra)
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertTrue(AccesoClinico.objects.filter(pk=acceso.pk).exists())
        self.assertTrue(Usuario.objects.filter(pk=practica.pk).exists())
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())

    def test_nombre_distinto_no_habilita_reset(self):
        self.escuela.nombre = "Escuela renombrada"
        self.escuela.save(update_fields=["nombre"])
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())

    def test_miembro_no_superusuario_no_puede_resetear(self):
        usuario = self.usuario("plataforma@test.local")
        Membresia.objects.create(usuario=usuario, rol=Membresia.Rol.PLATAFORMA)
        self.client.force_authenticate(usuario)
        respuesta = self.client.post(self.url)
        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertTrue(Area.objects.filter(pk=self.area.pk).exists())
