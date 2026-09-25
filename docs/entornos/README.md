# Dos entornos locales

Levantados y verificados el **17/09/2026** sobre el `main` actual (commit `4947633`).

| | Entorno **vacío** | Entorno **demo** |
|---|---|---|
| Para qué | Aprender a configurar el sistema desde cero | Mostrarlo funcionando, para vender |
| Aplicación | <http://localhost:8081> | <http://localhost:8082> |
| API directa | <http://localhost:8001/api/docs/> | <http://localhost:8002/api/docs/> |
| Proyecto Docker | `salud-vacio` | `salud-demo` |
| Datos | ninguno, salvo un superusuario | 3 instituciones, unos 2.300 casos en 12 meses, finanzas y financiadores |
| Guía | [Configurar desde cero](guia-configuracion-desde-cero.md) | [Guion de demo](guia-demo-comercial.md) |

Corren **a la vez**: proyectos, redes, volúmenes y puertos distintos. Son siete
contenedores cada uno, así que si la máquina va justa, bajá el que no estés usando.

---

## Archivos que agrega esta preparación

`docker-compose.vacio.yml`, `docker-compose.demo.yml` y `seed_financiadores.py` quedaron versionados el 18/09. Los `.env.*` no: los cubre `.gitignore`, como corresponde.

| Archivo | Qué es |
|---|---|
| `docker-compose.vacio.yml` · `docker-compose.demo.yml` | Puertos, proyecto y ajustes propios de cada entorno |
| `.env.vacio` · `.env.demo` | Claves y variables de cada entorno (ya cubiertos por `.gitignore`) |
| `backend/apps/financiadores/management/commands/seed_financiadores.py` | Siembra del circuito de obras sociales (código nuevo) |

Los dos `docker-compose.*.yml` se usan **junto** al `docker-compose.yml` base y
**sin** el override de desarrollo, así corren como en un despliegue real
(gunicorn + nginx) en lugar de con recarga en caliente.

---

## Levantar

```bash
# Entorno vacío
docker compose -p salud-vacio --env-file .env.vacio \
  -f docker-compose.yml -f docker-compose.vacio.yml up -d

# Entorno demo
docker compose -p salud-demo --env-file .env.demo \
  -f docker-compose.yml -f docker-compose.demo.yml up -d
```

Conviene guardarse el prefijo en una variable, porque se repite en cada comando:

```bash
VACIO="docker compose -p salud-vacio --env-file .env.vacio -f docker-compose.yml -f docker-compose.vacio.yml"
DEMO="docker compose -p salud-demo --env-file .env.demo -f docker-compose.yml -f docker-compose.demo.yml"

$DEMO ps
$DEMO logs -f backend
$DEMO exec backend python manage.py shell
```

## Bajar

```bash
$VACIO stop          # apaga, conserva los datos
$VACIO down -v       # borra TAMBIÉN la base y los adjuntos
```

`down -v` destruye el volumen de Postgres. En el entorno demo eso significa
volver a sembrar (~5 minutos, ver abajo); en el vacío, perder lo que hayas
configurado.

---

## Rehacer el entorno demo desde cero

Un solo comando **vacía la base** y carga todo, en orden y en una sola
transacción: si un paso falla, la base queda como estaba.

```bash
$DEMO up -d --build       # la imagen trae el código horneado: sin --build corre el de la última construcción
$DEMO exec backend python manage.py seed_entorno_demo --noinput
```

Tarda **entre 5 y 7 minutos** (medido en Docker local), y mientras corre la aplicación no responde:
el vaciado bloquea todas las tablas hasta el final. Al terminar imprime cada
usuario, su perfil y el trabajo pendiente que va a encontrar al entrar.

**Sólo corre donde `ENTORNO` no es `produccion`.** El `docker-compose.yml` base la
fija en `produccion`; `docker-compose.demo.yml` la pone en `demo`. No hace falta
bajar el entorno ni borrar el volumen.

