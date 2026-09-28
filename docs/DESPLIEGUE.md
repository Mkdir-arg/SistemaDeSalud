# Desplegar y operar I-Core Salud

> Qué necesita una instalación real, cómo se actualiza y **qué hacer cuando se
> pierde la base**. Escrito el 22/09/2026 contra el compose y los comandos del
> repositorio.

Esto **no** describe un despliegue existente: todavía no hay ninguno, y falta
decidir dónde se hospeda. Describe qué hay que tener resuelto antes de exponer el
sistema a un hospital, y es la lista contra la que conviene evaluar cualquier
proveedor.

Para levantar el sistema en tu máquina no es este el documento:
[`docs/entornos/`](entornos/README.md).

---

## 1. Qué se despliega

Siete servicios. Tres son la aplicación y **cuatro son procesos de fondo cuya muerte
no se nota desde afuera**:

| Servicio | Qué hace | Si se detiene |
|---|---|---|
| `db` | PostgreSQL 16 | Todo se cae, y se nota |
| `backend` | Django + gunicorn | Todo se cae, y se nota |
| `frontend` | nginx que sirve la app y proxea `/api/`, `/admin/` y `/static/` | Todo se cae, y se nota |
| `tiempos` | Reactiva las esperas vencidas y avisa demoras, cada 2 min | **El sistema responde normalmente**, pero un paciente que entró a «observación 6 horas» no vuelve nunca y los avisos de demora no salen |
| `repartos` | Procesa la distribución de gastos entre atenciones | Las solicitudes se acumulan en base y se recuperan al volver. No se pierde nada, pero los informes quedan desactualizados sin decirlo |
| `costos` | Recupera hechos de atención pendientes de costear | Igual: se acumulan |
| `respaldos` | Respaldo diario **con restauración verificada** | Deja de haber respaldos nuevos, en silencio |

**Esa es la razón de `/api/estado/`**: devuelve el latido de los cuatro y un 503 si
alguno se quedó callado. Es el endpoint que hay que monitorear. `/api/health/` es
otra cosa: responde si la instancia puede atender y si llega a la base, va sin
autenticación y por eso no cuenta nada del sistema.

> **Sólo `backend` aplica migraciones.** Los demás arrancan con
> `EJECUTAR_MIGRACIONES=0` y esperan a que esté sano. Cuatro contenedores de la
> misma imagen corriendo `migrate` a la vez toman locks de DDL en distinto orden y
> la migración puede quedar a mitad de camino, con `django_migrations` diciendo que
> terminó.

## 2. Antes de exponerlo

Lista de verificación. Cada punto tiene una forma concreta de fallar.

### Variables de entorno

Están todas documentadas en [`.env.example`](../.env.example). Las que no pueden
quedar en su valor de ejemplo:

- [ ] **`DATABASE_URL`**. Sin ella el sistema **cae a SQLite en silencio**: arranca,
      responde y parece andar hasta que alguien busca los datos.
- [ ] **`DJANGO_SECRET_KEY`** nueva. Con la de ejemplo, cualquiera que lea el
      repositorio puede firmar sesiones.
- [ ] **`DJANGO_DEBUG=false`**. Con `true`, Django muestra trazas completas ante un
      error y sirve `/media` directo.
- [ ] **`DJANGO_ALLOWED_HOSTS`** con el dominio real, o Django rechaza todo con 400.
- [ ] **`CORS_ALLOWED_ORIGINS`** con el origen real del navegador.
- [ ] **`ENTORNO=produccion`.** Si falta, la aplicación asume `desarrollo`, y ahí
      `seed_entorno_demo` puede **vaciar la base entera**. El `docker-compose.yml`
      la fija; en un despliegue sin compose (Railway y similares) hay que
      definirla a mano en el servicio.
- [ ] **`SEED_DEMO=0` y `SEED_GUARDIA=0`.** Sembrar datos ficticios sobre una
      instalación real es difícil de deshacer.
- [ ] **`SALUD_INTEGRACIONES_PERMITIDAS`** sólo con los hosts efectivamente
      autorizados. Viene vacía a propósito: la función está apagada hasta que
      infraestructura habilite cada host.

