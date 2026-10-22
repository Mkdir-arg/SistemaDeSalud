# Correo institucional durable #172

Estado: **opción B aprobada expresamente por el dueño e implementada localmente**, con validación PostgreSQL y ensayo de reinicio/worker en laboratorio sintético. No se agregan proveedores ni se acredita entrega real por generar/canjear tokens. Los apartados de propuesta conservan las alternativas y límites que motivaron la decisión; ya no bloquea la elección A/B.

## Problema y frontera de privacidad

Enviar SMTP dentro de la recuperación pública solo cuando existe una cuenta revela una diferencia temporal aunque status y cuerpo sean idénticos. `on_commit` evita correo ante rollback, pero no convierte el envío en asíncrono. Un timeout SMTP limita operaciones de socket, no necesariamente la duración total de DNS/conexión/TLS/envío. Un hilo daemon puede perder correos al reiniciar; tampoco constituye entrega garantizada.

La solicitud pública debe encolar el mismo tipo de trabajo para toda dirección sintácticamente válida, sin buscar usuario ni hablar con SMTP en el request. La resolución de elegibilidad, generación del token y envío ocurren en el consumidor. Mensajes administrativos se dirigen exclusivamente al email actual guardado; la confirmación de cambio se dirige al nuevo email autenticado por el titular. No enviar mensajes a destinatarios desconocidos para simular tiempos.

La recuperación administrativa resuelve primero el objeto dentro del ámbito administrado (404 uniforme fuera de él), antes de comprobar configuración y construir throttles. La ausencia de lookup en el request corresponde a la recuperación **pública**, no a la operación autenticada sobre una identidad ya autorizada. El alta verifica permisos antes de configuración, y configuración antes de crear o encolar.

## Opciones reales

| Alternativa | Resultado y recursos | Pérdidas y operación | Cambios necesarios |
|---|---|---|---|
| **A. Mejor esfuerzo diferido y acotado** | Cola en memoria por proceso con capacidad explícita y consumidor con cantidad fija de hilos; el request solo acepta trabajo. Sin broker ni tabla nueva. Cola llena rechaza uniformemente con 503 antes de aceptar. | Reinicio abrupto puede perder solicitudes aceptadas. Límite de hilos/cola se multiplica por workers/réplicas. Requiere cierre ordenado, timeout SMTP, métricas de cola/error y reenvío visible. No prometer supervivencia ni entrega garantizada. | Adapter y lifecycle explícitos, parámetros de capacidad/concurrencia aprobados, pruebas de cola llena/cierre/reinicio y autorización de consumo de recursos. No iniciar ejecutores al importar módulos. |
| **B. Outbox durable DB + worker propio** | Una tabla pequeña persiste solicitud y estado; worker supervisado consulta con reservas/locks y reintentos acotados. No broker nuevo. Aceptación pública significa solicitud confirmada en DB. | Añade migración, datos de direcciones/pending, índices, retención y worker que operar. Caída después de aceptación SMTP y antes de marcar envío puede duplicar correo: semántica al menos una vez, nunca exactamente una vez por SMTP. Errores/expiración visibles y conciliación necesarias. | Aprobar esquema, permisos/retención y concurrencia; migración compatible; servicio supervisado, salud/alerta/backoff y pruebas crash/replay. El token se genera al consumir, no se persiste en payload de cola. |

**Recomendación mínima:** A si el dueño acepta explícitamente que un correo aceptado puede perderse al reiniciar y que el usuario deba reenviarlo. B si la aceptación debe sobrevivir reinicios. No incorporar un ejecutor ni una tabla hasta la decisión. Ambas opciones necesitan tasas por IP/email/usuario explícitas; los límites compartidos de Django no prometen atomicidad estricta sin medir concurrencia.

## Interfaz implementada para la opción B

`_programar` inserta `CorreoInstitucionalOutbox` dentro de la transacción de alta o cambio; no usa `on_commit` para persistir. Si el INSERT falla, devuelve 503 sanitizado y revierte la mutación. No hay dispatcher de memoria ni envío inline. La recuperación pública encola la dirección válida recibida sin buscar identidad; el worker resuelve elegibilidad y genera el token al consumir. La outbox guarda referencias, dirección cuando corresponde y huella de estado; nunca enlaces ni tokens.

