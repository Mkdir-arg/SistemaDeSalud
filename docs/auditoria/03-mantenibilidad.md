# Auditoría de mantenibilidad

## Resumen ejecutivo

El coste de cambio está concentrado, no repartido de forma uniforme. El núcleo
de mayor riesgo es la pareja **motor de casos + editor de flujos**: dentro de
las últimas 200 revisiones locales, `backend/apps/casos/motor.py` cambió 28
veces y `frontend/src/pages/diseno/FlujoEditor.jsx` 26; además, ambos aparecen
juntos en 15 commits. Cambiar cómo se define o ejecuta un nodo de flujo suele
atravesar persistencia JSON, API, motor, pantalla de diseño, pantalla de
ejecución y pruebas.

No se recomienda una campaña de limpieza general. La primera inversión debe
hacer explícito y validable el contrato de configuración de los nodos; después,
reducir responsabilidades en los dos hotspots preservando sus interfaces y
pruebas. Las apps de Django y la cobertura focalizada ya dan una base útil para
hacerlo por cortes pequeños.

## Alcance y limitaciones

Se inspeccionaron estructura de módulos, dependencias entre apps, archivos
grandes, validación y manejo de errores, configuración, comentarios de deuda,
pruebas y las últimas 200 revisiones Git. Se consultó
`docs/auditoria/00-ownership-del-proyecto` solo como contexto; los hallazgos de
este documento se contrastaron contra código e historial actuales.

No se ejecutaron la suite completa, E2E, análisis de cobertura ni servicios de
Docker: la sesión es de auditoría estática y el árbol contiene cambios ajenos
sin confirmar (`backend/entrypoint.sh`, `docker-compose.yml`, `.gitattributes`,
`.playwright-cli/` y `docs/auditoria/`). No se infieren métricas de producción,
tiempos del equipo ni causas de negocio a partir del mensaje de un commit.

## Hotspots

| Zona | Evidencia de cambio | Por qué encarece cambios |
| --- | --- | --- |
| `backend/apps/casos/motor.py` | 2.102 líneas; 28 cambios; cambia junto con editor, vistas, serializers y pruebas | Reúne transiciones, reglas, permisos operativos, filas, camas, historia clínica, notificaciones, subprocesos e integraciones. |
| `frontend/src/pages/diseno/FlujoEditor.jsx` | 3.304 líneas; 26 cambios; 15 cambios conjuntos con el motor | Coordina canvas, gestos, carga, guardado, simulación, modales y configuración de todos los nodos. |
| `backend/apps/casos/views.py` | 1.128 líneas; 25 cambios | Expone muchas operaciones clínicas y repite adaptación HTTP sobre el motor. |
| Contrato `Nodo.config` | 55 accesos directos en motor, serializer/views de flujos y editor | Es un JSON de comportamiento sin validación de esquema por tipo en la API. |
| `backend/apps/common.py` | 570 líneas; 11 cambios; es ancestro de viewsets | Mezcla permisos, alcance institucional, filtros, archivos clínicos y CSV; una modificación compartida tiene radio de impacto alto. |

## Coste de cambio

La estimación se expresa en radio técnico, no en días-persona: no hay datos
confiables de capacidad, revisiones o despliegues del equipo.

| Cambio representativo | Radio actual estimado | Riesgo dominante |
| --- | --- | --- |
| Agregar/modificar una opción de un nodo | Alto: 4–6 superficies (`config`, editor, API, motor, ejecución, pruebas) | UI y motor aceptan o interpretan distinto el mismo JSON. |
| Agregar una transición/efecto del motor | Alto: motor, vista, serializers, pantallas y pruebas de flujo/caso | Regresión lateral de filas, camas, trazabilidad o subprocesos. |
| Agregar una acción operativa de caso | Medio-alto: vista, permiso, motor, refresh de detalle y prueba API | Omitir una precondición, la traducción de error o el contexto del serializer. |
| Cambiar una política transversal de viewsets | Medio-alto: `common.py` y todos sus consumidores | Aplicar un cambio de permiso, alcance o exportación a más endpoints de los previstos. |

## Complejidad relevante

