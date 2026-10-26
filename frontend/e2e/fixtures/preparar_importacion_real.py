"""Fixtures para navegador/API/PostgreSQL; sólo DB local exclusiva de pruebas.

Desde backend, con settings_financiadores_postgres_test y un destino temporal:
python ../frontend/e2e/fixtures/preparar_importacion_real.py <directorio_temporal>
El manifiesto contiene una contraseña ficticia efímera: no publicar ni commitear.
"""
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
if os.environ.get("DJANGO_SETTINGS_MODULE") != "config.settings_financiadores_postgres_test":
    raise RuntimeError("Esta fixture exige los settings PostgreSQL aislados.")

import django
django.setup()

from django.db import connection
from apps.accounts.models import Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.financiadores.ostel_synthetic import Lote, _persona, generar_xlsx

if connection.settings_dict["NAME"] != "salud_financiadores_test":
    raise RuntimeError("No se permite preparar esta fixture en otra base.")
destino = Path(sys.argv[1]).resolve()
destino.mkdir(parents=True, exist_ok=False)
identificador = uuid4().hex[:10]
password = secrets.token_urlsafe(24)
org = Financiador.objects.create(nombre=f"OSTEL FICTICIA E2E {identificador}", tipo="obra_social")
usuario = Usuario.objects.create_user(f"ostel-{identificador}@example.invalid", password=password, nombre="Operador ficticio E2E")
MembresiaFinanciador.objects.create(financiador=org, usuario=usuario, rol="operador")
casos = {}
offset = secrets.randbelow(400000) + 10000
for indice, (caso, cantidad, conflicto) in enumerate((
    ("normal", 205, True), ("respuesta_perdida", 205, False),
    ("otra_sesion", 101, False), ("completa", 101, False),
)):
    filas = []
    prefijo = f"E2E182-{identificador}-{caso}"
    for n in range(1, cantidad + 1 + int(conflicto)):
        cambios = {"NUMERO": f"{prefijo}-{n}", "NROAFI": f"{prefijo}-{n}"}
        if conflicto and n > cantidad:
            cambios["CUIL"] = "123"
        filas.append(_persona(offset + indice * 1000 + n, **cambios))
    archivo = destino / f"{caso}.xlsx"
    archivo.write_bytes(generar_xlsx(Lote(caso, tuple(filas))))
    casos[caso] = {"archivo": str(archivo), "prefijo": prefijo, "validas": cantidad,
                   "total": len(filas), "conflictos": int(conflicto)}
(destino / "manifiesto.json").write_text(json.dumps({"escenario": "importacion-respuesta-v1",
    "organizacion": org.pk, "email": usuario.email, "password": password, "casos": casos}), encoding="utf-8")
print("Fixtures ficticias creadas en base aislada; credenciales no mostradas.")
