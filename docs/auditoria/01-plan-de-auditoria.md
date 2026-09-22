# Plan de auditoría técnica

## Contexto inferido del repositorio

El proyecto es un monolito con backend Django/DRF (`backend/`), frontend React/Vite
(`frontend/`), PostgreSQL y ejecución local mediante Docker Compose. El dominio
central combina instituciones, usuarios y capacidades, flujos versionados y casos
clínico-operativos. Incluye filas, agenda, internación, farmacia, auditoría y una
fachada e integración FHIR.

Hay pruebas backend por aplicación y pruebas E2E con Playwright. No se encontraron
workflows de CI versionados en las ubicaciones habituales. La documentación existente
describe una demo y procesos funcionales; sirve para localizar recorridos, pero cada
afirmación relevante se contrastará con código, pruebas y configuración local.

## Supuestos y limitaciones

- Alcance: entorno local, hasta cinco días de trabajo de una persona.
- No se consultarán ni modificarán servicios, credenciales, datos o infraestructura
  externos. La integración FHIR se revisará por contrato, código y pruebas locales.
- No se presupone que la demo, sus datos ni los documentos existentes representen una
  instalación productiva.
- La auditoría produce hallazgos priorizados y evidencia reproducible; no implementa
  correcciones ni crea issues.
- El checkout contiene cambios locales ajenos a este plan; la auditoría debe ser de
  solo lectura.

## Riesgos iniciales

1. **P1 — motor y límites de acceso:** los casos, las capacidades por institución y
   los subprocesos con retorno concentran reglas que, si se contradicen, alteran la
   atención o exponen registros entre instituciones.
2. **P1 — verificación no automatizada en integración:** al no hallarse CI versionado,
   una regresión puede depender de pasos manuales aunque existan suites locales.
3. **P1 — tareas periódicas y recuperación:** tiempos, respaldos y health checks son
   procesos separados del backend; hay que demostrar cómo fallan, se detectan y se
   recuperan localmente.
4. **P2 — rendimiento de vistas operativas:** bandejas, filas, agenda, historia e
   internación pueden crecer por volumen y relaciones; se revisarán sus consultas y
   carga de interfaz antes de medir bajo carga.
5. **P2 — deuda de mantenibilidad:** el dominio está repartido en varias aplicaciones,
   motores y páginas; importa detectar duplicación o dependencias cruzadas que hagan
   riesgoso modificar los flujos.

## Orden recomendado de auditorías

| Orden | Tiempo orientativo | Prioridad | Resultado de la etapa |
|---|---:|---|---|
| 1. Mapa de arquitectura y recorridos críticos | Día 1 | P1 | Mapa de límites, datos y tres recorridos críticos verificables. |
| 2. Testing y Developer Experience | Día 1-2 | P1 | Línea de base de suites, huecos y comando local reproducible. |
| 3. Confiabilidad del motor, permisos e integraciones | Día 2-3 | P1 | Riesgos de estado, concurrencia, fallas externas y recuperación. |
| 4. Mantenibilidad | Día 3-4 | P2 | Hotspots concretos y dependencias que elevan el costo de cambio. |
| 5. Performance y frontend | Día 4 | P2 | Dos pantallas/consultas prioritarias y una línea de base local. |
| 6. Observabilidad básica y cierre | Día 5 | P2 | Señales mínimas, faltantes y backlog P0-P3 consolidado. |

El orden se calcula por impacto x probabilidad x frecuencia x coste de no actuar.
No se abrirá una pista profunda de rendimiento, telemetría o refactorización hasta
cerrar los riesgos P1 del motor y de la validación.

## Arquitectura

- **Por qué auditarla:** el sistema combina definición de flujos, ejecución de casos,
  datos clínicos, permisos y una SPA; sus límites determinan dónde pueden aparecer
  incoherencias.
- **Preguntas concretas:** ¿qué módulo es autoridad para cada estado del caso? ¿cómo
  se aplica el alcance de institución y grupo en API y UI? ¿qué dependencias existen
  entre el motor, los modelos y FHIR? ¿qué rutas cruzan límites sin un contrato claro?
- **Evidencia:** `backend/apps/*/models.py`, vistas, serializers, motores, rutas,
  `frontend/src/api/`, rutas de `App.jsx`, y pruebas de casos, flujos, cuentas y FHIR.
- **Profundidad:** medio.
- **Fuera de alcance:** rediseño de módulos, microservicios y reescritura de la API.
- **Resultado esperado:** un mapa de componentes y tres recorridos críticos
  (ingreso/avance de caso, acceso a historia y consulta FHIR) con propietarios de
  estado, contratos y riesgos.

