# P01: laboratorio PostgreSQL exclusivo de auditoría #172

Estado al 15/10/2026: **build, arranque PostgreSQL y validación focal ejecutados con autorización del dueño**. No es despliegue de aplicación ni certificación completa del aislamiento.
Responde a los criterios de P01 de [plan de implementación](2026-10-15-implementacion-auditoria-172.md): no cargar `.env` real, PostgreSQL exclusivo, media/caché/puertos propios, proveedores sintéticos y rechazo de destinos ajenos.

## Diseño y recursos

`docker-compose.auditoria172.yml` es independiente. Reutiliza el patrón de aislamiento de `docker-compose.padron130.yml` y de `settings_financiadores_postgres_test.py`, sin usar sus recursos ni su configuración compartida. Combinar con el Compose base heredaría workers, providers y defaults que no corresponden a este ensayo.

- Proyecto: `salud-auditoria172`; servicios `db-auditoria172` y `backend-auditoria172`.
- PostgreSQL 16 sin puerto publicado; base/rol `auditoria172`, test DB `test_auditoria172`. El usuario inicial puede crear DB **solo en este servidor descartable**; no representa el rol productivo mínimo.
- Volúmenes propios de PostgreSQL, media y adjuntos privados; caché portal en su tabla migrada dentro de la DB exclusiva, preservando el comportamiento compartido entre procesos.
- Red Docker `internal: true`, sin ruta externa habitual en runtime. No montar sockets Docker, carpetas del host, bases reales ni conectar redes adicionales. No representa una garantía absoluta de inaccesibilidad del host/gateway: depende también de Docker y del firewall; verificarlo antes de ensayos de destinos host/red interna.
- No se publica ningún puerto (ni DB ni API). El enlace sintético del portal usa `127.0.0.1:8172`, sin servidor escuchando; un ensayo futuro de navegador necesitará publicación loopback revisada.
- Límite inicial por contenedor: DB 512 MiB/1 CPU/128 procesos; backend 1 GiB/2 CPU/256 procesos. No constituye presupuesto de capacidad; sumar consumo de Docker y del build. Disco persistente sin cuota: revisar espacio antes y después; no correr carga o llenado de disco.
- Entry point Python omite espera/migración/seed automáticos de producción. El comando por defecto solo hace `manage.py check`; no inicia workers ni respaldos.
- Dockerfile propio sin `collectstatic` ni importación de settings durante build; contexto allowlist de código/requirements, excluyendo `.env*`, logs y claves. Runtime como UID/GID 10001. No trae cliente `pg_dump`/`psql`: backup/restore pertenece a otro paquete.

Los settings exigen marcadores de laboratorio, host, puerto, base y rol exactos; rechazan query params y URL de tests alternativa. Deshabilitan la lectura dotenv durante la importación del settings base y fuerzan correo en memoria, RENAPER simulado y allowlist de integraciones vacía. Se niegan a cargar si `config.settings` ya fue importado: usar proceso nuevo y `DJANGO_SETTINGS_MODULE` correcto.

La guarda de nombres no puede identificar por sí sola quién administra un servidor ni impedir que un operador cambie redes o comandos. El aislamiento depende también del archivo único Compose, de la red interna y de no montar recursos ajenos. No sirve para certificar TLS productivo, SMTP ni proveedor real. `LocMem` de correo almacena mensajes solamente en cada proceso; no simula entrega durable.

## Variables externas y procedimiento operativo autorizado

Crear **fuera del repositorio** un archivo exclusivo que contenga solamente `AUDITORIA172_DB_PASSWORD` y `AUDITORIA172_DJANGO_SECRET_KEY`, generados para este laboratorio. La clave DB debe usar caracteres aptos para URL (`A-Z`, `a-z`, `0-9`, `_`, `-`); no copiar credenciales reales ni imprimir el archivo. No se entregan claves ni defaults. No usar el `.env` del proyecto.

El dueño autorizó construir y levantar el laboratorio después de la revisión independiente. Se generaron claves exclusivas fuera del repositorio, con ACL restringida al usuario local y sin imprimir valores, en `C:\Users\Juanito\.codex\tmp\auditoria172\laboratorio.env`. No reemplazar ni mostrar ese archivo. PowerShell, desde la raíz del checkout:

