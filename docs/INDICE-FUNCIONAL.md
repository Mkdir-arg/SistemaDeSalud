# Índice de documentación — I-Core Salud

> Qué documento leer para cada cosa y qué contiene.
> Actualizado el **22/09/2026** contra `main` en `fca71e3`.

La regla de esta carpeta: **lo que describe cómo funciona el sistema se mantiene al
día o se borra.** Lo que describe un trabajo terminado se archiva en
[`historico/`](historico/README.md) y no se lee como estado actual.

---

## Empezá por tu rol

| Si sos… | Abrí |
|---|---|
| **Quien lo vende** | [`PARA-VENTAS.md`](PARA-VENTAS.md) — qué es, qué mostrar, qué contestar y qué no prometer |
| **Quien lo diseña** | [`PARA-DISENO.md`](PARA-DISENO.md) — qué pantallas hay, dónde vive la marca, qué reglas respetar |
| **Quien lo programa** | Seguí con la tabla de abajo |

Las dos primeras están escritas sin jerga técnica y no mencionan un solo endpoint.
El resto de esta carpeta está escrito para desarrollo: es preciso a propósito, y por
eso no es el mejor punto de entrada para todo el mundo.

---

## Por dónde empezar, en detalle

| Si necesitás… | Leé |
|---|---|
| Entender **qué hace el sistema** | [`funcionalidades/`](funcionalidades/README.md) → la ficha del módulo |
| Saber **en qué estado está el proyecto** | [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) |
| Entender **el vocabulario** de finanzas y cobertura | [`CONTEXT.md`](../CONTEXT.md) |
| **Mostrar** el sistema a un cliente | [`entornos/README.md`](entornos/README.md) → [guion comercial](entornos/guia-demo-comercial.md) |
| **Configurar** un hospital desde cero | [`entornos/guia-configuracion-desde-cero.md`](entornos/guia-configuracion-desde-cero.md) |
| Saber **quién puede hacer qué** | [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md), o [`roles/`](roles/README.md) rol por rol |
| **Desarrollar** sobre el frontend | [`FUNDACION-FRONTEND.md`](FUNDACION-FRONTEND.md) |
| Entender **por qué** algo se hizo así | [`historico/`](historico/README.md) |

---

## 1. Documentación funcional por módulo

[`docs/funcionalidades/`](funcionalidades/README.md) — la fuente de verdad. Cada
ficha tiene la misma estructura: propósito, actores, alcance implementado, reglas de
negocio, estados, pantallas y rutas, entidades y endpoints, integraciones y puntos a
validar.

### Identidad y configuración

| Módulo | Qué contiene |
|---|---|
| [Identidad, roles y accesos](funcionalidades/identidad-accesos/README.md) | Usuarios, membresías por institución, los 9 roles, legajo, permisos financieros, membresía de financiador |
| [Estructura organizativa](funcionalidades/estructura-organizativa/README.md) | Instituciones → áreas → subáreas, grupos de trabajo, boxes, camas, y el ámbito de un flujo |
| [Formularios](funcionalidades/formularios/README.md) | Biblioteca, constructor de campos, duplicar, reordenar, dónde se usa |
| [Flujos y motor de procesos](funcionalidades/flujos-motor/README.md) | Flujos versionados, editor visual, publicación, ensayo, motor de avance |

### Atención

| Módulo | Qué contiene |
|---|---|
| [Casos, guardia y filas](funcionalidades/casos-guardia-filas/README.md) | El caso como unidad trazable, tomar/llamar/derivar, filas por prioridad, pantalla pública |
| [Agenda y turnos](funcionalidades/agenda-turnos/README.md) | Agendas, disponibilidades, bloqueos, grilla, los 5 estados de turno |
| [Internación y camas](funcionalidades/internacion-camas/README.md) | Camas por sector, estadías, pases, egresos |
| [Registros clínicos, padrón e historia clínica](funcionalidades/registros-clinicos/README.md) | Padrón administrativo e historia clínica como dos accesos distintos; entradas firmadas con sello |
| [Red estatal y traslados](funcionalidades/red-traslados/README.md) | Redes, destinos, los 7 estados del traslado, quién puede cada acción |

