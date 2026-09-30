"""`preparar_cuentas_referencia`: idempotente, sin credenciales y apto para producción."""
from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Membresia, Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.instituciones.models import Area, Grupo, Institucion

from .models import CuentaReferencia
from .perfiles import DOMINIO


def preparar(**opciones):
    salida = StringIO()
    call_command("preparar_cuentas_referencia", stdout=salida, **opciones)
    return salida.getvalue()


class PrepararCuentasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Institucion.objects.create(nombre="Hospital A")
        cls.guardia = Area.objects.create(institucion=cls.a, nombre="Guardia")
        cls.pediatria = Area.objects.create(institucion=cls.a, nombre="Pediatría")
        cls.enfermera = Usuario.objects.create_user("enfermera@a.local", "x", nombre="Enfermera")
        m = Membresia.objects.create(usuario=cls.enfermera, institucion=cls.a, rol="enfermeria")
        m.areas.add(cls.guardia)
        cls.triage = Grupo.objects.create(area=cls.guardia, nombre="Triage")
        cls.triage.miembros.add(cls.enfermera)
        cls.medicos = Grupo.objects.create(area=cls.pediatria, nombre="Médicos de pediatría")
        cls.f = Financiador.objects.create(nombre="Obra F", tipo="obra_social")

    def test_crea_las_cuentas_sin_credenciales_ni_privilegios(self):
        preparar(institucion=[self.a.pk], financiador=[self.f.pk], ancla_estatal=self.a.pk)
        self.assertEqual(CuentaReferencia.objects.count(), 2 + 7 + 3)
        for ref in CuentaReferencia.objects.select_related("usuario"):
            u = ref.usuario
            self.assertFalse(u.has_usable_password(), u.email)
            self.assertFalse(u.is_staff or u.is_superuser, u.email)
            self.assertTrue(u.email.endswith(f"@{DOMINIO}"), u.email)
            self.assertEqual(u.nombre, "Superusuario")
        enfermeria = CuentaReferencia.objects.get(ambito="institucion", rol="enfermeria", institucion=self.a).usuario
        self.assertEqual(enfermeria.nombre_completo, "Superusuario Enfermería")
        self.assertEqual(list(enfermeria.membresias.values_list("institucion_id", "rol", "activo")),
                         [(self.a.pk, "enfermeria", True)])
        plataforma = CuentaReferencia.objects.get(ambito="plataforma", rol="plataforma").usuario
        self.assertEqual(list(plataforma.membresias.values_list("institucion_id", "rol")), [(None, "plataforma")])

    def test_los_perfiles_estatales_no_necesitan_institucion(self):
        self.a.delete()
        preparar(estatales=True)
        self.assertEqual(CuentaReferencia.objects.filter(ambito="plataforma", institucion__isnull=True).count(), 2)

    def test_solo_el_operador_queda_designado_para_resolver_autorizaciones(self):
        preparar(financiador=[self.f.pk])
        designados = dict(MembresiaFinanciador.objects.filter(financiador=self.f).values_list("rol", "resuelve_autorizaciones"))
        self.assertEqual(designados, {"admin": False, "operador": True, "auditor": False})

    def test_es_idempotente(self):
        preparar(institucion=[self.a.pk], financiador=[self.f.pk], ancla_estatal=self.a.pk)
        foto = (Usuario.objects.count(), Membresia.objects.count(), MembresiaFinanciador.objects.count(),
                sorted(Usuario.objects.values_list("pk", "password")))
        salida = preparar(institucion=[self.a.pk], financiador=[self.f.pk], ancla_estatal=self.a.pk)
        self.assertEqual(foto, (Usuario.objects.count(), Membresia.objects.count(), MembresiaFinanciador.objects.count(),
                                sorted(Usuario.objects.values_list("pk", "password"))))
        self.assertEqual(salida.count("sin cambios"), 12)

    def test_copia_areas_y_grupos_de_sus_pares_sin_quitar_los_propios(self):
        preparar(institucion=[self.a.pk])
        cuenta = CuentaReferencia.objects.get(rol="enfermeria", institucion=self.a).usuario
        self.assertEqual(set(cuenta.membresias.get().areas.all()), {self.guardia})
        self.assertEqual(set(cuenta.grupos.all()), {self.triage})
        medico = CuentaReferencia.objects.get(rol="medico", institucion=self.a).usuario
        self.assertFalse(medico.grupos.exists())
        # Lo que agregue la institución a mano se conserva.
        self.medicos.miembros.add(cuenta)
        preparar(institucion=[self.a.pk])
        self.assertEqual(set(cuenta.grupos.all()), {self.triage, self.medicos})

    def test_restablece_una_cuenta_alterada(self):
        preparar(institucion=[self.a.pk])
        cuenta = CuentaReferencia.objects.get(rol="enfermeria", institucion=self.a).usuario
        cuenta.set_password("una-clave-larga-123")
        cuenta.is_staff = True
        cuenta.save()
        otra = Institucion.objects.create(nombre="Hospital B")
        Membresia.objects.create(usuario=cuenta, institucion=otra, rol="admin")
        Membresia.objects.filter(usuario=cuenta, institucion=self.a).update(activo=False)
        salida = preparar(institucion=[self.a.pk])
        self.assertIn("actualizada", salida)
        cuenta.refresh_from_db()
        self.assertFalse(cuenta.has_usable_password() or cuenta.is_staff)
        self.assertEqual(list(cuenta.membresias.filter(activo=True).values_list("institucion_id", "rol")),
                         [(self.a.pk, "enfermeria")])

    def test_verificar_no_escribe_y_falla_si_falta_algo(self):
        with self.assertRaises(CommandError):
            preparar(institucion=[self.a.pk], verificar=True)
        self.assertFalse(CuentaReferencia.objects.exists())
        self.assertFalse(Usuario.objects.filter(email__endswith=f"@{DOMINIO}").exists())
        preparar(institucion=[self.a.pk])
        self.assertIn("están listas", preparar(institucion=[self.a.pk], verificar=True))

    def test_sin_ambitos_no_hace_nada(self):
        with self.assertRaises(CommandError):
            preparar()
        with self.assertRaises(CommandError):
            preparar(institucion=[999999])
        self.assertFalse(CuentaReferencia.objects.exists())

    def test_no_adopta_un_correo_de_otra_cuenta(self):
        Usuario.objects.create_superuser(f"enfermeria.i{self.a.pk}@{DOMINIO}", "x", nombre="Intruso")
        with self.assertRaises(CommandError):
            preparar(institucion=[self.a.pk])
        self.assertFalse(CuentaReferencia.objects.exists())

    def test_no_convierte_una_cuenta_comun_que_ocupa_el_correo_reservado(self):
        usuario = Usuario.objects.create_user(f"enfermeria.i{self.a.pk}@{DOMINIO}", "clave-123", nombre="Existente")
        with self.assertRaises(CommandError):
            preparar(institucion=[self.a.pk])
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("clave-123"))
        self.assertEqual(usuario.nombre, "Existente")
        self.assertFalse(CuentaReferencia.objects.exists())

    @override_settings(ENTORNO="produccion")
    def test_corre_en_produccion(self):
        preparar(institucion=[self.a.pk], ancla_estatal=self.a.pk)
        self.assertEqual(CuentaReferencia.objects.count(), 2 + 7)
