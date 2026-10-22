# Resembrar la demo compartida (Railway)

Cómo volver a cargar los datos de la demo que usa el equipo, completa o por
partes. Es el procedimiento que se corrió con éxito el **22/10/2026**.

La demo es el proyecto de Railway `faithful-commitment`, entorno `production`
(workspace Icore), con `ENTORNO=demo`. Todos los comandos corren **dentro** del
servicio `cauce-api`, con `railway ssh`.

> **No usar `railway run`.** Ejecuta el código de tu máquina con las variables
> del servicio, contra la base remota: corre otra versión del código y deja los
> archivos en tu disco en lugar del bucket.

## Qué camino elegir

| Necesito… | Camino | ¿Borra datos? |
|---|---|---|
| Dejar la demo como nueva | [A. Resembrado completo](#a-resembrado-completo) | **Sí, toda la base y los archivos del bucket** |
| Que la demo parezca recién cargada a una hora fija | [B. Completo anclado](#b-resembrado-completo-anclado) | **Sí, todo** |
| Agregar OSTEL a una demo que no lo tiene | [C. Solo OSTEL](#c-solo-ostel) | No |
| Rehacer OSTEL porque se ensayó sobre él | Camino A (no hay borrado parcial) | **Sí, todo** |
| Renovar el turno y la sala de espera de la paciente del portal | [D. Solo el portal del paciente](#d-solo-el-portal-del-paciente) | No |
| Comprobar que todas las cuentas entran | [Verificar los ingresos](#verificar-los-ingresos) | No |

## Antes de empezar

1. **CLI de Railway** con sesión iniciada (`railway login`) y una clave SSH
   registrada en tu cuenta (`railway ssh` ofrece registrarla la primera vez).
2. **Vincular una carpeta fuera del repo**, una sola vez:

   ```bash
   mkdir -p ~/railway-demo && cd ~/railway-demo
   railway link --project faithful-commitment --environment production --service cauce-api
   ```

   Los comandos de esta guía se corren desde esa carpeta.
3. **Shell:** los bloques usan sintaxis de bash (en Windows, Git Bash). Los
   que mandan un script por `<<'EOF'` no funcionan en PowerShell.
4. **`railway ssh` a veces da *timeout* al conectar** (`Connection timed out`
   al puerto 22). No es un error de la demo: repetir el comando.

## A. Resembrado completo

`seed_entorno_demo` **vacía toda la base y los archivos de la app en el bucket**
y carga el entorno entero. El 22/10 tardó **985 s (~16 min)**. Mientras corre,
las tablas quedan bloqueadas y la aplicación espera.

### 1. Avisar y elegir el momento

- Avisar al equipo: se pierde todo lo que hayan cargado u operado en la demo.
- **No mergear a `main` mientras corre.** Railway redespliega `cauce-api` en cada
  merge, el contenedor se reemplaza y la carga muere con él. Como corre en una
  transacción, la base vuelve a como estaba y hay que empezar de nuevo.

### 2. Comprobar el bucket (solo lee)

```bash
railway ssh --service cauce-api -- python manage.py shell -c "from apps.demo import archivos; print(len(archivos.claves_a_vaciar()), 'archivos en el bucket')"
```

Tiene que imprimir un número. Si falla con `SignatureDoesNotMatch`, `cauce-api`
tiene credenciales viejas del bucket `cauce-adjuntos`: **no sembrar**.
Redesplegar el servicio para que tome las actuales y volver a comprobar:

```bash
railway service redeploy --service cauce-api --from-source --yes
```

### 3. Lanzar la carga desacoplada

`railway ssh` corta las sesiones largas (unos 2 minutos), pero el proceso
remoto sigue. Para saber cuándo termina y si falló, la carga se lanza
desacoplada de la sesión, con la salida y el código de salida en `/tmp`:

```bash
railway ssh --service cauce-api -- sh <<'EOF'
cd /app
rm -f /tmp/seed-entorno.log /tmp/seed-entorno.exit
setsid nohup sh -c 'PYTHONUNBUFFERED=1 python manage.py seed_entorno_demo --noinput > /tmp/seed-entorno.log 2>&1; echo $? > /tmp/seed-entorno.exit' < /dev/null > /dev/null 2>&1 &
echo "Lanzada en el contenedor $(hostname)"
EOF
```

Anotar el nombre del contenedor que imprime.

### 4. Seguirla hasta que termine

Repetir cada uno o dos minutos:

```bash
railway ssh --service cauce-api -- sh <<'EOF'
echo "Contenedor: $(hostname)"
if [ ! -f /tmp/seed-entorno.log ]; then
  echo "No hay ninguna carga en este contenedor."
else
  echo "Código de salida: $(cat /tmp/seed-entorno.exit 2>/dev/null || echo 'todavía corre')"
  tail -n 5 /tmp/seed-entorno.log
fi
EOF
```

- **Código 0:** terminó bien. El log cierra con `Entorno de demo cargado en N s`
  y la tabla de usuarios.
- **Otro código:** falló y se revirtió todo (la base y el bucket quedan como
  estaban). El motivo está en el log: `cat /tmp/seed-entorno.log`.
- **Cambió el contenedor** o dice que no hay ninguna carga: se redesplegó `cauce-api` y la
  carga murió. La base quedó como estaba; volver al paso 2.

### 5. Cargar OSTEL

`seed_entorno_demo` no incluye OSTEL. Sobre la base recién cargada:

```bash
railway ssh --service cauce-api -- python manage.py seed_ostel_demo
```

Imprime un JSON con `"existente": false` y el inventario creado. Si la sesión se
corta antes de ver la salida, volver a correrlo es seguro: con `"existente": true`
solo devuelve el inventario, sin cambiar nada.

### 6. Verificar

Seguir [Verificar los ingresos](#verificar-los-ingresos). El 22/10 entraron las
66 cuentas (64 institucionales y 2 del portal del paciente).

## B. Resembrado completo anclado

Para una demo que tiene que verse recién cargada a una hora fija (por ejemplo,
cargarla la noche anterior). Es el camino A con `--ancla` en el paso 3; la
línea del `setsid` queda así:

```bash
setsid nohup sh -c 'PYTHONUNBUFFERED=1 python manage.py seed_entorno_demo --noinput --ancla 2026-10-30T09:00 > /tmp/seed-entorno.log 2>&1; echo $? > /tmp/seed-entorno.exit' < /dev/null > /dev/null 2>&1 &
```

La hora es local (`AAAA-MM-DDTHH:MM`). Hasta esa hora la aplicación muestra datos
con fecha futura, y lo que se opere antes queda desordenado: después de ensayar,
volver a cargar con la misma ancla. Las autorizaciones abiertas vencen unas 48 h
después del ancla.

OSTEL (paso 5) no tiene ancla: se carga con la hora real.

## C. Solo OSTEL

`seed_ostel_demo` **agrega** el escenario OSTEL sin tocar el resto. No tiene
opción de borrado.

```bash
railway ssh --service cauce-api -- python manage.py seed_ostel_demo
```

| Resultado | Qué significa |
|---|---|
| JSON con `"existente": false` | Se cargó ahora |
| JSON con `"existente": true` | Ya estaba. No restablece claves, permisos, pendientes ni fechas |
| `Hay identificadores reservados de OSTEL sin marcador completo` | Alguien creó datos con nombres de OSTEL a mano, o quedó una carga rota. **Investigar antes de tocar nada** |
| `El marcador OSTEL está incompleto o cambió su alcance` | Lo mismo: investigar, no reparar a mano |

**No hay forma de rehacer solo OSTEL.** Si se ensayó sobre él y hay que dejarlo
como nuevo, el único camino es el A (resembrado completo y después OSTEL). No
borrar datos a mano para «forzar» una recarga: el comando rechaza a propósito
cargar sobre restos.

Más detalle del escenario: [Operación técnica del escenario OSTEL](operacion-demo-ostel.md).

## D. Solo el portal del paciente

`seed_portal_demo` crea o **pone al día** la cuenta de Andrea Paniagua
(`andrea.paniagua@paciente.test`): turno reservado, estudios y lugar en la sala
de espera de Cardiología. Ya corre como último paso de `seed_entorno_demo`. Suelto
sirve para renovar el turno o la sala de espera después de haberlos usado en un
ensayo, sin vaciar nada:

```bash
railway ssh --service cauce-api -- python manage.py seed_portal_demo
```

Necesita que la base tenga la carga completa: si falta la paciente en Hospital
Central, falla y pide correr el camino A. La clave es la de `DEMO_PASSWORD`.

La paciente del portal de OSTEL (`paciente@ostel.demo.test`) es de
`seed_ostel_demo` y no se renueva así.

## Verificar los ingresos

Todas las cuentas usan la clave de `DEMO_PASSWORD` (hoy `demo1234`, pública a
propósito). La clave **se fija al sembrar**: cambiar la variable después no
cambia las cuentas existentes; hay que volver a sembrar.

**Una cuenta suelta:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Content-Type: application/json" \
  -d '{"email":"admin@ostel.demo.test","password":"demo1234"}' \
  https://cauce-api-production.up.railway.app/api/auth/token/
```

`200` es OK. Para las cuentas del portal del paciente la ruta es
`/api/mi/cuenta/ingresar/`.

**Todas las cuentas.** Primero la lista, desde la base:

```bash
railway ssh --service cauce-api -- sh <<'EOF' | sed -n 's/^CUENTAS=//p' > cuentas.json
cd /app && python manage.py shell <<'PY'
import json
from apps.accounts.models import Usuario
from apps.portal.models import CuentaPaciente
inst = [u.email for u in Usuario.objects.filter(is_active=True).order_by("email") if u.has_usable_password()]
portal = list(CuentaPaciente.objects.filter(activa=True, email_verificado_at__isnull=False).order_by("email").values_list("email", flat=True))
print("CUENTAS=" + json.dumps({"institucionales": inst, "portal": portal}))
PY
EOF
```

Después, el ingreso de cada una (en tu máquina):

```bash
DEMO_PASSWORD=demo1234 python - cuentas.json <<'PY'
import json, os, sys, time, urllib.request, urllib.error
API = "https://cauce-api-production.up.railway.app"
RUTAS = {"institucionales": "/api/auth/token/", "portal": "/api/mi/cuenta/ingresar/"}
cuentas, fallidas, total = json.load(open(sys.argv[1])), [], 0
for tipo, ruta in RUTAS.items():
    for email in cuentas[tipo]:
        total += 1
        datos = json.dumps({"email": email, "password": os.environ["DEMO_PASSWORD"]}).encode()
        pedido = urllib.request.Request(API + ruta, datos, {"Content-Type": "application/json"})
        try:
            codigo = urllib.request.urlopen(pedido, timeout=30).status
        except urllib.error.HTTPError as error:
            codigo = error.code
        if codigo != 200:
            fallidas.append((email, codigo))
        time.sleep(0.3)
print(f"{total - len(fallidas)} de {total} OK")
for email, codigo in fallidas:
    print(f"  FALLA {email}: {codigo}")
PY
```

**Límites de ingreso:** el institucional bloquea después de 10 fallos por email
y 100 por IP cada 15 minutos (los ingresos exitosos no cuentan). El del portal
cuenta todos los intentos: 30 por hora por IP, 10 por email e IP y 50 por email. Si
la clave está mal, la verificación completa gasta esos cupos rápido: probar
antes una cuenta suelta.

## Lo que no se usa en la demo de Railway

- **`seed_volumen --rehacer`**: vuelve a correr `seed_guardia` (que borra los
  casos) y el volumen, pero no las demás cargas que `seed_entorno_demo` arma
  sobre esos casos (finanzas, financiadores, farmacia, portal). Es para la base
  local de desarrollo; en la demo compartida, camino A.
- **Los `seed_*` sueltos** que encadena `seed_entorno_demo` (`seed_guardia`,
  `seed_financiadores`, `seed_comprador`…): dependen del orden y algunos se
  niegan a correr sobre datos ya cargados (`seed_financiadores`, por ejemplo).
  En la demo, siempre por el camino A.
- **`seed_padron_demo`**: exige una base PostgreSQL llamada `padron130`; es para
  el entorno del padrón, no para esta demo
  ([guía](guia-demo-padron-local.md)).
- **`seed_demo`** y las variables `SEED_DEMO` / `SEED_GUARDIA`: son del
  arranque de los entornos locales. En Railway quedan en `0`.