### Recursos y dinero

| Módulo | Qué contiene |
|---|---|
| [Farmacia e insumos](funcionalidades/farmacia-insumos/README.md) | Stock por depósito y lote, movimientos, pedidos, alertas, trazabilidad |
| [Finanzas, costos y cobros](funcionalidades/finanzas-costos/README.md) | El documento más extenso: gastos, aprobaciones, reparto, costos por atención, pagos y cobros, reportes |
| [Financiadores, cobertura y copagos](funcionalidades/financiadores-cobertura/README.md) | Portal del financiador, planes y reglas, padrón, convenios, cupo compartido, copago, autorizaciones |

### Control y plataforma

| Módulo | Qué contiene |
|---|---|
| [Auditoría, consentimiento e integridad](funcionalidades/auditoria-consentimiento/README.md) | Accesos clínicos, consentimientos, firma y cadena de sellos |
| [Interoperabilidad FHIR](funcionalidades/interoperabilidad-fhir/README.md) | Fachada R4 de sólo lectura: Patient, Encounter, Organization, Coverage |
| [Operación y monitoreo](funcionalidades/operacion-monitoreo/README.md) | `/api/health/` y `/api/estado/`: qué contesta cada uno y por qué |
| [Tablero, supervisión y notificaciones](funcionalidades/tablero-notificaciones/README.md) | Mi trabajo, bandeja, tablero, supervisión, campana de avisos |

### Anexos de finanzas

| Documento | Qué contiene |
|---|---|
| [Reportería ejecutiva](funcionalidades/finanzas-costos/reporteria-ejecutiva.md) | Contrato de las cifras de la pestaña Reportes, API, permisos y verificación |
| [Guía Los Aromos](funcionalidades/finanzas-costos/guia-los-aromos.md) | Recorrido de 25–30 min por el escenario ficticio, con sus cifras |

---

## 2. Autoridad: quién puede hacer qué

| Documento | Qué contiene |
|---|---|
| [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md) | La especificación: 9 roles, 20 capacidades, 18 acciones financieras, los roles de financiador, matrices, interacción módulo por módulo y el mapa técnico de dónde vive cada permiso |
| [`roles/`](roles/README.md) | Lo mismo contado **rol por rol, pantalla por pantalla**, en lenguaje de producto. Diez fichas, con usuario de demo y qué ve cada uno en el menú |
| [`CONTEXT.md`](../CONTEXT.md) | Glosario de finanzas y cobertura: 40 términos con su definición y los sinónimos a evitar. Fija el vocabulario, no describe pantallas |

---

## 3. Entornos, demo y operación

[`docs/entornos/`](entornos/README.md) — escritos verificando cada botón contra la
aplicación corriendo el 17–18/09/2026.

| Documento | Qué contiene |
|---|---|
| [`entornos/README.md`](entornos/README.md) | Los dos entornos locales (vacío en 8081, demo en 8082): cómo levantarlos, cómo resembrar, las decisiones detrás y los límites conocidos |
| [`entornos/guia-demo-comercial.md`](entornos/guia-demo-comercial.md) | Guion de 45–50 min: operación, integridad del registro, dos hospitales, finanzas, financiadores. Con qué usuario entrar y qué conviene no mostrar |
| [`entornos/guia-demo-financiadores.md`](entornos/guia-demo-financiadores.md) | Recorrido de 20 min por el circuito de obras sociales: convenios, cobertura, padrón, aranceles, copago en la atención, saldos |
| [`entornos/guia-configuracion-desde-cero.md`](entornos/guia-configuracion-desde-cero.md) | Crear institución, áreas, usuarios, formularios, flujos, finanzas, permisos y financiadores, paso por paso |
| [`DEMO.md`](DEMO.md) | El **stack de desarrollo** en 8080: reset, usuarios por rol del escenario de guardia, qué hay cargado, qué no mostrar |

---

## 4. Referencia y estado