### TLS

- [ ] Certificado válido y renovación automática.
- [ ] `DJANGO_SSL_REDIRECT` en su valor por defecto (`true`).
- [ ] `DJANGO_HSTS_SECONDS` en su valor por defecto (un año, con subdominios y
      preload). **Es difícil de revertir**: conviene confirmar el dominio definitivo
      antes de que el primer navegador lo reciba.
- [ ] El proxy delante debe mandar `X-Forwarded-Proto`; Django lo lee para saber que
      la conexión original era HTTPS.

Con `DEBUG=false` las cookies de sesión van marcadas `Secure`: **sin TLS, el admin
de Django no funciona**. La aplicación no lo necesita porque usa JWT.

### Base de datos

- [ ] PostgreSQL **16**. Otra versión no es intercambiable, ver §5.
- [ ] `DATABASE_SSL=true` salvo que la base esté en la misma red privada.
- [ ] Respaldos con destino **fuera del host de la base**. El volumen `respaldos`
      del compose vive al lado: sirve para verificar, no como copia de resguardo.

### Comprobación

```bash
python manage.py check --deploy
```

Tiene que salir limpio. Hay un test que lo corre, así que si algo se afloja se nota
en CI.

### Lo que falta resolver antes de un despliegue real

Esto no está construido y hay que decidirlo con el cliente:

- **Dónde se hospeda.** Es el bloqueo declarado del proyecto.
- **Herramienta de monitoreo** que consulte `/api/estado/` y a quién alerta.
- **Política de alertas, guardias técnicas y escalamiento.**
- **Indicadores de disponibilidad** exigidos por contrato o jurisdicción.

## 3. Primer arranque

```bash
# 1. Preparar el entorno
cp .env.example .env     # y completar según §2

# 2. Levantar sin el override de desarrollo: gunicorn y nginx, no runserver
docker compose -f docker-compose.yml up -d

# 3. Esperar a que backend quede sano (aplica migraciones al arrancar)
docker compose -f docker-compose.yml ps

# 4. Crear el superusuario
docker compose -f docker-compose.yml exec backend python manage.py createsuperuser
```

Desde ahí, la configuración inicial del hospital —institución, áreas, usuarios,
formularios, flujos, finanzas— se hace **por pantalla**, y hay un recorrido paso a
paso en
[`entornos/guia-configuracion-desde-cero.md`](entornos/guia-configuracion-desde-cero.md).

## 4. Actualizar una instalación

```bash
# 1. Respaldo AHORA, y verificado. No el de anoche.
docker compose -f docker-compose.yml exec backend python manage.py respaldar

# 2. Traer la versión nueva
git pull
docker compose -f docker-compose.yml build

# 3. Reiniciar. `backend` migra; los demás esperan a que esté sano.
docker compose -f docker-compose.yml up -d

# 4. Comprobar
curl -fsS https://TU-DOMINIO/api/health/          # {"status": "ok"}
# y con sesión de superusuario, GET /api/estado/  → los cuatro procesos al día
```

**Antes de migrar una base usada por personas hace falta respaldo y aprobación
explícita.** Una migración no se revierte sola.

## 5. Respaldos

El servicio `respaldos` corre una vez por día:

```
python manage.py respaldar --conservar 14
```

Lo que hace, y por qué importa cada parte:

- Vuelca la base a `/respaldos/salud-AAAAMMDD-HHMMSS.sql.gz`.
- **Falla si el archivo sale de menos de 1 KB.** Eso es lo que deja `pg_dump` cuando
  falla y nadie mira el código de salida: el respaldo inútil por excelencia.
- **Restaura el volcado en una base aparte y compara los conteos de tabla.** Un
  respaldo que nunca se restauró no es un respaldo. La falla clásica es que el cron
  corrió dos años, los archivos estaban ahí, y el día que hizo falta ninguno servía.
- Rota: conserva los últimos 14.
- **Sólo late si verificó.** Con `--sin-verificar` no registra latido, para que el
  monitor no diga «al día» sobre una carpeta que quizás no tenga un archivo
  restaurable.

### La trampa de la versión