**Clave de los usuarios:** la de `DEMO_PASSWORD`. Si no está definida es
`demo1234`, y el comando lo advierte, porque esa clave está en el repositorio.
En `.env.demo` o en las variables del servicio, nunca en un archivo versionado.

**Las fechas son relativas al momento de la carga** (ver
`backend/apps/demo/calendario.py`):

- Hay doce meses de historia que terminan ese momento.
- El mes en curso —el que abren por defecto Finanzas, Coberturas y la actividad
  del financiador— tiene su movimiento repartido entre el 1° y ese momento.
- Lo pendiente es de las últimas horas: casos abiertos, pacientes en la sala de
  espera, autorizaciones con 48 h de plazo.

**Para una demo con hora fija, cargala antes con `--ancla`.** Con
`--ancla 2026-10-01T08:00` la carga queda como si se hubiera hecho el 01/10 a
las 8, aunque se corra días antes: a las 9 hay pacientes esperando desde hace un
rato, octubre tiene movimiento y las autorizaciones abiertas vencen el 03/10.

```bash
$DEMO exec backend python manage.py seed_entorno_demo --noinput --ancla 2026-10-01T08:00
```

Dos consecuencias hasta que llega el ancla. La aplicación muestra datos con
fecha futura, con esperas negativas en la sala de espera. Y lo que se opere antes
—un ensayo— queda con la hora real, anterior a esos datos: **después de ensayar,
volvé a cargar con la misma ancla.** Sin `--ancla`, el momento es ahora, y la
carga conviene hacerla el mismo día.

Qué carga, por paso:

| Paso | Qué deja |
|---|---|
| `seed_los_aromos` | Finanzas y costos de Los Aromos: gastos, repartos, cuentas y pagos de 12 meses; pendientes de aprobación en el mes en curso |
| `seed_financiadores` | Tres financiadores (uno con convenio propuesto sin aceptar), padrón con bajas, 12 meses de atenciones con copago, autorizaciones pendientes, observada, aprobadas y rechazadas |
| `seed_guardia` | Estructura de Hospital Central: áreas, staff, grupos, flujos, farmacia, agendas |
| `seed_volumen` | 365 días de guardia, especialidades, estudios e internación; turnos, bloqueo de agenda y pantallas de llamados |
| `seed_roles` | Plataforma, auditoría, reportes y administración de Hospital Central |
| `seed_farmacia` | Pedidos de reposición en cada estado y consumos imputados a pacientes |
| `seed_red` | Villa Real y los traslados: resueltos, pendientes y uno aceptado sin despachar |
| `seed_accesos` | Registro de accesos clínicos de los últimos 45 días, para la auditoría |

Cada `seed_*` también se puede correr suelto. Declara en su docstring qué necesita
antes y qué carga. `seed_los_aromos` y `seed_financiadores` no se mezclan con
una carga anterior propia: para rehacerlos se usa `seed_entorno_demo`.

### En Railway

Pendiente de verificar contra el proyecto real: esta sección describe lo que
hace falta, no un procedimiento probado.