| Documento | Qué contiene |
|---|---|
| [`PARA-VENTAS.md`](PARA-VENTAS.md) | Para quien vende: el sistema en lenguaje de negocio, qué demo usar, la tabla de qué contestar y qué no prometer |
| [`PARA-DISENO.md`](PARA-DISENO.md) | Para quien diseña: las pantallas que existen, dónde vive la marca, cuál carpeta de capturas es la real y qué está sin resolver |
| [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) | Qué está construido, qué falta, qué decisiones están pendientes, y qué está validado y qué no |
| [`ESCENARIO-GUARDIA.md`](ESCENARIO-GUARDIA.md) | El escenario de referencia: guardia con triage Manchester, los 8 flujos publicados, el recorrido de prueba y cómo cargarlo |
| [`NOTIFICACIONES.md`](NOTIFICACIONES.md) | Los 4 eventos que disparan aviso, a quién y desde qué punto del motor; la API y la campana |
| [`FUNDACION-FRONTEND.md`](FUNDACION-FRONTEND.md) | Cómo está construido el frontend y las reglas al tocarlo: tokens, piezas, cómo migrar una pantalla, la suite e2e |
| [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) | Sólo un redirector, para enlaces viejos |

---

## 5. Diseño

[`diseño/`](../diseño/README.md) — el entregable de diseño de junio de 2026.

| Qué | Vigencia |
|---|---|
| `docs/01-manual-de-marca.md`, `docs/02-sistema-de-diseno.md`, `tokens.css`, `tokens.json` | **Vigentes.** Son la referencia de marca y el sistema de diseño |
| `docs/captures/`, `captures-app/`, `captures-manual/` | **Vigentes** como referencia visual de cada pantalla |
| `docs/03-arquitectura-y-roles.md`, `04-pantallas.md`, `05-modelo-de-datos.md`, `06-handoff-desarrollo.md`, `HANDOFF.md` | Del prototipo. Describen el alcance de junio, no el actual |
| `Salud - Procesos.dc.html` y los otros `.dc.html` | El prototipo interactivo original |

---

## 6. Histórico

Los planes de trabajo **en curso** viven en [`docs/plans/`](plans/); se mueven al
archivo cuando terminan.

[`docs/historico/`](historico/README.md) — planes, auditorías y documentos cerrados.
Explican **por qué** el sistema es como es. No describen su estado actual, y sus
fechas, puertos, cifras y pendientes son fotos del momento en que se escribieron.

Incluye el diseño completo del circuito de financiadores
([`historico/plans/financiadores/`](historico/plans/financiadores/README.md)), el
diseño lote por lote de finanzas, las cuatro auditorías de agosto, los planes de
desarrollo y de versiones, el detalle original de estructura y flujos, y el cierre de
la demo del 15/09.

---

## Qué se corrigió el 22/09/2026

Este índice nació de una revisión de toda la documentación contra el código. Lo que
se encontró y se corrigió:

- **Faltaba la ficha de financiadores y cobertura**, con el módulo implementado y en
  la demo. Se escribió.
- **La ficha de finanzas decía que obras sociales no estaba implementado**, no
  incluía los permisos de copago y describía como vigente el alcance financiero del
  administrador anterior al 18/09. Se reescribió entera.
- **`ROLES-Y-PERMISOS.md` documentaba 10 de las 20 capacidades** y no mencionaba
  finanzas ni financiadores en ninguna línea. Se completó, y se corrigieron filas de
  la matriz que daban al administrativo permisos que el código no le da.
- **`docs/roles/` cubría 5 de 9 roles** y afirmaba que el administrativo carga
  historia clínica, que es falso. Se reescribieron las diez fichas.
- **`ESTADO-DEL-PROYECTO.md` se contradecía consigo mismo** y contaba 6 apps de 13.
  Se reescribió contra el código.
- **El padrón de pacientes no estaba documentado**, ni la ruta `/legajo`, ni el
  recurso FHIR `Coverage`. Se agregaron.
- **Pendientes ya resueltos** seguían marcados como tales: la reactivación de esperas
  por tiempo la hace el servicio `tiempos` desde hace meses.
- **Siete documentos enlazaban `diseno/docs/`** cuando la carpeta es `diseño/docs/`.
- **Lo histórico se movió a `historico/`** para que dejara de mezclarse con el estado
  actual.
