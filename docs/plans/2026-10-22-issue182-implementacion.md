# #182: implementación y validación de confirmaciones OSTEL

## Reconciliación con los cinco criterios de #182 — 27/10/2026

El usuario pidió analizar el issue completo y terminar los pendientes posibles.
El faltante técnico principal era la validación funcional de los tamaños citados
en el issue: las pruebas anteriores llegaban a 205 filas. Se agregó cobertura
sin cambiar código productivo, límites, permisos, contratos ni reglas de negocio.

| Criterio del issue | Implementación y evidencia |
| --- | --- |
| Confirmación explícita, aislamiento y permisos | Botón de confirmación y acción POST por financiador; `test_permisos_ambito_y_entrada_invalida_no_aplican`, pruebas de lectura/carga de `test_ostel_api` y los recorridos reales. La previsualización del caso grande no incorpora personas. |
| Procedencia y auditoría sin exponer datos protegidos | `Importacion` conserva huella de fuente, autor, financiador y evidencia por fila. Los escenarios grandes conservan las 40 columnas originales; el historial corresponde al lote, autor y financiador. La prueba de repetición comprueba que los textos de auditoría no contienen nombre, documento ni CUIL del archivo. |
| Repetición, rectificaciones y concurrencia | Se verifican reintento del mismo lote y otro lote con los mismos datos, rollback de una tanda y recuperación tras perder la respuesta. Las correcciones con motivo/revisión y las conexiones PostgreSQL concurrentes ya tienen pruebas focales y recorridos reales. No se duplican personas, historial ni eventos de alta/cambio. |
| Ausencias nunca dan de baja | Los dos escenarios grandes incluyen una afiliación fuera del archivo y comparan todos sus campos antes/después, incluida su cobertura. El escenario de 7.486 bajas no crea ni modifica afiliaciones: conserva evidencia para revisión. |
| Partición/límites y fallos parciales | 5.754 altas en 58 tandas y 7.486 altas en 75 tandas, de hasta 100 por confirmación. Se provocan fallo de tanda y pérdida de respuesta. Los límites existentes se describen abajo; su aceptación expresa es una decisión del usuario. |

### Cobertura nueva

`test_issue182_aceptacion.py` usa `TransactionTestCase`, endpoints mediante
APIClient, PostgreSQL 16 y el generador sintético existente. No usa escrituras
masivas que eviten las validaciones del importador:

- **5.754 altas:** una falla de auditoría revierte sólo la tanda en curso y
  conserva las anteriores; después se pierde una respuesta posterior al commit.
  El siguiente intento recupera el lote completo y termina sin duplicar efectos.
- **7.486 altas completamente ficticias:** aplicación hasta el final, persistencia,
  procedencia, repetición segura y conservación íntegra de la persona ausente.
  No representa una orden de aplicar el histórico real de bajas.
- **7.486 filas marcadas como fuente de bajas:** permanecen en revisión como
  evidencia; la confirmación no las convierte en altas ni bajas efectivas.

Los tres escenarios aprobaron localmente, sin omisiones, en 1.152,566 s en
conjunto. Es duración del harness de aceptación, no una medición de rendimiento
productivo. `test_importacion_respuesta.py` agrega un caso pequeño de otro lote
con los mismos datos y privacidad de la auditoría. La regresión focal de
respuesta, importación OSTEL, concurrencia, API y prevalidación aprobó sus
73 pruebas, sin omisiones, en una ejecución separada de 62,541 s.

Comandos ejecutados en la base PostgreSQL local dedicada:

```powershell
python manage.py test apps.financiadores.test_issue182_aceptacion --noinput --verbosity 2
python manage.py test apps.financiadores.test_importacion_respuesta apps.financiadores.test_ostel_importacion apps.financiadores.test_ostel_concurrencia apps.financiadores.test_ostel_api apps.financiadores.test_ostel_prevalidacion --noinput
```