1. **Respaldo o confirmación de que la base es descartable** (criterio 6 del
   #65). El comando vacía la base entera.
2. En el servicio del backend, variables `ENTORNO=demo`, `DEMO_PASSWORD` (se
   guarda fuera del repositorio), `SEED_DEMO=0` y `SEED_GUARDIA=0`. Cambiar
   variables **redespliega el servicio**: esperá a que quede sano antes del paso 3.
3. Desde una consola **del contenedor** del backend (`railway ssh` o la consola
   web): `python manage.py seed_entorno_demo --noinput --ancla 2026-10-01T08:00`.
   No uses `railway run`:
   corre el código de tu máquina con las variables del servicio, y necesita la
   URL pública de la base.
4. Revisar el resumen que imprime: ningún usuario operativo sin trabajo y el
   aviso de clave por defecto ausente.

El servicio productivo, si alguna vez comparte proyecto, tiene que tener
`ENTORNO=produccion` explícito: sin la variable, la aplicación asume
`desarrollo` y el comando corre. Lo mismo vale para cada servicio que use la
imagen del backend (tiempos, repartos, costos, respaldos).

### El día de la demo

La demo del 01/10 es a las 9: la idea es **no tener que cargar nada esa mañana.**

1. **Apenas haya acceso a Railway, cargá con el ancla** del día de la demo, con el
   procedimiento de arriba: `--ancla 2026-10-01T08:00`. Anotá cuánto tardó. Si la
   consola corta la sesión antes de que termine, la carga se revierte entera y
   la base queda como estaba: mejor descubrirlo con días de margen.
2. **Verificá con el resumen del comando** que no haya líneas «Sin trabajo
   pendiente» ni el aviso de clave por defecto, y entrá con un usuario de cada
   lado (hospital, financiador, finanzas). Las fechas se ven futuras hasta el
   01/10: es lo esperado.
3. **Si ensayás el recorrido, volvé a cargar con la misma ancla** al terminar. El
   ensayo consume los casos preparados, y no hay recarga parcial.
4. **El 30/09 a la tarde, última carga con la misma ancla**, y nadie opera hasta
   la demo.
5. **El 01/10 no hace falta cargar.** Si algo se rompió igual, la recarga sin
   ancla tarda entre 5 y 7 minutos, con la aplicación sin responder; si falla, la
   base queda con la carga anterior, que sigue sirviendo.

---

## Decisiones de esta preparación

**Dos instituciones en el mismo entorno demo.** Conviven Los Aromos (finanzas
profundas, un año de historia) y Hospital Central (operación clínica densa), y la
demo puede mostrar la plataforma gobernando dos efectores con madurez distinta.

**El circuito de financiadores entra en un área nueva.** «Consultorios externos»
la crea `seed_financiadores`. El reparto distribuye cada gasto entre las
atenciones elegibles *de su área*, así que sumar atenciones a un área con gastos
repartidos le cambia la porción a todas las demás. Hacerlo sobre las áreas
existentes habría reescrito en silencio las cifras por atención ya verificadas en
[`guia-los-aromos.md`](../funcionalidades/finanzas-costos/guia-los-aromos.md). Se
comprobó después de sembrar: el mes en curso sigue en **$750.000** aprobados y la
atención de Clara Benítez sigue en **$23.500** directos y **$92.500** compartidos,
idénticos a los documentados.

**Sin TLS y sin HSTS.** Con `DEBUG=false` el sistema fuerza HTTPS; en local no
hay certificado, así que los dos entornos traen `DJANGO_SSL_REDIRECT=false`. Y
`DJANGO_HSTS_SECONDS=0`, porque el valor por defecto es un año con subdominios:
si el navegador lo recibe para `localhost`, te fuerza https en `localhost` para
**todos** tus proyectos locales y revertirlo exige limpiar el estado HSTS.

**Sólo `backend` migra.** Los procesos de fondo arrancan con
`EJECUTAR_MIGRACIONES=0` y esperan a que `backend` esté sano. Cuatro contenedores
de la misma imagen corriendo `migrate` a la vez toman locks de DDL en distinto
orden y la migración puede quedar a mitad de camino con `django_migrations`
diciendo que terminó.

## Límites conocidos

- **El admin de Django (`/admin/`) no funciona por http en estos entornos.** Con
  `DEBUG=false` las cookies de sesión van marcadas `Secure` y el navegador no las
  manda sin TLS. La aplicación no lo necesita: usa JWT. Si hace falta el admin,
  levantá con `DJANGO_DEBUG=true`.
- **`/fhir/` no pasa por el puerto de la aplicación.** El nginx del frontend
  proxea `/api/`, `/admin/` y `/static/`, no `/fhir/`. Por eso cada entorno
  expone además el backend directo (8001 y 8002), que es donde responde la
  fachada FHIR.
- Las contraseñas de siembra de este documento son de un entorno local ficticio.
  No sirven para nada fuera de tu máquina y no deben reutilizarse.
