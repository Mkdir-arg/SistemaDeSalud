# #182: implementación y validación de confirmaciones OSTEL

## Publicación autorizada el 26/10/2026

El usuario autorizó commits separados, creación de PR dependiente y ejecución/monitoreo de CI remoto. Se verificó que #186 sigue OPEN/draft en `20dd78eb3845f7ded08c9ecd76cd12db7e5ada4b`, con main `45f8e3319761747efb9df2702ae6048262a0262a` ya integrado. No se cambió esa dependencia ni su bloqueo.

La rama se publica como PR draft contra `feat/ostel-prevalidacion-escenarios` (#186), para mostrar únicamente el diff de #182. Los commits separan implementación coordinada (`4d94272`), pruebas/CI (`6fd8443`) y este informe. La descripción del PR registra el resultado de CI remoto para el SHA publicado; las ejecuciones locales del 22/10 se mantienen abajo como evidencia histórica, sin confundirlas con CI.

Pendientes de OSTEL que no resuelve esta entrega: CUILTIT/correspondencia verificable con titular; identificación y fecha efectiva de movimientos; diccionarios TIPODOC/MOTIVO y significado de NROREF/planes/coseguro; alcance de FECVTO; revisión de fechas/casos individuales contradictorios. No se aplican por inferencia bajas, reingresos, vínculos familiares ni derechos. No se cierra #182 por este corte técnico.

Merge, retarget a main, promoción y despliegue siguen fuera de autorización. Un CI aprobado no levanta la espera de #186 ni acredita aceptación humana de reglas de negocio. Los cambios futuros de la base requerirán comprobar el conjunto final antes de incorporarlo.

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
| `frontend/playwright.importacion-real.config.js` | Configuración de navegador local, sin servicios ni seeds automáticos |
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

El cierre técnico de este arreglo no responde las preguntas de OSTEL ni cierra todo #182. El bloqueo para incorporar/desplegar el conjunto es la espera de #186 definida por el usuario. La publicación y CI sí fueron autorizados el 26/10. Cuando se habilite la incorporación, verificar CI del SHA final y su base vigente. Si se revierte esta optimización, volver al modo completo conservando el esquema y las reglas de habilitación de cobertura de #186; no regresar a código que ignore registros administrativos.

Skills utilizadas: `orca-cli` para aislar el checkout sin perder avances; `systematic-debugging` para reproducir y corregir la brecha real de esquema; `vercel-react-best-practices` para combinación inmutable con índices; se consultó `playwright` y se reutilizó el runner de pruebas establecido por el repo para verificar UI y HTTP. `brainstorming` se aplicó en la etapa de elección del contrato, ya aprobada; no se reabrieron esas decisiones.