```powershell
$labEnv172 = 'C:\Users\Juanito\.codex\tmp\auditoria172\laboratorio.env'
$labCompose172 = @('compose', '--project-name', 'salud-auditoria172', '--env-file', $labEnv172, '-f', 'docker-compose.auditoria172.yml')
# Validar sin imprimir configuración resuelta ni secretos.
docker @labCompose172 config --quiet
# El build necesita red para paquetes/imágenes; internal:true protege runtime,
# no build/pull. Descargas/recursos de este laboratorio autorizados.
docker @labCompose172 build backend-auditoria172
docker @labCompose172 up -d db-auditoria172
# Comprobar identidad antes de ejecutar migraciones o tests.
docker @labCompose172 exec -T db-auditoria172 psql -U auditoria172 -d auditoria172 -tAc 'SELECT current_database(), current_user, version()'
docker @labCompose172 run --rm backend-auditoria172 manage.py check
```

No agregar `-f docker-compose.yml`; no ejecutar `config` sin `--quiet`; no habilitar `.env` implícito; no usar `--network host`, servicios compartidos ni variables de proveedor. Evitar variables `AUDITORIA172_*` heredadas de otro ensayo: Compose prioriza el entorno de la shell sobre el archivo explícito. No cambiar el nombre de proyecto: los settings lo fijan intencionalmente.

Después de revisar identidad/aislamiento y autorizar escritura sintética, el primer ensayo focal propuesto es:

```powershell
docker @labCompose172 run --rm backend-auditoria172 manage.py test config.test_auditoria172_guard --noinput
```

Ese test prueba únicamente guardas y no valida PostgreSQL. Para probar comportamiento de aplicación, elegir módulos focales del paquete implementado y ejecutar el mismo comando `manage.py test <modulo_focal> --noinput`; Django creará/migrará/borrará `test_auditoria172`. **No ejecutar dos corridas concurrentes sobre este mismo laboratorio**: para paralelismo operativo hacen falta laboratorios adicionales con nombres/guardas propios o ejecución serial. No reutilizar `test_salud` ni detener workers ajenos. No usar `--keepdb` hasta definir custodia y limpieza de fixtures.

Un servidor para navegador requerirá migración explícita y fixture sintético revisado. No se incluye `up` de backend ni seed automático como aceptación. Los ensayos backup/restore necesitan destino adicional de verificación y guardas de AUD-016: este laboratorio no habilita el comando `respaldar` actual.

Para detener conservando evidencia/volúmenes: `docker @labCompose172 stop`. No se prescribe `down -v`: borraría evidencia y datos sintéticos persistidos y requiere aprobación específica después de comprobar ownership. No usar backups ni datos personales reales.

## Evidencia y pendientes

Validación segura local ejecutada: `python -B -m unittest config.test_auditoria172_guard -v` desde `backend`: **3 tests OK**; usa solo stdlib, no importa Django, no abre DB ni `.env`. Verifica aceptación del destino único y rechazo de host/base/rol/puerto/esquema/opciones/marcadores/URL alternativos.

Validación operativa ejecutada el 15/10/2026:

- Docker Engine 29.4.2; proyecto no existía antes de crearlo. Había aproximadamente 240 GiB libres en C:; no se ejecutó carga ni llenado de disco.
- `config --quiet`: OK. Build del Dockerfile exclusivo: OK. Imagen resultante `sha256:615256b542687a15f1d118b2561d063d6d63fe278aef7d998e20923f0d4051a3`.
- PostgreSQL **16.15** saludable; consulta de identidad devuelve únicamente DB/rol `auditoria172`. Red con `Internal=true` y etiquetas de proyecto correctas; volumen PostgreSQL con propiedad de proyecto correcta; contenedor DB sin puertos publicados, límite 512 MiB/1 CPU.
- `manage.py check`: sin incidencias. Python **3.12.15**, Django **6.1.2**; el build resolvió las dependencias declaradas sin pin. No confundir esto con stack fijado: AUD-025 sigue pendiente.
- Proceso runtime UID 10001; `.env` ausente en imagen; importación Django con un espía exterior a `dotenv.load_dotenv` verificó cero llamadas al cargador real. Correo en memoria, RENAPER simulado/sin URL e integraciones externas vacías comprobados. Conexión efectiva y nombre exclusivo de DB de test comprobados. Creación y borrado de un archivo temporal sintético en cada directorio media/privado: OK.
- Un primer script de comprobación referenció el nombre de variable de entorno en lugar del atributo de settings `INTEGRACIONES_PERMITIDAS`; falló el script sin escritura persistente y se corrigió. No fue una falla de aplicación.
- `manage.py test config.test_auditoria172_guard apps.registros.tests_api.EstudiosTests apps.portal.tests.AislamientoDeTokensTests --noinput --verbosity 1`: **16 pruebas aprobadas**, sin skips; Django creó/migró y eliminó `test_auditoria172`. Consulta posterior confirma que no queda esa base. No se usó una base compartida.
- Advertencia observada de WhiteNoise por ausencia de `/app/staticfiles/`: el laboratorio no ejecuta collectstatic ni sirve UI. No hubo fallo en estas pruebas; una validación de navegador requerirá resolver la provisión de estáticos según su escenario.
- Revisión independiente de archivos del laboratorio y diff de AUD-002: sin P1/P2 accionables; reejecutó 3 pruebas stdlib y 6 Node, sin operar Docker en paralelo.

