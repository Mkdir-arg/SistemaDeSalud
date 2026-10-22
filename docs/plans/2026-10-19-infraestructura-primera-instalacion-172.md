# Infraestructura de la primera instalación (#172)

Estado: **diseño sin gasto, para decisión del dueño**. Fecha: 19/10/2026. Base: rama `juanikitro/auditoria-172-implementacion`, HEAD `b6c0266`.

Origen: decisión 7 del dueño del 19/10 ([plan de implementación](2026-10-15-implementacion-auditoria-172.md), «Decisiones del dueño para los cortes siguientes»): «preparar sin gasto el diseño de una VM con Docker Compose, NGINX con TLS y copia diaria de base y media hacia almacenamiento externo, con retención, costo estimado y runbook de restauración. Nada se contrata sin aprobación».

Cubre AUD-017 (recuperación DB+media fuera del dominio de falla), AUD-024 (cadena TLS confiable y ruta FHIR) y AUD-036 (despliegue operable por 1–4 personas), y toca AUD-020 (presupuesto de conexiones) y AUD-027 (contenedor sin root).

**Este documento no autoriza recursos, gastos, dependencias ni cambios de código.** Nada de lo que sigue está implementado ni ensayado.

Convenciones:

- **[Hecho]**: verificado en el repositorio, con `archivo:línea`.
- **[Recomendación del agente]**: propuesta del agente, no decisión humana.
- **[Supuesto]**: dato no confirmado que cambia el diseño si es falso. Debe medirse o confirmarse.
- **[Pendiente]**: decisión del dueño.

---

## 0. Conflicto que hay que resolver primero

El dueño aceptó dos cosas que no son compatibles tal como están escritas:

- Objetivo de servicio: **pérdida máxima de 15 minutos y recuperación en hasta 1 hora** ante caída completa, comprobando DB y media ([plan](2026-10-15-implementacion-auditoria-172.md), «Primera instalación y objetivos de servicio», línea 79).
- Decisión 7: «**copia diaria** de base y media».

**Una copia diaria no cumple una pérdida máxima de 15 minutos.** Con un volcado cada 24 h, una caída justo antes del siguiente volcado pierde hasta 24 h de atención: casos, firmas, stock y registros financieros. `DESPLIEGUE.md` ya lo dice ([Hecho] `docs/DESPLIEGUE.md:292-298`). Además, el monitor actual da por al día un respaldo de hasta 36 h ([Hecho] `backend/apps/auditoria/latidos.py:71`).

Opciones para el dueño:

1. **Mantener RPO 15 min** y sumar a la copia diaria un mecanismo continuo para la base (archivado de WAL, §2) y sincronizaciones frecuentes de media. Es lo que recomienda este documento.
2. **Bajar el objetivo** a «pérdida máxima 24 h» y quedarse solo con la copia diaria. Es más barato y más simple, pero contradice el objetivo ya aceptado y deja sin cubrir el riesgo que `DESPLIEGUE.md` describe para un hospital.

El resto del documento asume la opción 1 y conserva la copia diaria como segunda vía independiente.

---

## 1. Topología propuesta

### 1.1 Hechos del repositorio que condicionan el diseño

| Hecho | Evidencia |
|---|---|
| Compose de siete servicios: `db` (PostgreSQL 16 alpine), `backend` (gunicorn), `tiempos`, `repartos`, `costos`, `respaldos` y `frontend` (nginx). | `docker-compose.yml:1-188`; `docs/DESPLIEGUE.md:19-30` |
| Solo `frontend` publica un puerto (`${WEB_PORT:-8080}:80`). `db` y `backend` no publican puertos. | `docker-compose.yml:182-183` |
| Volúmenes locales `pgdata`, `media` y `respaldos`. `respaldos` vive en el mismo host. | `docker-compose.yml:8-9,46-48,171-172,190-193`; `docs/DESPLIEGUE.md:247-251` |
| Solo `repartos` tiene `restart: unless-stopped`. Los demás no se levantan solos tras un reinicio de la VM. | `docker-compose.yml:100` |
| NGINX escucha solo en el puerto 80, sin TLS. | `frontend/nginx.conf:1-3` |
| NGINX reemplaza `X-Forwarded-For` por `$remote_addr` y manda `X-Forwarded-Proto $scheme`. | `frontend/nginx.conf:17-21,26-30` |
| Django confía en `X-Forwarded-Proto: https` y redirige a https cuando `DEBUG=false`. `/api/health/` queda exento. | `backend/config/settings.py:87-104` |
| HSTS por defecto: un año, con subdominios y preload. | `backend/config/settings.py:108-110`; `docs/DESPLIEGUE.md:100-102` |
| `NUM_PROXIES` sale de `SALUD_PROXIES_DE_CONFIANZA` y vale 1 por defecto. | `backend/config/settings.py:298-303` |
| K4: el dueño eligió **un único NGINX propio delante de Django**. Si el puerto de Django se publica sin NGINX, `X-Forwarded-For` vuelve a ser falsificable. | [plan](2026-10-15-implementacion-auditoria-172.md), bloque K4 (líneas 527 y 533) |
| La fachada FHIR se monta en `/fhir/`, fuera de `/api/`. | `backend/config/urls.py:164-167`; `backend/apps/fhir/urls.py` |
| **NGINX no proxea `/fhir/`.** No hay `location` para esa ruta, así que `/fhir/metadata` cae en `location /` y devuelve `index.html` con 200. AUD-024 queda confirmado. El compose `vacio` publica el 8000 del backend «porque nginx no proxea /fhir/». | `frontend/nginx.conf:9-11` (único `location` aplicable); `docker-compose.vacio.yml:30-33` |
| `/media/` responde 404 en NGINX. Los archivos clínicos salen solo por Django. | `frontend/nginx.conf:34-43`; `docs/DESPLIEGUE.md:300-315` |
| Nombres de subida `uploads/<institución>/<uuid>.<ext>`: archivos nuevos, sin sobrescritura. | `backend/apps/common.py:484-485` |
| `SALUD_FACTURAS_ADJUNTOS_DIR` vale `BASE_DIR/privado/facturas` por defecto, y el Compose **no lo monta en un volumen**. | `backend/config/settings.py:539-543`; `docker-compose.yml` (sin montaje) |
| `/api/estado/` exige autenticación y devuelve 503 si hay algo atrasado. | `backend/config/urls.py:78-133` (`permission_classes = [IsAuthenticated]` en la línea 95) |
| El cliente `pg_dump` está fijado a la versión mayor del servidor (`PG_MAJOR=16`) desde el repositorio PGDG. | `backend/Dockerfile:15,23-35` |

