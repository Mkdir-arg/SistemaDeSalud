"""Fixture ficticia exclusiva de borradores en PostgreSQL local descartable."""
from datetime import date
import json
import os
from pathlib import Path
import secrets
import sys
from tempfile import gettempdir
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings_financiadores_postgres_test":
    raise RuntimeError("Se requieren settings PostgreSQL aislados.")
import django
django.setup()
from django.db import connection
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador, Plan
from apps.financiadores.derechos_borrador import BorradorDerechos
from apps.financiadores.borradores_derechos import guardar_borradores

if connection.settings_dict["NAME"] != "salud_financiadores_test":
    raise RuntimeError("Sólo base ficticia dedicada.")
destino = Path(sys.argv[1]).resolve()
if destino.parent != Path(gettempdir()).resolve() or not destino.name.startswith("ostel-borradores-ui-"):
    raise RuntimeError("Se requiere temporal dedicado.")
destino.mkdir(exist_ok=False)
marca = uuid4().hex[:10]
password = secrets.token_urlsafe(24)
usuarios = {}
for rol in ("admin", "auditor"):
    usuario = Usuario.objects.create_user(f"borradores-{rol}-{marca}@example.invalid", password=password, nombre="Persona ficticia")
    usuarios[rol] = usuario
organizaciones = []
for letra in ("A", "B"):
    org = Financiador.objects.create(nombre=f"BORRADORES FICTICIOS {letra} {marca}", tipo="otro")
    Plan.objects.create(financiador=org, codigo="FICTICIO", nombre="Plan ficticio")
    for rol, usuario in usuarios.items():
        MembresiaFinanciador.objects.create(financiador=org, usuario=usuario, rol=rol)
    organizaciones.append(org.pk)
guardar_borradores(usuario=usuarios["admin"], financiador_id=organizaciones[0],
    propuesta=(BorradorDerechos("simulacion-ficticia", 1, "Fuente ficticia de simulación",
        organizaciones[0], "dependencia", None, date(2029, 1, 1)),),
    motivo="Fixture ficticia de consulta", regimen="dependencia", plan_id=None, fecha=date(2030, 1, 8))
(destino / "manifiesto.json").write_text(json.dumps({"escenario": "borradores-derechos-v1", "organizaciones": organizaciones,
    "usuarios": {rol: user.email for rol, user in usuarios.items()}, "password": password}), encoding="utf-8")
print("Fixture ficticia preparada; credenciales no mostradas.")
