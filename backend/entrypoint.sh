#!/usr/bin/env bash
set -e

# Sin root (#172, AUD-027). Si el contenedor arranca como root, solo corrige
# el dueño de los directorios de datos y vuelve a ejecutar este script como
# 10001: migraciones, seeds y el proceso final nunca corren como root.
#
# El chown es recursivo pero solo cuando la raíz del directorio no es ya de
# 10001 (volúmenes creados con la imagen anterior); un arranque normal no
# recorre nada. Archivos que alguien deje como root adentro (por ejemplo con
# `docker compose exec` sin `-u 10001`) no se corrigen solos.
APP_UID=10001
if [ "$(id -u)" = "0" ]; then
  facturas="${SALUD_FACTURAS_ADJUNTOS_DIR:-/app/privado/facturas}"
  case "$facturas" in /*) ;; *) facturas="/app/$facturas" ;; esac
  for dir in /app/media /respaldos "$facturas"; do
    if [ -d "$dir" ] && [ "$(stat -c %u "$dir")" != "$APP_UID" ]; then
      echo "Corrigiendo el dueño de $dir para el usuario $APP_UID..."
      chown -R "$APP_UID:$APP_UID" "$dir"
    fi
  done
  exec gosu "$APP_UID:$APP_UID" "$0" "$@"
fi

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

# Las migraciones las aplica UN solo contenedor.
#
# La misma imagen corre como servidor web, como reloj del motor y como respaldo.
# Si los tres migran, en cada despliegue hay tres `migrate` concurrentes sobre la
# misma base tomando locks de DDL en distinto orden: en el mejor caso uno espera,
# en el peor se trepan y la migración queda a mitad de camino —con la tabla
# `django_migrations` diciendo que terminó—.
#
# Por defecto migra, que es lo que corresponde en docker compose (un solo
# servicio con la base) y lo que espera cualquiera que corra esta imagen a mano.
# Los procesos de fondo se despliegan con EJECUTAR_MIGRACIONES=0 y arrancan sobre
# el esquema que dejó el web.
if [ "${EJECUTAR_MIGRACIONES:-1}" = "1" ]; then
  echo "Aplicando migraciones..."
  python manage.py migrar_con_candado
else
  echo "EJECUTAR_MIGRACIONES=0: no migro, uso el esquema existente."
fi

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
