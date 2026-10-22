#!/usr/bin/env bash
# Corre un comando de manage.py en el contenedor de la demo y espera a que termine.
#
#   correr-remoto.sh <nombre> <segundos máximos> <comando de manage.py...>
#
# Railway corta las sesiones SSH largas (unos 2 minutos) pero el proceso remoto
# sigue. Por eso el comando no corre dentro de la sesión: se lanza desacoplado
# (setsid nohup), con salida y código de salida a archivos en /tmp, y se sondea
# con sesiones cortas. Cada sondeo muestra lo nuevo del log.
#
# Si cambia el hostname entre sondeos, el contenedor se reemplazó (un merge a main
# redesplegó cauce-api) y el proceso murió con él: seed_entorno_demo corre en una
# transacción, así que la base quedó como estaba. Se falla con ese mensaje.
#
# Necesita el host `demo` en ~/.ssh/config (lo arma el workflow).
set -euo pipefail

nombre=$1 tope=$2
shift 2
comando="python manage.py $*"
dir="/tmp/resembrar-${GITHUB_RUN_ID:-local}"
log="$dir/$nombre.log" salida="$dir/$nombre.exit"

remoto() { ssh demo sh; }

# ssh.railway.com a veces no acepta la conexión: un sondeo que falla no es un
# seed que falla. Se tolera hasta 5 minutos de fallas seguidas.
FALLAS_TOLERADAS=10
INTERVALO=30

host=""
for intento in 1 2 3; do
  if host=$(remoto <<EOF
set -e
cd /app
mkdir -p $dir
rm -f $log $salida
setsid nohup sh -c 'PYTHONUNBUFFERED=1 $comando > $log 2>&1; echo \$? > $salida' < /dev/null > /dev/null 2>&1 &
hostname
EOF
  ); then
    break
  fi
  host=""
  [ "$intento" = 3 ] && break
  echo "No se pudo lanzar (intento $intento); reintento en $INTERVALO s." >&2
  sleep "$INTERVALO"
done
[ -n "$host" ] || { echo "::error::No se pudo lanzar «$comando» por SSH."; exit 1; }
echo "Lanzado «$comando» en el contenedor $host."

inicio=$(date +%s)
leido=0 fallas=0
while :; do
  sleep "$INTERVALO"
  if estado=$(remoto <<EOF
hostname
cat $salida 2>/dev/null || echo corriendo
total=\$(wc -c < $log 2>/dev/null || echo 0)
echo \$total
tail -c +$((leido + 1)) $log 2>/dev/null | head -c \$((total - $leido))
EOF
  ); then
    fallas=0
  else
    fallas=$((fallas + 1))
    echo "Sondeo sin conexión ($fallas de $FALLAS_TOLERADAS)." >&2
    [ "$fallas" -lt "$FALLAS_TOLERADAS" ] || { echo "::error::Se perdió la conexión con la demo; «$nombre» puede seguir corriendo."; exit 1; }
    continue
  fi

  actual=$(sed -n 1p <<<"$estado")
  codigo=$(sed -n 2p <<<"$estado")
  total=$(sed -n 3p <<<"$estado")
  nuevo=$(sed -n '4,$p' <<<"$estado")
  [ -z "$nuevo" ] || printf '%s\n' "$nuevo"
  leido=${total:-$leido}

  if [ "$actual" != "$host" ]; then
    echo "::error::El contenedor cambió ($host → $actual): se redesplegó cauce-api y «$nombre» murió. La transacción se revirtió; volvé a correr el workflow."
    exit 1
  fi
  if [ "$codigo" != "corriendo" ]; then
    echo "«$nombre» terminó con código $codigo en $(( $(date +%s) - inicio )) s." | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
    [ "$codigo" = "0" ] || { echo "::error::«$comando» falló (código $codigo)."; exit 1; }
    exit 0
  fi
  if [ $(( $(date +%s) - inicio )) -ge "$tope" ]; then
    echo "::error::«$nombre» sigue corriendo después de $tope s; no se espera más. Revisá $log en el contenedor."
    exit 1
  fi
done