La auditoría de intentos se conserva: reconfirmar un lote terminado registra
otro intento `aplicar_ostel`. Eso no genera otra alta/cambio ni otro historial.
La prueba distingue y verifica ambos conteos; no se elimina trazabilidad para
aparentar idempotencia. Las tandas anteriores ya confirmadas no se revierten si
una posterior falla; la carga completa no se presenta como una transacción única.

### Límites y condición de cierre

OSTEL mantiene **10.000 posiciones por hoja**, archivo de **5 MiB**, contenido
expandido de 25 MiB, 128 entradas ZIP y hasta 100 filas válidas por tanda. La
plantilla genérica conserva su límite predeterminado de 2.000 filas. El issue
mezclaba ese límite con el formato OSTEL; no fue necesario ampliarlo.

Se solicitó al usuario confirmar los límites vigentes, porque el último criterio
exige acordarlos. Esa confirmación no se deduce del silencio ni de pruebas verdes;
su estado actualizado se registra en el PR. No hay un SLA acordado ni ensayo de
carga multiusuario. Los volúmenes grandes se verifican por APIClient/ORM, sin
transporte HTTP ni navegador; los cuatro recorridos pequeños sí usan navegador
y HTTP reales y complementan esta evidencia.

No se declara completada la homologación semántica de #181/#142 por estas pruebas.
Se mantiene el alcance administrativo ya confirmado y los valores no homologados
como evidencia. Cerrar/incorporar el issue requiere la aceptación pertinente y
la incorporación del PR #200; este encargo no autoriza su merge ni despliegue.

## Estado vigente: integración con main del 27/10/2026

La orden del usuario reemplaza el bloqueo anterior: #186 se incorporó a main
en `2cb8464929c585d7f8281d9d0235f96e5776742c`. Se integró `origin/main` mediante
el merge `4c44e2de0c43e7028a9ade00fe7e87dcd26dbc31`, sin rebase ni reescritura
de historia. El PR #200 debe apuntar a main y conservar su estado draft;
mergearlo o desplegarlo sigue fuera de autorización. Las secciones del 22 y
26/10 que siguen son evidencia histórica, no restricciones actuales.

El único conflicto textual fue `ImportacionAdministrativa.jsx`. Se conservan
los componentes de pasos, pestañas, revisión de ficha y descarga anotada de
main, y se integra la confirmación por cambios y el aviso de resultado incierto
de #182. `views.py` y `serializers.py` se fusionaron automáticamente y se
revisaron sus acciones: mantienen los endpoints de subsanación y anotación,
la ficha corregida y el alcance por financiador.

La respuesta por cambios incorpora `columnas`, como la respuesta completa de
main. Se reprodujo su ausencia con una prueba HTTP antes de corregir el
serializer. La prueba reconstruye el lote y lo compara con el estado persistido:
preserva las 40 columnas originales, `columnas_error`, `columnas_bloqueo`,
advertencias, campos advertidos y una fila excluida con su historial. No se
modifican `ostel_importacion.py`, `importaciones.py`, modelos, migraciones ni
reglas de main. Los e2e usan el botón «Importar N filas válidas», las pestañas
«Aplicadas»/«Excluidas» y el diálogo de detalle nuevos.

Validación local del 27/10, con PostgreSQL 16 exclusivo y datos ficticios:

- 15 pruebas focales aprobadas: 12 de respuesta/recuperación/concurrencia y las
  3 de integración de migraciones. El fallo anterior de la hoja 0014 desapareció
  al integrar main, sin editar ni omitir esas pruebas.
- Regresión completa de financiadores: 713 pruebas aprobadas, sin omisiones,
  después de preparar los estáticos con el comando oficial de CI.
- 4 recorridos reales navegador → API → PostgreSQL aprobados en 49,5 s:
  varias tandas con conflicto, pérdida de respuesta posterior al commit,
  exclusión desde otra sesión y compatibilidad con respuesta tradicional.
- 4 recorridos existentes de historial, subsanación y cobertura de los dos
  formatos aprobados con API interceptada, en 8,6 s.
