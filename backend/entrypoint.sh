#!/usr/bin/env bash
set -e

# Espera a que Postgres acepte conexiones (si se usa DATABASE_URL).
if [ -n "$DATABASE_URL" ]; then
  echo "Esperando a la base de datos..."
  python - <<'PY'
import os, time, sys
import dj_database_url
import psycopg

cfg = dj_database_url.parse(os.environ["DATABASE_URL"])
dsn = (
    f"host={cfg['HOST']} port={cfg.get('PORT') or 5432} "
    f"dbname={cfg['NAME']} user={cfg['USER']} password={cfg['PASSWORD']}"
)
for _ in range(30):
    try:
        psycopg.connect(dsn, connect_timeout=2).close()
        print("Base de datos lista.")
        sys.exit(0)
    except Exception as e:
        print(f"  ...todavía no ({e})")
        time.sleep(2)
print("La base de datos no respondió a tiempo.", file=sys.stderr)
sys.exit(1)
PY
fi

echo "Aplicando migraciones..."
python manage.py migrate --noinput

# Carga datos de demostración si SEED_DEMO=1 (idempotente del lado del comando).
if [ "$SEED_DEMO" = "1" ]; then
  echo "Sembrando datos de demo..."
  python manage.py seed_demo || echo "seed_demo falló o ya estaba sembrado; continúo."
fi

# Carga el escenario de guardia si SEED_GUARDIA=1. Con --si-vacio solo siembra
# cuando la base no tiene datos, así un reinicio no pisa los casos creados.
if [ "$SEED_GUARDIA" = "1" ]; then
  echo "Sembrando escenario de guardia (si la base está vacía)..."
  python manage.py seed_guardia --si-vacio || echo "seed_guardia falló; continúo."
fi

exec "$@"