## Mantenibilidad

- **Por qué auditarla:** los cambios en flujos clínicos atraviesan modelos, motores,
  serialización, permisos, UI y pruebas.
- **Preguntas concretas:** ¿dónde se repiten reglas de autorización o transición?
  ¿qué archivos concentran demasiadas responsabilidades? ¿qué dependencias circulares
  o implícitas dificultan probar y cambiar el sistema?
- **Evidencia:** hotspots elegidos por tamaño, dependencias y cambios recientes;
  imports entre aplicaciones; servicios/motores; convenciones en tests y frontend.
- **Profundidad:** medio, limitado a los cinco hotspots que afecten recorridos P1.
- **Fuera de alcance:** formateo masivo, renombres cosméticos y refactorización
  preventiva sin hallazgo.
- **Resultado esperado:** hasta cinco hallazgos accionables, cada uno con archivo,
  mecanismo, impacto y alternativa de bajo riesgo.

## Testing

- **Por qué auditarla:** hay pruebas backend y E2E, pero la protección real depende de
  que cubran invariantes del dominio y se puedan ejecutar de forma consistente.
- **Preguntas concretas:** ¿qué cubren los recorridos críticos y sus rechazos? ¿qué
  pruebas distinguen institución, rol y grupo? ¿qué casos de transición, reintento,
  concurrencia y error FHIR faltan? ¿qué pruebas E2E están vigentes y cuáles son
  temporales u obsoletas?
- **Evidencia:** inventario de tests backend, Playwright, configuración de test,
  comandos declarados, resultados de una selección enfocada y cobertura indirecta por
  endpoint/regla.
- **Profundidad:** profundo en los tres recorridos P1; superficial para el resto.
- **Fuera de alcance:** perseguir cobertura porcentual global, reescribir suites o
  ejecutar carga masiva.
- **Resultado esperado:** matriz requisito-riesgo-prueba, una lista corta de huecos
  P1/P2 y un conjunto mínimo de comandos locales repetibles.

## Performance y frontend

- **Por qué auditarla:** las pantallas operativas listan relaciones y datos de casos;
  el costo puede crecer sin ser visible en la demo.
- **Preguntas concretas:** ¿las listas críticas tienen paginación y orden estable?
  ¿hay N+1, serialización excesiva o peticiones redundantes? ¿qué ruta o bundle debe
  medirse primero? ¿la UI refleja los rechazos de permisos y fallas del API?
- **Evidencia:** consultas y serializers de bandejas, filas, agenda e historia;
  `frontend/src/api/`, rutas y componentes de esas pantallas; build local y DevTools
  solo para establecer una línea de base simple.
- **Profundidad:** superficial, ampliable a medio solo ante una señal concreta.
- **Fuera de alcance:** benchmark de producción, pruebas de carga, optimización de
  bundle general y rediseño visual.
- **Resultado esperado:** dos escenarios medidos localmente y, si existe, una causa
  técnica probable con su prioridad; si no hay señal, constancia de que no se escala.

## Confiabilidad

- **Por qué auditarla:** el motor de casos, la cola, las tareas de tiempo, los
  respaldos y las integraciones determinan continuidad y consistencia del proceso.
- **Preguntas concretas:** ¿las transiciones son atómicas e idempotentes? ¿qué pasa
  si dos operadores actúan sobre el mismo caso/cama/fila? ¿cómo se comporta una
  consulta FHIR lenta o inválida? ¿qué prueban health, latidos y respaldo, y qué
  recuperación local está documentada?
- **Evidencia:** motores, transacciones y bloqueos de filas/camas, comandos de
  `tiempos` y `respaldos`, Compose, health endpoint, manejo de errores FHIR y sus
  pruebas.
- **Profundidad:** profundo en transición de caso, cola/cama y FHIR; medio para
  respaldo y tareas periódicas.
- **Fuera de alcance:** restauración sobre datos reales, pruebas de desastre,
  alta disponibilidad y validación de proveedores externos.
- **Resultado esperado:** tabla de fallas plausibles, detección actual, impacto,
  evidencia y prioridad; incluirá claramente lo que solo podría validarse fuera del
  entorno local.

## Observabilidad básica

- **Por qué auditarla:** el repositorio ya tiene health, logging, latidos y señales
  de estado; hay que saber si sirven para localizar una falla local relevante.