Estado al finalizar este hito: DB del laboratorio continúa saludable; backend se ejecuta bajo demanda y sus contenedores `run --rm` ya terminaron. No hay servidor web levantado. No detener servicios de otros proyectos ni borrar estos volúmenes para liberar recursos sin comprobar propiedad y autorización.

Pendiente: aislamiento frente a host/gateway/firewall más allá de la configuración comprobada, pruebas adversariales de dotenv/configuración, E2E y escenarios por paquete. Los fixtures generales se agregan con cada reproducción. Sin suite completa, build frontend, carga, backup/restore, seed real, proveedor real, commit/push/merge/deploy. Las pruebas focales no certifican capacidad ni recuperación.

## Continuación del mismo día

Se reutilizó este laboratorio de forma serial, reconstruyendo la imagen al cambiar fuentes. Tandas adicionales aprobadas: 55 tests de CSV/reset/privacidad; 110 de FHIR; 56 de flujos y publicación; después 9 de concurrencia ampliada. Las tandas tienen casos solapados: no sumarlas como cobertura única. Se comprobaron fallos esperados antes de los fixes de CSV, logs/eventos, alcance FHIR y mutaciones del grafo. La base test se creó/migró/eliminó en cada corrida.

Imagen final de esta continuación: `sha256:0258aa1c250b5254934e00fbcec1568bc677bca57a2b79e2f7f2b08e8675f75a`. El SHA Git sigue siendo el corte base con cambios locales sin commit; la evidencia no se atribuye a un commit integrado ni a CI. Consulta final confirmó que solo permanece `auditoria172` y no `test_auditoria172`.

Se observaron advertencias de estáticos y de paginación sin orden en un listado de flujos, y errores deliberadamente provocados por tests negativos de auditoría/finanzas. Las tandas finalizaron OK; esas advertencias no se corrigen mediante cambios ajenos al paquete ni se presentan como validación de UI o rendimiento. No se abrieron puertos ni se activó proveedor real durante esta continuación. Estado detallado y limitaciones por ID en el plan principal.

## Identidad institucional: primera integración y revisión

Se mantuvo una sola ejecución de pruebas por vez y PostgreSQL exclusivo. Nuevas tandas: 36 pruebas iniciales de identidad/credenciales/JWT y 94 de cuentas/simulación, aprobadas. Después de corregir los tres P2 de revisión (autoridad de plataforma, carrera de email y límites administrativos), corrida conjunta de **142 pruebas aprobadas, sin skips**. Incluye ambos órdenes concurrentes de refresh/reset y confirmaciones de email con variantes de mayúsculas. Las cantidades se solapan; no sumarlas como pruebas únicas.

Un refuerzo posterior incluyó la revisión `Usuario.actualizado` en el token de recuperación para que un cambio de email A→B→A no reactive enlaces previos, y una prueba de alta concurrente con confirmación de email. `manage.py test apps.accounts.test_credenciales_auditoria172 apps.accounts.test_revocacion_password_auditoria172 --noinput --verbosity 1`: **32 aprobadas, sin skips**. La configuración de correo es explícita en fixtures, con buzón locmem y dispatcher inmediato sintético; no demuestra asincronía, privacidad temporal, SMTP ni persistencia del correo.

