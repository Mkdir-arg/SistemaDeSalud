#!/bin/sh
# Arranque de PostgreSQL con archivado continuo de WAL opcional (#172, AUD-017).
#
# Sin WALG_S3_PREFIX la base arranca exactamente como la imagen oficial:
# archive_mode queda apagado. Con WALG_S3_PREFIX, la configuración tiene que
# estar completa; si falta algo, la base NO arranca. Un archivado a medio
# configurar es peor que ninguno: `archive_command` falla en cada segmento,
# PostgreSQL guarda el WAL en pg_wal hasta llenar el disco y la base se detiene.
#
# Los parámetros van por línea de comandos (-c) y no en postgresql.conf: no se
# toca PGDATA, y quitar las variables vuelve al comportamiento de siempre.
set -eu

if [ "${1:-}" = "postgres" ] && [ -n "${WALG_S3_PREFIX:-}" ]; then
  faltan=""
  for nombre in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY WALG_LIBSODIUM_KEY; do
    eval "valor=\${$nombre:-}"
    [ -n "$valor" ] || faltan="$faltan $nombre"
  done
  [ -n "${AWS_REGION:-}${AWS_ENDPOINT:-}" ] || faltan="$faltan AWS_REGION/AWS_ENDPOINT"
  if [ -n "$faltan" ]; then
    echo "WALG_S3_PREFIX está definido pero faltan:$faltan." >&2
    echo "No arranco: el archivado fallaría y el WAL llenaría el disco." >&2
    exit 1
  fi
  timeout="${ARCHIVO_WAL_TIMEOUT:-300}"
  echo "Archivado continuo de WAL encendido (archive_timeout=${timeout}s)."
  # `%p` es la ruta del segmento relativa a PGDATA; wal-g lee su configuración
  # del entorno del postmaster, que heredan los procesos del archivador.
  set -- "$@" \
    -c archive_mode=on \
    -c "archive_command=wal-g wal-push %p" \
    -c "archive_timeout=${timeout}"
elif [ "${1:-}" = "postgres" ]; then
  echo "Archivado continuo de WAL apagado (sin WALG_S3_PREFIX)."
fi

exec docker-entrypoint.sh "$@"
