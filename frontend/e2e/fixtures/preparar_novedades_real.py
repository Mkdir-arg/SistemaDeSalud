"""Fixture propia y ficticia, sólo PostgreSQL loopback dedicado; no carga seeds."""
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from uuid import uuid4

if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings_financiadores_postgres_test":
    raise RuntimeError("Esta fixture requiere settings PostgreSQL de pruebas explícitos.")

backend = Path(__file__).resolve().parents[3] / "backend"
sys.path.insert(0, str(backend))

import django
django.setup()

from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.financiadores.novedades import registrar
from apps.financiadores.services import registrar_afiliado

config = connection.settings_dict
if config["NAME"] != "salud_financiadores_test" or config["HOST"] not in {"127.0.0.1", "localhost", "::1"}:
    raise RuntimeError("Destino no admitido: se exige base ficticia exclusiva en loopback.")
destino = Path(sys.argv[1]).resolve()
if Path(tempfile.gettempdir()).resolve() not in destino.parents or destino.exists():
    raise RuntimeError("El manifiesto debe ser nuevo y estar fuera del repositorio, en temporal.")

marca = uuid4().hex[:10]
password = secrets.token_urlsafe(24)
with transaction.atomic():
    operador = Usuario.objects.create_user(f"novedades-{marca}@example.invalid", password=password,
                                           nombre="Operación ficticia Novedades")
    auditor = Usuario.objects.create_user(f"novedades-lectura-{marca}@example.invalid", password=password,
                                          nombre="Auditoría ficticia Novedades")
    organizaciones = []
    for letra in ("A", "B"):
        org = Financiador.objects.create(nombre=f"NOVEDADES FICTICIAS {letra} {marca}", tipo="obra_social")
        MembresiaFinanciador.objects.create(financiador=org, usuario=operador, rol="operador")
        MembresiaFinanciador.objects.create(financiador=org, usuario=auditor, rol="auditor")
        afiliado = registrar_afiliado(financiador=org, usuario=operador, numero="NOV-FICTICIO-1",
            documento="99018501", nombre=f"PERSONA FICTICIA {letra}", plan=None,
            desde=timezone.localdate(), cobertura_habilitada=False)
        novedad_legacy, _ = registrar(financiador=org, usuario=operador, clave=uuid4(),
            afiliado=afiliado.pk, fuente="Fixture histórica ficticia",
            referencia=f"LEGACY-{letra}-{marca}", codigo="LEGACY",
            fecha_informada=None, descripcion="Snapshot histórico sintético sin campo de cobertura",
            motivo="Preparación aislada del estado histórico", rectifica=None)
        novedad_legacy.filas[0]["persona_inicial"].pop("cobertura_habilitada", None)
        novedad_legacy.save(update_fields=["filas"])
        organizaciones.append({"id": org.pk, "nombre": org.nombre,
                                "afiliado": afiliado.pk, "documento": afiliado.documento,
                                "legacy_novedad": novedad_legacy.pk})
    destino.write_text(json.dumps({"purpose": "salud-novedades-e2e", "password": password,
        "operador": operador.email, "auditor": auditor.email, "organizaciones": organizaciones}), encoding="utf-8")