`manage.py spectacular --fail-on-warn --file /tmp/esquema-auditoria172.yml`: **exit 0**, con rutas nuevas documentadas. Artefacto temporal eliminado con el contenedor; no incorporado al repositorio. Frontend: **12 pruebas Node aprobadas** del cliente real en VM y manejo de fragmentos. No equivale a compilación JSX o navegación real; autorización de instalación/build consultada por separado.

Las rutas nuevas no se habilitan sin políticas/configuración y adapter explícitos; el alta administrativa requiere esa configuración. Al desplegar el cambio de JWT, los tokens anteriores sin huella requerirán nuevo login. No hay cambio de esquema ni cola productiva en este corte; revocación por pertenencia, logout remoto, replay y entrega durable siguen abiertos. La imagen y los archivos locales siguen cambiando durante integración: el identificador de imagen del apartado previo corresponde a aquel corte, no al resultado actual.

## Corte integrado de identidad y descarga directa

Última imagen validada: `sha256:f8faaecb3463baccb7c773599122eb340da81910d1fb380e4cbcd04e6aac07e9`. Incluye el origen institucional sin subruta, el serializer administrativo corregido, el modal global adaptado y AUD-003. Corrida focal conjunta de cuentas, simulación, descarga, subida, estudios, consentimientos y aislamiento del portal: **187 tests aprobados, sin skips**, en 54,391 segundos de ejecución de tests (sin contar build/arranque/migraciones). Comando exacto en el plan principal.

AUD-003 se reprodujo con ocho tests: seis fallos esperados y dos denegaciones aprobadas antes del parche. La corrida preliminar también mostró un error del propio helper por cierre doble de `FileResponse`; se comprobó `closing_iterator_wrapper` de Django instalado y se eliminó el cierre duplicado, sin cambios productivos en DB. La corrida roja limpia y la verde integrada quedan distinguidas.

Comprobaciones finales: OpenAPI `--fail-on-warn` exit 0, doce tests Node aprobados y diff-check sin errores. Consulta de bases confirmó que permanece solamente `auditoria172`, no `test_auditoria172`. DB saludable y backend bajo demanda, sin puertos ni proveedor real. No hay servidor web, compilación JSX o navegación acreditadas. No hay código integrado en Git ni CI ejecutado; SHA base continúa con cambios locales.

## Extensión visual autorizada y corte de autoría/boxes

Se agregó `docker-compose.auditoria172-visual.yml`, combinado exclusivamente con el compose base. Publica la API en **127.0.0.1:8192**; Vite sirve el build en **127.0.0.1:5172**. PostgreSQL permanece sin puerto publicado. La red interna por sí sola no produjo publicación funcional en Docker Desktop; se añadió un bridge visual con masquerade desactivado. Eso no constituye un firewall ni aislamiento garantizado frente al host/gateway. El navegador de prueba aborta solicitudes HTTP externas; no modifica respuestas de la API local.

`config.settings_visual_auditoria172` exige bandera explícita, hereda las guardas de DB y no carga dotenv. Correo en directorio privado del volumen y dispatcher síncrono solo para el fixture, sin SMTP. `preparar_visual_auditoria172` crea únicamente cuentas/institución con namespace reservado, contraseña sintética externa y comprobación de colisiones; no ejecuta la semilla demo ni resetea credenciales existentes. La DB exclusiva `auditoria172` fue migrada y sembrada con datos sintéticos. Los secretos siguen fuera del repo en archivos de acceso restringido; no se incluyen valores en evidencia.

Arranque autorizado (PowerShell, sin definir secretos en la línea de comandos):

```powershell
Remove-Item Env:AUDITORIA172_DB_PASSWORD,Env:AUDITORIA172_DJANGO_SECRET_KEY,Env:AUDITORIA172_VISUAL_PASSWORD -ErrorAction SilentlyContinue
docker compose --project-name salud-auditoria172 --env-file C:/Users/Juanito/.codex/tmp/auditoria172/visual.env -f docker-compose.auditoria172.yml -f docker-compose.auditoria172-visual.yml up -d backend-auditoria172
```

