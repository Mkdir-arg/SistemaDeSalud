"""Diagnóstico explicable, aislado por hospital y sin escrituras de negocio."""
from datetime import timedelta
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano
from .legado import diagnosticar, huella_aliases, validar_aliases
from .management.commands import diagnosticar_coberturas_legacy as comando_legado
from .models import (
    Afiliado, Convenio, Financiador, HistorialAfiliacion, Plan, VinculoCiudadano,
)


class DiagnosticoLegadoTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.hospital = Institucion.objects.create(nombre="Hospital confidencial")
        self.otro = Institucion.objects.create(nombre="Otro hospital")
        self.usuario = Usuario.objects.create_user("legacy@prueba.local", "x")
        self.financiador = Financiador.objects.create(nombre="Organización privada", tipo="obra_social")
        self.plan = Plan.objects.create(financiador=self.financiador, codigo="PLAN", nombre="Plan privado")
        self.convenio = Convenio.objects.create(
            institucion=self.hospital, financiador=self.financiador, estado="activo",
            propuesto_por="plataforma", creado_por=self.usuario,
        )
        self.secuencia = 0

    def ciudadano(self, **datos):
        self.secuencia += 1
        valores = {
            "institucion": self.hospital, "nombre": "Nombre muy privado", "apellido": "Apellido privado",
            "documento": f"00{self.secuencia:06d}", "obra_social": "Texto legado privado",
        }
        valores.update(datos)
        return Ciudadano.objects.create(**valores)

    def afiliado(self, ciudadano, **datos):
        valores = {
            "financiador": self.financiador, "numero": f"AFIL-{ciudadano.pk}",
            "documento": ciudadano.documento, "nombre": "Identidad reservada",
            "plan": self.plan, "desde": self.hoy,
        }
        valores.update(datos)
        return Afiliado.objects.create(**valores)

    def registros(self, **datos):
        valores = {"institucion_id": self.hospital.pk, "hasta_pk": 100000, "lote": 2}
        valores.update(datos)
        return list(diagnosticar(**valores))

    def comando(self, **datos):
        stdout, stderr = StringIO(), StringIO()
        call_command("diagnosticar_coberturas_legacy", institucion=self.hospital.pk,
                     stdout=stdout, stderr=stderr, **datos)
        self.assertEqual(stderr.getvalue(), "")
        return json.loads(stdout.getvalue()), stdout.getvalue()

    def test_clasificaciones_estables_por_pk_lotes_y_sin_sql_de_escritura(self):
        esperado = {}
        esperado[self.ciudadano(obra_social=" ").pk] = "sin_dato"
        esperado[self.ciudadano(documento="").pk] = "sin_documento"
        esperado[self.ciudadano(documento="N.N.").pk] = "sin_documento"
        esperado[self.ciudadano().pk] = "sin_padron_verificado"
        candidato = self.ciudadano()
        self.afiliado(candidato)
        esperado[candidato.pk] = "candidato_unico"
        sin_plan = self.ciudadano()
        self.afiliado(sin_plan, plan=None)
        esperado[sin_plan.pk] = "plan_desconocido"
        segundo = Financiador.objects.create(nombre="Mutual", tipo="mutual")
        otro_plan = Plan.objects.create(financiador=segundo, codigo="M", nombre="Mutual")
        sin_convenio = self.ciudadano()
        self.afiliado(sin_convenio, financiador=segundo, plan=otro_plan)
        esperado[sin_convenio.pk] = "sin_convenio"
        ambiguo = self.ciudadano()
        self.afiliado(ambiguo)
        self.afiliado(ambiguo, financiador=segundo, plan=otro_plan)
        esperado[ambiguo.pk] = "ambiguo"
        corregido = self.ciudadano()
        afiliado = self.afiliado(corregido, documento="88000111")
        HistorialAfiliacion.objects.create(
            afiliado=afiliado, documento=corregido.documento, numero=afiliado.numero,
            plan=self.plan, desde=self.hoy, registrado_por=self.usuario,
        )
        esperado[corregido.pk] = "identidad_en_conflicto"
        self.ciudadano(institucion=self.otro)
        with CaptureQueriesContext(connection) as consultas:
            uno, varios = self.registros(lote=1), self.registros(lote=500)
            resumen, _ = self.comando(lote=2)
        self.assertEqual(uno, varios)
        self.assertEqual([r["ciudadano"] for r in uno], sorted(esperado))
        self.assertEqual({r["ciudadano"]: r["clasificacion"] for r in uno}, esperado)
        self.assertEqual(resumen["total"], len(esperado))
        self.assertTrue(consultas.captured_queries)
        for consulta in consultas:
            self.assertIsNone(re.search(r"\b(?:INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|REPLACE)\b",
                                        consulta["sql"], re.IGNORECASE), consulta["sql"])
        self.assertFalse(VinculoCiudadano.objects.exists())

    def test_documento_normalizado_con_ceros_no_coincide_con_otro_documento(self):
        ciudadano = self.ciudadano(documento="00.123.456")
        correcto = self.afiliado(ciudadano)
        otro = self.ciudadano(documento="123456")
        incorrecto = self.afiliado(otro)
        resultado = self.registros()[0]
        self.assertEqual(resultado["candidato"], correcto.pk)
        self.assertNotIn(incorrecto.pk, [a["id"] for a in resultado["afiliados"]])
        self.assertEqual(ciudadano.documento, "00123456")

    def test_homonimos_y_semejanza_de_texto_no_acreditan_afiliacion(self):
        original = self.ciudadano(obra_social="Organizacion privada")
        homonimo = self.ciudadano()
        self.afiliado(homonimo, nombre=original.nombre)
        aliases = validar_aliases({"Organización privada": {"financiador": self.financiador.pk}})
        resultado = self.registros(aliases=aliases)[0]
        self.assertEqual(resultado["clasificacion"], "sin_padron_verificado")
        self.assertIsNone(resultado["alias"])
        self.assertEqual(resultado["afiliados"], [])

    def test_alias_revisado_desambigua_sin_crear_vinculos_ni_inferir_plan(self):
        ciudadano = self.ciudadano(obra_social="  OBRA   REVISADA  ")
        correcto = self.afiliado(ciudadano)
        otro_financiador = Financiador.objects.create(nombre="Otro", tipo="otro")
        self.afiliado(ciudadano, financiador=otro_financiador, plan=None)
        aliases = validar_aliases({"obra revisada": {"financiador": self.financiador.pk, "plan": self.plan.pk}})
        resultado = self.registros(aliases=aliases)[0]
        self.assertEqual(resultado["clasificacion"], "candidato_unico")
        self.assertEqual(resultado["candidato"], correcto.pk)
        self.assertIn("alias_explicito", resultado["criterios"])
        self.assertFalse(VinculoCiudadano.objects.exists())
        otro_plan = Plan.objects.create(financiador=self.financiador, codigo="B", nombre="Plan B")
        aliases = validar_aliases({"obra revisada": {"financiador": self.financiador.pk, "plan": otro_plan.pk}})
        self.assertEqual(self.registros(aliases=aliases)[0]["clasificacion"], "plan_desconocido")
        correcto.refresh_from_db()
        self.assertEqual(correcto.plan_id, self.plan.pk)

    def test_alias_no_sustituye_un_padron_documental_ausente(self):
        self.ciudadano(obra_social="Obra revisada")
        aliases = validar_aliases({"obra revisada": {"financiador": self.financiador.pk, "plan": self.plan.pk}})
        self.assertEqual(self.registros(aliases=aliases)[0]["clasificacion"], "sin_padron_verificado")

    def test_documento_corregido_no_reutiliza_un_vinculo_anterior(self):
        ciudadano = self.ciudadano()
        afiliado = self.afiliado(ciudadano)
        VinculoCiudadano.objects.create(afiliado=afiliado, ciudadano=ciudadano, verificado_por=self.usuario)
        ciudadano.documento = "99999999"
        ciudadano.save(update_fields=["documento"])
        nuevo = self.afiliado(ciudadano)
        resultado = self.registros()[0]
        self.assertEqual(resultado["clasificacion"], "identidad_en_conflicto")
        self.assertEqual(resultado["afiliados_en_conflicto"], [afiliado.pk])
        self.assertNotIn("candidato", resultado)
        self.assertEqual(Afiliado.objects.get(pk=nuevo.pk).documento, "99999999")

    def test_documento_legacy_no_normalizado_requiere_revision(self):
        ciudadano = self.ciudadano()
        self.afiliado(ciudadano)
        Ciudadano.objects.filter(pk=ciudadano.pk).update(documento="00.000.001")
        self.assertEqual(self.registros()[0]["clasificacion"], "identidad_en_conflicto")

    def test_afiliados_finalizados_futuros_o_financiador_inactivo_no_son_candidatos(self):
        for cambio in ({"finalizado_en": timezone.now()}, {"desde": self.hoy + timedelta(days=1)}):
            ciudadano = self.ciudadano()
            self.afiliado(ciudadano, **cambio)
        self.assertEqual({r["clasificacion"] for r in self.registros()}, {"sin_padron_verificado"})
        ciudadano = self.ciudadano()
        self.afiliado(ciudadano)
        self.financiador.activo = False
        self.financiador.save(update_fields=["activo"])
        self.assertEqual({r["clasificacion"] for r in self.registros()}, {"sin_padron_verificado"})

    def test_plan_inactivo_o_ajeno_no_se_infiere_del_alias(self):
        ciudadano = self.ciudadano()
        afiliado = self.afiliado(ciudadano)
        self.plan.activo = False
        self.plan.save(update_fields=["activo"])
        self.assertEqual(self.registros()[0]["clasificacion"], "plan_desconocido")
        otro = Financiador.objects.create(nombre="Otro", tipo="otro")
        self.plan.financiador, self.plan.activo = otro, True
        self.plan.save(update_fields=["financiador", "activo"])
        self.assertEqual(self.registros()[0]["clasificacion"], "plan_desconocido")
        self.assertEqual(Afiliado.objects.get(pk=afiliado.pk).plan_id, self.plan.pk)

    def test_convenio_cerrado_propuesto_o_aceptado_en_futuro_no_habilita(self):
        self.afiliado(self.ciudadano())
        for cambios in (
            {"estado": "finalizado", "cerrado_en": timezone.now()},
            {"estado": "finalizado", "cerrado_en": None},
            {"estado": "propuesto", "cerrado_en": None},
            {"estado": "activo", "aceptado_en": timezone.now() + timedelta(days=1)},
        ):
            Convenio.objects.filter(pk=self.convenio.pk).update(**cambios)
            self.assertEqual(self.registros()[0]["clasificacion"], "sin_convenio")

    def test_limite_superior_fija_altas_y_ambito_no_incluye_otro_hospital(self):
        primero = self.ciudadano()
        self.ciudadano()
        self.ciudadano(institucion=self.otro, documento=primero.documento)
        self.assertEqual([r["ciudadano"] for r in self.registros(hasta_pk=primero.pk)], [primero.pk])

    def test_reporte_metadatos_ids_resumen_sin_datos_personales(self):
        ciudadano = self.ciudadano()
        afiliado = self.afiliado(ciudadano)
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "diagnostico.jsonl"
            with CaptureQueriesContext(connection) as consultas:
                resumen, stdout = self.comando(reporte=str(ruta))
            contenido = ruta.read_text(encoding="utf-8")
            filas = [json.loads(linea) for linea in contenido.splitlines()]
            for privado in (ciudadano.nombre, ciudadano.apellido, ciudadano.documento, ciudadano.obra_social,
                            afiliado.nombre, afiliado.numero, self.financiador.nombre, self.plan.nombre,
                            self.hospital.nombre, str(ruta)):
                self.assertNotIn(privado, stdout)
                self.assertNotIn(privado, contenido)
            self.assertEqual(filas[0]["institucion"], self.hospital.pk)
            self.assertTrue(filas[0]["solo_lectura"])
            self.assertIn("generado_en", filas[0])
            self.assertIn("aliases_sha256", filas[0])
            self.assertEqual(filas[1]["ciudadano"], ciudadano.pk)
            self.assertEqual(filas[1]["candidato"], afiliado.pk)
            self.assertEqual(filas[-1], resumen)
            self.assertEqual(resumen["total"], 1)
            self.assertTrue(resumen["reporte_generado"])
            self.assertTrue(resumen["completo"])
            self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in consultas))

    def test_consultas_acotadas_por_lote_no_por_afiliado(self):
        self.afiliado(self.ciudadano())
        with CaptureQueriesContext(connection) as consultas:
            self.registros(lote=250)
        consultas_uno = len(consultas)
        for _ in range(20):
            self.afiliado(self.ciudadano())
        with CaptureQueriesContext(connection) as consultas:
            resultados = self.registros(lote=250)
        self.assertEqual(len(resultados), 21)
        self.assertEqual(len(consultas), consultas_uno)
        self.assertEqual({r["clasificacion"] for r in resultados}, {"candidato_unico"})

    def test_salida_solo_agregada_por_defecto_y_hospital_vacio(self):
        resumen, stdout = self.comando()
        self.assertEqual(resumen["total"], 0)
        self.assertFalse(resumen["reporte_generado"])
        self.assertNotIn("ciudadano", stdout)
        self.assertEqual(len(stdout.splitlines()), 1)

    def test_reporte_no_sobrescribe_y_rechaza_repositorio(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "existente.jsonl"
            ruta.write_text("original", encoding="utf-8")
            with self.assertRaises(CommandError):
                self.comando(reporte=str(ruta))
            self.assertEqual(ruta.read_text(encoding="utf-8"), "original")
        # La copia de trabajo se simula en vez de usar la real: la raíz depende
        # del despliegue —dentro del contenedor el código no vive en un
        # repositorio y no hay ninguna— y probar contra ella hacía que este caso
        # afirmara cosas distintas según dónde corriera.
        with tempfile.TemporaryDirectory() as repo:
            raiz = Path(repo).resolve()
            (raiz / ".git").mkdir()
            destino = raiz / "diagnostico-no-debe-existir.jsonl"
            with patch.object(comando_legado, "REPOSITORIO", raiz):
                with self.assertRaisesMessage(CommandError, "fuera del repositorio"):
                    self.comando(reporte=str(destino))
            self.assertFalse(destino.exists())

    def test_la_raiz_se_ubica_por_la_marca_git_y_no_por_la_profundidad(self):
        """Las dos ramas de la detección, sin depender de dónde corra la prueba.

        Es el camino que la suite no ejercitaba: los casos de la guarda parchean
        `REPOSITORIO`, y dentro del contenedor no hay copia de trabajo, así que
        la rama que encuentra el repositorio no llegaba a ejecutarse nunca.
        """
        with tempfile.TemporaryDirectory() as base:
            raiz = Path(base).resolve()
            hondo = raiz / "backend" / "apps" / "financiadores" / "management" / "commands"
            hondo.mkdir(parents=True)
            archivo = hondo / "comando.py"
            archivo.touch()

            # Sin marca todavía: no hay copia de trabajo que proteger.
            self.assertIsNone(comando_legado._raiz_del_repositorio(archivo))

            # `.git` como directorio (clon) y como archivo (worktree o submódulo).
            marca = raiz / ".git"
            marca.mkdir()
            self.assertEqual(comando_legado._raiz_del_repositorio(archivo), raiz)
            marca.rmdir()
            marca.write_text("gitdir: /otro/lado", encoding="utf-8")
            self.assertEqual(comando_legado._raiz_del_repositorio(archivo), raiz)

            # Gana la marca más cercana, no la profundidad: un repositorio
            # anidado protege su propio árbol y no el de arriba.
            anidado = raiz / "backend"
            (anidado / ".git").mkdir()
            self.assertEqual(comando_legado._raiz_del_repositorio(archivo), anidado)

    def test_sin_copia_de_trabajo_el_reporte_no_queda_bloqueado(self):
        """Sin repositorio no hay commit accidental que evitar, y el reporte sale.

        Calcular la raíz contando niveles fijos daba `/` en el contenedor: toda
        ruta caía «dentro del repositorio» y el comando era inejecutable ahí.
        """
        with patch.object(comando_legado, "REPOSITORIO", None), tempfile.TemporaryDirectory() as fuera:
            ruta = Path(fuera) / "diagnostico.jsonl"
            resumen, _ = self.comando(reporte=str(ruta))
        self.assertTrue(resumen["reporte_generado"])

    def test_alias_archivo_validado_y_errores_no_exponen_contenido(self):
        ciudadano = self.ciudadano(obra_social="Alias reservado")
        self.afiliado(ciudadano)
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "aliases.json"
            ruta.write_text(json.dumps({"Alias reservado": {"financiador": self.financiador.pk}}), encoding="utf-8")
            resumen, _ = self.comando(aliases=str(ruta))
            self.assertEqual(resumen["clasificaciones"]["candidato_unico"], 1)
            ruta.write_text('{"Alias reservado": {}, "Alias reservado": {}}', encoding="utf-8")
            with self.assertRaises(CommandError) as error:
                self.comando(aliases=str(ruta))
            self.assertNotIn("Alias reservado", str(error.exception))
            ruta.write_text('{"Alias reservado": inválido}', encoding="utf-8")
            with self.assertRaises(CommandError) as error:
                self.comando(aliases=str(ruta))
            self.assertNotIn("Alias reservado", str(error.exception))

    def test_aliases_invalidos_no_infiere_planes_y_huella_estable(self):
        otro = Financiador.objects.create(nombre="Otro", tipo="otro")
        invalidos = (
            [], {"": {"financiador": self.financiador.pk}},
            {"A": {"financiador": True}}, {"A": {"financiador": 999999}},
            {"A": {"financiador": self.financiador.pk, "plan": "PLAN"}},
            {"A": {"financiador": self.financiador.pk, "plan": 999999}},
            {"A": {"financiador": otro.pk, "plan": self.plan.pk}},
            {"A": {"financiador": self.financiador.pk, "nuevo_plan": True}},
            {" A ": {"financiador": self.financiador.pk}, "a": {"financiador": otro.pk}},
        )
        for datos in invalidos:
            with self.subTest(datos=datos), self.assertRaises(ValidationError):
                validar_aliases(datos)
        a = validar_aliases({" A ": {"financiador": self.financiador.pk}})
        b = validar_aliases({"a": {"financiador": self.financiador.pk}})
        self.assertEqual(huella_aliases(a), huella_aliases(b))

    def test_institucion_obligatoria_existente_y_lotes_acotados(self):
        with self.assertRaises(CommandError):
            call_command("diagnosticar_coberturas_legacy", stdout=StringIO(), stderr=StringIO())
        with self.assertRaisesMessage(CommandError, "no existe"):
            call_command("diagnosticar_coberturas_legacy", institucion=999999, stdout=StringIO())
        for lote in (0, -1, 501):
            with self.assertRaises(CommandError):
                self.comando(lote=lote)
            with self.assertRaises(ValidationError):
                self.registros(lote=lote)
