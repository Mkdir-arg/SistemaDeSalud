#!/bin/sh
# Trabajos del respaldo continuo (#172, AUD-017). Corre en la imagen de
# docker/postgres, que trae wal-g, restic y psql.
#
#   respaldo-continuo.sh base      copia base con WAL-G y retención
#   respaldo-continuo.sh archivos  media y facturas con restic, cada 15 min
#
# Cada pasada exitosa deja un latido en `auditoria_latido` (el modelo Latido
# del backend) con SQL directo: esta imagen no tiene Django. Lo vigila
# `/api/estado/` cuando RESPALDO_CONTINUO=1. Si cambia la tabla o el nombre de
# un servicio, falla `apps.auditoria.test_respaldo_continuo_auditoria172`.
#
# Ninguna variable con secretos se imprime.
set -eu

MODO="${1:-}"

requerir() {
  faltan=""
  for nombre in "$@"; do
    eval "valor=\${$nombre:-}"
    [ -n "$valor" ] || faltan="$faltan $nombre"
  done
  if [ -n "$faltan" ]; then
    echo "respaldo-continuo ${MODO}: faltan${faltan}; no arranco." >&2
    exit 1
  fi
}

registro() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) respaldo-continuo ${MODO}: $*"; }

# latir <servicio> <detalle> [momento]
# Sin momento usa now(). Nunca corta el trabajo: un latido que no se pudo
# escribir se ve igual en /api/estado/, como atrasado.
latir() {
  if ! psql -X -q -v ON_ERROR_STOP=1 -v servicio="$1" -v detalle="$2" -v momento="${3:-}" \
      >/dev/null <<'SQL'
INSERT INTO auditoria_latido (servicio, momento, detalle)
VALUES (:'servicio', COALESCE(NULLIF(:'momento', '')::timestamptz, now()), left(:'detalle', 200))
ON CONFLICT (servicio) DO UPDATE SET momento = EXCLUDED.momento, detalle = EXCLUDED.detalle;
SQL
  then
    registro "no se pudo dejar el latido $1 (el respaldo sí terminó)." >&2
  fi
}

# Copia base más nueva del almacenamiento: imprime «segundos|hora|nombre», o
# nada si no hay ninguna. Usa psql para leer el JSON y hacer la cuenta, así la
# imagen no suma jq.
ultima_base() {
  lista="$(wal-g backup-list --json 2>/dev/null || true)"
  case "$lista" in \[*) ;; *) return 0 ;; esac
  psql -X -At -v ON_ERROR_STOP=1 -v lista="$lista" <<'SQL'
SELECT extract(epoch FROM now() - (b->>'time')::timestamptz)::bigint || '|' || (b->>'time') || '|' || (b->>'backup_name')
FROM json_array_elements(:'lista'::json) b
ORDER BY (b->>'time')::timestamptz DESC LIMIT 1;
SQL
}

base() {
  requerir WALG_S3_PREFIX AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY WALG_LIBSODIUM_KEY \
    PGHOST PGUSER PGPASSWORD PGDATABASE PGDATA
  intervalo="${WALG_INTERVALO_BASE:-604800}"
  conservar="${WALG_CONSERVAR_BASES:-3}"
  revisar="${WALG_REVISAR_CADA:-3600}"
  registro "copia base cada ${intervalo}s, conservar ${conservar} completas, revisar cada ${revisar}s."
  while true; do
    ultima="$(ultima_base || true)"
    edad="${ultima%%|*}"
    if [ -z "$ultima" ] || [ "$edad" -ge "$intervalo" ]; then
      if [ -z "$ultima" ]; then motivo="no hay ninguna"; else motivo="la última tiene ${edad}s"; fi
      registro "sacando copia base (${motivo})."
      if wal-g backup-push "$PGDATA"; then
        # Retención por cantidad de completas, ordenadas por la hora real de
        # la copia: el orden por nombre se rompe si el timeline vuelve a 1
        # (base nueva, pg_upgrade). Borra también el WAL anterior a la más
        # vieja que queda.
        wal-g delete retain FULL "$conservar" --use-sentinel-time --confirm \
          || registro "falló la retención; las copias siguen ahí." >&2
        ultima="$(ultima_base || true)"
      else
        registro "falló la copia base; reintento en ${revisar}s." >&2
      fi
    fi
    if [ -n "$ultima" ]; then
      resto="${ultima#*|}"
      latir respaldo_base "${resto#*|}" "${resto%%|*}"
    fi
    sleep "$revisar"
  done
}

archivos() {
  requerir RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY \
    PGHOST PGUSER PGPASSWORD PGDATABASE
  intervalo="${RESTIC_INTERVALO:-900}"
  conservar="${RESTIC_CONSERVAR:-14d}"
  poda="${RESTIC_INTERVALO_PODA:-86400}"
  origen="${RESTIC_ORIGEN:-/datos}"
  export RESTIC_CACHE_DIR="${RESTIC_CACHE_DIR:-/tmp/restic-cache}"
  # Código 10: el repositorio no existe (restic >= 0.17). Cualquier otro error
  # (red, contraseña) no inicializa nada: se corta.
  set +e
  restic cat config >/dev/null 2>&1
  rc=$?
  set -e
  if [ "$rc" -eq 10 ]; then
    registro "repositorio nuevo: inicializando."
    restic init
  elif [ "$rc" -ne 0 ]; then
    registro "no se pudo abrir el repositorio (código $rc)." >&2
    exit 1
  fi
  registro "archivos de ${origen} cada ${intervalo}s, conservar ${conservar}, podar cada ${poda}s."
  ultima_poda=0
  while true; do
    if salida="$(restic backup --host salud --tag archivos --json --quiet "$origen")"; then
      id="$(printf '%s\n' "$salida" | sed -n 's/.*"snapshot_id":"\([0-9a-f]\{8\}\).*/\1/p' | tail -n 1)"
      latir respaldo_archivos "snapshot ${id:-?}"
    else
      registro "falló la copia de archivos; reintento en ${intervalo}s." >&2
    fi
    ahora="$(date +%s)"
    if [ $((ahora - ultima_poda)) -ge "$poda" ]; then
      if restic forget --host salud --tag archivos --keep-within "$conservar" --prune; then
        ultima_poda="$ahora"
      else
        registro "falló la poda; las copias siguen ahí." >&2
      fi
    fi
    sleep "$intervalo"
  done
}

case "$MODO" in
  base) base ;;
  archivos) archivos ;;
  *) echo "uso: respaldo-continuo.sh base|archivos" >&2; exit 2 ;;
esac
