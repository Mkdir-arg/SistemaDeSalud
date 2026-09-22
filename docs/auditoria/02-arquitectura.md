# Auditoría de arquitectura

## Resumen ejecutivo

El sistema es un monolito Django/DRF con una SPA React que modela la atención como casos que recorren versiones de flujos. Esa elección sigue siendo razonable para el estado actual: evita coordinación distribuida y concentra las transacciones clínicas en Postgres.

El coste de cambio se concentra en el motor de casos y en el contrato de los nodos: hoy un nuevo tipo o una nueva configuración cruza el modelo `Nodo`, JSON persistido, validación, motor, editor y, en algunos casos, la pantalla de ejecución. También hay acoplamientos directos desde Agenda y Red hacia detalles internos del motor. Con la hipótesis de crecimiento confirmada para esta auditoría —nuevos tipos, más integraciones y red interinstitucional— estos dos puntos son P1.

La operación periódica está protegida por latidos y un endpoint de estado, pero Compose ejecuta tres tareas críticas en una única secuencia que absorbe fallos. Como se asume Compose sin monitor externo verificable, una degradación puede ser detectada por la aplicación pero no necesariamente atendida. Las integraciones salientes son síncronas dentro del avance transaccional; no son bloqueantes hoy, por lo que quedan P2, pero deben cambiar antes de que una integración de escritura sea crítica.

## Alcance y limitaciones

- Inspección estática del checkout actual, incluyendo entrypoints, API, modelos, motores, frontend, tareas, FHIR, Compose y pruebas. La documentación existente en `docs/auditoria/` se usó sólo como contexto y sus afirmaciones se contrastaron con código.
- No se ejecutaron migraciones, pruebas, Docker ni tráfico real: no se infiere rendimiento, volumen ni salud del despliegue desde la lectura de código.
- El checkout tenía cambios no relacionados en `backend/entrypoint.sh`, `docker-compose.yml`, `.gitattributes` y archivos locales; no se modificaron ni se atribuyen a esta auditoría.
- Supuestos proporcionados: habrá nuevos tipos de nodo, más integraciones y red interinstitucional; la operación se asume basada en Compose y no hay integración externa bloqueante conocida hoy.

## Mapa actual del sistema

```text
React/Vite SPA
  └─ cliente HTTP + JWT + React Query ──> Django/DRF (/api)
                                       ├─ apps de dominio y modelos Django
                                       ├─ Postgres en Compose (SQLite sólo sin DATABASE_URL)
                                       ├─ FHIR de lectura (/fhir)
                                       └─ media clínica en volumen compartido

Compose
  ├─ backend: migra y sirve la API
  ├─ tiempos: casos vencidos + recordatorios + alertas de saturación
  ├─ respaldos: backup y restauración de verificación
  └─ frontend: Vite en desarrollo / nginx en imagen base

Nodos de flujo ──> motor de casos ──> casos, filas, cama, historia,
                                      notificaciones e integración HTTP
```

El entrypoint `backend/entrypoint.sh` espera la base, aplica migraciones sólo en `backend` y siembra según variables. `cauce/urls.py` expone la API REST central, la salud, el estado de tareas, archivos y la fachada FHIR. `cauce/api.py` registra los ViewSets de todas las apps en un router único.

## Componentes y responsabilidades

| Componente | Responsabilidad observada | Dependencias relevantes |
| --- | --- | --- |
| `accounts`, `instituciones` | identidad, membresías, capacidades y estructura institucional | usados como scope y autorización por otras apps |
| `flujos`, `formularios` | diseño/versionado del grafo y sus campos | `Nodo.config` y `Conexion.condicion` son JSON |
| `casos` | ejecución del grafo, filas, camas, historia, subprocesos, eventos y notificaciones | importa Formularios, Flujos, Instituciones y Registros |
| `agenda`, `farmacia`, `red` | turnos, stock y traslados | Agenda y Red invocan directamente al motor de Casos |
| `registros`, `auditoria` | historia clínica, archivos, integridad, accesos, retención, respaldo y latidos | auditoría transversal y persistida |
| `fhir` | fachada FHIR de lectura y cliente para padrón externo | lee modelos de Casos, Instituciones y Registros |
| `frontend` | navegación, permisos visibles, diseño/ejecución de flujos y operación | consume la API; el servidor conserva la autorización efectiva |

## Boundaries

Los límites son módulos de un monolito, no servicios aislados. Comparten proceso Django, ORM, base y transacciones; esto es apropiado para las invariantes clínicas actuales. Los límites más claros son el adaptador FHIR, el cliente HTTP del frontend y las aplicaciones de inventario/agenda/red.

