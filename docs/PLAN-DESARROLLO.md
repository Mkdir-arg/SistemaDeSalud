# Plan de desarrollo punta a punta — NODO Salud

> Hoja de ruta técnica para llevar Cauce/NODO de "sistema completo en su núcleo" a
> **producto**. Documento vivo. Creado: **2026-07-31**.

Complementa [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) (qué hay hecho),
[`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) (catálogo) y
[`PLAN-DE-VERSIONES.md`](PLAN-DE-VERSIONES.md) (la ruta demo-first, que queda
absorbida acá como un hito, ver §8).

## Decisiones que fijan este plan

| Decisión | Elegido |
|---|---|
| **Alcance** | Núcleo clínico completo **sin facturación** (se integra contra el sistema del cliente) |
| **Capa de estilos** | **Tailwind + shadcn/ui** sobre los tokens de marca actuales |
| **Dirección visual** | **Evolucionar** el sistema actual: marca y paleta se conservan, la capa de componentes se rehace |
| **Equipo** | Una persona (Mati) + Claude. Sin frentes paralelos. |

---

# 1. Diagnóstico del frontend

El backend está sano: 21 modelos, ~30 endpoints, 54 tests, motor de ejecución
probado. **El problema de escala está en el frontend**, y es medible:

| Síntoma | Medición | Consecuencia |
|---|---|---|
| Estilos inline | **~1.100 bloques `style={{}}`** en 29 archivos | No hay forma de reusar ni de cambiar nada globalmente |
| CSS real | **1 archivo, 77 líneas** | Sin capa de estilos: todo vive en el JSX |
| Responsive | **1 media query en toda la app** (`prefers-reduced-motion`) | **La app no funciona en tablet.** En un hospital eso es descalificante |
| Hover / focus | **23 `onMouseEnter` + 45 mutaciones directas del DOM** (`e.target.style.…`) | Los estados interactivos se simulan en JS porque los estilos inline no soportan pseudo-clases. Frágil y se pelea con React |
| Librería de componentes | **15 componentes** en 365 líneas | Faltan Tabs, Drawer, Toast, Tooltip, Dropdown, Combobox, DatePicker, Pagination, Skeleton, Breadcrumb, ConfirmDialog… Cada pantalla los reinventa inline |
| Tamaño de archivos | FlujoEditor **1.450** · MiTrabajo **851** · Areas **777** · Dashboard **697** · CasoDetalle **694** | Modales, tabs y sub-componentes viven dentro del archivo de la página |
| Capa de datos | Ninguna (`fetch` a mano) | Cada pantalla reimplementa loading, error, refetch y polling. Es la causa principal del volumen de código |
| **Paginación** | **0 de 17 pantallas la manejan** | Todas leen `d.results` y muestran los primeros **25** de la API, descartando el resto **en silencio**. Con 531 casos, la pantalla *Casos* muestra 25 y no hay forma de llegar a los otros 506. No es una carencia de UX: es pérdida de datos a la vista del usuario |
| Tests de frontend | **0** (Playwright instalado, sin specs) | Cada rework visual es una regresión potencial sin red |
| Dark mode / white-label | Imposible con estilos inline | Se pierde un argumento de venta: **cada gobierno quiere su identidad** |

**Lo que sí está bien y se conserva:** [`theme.js`](../frontend/src/theme.js) es un
buen sistema de tokens — escala tipográfica de 7 pasos, espaciado en grilla de 4,
radios, sombras, tonos semánticos de badge y las 10 categorías de nodo. **No se
tira: se promueve** a variables CSS y a la configuración de Tailwind. La marca no
cambia.

### La conclusión que ordena todo el plan

> **La fundación visual va antes que los módulos nuevos.**

Si turnos, camas y farmacia se construyen con estilos inline, la superficie a migrar
pasa de ~30 pantallas a ~50. Migrar después cuesta el doble y se hace con el
producto ya vendido. **Primero la fundación, después el dominio nuevo encima.**

---

# 2. Arquitectura objetivo

```
frontend/src/
  styles/
    tokens.css          # theme.js promovido a CSS custom properties (fuente única)
    themes/             # dark + overrides por institución (white-label)
  components/
    ui/                 # shadcn: Button, Tabs, Dialog, Drawer, Toast, Combobox…
    domain/             # propios: EstadoBadge, NodoChip, PrioridadTag, ColaItem,
                        # StepperCaso, TablaDensa, FiltroBarra, GraficoLinea
    layout/             # Shell, Sidebar, TopBar, PageHeader, Breadcrumbs, CommandPalette
  features/             # por dominio: casos/, flujos/, registros/, camas/, turnos/
    <feature>/
      api.ts            # hooks de TanStack Query (queries + mutations)
      components/       # componentes de esa feature
      routes/           # las páginas
  lib/                  # format, permisos, simular
```

Tres cambios estructurales:

1. **Tokens en un solo lugar.** `tokens.css` es la fuente; Tailwind lee de ahí; `theme.js`
   queda como puente re-exportando desde CSS durante la migración y se borra al final.
2. **Páginas por feature, no por rol.** Hoy `pages/diseno|ejecucion|registros|admin`
   mezcla criterios. Con features, agregar *camas* o *turnos* es una carpeta nueva.
3. **TanStack Query para todo lo que viene del servidor.** Es lo que hace que
   MiTrabajo baje de 851 líneas a ~250: se van el `useState` de loading/error, el
   `useEffect` de carga, el polling manual y la invalidación a mano. Además trae
   cache compartida, refetch en foco y estados optimistas — que es lo que hace que
   una app grande se sienta rápida.

---

# 3. Los siete pilares del rework visual

Lo que "mejorar el apartado visual **porque son aplicaciones grandes**" significa en
concreto. Cada pilar es criterio de aceptación de la Fase 0 y 1.

| # | Pilar | Qué se construye |
|---|---|---|
| 1 | **Navegación y orientación** | Sidebar colapsable con estado persistido · breadcrumbs · **command palette (⌘K)** para saltar a cualquier caso, paciente, flujo o pantalla · búsqueda global real (hoy el buscador de la TopBar es decorativo) · "recientes" |
| 2 | **Densidad y escala** | Tabla densa con paginación del servidor, orden y **columnas configurables** · filtros persistentes en la URL (compartir una vista filtrada) · alternar vista compacta/cómoda · virtualización donde haya miles de filas |
| 3 | **Estados completos** | Skeletons en vez de spinner de página · vacío · error con reintento · **sin permiso** · offline. Hoy solo existen `Spinner` y `EmptyState` |
| 4 | **Feedback y seguridad de la acción** | Toasts · confirmación para lo destructivo · **deshacer** donde se pueda · estados optimistas · bloqueo de doble envío |
| 5 | **Responsive de verdad** | Escritorio denso (puesto de trabajo) · **tablet** (enfermería y médico en sala — hoy no funciona) · TV (ya existe) · móvil acotado a consulta y notificaciones |
| 6 | **Accesibilidad** | Navegación completa por teclado, foco visible y atrapado en diálogos, ARIA, contraste AA. **Es ítem de pliego en licitación pública**, no un extra |
| 7 | **Identidad y modo** | Dark mode (turnos noche en guardia) y **white-label por institución**: logo y color de acento por cliente. Solo posible una vez fuera de los estilos inline |

---

# 4. Fases

Estimaciones en **semanas de una persona con Claude**. Son de construcción; no
incluyen reuniones comerciales, soporte ni viajes.

## Fase 0 — Fundación (4 semanas)

Nada de dominio nuevo. Es la inversión que hace baratas todas las fases siguientes.

| # | Entregable | Sem. |
|---|---|:--:|
| 0.1 | ✅ **HECHO** — **Generador de datos con volumen** (`seed_volumen`): ~40 pacientes y ~530 casos recorridos **con el motor real** y refechados sobre 90 días; reset completo en un comando (`--rehacer`, 40 s), reproducible por semilla. Iba primero **por una razón de diseño, no de demo**, y se confirmó al instante: apenas hubo volumen apareció el fallo de paginación de las 17 pantallas, invisible con los 3 casos del seed anterior | 0,5 |
| 0.2 | ✅ **HECHO** — **Tailwind 4 + tokens.** `tokens.css` se generaba desde `theme.js` mientras convivían las dos capas; al terminar la Fase 2A ese archivo se borró y `tokens.css` pasó a ser la única fuente (de ahí se deriva `escalas.js` con `npm run escalas`). 96 tokens en `@theme static`, con las escalas de Tailwind **reemplazadas** (`bg-red-500` no existe: la regla «no inventar colores» pasa a estar en la herramienta). Dark mode por clase y white-label por override de `--color-accent` en runtime. Verificado sin regresión visual | 1 |
| 0.3 | **Librería de componentes** — base shadcn (Tabs, Dialog, Drawer, Toast, Tooltip, Dropdown, Combobox, DatePicker, **tabla paginada**, Skeleton, ConfirmDialog) + los de dominio (EstadoBadge, PrioridadTag, NodoChip, StepperCaso, TablaDensa, FiltroBarra). **La tabla paginada es prioridad**: arregla de una vez el fallo de las 17 pantallas | 1,5 |
| 0.4 | ✅ **HECHO** — **Shell responsive**: cajón en móvil (hamburguesa, Escape, cierre al navegar), colapso en escritorio, TopBar que no desborda. Cierra el desborde horizontal en 390px. *Breadcrumbs y command palette quedan para la Fase 1* | 0,5 |
| 0.5 | ✅ **HECHO** — **TanStack Query + suite e2e en el repo**: 23 tests Playwright sobre los recorridos críticos, con el contraste AA **medido** en ambos temas. `npm run e2e` | 0,5 |

### Dos convenciones que fija la Fase 0.2

1. **`tokens.css` se genera, no se escribe.** Mientras convivan los estilos inline
   (que leen `theme.js`) y las clases, dos listas de colores mantenidas a mano
   divergen sin que nadie se entere. Al terminar la Fase 1 se borra el generador y
   `tokens.css` pasa a mano.
2. **Las variantes usan mapas de clases completas, nunca interpolación.** Tailwind
   escanea el código como texto: `` `bg-badge-${tono}-bg` `` no genera nada. Va un
   objeto con los strings enteros (ver `BADGE_TONO` en
   [`ui.jsx`](../frontend/src/components/ui.jsx)).

> **Preflight queda desactivado a propósito.** El reset global de Tailwind cambiaría
> las 30 pantallas de golpe, porque hoy los ~1.100 estilos inline asumen el reset
> propio. Se importan solo las capas `theme` y `utilities`; el preflight se adopta al
> cerrar la Fase 1, cuando ya no queden estilos inline.

**Terminado cuando:** existe una pantalla piloto (Fila de espera) migrada completa —
Tailwind, componentes nuevos, query, responsive, dark, estados y test — que sirve de
patrón a copiar para las otras 29.

> ## ✅ Fase 0 cerrada (2026-08-01)
>
> El criterio se cumple: **Fila de espera** está migrada entera y verificada, y
> **Casos** la acompaña con la tabla paginada. Las reglas de la fundación y el
> procedimiento para migrar cada pantalla están en
> [`FUNDACION-FRONTEND.md`](FUNDACION-FRONTEND.md).
>
> | | |
> |---|---|
> | Tests | 68 backend · 23 e2e |
> | Contraste AA | 0 fallos en claro y en oscuro (eran 16 y 29) |
> | Responsive | 1440 / 1024 / 390 sin desborde |
> | Datos de demo | ~530 casos, reset en un comando |
>
> **Queda fuera de la Fase 0, a propósito:** breadcrumbs y command palette (0.4),
> y los componentes Radix de shadcn —Tabs, Dialog, Drawer, Tooltip, Combobox,
> DatePicker, ConfirmDialog— que se agregan cuando la primera pantalla los
> necesite, en vez de construirlos por adelantado.

## Fase 1 — Migración de las pantallas existentes (5 semanas)

Por grupo, en orden de valor comercial. Cada pantalla se migra completa: estilos,
componentes, capa de datos, responsive, estados, accesibilidad y test.

| Grupo | Pantallas | Sem. |
|---|---|:--:|
| **A · Trabajo** | Mi trabajo, Bandeja, Fila, Detalle de caso, Puesto, Supervisión, Pantalla TV | 1,5 |
| **B · Tableros** | Dashboard, Inicio, Directorio, Notificaciones | 1 |
| **C · Diseño** | Flujos, Formularios, Mapa de flujos | 0,75 |
| **D · Registros y admin** | Historia clínica (lista y detalle), Legajo, Estructura, Usuarios, Login | 1 |

> El **editor de flujos no se migra acá**: tiene fase propia (Fase 2). Es el
> diferencial del producto, no una pantalla más.

**Terminado cuando:** las 29 pantallas están migradas, `theme.js` se borró, no queda
ningún `style={{}}` estructural y la app funciona en tablet.

---

## Fase 2 — El constructor de flujos — ✅ 2A + 2B HECHAS

> **Estado al 2026-08-02.** Los dos tramos comprometidos están terminados y en
> `main`. Lo que sigue de esta sección se conserva como registro de qué faltaba
> y por qué; al final está lo que quedó pendiente de verdad.

**Es el diferencial del producto.** Lo que se vende no es un módulo de guardia: es
que el proceso *se configura en días en vez de programarse en meses*. Todo lo demás
del plan es dominio que la competencia también tiene; esto no.

### 2.0 Lo que YA funciona (no se rehace)

El editor está mejor de lo que sugiere su tamaño. Tiene arrastre con Pointer Events
(mouse + touch + lápiz), snap a grilla de 20px, zoom 0.3–2 con *ajustar al contenido*,
**undo/redo con operaciones inversas** (Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y, pila de 60),
Delete/Backspace, autosave con indicador, toast con deshacer, handles de salida con
línea fantasma, conexiones interactivas, paneles colapsables para tablet, constructor
de reglas, validación con foco en el problema, **Probar** (simulación) y
**Reproducir** (animación). Las plantillas de arranque viven en
[`Flujos.jsx`](../frontend/src/pages/diseno/Flujos.jsx).

### 2.1 El problema arquitectónico que hay que resolver primero

[`lib/simular.js`](../frontend/src/lib/simular.js) tiene **83 líneas** y espeja a
[`motor.py`](../backend/apps/casos/motor.py), que tiene **823**. Son **dos
implementaciones de la misma semántica**, y ya divergen: el simulador evalúa
condiciones y atraviesa nodos, pero no sabe nada de grupos responsables, boxes,
prioridad de triage, estudios de ida y vuelta, notificaciones ni de la regla de firma
médica.

Consecuencia: **el botón "Probar" miente, y cada vez que el motor crezca va a mentir
más** — en silencio. Es la peor clase de bug: el configurador prueba el flujo, le da
bien, publica, y en producción hace otra cosa.

**Solución:** endpoint de *dry-run* del motor real (ejecución en transacción con
rollback). El cliente deja de simular y solo dibuja. Se borra `simular.js`.

### 2.2 Lo que falta — funcional

| Hueco | Detalle | Por qué importa |
|---|---|---|
| **Paralelismo no dibujable** | El fork/join **existe en el motor** (sub-casos bloqueantes con join real en `_retornar_al_origen`), pero está **cableado en las acciones** "solicitar estudio / interconsulta". No hay nodo de bifurcación en la paleta ni se ve en el diagrama | El configurador no puede modelar un proceso paralelo propio; depende de que se lo programemos |
| **Reglas de una sola condición** | `Conexion.condicion` = `{campo, operador, valor}`. Sin AND/OR | Una decisión clínica real casi siempre es compuesta (*edad > 65* **Y** *dolor torácico*) |
| **Operadores pobres** | `=`, `!=`, `>`, `<`, `contiene` | Faltan *entre*, *en lista*, *vacío / no vacío* y comparación de fechas |
| **Sin expresiones ni variables** | No se puede derivar edad de la fecha de nacimiento ni calcular un score | Todo score de triage o riesgo hay que cargarlo a mano |
| **Sin SLA ni temporizadores reales** | La espera por tiempo **no se reactiva sola** (no hay cron). No existe "si tarda más de X, avisar o escalar" | Es lo que un director de hospital pide primero |
| **Sin nodo de integración** | No hay nodo *llamar API externa* ni *enviar notificación* (SMS / email / WhatsApp) | **Es el nodo que haría verdadera la promesa comercial de "integración con sistemas existentes"** |
| **Sin manejo de excepciones** | No se modela "el paciente se retira", "el estudio falla" | Todo camino no feliz termina en cancelación manual |
| **Firma fija al rol médico** | El nodo no declara quién firma (Capa 4 pendiente de [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md)) | Bloquea flujos donde firma enfermería, trabajo social o un administrativo |
| **Versiones sin diff** | No se puede comparar v1 con v2, ni ver qué casos vivos quedaron en la versión anterior | Publicar una versión nueva se hace a ciegas |

### 2.3 Lo que falta — visual y de operación del lienzo

Verificado sobre el archivo: **sin minimapa** · **sin zoom con la rueda** (solo
botones — doloroso en un flujo de 40 nodos) · **sin buscar nodo en el lienzo** ·
**sin multi-selección** (ni shift-clic ni marquesina) · **sin copiar/pegar/duplicar** ·
**sin auto-layout** · sin guías de alineación entre nodos (solo snap a grilla) · sin
carriles por área o grupo · sin comentarios en el lienzo · atajos de teclado mínimos
(solo deshacer, rehacer y borrar).

### 2.4 Plan por tramos

| Tramo | Contenido | Sem. |
|---|---|:--:|
| **2A · Imprescindible** ✅ | Dry-run server-side (borra `simular.js`) · reglas compuestas AND/OR + operadores nuevos · editor migrado a la fundación · minimapa, zoom con rueda, buscar nodo, multi-selección, copiar/pegar | 4 |
| **2B · Diferencial** ✅ | **Nodo de integración** (llamada a API externa) y **nodo de notificación** · SLA y temporizadores + escalamiento · auto-layout · firma configurable por nodo | 4 |
| **2C · Avanzado** *(opcional, diferible)* | Fork/join dibujable en el diagrama (toca `Caso.nodo_actual` → modelo de tokens: es el refactor más profundo del plan) · expresiones y variables calculadas · diff entre versiones y migración de casos vivos · excepciones · comentarios en el lienzo | 4 |

**2A + 2B están hechas.** 2C sigue fuera del cronograma y se decide cuando haya un
cliente que lo pida.

> **React Flow — decidido: se construyó a mano.** El editor ya tenía resuelto lo
> difícil (arrastre con Pointer Events, snap, ajuste al contenido, undo/redo con
> operaciones inversas, autosave, conexiones con línea fantasma). Migrar obligaba a
> reintegrar todo eso sobre otra abstracción, en la pantalla más importante del
> producto, mientras que lo que faltaba era aditivo. Es reversible: si más adelante
> hace falta auto-layout más sofisticado, `dagre`/`elkjs` resuelven eso sin cambiar
> de canvas.

> **Lo que quedó pendiente de 2B.** Los *carriles por área/grupo* no se hicieron:
> son presentación pura y, con el auto-layout y los colores por categoría, el
> diagrama ya se lee. Se retoma si un cliente con flujos muy grandes lo pide.

> **Sinergia con la Fase 8.** El nodo de integración de 2B es la cañería genérica de
> llamada a sistemas externos. HL7/FHIR en la Fase 8 se monta encima, no se duplica.

---

> ## ✅ Fase 2 (2A + 2B) cerrada — 2026-08-02
>
> **Lo que cambió para el producto.** El botón «Probar» dejó de mentir: corre el
> motor real en una transacción que se deshace, así que lo que se ve al diseñar
> es lo que va a pasar con un paciente. Las reglas pasaron de una condición a
> compuestas anidables con 13 operadores. Aparecieron el nodo de integración
> —con lista blanca de destinos, porque una URL configurable que llama el
> servidor es un SSRF con formulario— y el de notificación. El SLA existe, y las
> esperas por tiempo se reactivan solas: antes un caso que entraba a
> «Observación 6 horas» no volvía nunca. La firma dejó de estar clavada al rol
> médico.
>
> **Lo que cambió para quien diseña.** Zoom con rueda anclado al cursor, Ctrl+F,
> multi-selección con marquesina, copiar/pegar con las conexiones internas,
> minimapa y auto-layout reversible. El editor entró al sistema de diseño (tema
> oscuro incluido) y pasó de cero a 9 tests e2e.
>
> **Lo que se decidió.** No se adoptó React Flow: el editor ya tenía resuelto lo
> difícil y migrar era rehacer trabajo probado en la pantalla más importante.
>
> **Lo que NO se hizo.** Carriles por área/grupo (presentación pura; el diagrama
> ya se lee con el auto-layout y los colores por categoría) y todo el tramo 2C.
>
> **Bugs que sólo aparecieron al construir esto:** el cálculo de profundidad no
> convergía en flujos con ciclos y estiraba los diagramas cuatro mil píxeles;
> `>` sobre fechas devolvía siempre False en silencio; `contiene` era sensible a
> las tildes, así que una regla de triage mandaba al paciente por el circuito
> equivocado; y «1 mes» se interpretaba como 1 minuto.

---

## Fase 3 — Cierre del núcleo actual (3 semanas)

Lo que falta para que lo que ya existe sea un producto y no un prototipo avanzado.
(La reactivación automática de esperas por tiempo se resuelve en la Fase 2B, junto
con los SLA.)

- Exportación CSV/PDF de tableros, casos y colas.
- **OpenAPI/Swagger** de la API (es también el primer paso del trabajo de integración).
- Permisos de escritura auditados extremo a extremo por rol.
- Operación de fila completa: devolver a la cola, marcar ausente, reordenar.
- Suite de Playwright sobre los recorridos críticos.

## Fase 4 — Camas e internación (3 semanas)

Modelo `Cama` (sector, estado, ocupación ligada al caso) · enganche con el nodo
*Asignar cama* del flujo de Internación · tablero de ocupación por sector · pases
entre sectores · % de ocupación en los tableros. Es la pieza que más se reutiliza:
aparece en Guardia, Clínica y Red.

## Fase 5 — Turnos y agenda (5 semanas)

**El módulo faltante más grande del Paquete 2.** Hoy no existe nada: el `turno`
actual es un número de ticket de fila. Incluye agenda por profesional y por recurso,
plantillas de disponibilidad, reserva, sobreturnos, cancelación, ausentismo,
recordatorios y el enganche con el motor (un turno agenda un caso).

## Fase 6 — Farmacia e insumos (5 semanas)

Catálogo, stock por depósito, movimientos, consumo imputado al caso, pedidos,
alertas de faltante y vencimiento, trazabilidad de lote.

## Fase 7 — Red multicentro (6 semanas)

- **Derivación entre establecimientos** — hoy la derivación es siempre
  [intra-institución](../backend/apps/casos/motor.py#L372). Toca el motor, el modelo de
  permisos y el scope. Es el cambio de arquitectura más profundo del plan.
- Tablero multicentro consolidado e indicadores comparados.
- Disponibilidad de camas en red.
- Traslados (solicitud, móvil, seguimiento).
- Alertas por saturación con notificación real.
- Mapa sanitario georreferenciado.

## Fase 8 — Producción e integración (5 semanas)

- **Integración**: conectores HL7/FHIR según el cliente. Es el hueco más grave entre
  lo que promete el mensaje comercial y lo que hay construido.
- **Normativa**: Ley 26.529 (historia clínica) y 25.326 (datos personales), auditoría
  de accesos, retención, evaluación de firma digital.
- **Infraestructura**: despliegue real, backups, monitoreo, performance con volumen.
- Migración de datos y capacitación.

---

# 5. Cronograma

| Fase | Semanas | Acumulado |
|---|:--:|:--:|
| 0 · Fundación ✅ | 4 | 4 |
| 1 · Migración de pantallas ✅ | 4,5 | 8,5 |
| **2 · Constructor de flujos** (2A+2B) ✅ | **8** | **16,5** |
| 3 · Cierre del núcleo | 3 | 19,5 |
| 4 · Camas | 3 | 22,5 |
| 5 · Turnos | 5 | 27,5 |
| 6 · Farmacia | 5 | 32,5 |
| 7 · Red multicentro | 6 | 38,5 |
| 8 · Producción e integración | 5 | 43,5 |

**≈ 43 semanas ≈ 10 meses de una persona a tiempo completo.** Las tres primeras
fases están hechas: quedan ≈ 27 semanas.

**≈ 43 semanas ≈ 10 meses de una persona a tiempo completo.** (Con el tramo 2C
opcional, 47 semanas.)

Ese es el número honesto y conviene decirlo en voz alta antes de comprometer fechas
comerciales. Cuatro formas de bajarlo, en orden de efectividad:

1. **Sumar una segunda persona en la Fase 1.** La migración de pantallas es el trabajo
   más paralelizable de todo el plan (grupos independientes, patrón ya definido en la
   Fase 0). Dos personas la hacen en 2,5 semanas en vez de 4,5.
2. **Diferir Farmacia (Fase 6).** Rara vez es el motivo de compra y son 5 semanas.
3. **Diferir Turnos (Fase 5) si el primer cliente es un ministerio.** Un ministerio
   compra red y guardia; los turnos los pide una clínica privada.
4. **Adoptar React Flow** en la Fase 2 (spike de 2 días): baja 2A de 4 a 3 semanas.

Con esos recortes el núcleo vendible **con el diferencial intacto** queda en
**~26 semanas (6 meses)**.

> **Lo que NO se recorta: la Fase 2.** Es tentadora porque son 8 semanas seguidas sin
> un módulo nuevo que mostrar, pero es lo único del plan que la competencia no tiene.
> Recortar ahí es quedarse con un HIS mediano compitiendo contra HIS grandes.

---

# 6. Hitos con valor comercial

El plan no obliga a esperar 8 meses para mostrar algo. Hay tres puntos de corte donde
el producto es demostrable:

| Hito | Semana | Qué se puede hacer |
|---|:--:|---|
| **H1 · Demo con datos** | 4 | Fin de Fase 0. La app ya se ve con volumen real y con el shell nuevo. Suficiente para demos de guardia |
| **H2 · Producto visual completo** | 8,5 | Fin de Fase 1. Las 29 pantallas migradas, responsive, dark mode. **Momento de rehacer las capturas y la presentación comercial** |
| **H3 · El diferencial demostrable** | 16,5 | Fin de Fase 2. El constructor con reglas compuestas, simulación fiel, SLA y nodo de integración. **Es el hito que sostiene el discurso de "se configura, no se programa"** — y el que habilita responder "sí" a la pregunta por integración |
| **H4 · Núcleo vendible** | 22,5 | Fases 3 y 4. Cierre operativo + camas: se puede firmar un piloto pago de clínica sin prometer nada que no exista |

---

# 7. Riesgos

| Riesgo | Mitigación |
|---|---|
| **Migrar 30 pantallas sin tests es una ruleta** | Los Playwright de los recorridos críticos se escriben en la Fase 0.5, **antes** de tocar nada |
| **El editor de flujos (1.450 líneas) se rompe al migrarlo** | Tiene fase propia (Fase 2) con spike de React Flow al arrancar, y los Playwright de la Fase 0.5 cubren diseñar → validar → publicar → ejecutar antes de tocarlo |
| **El "Probar" del diseñador miente** | Es el riesgo más silencioso del sistema: `simular.js` (83 líneas) espeja `motor.py` (823) y ya divergen. Se cierra en 2A con dry-run server-side. **Hasta entonces, no usar "Probar" como argumento de venta** |
| **La Fase 2 se percibe como 8 semanas sin entregable** | Se ordena para que 2A cierre con el editor migrado y visible (semana 12,5) y 2B con el nodo de integración, que es argumento comercial directo |
| **La Fase 0 se estira y se posterga el dominio** | Fase 0 tiene entregable verificable (pantalla piloto completa). Si a la semana 4 no está, se corta alcance de la librería, no se sigue |
| **Aparece una venta a mitad del rework** | H1 (semana 4) y H2 (semana 9) son estados demostrables. Entre medio la app queda con pantallas mezcladas: **evitar demos entre las semanas 5 y 8** |
| **Las 17 capturas dejan de coincidir con el producto** | Se rehacen en H2. Hasta entonces, `diseño/docs/HANDOFF.md` deja de ser ley: la regla "replicar, no mejorar" se levanta explícitamente |
| **Facturación vuelve a entrar por pedido de un cliente** | Está fuera de alcance por decisión. La respuesta acordada es integración contra el facturador existente |

---

# 8. Relación con el plan comercial

[`PLAN-DE-VERSIONES.md`](PLAN-DE-VERSIONES.md) planteaba una ruta *demo-first* de 4-6
semanas. **Este plan la absorbe y la reemplaza**, con dos diferencias:

- El generador de datos (que allí era el primer entregable de v1.0) sigue siendo lo
  primero, pero ahora por una razón de ingeniería además de comercial.
- El hito de demo se corre de la semana 2 a la **semana 4 (H1)**, y a cambio se llega
  con el shell nuevo, responsive y la librería de componentes — no con lo actual
  apenas pulido.

Lo que sí sigue vigente de ese documento: los **guiones de demo** por perfil (Ministro
de Salud y Dueño de clínica) y la **tabla de respuestas** para lo que no está
construido. Conviene escribirlos en H2, cuando el producto ya se vea como se va a ver.