El worker reserva con `select_for_update(skip_locked=True)`, lease y UUID. Un resultado de reserva vieja no pisa una nueva. Recupera reservas vencidas, aplica backoff acotado y distingue enviado, descartado y error terminal. No mantiene locks de DB durante SMTP. Rechazos SMTP 5xx terminan sin retry; fallos temporales se reintentan dentro del máximo y vencimiento configurados. Una cuenta inactiva, destinatario desconocido, autoridad perdida o estado cambiado se descarta sin enviar. Un propósito desconocido también se descarta, sin retry.

Base institucional confiable explícita, limitada al origen sin path (la SPA no configura basename); links en fragmentos de `/restablecer-acceso` y `/confirmar-email`; nunca `Host` ni base del portal del paciente. Logs solo propósito/resultado y referencias internas permitidas, sin direcciones, enlaces, tokens o mensajes de excepción del proveedor. No almacenar payload SMTP completo en errores.

## Decisiones necesarias antes de habilitar

- La opción B y la posibilidad de duplicados están aprobadas. Sigue pendiente quién recibe alertas y cómo se opera su atención; el estado público no enumera destinatarios.
- Vigencias separadas de invitación, recuperación y confirmación. Recomendación enviada: 24 horas / 30 minutos / 30 minutos, todavía sin fijarlas como defaults.
- Tasas y tolerancia de NAT; para A, capacidad y consumidores por proceso; para B, retención/reintentos/lote y servicio supervisado.
- Timeout/proveedor de correo y ensayo de envío/recepción autorizado. No se aprueba gasto con este documento.

Hasta fijar la configuración operacional y probar el proveedor autorizado, mantener el despacho productivo cerrado. No declarar onboarding/recuperación implementados de extremo a extremo ni cerrar AUD-028 por pruebas de buzón sintético.

## Preparación del núcleo y límites de integración

Actualización de decisión: el dueño aprobó persistir los correos pendientes en PostgreSQL y enviarlos mediante un worker, con reintentos y consulta de errores. Aceptación observable: alta y solicitud quedan juntas en la misma transacción; rollback no deja correo; request público no resuelve identidad ni hace SMTP; reinicio conserva trabajo pendiente; workers concurrentes no reservan simultáneamente la misma solicitud vigente; errores reintentables y descartes permanentes se distinguen. SMTP admite duplicados tras un crash entre envío y confirmación, no exactamente una vez. El agente recomienda política explícita del laboratorio y purga manual de payloads terminales; no inventa una retención legal productiva ni un proveedor contratado.

La implementación y sus pruebas focales están preparadas; la ejecución PostgreSQL la coordina el agente principal. Las vigencias y tasas son obligatorias sin defaults válidos; valores sintéticos de tests/laboratorio no son política productiva. `enviado` significa aceptación del backend de correo, no recepción humana. Un fallo posterior al alta confirmada requiere reenvío o conciliación; no revierte la identidad creada.

## Configuración y operación explícitas

- Activar `INSTITUCIONAL_CORREO_MODO=outbox`, `INSTITUCIONAL_URL_BASE`, `INSTITUCIONAL_INVITACION_TIMEOUT`, `INSTITUCIONAL_RECUPERACION_TIMEOUT`, `INSTITUCIONAL_EMAIL_TIMEOUT`, `INSTITUCIONAL_TASA_IP`, `INSTITUCIONAL_TASA_EMAIL`, `INSTITUCIONAL_TASA_USUARIO` y proveedor/from/timeout SMTP existentes. En producción además exigir `INSTITUCIONAL_PROVEEDOR_CONFIRMADO=True`, backend SMTP y host. No se agrega proveedor ni gasto.
- Fijar enteros positivos `INSTITUCIONAL_OUTBOX_MAX_INTENTOS`, `INSTITUCIONAL_OUTBOX_LEASE_SEGUNDOS`, `INSTITUCIONAL_OUTBOX_BACKOFF_INICIAL_SEGUNDOS`, `INSTITUCIONAL_OUTBOX_BACKOFF_MAXIMO_SEGUNDOS`, `INSTITUCIONAL_OUTBOX_ESPERA_SEGUNDOS`. El lease requiere margen respecto de la duración SMTP real; no elimina duplicados. PostgreSQL es obligatorio; SQLite no demuestra reservas concurrentes seguras.
- Supervisar `python manage.py procesar_correo_institucional`; `--una-pasada --max-trabajos 100` ejecuta un lote y sale no cero si hay errores definitivos o plazos/reservas vencidos. `--estado` devuelve solo conteos y antigüedad. Esos errores históricos siguen visibles; no hay confirmación de atención ni canal de alertas implementado.
- `/api/estado` exige latido `correo_institucional` solo en modo outbox, con umbral lease + tres intervalos de espera. Detecta worker ausente o atrasado; un latido verde no prueba entrega ni que la cola esté sana. Observar también el estado agregado del comando.
- Purga manual: `python manage.py procesar_correo_institucional --purgar-antes 2026-10-01T00:00:00+00:00 --max-trabajos 100` limpia payloads terminales anteriores a la fecha, conserva filas/estados y no toca pendientes. La fecha es un ejemplo, no retención productiva aprobada; no borra copias/WAL. No hay purga automática ni Admin que exponga direcciones.

