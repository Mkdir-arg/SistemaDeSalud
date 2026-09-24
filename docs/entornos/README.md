# Dos entornos locales

Levantados y verificados el **17/09/2026** sobre el `main` actual (commit `4947633`).

| | Entorno **vacío** | Entorno **demo** |
|---|---|---|
| Para qué | Aprender a configurar el sistema desde cero | Mostrarlo funcionando, para vender |
| Aplicación | <http://localhost:8081> | <http://localhost:8082> |
| API directa | <http://localhost:8001/api/docs/> | <http://localhost:8002/api/docs/> |
| Proyecto Docker | `salud-vacio` | `salud-demo` |
| Datos | ninguno, salvo un superusuario | 3 instituciones, 757 casos, finanzas y financiadores |
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
volver a sembrar (~15 minutos); en el vacío, perder lo que hayas configurado.

---

## Rehacer el entorno demo desde cero

El orden **no es opcional**: `seed_los_aromos` aborta si encuentra una sola
institución, usuario o caso, así que va primero y sin la siembra automática del
arranque (por eso los dos compose ponen `SEED_DEMO=0` y `SEED_GUARDIA=0`).

```bash
$DEMO down -v
$DEMO up -d
# esperá a que backend quede "healthy": $DEMO ps

$DEMO exec -e DEMO_LOS_AROMOS_PASSWORD='LosAromos2026!' backend \
  python manage.py seed_los_aromos --confirmar ESCENARIO_LOS_AROMOS

$DEMO exec -e DEMO_FINANCIADORES_PASSWORD='Financiadores2026!' backend \
  python manage.py seed_financiadores --confirmar ESCENARIO_FINANCIADORES

$DEMO exec backend python manage.py seed_guardia
$DEMO exec backend python manage.py seed_volumen
$DEMO exec backend python manage.py seed_faltantes --institucion 2
$DEMO exec backend python manage.py seed_red
```

`seed_red` va al final y **por separado**. `seed_volumen` sólo arma la red cuando
se lo corre con `--rehacer`; sin ese flag deja el módulo de traslados vacío, que
es peor que no tenerlo: parece que la función existe y no anda.

`--institucion 2` en `seed_faltantes` **no se puede omitir**: sin él, el comando
elige la primera institución activa, que acá es Los Aromos, y le carga a esa los
pedidos de farmacia y los bloqueos de agenda que corresponden a Hospital Central.

`seed_volumen` fecha los casos contra *ahora*. Si la demo es otro día, volvé a
correr `seed_volumen --rehacer` ese día, o la cola de espera aparecerá con
pacientes esperando desde hace semanas.

---

## Decisiones de esta preparación

**Dos instituciones en el mismo entorno demo.** `seed_los_aromos` exige una base
vacía, pero `seed_guardia` borra sólo dentro de *su* institución. Sembrando en el
orden de arriba conviven Los Aromos (finanzas profundas, un año de historia) y
Hospital Central (operación clínica densa), y la demo puede mostrar la plataforma
gobernando dos efectores con madurez distinta.

**El circuito de financiadores entra en un área nueva.** «Consultorios externos»
la crea `seed_financiadores`. El reparto distribuye cada gasto entre las
atenciones elegibles *de su área*, así que sumar atenciones a un área con gastos
repartidos le cambia la porción a todas las demás. Hacerlo sobre las áreas
existentes habría reescrito en silencio las cifras por atención ya verificadas en
[`guia-los-aromos.md`](../funcionalidades/finanzas-costos/guia-los-aromos.md). Se
comprobó después de sembrar: septiembre sigue en **$750.000** aprobados y la
atención de Clara Benítez sigue en **$23.500** directos y **$92.500** compartidos,
idénticos a los documentados.

**Sin TLS y sin HSTS.** Con `DEBUG=false` el sistema fuerza HTTPS; en local no
hay certificado, así que los dos entornos traen `DJANGO_SSL_REDIRECT=false`. Y
`DJANGO_HSTS_SECONDS=0`, porque el valor por defecto es un año con subdominios:
si el navegador lo recibe para `localhost`, te fuerza https en `localhost` para
**todos** tus proyectos locales y revertirlo exige limpiar el estado HSTS.

**Sólo `backend` migra.** El Compose base configura los procesos de fondo con
`EJECUTAR_MIGRACIONES=0` cuando usan el entrypoint y los hace esperar a que
`backend` esté sano. `repartos` usa `entrypoint: python`: no ejecuta migraciones,
pero también espera al esquema. Cuatro contenedores
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
