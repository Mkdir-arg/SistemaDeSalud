"""El registro por lotes conserva evidencia, normalización y atomicidad."""
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.instituciones.models import Institucion
from apps.registros.models import Ciudadano

from .mixins import registrar_acceso, registrar_accesos
from .models import AccesoClinico


class RegistroPorLotesTests(TestCase):
    def setUp(self):
        self.hospital = Institucion.objects.create(nombre="Hospital de origen")
        self.otro = Institucion.objects.create(nombre="Hospital actual")
        self.usuario = Usuario.objects.create_user("auditoria-lotes@test.local", "x")
        Membresia.objects.create(usuario=self.usuario, institucion=self.hospital, rol="admin")
        self.paciente = Ciudadano.objects.create(institucion=self.hospital, nombre="Persona ficticia")
        self.request = SimpleNamespace(
            user=self.usuario, query_params={},
            META={"REMOTE_ADDR": "127.0.0.1", "HTTP_X_FORWARDED_FOR": " 192.0.2.1, 127.0.0.1"},
        )

    def test_misma_normalizacion_y_fecha_que_el_registro_individual(self):
        ahora = timezone.now()
        registros = [
            {"ciudadano": self.paciente, "objeto_id": "1" * 45, "detalle": "á" * 320, "resultados": 10},
            {"institucion_id": self.otro.pk, "objeto_id": 0, "detalle": None},
            {"objeto_id": None, "detalle": "Sin persona: institución del pedido"},
        ]
        with patch("django.db.models.fields.timezone.now", return_value=ahora):
            for registro in registros:
                registrar_acceso(self.request, "financiador", "actividad", **registro, estricto=True)
            individuales = list(AccesoClinico.objects.order_by("pk").values())
            registrar_accesos(self.request, "financiador", "actividad", iter(registros), estricto=True)
        agrupados = list(AccesoClinico.objects.order_by("pk").values())[len(registros):]
        for individual, agrupado in zip(individuales, agrupados):
            individual.pop("id")
            agrupado.pop("id")
            self.assertEqual(individual, agrupado)
        self.assertEqual(agrupados[0]["objeto_id"], "1" * 40)
        self.assertEqual(agrupados[0]["detalle"], "á" * 300)
        self.assertEqual(agrupados[0]["ip"], "192.0.2.1")
        self.assertEqual(agrupados[0]["momento"], ahora)
        self.assertEqual(agrupados[2]["institucion_id"], self.hospital.pk)

    def test_conserva_institucion_original_explicita_aunque_cambie_la_del_ciudadano(self):
        self.paciente.institucion = self.otro
        self.paciente.save(update_fields=["institucion"])
        registrar_accesos(self.request, "financiador", "actividad", [{
            "ciudadano": self.paciente, "institucion_id": self.hospital.pk,
            "objeto_id": 42, "detalle": "financiador=1 reservas=42", "resultados": 1,
        }], estricto=True)
        acceso = AccesoClinico.objects.get()
        self.assertEqual(acceso.institucion_id, self.hospital.pk)
        self.assertEqual(acceso.ciudadano_id, self.paciente.pk)

    def test_lotes_acotados_y_vacio_no_inserta(self):
        with patch("apps.auditoria.mixins.AccesoClinico.objects.bulk_create", wraps=AccesoClinico.objects.bulk_create) as crear:
            registrar_accesos(self.request, "financiador", "actividad", [], estricto=True)
            crear.assert_not_called()
            with patch("apps.auditoria.mixins.TAMANIO_LOTE_ACCESOS", 2):
                registrar_accesos(self.request, "financiador", "actividad", (
                    {"ciudadano": self.paciente, "objeto_id": n} for n in range(5)
                ), estricto=True)
            self.assertEqual([len(c.args[0]) for c in crear.call_args_list], [2, 2, 1])
        self.assertEqual(AccesoClinico.objects.count(), 5)

    def test_fallo_estricto_revierte_todos_los_lotes(self):
        crear = AccesoClinico.objects.bulk_create
        intentos = []

        def insertar_o_fallar(objetos, **kwargs):
            intentos.append(len(objetos))
            if len(intentos) == 2:
                raise RuntimeError("Lote no disponible")
            return crear(objetos, **kwargs)

        with (
            patch("apps.auditoria.mixins.TAMANIO_LOTE_ACCESOS", 1),
            patch("apps.auditoria.mixins.AccesoClinico.objects.bulk_create", side_effect=insertar_o_fallar),
            self.assertLogs("apps.auditoria.mixins", level="ERROR"),
            self.assertRaises(RuntimeError),
        ):
            registrar_accesos(self.request, "financiador", "actividad", [
                {"ciudadano": self.paciente}, {"ciudadano": self.paciente},
            ], estricto=True)
        self.assertEqual(intentos, [1, 1])
        self.assertFalse(AccesoClinico.objects.exists())

    def test_lectura_clinica_individual_conserva_tolerancia_y_modo_estricto(self):
        with (
            patch("apps.auditoria.mixins.AccesoClinico.objects.create", side_effect=RuntimeError("Base no disponible")),
            self.assertLogs("apps.auditoria.mixins", level="ERROR"),
        ):
            registrar_acceso(self.request, "detalle", "ciudadano", ciudadano=self.paciente)
            with self.assertRaises(RuntimeError):
                registrar_acceso(self.request, "detalle", "ciudadano", ciudadano=self.paciente, estricto=True)
        self.assertFalse(AccesoClinico.objects.exists())

    def test_lote_tolerante_tampoco_deja_evidencia_parcial(self):
        crear = AccesoClinico.objects.bulk_create

        def insertar_y_fallar(objetos, **kwargs):
            crear(objetos, **kwargs)
            raise RuntimeError("Fallo posterior a inserción")

        with (
            patch("apps.auditoria.mixins.AccesoClinico.objects.bulk_create", side_effect=insertar_y_fallar),
            self.assertLogs("apps.auditoria.mixins", level="ERROR"),
        ):
            registrar_accesos(self.request, "listado", "ciudadano", [{"ciudadano": self.paciente}])
        self.assertFalse(AccesoClinico.objects.exists())

    def test_lotes_conservan_todos_los_registros_y_consumen_un_iterador(self):
        datos = (dict(ciudadano=self.paciente, objeto_id=i) for i in range(501))
        tamanos = []
        crear = AccesoClinico.objects.bulk_create

        def guardar(objetos, **kwargs):
            tamanos.append(len(objetos))
            return crear(objetos, **kwargs)

        with patch.object(AccesoClinico.objects, "bulk_create", side_effect=guardar):
            registrar_accesos(self.request, "financiador", "actividad", datos, estricto=True)
        self.assertEqual(tamanos, [500, 1])
        self.assertEqual(AccesoClinico.objects.count(), 501)

    def test_error_real_de_escritura_revierte_lotes_previos(self):
        for fallo in (1, 2, 3):
            with self.subTest(lote=fallo):
                intentos = 0

                def fallar(ejecutar, sql, params, many, context):
                    nonlocal intentos
                    if sql.lstrip().upper().startswith("INSERT") and AccesoClinico._meta.db_table in sql:
                        intentos += 1
                        if intentos == fallo:
                            raise DatabaseError("Fallo de escritura simulado")
                    return ejecutar(sql, params, many, context)

                datos = [dict(ciudadano=self.paciente)] * 3
                with patch("apps.auditoria.mixins.TAMANIO_LOTE_ACCESOS", 1), connection.execute_wrapper(fallar):
                    with self.assertRaises(DatabaseError):
                        registrar_accesos(self.request, "financiador", "actividad", datos, estricto=True)
                self.assertEqual(intentos, fallo)
                self.assertFalse(AccesoClinico.objects.exists())

    def test_error_del_iterador_revierte_primer_lote(self):
        def datos():
            yield dict(ciudadano=self.paciente)
            raise ValueError("No se pudo preparar el siguiente acceso")

        with patch("apps.auditoria.mixins.TAMANIO_LOTE_ACCESOS", 1):
            with self.assertRaises(ValueError):
                registrar_accesos(self.request, "financiador", "actividad", datos(), estricto=True)
        self.assertFalse(AccesoClinico.objects.exists())
