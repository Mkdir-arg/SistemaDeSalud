# Runbook de respaldo continuo y restauración (#172, AUD-017)

Estado: **implementado y opt-in, apagado por defecto**. Ensayado de punta a punta con recursos Docker locales y efímeros el 20/10/2026 (§5.2). No hay infraestructura real contratada: proveedor, región, presupuesto, custodia de claves y canal de alertas siguen pendientes ([diseño](2026-10-19-infraestructura-primera-instalacion-172.md), §6.3).

Origen: decisión del dueño del 19/10, «RPO de 15 min con archivado continuo», y la del 20/10 que elige **WAL-G** (en lugar de pgBackRest, para conservar `postgres:16-alpine` y no cambiar la colación) y **restic** para media y facturas. certbot queda fuera de este corte. Este runbook reemplaza, para la base, los pasos 5 y 5b de pgBackRest del [diseño](2026-10-19-infraestructura-primera-instalacion-172.md#32-pasos); el resto de aquel runbook (VM, DNS, TLS, prueba de humo) sigue valiendo.

Convenciones: **[Hecho]** verificado en el repositorio o en el ensayo; **[Fuente]** documentación oficial citada; **[Recomendación del agente]**; **[Pendiente]** decisión del dueño.

---

## 1. Qué hay

| Pieza | Archivo | Qué hace |
|---|---|---|
| Imagen de la base | `docker/postgres/Dockerfile` | `postgres:16-alpine` + WAL-G v3.0.9 (binario oficial con sha256 fijado) + `gcompat` + restic 0.19.1 copiado de la imagen oficial por digest. |
| Arranque | `docker/postgres/iniciar-db.sh` | Sin `WALG_S3_PREFIX`: igual que la imagen oficial, `archive_mode` apagado. Con `WALG_S3_PREFIX`: exige credenciales, endpoint o región y `WALG_LIBSODIUM_KEY`; si falta algo, **no arranca**. Si está todo, agrega `-c archive_mode=on -c "archive_command=wal-g wal-push %p" -c archive_timeout=300`. |
| Trabajos | `docker/postgres/respaldo-continuo.sh` | `base`: copia completa con `wal-g backup-push` al arrancar si no hay ninguna y luego cuando la última tiene más de `WALG_INTERVALO_BASE` (semanal); retención `wal-g delete retain FULL <n> --use-sentinel-time --confirm`. `archivos`: `restic backup` de `/datos` (media y facturas, solo lectura) cada 15 min y `restic forget --keep-within <retención> --prune` una vez por día. Cada pasada exitosa deja un latido en `auditoria_latido`. |
| Compose | `docker-compose.respaldo.yml` | Cambia la imagen de `db`, pasa `RESPALDO_CONTINUO=1` al backend solo si hay `WALG_S3_PREFIX`, monta un volumen `facturas` en el backend y declara los servicios `respaldo-base` y `respaldo-archivos` en el perfil `respaldo-continuo`. |
| Monitoreo | `backend/apps/auditoria/latidos.py` | Con `RESPALDO_CONTINUO=1`, `/api/estado/` suma `wal_archivado` (de `pg_stat_archiver`), `respaldo_base` (8 días) y `respaldo_archivos` (30 min). Sin la variable no cambia nada. |
| Tablero | `frontend/src/pages/Dashboard.jsx` | Nombres y «qué se rompe» de los tres servicios nuevos. |

El compose base, el override de desarrollo, la demo y el CI no cambian: siguen con `postgres:16-alpine` sin WAL-G.

### 1.1 Por qué `gcompat` [Hecho]

WAL-G v3.0.9 publica solo binarios compilados en Ubuntu contra glibc (`wal-g-pg-20.04|22.04|24.04-amd64|aarch64`). En `postgres:16-alpine` (musl) el binario no arranca (`not found`: falta `/lib64/ld-linux-x86-64.so.2`). Solo enlaza `libc.so.6` y `libm.so.6`; libsodium va adentro. Con `gcompat` 1.1.0-r4, del repositorio de Alpine, corre: el ensayo hizo `wal-push`, `backup-push`, `backup-fetch`, `wal-fetch` con cifrado libsodium, `delete retain` y recuperación a un instante.

Alternativa mínima, si se prefiere no depender de `gcompat`: compilar WAL-G del tag `v3.0.9` (commit `3e493188db28335fb93a45bd680c6ff8fc3028c1`) en una etapa `golang:alpine` con `USE_LIBSODIUM=1` y copiar el binario. Conserva alpine, pero suma una cadena de compilación (Go 1.25, libsodium) que hay que mantener. No se probó. **[Pendiente: gcompat o compilado.]** Cambiar a una imagen Debian no se hizo ni se recomienda con datos (colaciones).

### 1.2 Variables

Ninguna se versiona. Van en el `.env` productivo, que nunca se imprime. Están acá y no en `.env.example` porque ese archivo lo está editando otra línea de trabajo (#171); hay que sumarlas ahí después.

| Variable | Servicio | Uso |
|---|---|---|
| `WALG_S3_PREFIX` | db, respaldo-base, backend (derivada) | `s3://<bucket>/<prefijo>`. Es el interruptor: vacía = todo apagado. |
| `WALG_AWS_ACCESS_KEY_ID`, `WALG_AWS_SECRET_ACCESS_KEY` | db, respaldo-base | Credencial del bucket de la base. |
| `WALG_AWS_REGION` y/o `WALG_AWS_ENDPOINT`, `WALG_AWS_S3_FORCE_PATH_STYLE` | db, respaldo-base | Destino S3-compatible. |
| `WALG_LIBSODIUM_KEY` (+ `WALG_LIBSODIUM_KEY_TRANSFORM`, por defecto `hex`) | db, respaldo-base | Clave de cifrado de 32 bytes (`openssl rand -hex 32`). **Sin ella los respaldos de la base no sirven.** |
| `ARCHIVO_WAL_TIMEOUT` | db | Segundos; por defecto 300. Acota la pérdida con poco tráfico. |
| `WALG_INTERVALO_BASE`, `WALG_CONSERVAR_BASES`, `WALG_REVISAR_CADA` | respaldo-base | 604800 s, 3 completas, 3600 s. Con 3 completas semanales la recuperación a un instante cubre al menos 14 días. |
| `RESTIC_REPOSITORY`, `RESTIC_PASSWORD` | respaldo-archivos | `s3:https://<endpoint>/<bucket>/archivos` y la contraseña del repositorio. **Sin la contraseña los archivos no sirven.** |
| `RESTIC_AWS_ACCESS_KEY_ID`, `RESTIC_AWS_SECRET_ACCESS_KEY`, `RESTIC_AWS_REGION` | respaldo-archivos | Credencial del bucket de archivos (conviene que sea otra). |
| `RESTIC_INTERVALO`, `RESTIC_CONSERVAR`, `RESTIC_INTERVALO_PODA` | respaldo-archivos | 900 s, `14d`, 86400 s. |

`WALG_PREVENT_WAL_OVERWRITE=true` va fijo: si dos bases archivan en el mismo prefijo, `wal-push` falla en lugar de pisar un segmento ajeno.

### 1.3 Activar

```sh
docker compose -f docker-compose.yml -f docker-compose.respaldo.yml build db
docker compose -f docker-compose.yml -f docker-compose.respaldo.yml --profile respaldo-continuo up -d
```

Comprobar:

- Log de `db`: «Archivado continuo de WAL encendido (archive_timeout=300s)».
- `docker compose ... logs respaldo-base`: «Wrote backup with name base_…».
- `GET /api/estado/`: `wal_archivado`, `respaldo_base` y `respaldo_archivos` en «al día».

**Cambio de imagen con datos existentes.** La imagen nueva es la misma `postgres:16-alpine` más binarios: misma libc, mismo UID 70, mismo PGDATA. No hace falta volcado ni restauración. Igual, antes del primer cambio en una base con datos reales, sacar `respaldar` verificado.

---

## 2. Restaurar en una VM nueva

Supuesto: la VM original no existe o no es confiable. Se restaura siempre en volúmenes nuevos. Anotar la hora de cada paso.

**Antes de empezar**, si la original todavía corre: **apagarla o quitarle las credenciales del bucket**. Dos bases archivando en el mismo prefijo mezclan historias; `WALG_PREVENT_WAL_OVERWRITE` frena el choque de nombres, pero no la confusión.

Abreviatura: `DC="docker compose -f docker-compose.yml -f docker-compose.respaldo.yml"`.

| # | Paso | Comando | Comprobación |
|---|---|---|---|
| 0 | **T0.** Declarar el incidente. Anotar la caída observada (Tc) y el objetivo: «lo último posible» o un instante UTC (antes de un error lógico). | — | — |
| 1 | VM, Docker, repositorio en el SHA desplegado y `.env` desde la custodia. | `$DC config -q` | Sin errores. |
| 2 | Construir la imagen de la base y la del backend. | `$DC build db backend` | Imágenes presentes. |
| 3 | **Base: bajar la copia completa** al volumen nuevo (vacío). | `$DC run --rm --no-deps -u postgres --entrypoint sh db -c 'wal-g backup-fetch "$PGDATA" LATEST && echo "restore_command = '"'"'wal-g wal-fetch %f %p'"'"'" >> "$PGDATA/postgresql.auto.conf" && touch "$PGDATA/recovery.signal"'` | «Backup extraction complete». |
| 3b | Solo si el objetivo es **un instante**: elegir la copia completa anterior a ese instante (`wal-g backup-list --detail`), usar su nombre en lugar de `LATEST` y sumar al `postgresql.auto.conf` `recovery_target_time = '<UTC>'` y `recovery_target_action = 'promote'`. | (igual al paso 3) | — |
| 4 | **Archivos, en paralelo con 3–5.** | `$DC run --rm --no-deps -u 0 -v <proyecto>_media:/restaurar/media -v <proyecto>_facturas:/restaurar/facturas --entrypoint sh respaldo-archivos -c 'restic restore latest:/datos --target /restaurar --host salud --tag archivos'` | «Summary: Restored N files». `restic stats latest` para comparar. Como root, restic conserva el dueño 10001. Para un instante, en lugar de `latest`, el primer snapshot **posterior** al objetivo (`restic snapshots`); ver §2.2. |
| 5 | Levantar la base. Reproduce WAL del bucket hasta el último segmento archivado (o hasta el objetivo), elige un timeline nuevo y promueve. | `$DC up -d --no-deps db` | Log: `last completed transaction was at log time …`, `selected new timeline ID`, `archive recovery complete`. Anotar esa hora: es el punto recuperado. |
| 6 | Quitar `restore_command` y `recovery_target_*` del `postgresql.auto.conf` (ya no se usan tras la promoción, pero confunden en la próxima restauración). Paso no ensayado. | `$DC exec -u postgres db sh -c 'sed -i "/^restore_command\|^recovery_target/d" "$PGDATA/postgresql.auto.conf"'` | — |
| 7 | Levantar `backend` (migra con `migrar_con_candado` si hace falta; el entrypoint corrige dueños). | `$DC up -d --no-deps backend` | `/api/health/` 200. |
| 8 | **Antes** de `tiempos`, `repartos`, `costos` y el correo: revisar los efectos externos (§4). Después, el resto con el perfil. | `$DC --profile respaldo-continuo up -d` | `docker compose ps` sano. |
| 9 | Reactivar el respaldo: el archivado arranca solo (el timeline nuevo se sube al mismo prefijo). Forzar una copia base nueva. | `$DC exec respaldo-base wal-g backup-push /var/lib/postgresql/data` | `/api/estado/` 200, `wal_archivado` al día con un segmento `00000002…`. |
| 10 | TLS, DNS y prueba de humo del [diseño, §3.2 pasos 9–10](2026-10-19-infraestructura-primera-instalacion-172.md#32-pasos). **T1.** | — | — |
| 11 | Conciliación: archivos faltantes y huérfanos (§2.2), correos, operaciones económicas del período perdido. | — | — |

Vía alternativa si la física falla: base vacía y el último volcado verificado de `respaldar` (`gunzip -c … | psql`). RPO de hasta 24 h: avisar al dueño.

### 2.1 Restauración de verificación, sin archivar

Para comprobar una copia mientras la base original sigue viva (ensayo, auditoría): **no** usar el servicio `db`, que encendería el archivado contra el mismo prefijo. Usar la imagen con el entrypoint oficial y `archive_mode=off`:

```sh
docker run --rm -u postgres -v verif_pgdata:/var/lib/postgresql/data --env-file <solo WAL-G> \
  --entrypoint sh salud-postgres-respaldo:16-walg-v3.0.9 \
  -c 'wal-g backup-fetch "$PGDATA" LATEST && touch "$PGDATA/recovery.signal"'
docker run -d --name verif -v verif_pgdata:/var/lib/postgresql/data --env-file <solo WAL-G> \
  --entrypoint docker-entrypoint.sh salud-postgres-respaldo:16-walg-v3.0.9 postgres \
  -c archive_mode=off -c "restore_command=wal-g wal-fetch %f %p" \
  -c "recovery_target_time=<UTC>" -c recovery_target_action=promote
```

`<solo WAL-G>` es un archivo con las variables `WALG_*`/`AWS_*` ya con los nombres que lee WAL-G (sin el prefijo `WALG_AWS_`). Se recomienda una credencial **de solo lectura** para esto.

### 2.2 Coherencia entre base y archivos

Los archivos nuevos llevan nombre con UUID y no se sobrescriben ([diseño, §2.4](2026-10-19-infraestructura-primera-instalacion-172.md#24-recomendación-recomendación-del-agente)). Restaurando la base a T, se usa el primer snapshot de restic **posterior** a T:

- lo que sobra son huérfanos (sin fila no hay ruta de descarga): se listan para revisión;
- lo que falta son los archivos subidos después del último snapshot, cuya fila sí volvió: se listan para pedir que se vuelvan a cargar.

No hay script de conciliación todavía (trabajo derivado 8 del diseño).

---

## 3. Medir RPO y RTO en un ensayo

### 3.1 Método

- **Marcador:** una base aparte `ensayo` en el mismo clúster, con `marca(id bigserial, momento timestamptz default clock_timestamp())` y un bucle que inserta cada 5 s y registra el `id` y la hora devueltos. El archivado cubre todo el clúster.
- **Caída:** `docker kill` (SIGKILL) de la base, sin `down`. Tc = hora del `kill`. Borrar el contenedor y los volúmenes de base, media y facturas.
- **RPO de la base** = Tc − `max(momento)` restaurado. **Filas perdidas** = último `id` registrado por el bucle − `max(id)` restaurado.
- **RPO de archivos** = Tc − hora del snapshot restaurado; archivos perdidos = los escritos después.
- **RTO** = T1 − T0, por paso.
- Criterios: RPO ≤ 15 min, RTO ≤ 60 min, archivos y conteos coherentes, `/api/estado/` 200.

**Ojo con `last_archived_time`:** es la hora en que se **subió** el segmento, no la de su contenido. Tras una caída del almacenamiento, los segmentos atrasados se suben juntos con la hora de la subida. El punto recuperado real lo dice el log de la restauración (`last completed transaction was at log time …`).

### 3.2 Resultado del ensayo local del 20/10/2026 [Hecho]

Recursos propios y efímeros (proyecto `respaldo-f172`, red y volúmenes propios), con el `docker-compose.respaldo.yml` real más un archivo de ensayo fuera del repo que agregó MinIO y el marcador. MinIO: la imagen oficial ya no está publicada en Docker Hub ni en Quay; se usó `bitnamilegacy/minio:2025.7.23-debian-12-r5@sha256:6dabb4a2…3fb20`. Credenciales sintéticas generadas al azar, nunca impresas, borradas al terminar. `archive_timeout=300` (el de producción). Para no esperar 15 min, restic corrió cada 120 s.

| Medida | Valor |
|---|---|
| Base (todo el clúster) | 46 MB; en el bucket, 20 MiB tras la retención |
| Copia base inicial | `base_000000010000000000000003`, ~0,3 s |
| Escritura | 26 min desde la copia base (13:51:45 → 14:18:02 UTC); 334 filas en `marca` en total |
| Último segmento archivado antes de la caída | `000000010000000000000009`, contenido hasta 14:14:10.96 |
| **Tc** (SIGKILL) | 14:18:02.002 |
| Restaurado | 287 filas, `max(momento)` 14:14:10.956 |
| **RPO de la base** | **231,0 s (3 min 51 s), 47 filas perdidas** (288–334) |
| Snapshot de archivos restaurado | `b92b394e` de 14:17:29.56: `a.txt` y `b.txt` |
| **RPO de archivos** | **32,4 s**; 1 archivo perdido (`c.txt`, escrito 14:17:51, después del snapshot) |
| **RTO** (T0 → backend sano y conteo verificado) | **18,6 s**: `backup-fetch` 7,4 s; recuperación y promoción 3,4 s; backend sano 7,5 s; archivos (en paralelo) 1,5 s |
| Archivado tras restaurar | Timeline 2 (`00000002.history`, `00000002…0A`), `/api/estado/` al día en los tres servicios |

Además se comprobó:

- **Recuperación a un instante**, con la restauración de verificación de §2.1 (objetivo 14:10:00 UTC): se detuvo antes de la transacción de 14:10:00.03, con 234 filas y `max(momento)` 14:09:55.01.
- **Retención:** con tres completas, `delete retain FULL 2 --use-sentinel-time --confirm` borró la más vieja y el WAL anterior a la más vieja que quedó.
- **Cifrado:** `wal-fetch` con otra clave libsodium falla («corrupted chunk»); con la correcta devuelve el segmento de 16 MiB.
- **Corte del almacenamiento** (MinIO detenido 17 min): `wal-push` **no falla, se queda esperando** (un `backup-list` tardó 1026 s, hasta que volvió). `failed_count` no sube. `/api/estado/` pasó `wal_archivado` a **atrasado a los 929 s** del último archivado, por antigüedad. Al volver MinIO, los segmentos atrasados se subieron solos en ~3,5 min.
- **Pruebas de Django en PostgreSQL** dentro del backend del ensayo (archivado encendido): `apps.auditoria.test_respaldo_continuo_auditoria172`, `test_respaldo_salud_auditoria172` y `tests_monitoreo`, 37 ejecutadas, OK (2 omitidas: la de SQLite y la del script, que no está en la imagen).

**Lo que este RTO no mide:** crear la VM, instalar Docker, construir las imágenes (se usaron ya construidas), bajar datos por internet, DNS y TLS. Con 46 MB todo es instantáneo; con GB, `backup-fetch` y `restic restore` dependen del ancho de banda. El presupuesto del [diseño, §3.3](2026-10-19-infraestructura-primera-instalacion-172.md#33-ensayo-y-medición) sigue siendo la referencia hasta un ensayo en la infraestructura real.

**El RPO de la base depende del momento de la caída:** con `archive_timeout=300` la pérdida va de casi 0 a ~5 min más la subida. 3 min 51 s es una muestra, no el peor caso. El peor caso con el almacenamiento caído es mayor: todo lo no subido desde el último archivado (la alarma salta a los 15 min).

---

## 4. Lo que la restauración no recupera

Igual que el [diseño, §3.4](2026-10-19-infraestructura-primera-instalacion-172.md#34-lo-que-la-restauración-no-recupera-ni-deshace): correos ya enviados en la ventana perdida (y correos pendientes que se reenvían), consultas a RENAPER y FHIR salientes, lo que vieron integradores externos, sesiones JWT emitidas después del punto recuperado, contadores de límite de login, actividad en papel durante la caída, certificado TLS y DNS. Sumar:

- **Archivos subidos después del último snapshot** de restic (hasta 15 min con la cadencia por defecto).
- **Latidos:** vuelven al valor del punto recuperado; `respaldo_base` se corrige solo en la primera pasada (`WALG_REVISAR_CADA`), porque lleva la hora de la copia más nueva del bucket.
- **El último segmento de WAL sin archivar** de la base perdida: en un disco que sobrevive se podría recuperar a mano copiando `pg_wal`; este runbook no lo cubre.

---

## 5. Rotación de claves

| Secreto | Cómo rotar | Riesgo |
|---|---|---|
| Credencial del bucket de WAL-G | Crear la nueva con permiso sobre el prefijo, cambiar `WALG_AWS_*` en `.env`, recrear `db` y `respaldo-base`, verificar un `wal-push` (`pg_switch_wal()` y `pg_stat_archiver`), **después** revocar la vieja. | Revocar primero corta el archivado y el WAL se acumula en el disco (§6). Recrear `db` es un reinicio corto de la base. |
| Credencial del bucket de restic | Igual, con `RESTIC_AWS_*` y `respaldo-archivos`; verificar un snapshot nuevo. | Sin archivos respaldados hasta que se corrija. |
| `WALG_LIBSODIUM_KEY` | No se rota en el lugar: las copias viejas solo se leen con la clave vieja. Para cambiarla: prefijo nuevo con la clave nueva, copia base nueva, y conservar la vieja (y su prefijo) hasta que venza la retención. | **Perderla pierde las copias cifradas con ella.** |
| `RESTIC_PASSWORD` | restic admite varias claves: `restic key add`, probar con la nueva, `restic key remove` la vieja. La clave maestra del repositorio no cambia. | Perder todas las claves pierde el repositorio. |
| `POSTGRES_PASSWORD` | Ver [diseño, §4.3](2026-10-19-infraestructura-primera-instalacion-172.md#43-rotación-de-secretos); los trabajos de respaldo la usan para el latido y la copia base. | — |

Las cuatro primeras viven **fuera de la VM**, en dos custodias. **[Pendiente: custodia.]**

---

## 6. Si el archivado falla

Qué pasa: PostgreSQL reintenta cada segmento y no lo borra de `pg_wal` hasta que `archive_command` termina bien. Si el almacenamiento no responde, **`pg_wal` crece hasta llenar el disco de la base y la base se detiene**. Con almacenamiento inaccesible, WAL-G no devuelve error: se queda reintentando (ensayo, §3.2), así que la señal útil es la antigüedad.

Cómo se ve:

- `/api/estado/` → `wal_archivado` atrasado: «El último segmento archivado (…) es viejo» (más de `archive_timeout` + 10 min), «El último intento de archivar falló» (WAL-G devolvió error, por ejemplo credencial rechazada o bucket inexistente) o «PostgreSQL arrancó sin archive_mode».
- `docker compose logs db`: `archive command failed with exit code …`.
- `SELECT * FROM pg_stat_archiver;` y `ls $PGDATA/pg_wal/archive_status/*.ready | wc -l` (segmentos esperando).

Qué hacer:

1. Mirar el log de `db`: credencial, bucket, red o DNS del endpoint.
2. Medir el disco: `df -h` del volumen `pgdata` y `du -sh $PGDATA/pg_wal`. Cada segmento pesa 16 MiB.
3. Corregir la causa. Al volver, PostgreSQL sube los atrasados solo; confirmar que `.ready` baja a 0 y que `wal_archivado` vuelve a «al día».
4. **Si el disco está por llenarse y la causa no se corrige a tiempo**, la decisión es del dueño: (a) ampliar el disco; (b) apagar el archivado (quitar `WALG_S3_PREFIX` y recrear `db`), aceptando que el RPO pasa a ser el de `respaldar` diario hasta reactivarlo y sacar una copia base nueva. **Nunca borrar archivos de `pg_wal` a mano.**
5. Después de cualquier hueco en el archivado: copia base nueva (`wal-g backup-push`), porque la recuperación a un instante no cruza el hueco.

**Alerta de disco:** no está implementada (no hay canal de alertas). [Pendiente, diseño §4.1.]

---

## 7. Aplicabilidad a Railway

La demo corre hoy en Railway. **Este corte no toca Railway** y nada de lo anterior está probado ahí. Lo que dice la documentación oficial, consultada el 20/10/2026:

- [Fuente: [Point-in-Time Recovery](https://docs.railway.com/volumes/point-in-time-recovery)] Railway ofrece PITR propio para PostgreSQL: su imagen archiva cada segmento de WAL con **pgBackRest** a un *Railway Bucket*, con `archive_timeout=60`, completa semanal y diferencial diaria, y conserva las últimas 4 completas (~4 semanas). El archivado es asíncrono y, ante un corte sostenido del bucket, al pasar una cola de 5 GiB **descarta WAL** para que la base siga: la ventana de recuperación queda con un hueco. La restauración crea un servicio PostgreSQL nuevo al lado del original.
- [Fuente: [Backups](https://docs.railway.com/reference/backups)] Los volúmenes tienen copias diarias (6 días), semanales (27) y mensuales (89), incrementales; «borrar un volumen borra todas sus copias» y solo se restauran en el mismo proyecto y entorno.
- [Fuente: [Volumes](https://docs.railway.com/reference/volumes)] Las imágenes que corren como un UID no root pueden tener problemas de permisos en un volumen montado.
- [Fuente: [PostgreSQL](https://docs.railway.com/guides/postgresql)] Cambiar la imagen, el comando de inicio o las variables de la plantilla hace que la base pase a ser responsabilidad del usuario.

Qué habría que verificar antes de decidir para Railway (nada de esto está comprobado):

1. **¿PITR nativo o esta imagen?** El PITR nativo cumple el RPO (60 s) pero guarda en un bucket **del mismo proveedor**: no saca la copia del dominio de falla (AUD-017 pide «fuera del dominio de falla»). Esta imagen sí puede apuntar a otro proveedor, pero usarla cambia la plantilla y Railway deja de administrar la base.
2. **Un servicio por volumen:** el job `respaldo-base` lee PGDATA en solo lectura desde otro contenedor. Si Railway no permite montar el mismo volumen en dos servicios, habría que correr `backup-push` dentro del contenedor de la base o en modo remoto (`wal-g backup-push` sin PGDATA, que requiere permiso de replicación y una regla en `pg_hba.conf`).
3. **Media en Railway:** depende de #171 (adjuntos en bucket). Si los archivos pasan a un bucket, restic sobre un volumen deja de aplicar; el respaldo pasa a ser versionado o replicación del bucket a otro proveedor.
4. **Política de datos descartados:** la de Railway prioriza que la base siga y acepta huecos; la de esta imagen detiene la base cuando se llena el disco. Es una elección de riesgo distinta. [Pendiente.]
5. Costo de buckets, egress y copias, y dónde quedan las claves.

---

## 8. Riesgos, decisiones pendientes y deuda

Riesgos:

- **`gcompat` no es glibc completa.** Funcionó en todo lo ensayado, pero un cambio de versión de WAL-G o de Alpine puede romperlo. Por eso la versión de WAL-G está fijada y el build corre `wal-g --version`. La etiqueta `postgres:16-alpine` sigue flotante, igual que en el compose base.
- **El latido usa SQL directo** sobre `auditoria_latido`. Lo cuida `ContratoDelScriptTests`, que en CI corre porque el script está en el checkout (dentro de la imagen del backend se omite).
- **Una base sin ninguna escritura** no archivaría y daría falso atrasado; hoy `tiempos` escribe un latido cada 2 min.
- **Credenciales en variables de entorno:** visibles con `docker inspect` para quien controle Docker en la VM. La credencial de la VM debería poder escribir pero no borrar versiones (diseño, §2.5): eso choca con `delete retain` y `forget --prune`. [Pendiente: dónde corre la retención.]
- **El volumen `facturas`** se agrega solo con este archivo. Si #171 mueve las facturas a un bucket, hay que revisar este montaje.
- **Restauración con la base vieja viva:** si alguien levanta `db` restaurada con el mismo prefijo mientras la original archiva, se mezclan historias. El runbook lo advierte; no hay candado técnico más allá de `WALG_PREVENT_WAL_OVERWRITE`.

Decisiones pendientes del dueño:

1. `gcompat` con el binario oficial (lo implementado) o WAL-G compilado del tag.
2. Base que no arranca con `WALG_S3_PREFIX` incompleto (lo implementado, recomendación del agente) o que arranque sin archivar.
3. Ante archivado caído con el disco lleno: ¿la base se detiene (comportamiento de PostgreSQL) o se descarta WAL como hace Railway?
4. Retención: 3 completas semanales (≥14 días de PITR) y `14d` de archivos son los valores sugeridos del diseño, sin validación legal.
5. Proveedor y región del bucket, custodia de claves, canal de alertas y alerta de disco.
6. Para Railway, los puntos de §7.

Comprensión: este runbook y las decisiones de implementación los preparó el agente. Antes de activar el respaldo con datos reales, el dueño debería poder explicar qué hace `archive_timeout`, por qué un archivado caído llena el disco, dónde están las dos claves de cifrado y cómo se mide el RPO. Esa comprensión no está demostrada.