El wrapper Vite temporal externo al repo evita leer `.env` reales, configura proxy a la API local y genera únicamente `frontend/dist` ignorado. Se usó `npm ci --no-audit --no-fund` con lockfile sin cambios y el Chromium de Playwright existente; sin nuevas dependencias productivas. Build final aprobado, auditor CSS aprobado (287 clases), 12 pruebas Node aprobadas. La automatización temporal usa la API Node instalada de Playwright para conservar tokens de correo/contraseñas solo en memoria; no genera trazas con secretos.

Navegación contra servicios reales del laboratorio: 40 controles de identidad y 14 clínicos aprobados, escritorio/móvil, cero excepciones JavaScript. Capturas y JSON sanitizados en `output/playwright/`. La última prueba clínica creó un paciente sintético nuevo y comprobó que después de editar se previsualizara el texto actualizado antes de firmar. Los archivos de captura de intentos fallidos documentan reproducciones, no aceptación del corte final. No se ejecutó el E2E general basado en demo ni se acredita entrega de correo real.

PostgreSQL: 143 pruebas integradas aprobadas y, después del último fix 404, 36 focales aprobadas; tandas solapadas. Comandos exactos en el plan principal. Imagen final de **tests**: `sha256:2417ff34feb34ac26ef8fcf4020e6e5fe18d7f7b65547e690fca932c761dd307`. Backend visual actualmente usa `sha256:976c86d02c84dc1b4e1c290743df9a50d6d0d2f5b9ba5ade03905b57d35b66dc`: incluye autoría/boxes pero antecede al último fix 404 de desaparición concurrente de historia, cubierto por la imagen de tests. No atribuir al navegador ese escenario concurrente. OpenAPI final exit 0. Consulta final confirma solo `auditoria172`, sin `test_auditoria172`.

Al registrar este corte permanecen API/Vite locales y DB saludable. Son servicios del laboratorio; no hay cambios de producción ni proveedor real. No confundir el build y la validación visual con despliegue, ni estos ensayos con carga, backup/restore o aceptación humana. Ningún volumen se eliminó.

## Outbox durable y revisión obligatoria: corte posterior

El dueño aprobó ambos paquetes. La migración expansiva `accounts.0007_correo_institucional_outbox` se aplicó únicamente a la DB sintética del laboratorio; no altera usuarios existentes ni migra datos clínicos. El modo visual ahora usa outbox y dejó de consumir correo dentro del request. Se añadió servicio **correo-auditoria172**, perfil `correo`, imagen compartida con backend, 256 MiB/0,5 CPU, sin puerto ni red visual, `restart: unless-stopped`. Solo escribe en el buzón privado de archivos; sin SMTP ni costo de proveedor.

Arrancar explícitamente el worker tras migración/build y configuración del fixture:

```powershell
docker compose --project-name salud-auditoria172 --env-file C:/Users/Juanito/.codex/tmp/auditoria172/visual.env -f docker-compose.auditoria172.yml -f docker-compose.auditoria172-visual.yml --profile correo up -d correo-auditoria172
docker compose --project-name salud-auditoria172 --env-file C:/Users/Juanito/.codex/tmp/auditoria172/visual.env -f docker-compose.auditoria172.yml -f docker-compose.auditoria172-visual.yml exec -T backend-auditoria172 python manage.py procesar_correo_institucional --estado
```

Antes de nuevas suites backend, detener exclusivamente `correo-auditoria172` del proyecto de laboratorio; no ejecutar suites en paralelo ni tocar workers de otros proyectos. No revertir la migración ni borrar pendientes como forma de rollback: detener/deshabilitar el worker preserva la cola. La purga manual de payloads terminales tiene su contrato en el documento de correo.

Validaciones finales: **108 tests clínicos aprobados**; **161 de cuentas/simulación aprobados**, sin skips y en corridas seriales; 18 controles de navegador con dos pestañas sobre edición/firma; 10 controles de outbox y reinicio real de API; después 40 controles de identidad con el nuevo worker. Build, auditor CSS, 12 Node, OpenAPI y chequeo de migraciones aprobados. No sumar tandas previas solapadas como cobertura única. Sin suite E2E general basada en demo, suite backend global, SMTP/recepción real, carga ni restauración. El primer intento del ensayo de reinicio comenzó antes de que el servidor aceptara conexiones; se añadió espera acotada de readiness en el script de prueba y se repitió con éxito, sin cambiar producto.