`motor.py` no es grande por una única rutina accidental: sus funciones cubren
dominios distintos y mutan los mismos agregados de caso. Por ejemplo, contiene
evaluación de condiciones y elección de siguiente nodo, ejecución automática,
colas, camas, firmas, historia clínica, derivaciones e integración HTTP. La
transacción en cada operación protege invariantes, pero también vuelve costoso
aislar mentalmente una modificación.

En `FlujoEditor.jsx`, el componente raíz comparte estado entre el lienzo SVG,
selección, arrastre, zoom, conexiones, undo/autoguardado, carga paginada,
simulación y el panel de propiedades. La dificultad no es la cantidad de JSX:
es que cambios locales de configuración conviven con interacciones delicadas
del canvas en el mismo archivo.

No se detectó un TODO/FIXME/HACK vivo que, por sí mismo, sea una prioridad de
mantenibilidad. Los `pass` localizados pertenecen a manejos controlados de
errores o a migraciones y no son evidencia suficiente de código muerto.

## Acoplamiento y cohesión

Las apps separan bien modelos y endpoints por capacidad (`casos`, `flujos`,
`registros`, `instituciones`, etc.), pero `casos` es el integrador real: su
motor importa cuentas, instituciones y registros, y es invocado desde flujos,
red, agenda y vistas de casos. Esa centralidad es razonable para ejecutar un
caso, pero no tiene una frontera interna que distinga capacidades.

El mayor acoplamiento transversal no es una importación: es `Nodo.config`.
`NodoSerializer` recibe el campo entero y valida la pertenencia de formulario y
grupos, pero no claves, tipos, combinaciones ni defaults del JSON. El editor lo
mezcla con actualizaciones parciales; el motor lo lee con `.get()` para decidir
fila, firmas, SLA, sectores, estados, derivaciones e integraciones. La
compatibilidad queda distribuida en comentarios y defaults.

`common.py` presenta cohesión baja: permisos/capacidades, filtrado institucional,
uploads clínicos y CSV no evolucionan por el mismo motivo. No es un P1 porque
su churn es bastante menor y extraerlo sin un consumidor concreto podría crear
movimiento sin beneficio.

## Duplicación relevante

La duplicación que sí afecta cambios está en `CasoViewSet`: varias acciones
repiten obtener el caso, verificar permiso, llamar al motor, convertir
`ErrorMotor` en 400, volver a consultar y serializar el detalle. Esto aparece,
con variaciones, en llamar, rellamar, devolver, ausente, cama, receta, estudio,
interconsulta, cancelar e iniciar. La repetición hace que un endpoint nuevo
pueda olvidar una parte de la envoltura; no justifica una abstracción genérica
para todos los viewsets.

No se prioriza duplicación de estilos, textos o helpers pequeños: no hay
evidencia de que sean puntos de cambio o de fallos recurrentes.

## Abstracciones problemáticas

Faltan dos abstracciones acotadas:

- Un contrato versionable por tipo de nodo, con validación de API y defaults
  explícitos para configuraciones existentes.
- Una fachada estable del motor que permita extraer capacidades cohesivas sin
  obligar a migrar de una vez sus callers.

También falta un adaptador HTTP específico para acciones de caso. En cambio, no
conviene introducir una capa genérica de "servicios" en todas las apps: la
evidencia se concentra en casos y flujos, no en el proyecto entero.

## Configuración y conocimiento implícito

La configuración de despliegue está bastante documentada en `.env.example`,
`docker-compose.yml`, `docker-compose.override.yml` y `cauce/settings.py`.
Hay defaults repetidos entre esos planos, pero el motivo y la separación
desarrollo/producción están escritos; no se deriva un issue solo por eso.

El conocimiento implícito de mayor impacto vive en `config` de nodos: qué
claves aplican a cada tipo, cuál es su default y qué combinaciones son válidas
se reparte entre el editor, el motor, tests y comentarios. Por ejemplo,
`firma_roles`, `firma_matricula`, `con_fila`, `sla_minutos`, `sector`,
`flujo_destino_id`, `url` y `prioridad_mapa` no tienen una definición común.

## Fortalezas

- La división en apps de Django y el router central hacen visibles los límites
  externos, aunque `casos` siga siendo transversal.
- Hay pruebas focalizadas para motor, permisos, filas exclusivas, volumen,
  validación/ensayo y APIs; el editor además tiene E2E específico.