El límite menos claro es `casos`: además de ejecutar el flujo, coordina persistencia y reglas de cama, historia, filas, notificaciones, derivaciones e integración externa. Agenda y Red lo atraviesan mediante llamadas Python directas. Por ejemplo, `apps.red.motor` consume funciones internas `_registrar` y `_liberar_camas_del_caso`.

## Dirección de dependencias

- La SPA depende de contratos HTTP, no de módulos Django; el cliente y `useLista`/`useAccion` concentran autenticación, reintento y caché básica.
- El router y las URLs dependen de las views de todas las apps, como corresponde a la capa de entrega.
- La ejecución depende desde `casos.motor` hacia Formularios, Flujos, Instituciones y Registros. Agenda y Red vuelven a depender de Casos para iniciar, cancelar, registrar y liberar recursos.
- `apps.common` reúne autorización, scope institucional, archivos y CSV. Nueve módulos de entrega dependen de él; además resuelve modelos de Instituciones y Registros para archivos. Es una base compartida útil, pero debe mantenerse acotada a preocupaciones transversales.
- No se confirmó un ciclo de importación de módulo en el código de producción inspeccionado. Sí existe acoplamiento de dominio bidireccional de facto entre Casos y Red/Agenda: comparten comportamiento a través de llamadas directas y datos comunes.

## Flujos relevantes

1. **Diseño a ejecución:** el editor React crea/edita `Nodo` y `Conexion`; publicar valida el grafo; un `Caso` queda asociado a una `VersionFlujo`; `casos.motor.iniciar/avanzar` recorre automáticos y se detiene en tareas humanas, filas, tiempos, camas o fin.
2. **Atención y recursos:** `casos.motor` aplica efectos de entrada, guarda valores, crea eventos/notificaciones, asigna o libera camas y puede crear historia clínica. La Red crea un caso en el destino y luego modifica el caso de origen.
3. **Procesos diferidos:** `correr_tiempos` reactiva esperas y SLA con `select_for_update(skip_locked=True)`; otros comandos recuerdan turnos y avisan saturación. Compose los ejecuta serialmente en `tiempos`.
4. **Integración:** un nodo de integración llama por HTTP durante `avanzar`; una allowlist de infraestructura limita hosts. FHIR también puede completar datos de un ciudadano.

## Fortalezas

- Las versiones publicadas de flujos son inmutables desde las views y el motor valida estructura, condiciones y configuraciones antes de publicar.
- Las transiciones sensibles usan transacciones y, en filas/camas/tareas, hay bloqueos explícitos. Hay pruebas enfocadas en guardas de cama, transiciones, concurrencia de traslados, condiciones y tiempos.
- La autorización efectiva y el scope institucional están del lado del servidor; el frontend sólo oculta o habilita navegación.
- Las tareas dejan latidos persistidos y `/api/estado/` informa atraso con 503; el respaldo incluye restauración y comparación de tablas críticas.
- La fachada FHIR está separada como adaptador de lectura y las salidas HTTP tienen allowlist y timeout.

## Hallazgos principales

### ARQ-01 — El motor de Casos concentra reglas y efectos de dominios distintos

- **Estado:** confirmado.
- **Evidencia concreta:** `backend/apps/casos/motor.py` tiene 2.102 líneas, importa Formularios, Flujos, Instituciones y Registros y resuelve 13 tipos de `Nodo`. Dentro del mismo módulo valida el grafo, procesa condiciones, filas, tiempos, camas, historia, recetas, estudios, derivaciones, notificaciones e integración HTTP.
- **Archivos o módulos involucrados:** `backend/apps/casos/motor.py`; `backend/apps/casos/models.py`; `backend/apps/flujos/models.py`; `backend/apps/instituciones/models.py`; `backend/apps/registros/models.py`.
- **Escenario donde importa:** agregar un nodo clínico o cambiar la semántica de una transición obliga a modificar y probar un punto central que también controla cama, historia, fila y derivación.
- **Impacto:** alto coste de cambio y radio de regresión clínico/operativo innecesariamente amplio.
- **Nivel de confianza:** alto.
- **Prioridad:** P1.
- **Dirección general de mejora:** separar gradualmente los manejadores de efectos y transiciones por responsabilidad, detrás de una interfaz explícita del motor; conservar una única orquestación transaccional hasta que exista evidencia para partirla.
- **Qué no se debería cambiar todavía:** no reemplazar el motor ni dividir el monolito/base de datos; tampoco reescribir todos los nodos en una sola iniciativa.

### ARQ-02 — El contrato de los nodos está distribuido y no tiene esquema versionado