- 7 controles del runner, 32 contratos frontend y 29 controles de descargas y
  credenciales aprobados. Build, auditor de clases (294), OpenAPI estricto y
  `makemigrations --check --dry-run` aprobados.

La primera regresión de 713 pruebas tuvo un error porque este checkout no
tenía el manifiesto de estáticos del admin. Se ejecutó el paso oficial
`python manage.py collectstatic --noinput` y se repitió la suite; no se cambió
código para ocultarlo. La base de prueba y la del navegador son distintas y
pertenecen al mismo contenedor local descartable. No se usan archivos OSTEL
reales, servicios operativos ni credenciales reales.

El CI remoto del head publicado se registra en el PR, separado de estos
resultados locales. La corrección de compatibilidad es `d5984a6`.

## Publicación autorizada el 26/10/2026

El usuario autorizó commits separados, creación de PR dependiente y ejecución/monitoreo de CI remoto. Se verificó que #186 sigue OPEN/draft en `20dd78eb3845f7ded08c9ecd76cd12db7e5ada4b`, con main `45f8e3319761747efb9df2702ae6048262a0262a` ya integrado. No se cambió esa dependencia ni su bloqueo.

La rama se publica como PR draft contra `feat/ostel-prevalidacion-escenarios` (#186), para mostrar únicamente el diff de #182. Los commits separan implementación coordinada (`4d94272`), pruebas/CI (`6fd8443`) y este informe. La descripción del PR registra el resultado de CI remoto para el SHA publicado; las ejecuciones locales del 22/10 se mantienen abajo como evidencia histórica, sin confundirlas con CI.

Pendientes de OSTEL que no resuelve esta entrega: CUILTIT/correspondencia verificable con titular; identificación y fecha efectiva de movimientos; diccionarios TIPODOC/MOTIVO y significado de NROREF/planes/coseguro; alcance de FECVTO; revisión de fechas/casos individuales contradictorios. No se aplican por inferencia bajas, reingresos, vínculos familiares ni derechos. No se cierra #182 por este corte técnico.

Merge, retarget a main, promoción y despliegue siguen fuera de autorización. Un CI aprobado no levanta la espera de #186 ni acredita aceptación humana de reglas de negocio. Los cambios futuros de la base requerirán comprobar el conjunto final antes de incorporarlo.

## Ampliación de CI autorizada el 26/10/2026

El usuario autorizó incorporar al CI los cuatro recorridos reales de importación que hasta entonces sólo se habían ejecutado localmente. Se amplió el job existente `circuito-real` de `.github/workflows/issue43.yml`: reutiliza PostgreSQL 16, Python, Node y Chromium, conserva el nombre del check y su timeout, y ejecuta los cuatro casos después de los recorridos existentes de finanzas. No se creó otro workflow, servicio ni dependencia.

`backend/tests/importacion_real.py` prepara una base nueva `salud_financiadores_test` dentro del PostgreSQL descartable del job; no reutiliza ni elimina bases existentes. Requiere marca explícita `SALUD_IMPORTACION_E2E_AISLADO=1`, desarrollo, URL validada por el guard PostgreSQL existente y directorio propio directamente bajo el temporal del runner. No lee `.env` ni hereda conexiones operativas. Reutiliza el preparador de fixtures y los settings de pruebas de financiadores, sin ampliar sus destinos permitidos.

La configuración Playwright conserva el modo manual. Con la marca de aislamiento, inicia Django en `127.0.0.1:8232` y Vite en `127.0.0.1:5189`, con `reuseExistingServer: false`, y los retira al terminar. No usa los puertos ni la base del escenario de finanzas. El runner genera una clave Django efímera para el proceso, mantiene correo en memoria y RENAPER simulado. Las credenciales de usuarios ficticios quedan sólo en el manifiesto temporal, nunca en logs ni artefactos.

Un paso `always()` elimina el manifiesto aunque falle la preparación o el navegador. La captura de fallos incorpora únicamente las carpetas de resultados de ambos grupos de Playwright; excluye la carpeta de fixtures y su manifiesto. Traces y video permanecen desactivados. El servicio PostgreSQL se retira con el job; el runner no introduce un DROP automático ni operaciones sobre una base operativa.

Validación local de esta ampliación:

- 7 pruebas puras del runner aprobadas: marca/entorno, destino PostgreSQL, sustitución de variables heredadas, rechazo de directorio o base existentes y limpieza limitada/repetible.
- 141 pruebas PostgreSQL existentes de #43 aprobadas.
- 2 recorridos existentes de finanzas aprobados.
- 4 recorridos de importación aprobados con arranque automático de los servidores y PostgreSQL real, en la otra base del mismo contenedor.
- YAML, conexión del paso al workflow y limpieza incondicional comprobados. Los cuatro puertos quedaron sin servidores al finalizar; se ejecutó la limpieza real y se retiró el contenedor propio con sus volúmenes. No se modificaron API, modelos, migraciones ni reglas de negocio.

El resultado remoto de esta ampliación se registra en el PR para su SHA correspondiente; el verde previo de `3cfe8c8` no se atribuye a los commits nuevos. No se levantó el bloqueo de #186/OSTEL.

Reproducción del runner desde backend, con un PostgreSQL local descartable que permita crear la base y variables de aislamiento preparadas:

```powershell
python -m unittest tests.test_importacion_real -v
python tests/importacion_real.py preparar
# Desde frontend, con las mismas variables:
npx playwright test -c playwright.importacion-real.config.js
# Desde backend, ejecutar siempre, incluso ante un fallo:
python tests/importacion_real.py limpiar
```

`SALUD_IMPORTACION_DIRECTORIO` debe ser una carpeta nueva cuyo nombre empiece por `salud-importacion182-`, directamente bajo el directorio temporal. `SALUD_IMPORTACION_MANIFEST`, si se define, debe apuntar a su `manifiesto.json`. `SALUD_TEST_POSTGRES_URL` sólo admite la base local dedicada de financiadores; nunca una URL de producción. El workflow configura esas rutas con `RUNNER_TEMP` y conserva la base `salud_issue43` para el escenario anterior.

## Resultado y alcance

Implementación real en `C:/Users/Juanito/orca/workspaces/SistemaDeSalud/Salud-182-integracion`, rama `juanikitro/Salud-182-integracion`. Sustituye el corte preparatorio anterior; no requiere aplicar un archivo de diferencias ni copiar código manualmente.

Autorización del usuario en el corte del 22/10: probar el flujo completo, validar PostgreSQL, reconciliar #186 y entregar un arreglo cerrado. El usuario descartó seguir trabajando en rendimiento como condición de cierre y delegó la revisión técnica sin ejercicios de modos de fallo. Se mantuvo su restricción expresa: #186 no se mergea hasta recibir las respuestas de OSTEL. Ese corte no incluyó commit, push, edición de GitHub, merge remoto ni deploy; la publicación posterior fue autorizada el 26/10 y se describe arriba.

Base final: PR #186 `20dd78eb3845f7ded08c9ecd76cd12db7e5ada4b`, que ya incluye main `45f8e3319761747efb9df2702ae6048262a0262a`. Se conservó la integración de permisos/cortes de membresía de main y la conservación literal de CODPAR publicada en #186. No se asignaron parentescos ni derechos por ese código.

La reconciliación empezó desde `0f84003` en un checkout Orca propio, sin agentes nuevos. Al cambiar #186 durante el trabajo, se incorporaron sus cinco destinos nuevos/modificados respecto de la integración local. Se descartó únicamente la migración de unión vacía creada por este trabajo en el entorno descartable y se reutilizó la migración canónica de #186: `0014_merge_cobertura_baja_membresia`. No se renombraron migraciones publicadas. El checkout avanzó por fast-forward al PR actualizado preservando los cambios propios; no quedó una operación de merge pendiente.

El worktree compartido `Salud-padron-avance-sin-OSTEL` y los archivos de los demás especialistas se conservaron. Todos los cambios del arreglo están en el checkout aislado indicado arriba.

## Archivos propios

| Archivo | Responsabilidad |
| --- | --- |
| `backend/apps/financiadores/importacion_respuesta.py` | Snapshot de lote, huella, aplicación OSTEL bajo lock y selección de filas cambiadas |
| `backend/apps/financiadores/serializers.py` | Entrada de confirmación y variantes de respuesta; mantiene intacto el serializer tradicional |
| `backend/apps/financiadores/views.py` | Validación de entrada con queryset limitado al financiador, selección optativa de respuesta y OpenAPI real |
| `frontend/src/lib/importacionRespuesta.mjs` | Combina cambios por fila y comprueba identidad/base/contadores, sin mutar el estado anterior |
| `frontend/src/pages/financiadores/ImportacionAdministrativa.jsx` | Usa el contrato optativo y explicita incertidumbre tras un corte de respuesta |
| `backend/apps/financiadores/test_importacion_respuesta.py` | 11 pruebas de API/DB, recuperación, autorización, concurrencia y esquema real |
| `frontend/src/lib/importacionRespuesta.test.mjs` | 5 controles de combinación/compatibilidad/errores |
| `frontend/e2e/importacion-real.spec.js` | 4 recorridos navegador → HTTP → PostgreSQL real |
| `frontend/e2e/fixtures/preparar_importacion_real.py` | Fixtures completamente ficticias, sólo para la DB local dedicada |
| `frontend/playwright.importacion-real.config.js` | Navegador local y arranque de servidores sólo en modo explícitamente aislado |
| `backend/tests/importacion_real.py` | Preparación de la base E2E nueva, entorno del servidor y retiro del manifiesto |
| `backend/tests/test_importacion_real.py` | 7 controles del aislamiento, rechazo de reutilización y limpieza |
| `.github/workflows/issue43.yml` | Ejecuta los cuatro recorridos de importación reutilizando el job real existente |
| `.github/workflows/calidad.yml` | Agrega los controles del helper al paso existente de contratos; no crea otro workflow |
| Este informe | Evidencia, reproducción, límites y estado de integración |

## Comportamiento del contrato

El endpoint existente `confirmar-importacion` sigue devolviendo su cuerpo tradicional si no se solicita otro modo. No se modificó el cliente HTTP general ni el importador v1/v2.

El flujo OSTEL solicita `modo_respuesta: "cambios"` y, si la tiene, `huella_lote`. La primera llamada o una base desactualizada devuelve un lote completo con una nueva huella. Con base coincidente devuelve resumen/metadatos, `base_huella`, nueva huella y `filas_cambiadas`, sin reenviar todas las filas. Cada fila modificada es completa: no se reconstruyen campos retirados mediante una combinación superficial.

La huella vincula id, versión, estado, resumen y filas; no concede permisos ni acredita identidad de personas. Se obtiene el snapshot y se aplica bajo el lock del lote, conservando la transacción por tanda de #186 y su orden de locks. El formato final ocurre fuera de la transacción, usando los objetos locales sin recarga: un error al entregar la respuesta no demuestra rollback. El importador sigue seleccionando solamente filas válidas, hasta 100 por llamada.

La UI comprueba id, versión, huella base, identificadores de fila y coherencia del resumen. Conserva las filas no modificadas, su orden y evidencia. Ante un corte o respuesta inconsistente no reintenta ocultamente: invalida su huella, informa que la tanda pudo haberse guardado y el siguiente intento explícito recupera el lote completo. Ese intento puede aplicar las válidas restantes; no es un GET ni una operación de lectura sin efectos.

No se cambiaron permisos, cobertura, relaciones familiares, fechas, datos de cobranza, modelos ni servicios externos. Ausencias siguen sin producir bajas. Las correcciones continúan pasando por `subsanar-ostel` y conservan su motivo/autor/evidencia.

## Hallazgo de integración corregido

La anotación `extend_schema_view` de la clase prevalecía sobre la anotación añadida al método: el OpenAPI real sólo publicaba `Importacion`, aunque el endpoint podía devolver cambios. Además, drf-spectacular marcaba como obligatorias las huellas declaradas read-only en respuestas tradicionales. El preflight por AST del corte anterior no cubría la interacción con la clase real.

Se reprodujo el problema con una prueba de `SchemaGenerator` sobre las URLs reales: esperaba `ConfirmacionImportacionRespuesta` y obtuvo `Importacion`. La prueba falló antes del arreglo y pasó después. La corrección declara el contrato una sola vez en la anotación de clase, reutiliza el serializer de entrada en runtime y separa el serializer tradicional de las respuestas completas con metadata de sincronización. El esquema distingue las dos variantes por la presencia requerida de `filas` o `filas_cambiadas`; las huellas no son obligatorias en la respuesta tradicional.

## Validación

Entorno: Windows, Python 3.14.6, Node 24.13.0, PostgreSQL 16-alpine descartable. Paquetes Python existentes. Se intentó reutilizar node_modules con lockfile coincidente, pero faltaban dependencias declaradas (`jspdf`/`jspdf-autotable`). Se retiró sólo la junction propia y se ejecutó `npm ci` en el checkout aislado. No cambiaron package.json, lockfile ni versiones declaradas.

| Comprobación | Resultado |
| --- | --- |
| Regresión de financiadores, integración inicial | 676 pruebas aprobadas |
| Regresión tras actualizar #186 a `20dd78e` | 681 pruebas aprobadas, sin omisiones; incluye 3 escenarios de migración y los 2 controles nuevos de CODPAR |
| Controles finales del endpoint tras corregir OpenAPI | 11 aprobados en PostgreSQL; 38,381 s de ejecución de pruebas, sin omisiones |
| Navegador/API/DB tras el ajuste final | 4 aprobados en 1,1 minutos, sin reintentos automáticos ni omisiones |
| Navegador/API/DB previo al ajuste de OpenAPI | 4 recorridos aprobados sobre `20dd78e` |
| Recorridos existentes de formatos/historial/cobertura con API simulada | 6 aprobados |
| Contratos frontend del workflow, incluidos los nuevos | 32 aprobados |
| Descargas y credenciales, comando del workflow | 28 aprobados |
| Build de producción | Aprobado |
| Auditor de clases tras build | 293 clases, ninguna huérfana ni colisión |
| Migraciones | Instalación completa en DB vacía aprobada; `makemigrations --check --dry-run`: sin cambios |
| OpenAPI real estricto | `spectacular --validate --fail-on-warn`: aprobado |

Las 681 pruebas terminaron antes del ajuste final de serializers/esquema. Las pruebas focales y el recorrido real final validan ese ajuste; no se presentan esas ejecuciones como una única corrida de 682 pruebas.

Casos de persistencia comprobados: tanda completa y delta posterior; respuesta perdida; exclusión por otra sesión; fallo técnico tras crear una persona; fallo de auditoría que revierte sólo la tanda actual; fallo de formato después del commit; reintento sin repetir personas ni historial de afiliación; dos conexiones PostgreSQL que confirman con la misma base; usuario anónimo, auditor y financiador ajeno rechazados antes de aplicar.

Los recorridos reales usan lotes de 101 y 205 filas y un caso de 206 filas con una pendiente. Las peticiones llegan al servidor y se comprueba el padrón persistido por una sesión API independiente. Playwright sólo pausa, observa o pierde deliberadamente una respuesta; no fabrica resultados del backend. La compatibilidad completa se prueba solicitando al API real su modo tradicional. No equivale a desplegar una versión antigua completa de backend/frontend.

La primera ejecución de navegador agotó su espera de 15 segundos mientras se confirmaban varias tandas; las respuestas HTTP terminaron después. Se ajustó únicamente la espera de esas aserciones a 60 segundos y se usaron fixtures nuevas. No se alteró el timeout de la aplicación ni se declaró rendimiento productivo. Un error de `route.fetch` imprimió una cabecera con un token del entorno ficticio: se invalidó su firma, después se eliminó ese contenedor, y se sanitizaron los errores del wrapper de pruebas. No se utilizaron credenciales productivas. La configuración desactiva traces y video.

Comandos de proyecto ejecutados, con credenciales efímeras inyectadas fuera del repo:

```powershell
# backend; settings y URL apuntan exclusivamente al PostgreSQL local descartable
python manage.py test apps.financiadores --noinput
python manage.py test apps.financiadores.test_importacion_respuesta --noinput
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file <archivo-temporal> --validate --fail-on-warn

# frontend
npm ci --no-audit --no-fund
npm run build
npm run auditar
node --test src/lib/padronEdicion.test.mjs src/lib/padronNavigation.test.mjs src/lib/importacionRespuesta.test.mjs src/components/financiadores/padronCampos.test.mjs src/components/financiadores/padronTabla.test.mjs scripts/auditar-clases.test.mjs
node --experimental-vm-modules --test src/api/client.test.mjs src/auth/credencialesInstitucionales.test.mjs
node node_modules/@playwright/test/cli.js test --config playwright.importacion-real.config.js
```

Para reproducir el último comando, iniciar Django local en `127.0.0.1:8232` con `config.settings_financiadores_postgres_test`, URL para `salud_financiadores_test` en un contenedor exclusivo, y Vite en `127.0.0.1:5189` con `VITE_PROXY_TARGET=http://127.0.0.1:8232`. Ejecutar desde backend el preparador de fixtures pasando un directorio temporal nuevo, y definir `SALUD_IMPORTACION_MANIFEST` con la ruta de su `manifiesto.json`. El preparador verifica los settings y nombre de DB, crea cuentas .invalid y no imprime sus contraseñas. Retirar el entorno y el manifiesto al terminar. Nunca usar una URL de producción ni heredar un `.env` operativo.

## Cierre y límites

La implementación está en archivos productivos y pruebas normales del repositorio. El grafo local parte del PR vigente y ya contiene main; no hay una integración Git pendiente. La migración canónica se hereda de #186 y no forma parte del diff propio.

En la validación local del 22/10 no se corrió toda la suite de todas las apps del backend ni CI remoto. Se validó todo el módulo afectado más el flujo real y los checks frontend/OpenAPI indicados. Pasar checks locales no acredita aceptación humana, CI ni despliegue. La ejecución remota autorizada el 26/10 se informa en el PR.

No se seguirá trabajando en benchmarks por decisión del usuario. Se conserva el costo de huella/snapshot como característica conocida, sin promesa de SLA ni prueba de capacidad productiva.

Se detuvieron Django y Vite de esta validación y se eliminó el contenedor PostgreSQL propio con su volumen y credenciales efímeras. También se retiraron los manifiestos temporales que contenían contraseñas ficticias. Las dependencias y el build locales del checkout quedan ignorados por Git y disponibles para reproducir verificaciones; no se alteraron dependencias de otros worktrees.

El cierre técnico de este arreglo no responde por sí mismo las preguntas de negocio ni cierra todo #182. La espera de #186 registrada en este corte histórico quedó superada por su merge y la orden del 27/10 descrita al inicio. La incorporación de #200 y el despliegue requieren autorización del usuario y validación del SHA final. Si se revierte esta optimización, volver al modo completo conservando el esquema y las reglas vigentes de main; no regresar a código que ignore registros administrativos.

Skills utilizadas: `orca-cli` para aislar el checkout sin perder avances; `systematic-debugging` para reproducir y corregir la brecha real de esquema; `vercel-react-best-practices` para combinación inmutable con índices; se consultó `playwright` y se reutilizó el runner de pruebas establecido por el repo para verificar UI y HTTP. `brainstorming` se aplicó en la etapa de elección del contrato, ya aprobada; no se reabrieron esas decisiones.