Imagen final de API, worker y tests: `sha256:2f610b36919d1b1f742eb982a97e691e8122beecf9bb0a678720f3bd0ce89afc`. Los 108 tests y el ensayo clínico de revisión usaron un corte anterior con el mismo código clínico; la última imagen agrega configuración y refinamientos de outbox/salud. API y worker corren el corte final y la regresión de identidad sí corresponde a ese corte. Consulta final: no existe `test_auditoria172`, DB exclusiva saludable. Estado actual: Vite 127.0.0.1:5172, API 127.0.0.1:8192, worker sin puerto y DB sin publicar. Sin Git integrado ni producción modificada.

## Continuación aceptada: clínica, portal, pedidos y transporte

El dueño aceptó revisión/outbox y autorizó continuar. Se detuvo únicamente `correo-auditoria172` antes de los tests, sin borrar el contenedor ni sus volúmenes. Al usar el compose base sin la extensión visual, Compose avisó que ese worker detenido era un orphan; se conservó deliberadamente y nunca se ejecutó `--remove-orphans`.

Corridas seriales nuevas: rojo043/045 ocho métodos/siete fallos; rojo farmacia+portal17 métodos/13 fallos+dos errores de aserción del fixture; verde300 clínica/agenda/portal. Revisión halló y reprodujo un error adicional de rechazo tras DELETE; se corrigió. Rojo105 farmacia/redirects tuvo17 fallos de redirects. Tanda550 amplia tuvo un único fallo de orden de permisos/configuración; tanda199 encontró una expectativa incorrecta del nuevo test de permisos de objeto. Se precisó el contrato y terminó verde focal48 de identidad/credenciales/barrida. Los detalles, comandos y resultados están en el plan principal; no se suman tandas solapadas ni se presenta550 como aprobada.

Los ensayos HTTP de redirects usan dos servidores `127.0.0.1:0` dentro del contenedor de tests, sin puertos de host ni red externa. Se verificaron GET/POST y FHIR, rechazo de saltos y cierre/sanitización de respuestas. Los destinos de prueba no recibieron requests después del fix; no es prueba del egreso/DNS/TLS/proveedor productivos.

Build frontend/CSS, OpenAPI y chequeo de migraciones aprobados; no hay nueva migración en este bloque. Para la validación visual se usaron scripts privados temporales: fixture bajo guardas de settings/DB/rol/institución que crea una historia nueva y cuatro entradas sintéticas (v1, v2, desconocida y alteración controlada), sin editar registros antiguos. Browser real sin mocks locales: **19 controles aprobados**, dos capturas revisadas visualmente y cero errores JS. La captura móvil se tomó después de desplazar la historia hasta los badges: el primer encuadre mostraba solo cabecera/estadísticas y no se aceptó como evidencia visual de las etiquetas.

Imagen final API/worker/tests focales48: `sha256:007e39fb108b33f1a702a300544cb95d66cfbb5ab6f5b4ced421cbd54126db98`. API y worker comparten ese ID. Los tests550/199 validaron cortes inmediatamente anteriores; no se repitieron completos después del ajuste focal de recuperación administrativa. Fuente Git sigue base `c6f101b` con cambios locales, sin SHA integrado ni CI. Consulta final: solo `auditoria172`, no `test_auditoria172`; outbox sin pendientes, reservas vencidas ni errores. DB, API, Vite y worker siguen levantados con los mismos puertos/recursos. No se agregó proveedor, gasto ni acceso a datos reales.

## Corte de conservación de pedidos y Git

La corrida serial de408 tests PostgreSQL de farmacia/flujos/instituciones/cuentas/simulación/permisos pasó sin skips en151,026s; comando y límites en el plan principal. Worker exclusivo detenido durante la suite, sin otra corrida de DB paralela. SQL de farmacia0003 confirmado no-op, chequeo de migraciones y OpenAPI aprobados. Migración aplicada sólo al laboratorio sintético; no se cerraron ni eliminaron pedidos en masa.

Imagen de tests408: `sha256:282effd4382622e965afae7ccdb91d934754013a859b4c3c50dbed2570ee2857`. API/worker se recrean juntos después de la validación; una representación literal Unicode posterior en el mensaje404 de flujos tiene idéntico valor de ejecución. Rama `juanikitro/auditoria-172-implementacion`, PR borrador174. Capturas/JSON permanecen locales e ignorados; archivos privados de entorno no versionados. Sin proveedor real ni producción. CI se informa aparte en el PR.
