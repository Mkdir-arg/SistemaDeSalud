"""Escenarios persistentes ficticios para navegador, nunca datos operativos."""
import json
import os
from pathlib import Path
import secrets
import sys
from tempfile import gettempdir
import unittest
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings_financiadores_postgres_test":
    raise RuntimeError("Se requieren settings PostgreSQL aislados.")
import django
django.setup()
from django.db import connection, transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import Usuario
from apps.financiadores import models as m
from apps.financiadores.test_autorizaciones import AutorizacionSetup
from apps.financiadores import autorizaciones as a
from apps.financiadores.prescripciones_autorizacion import presentar

if connection.settings_dict["NAME"] != "salud_financiadores_test":
    raise RuntimeError("Sólo base ficticia dedicada.")
destino = Path(sys.argv[1]).resolve()
if destino.parent != Path(gettempdir()).resolve() or not destino.name.startswith("ostel-prescripciones-ui-"):
    raise RuntimeError("Se requiere temporal dedicado.")
if destino.exists():
    raise RuntimeError("El escenario ya existe; no se sobrescribe.")
destino.mkdir(exist_ok=False)


class Escenario(AutorizacionSetup, unittest.TestCase):
    def runTest(self):
        pass


marca = uuid4().hex[:10]
clave = secrets.token_urlsafe(24)
usuarios = Usuario.objects
comunes = m.PrestacionComun.objects
original_usuario, original_admin, original_comun = usuarios.create_user, usuarios.create_superuser, comunes.create
secuencia = 0


def crear_persona(creador):
    def crear(email, password=None, **datos):
        global secuencia
        secuencia += 1
        return creador(f"prescripcion-{marca}-{secuencia}@example.invalid", password=clave, **datos)
    return crear


def crear_comun(**datos):
    return original_comun(**{**datos, "codigo": f"FICT-{marca}-{secuencia}"})


escenarios = []
fixture_lectura = None
with transaction.atomic(), patch.object(usuarios, "create_user", side_effect=crear_persona(original_usuario)), \
        patch.object(usuarios, "create_superuser", side_effect=crear_persona(original_admin)), \
        patch.object(comunes, "create", side_effect=crear_comun):
    for numero in range(7):
        fixture = Escenario()
        # Sólo setUp ORM: no runner/TestCase._pre_setup, flush ni transacciones de tests.
        fixture.setUp()
        if numero == 3:
            fixture_lectura = fixture
        fixture.institucion.nombre = f"Hospital FICTICIO {marca}-{numero}"
        fixture.institucion.save(update_fields=["nombre"])
        fixture.financiador.nombre = f"Financiador FICTICIO {marca}-{numero}"
        fixture.financiador.save(update_fields=["nombre"])
        medico = usuarios.create_user("medico@example.invalid")
        m.MembresiaFinanciador.objects.create(financiador=fixture.financiador, usuario=medico,
            rol="auditor", auditoria_medica=True, resuelve_autorizaciones=False)
        actores = {"institucion": fixture.usuario.email, "medico": medico.email,
                   "operador": fixture.operador.email}
        if numero >= 5:
            evaluador = usuarios.create_user("evaluador@example.invalid")
            m.MembresiaFinanciador.objects.create(financiador=fixture.financiador, usuario=evaluador,
                rol="operador", auditoria_medica=True, resuelve_autorizaciones=True)
            actores["evaluador"] = evaluador.email
        escenarios.append({"caso": fixture.caso.pk, "institucion": fixture.institucion.pk,
            "institucion_nombre": fixture.institucion.nombre, "financiador": fixture.financiador.pk,
            "prestacion": fixture.prestacion.pk, "usuarios": actores})

semilla = presentar(caso=fixture_lectura.caso, prestacion=fixture_lectura.prestacion, usuario=fixture_lectura.usuario,
    intento=a.intento_actual(fixture_lectura.caso), cantidad=1, justificacion="Constancia totalmente ficticia",
    clave=uuid4(), prescripcion=SimpleUploadedFile("semilla-ficticia.pdf",
        b"%PDF-1.4\nDocumento totalmente ficticio\n%%EOF", content_type="application/pdf"))
escenarios[3]["solicitud"] = semilla.pk
(destino / "manifiesto.json").write_text(json.dumps({"escenario": "prescripciones-autorizacion-v1",
    "escenarios": escenarios, "password": clave}), encoding="utf-8")
print("Escenarios ficticios preparados; credenciales no mostradas.")