Aceptación SMTP y marcado de DB no son atómicos. Crash después de SMTP, lease insuficiente o envío parcial (mensaje principal aceptado y aviso fallido) pueden duplicar mensajes al reintentar. Es semántica **al menos una vez** con expiración/reintentos acotados, sin promesa de entrega eventual o exactamente una vez. Los logs solo contienen códigos fijos e IDs internos, sin payloads ni excepciones del proveedor.

Rollback operacional: detener worker y desactivar modo; no borrar tablas ni pendientes. Una reversión de migración destruiría la cola, por lo que requiere decisión y respaldo separados. Rehabilitar tras corregir configuración conserva pendientes no vencidos. La validación de proveedor, recepción, supervisión real, alertas y retención sigue pendiente.

Los enlaces de confirmación e invitación/recuperación se vinculan al campo `Usuario.actualizado` existente y lo actualizan al guardar email/contraseña. Esto evita revivir un enlace al cambiar A→B→A; **también invalida enlaces pendientes si otro cambio de perfil actualiza ese campo**. No se agregó una columna de sesión ni se promete revocación individual de todos los enlaces sin cambiar estado.

El helper `bloquear_destino_email` requiere PostgreSQL y transacción activa. Usa advisory lock transaccional con `UPPER` del destino, la misma equivalencia de la comprobación `email__iexact`; confirmación y alta administrativa deben usarlo antes de volver a comprobar disponibilidad. Serializa estos escritores sin modificar el esquema ni convertir direcciones silenciosamente a minúsculas. No protege escrituras que omitan el protocolo, como Django Admin/management commands fuera de este alcance.

## Evidencia local del corte implementado

`manage.py test apps.accounts apps.simulacion --noinput --verbosity 1`: **161 aprobadas, sin skips**, PostgreSQL exclusivo, 56,437 s. Incluye 17 nuevas de outbox: atomicidad/rollback, error de INSERT sanitizado, recuperación pública sin lookup, revalidación de elegibilidad, payload acotado, backoff/tope, SMTP550 permanente sin datos del proveedor en logs, lease vencido/UUID viejo, crash posterior al envío, expiración, configuración incompleta, purga, comando/latido y dos workers con conexiones independientes. El crash entre SMTP y confirmación fue una inyección de fallo en test, no un corte de proveedor real.

Ensayo separado con API/PostgreSQL/worker de Docker reales: **10 controles aprobados**. Se aceptaron dos solicitudes con worker detenido y sin envío inline; ambas conservaron IDs/estado pendiente tras reiniciar API. Al iniciar el worker una llegó al buzón sintético de archivos y la dirección inexistente se descartó, con un intento por trabajo. No hubo tokens ni cuerpos persistidos en la outbox. `output/playwright/aud172-outbox-evidencia.json` registra alcance y límites.

Regresión posterior de navegador contra ese worker: **40 controles de identidad aprobados**, ocho capturas y cero excepciones JS. El lector de enlaces espera al buzón sintético; no invoca un consumidor desde el request. Build, esquema OpenAPI `--fail-on-warn`, `makemigrations --check --dry-run` y diff-check aprobados. Revisión independiente sin P1/P2 nuevos. No hay CI, despliegue, ensayo SMTP/recepción real ni aceptación humana integral.
