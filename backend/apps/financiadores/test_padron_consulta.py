from datetime import timedelta
import unicodedata

from django.core.paginator import Paginator
from django.http import QueryDict
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import models as m
from .padron import CAMPOS_GENERALES, estado_administrativo
from .padron_consulta import COLUMNAS_PADRON, consultar_padron, validar_columnas_padron, valor_columna_padron


class ConsultaPadronTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.org = m.Financiador.objects.create(nombre="Organización ficticia A", tipo="obra_social")
        self.otra = m.Financiador.objects.create(nombre="Organización ficticia B", tipo="obra_social")
        self.plan = m.Plan.objects.create(financiador=self.org, codigo="BASE", nombre="Plan A", tipo="base")
        self.filas = [m.Afiliado.objects.create(
            financiador=self.org, numero=f"00{i}", documento=f"9000000{i}", nombre=nombre,
            desde=self.hoy, plan=self.plan if i != 3 else None,
            localidad="Río" if i < 3 else "Monte", alta_administrativa=self.hoy if i < 3 else None,
        ) for i, nombre in enumerate(["Zeta", "Alfa", "Alfa", "Beta"])]
        self.ajeno = m.Afiliado.objects.create(financiador=self.otra, numero="099", documento="80000000", nombre="Alfa", desde=self.hoy)

    def consulta(self, **parametros):
        return consultar_padron(financiador=self.org, parametros=parametros)

    def test_orden_global_ambas_direcciones_y_desempate_entre_paginas(self):
        for orden, indices in [("nombre", [1, 2, 3, 0]), ("-nombre", [0, 3, 1, 2])]:
            with self.subTest(orden=orden):
                paginador = Paginator(self.consulta(ordering=orden), 2)
                ids = [f.pk for p in (1, 2) for f in paginador.page(p)]
                self.assertEqual(ids, [self.filas[i].pk for i in indices])
        self.assertEqual(list(self.consulta().values_list("pk", flat=True)), [f.pk for f in self.filas])

    def test_cada_columna_ofrecida_tiene_orden_sql_ambos_sentidos(self):
        for clave in COLUMNAS_PADRON:
            for orden in (clave, f"-{clave}"):
                with self.subTest(orden=orden):
                    self.assertEqual(len(list(self.consulta(ordering=orden))), 4)

    def test_filtro_global_tipo_y_rangos(self):
        self.assertEqual(list(self.consulta(flt_localidad="río").values_list("pk", flat=True)), [self.filas[0].pk, self.filas[1].pk, self.filas[2].pk])
        self.assertEqual(self.consulta(flt_plan=str(self.plan.pk)).count(), 3)
        self.assertEqual(self.consulta(flt_plan_tipo="base").count(), 3)
        self.assertEqual(self.consulta(flt_numero="001").get().pk, self.filas[1].pk)
        self.assertEqual(self.consulta(flt_alta_administrativa_desde=str(self.hoy), flt_alta_administrativa_hasta=str(self.hoy)).count(), 3)
        self.assertEqual(self.consulta(alta_desde=str(self.hoy), alta_hasta=str(self.hoy)).count(), 3)
        self.assertEqual(self.consulta(flt_alta_administrativa_vacio="true").get().pk, self.filas[3].pk)
        self.assertEqual(self.consulta(flt_localidad_vacio="false").count(), 4)

    def test_cada_columna_ofrecida_tiene_filtro_tipado(self):
        for clave, col in COLUMNAS_PADRON.items():
            if col["type"] in ("date", "datetime"):
                params = {f"flt_{clave}_desde": str(self.hoy), f"flt_{clave}_hasta": str(self.hoy)}
            else:
                valor = next(iter(col["options"])) if col["type"] == "choice" else "1" if col["type"] == "relation" else "texto"
                params = {f"flt_{clave}": valor}
            with self.subTest(clave=clave):
                list(self.consulta(**params))
                if col.get("nullable"):
                    list(self.consulta(**{f"flt_{clave}_vacio": "true"}))

    def test_crossorg_y_relaciones_ajenas_no_entregan_personas(self):
        self.assertNotIn(self.ajeno.pk, self.consulta(ordering="nombre").values_list("pk", flat=True))
        plan_ajeno = m.Plan.objects.create(financiador=self.otra, nombre="Plan A", codigo="AJENO")
        self.assertEqual(self.consulta(flt_plan=str(plan_ajeno.pk)).count(), 0)
        self.assertEqual(self.consulta(flt_titular=str(self.ajeno.pk)).count(), 0)
        with self.assertRaises(ValidationError):
            self.consulta(financiador=str(self.otra.pk))

    def test_invalidos_y_protegidos_son_400_sin_reflejar_campos_o_valores(self):
        casos = [
            {"ordering": "salud__cud"}, {"ordering": "nombre,-numero"}, {"columnas": "nombre,numero,cbu"},
            {"flt_regimen": "inventado"}, {"flt_titular": "0"}, {"flt_plan": "1.5"},
            {"flt_fecha_nacimiento_desde": "ayer"}, {"flt_email_vacio": "yes"},
            {"flt_nombre_desde": "algo"}, {"flt_cbu": "1234"}, {"cud": "true"},
            {"page_size": "201"}, {"page": "-1"},
            {"flt_desde_desde": str(self.hoy), "flt_desde_hasta": str(self.hoy - timedelta(days=1))},
            {"alta_desde": str(self.hoy), "alta_hasta": str(self.hoy - timedelta(days=1))},
        ]
        for params in casos:
            with self.subTest(params=params), self.assertRaises(ValidationError) as err:
                self.consulta(**params)
            self.assertEqual(err.exception.status_code, 400)
            self.assertNotIn("cbu", str(err.exception.detail))
            self.assertNotIn("1234", str(err.exception.detail))
        with self.assertRaises(ValidationError):
            consultar_padron(financiador=self.org, parametros=QueryDict("ordering=nombre&ordering=numero"))

    def test_estados_calculados_equivalentes_a_serializacion(self):
        futura, finalizada, programada, baja = self.filas
        futura.desde = self.hoy + timedelta(days=1)
        futura.save()
        finalizada.finalizado_en = timezone.now()
        finalizada.estado_tramite = "completo"
        finalizada.save()
        programada.baja_efectiva = self.hoy + timedelta(days=1)
        programada.save()
        baja.baja_efectiva = self.hoy
        baja.save()
        for fila in self.filas:
            clave = "finalizadas" if fila.finalizado_en else "futuras" if fila.desde > self.hoy else "vigentes"
            self.assertIn(fila.pk, self.consulta(flt_derecho=clave).values_list("pk", flat=True))
            self.assertIn(fila.pk, self.consulta(flt_estado_administrativo=estado_administrativo(fila)).values_list("pk", flat=True))
        self.assertEqual(self.consulta(estado="vigentes").count(), 2)
        self.assertEqual(self.consulta(estado="vigentes", derecho="finalizadas").get().pk, finalizada.pk)
        self.assertEqual(self.consulta(flt_finalizado_en_desde=str(self.hoy), flt_finalizado_en_hasta=str(self.hoy)).get().pk, finalizada.pk)

    def test_relacion_orden_nombre_nulos_ultimos_ambos_sentidos(self):
        otro = m.Plan.objects.create(financiador=self.org, codigo="Z", nombre="Plan Z")
        self.filas[1].plan = otro
        self.filas[1].save()
        for orden, ids in [("plan", [0, 2, 1, 3]), ("-plan", [1, 0, 2, 3])]:
            self.assertEqual(list(self.consulta(ordering=orden).values_list("pk", flat=True)), [self.filas[i].pk for i in ids])

    def test_legacy_documento_search_y_regimen(self):
        self.assertEqual(self.consulta(documento=self.filas[1].documento).get().pk, self.filas[1].pk)
        self.assertEqual(self.consulta(search=" Alfa ").count(), 2)
        self.assertEqual(self.consulta(estado_administrativo="en_tramite").count(), 4)
        self.assertEqual(self.consulta(regimen="monotributo").count(), 0)

    def test_search_coincide_en_cualquiera_de_los_cuatro_campos(self):
        afiliado = m.Afiliado.objects.create(
            financiador=self.org, numero="SOC-008", documento="32123456",
            nombre="Identidad administrativa", nombres="Mariana", apellidos="Figueroa",
            desde=self.hoy,
        )
        m.Afiliado.objects.filter(pk=self.ajeno.pk).update(
            numero=afiliado.numero, documento=afiliado.documento,
            nombres=afiliado.nombres, apellidos=afiliado.apellidos,
        )
        for campo, texto in (
            ("numero", "oc-00"), ("nombres", "  rIaN  "),
            ("apellidos", "gUeR"), ("documento", "32.123.456"),
            ("documento_parcial", "1234"),
        ):
            with self.subTest(campo=campo):
                self.assertEqual(list(self.consulta(search=texto).values_list("pk", flat=True)), [afiliado.pk])
        self.assertFalse(self.consulta(search="Sin coincidencias").exists())

    def test_search_ignora_tildes_mayusculas_y_unicode_descompuesto(self):
        afiliado = self.filas[0]
        for campo in ("nombre", "nombres", "apellidos"):
            for guardado in ("José Álvarez Muñoz Güemes Íñigo Óscar Úrsula", "Jose Alvarez Munoz Guemes Inigo Oscar Ursula", unicodedata.normalize("NFD", "José Álvarez Muñoz Güemes Íñigo Óscar Úrsula")):
                datos = {"nombre": "Identidad administrativa", "nombres": "", "apellidos": ""}
                datos[campo] = guardado
                m.Afiliado.objects.filter(pk=afiliado.pk).update(**datos)
                for texto in ("jose", "JOSÉ", "alvarez", "ALVAREZ", "munoz", "muñoz", "guemes", "iñigo", "oscar", "ursula", unicodedata.normalize("NFD", "JOSÉ")):
                    with self.subTest(campo=campo, guardado=guardado, texto=texto):
                        self.assertEqual(list(self.consulta(search=texto).values_list("pk", flat=True)), [afiliado.pk])

    def test_search_palabras_en_cualquier_orden_y_campos_independientes(self):
        afiliado = self.filas[0]
        m.Afiliado.objects.filter(pk=afiliado.pk).update(nombres="José María", apellidos="Pérez", cuil="20345678901")
        m.Afiliado.objects.filter(pk=self.ajeno.pk).update(nombres="José María", apellidos="Pérez")
        for texto in ("jose perez", "  PEREZ   JOSE  ", "pérez\tmaría", "jose 000", "perez 90.000.000", "jose 20345678901"):
            with self.subTest(texto=texto):
                self.assertEqual(list(self.consulta(search=texto).values_list("pk", flat=True)), [afiliado.pk])
        self.assertFalse(self.consulta(search="jose inexistente").exists())
        self.assertFalse(self.consulta(search="jose", flt_localidad="Monte").exists())

    def test_search_simbolos_literales_y_sin_coincidencias_no_devuelve_todo(self):
        afiliado = self.filas[0]
        m.Afiliado.objects.filter(pk=afiliado.pk).update(nombre="José (A+B)")
        for texto in ("(A+B)", "jose (A+B)"):
            with self.subTest(texto=texto):
                self.assertEqual(list(self.consulta(search=texto).values_list("pk", flat=True)), [afiliado.pk])
        for texto in (".*", "...", "[", "%", "\u0301", "Sin coincidencias"):
            with self.subTest(texto=texto):
                self.assertFalse(self.consulta(search=texto).exists())

    def test_catalogo_proyeccion_solo_administrativo_y_columnas(self):
        self.assertTrue(set(CAMPOS_GENERALES).issubset(COLUMNAS_PADRON))
        self.assertFalse({"cbu", "cud", "dbt", "situacion", "parentesco_sensible", "acciones", "revision"} & set(COLUMNAS_PADRON))
        self.assertEqual(validar_columnas_padron("numero,nombre,documento"), ("numero", "nombre", "documento"))
        for valor in ("", "nombre", "nombre,numero,numero", "nombre,numero,salud"):
            with self.assertRaises(ValidationError):
                validar_columnas_padron(valor)
        self.assertEqual(valor_columna_padron(self.filas[0], "numero"), "000")
        self.assertEqual(valor_columna_padron(self.filas[0], "plan"), "Plan A")
        self.assertEqual(valor_columna_padron(self.filas[0], "plan_tipo"), "Base")
        self.assertEqual(valor_columna_padron(self.filas[0], "desde"), self.hoy)
        with self.assertRaises(ValidationError):
            valor_columna_padron(self.filas[0], "cbu")