### 1.2 Diseño [Recomendación del agente]

```text
Internet ──443/80──► [firewall del proveedor: 80, 443; 22 solo desde IPs del dueño]
                         │
                    ┌────┴──────────────────────── VM única ───────────────────────────┐
                    │  frontend (nginx)  :80 → 301 https (y desafío ACME)              │
                    │                    :443 TLS → /api/ /admin/ /static/ /fhir/ → backend:8000
                    │  certbot           renueva en volumen compartido con nginx       │
                    │  backend · tiempos · repartos · costos · respaldos (sin puertos) │
                    │  db (PostgreSQL 16 + pgBackRest; archive_command → bucket)       │
                    │  respaldo-archivos (restic: media + último volcado verificado)   │
                    │  Volúmenes: pgdata, media, respaldos, facturas, certs            │
                    └──────────────────────────────┬───────────────────────────────────┘
                                                   │ HTTPS saliente, cifrado del lado cliente
                       Almacenamiento S3-compatible en OTRO proveedor o región
                       (bucket con versionado y protección de borrado)
```

- **Una VM** con Docker Compose, sin balanceador delante. Un balanceador agregaría un proxy y obligaría a `NUM_PROXIES=2` con `real_ip`, en contra de la decisión K4.
- **Qué se expone:** solo 80 y 443 de `frontend`. SSH (22), si hace falta, solo desde las IPs del dueño o por la consola del proveedor. Los puertos se filtran con el **firewall del proveedor**, no solo con `ufw`: Docker publica puertos escribiendo iptables por su cuenta y puede saltear reglas locales. `db` y `backend` siguen sin `ports:`.
- **TLS en el mismo NGINX** de `frontend`. El bloque del 80 sirve solo `/.well-known/acme-challenge/` y redirige el resto a https; nunca proxea a Django. El bloque del 443 conserva los `location` actuales y agrega `/fhir/`. Los certificados son de una CA ACME (por ejemplo Let's Encrypt): `certbot` en un contenedor aparte, con webroot compartido y renovación periódica, y NGINX recarga su configuración periódicamente para tomar el certificado renovado.
- **Coherencia con K4:**
  - El cliente llega directo a NGINX, así que `$remote_addr` es la IP real del cliente.
  - NGINX **reemplaza** `X-Forwarded-For` ([Hecho] `frontend/nginx.conf:20`), y `SALUD_PROXIES_DE_CONFIANZA=1` queda correcto.
  - En el bloque 443, `$scheme` vale `https`, coincide con `SECURE_PROXY_SSL_HEADER` (`settings.py:90`) y no hay bucle de redirección.
  - La sonda de salud del Compose entra directo al contenedor por http y está exenta (`settings.py:104`; `docker-compose.yml:52-57`).
  - El escenario de bucle de AUD-024 (un terminador TLS externo que habla http con este NGINX) no aparece en esta topología.
  - **Supuesto:** si más adelante se pone un balanceador o una CDN delante, hay que recalcular `NUM_PROXIES` y configurar `real_ip`. La demo en Railway ya está en ese caso (bloque K4).
  - `DESPLIEGUE.md:90-94` dice «2 si además hay un proxy TLS delante». Acá el TLS lo termina el mismo NGINX, así que el valor sigue en 1. Conviene aclarar esa línea cuando se implemente.
- **Ruta FHIR (AUD-024).** Agregar `location ^~ /fhir/ { proxy_pass http://backend:8000; ... }` con las mismas cabeceras que `/api/`, más `location = /fhir { return 301 /fhir/; }`. La alternativa, un host separado (`fhir.<dominio>`), suma certificado, `ALLOWED_HOSTS` y documentación para integradores sin ganar aislamiento real, porque es el mismo proceso. Criterio de aceptación: `GET https://<dominio>/fhir/metadata` responde `application/fhir+json` y no `text/html`. `Patient/abc` sale por la vista FHIR, no por la SPA.
- **HSTS:** usar `DJANGO_HSTS_SECONDS` bajo (por ejemplo 300) en el primer despliegue y subirlo a un año cuando el dominio definitivo esté confirmado ([Hecho] `DESPLIEGUE.md:100-102`). El preload no se revierte rápido.
- **`/admin/` público:** hoy se proxea sin restricción (`nginx.conf:25-31`). Se propone restringirlo por IP en NGINX [Pendiente: decisión del dueño, porque cambia quién puede administrar desde dónde].
- **Volumen `facturas`:** si se habilitan los adjuntos de facturas, hace falta un volumen persistente propio, montado en `backend` fuera de `MEDIA_ROOT` y respaldado como media. Hoy se perderían en cada recreación del contenedor ([Hecho] §1.1).
- **AUD-027:** con la decisión 2 (`chown` acotado y `gosu` a UID 10001), `media`, `respaldos` y `facturas` quedan de 10001. El job de archivos los monta **solo lectura**. Al restaurar en una VM nueva, el entrypoint corrige la propiedad, porque el `chown` es «solo si hace falta».

### 1.3 Supuestos de tamaño para menos de 25 personas simultáneas

| Recurso | Supuesto inicial | Por qué y qué medir |
|---|---|---|
| vCPU | 2–4 | gunicorn con 3 workers síncronos (`backend/Dockerfile:53`), cuatro procesos de fondo y PostgreSQL. La verificación diaria de `respaldar` restaura la base completa: medir que no compita con horario clínico (programarla de madrugada). |
| RAM | 8 GB | Unos 7 procesos Django más PostgreSQL con `shared_buffers` del orden del 25 % de la RAM. Medir RSS real. |
| Disco del sistema | 30–50 GB SSD | Imágenes Docker, logs. |
| Disco de datos (volumen aparte) | 100–200 GB SSD | `pgdata` (supuesto 1–10 GB el primer año) más el doble de la base para la verificación de `respaldar` y su volcado, `pg_wal` con margen ante un archivado caído (§2.6), y `media` (supuesto 10–100 GB; tope 10 MB por archivo, `settings.py:545`). **Volumen real desconocido: lo define la carga del hospital.** |
| Almacenamiento externo | 3–5 × (base + media) | Respaldos completos, WAL de la ventana de retención, versiones de media y volcados diarios. |
| Egreso | Bajo en operación | Tráfico de usuarios: KB por pantalla, salvo adjuntos. La subida de respaldos al bucket es salida de la VM (algunos proveedores la cobran). Una restauración saca del bucket la base completa más la media: es el egreso caro y raro. |

AUD-020, presupuesto de conexiones [Supuesto razonado]:

- 3 workers con `conn_max_age=600` (`settings.py:236`): hasta 3 conexiones persistentes.
- `repartos`: 1 LISTEN más el ORM.
- `tiempos` y `costos`: 1–2.
- `respaldar`: la propia más `pg_dump`/`psql` en serie.
- pgBackRest: 1–2 durante el respaldo.
- Total: menos de 20, con el máximo por defecto de PostgreSQL en 100.

Sin pooler. Medir con `pg_stat_activity` en el ensayo y fijar `statement_timeout` y `idle_in_transaction_session_timeout` por rol después de medir, no antes.

---

## 2. Recuperación con RPO 15 min y RTO 1 h

### 2.1 Qué hay hoy [Hecho]

- `respaldar` vuelca con `pg_dump --snapshot` dentro de una transacción REPEATABLE READ, cuenta todas las tablas en ese mismo snapshot, restaura en una base de nombre único y marcada, compara los conteos y solo late si verificó (`respaldar.py:168-195,265-314,117-118`).
- Rota los últimos N archivos en el mismo volumen (`respaldar.py:317-330`).
- El servicio corre cada 86 400 s (`docker-compose.yml:154-160`).
- **No cubre:** media, copia fuera del host, cifrado, recuperación a un punto en el tiempo ni pérdida menor a un día. Lo admite el propio plan (bloque K6, «Límites»).

### 2.2 Por qué un volcado diario no alcanza

RPO efectivo = intervalo entre copias + duración de la copia + demora de subida. Con 24 h el RPO es de hasta 24 h. Para garantizar 15 minutos hay que copiar algo al menos cada 10–15 minutos y que la copia salga del host en ese plazo.

### 2.3 Caminos comparados

| | A. Archivado continuo de WAL + respaldo base (pgBackRest o WAL-G) hacia S3-compatible | B. Volcados lógicos frecuentes (`respaldar` cada 10 min + subida) | C. Base administrada del proveedor con PITR |
|---|---|---|---|
| RPO | Lo que fije `archive_timeout` más la subida: con 300 s, unos 5–6 min. **Cumple.** | Intervalo más volcado más subida: cumple solo si cada corrida termina en menos de 5 min y ninguna falla. Frágil al crecer la base. | Típicamente de minutos (según el servicio). Cumple. |
| Recuperación a un instante | **Sí** (por ejemplo, justo antes de un borrado erróneo). | Solo a los puntos de volcado. | Sí. |
| RTO | Restaurar el respaldo base más reproducir WAL: con pocos GB, minutos. | `psql` del volcado: crece linealmente con el tamaño y reconstruye índices. | Minutos más el cambio de conexión. |
| Carga sobre producción | Baja: copia física incremental o diferencial. | Un volcado completo cada 10 min, más 144 restauraciones de verificación por día si se verifica cada uno. **Inviable verificarlos todos.** | Ninguna en la VM. |
| Complejidad para 1–4 personas | Media: imagen `db` propia, configuración, monitoreo del archivado y custodia de claves. Riesgo propio: si el archivado falla, `pg_wal` crece hasta llenar el disco (§2.6). | Baja: reutiliza `respaldar`. | Baja en operación, pero **sale de la decisión «una VM»**, suma costo y proveedor y cambia `DATABASE_SSL`, roles y red. |
| Portabilidad | Copia física: misma versión mayor y misma arquitectura. | El volcado lógico se restaura en otras versiones: es una buena segunda vía. | Atada al proveedor. |
| Dependencias nuevas | pgBackRest (paquete del repositorio PGDG, el mismo que ya usa `backend/Dockerfile:28-33`) o WAL-G (binario de GitHub: fijar versión y checksum). | Ninguna. | Servicio pago. |

Descartados:

- **Réplica en streaming a una segunda VM.** Duplica el costo y no protege de errores lógicos: un borrado se replica en el acto.
- **Snapshots del disco del proveedor como única copia.** Quedan dentro del mismo proveedor, no siempre son consistentes con PostgreSQL y su frecuencia típica no da 15 minutos. Sirven como capa extra, no como base.

### 2.4 Recomendación [Recomendación del agente]

**Camino A con pgBackRest, conservando `respaldar` diario como segunda vía, más restic para archivos.**

1. **Base: pgBackRest** dentro del contenedor `db`.
   - Imagen derivada fijada a PostgreSQL 16, con pgBackRest del repositorio PGDG.
   - `archive_mode=on` y `archive_command` hacia `archive-push`, en modo asíncrono.
   - `archive_timeout=300`, para que una base con poco tráfico no retenga WAL durante horas sin llenar un segmento. Este valor es lo que hace cumplir el RPO con poca carga.
   - Respaldo completo semanal, diferencial diario y WAL continuo.
   - Repositorio en un bucket S3-compatible **de otro proveedor o región** que la VM, cifrado del lado del cliente (`repo1-cipher-type=aes-256-cbc`) y compresión.
   - Por qué pgBackRest y no WAL-G: viene empaquetado y firmado por el mismo repositorio que el proyecto ya usa, trae `check`, `verify`, `info`, retención y restauración a un instante integradas, y se configura en un archivo legible.
   - WAL-G es una alternativa válida, sobre todo para conservar la imagen alpine: es un binario único configurado por variables de entorno.
   - Las opciones citadas deben verificarse contra la documentación oficial de la versión que se fije; este documento no consultó fuentes externas.
2. **`respaldar` sigue diario** como vía lógica independiente:
   - protege de un defecto de la herramienta física o de una corrupción que se copie en el WAL;
   - se restaura en otra versión de PostgreSQL;
   - conserva su verificación por snapshot (K6).

   El job de archivos sube al bucket solo el último volcado **verificado**, que es el único que deja latido (`respaldar.py:117-118`).
3. **Media y facturas: restic** cada 15 minutos hacia otro prefijo o bucket.
   - Cifrado siempre, deduplicado y con snapshots versionados.
   - `restic check --read-data-subset` semanal.
   - Lee los volúmenes en solo lectura.
   - Alternativa más simple: `rclone sync --backup-dir`. Es menos íntegra y no cifra por defecto.
4. **Coherencia DB–media.** Los archivos son nuevos con UUID y no se sobrescriben (`common.py:484`). Al restaurar a un instante T, se usa el primer snapshot de media **posterior** a T:
   - lo que sobra son huérfanos, que siguen siendo datos clínicos: se listan para revisión y no se sirven, porque sin fila no hay ruta de descarga;
   - lo que falta son, como mucho, los archivos subidos en los últimos ≤15 min previos a la caída, cuya fila sí se recuperó: se listan para pedir que se vuelvan a cargar.
5. **Supervisión** en `/api/estado/` (trabajo derivado, §6.3):
   - **edad del último WAL archivado**: atrasado si supera 15 min;
   - **edad del último snapshot de media**: atrasado si supera 30 min;
   - **edad del último respaldo base**: atrasado si supera 8 días.

   Así el monitor existente avisa cuando el RPO deja de cumplirse.

### 2.5 Cifrado, retención y protección contra borrado

- **Cifrado** del lado del cliente: pgBackRest y restic. El proveedor del bucket nunca ve datos clínicos en claro. Transporte TLS.
- **Claves:**
  - frase del repositorio pgBackRest;
  - contraseña de restic;
  - credenciales del bucket;
  - `.env` completo.

  **Sin estas claves los respaldos no sirven.** Deben guardarse fuera de la VM, en al menos dos custodias. [Pendiente: custodia.]
- **Retención propuesta** [Recomendación del agente; Pendiente de validación legal]:
  - PITR: 2 respaldos completos semanales con sus WAL, es decir, al menos 14 días de recuperación a un instante.
  - Volcados lógicos diarios: 30 días, más uno mensual durante 12 meses.
  - Media: `restic forget --keep-within 14d --keep-daily 30 --keep-monthly 12`.
  - La retención de **respaldos** no es la retención legal de la **historia clínica**, que vive en la base y se rige por sus plazos (la decisión 4 excluye historia y accesos de la purga).
- **Protección contra borrado:**
  - El bucket tiene versionado.
  - La credencial que vive en la VM **no puede borrar versiones** (solo crear marcas de borrado).
  - Una regla del bucket expira las versiones no actuales a los N días (por ejemplo 30).

  Así, si alguien toma la VM, puede «borrar» pero los datos siguen recuperables durante N días. Si el proveedor ofrece bloqueo de objetos (WORM) en modo *governance*, es la versión más fuerte. Hay que verificar que sea compatible con la expiración de pgBackRest y el `prune` de restic antes de activarlo.
- **Rol de respaldo separado** (límite de K6, AUD-016/027):
  - pgBackRest usa el socket local del superusuario dentro de `db`;
  - `respaldar` sigue con el rol de la aplicación (deuda conocida);
  - las credenciales del bucket están **solo** en `db` y en `respaldo-archivos`, nunca en `backend`.

### 2.6 Riesgos propios del camino A

- **Archivado caído llena el disco.** Si `archive-push` falla (bucket inaccesible, clave rotada), PostgreSQL retiene WAL en `pg_wal` hasta que se llena el volumen y la base se detiene. Mitigaciones:
  - alerta por edad del último WAL archivado (15 min);
  - margen de disco;
  - alerta de disco al 80 %.
- **Cambio de imagen.** Hoy `db` es `postgres:16-alpine` (`docker-compose.yml:3`).
  - Pasar a una imagen Debian cambia de musl a glibc: cambian las colaciones, con riesgo de índices de texto inválidos.
  - También cambia el UID de `postgres` (70 en alpine, 999 en Debian).
  - Como **no hay producción**, conviene decidir la imagen antes de los primeros datos reales.
  - Nunca cambiar la libc con datos en el lugar: se migra con volcado y restauración.
  - Si se quiere conservar alpine, la alternativa es WAL-G.
- **Restauración física con versión mayor distinta:** imposible. La copia lógica diaria cubre ese caso.

---

## 3. Runbook de restauración en una VM nueva

Supuesto: la VM original no existe o no es confiable. Restaurar siempre en un **destino nuevo** y promoverlo después de validar. Si la original todavía responde, primero sacar un volcado de su estado (`DESPLIEGUE.md:257-259`) y no reutilizarla hasta cerrar el incidente.

### 3.1 Requisitos previos, preparados antes del incidente

- Repositorio en la etiqueta o SHA desplegado, y el número de esa versión anotado en cada release.
- `.env` productivo, frases de pgBackRest y restic, y credenciales del bucket **de lectura**, en custodia fuera de la VM.
- Script de aprovisionamiento versionado: Docker, firewall y usuario. Es trabajo derivado (§6).
- DNS con TTL bajo (por ejemplo 300 s) para poder mover el dominio.

### 3.2 Pasos

Cada paso anota la hora para medir el RTO.

| # | Paso | Comprobación |
|---|---|---|
| 0 | **T0**: declarar el incidente. Anotar la hora de la caída observada (Tc) y el instante objetivo de recuperación (por defecto, el último posible; antes de un error lógico, ese instante). | — |
| 1 | Crear la VM del mismo tamaño, con el firewall: 80 y 443 abiertos, 22 restringido. | Acceso por SSH. |
| 2 | Instalar Docker y el plugin Compose; clonar el repositorio en el SHA anotado; copiar `.env` desde la custodia. | `docker compose -f docker-compose.yml config` sin errores. |
| 3 | `build` de las imágenes, o `pull` si se publican en un registro (trabajo derivado). | Imágenes presentes. |
| 4 | Crear los volúmenes vacíos. Levantar **solo** el contenedor `db` en modo restauración: PostgreSQL detenido y volumen `pgdata` vacío. | — |
| 5 | `pgbackrest --stanza=<s> restore`. Para un instante, con `--type=time --target="<UTC>"`. Arrancar PostgreSQL: reproduce WAL hasta el objetivo y promueve. | El log muestra el fin de la recuperación; `pgbackrest info`. |
| 5b | **Vía alternativa** si el paso 5 falla: base vacía y `gunzip -c <último volcado verificado> \| psql` (`DESPLIEGUE.md:271-276`). RPO de hasta 24 h: avisar al dueño. | `psql` sin errores con `ON_ERROR_STOP`. |
| 6 | Media y facturas: `restic restore <snapshot ≥ objetivo> --target` sobre los volúmenes. | Cantidad de archivos y bytes contra `restic stats`. |
| 7 | Levantar `backend`. Migra con `migrar_con_candado` si el respaldo es de una versión anterior (`entrypoint.sh:42-44`). El entrypoint corrige la propiedad (decisión 2). | `/api/health/` 200 dentro de la red. |
| 8 | **Antes de levantar `tiempos`, `repartos`, `costos` y el correo:** revisar los efectos externos (§3.4). Levantar el resto. | `docker compose ps`: todos sanos. |
| 9 | Certificado: emitir uno nuevo por ACME (necesita el DNS ya apuntado) o reponer el respaldado. Mover el DNS. | `https://<dominio>/api/health/` 200 con certificado válido. |
| 10 | Prueba de humo con una cuenta real del dueño: login, abrir una ficha, descargar un adjunto, `GET /api/estado/` 200, `GET /fhir/metadata` en FHIR. | Todo 200. Fin del RTO = **T1**. |
| 11 | Conciliación (puede seguir después de T1): huérfanos y faltantes de media (§2.4), correos pendientes, operaciones económicas del período perdido. Reactivar el archivado y verificar un respaldo base nuevo. | Primer WAL archivado desde la VM nueva y `respaldar` verificado. |

### 3.3 Ensayo y medición

Solo en un sandbox autorizado, con datos sintéticos y presupuesto aprobado. No se ejecuta sin autorización: `V7` de la [auditoría](2026-10-14-auditoria-ingenieria.md).

- **Marcador de RPO** sin tocar el esquema de la aplicación: una base aparte `ensayo` en el mismo clúster, con una tabla `marca(momento timestamptz)` donde un bucle inserta `now()` cada 10 s. El archivado de WAL cubre todo el clúster. Al restaurar, **RPO medido = Tc − max(momento)**. Los latidos de `tiempos` (cada ~2 min) sirven de control grueso.
- **Simular la caída** apagando la VM de golpe, sin `docker compose down`, para no forzar un vaciado ordenado.
- **RTO medido = T1 − T0**, desglosado por paso. Presupuesto orientativo [Supuesto, a medir]: VM y Docker 15 min; build o pull 10 min; restauración de la base (pocos GB) 10 min; media (depende del volumen y del ancho de banda) 10–20 min; DNS, TLS y prueba de humo 10 min. **La media es el tramo con más riesgo para el objetivo de 1 h.** Si el ensayo lo supera, conviene tener imágenes en un registro y una VM preparada, o restaurar la media en paralelo con la base.
- **Criterios de éxito:**
  - RPO medido ≤ 15 min;
  - RTO medido ≤ 60 min;
  - mismos conteos de las cinco tablas críticas (`respaldar.py:40-46`) que una referencia tomada a la hora del objetivo;
  - historias clínicas verificadas con `verificar_historia` sin cadenas rotas;
  - todos los archivos referenciados presentes salvo los ≤15 min listados;
  - `/api/estado/` 200;
  - FHIR responde JSON.
- **Repetir** el ensayo al menos una vez antes de los datos reales, y después de cada cambio de herramienta, imagen o proveedor. Propuesta: un ensayo trimestral [Pendiente].

### 3.4 Lo que la restauración no recupera ni deshace

- **Correos ya enviados** dentro de la ventana perdida (portal, recuperación de contraseña, avisos de turno): el paciente puede tener un correo sobre un turno que ya no existe. Y al revés: un correo marcado como pendiente en el instante restaurado pero ya enviado se reenvía, porque la base vuelve a «pendiente». Revisar la bandeja de salida antes de levantar el worker de correo.
- **Consultas a RENAPER y llamadas FHIR salientes** del motor: el proveedor externo las registró aunque la base ya no.
- **Lo que vieron sistemas externos** (integradores FHIR) entre el instante restaurado y la caída.
- **Sesiones:** los JWT emitidos después del instante restaurado no tienen fila de sesión, así que se invalidan o hay que volver a iniciar sesión.
- **Contadores de límite de login** (en `DatabaseCache`, dentro de la base): vuelven al valor del instante restaurado.
- **Actividad clínica en papel** o fuera del sistema durante la caída: se carga a mano, con su hora real.
- **El certificado TLS** y el DNS: no están en los respaldos y se reemiten.

---

## 4. Operación mínima

### 4.1 Monitoreo y alertas

[Hecho] `/api/estado/` exige un usuario autenticado (`urls.py:95`) y el access JWT dura 60 min (`settings.py:499`): un monitor externo necesitaría una cuenta real y renovarla.

[Recomendación del agente]:

1. **Latido saliente («dead man's switch»).** Un temporizador en la VM (cron o systemd) corre cada 5 minutos un comando que evalúa `latidos.estado()` dentro del contenedor `backend`. Si no hay atrasados, avisa a un servicio externo de latidos. Si el aviso no llega, por proceso atrasado, base caída o VM muerta, el servicio externo alerta. No expone nada y no necesita cuenta.
2. **Chequeo externo** de `https://<dominio>/api/health/` cada 1–5 minutos: detecta caída del NGINX o del TLS, y **vencimiento del certificado** (alerta 14 días antes).
3. **Alertas locales** que entren en el mismo latido (trabajo derivado):
   - disco de datos al 80 %;
   - edad del último WAL archivado;
   - edad del snapshot de media.

Quién recibe: el dueño, que opera los incidentes (plan, «Primera instalación», línea 77). El canal (correo, SMS, mensajería) y el servicio de latidos están [Pendientes]. K4 eligió «sin proveedor» para la alerta de auditoría; esto sí necesita uno externo, porque una VM muerta no puede avisar de sí misma.

### 4.2 Actualizaciones

Según `DESPLIEGUE.md:195-214`, más K7:

1. `respaldar` manual y verificado, **más** `pgbackrest backup --type=incr` para tener un punto de restauración justo antes de la versión nueva.
2. `git checkout <tag>`, luego `docker compose -f docker-compose.yml build` (nunca sin `-f`, porque cargaría el override de desarrollo; `DESPLIEGUE.md:140-141`).
3. `up -d`. `backend` migra con `migrar_con_candado` (advisory lock; un segundo proceso espera hasta 600 s y, si no lo obtiene, falla en vez de arrancar sin esquema; bloque K7). Los workers tienen `EJECUTAR_MIGRACIONES=0` (`docker-compose.yml:89,141,170`). Con `ENTORNO=produccion`, una configuración incompleta impide el arranque (`settings.py:555-565`).
4. Comprobar `/api/health/`, `/api/estado/` y `/fhir/metadata`.
5. **Volver atrás:**
   - Si la migración no tocó datos, se redespliega la imagen anterior.
   - Si los tocó, no se revierte la migración en caliente (`DESPLIEGUE.md:317-323`): se restaura al punto del paso 1 aceptando la pérdida desde entonces, o se corrige hacia adelante.

   Ventana de actualización fuera del horario clínico [Pendiente].

### 4.3 Rotación de secretos

| Secreto | Efecto de rotarlo | Frecuencia propuesta |
|---|---|---|
| `DJANGO_SECRET_KEY` | **Cierra todas las sesiones**: SimpleJWT firma con `SECRET_KEY` por defecto (inferencia: `settings.py:498-506` no fija `SIGNING_KEY`). Hay que revisar qué otras huellas HMAC dependen de ella (límite de login K4) antes de rotar. | Ante sospecha de filtración; programada, en una ventana. |
| `POSTGRES_PASSWORD` | Cambiarla en la base y en `.env` a la vez, y reiniciar todos los servicios. | Anual o ante sospecha. |
| Credenciales del bucket | Crear la nueva, desplegarla, verificar un `archive-push` y luego revocar la vieja. Si se revoca primero, se corta el archivado (§2.6). | Anual. |
| Frase de pgBackRest y contraseña de restic | No se cambian sin rehacer el repositorio (restic admite varias claves). **Perderlas pierde los respaldos.** | Solo ante compromiso. |
| SMTP y RENAPER | Según el proveedor. | Según el contrato. |

`.env` nunca se versiona ni se imprime. Lo guardan dos custodias [Pendiente].

### 4.4 Quién hace qué

| Rol | Responsable | Tareas |
|---|---|---|
| Incidentes y restauración | **Dueño** (declarado) | Recibe alertas, declara el incidente, ejecuta el runbook y decide el instante de recuperación y la conciliación. |
| Custodia de claves | Dueño más una segunda persona [Pendiente] | Guardar `.env` y frases fuera de la VM; comprobar trimestralmente que se pueden leer. |
| Releases | Quien despliega (1–4 personas) | Sigue §4.2. Nunca en paralelo con otra persona: un solo operador por ventana. |
| Ensayos | Dueño con autorización de gasto | §3.3. |
| Revisión de costos | Dueño | Mensual, contra el tope [Pendiente]. |

---

## 5. Costo

No se consultaron precios. **Ninguna cifra de este documento es un precio.** La fila se completa con una cotización del proveedor elegido, con fecha y URL oficial.

| Componente | Unidad de costo habitual | Cantidad supuesta | Precio |
|---|---|---|---|
| VM | Por hora o por mes, según vCPU y RAM | 1 × (2–4 vCPU, 8 GB) | A cotizar |
| Disco de datos SSD | Por GB por mes | 100–200 GB | A cotizar |
| Snapshots de disco del proveedor (opcional) | Por GB almacenado por mes | Según retención | A cotizar |
| IP pública fija | Por mes (algunos proveedores la cobran aparte) | 1 | A cotizar |
| Almacenamiento S3-compatible (otro proveedor o región) | Por GB por mes, más operaciones (PUT/GET por cada mil) | 3–5 × (base + media) | A cotizar |
| Versionado o bloqueo de objetos | Mismo precio por GB (las versiones ocupan espacio) más posible mínimo de días | Incluido arriba, multiplicado por la retención de versiones | A cotizar |
| Egreso de la VM (subida de respaldos y tráfico) | Por GB, con franja gratuita según el proveedor | WAL más media nueva por día, más el tráfico de usuarios | A cotizar |
| Egreso del bucket (restauraciones y ensayos) | Por GB | (base + media) por ensayo | A cotizar |
| Dominio y DNS | Por año y por zona | 1 | A cotizar |
| Certificado TLS (ACME) | Sin cargo de la CA (por ejemplo Let's Encrypt) | — | Confirmar los términos vigentes |
| Servicio de latidos y chequeo externo | Por mes o en franja gratuita | 2 chequeos | A cotizar |
| Ensayos de restauración | VM temporal por horas más egreso | 1 por trimestre [Pendiente] | A cotizar |
| Tiempo humano | Horas por mes de operación, más horas por ensayo | Sin estimar | No monetizado |

---

## 6. Riesgos, supuestos, decisiones pendientes y trabajo derivado

### 6.1 Riesgos

- **Punto único de falla:** la VM. La disponibilidad depende de un host. El objetivo es recuperar en 1 h, no evitar la caída. El plan no aprobó un porcentaje de disponibilidad (línea 80).
- **Archivado de WAL roto en silencio**, que además llena el disco (§2.6), si no se agrega su edad a `/api/estado/`.
- **Pérdida de claves:** respaldos irrecuperables.
- **Credencial del bucket en la VM:** la mitiga el versionado sin permiso de borrar versiones.
- **Media fuera de las 15 min** si restic falla y nadie mira la edad del snapshot.
- **Restaurar encima de una base con datos:** el runbook siempre usa un destino nuevo.
- **Exposición accidental de `backend:8000`** (por ejemplo, copiando `docker-compose.vacio.yml:30-33`): IP falsificable y salto del TLS (bloque K4).
- **HSTS con preload** sobre un dominio provisional.
- **Cambio de libc o UID** de la imagen de la base con datos en el lugar.
- **Correos duplicados o huérfanos** tras una restauración (§3.4).

### 6.2 Supuestos

- Menos de 25 personas simultáneas, una institución (plan, línea 75).
- Base de 1–10 GB y media de 10–100 GB el primer año, **sin medir**.
- No hay balanceador ni CDN delante.
- El proveedor ofrece un firewall de red y un almacenamiento S3-compatible con versionado.
- El ancho de banda de restauración permite bajar la media en el tiempo presupuestado.

### 6.3 Decisiones pendientes del dueño

1. **RPO:** confirmar 15 min con archivado continuo (recomendado) o bajarlo a 24 h con la copia diaria (§0).
2. **Proveedor y región** de la VM, y **otro** proveedor o región para el almacenamiento externo. Residencia de datos de pacientes reales: requiere un responsable competente; este documento no da asesoramiento jurídico.
3. **Presupuesto** mensual tope y presupuesto de ensayos.
4. **Custodia de claves:** quién guarda `.env`, las frases de pgBackRest y restic y las credenciales del bucket, dónde, y quién es la segunda custodia.
5. **Retención** de respaldos (PITR, volcados, mensuales) y días de versiones protegidas, validada contra las obligaciones aplicables.
6. **Dependencias nuevas:** pgBackRest (o WAL-G), restic, certbot e imagen de `db` derivada (alpine o Debian; decidir antes de los datos reales).
7. **Canal de alertas** y servicio de latidos y chequeo externo.
8. **Dominio definitivo,** DNS con TTL bajo y fecha para subir HSTS.
9. **Restricción de `/admin/`** por IP.
10. **Acceso SSH:** IPs permitidas o solo consola del proveedor.
11. **Frecuencia de ensayos** y ventana de actualizaciones.

### 6.4 Trabajo de código y Compose derivado (no implementado)

1. `frontend/nginx.conf`:
   - bloque 443 con TLS y bloque 80 limitado a ACME y redirección;
   - `location ^~ /fhir/` con las mismas cabeceras que `/api/` y `= /fhir` con 301;
   - recarga periódica para tomar el certificado renovado;
   - opcional: lista de IPs para `/admin/`.
2. Compose de producción (archivo nuevo usado con `-f` explícito, o cambios al base):
   - servicio `certbot` y volumen `certs`;
   - puertos 80 y 443;
   - `restart: unless-stopped` en todos los servicios (hoy solo `repartos`, `docker-compose.yml:100`);
   - volumen `facturas` montado en `backend`;
   - servicio `respaldo-archivos` con volúmenes en solo lectura.
3. Imagen `db` derivada: PostgreSQL 16 fijado, más pgBackRest; `postgresql.conf` con `archive_mode`, `archive_command` y `archive_timeout=300`; configuración del repositorio por variables sin secretos en la imagen.
4. Programación de `pgbackrest backup` (completo semanal, diferencial diario), `pgbackrest check` y `verify`, y restic (cada 15 min, `forget/prune` semanal desde una credencial que no viva en la VM, `check` semanal).
5. Subida del último volcado verificado de `respaldar` al bucket. `respaldar` en sí no cambia; la verificación por snapshot de K6 se conserva.
6. `latidos.ESPERADOS` y `/api/estado/`: `wal_archivado` (15 min), `respaldo_base` (8 días), `media_respaldada` (30 min); bajar `respaldar` a unas 26 h si se quiere detectar un día perdido (hoy 36 h, `latidos.py:71`). La alerta de disco puede ir en el mismo latido.
7. Comando de latido saliente para el monitor, sin exponer `/api/estado/` sin autenticación.
8. Script de verificación posterior a la restauración: conteos de las cinco tablas, `verificar_historia`, archivos referenciados ausentes y huérfanos.
9. Script de aprovisionamiento de la VM (Docker, firewall, usuario) y registro de imágenes, si el ensayo muestra que el `build` no entra en el RTO.
10. `docs/DESPLIEGUE.md`: TLS en el NGINX propio con `SALUD_PROXIES_DE_CONFIANZA=1` (aclarar la línea 90-94), FHIR, runbook de §3 y §4.
11. AUD-027 (decisión 2, ya aprobada): `chown` acotado y `gosu`. Coordinar con el montaje en solo lectura del job de archivos y con la restauración.
12. AUD-020: medir conexiones y fijar timeouts por rol en el ensayo; no agregar un pooler sin un cuello de botella medido.

---

## 7. Comprensión y deuda

Este diseño lo preparó el agente sin decisiones nuevas del dueño, salvo la decisión 7 y las anteriores citadas. Las recomendaciones marcadas no son decisiones humanas. Antes de contratar o implementar, el dueño debería poder explicar:

- por qué la copia diaria no cumple 15 min;
- qué hace el archivado de WAL y qué pasa si falla;
- dónde están las claves;
- cómo se mide el RPO en el ensayo;
- qué efectos externos quedan fuera de la recuperación.

Esa comprensión no está demostrada. Se suma a la deuda de comprensión ya registrada en el plan.