- Los comentarios del código suelen explicar la consecuencia operativa de una
  guarda, default o transacción. Eso reduce conocimiento tribal y debe
  preservarse al extraer módulos.
- El historial muestra que se agregaron pruebas y correcciones de rendimiento
  junto con funcionalidad, no solo cambios de interfaz.

## Hallazgos principales

### MNT-01 — Motor de casos con demasiadas capacidades acopladas

- **Prioridad:** P1. **Confianza:** alta.
- **Evidencia:** `backend/apps/casos/motor.py` tiene 2.102 líneas y es el
  archivo con mayor churn (28/200). Cambió junto con `FlujoEditor.jsx` y
  `casos/views.py` en 15 commits cada uno; contiene reglas, ejecución, cola,
  camas, historia, notificaciones e integraciones.
- **Archivos involucrados:** `backend/apps/casos/motor.py`,
  `backend/apps/casos/views.py`, `backend/apps/casos/models.py`,
  `backend/apps/casos/tests*.py`, más `instituciones`, `registros` y `flujos`.
- **Cambio representativo afectado:** agregar un efecto de nodo o cambiar una
  transición clínica.
- **Coste/riesgo actual:** alto; revisar una modificación exige recuperar
  invariantes de varios subdominios en el mismo módulo y aumenta la probabilidad
  de una regresión lateral.
- **Frecuencia:** alta por churn e incorporación histórica de filas, camas,
  firmas, SLA, integraciones y red.
- **Dirección de mejora:** mantener una fachada pública y extraer por cortes
  cohesionados, empezando por una capacidad con pruebas fuertes (cola, camas o
  integraciones). No realizar una reescritura.

### MNT-02 — Configuración de nodos como contrato implícito entre capas

- **Prioridad:** P1. **Confianza:** alta.
- **Evidencia:** 55 accesos directos a `config` entre motor, flujos y editor.
  `NodoSerializer.validate()` valida relaciones, no el contenido de `config`;
  el editor y el motor comparten los mismos defaults de forma dispersa.
- **Archivos involucrados:** `backend/apps/flujos/models.py`,
  `backend/apps/flujos/serializers.py`, `backend/apps/flujos/views.py`,
  `backend/apps/casos/motor.py`,
  `frontend/src/pages/diseno/FlujoEditor.jsx` y pruebas de casos/flujos/editor.
- **Cambio representativo afectado:** sumar o modificar un parámetro de fila,
  firma, SLA, integración, derivación o prioridad.
- **Coste/riesgo actual:** alto; un payload válido para la pantalla puede ser
  semánticamente inválido para ejecución, o una compatibilidad histórica puede
  romperse al cambiar un default.
- **Frecuencia:** alta; 15 commits conjuntos entre motor y editor y múltiples
  capacidades recientes configuradas por nodo.
- **Dirección de mejora:** contrato por tipo validado en la API, con defaults y
  compatibilidad explícitos; pruebas de contrato válidas, inválidas y legado.

### MNT-03 — Editor de flujos monolítico en un hotspot de evolución

- **Prioridad:** P1. **Confianza:** alta.
- **Evidencia:** `FlujoEditor.jsx` tiene 3.304 líneas y 26 cambios; reúne carga,
  persistencia, canvas, selección, undo, simulación y formularios de todos los
  tipos de nodo. Tiene 15 cambios conjuntos con el motor y E2E dedicado.
- **Archivos involucrados:** `frontend/src/pages/diseno/FlujoEditor.jsx`,
  `frontend/e2e/editor.spec.js`, `frontend/src/lib/nodos.js`,
  `backend/apps/flujos/*` y `backend/apps/casos/motor.py`.
- **Cambio representativo afectado:** agregar una propiedad o interacción de
  nodo sin alterar drag, zoom, conexiones, publicación o simulación.
- **Coste/riesgo actual:** alto; el archivo impone cargar contexto de UI no
  relacionado y hace amplia una revisión que debería ser local.
- **Frecuencia:** alta; el historial registra cambios funcionales y fixes de
  canvas/editor repetidos.
- **Dirección de mejora:** separar hook de carga/guardado, lienzo-interacciones
  y panel de configuración, manteniendo payloads, rutas y E2E.

### MNT-04 — Adaptación HTTP repetida en operaciones de caso