El cliente de Postgres de la imagen está fijado a la mayor del servidor (`PG_MAJOR`).
Con `pg_dump` 17 contra un servidor 16 **el volcado sale bien** —tamaño razonable,
código de salida cero— y no se puede restaurar: incluye parámetros que el 16 no
conoce. Un archivo con nombre de respaldo, que es la peor forma de no tener respaldo.

El comando comprueba las versiones antes de volcar. Si cambiás la versión del
servidor, hay que reconstruir la imagen con el `PG_MAJOR` que corresponda.

### Dónde viven

En el volumen `respaldos`. **Eso no es una copia de resguardo**: está en el mismo
host. Un despliegue real tiene que copiarlos fuera —otro proveedor, otra región— y
eso todavía no está resuelto.

## 6. Recuperación: se perdió la base

Esto es lo que se hace cuando pasó de verdad.

> **Antes de tocar nada:** si la base todavía responde aunque sea parcialmente, sacá
> un volcado del estado actual. Restaurar encima destruye lo que quede, y a veces lo
> que quedó vale más que el respaldo de anoche.

```bash
DC="docker compose -f docker-compose.yml"

# 1. Parar todo lo que escribe. La aplicación Y los cuatro procesos de fondo:
#    si `repartos` o `costos` siguen vivos, escriben sobre la base a medio restaurar.
$DC stop backend frontend tiempos repartos costos respaldos

# 2. Elegir el respaldo. El más nuevo verificado.
$DC run --rm --entrypoint sh respaldos -c "ls -lh /respaldos"

# 3. Restaurar sobre una base VACÍA. Restaurar encima de una con datos deja
#    una mezcla de los dos estados, que es peor que cualquiera de los dos.
$DC exec db psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS salud;"
$DC exec db psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE salud OWNER $POSTGRES_USER;"
$DC run --rm --entrypoint sh respaldos -c \
  "gunzip -c /respaldos/salud-AAAAMMDD-HHMMSS.sql.gz | psql '$DATABASE_URL'"

# 4. Aplicar migraciones pendientes: el respaldo puede ser de una versión anterior.
$DC up -d backend
$DC exec backend python manage.py migrate

# 5. Levantar el resto
$DC up -d

# 6. Comprobar
curl -fsS https://TU-DOMINIO/api/health/
# y con sesión, GET /api/estado/
```

### Qué se perdió

**Todo lo ocurrido entre el respaldo y la caída.** Con el respaldo diario, eso es de
hasta 24 horas de atención: casos, atenciones firmadas, movimientos de stock,
registros financieros.

Si eso es inaceptable para el cliente —y en un hospital suele serlo— hace falta
resolver replicación o *point-in-time recovery* del lado de la base, que **no está
implementado** y es una decisión de infraestructura, no de la aplicación.

### Los adjuntos van aparte

Las subidas clínicas viven en el volumen `media`, **no** en la base. El respaldo de
la base no las incluye. Un plan de recuperación completo tiene que cubrir los dos.

## 7. Qué no se puede deshacer

Conviene tenerlo presente antes de una operación de emergencia:

- **Una migración inversa destructiva** para salir de un incidente. Las decisiones
  financieras ya emitidas y las reservas de cobertura activas exigen reconciliación
  antes de retirar cualquier estructura.
- **Desactivar una pantalla** no libera cupos ni borra deudas. La reversión operativa
  del circuito de cobertura es: detener nuevas confirmaciones e importaciones,
  mantener lectura y recuperación de lo ya comprometido, y resolver los pendientes.
- **Borrar una institución.** No se puede: la auditoría clínica y los flujos la
  protegen. La única baja es la de estado.
- **HSTS**, una vez que el navegador lo recibió.

## Referencias

- [`.env.example`](../.env.example) — todas las variables, con cuáles son obligatorias.
- [`docs/funcionalidades/operacion-monitoreo/`](funcionalidades/operacion-monitoreo/README.md) — qué contesta cada endpoint de salud y por qué.
- [`docs/ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) — qué está validado y qué no.
- [`docs/entornos/`](entornos/README.md) — para levantarlo en tu máquina.
