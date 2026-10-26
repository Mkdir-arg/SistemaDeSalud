"""Diccionario de códigos por financiador: carga idempotente y admin restringido.

Las planillas se arman en memoria con códigos del diccionario OSTEL, que no
contiene datos personales.
"""
from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from apps.accounts.models import Usuario
from .models import CodigoFinanciador, Financiador

PARENTESCOS = ("CODPAR", "DESCRI", "GRUPO", "VENCE", "MOTIVO", "TITULAR", "PMI", "ACTIVO", "CODSSS",
               "QUIEN", "FECMOD", "PAR", "CODAFIP", "MARCA", "USADO")
CATALOGO = ("TABLA", "CODIGO", "DESCRIP", "VALOR", "LOGICO", "USADO", "FILTRO", "ACTIVO", "CODSSS")


def diccionario(parentescos=None, catalogo=None, hojas=("Parentescos", "Catalogo_completo")):
    parentescos = parentescos if parentescos is not None else [
        ("AAA", "TITULAR", "X", None, None, True, True, True, "00", "AFILIA", datetime(1998, 1, 1), "00", None, None, None),
        ("H01", "HIJO / HIJA", "X", 21, "06", None, True, True, "03", "AFILIA", datetime(1998, 1, 1), "10", 2, None, None),
        ("HE2", "HERMANO / HERMANA", None, None, None, None, None, False, None, "AFILIA", datetime(1998, 1, 1), None, 7, "*", None),
    ]
    catalogo = catalogo if catalogo is not None else [
        ("03", "4", "DU", 0, None, None, None, True, "DU"),
        ("02", "06", "MAYOR DE EDAD", None, True, None, None, True, None),
        ("05", "1", "SOLTERO", 0, None, None, None, True, None),
        ("12", None, "DESCONOCIDO", 0, False, False, None, True, "00"),
    ]
    libro = Workbook()
    libro.remove(libro.active)
    for nombre, encabezado, filas in (("Parentescos", PARENTESCOS, parentescos), ("Catalogo_completo", CATALOGO, catalogo)):
        if nombre not in hojas:
            continue
        hoja = libro.create_sheet(nombre)
        hoja.append(encabezado)
        for fila in filas:
            hoja.append(fila)
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


class CargaDiccionarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Financiador.objects.create(nombre="OSTEL ficticia", tipo="obra_social")
        cls.otra = Financiador.objects.create(nombre="Otra ficticia", tipo="mutual")

    def cargar(self, contenido, financiador=None):
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "diccionario.xlsx"
            ruta.write_bytes(contenido)
            salida = StringIO()
            call_command("cargar_diccionario_ostel", str(ruta), financiador=(financiador or self.org).pk, stdout=salida)
            return salida.getvalue()

    def test_carga_tablas_y_atributos_y_es_idempotente(self):
        self.assertIn("creados: 6", self.cargar(diccionario()))
        self.assertIn("filas_sin_codigo: 1", self.cargar(diccionario()))
        self.assertIn("sin_cambios: 6", self.cargar(diccionario()))
        self.assertEqual(CodigoFinanciador.objects.count(), 6)
        hijo = CodigoFinanciador.objects.get(financiador=self.org, tabla="parentescos", codigo="H01")
        self.assertEqual(hijo.descripcion, "HIJO / HIJA")
        self.assertEqual((hijo.atributos["VENCE"], hijo.atributos["MOTIVO"], hijo.atributos["CODSSS"]), (21, "06", "03"))
        self.assertEqual(hijo.atributos["FECMOD"], "1998-01-01T00:00:00")
        self.assertFalse(CodigoFinanciador.objects.get(tabla="parentescos", codigo="HE2").activo)
        self.assertEqual(set(CodigoFinanciador.objects.values_list("tabla", flat=True)),
                         {"parentescos", "tipos_documento", "motivos_baja", "ostel_05"})

    def test_actualiza_sin_borrar_ausentes_y_aisla_financiadores(self):
        self.cargar(diccionario())
        salida = self.cargar(diccionario(
            parentescos=[("AAA", "TITULAR DEL GRUPO", "X", None, None, True, True, True, "00",
                          "AFILIA", datetime(1998, 1, 1), "00", None, None, None)],
            catalogo=[]))
        self.assertIn("actualizados: 1", salida)
        self.assertIn("no_informados: 5", salida)
        self.assertEqual(CodigoFinanciador.objects.filter(financiador=self.org).count(), 6)
        self.assertEqual(CodigoFinanciador.objects.get(codigo="AAA").descripcion, "TITULAR DEL GRUPO")
        self.cargar(diccionario(), financiador=self.otra)
        self.assertEqual(CodigoFinanciador.objects.filter(financiador=self.otra).count(), 6)

    def test_errores_de_estructura_no_cargan_nada(self):
        for contenido in (diccionario(hojas=("Parentescos",)), b"no es xlsx",
                          diccionario(catalogo=[("03", "4", "DU", 0, None, None, None, True, "DU")] * 2)):
            with self.subTest(contenido=contenido[:10]), self.assertRaises(CommandError):
                self.cargar(contenido)
        self.assertFalse(CodigoFinanciador.objects.exists())
        with self.assertRaises(CommandError):
            call_command("cargar_diccionario_ostel", "no-existe.xlsx", financiador=self.org.pk)

    def test_unicidad_por_financiador_tabla_codigo(self):
        CodigoFinanciador.objects.create(financiador=self.org, tabla="parentescos", codigo="AAA")
        with self.assertRaises(IntegrityError):
            CodigoFinanciador.objects.create(financiador=self.org, tabla="parentescos", codigo="AAA")


class AdminCodigosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Financiador.objects.create(nombre="OSTEL ficticia", tipo="obra_social")
        cls.codigo = CodigoFinanciador.objects.create(financiador=cls.org, tabla="parentescos", codigo="H01",
                                                      descripcion="HIJO / HIJA")
        cls.root = Usuario.objects.create_superuser("root-codigos@example.invalid", "x", nombre="Root")
        cls.staff = Usuario.objects.create_user("staff-codigos@example.invalid", "x", nombre="Staff", is_staff=True)
        cls.staff.user_permissions.add(*Permission.objects.filter(codename__endswith="codigofinanciador"))

    def test_superusuario_lista_busca_y_filtra(self):
        self.client.force_login(self.root)
        url = reverse("admin:financiadores_codigofinanciador_changelist")
        respuesta = self.client.get(url, {"q": "HIJO", "tabla": "parentescos"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "HIJO / HIJA")
        cambio = reverse("admin:financiadores_codigofinanciador_change", args=[self.codigo.pk])
        self.assertEqual(self.client.get(cambio).status_code, 200)

    def test_staff_con_permisos_de_modelo_no_accede(self):
        self.client.force_login(self.staff)
        for nombre, args in (("changelist", []), ("change", [self.codigo.pk]), ("add", [])):
            with self.subTest(vista=nombre):
                respuesta = self.client.get(reverse(f"admin:financiadores_codigofinanciador_{nombre}", args=args))
                self.assertEqual(respuesta.status_code, 403)