- **Estado:** confirmado.
- **Evidencia concreta:** `Nodo.Tipo` y `Nodo.config`/`Conexion.condicion` se almacenan en `JSONField` en `backend/apps/flujos/models.py`; `casos/motor.py` interpreta sus claves y valida por tipo; `frontend/src/lib/nodos.js` replica los tipos; `FlujoEditor.jsx` contiene ramas y paneles específicos de cada tipo, y `CasoDetalle.jsx` también decide cómo ejecutar varios tipos.
- **Archivos o módulos involucrados:** `backend/apps/flujos/models.py`; `backend/apps/casos/motor.py`; `frontend/src/lib/nodos.js`; `frontend/src/pages/diseno/FlujoEditor.jsx`; `frontend/src/pages/ejecucion/CasoDetalle.jsx`.
- **Escenario donde importa:** los nuevos tipos y configuraciones previstos requieren coordinar persistencia, validación, motor, editor y ejecución. Un cambio parcial puede dejar flujos publicados legibles pero no editables, o editables pero no ejecutables.
- **Impacto:** alto riesgo de incompatibilidades hacia adelante y de regresiones al evolucionar flujos ya guardados.
- **Nivel de confianza:** alto.
- **Prioridad:** P1.
- **Dirección general de mejora:** definir contratos explícitos por tipo —incluida versión y validación de compatibilidad— y someter backend/frontend a pruebas de contrato; migrar los tipos uno por uno empezando por los que cambien.
- **Qué no se debería cambiar todavía:** no eliminar JSON ni migrar todos los flujos existentes; no introducir un nuevo motor de workflows por este hallazgo.

### ARQ-03 — Red y Agenda dependen directamente de detalles internos de Casos

- **Estado:** confirmado.
- **Evidencia concreta:** `backend/apps/red/motor.py` llama a `motor_casos.iniciar`, `cancelar_caso`, `version_receptora_para_area` y a internos `_registrar`/`_liberar_camas_del_caso`; `backend/apps/agenda/motor.py` llama a `motor_casos.iniciar`. Red además crea y muta casos para materializar el traslado.
- **Archivos o módulos involucrados:** `backend/apps/red/motor.py`; `backend/apps/agenda/motor.py`; `backend/apps/casos/motor.py`.
- **Escenario donde importa:** al ampliar la red interinstitucional, cambiar el registro de eventos, el ciclo de cama o el inicio de casos puede romper traslados sin que el contrato sea visible ni estable.
- **Impacto:** acoplamiento de cambios entre módulos que deberían evolucionar con menor coordinación; uso de funciones privadas reduce la seguridad de refactor.
- **Nivel de confianza:** alto.
- **Prioridad:** P1.
- **Dirección general de mejora:** publicar operaciones de aplicación de Casos con entradas/salidas acotadas para Agenda y Red; dejar que Casos sea dueño de sus eventos, colas y camas, sin exponer internos.
- **Qué no se debería cambiar todavía:** no crear microservicios, broker genérico ni sincronización eventual para cada operación; la transacción única sigue aportando consistencia valiosa.

### ARQ-04 — Las tareas críticas comparten un trabajador serial que absorbe fallos

- **Estado:** confirmado en configuración; pendiente de confirmar en operación real.
- **Evidencia concreta:** `docker-compose.yml` ejecuta en el mismo bucle `correr_tiempos`, `recordar_turnos` y `alertar_saturacion`, todos con `|| true`. `respaldos` tiene otro bucle con la misma absorción. Hay latidos y `/api/estado/`, pero no se encontró configuración de monitor externo y se asumió Compose.
- **Archivos o módulos involucrados:** `docker-compose.yml`; `backend/apps/casos/management/commands/correr_tiempos.py`; `backend/apps/agenda/management/commands/recordar_turnos.py`; `backend/apps/red/management/commands/alertar_saturacion.py`; `backend/apps/auditoria/latidos.py`; `backend/cauce/urls.py`.
- **Escenario donde importa:** una pasada lenta, bloqueada o fallida retrasa los comandos que siguen; pueden quedar esperas clínicas sin reactivar, recordatorios omitidos o alertas de saturación atrasadas. El sistema se entera por latidos, pero no hay evidencia de que alguien lo alerte.
- **Impacto:** degradación operacional silenciosa en componentes que cambian el curso de casos y alertas.
- **Nivel de confianza:** alto para el diseño, medio para su efecto en producción.
- **Prioridad:** P1.
- **Dirección general de mejora:** ejecutar cada cadencia crítica de forma aislable y observable, con política explícita de reintento/error; conectar `/api/estado/` a un monitor antes de aumentar la automatización.
- **Qué no se debería cambiar todavía:** no incorporar una plataforma de colas ni un scheduler complejo sin definir volumen, SLA, responsable operativo y canal de alerta.

