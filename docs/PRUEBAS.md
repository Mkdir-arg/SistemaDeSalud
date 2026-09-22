# Cómo correr las pruebas

> Leé esto **antes** de la primera corrida. Hay trampas del entorno que producen
> cientos de fallas que no son reales, y cada una cuesta una corrida perdida.

---

## La versión corta

```bash
DC="docker compose"

# Los procesos de fondo compiten por Postgres y tumban la corrida.
$DC stop tiempos costos repartos respaldos

$DC exec -T backend python manage.py test --noinput
```

Frontend:

```bash
cd frontend && npm run e2e
```

## Las tres trampas

### 1. Sin `DEBUG=true`, todo da 301

Con `DJANGO_DEBUG=false` se activa el redirect a HTTPS y **todas** las pruebas de API
reciben un 301 antes de llegar al código. Da cientos de fallas y ninguna es real.

El síntoma es inconfundible:

```
AttributeError: 'HttpResponsePermanentRedirect' object has no attribute 'data'
```

Se resuelve con `DJANGO_DEBUG=true` o `DJANGO_SSL_REDIRECT=false`. El override de
desarrollo ya trae `DEBUG=true`; los compose de `docs/entornos/` no, así que ahí hay
que pasar el override que corresponda.

### 2. Con los procesos de fondo vivos, Postgres se queda sin conexiones

`tiempos`, `costos`, `repartos` y `respaldos` mantienen conexiones abiertas. A mitad
de la suite Postgres se queda sin cupo y aparecen decenas de errores así:

```
ERROR: setUpClass (apps.finanzas.test_cobros.CobrosApiTests)
  ...
  File ".../django/db/backends/base/base.py", line 256, in connect
psycopg.OperationalError: connection failed
```

Son de infraestructura, no de código. **Pararlos antes de correr.**

### 3. Dos corridas a la vez se destruyen entre sí

Las dos usan la misma base `test_salud`. La que termina primero la borra, y la otra
empieza a fallar con:

```
FATAL: database "test_salud" does not exist
DETAIL: It seems to have just been dropped or renamed.
```

O, si la primera todavía está migrando, un `deadlock detected` durante la creación
de la base.

Pasa más de lo que parece: el contenedor es compartido, y basta con que otra persona
—o un agente— esté corriendo la suite.

**Antes de una corrida larga, comprobá que no haya otra:**

```bash
docker compose exec db psql -U salud -d postgres \
  -c "select pid, datname, state from pg_stat_activity where datname like 'test%';"
```

Si hay una y no es tuya, usá una base propia en vez de pelear por la misma. Creá un
módulo de settings efímero:

```python
# backend/settings_local_test.py  (no lo commitees)
from config.settings import *  # noqa: F401,F403

DATABASES["default"]["TEST"] = {"NAME": "test_salud_lo_que_sea"}  # noqa: F405
```

```bash
docker compose exec backend python manage.py test --settings=settings_local_test --noinput
```

Y limpiá al terminar:

```bash
docker compose exec db psql -U salud -d postgres -c "drop database if exists test_salud_lo_que_sea;"
```

## Correr una parte

```bash
# Una app
... manage.py test apps.finanzas

# Un módulo
... manage.py test apps.finanzas.test_editor_permisos

# Una prueba
... manage.py test apps.finanzas.test_editor_permisos.EditorPermisosApiTests.test_consulta_conserva_alcances_y_separa_otra_membresia_sin_filtrar_otra_institucion
```

Para diagnosticar, `-v 2` muestra el nombre de cada prueba a medida que corre.

## Qué hay

| Suite | Qué cubre |
|---|---|
| `apps.*` (backend) | ~1767 pruebas. Incluye concurrencia real con PostgreSQL: dos conexiones compitiendo por el último cupo de cobertura, dos aprobadores sobre el mismo gasto, dos workers sobre el mismo reparto |
| `frontend/e2e/*.spec.js` | 35 suites de Playwright, en dos temas |
| `npm run auditar` | Clases de Tailwind que no existen. Como el escaneo es textual, una clase mal escrita no rompe el build: simplemente no pinta |
| `manage.py spectacular --fail-on-warn` | El esquema OpenAPI se genera sin avisos |
| `manage.py check --deploy` | Endurecimiento para producción. Hay una prueba que lo corre |

Las pruebas de concurrencia **exigen PostgreSQL**; contra SQLite no valen y se
saltean. Por eso CI levanta un Postgres 16, la misma mayor que producción.

## Dos specs que conviene borrar

`e2e/_tmp_caso7.spec.js` y `e2e/_tmp_turnos.spec.js` quedaron de una prueba manual,
apuntan a una interfaz que ya cambió y cada uno consume 120 s de timeout. No prueban
nada que las otras no cubran. Junto con los `_tmp_A*.png` del mismo directorio.

`e2e/finanzas-feedback.spec.js` conserva expectativas de una versión anterior de
Finanzas: **revisarlo antes de usarlo como evidencia**. Necesita
`FINANZAS_DEMO_PASSWORD` en el entorno y su configuración es
`playwright.finanzas.config.js`. No confundirlo con `playwright.finanzas-ui.config.js`,
cuya suite usa respuestas simuladas y no requiere credenciales ni escribe datos.

## En CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) corre en cada push a `main`
y en cada pull request: comprobaciones de Django, consistencia de migraciones,
pruebas de backend contra Postgres 16, build del frontend, auditor de clases y
generación del esquema.

Los recorridos de Playwright **no** corren ahí todavía: necesitan el stack completo
y datos sembrados, que son unos 15 minutos.

## El estado de hoy

**`main` está en rojo**: unas 50 fallas y 3 errores. No es aleatorio y no es del
entorno.

La causa es `c4eefbb` del 18/09, que amplió la herencia financiera del admin de
institución de dos acciones a las dieciocho —decisión aprobada—. Los fixtures usan
una membresía con rol `admin` como portador neutro para comprobar que un permiso
viene de la concesión y no del rol; al heredar todo, esas afirmaciones negativas
pasan solas y la prueba falla.

Está medido: revirtiendo esa línea en una corrida aislada, las mismas 724 pruebas
bajan a 4 fallas. **La regla de producción es la correcta; lo viejo son los
fixtures**, en unos 16 módulos.

El diagnóstico completo y el plan para atacarlo están en
[`docs/plans/2026-09-22-prompt-main-en-rojo.md`](plans/2026-09-22-prompt-main-en-rojo.md).