- **Preguntas concretas:** ¿qué señal permite detectar base caída, tarea detenida,
  respaldo vencido o error de integración? ¿la señal identifica servicio, momento y
  causa? ¿qué queda sin señal?
- **Evidencia:** configuración de logging, `/api/health/`, estado/latidos, comandos
  de auditoría y salida de los servicios de Compose.
- **Profundidad:** superficial.
- **Fuera de alcance:** APM, métricas centralizadas, alertas, retención de logs y
  tableros de producción.
- **Resultado esperado:** checklist de señales locales mínimas y hasta tres faltantes
  que afecten P1/P2.

## Developer Experience

- **Por qué auditarla:** Docker, dos runtimes y servicios auxiliares deben permitir
  que una persona reproduzca una regresión sin conocimiento implícito.
- **Preguntas concretas:** ¿el arranque local y las suites clave tienen una única
  secuencia fiable? ¿los documentos coinciden con los manifiestos y Compose? ¿qué
  falta para impedir que una regresión llegue sin ejecución automatizada?
- **Evidencia:** Dockerfiles, Compose, entrypoints, `.env.example`, manifiestos de
  dependencias, comandos declarados, documentación de demo y configuración CI
  versionada disponible.
- **Profundidad:** medio.
- **Fuera de alcance:** cambiar imágenes, dependencias, scripts, pipelines o el
  proceso de despliegue.
- **Resultado esperado:** guía de reproducción de una página, discrepancias
  verificadas de documentación y recomendación concreta para un control mínimo de CI
  si el hallazgo se confirma.

## Profundidad por área

| Área | Profundidad | Corte explícito |
|---|---|---|
| Arquitectura | Medio | Tres recorridos críticos, no reconstrucción total. |
| Mantenibilidad | Medio | Máximo cinco hotspots. |
| Testing | Profundo | Solo invariantes y rechazos P1; inventario superficial del resto. |
| Performance y frontend | Superficial | Dos escenarios locales; sin carga. |
| Confiabilidad | Profundo/medio | Profundo en motor, fila/cama y FHIR; medio en tareas y respaldo. |
| Observabilidad básica | Superficial | Señales existentes y faltantes inmediatos. |
| Developer Experience | Medio | Arranque, pruebas clave, documentación y ausencia/presencia de CI. |

## Fuera de alcance

- Auditoría de seguridad integral, pentest, cumplimiento normativo y revisión legal.
- Producción, redes, secretos, permisos de nube, despliegues, backups reales y datos
  no locales.
- Pruebas de carga, capacidad, accesibilidad exhaustiva y compatibilidad de todos los
  navegadores.
- Implementar mejoras, refactorizar, actualizar dependencias o abrir issues.

## Criterio de prioridad P0-P3

- **P0:** pérdida, exposición o corrupción inmediata de datos locales; transición
  clínica que puede ejecutar una acción incorrecta sin mitigación. Requiere detener
  el uso del recorrido afectado hasta contenerlo.
- **P1:** riesgo alto, recurrente o bloqueante en los recorridos críticos; incluye
  límites de acceso, inconsistencia de estado, tarea esencial sin recuperación o
  ausencia de una verificación que deja pasar regresiones críticas.
- **P2:** problema con impacto concreto y evidencia suficiente, pero con alternativa
  operativa o alcance limitado; por ejemplo degradación de una pantalla frecuente o
  deuda que encarece un cambio próximo.
- **P3:** mejora conveniente sin daño actual demostrable ni dependencia inmediata.

La prioridad se asigna con evidencia de impacto, probabilidad, frecuencia y coste de
no actuar. Una recomendación no sube de prioridad solo por ser una buena práctica.

## Definición de terminado

La primera auditoría queda terminada cuando exista un resultado breve que incluya:

1. mapa validado de los tres recorridos críticos y sus límites;
2. matriz de cobertura y huecos de prueba para esos recorridos;
3. inventario de fallas/reintentos y señales locales de recuperación;
4. hasta diez hallazgos priorizados P0-P3 con evidencia, impacto, alcance y siguiente
   experimento o corrección sugerida;
5. registro explícito de validaciones no realizadas por ser externas al entorno local;
6. una recomendación de próximo corte, sin haber modificado el repositorio.

## Próximo paso recomendado

Iniciar el día 1 con un recorrido trazable de **admisión → triage/fila → atención o
derivación**, y en paralelo mapear sus pruebas de permisos. Es el corte que valida
antes que nada la coherencia entre estado clínico, instituciones/grupos, API y UI;
también decide si aparece un P0/P1 que deba desplazar el resto del plan.