- **Prioridad:** P2. **Confianza:** alta.
- **Evidencia:** `CasoViewSet` (1.128 líneas, 25 cambios) contiene más de una
  docena de acciones y repite el patrón permiso → motor → `ErrorMotor` →
  recarga → serializer.
- **Archivos involucrados:** `backend/apps/casos/views.py`,
  `backend/apps/casos/motor.py`, `backend/apps/casos/serializers.py` y pruebas
  API/permisos.
- **Cambio representativo afectado:** agregar una operación clínica u homogeneizar
  una respuesta de error/detalle.
- **Coste/riesgo actual:** medio-alto; es fácil omitir una guarda, contexto de
  serializer o refresh, dejando endpoints parecidos con semántica distinta.
- **Frecuencia:** alta por churn del archivo; no se puede inferir uso de cada
  endpoint en producción.
- **Dirección de mejora:** helper limitado a operaciones de caso, sin ocultar
  precondiciones propias de cada acción ni cambiar los endpoints.

### MNT-05 — `common.py` concentra infraestructura transversal heterogénea

- **Prioridad:** P2, en observación. **Confianza:** media.
- **Evidencia:** 570 líneas y 11 cambios; combina capacidades/permisos, alcance
  institucional, filtros, uploads clínicos, descarga, CSV y la clase base de
  los viewsets. Es dependencia de varios módulos.
- **Archivos involucrados:** `backend/apps/common.py` y los viewsets que heredan
  `BaseModelViewSet`.
- **Cambio representativo afectado:** cambiar una regla de alcance, exportación
  o almacenamiento de archivos.
- **Coste/riesgo actual:** medio-alto por radio de impacto, aunque no hay
  evidencia de fallos recurrentes ni churn comparable al motor.
- **Frecuencia:** media.
- **Dirección de mejora:** no extraer por tamaño; separar solo al tocar un
  consumidor concreto, comenzando por archivos/CSV fuera de permisos y scope.

## Código que no conviene refactorizar actualmente

- Los comandos de siembra (`seed_volumen.py`, `seed_guardia.py` y afines), aun
  cuando son largos y cruzan módulos. Son código de demo/prueba con alto
  conocimiento de escenario; no están entre los principales paths de cambio
  productivo y partirlos ahora elevaría el riesgo de dejar escenarios incoherentes.
- `frontend/src/components/ui.jsx` y `frontend/src/components/Shell.jsx` solo
  por su tamaño. Son compartidos y cambian, pero la evidencia no demuestra
  responsabilidades mezcladas comparables a motor/editor; una extracción
  cosmética tendría radio visual grande.
- Los serializers/modelos simples por app. La estructura actual aporta límites
  comprensibles y no hay evidencia de duplicación o churn que justifique una
  capa de dominio global.
- La separación de servicios en Compose. Repite variables de entorno, pero los
  comentarios y la distinción operativa son claros; no se debe consolidar a
  costa de perder procesos aislados y observables.

## Riesgos no confirmados

- No se midió cobertura ni mutación: las pruebas existentes indican intención,
  no que todos los caminos de integración editor/API/motor estén cubiertos.
- No se verificaron PRs remotos ni despliegues; el churn se basa solo en el
  historial Git local de 200 revisiones.
- No hay telemetría de uso. Un endpoint de bajo uso puede tener más churn que
  uno crítico por causas de implementación y no de prioridad operativa.
- La posible divergencia de `config` se confirma como riesgo estructural; no se
  demostró en esta sesión un incidente concreto de datos inválidos persistidos.

## Issues derivados

Se crearon issues solo para los cuatro hallazgos con escenario de cambio y
dirección de mejora concreta. MNT-05 queda documentado sin issue hasta que un
cambio en un consumidor justifique la extracción.

## Issues

- [#1 Validar por tipo el contrato de configuración de nodos](https://github.com/Mkdir-arg/SistemaDeSalud/issues/1)
- [#2 Separar capacidades del motor de casos detrás de una fachada estable](https://github.com/Mkdir-arg/SistemaDeSalud/issues/2)
- [#3 Descomponer el editor de flujos por responsabilidades sin cambiar su UX](https://github.com/Mkdir-arg/SistemaDeSalud/issues/3)
- [#4 Unificar el adaptador HTTP de operaciones de caso](https://github.com/Mkdir-arg/SistemaDeSalud/issues/4)