### ARQ-05 — Las integraciones salientes bloquean el avance transaccional y no tienen entrega durable

- **Estado:** confirmado.
- **Evidencia concreta:** `casos.motor.avanzar` es transaccional y, al procesar un nodo de integración, `_llamar_externo` usa `urlopen` con timeout de hasta 6 segundos. La configuración permite POST, pero no se observó outbox, idempotency key ni reintento durable. El propio código evita la llamada durante un ensayo porque una llamada externa no se revierte con la transacción local.
- **Archivos o módulos involucrados:** `backend/apps/casos/motor.py`; `backend/apps/fhir/cliente.py`; `backend/cauce/settings.py`.
- **Escenario donde importa:** si una futura integración de escritura crea un turno u orden externa y la respuesta se pierde, reintentar puede duplicar la operación; además una dependencia lenta retiene el flujo del caso hasta el timeout.
- **Impacto:** riesgo de inconsistencia con terceros y de latencia en atención cuando las integraciones ganen criticidad.
- **Nivel de confianza:** alto para el mecanismo, medio para prioridad actual porque se asumió que no es bloqueante hoy.
- **Prioridad:** P2.
- **Dirección general de mejora:** antes de una integración crítica de escritura, persistir intención/resultado e incorporar idempotencia y reintento controlado; mantener síncrona sólo la lectura opcional cuyo fallo no detiene la atención.
- **Qué no se debería cambiar todavía:** no hacer asíncrona toda consulta de padrón ni eliminar la allowlist, el timeout o el registro de fallos actuales.

## Riesgos no confirmados

- No hay evidencia de volumen, concurrencia máxima ni tiempos de respuesta reales; no se prioriza una separación física del motor por tamaño de archivo solamente.
- No se verificó proveedor, réplicas, backups fuera del volumen Compose ni monitor externo; el riesgo operacional de ARQ-04 puede ser menor o mayor según esa infraestructura.
- No se probó un contrato real con un HIS/padrón ni operaciones remotas de escritura; ARQ-05 no prueba fallas observadas, sólo el mecanismo que las permitiría.
- No se halló una política automatizada que prohíba dependencias de importación entre apps. La ausencia aumenta el riesgo futuro, pero no constituye por sí sola un hallazgo de producto.

## Decisiones que conviene conservar

- Mantener el monolito y una base transaccional mientras el producto está validando venta y flujos; partir componentes ahora elevaría el coste operativo sin evidencia de beneficio.
- Mantener flujos publicados versionados y la validación antes de publicación.
- Mantener los bloqueos/transacciones de cama, filas, traslados y tiempos, y el registro de eventos clínicos.
- Mantener el scope institucional y la autorización efectiva en backend.
- Mantener la allowlist, timeout, límite de lectura y supresión de llamadas externas durante ensayos.
- Mantener los latidos y la verificación por restauración de respaldos; completar su operación, no sustituirlos.

## Cambios que no se justifican actualmente

- Reescribir el backend en Clean/Hexagonal Architecture o introducir una capa por cada modelo.
- Separar Casos, Agenda, Red o FHIR en microservicios.
- Sustituir todo `JSONField` de flujos por tablas relacionales en bloque.
- Introducir un bus de eventos genérico, Celery u otro scheduler sin un SLA, volumen y operación objetivo definidos.
- Descomponer componentes React sólo por cantidad de líneas: la prioridad es aislar el contrato de nodo que ya cruza backend y frontend.

## Issues derivados

Se derivan cinco issues, uno por cada hallazgo confirmado con impacto y dirección de mejora:

1. [#27 — P1: Modularizar el motor de ejecución de casos por efectos y transiciones](https://github.com/Mkdir-arg/SistemaDeSalud/issues/27).
2. [#28 — P1: Definir contratos versionados para tipos y configuración de nodos](https://github.com/Mkdir-arg/SistemaDeSalud/issues/28).
3. [#29 — P1: Estabilizar el contrato entre Casos, Agenda y Red](https://github.com/Mkdir-arg/SistemaDeSalud/issues/29).
4. [#30 — P1: Aislar y monitorear las tareas periódicas críticas](https://github.com/Mkdir-arg/SistemaDeSalud/issues/30).
5. [#31 — P2: Preparar entrega idempotente para integraciones externas críticas](https://github.com/Mkdir-arg/SistemaDeSalud/issues/31).

## Issues

Los detalles completos —problema, evidencia, impacto, alcance, dirección, criterios de aceptación, fuera de alcance, riesgos y dependencias— se publican en los cinco issues derivados. No se proponen issues por estilo, tamaño de carpeta ni adopción de un patrón teórico.
