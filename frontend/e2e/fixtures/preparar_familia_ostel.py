"""Escenario ficticio exclusivo para UI/API/PostgreSQL local de familias OSTEL."""
import json
import os
from pathlib import Path
import secrets
import sys
from tempfile import gettempdir
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings_financiadores_postgres_test":
    raise RuntimeError("Se requieren los settings PostgreSQL aislados.")

import django
django.setup()

from django.db import connection
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.financiadores.ostel_synthetic import COLUMNAS, Lote, _persona, generar_xlsx

if connection.settings_dict["NAME"] != "salud_financiadores_test":
    raise RuntimeError("La fixture sólo admite la base descartable dedicada.")
destino = Path(sys.argv[1]).resolve()
if destino.parent != Path(gettempdir()).resolve() or not destino.name.startswith("ostel-familia-ui-"):
    raise RuntimeError("Se requiere un directorio propio bajo el temporal del sistema.")
destino.mkdir(exist_ok=False)
marca = uuid4().hex[:10]
password = secrets.token_urlsafe(24)
org = Financiador.objects.create(nombre=f"OSTEL FAMILIAS FICTICIAS {marca}", tipo="obra_social")
usuario = Usuario.objects.create_user(f"familias-{marca}@example.invalid", password=password, nombre="Operador ficticio")
MembresiaFinanciador.objects.create(financiador=org, usuario=usuario, rol="operador")
casos = {}
for i, caso in enumerate(("normal", "conflicto", "perdida", "movil")):
    titular = dict(zip(COLUMNAS, _persona(100 + i * 2)))
    archivo = destino / f"{caso}.xlsx"
    archivo.write_bytes(generar_xlsx(Lote(caso, (
        _persona(101 + i * 2, NUMERO=f"{marca}-{caso}-I", APENOM=f"Integrante ficticio {caso}",
                 CUILTIT=titular["CUIL"], NROAFI="FAMILIA-COMPARTIDA"),
        _persona(100 + i * 2, NUMERO=f"{marca}-{caso}-T", APENOM=f"Titular ficticio {caso}",
                 CUILTIT=titular["CUIL"], NROAFI="FAMILIA-COMPARTIDA"),
    ))))
    casos[caso] = str(archivo)
(destino / "manifiesto.json").write_text(json.dumps({"escenario": "familia-ostel-v1",
    "organizacion": org.pk, "email": usuario.email, "password": password, "casos": casos}), encoding="utf-8")
print("Escenario ficticio preparado; credenciales no mostradas.")
