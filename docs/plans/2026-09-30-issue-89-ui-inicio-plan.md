# Issue #89 — Sidebar, listados e Inicio institucional

Origen: #86. Relacionados: #67 (design system), #58 (auditoría UX/UI).

## Decisiones confirmadas por el usuario

1. **Fuente de datos del Inicio enriquecido (30/09/2026):** reusar sólo datos existentes —métricas actuales de Inicio y el endpoint `/instituciones/{id}/tablero/`—, sin cambios de backend ni indicadores nuevos. Aplica a quien tenga la capacidad `supervision` (admin institucional, superadmin); el resto conserva el Inicio actual. Período: 7 días (recomendación del agente, no objetada).

2. **«Requiere atención» en Inicio (30/09/2026):** una tarjeta con dos grupos rotulados: «Configuración» (pasos de puesta en marcha pendientes, como hoy) y «Operación» (alertas que ya calcula el tablero: urgentes > 0, espera promedio ≥ 30 min, turnos sin registrar > 0). «Operación» sólo con capacidad `supervision`. El (?) explica ambos grupos y sus reglas. Términos en `CONTEXT.md`.

3. **Bloques del Inicio con `supervision` (30/09/2026):** versión compacta del tablero, 7 días: encabezado actual; fila de KPIs (casos activos con urgentes/en cola, espera promedio, turnos del período con ausentes/sin registrar, casos cerrados, ocupación de camas sólo si hay camas); gráfico de ingresos junto a «Requiere atención»; «Carga por área» (top 5); accesos rápidos y enlace «Ver tablero completo». Dona, comparativa y top de demoras quedan sólo en `/dashboard`.

4. **Regla de botones (30/09/2026):** a lo sumo una acción con gradiente (`primary`) por pantalla o modal: la acción principal («Nuevo caso», confirmar en modal, «Continuar» en la puesta en marcha). Acciones por fila y de barra (filtrar, exportar, ver, editar) usan `secondary`. Excepción: «Tomar» en Bandeja y «Tomar y abrir» en Mi trabajo conservan gradiente (pedido de #67/Figma).

5. **Alcance de la regla de botones (30/09/2026):** todas las páginas de la app institucional y sus modales. Excluye portal de financiadores (#92), app de pacientes (#66) y landing (#88).

6. **Avatares (30/09/2026):** fondo sólido `accent-fuerte` con iniciales blancas en todos los avatares de la app institucional (pacientes, usuarios, personal, sidebar), cambiando sólo el componente `Avatar`. App de pacientes (#66) fuera si usa su propio avatar.

7. **Referencia de íconos (30/09/2026):** no hay sidebar de Figma disponible en la sesión. El agente propone una tabla sin repetidos en estilo lucide; el usuario la aprueba antes de implementar. La verificación contra Figma queda como criterio **sin cubrir**.

8. **Tabla de íconos del sidebar (30/09/2026, aprobada):**

| Destino | Ícono |
|---|---|
| Tablero | activity |
| Finanzas y cobros | wallet |
| Coberturas y copagos | shieldCheck (nuevo) |
| Red de establecimientos | mapPin (nuevo) |
| Inicio | home |
| Bandeja | inbox |
| Turnos | calendar |
| Internación | bed |
| Farmacia e insumos | pill (nuevo) |
| Padrón de pacientes | idCard |
| Historia clínica | clipboard |
| Casos | fileText |
| Supervisión | eye |
| Estructura organizativa | network (nuevo) |
| Usuarios y permisos | users |
| Flujos | workflow |
| Mapa de flujos | map |
| Formularios | form |
| Legajo profesional | stethoscope (nuevo) |
| Registro de accesos (institución y plataforma) | enter |
| Portal de financiadores / Financiadores (plataforma) | handshake (nuevo) |
| Instituciones (plataforma) | building |
| Usuarios (plataforma) | users |

El menú interno del portal de financiadores queda fuera (#92).

## Supuestos del agente (reversibles, no preguntados)

- Institución «en configuración»: Inicio conserva la guía de puesta en marcha primero, como hoy.
- Animación del sidebar: plegado/desplegado del ancho y de los grupos en ~200 ms ease-out; sin animación con `prefers-reduced-motion`. Los ítems de un grupo cerrado no reciben foco de teclado.

## Plan de implementación

1. **Sidebar** (`components/Shell.jsx`, `components/icons.jsx`): transición de ancho 200 ms; grupos con transición de altura (grid-rows 0fr→1fr) manteniendo los ítems montados pero `inert` y `aria-hidden` al cerrar; `motion-reduce:transition-none`; íconos según tabla y 6 trazos lucide nuevos.
2. **Botones**: revisar los `<Button>` sin variante en páginas de la app institucional y sus modales; `variant="secondary"` para acciones por fila y de barra; primario sólo en la acción principal. Excepción «Tomar»/«Tomar y abrir».
3. **Avatar** (`components/ui.jsx`): fondo `accent-fuerte` + iniciales `text-sobre-accent`; conservar la firma (`i` queda sin efecto).
4. **Inicio** (`pages/Inicio.jsx`): con `supervision`, consultar `/instituciones/{id}/tablero/?desde&hasta` (7 días, fecha local) y mostrar bloques de la decisión 3. Extraer de `pages/Dashboard.jsx` a `components/tablero.jsx` lo reutilizado (`KpiDireccion`, `BarrasIngresos`, `ResumenDireccion`, helpers de fecha y reglas de alertas) para que Tablero e Inicio compartan reglas; Dashboard sin cambio visible.
5. **Requiere atención**: grupos «Configuración» y «Operación», estado vacío por grupo, botón (?) accesible (popover/tooltip con foco de teclado y Escape) que explique ambos grupos y reglas.

## Riesgos

- Extraer componentes de Dashboard puede cambiar su render: se valida Tablero sin diferencias visibles.
- Cambiar 100+ botones puede degradar a secundario una acción principal de un modal: revisión archivo por archivo del diff.
- Grupos del sidebar con ítems montados: foco de teclado en ítems ocultos si falta `inert`.
- Inicio hace una consulta extra para supervisores (tablero ya es consultado por /dashboard; mismo costo de backend).
- Íconos no verificados contra Figma (criterio sin cubrir, decisión 7).

## Validación

- `npm run build` y `npm run auditar` en `frontend/`.
- E2E con API interceptada relevantes, si no requieren stack: `tablero.spec.js`, `shell.spec.js`, `ui.spec.js` (revisar su config antes de correr).
- Verificación manual/capturas con API interceptada: Inicio con y sin `supervision`, estados vacíos, tema claro/oscuro, sidebar plegado en escritorio y cajón móvil, foco de teclado.
- Sin Railway, bases compartidas, datos reales ni credenciales.

## Resultado de la implementación (30/09/2026)

- Implementó Codex CLI; revisó Claude. En la revisión se revirtió el cambio de «Llamar al siguiente» en `Fila.jsx`, que el código ya documentaba como la acción principal de la pantalla, y se unificó el grosor de trazo de los íconos nuevos (1,8 como el resto).
- Corrió: `npm run build` y `npm run auditar` (273 clases, ninguna huérfana).
- No quedó validado: la suite de Playwright con API interceptada. Una corrida se cortó por falta de memoria de la máquina y mostró fallos en specs del portal de financiadores sin causa confirmada (regresión del sidebar o entorno). `inicio-ui.spec.js` se corrigió (interceptaba `/src/api/client.js`) y no volvió a correrse.
- Sin verificar: íconos contra Figma (decisión 7), revisión visual en tema claro/oscuro y móvil.
