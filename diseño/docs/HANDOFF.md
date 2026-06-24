# HANDOFF — Implementar Cauce tal cual

> Objetivo: que el código quede **idéntico** al prototipo `Cauce - Procesos.dc.html`. Este documento es para vos (dev) o para un agente de código. Léelo entero antes de escribir una línea.

---

## 0. Regla de oro del handoff

**No interpretes ni "mejores" el diseño. Replicalo.**

- La **fuente de verdad visual** son las capturas en `docs/captures/`. Cada pantalla implementada debe verse igual a su captura.
- La **fuente de verdad de estilos** es `docs/tokens.css` / `docs/tokens.json`. Usá esos valores exactos — nunca inventes un hex, un tamaño ni un nombre nuevo.
- La **fuente de verdad de comportamiento** es `docs/04-pantallas.md` + el prototipo abierto en el navegador.
- Si algo no está especificado, **mirá el prototipo**, no adivines. Ante la duda, preguntá.

> ⚠️ El prototipo está hecho en un runtime propio (`.dc.html`, `support.js`, `sc-for`, `DCLogic`). **No copies esa sintaxis.** Es solo para *mirar*. Reimplementá en el stack de abajo con HTML/CSS estándar.

---

## 1. Stack recomendado

- **React 18 + TypeScript + Vite**
- **Tailwind CSS** con el tema mapeado desde `tokens.json` (config abajo) — o CSS Modules + `tokens.css` si preferís CSS plano.
- **react-router** para las rutas.
- Lienzo del diseñador: **React Flow** (xyflow) es el atajo natural — nodos custom + edges con label. Si no, `<svg>` + divs absolutos como en el prototipo.
- Estado: Context/Zustand alcanza para el front; el back define la API (ver `docs/05-modelo-de-datos.md` y `docs/06-handoff-desarrollo.md`).

No es obligatorio este stack, pero **los tokens y el aspecto sí lo son**.

---

## 2. Setup de tokens (hacelo primero)

### Opción A — Tailwind
Pegá esto en `tailwind.config.js` (valores desde `tokens.json`):

```js
module.exports = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: { DEFAULT: '#3949C0', hover: '#2D3A9E', 50: '#ECEEFB', 100: '#C7CDF2', soft: '#F3F4FC' },
        ink: '#14161C',
        slate: { 900:'#1F2430', 700:'#344054', 600:'#475467', 500:'#667085', 400:'#98A0AE', 300:'#A4ABB8' },
        surface: '#FFFFFF', canvas: '#F4F5F7', subtle: '#FAFBFC',
        border: { DEFAULT:'#E7E9EE', 2:'#E2E5EA' },
        divider: { DEFAULT:'#EEF0F3', 2:'#F1F2F5' },
      },
      borderRadius: { input:'9px', card:'13px', lg:'16px', node:'14px', pill:'999px' },
      boxShadow: {
        card:'0 1px 3px rgba(16,24,40,.07)',
        raise:'0 6px 18px rgba(16,24,40,.10)',
        modal:'0 24px 60px rgba(16,24,40,.28)',
      },
      fontFamily: { sans:['Inter','system-ui','sans-serif'], mono:['JetBrains Mono','monospace'] },
    },
  },
};
```
Importá las fuentes en `index.html`:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
```
Estados semánticos y colores de nodo: importá `tokens.json` y mapealos en runtime (NO los pongas a ojo). Ej.: `const STATUS = tokens.status; const NODE = tokens.node;`

### Opción B — CSS plano
Importá `docs/tokens.css` una vez en el root y usá `var(--accent)` etc.

---

## 3. Las DOS experiencias visuales (lo que más se rompe en código)

El sistema tiene dos mundos que **no deben parecerse**. Es el error más común al implementar — respetalo a rajatabla:

| | **Diseño** (configurador) | **Ejecución** (administrativo/profesional) |
|---|---|---|
| Metáfora | Lienzo / diagrama (draw.io, n8n) | Software de gestión / ERP / expediente |
| Fondo | Canvas con **grilla de puntos** | Liso `--canvas`, **sin grilla** |
| Elementos | Nodos arrastrables + flechas + zoom/paneo + minimapa | Formularios, tablas, badges, **stepper** |
| Sensación | "Estoy dibujando un proceso" | "Estoy operando un sistema institucional" |

> Si la pantalla de ejecución parece un diagrama → está mal. Si el diseñador parece un formulario lineal → está mal.

---

## 4. Orden de construcción (incremental, verificable)

Implementá por fases y comparando contra la captura en cada paso:

1. **Shell**: sidebar (248px) + header (64px) + selector de rol + header de contexto de institución. → `captures/`
2. **Backoffice multi-institución**: directorio de instituciones, alta, ingreso, panel. (super admin / admin de institución)
3. **Estructura organizativa**: árbol Institución → Área → Sub-área + ficha con pestañas (Datos / Staff / Procesos / Sub-áreas). Regla: sub-área NO contiene sub-áreas.
4. **Flujos**: listado + **diseñador (lienzo)** con paleta de 10 nodos, panel de propiedades, validación viva (solapa Problemas), Probar y Reproducir.
5. **Constructor de formularios** con preview en vivo + campos vinculados a HC/legajo ciudadano + paso de Atención.
6. **Ejecución**: bandeja, filas de espera (operador), ejecución de caso (stepper + antecedentes HC + credencial), trazabilidad (timeline).
7. **Registros**: Historia clínica (lista→detalle con pestañas) + Legajo profesional.
8. **Administración**: usuarios y áreas (alcance institución).

Detalle de cada pantalla: `docs/04-pantallas.md`. Roles/permisos/navegación: `docs/03-arquitectura-y-roles.md`.

---

## 5. Checklist de fidelidad (revisá cada pantalla contra esto)

- [ ] Coincide con la captura de `docs/captures/` (layout, espaciados, jerarquía).
- [ ] Todos los colores salen de los tokens (cero hex hardcodeado fuera del tema).
- [ ] Tipografía: Inter en UI, JetBrains Mono en IDs/versiones/matrículas.
- [ ] Badges de estado con el color semántico correcto (ver mapa en tokens).
- [ ] Tablas con `grid` + columnas `minmax(px, fr)` (truncar con ellipsis, no colapsar).
- [ ] Botón primario `--accent`; deshabilitado cuando corresponde (ej. Publicar con errores).
- [ ] Hover/estados a 120ms.
- [ ] Modo diseño con grilla de puntos; modo ejecución sin grilla.
- [ ] El selector de rol cambia menú + mundo visual; todo se filtra por la institución del contexto.

---

## 6. Cómo mirar el prototipo mientras desarrollás

Abrí `Cauce - Procesos.dc.html` en un navegador (es autocontenido). Usá el selector de rol del header y "Ingresar" a una institución para recorrer todo. Cuando una interacción no esté clara en los docs, **reproducila ahí**.

---

## 7. Qué NO hacer

- ❌ Copiar la sintaxis `.dc.html` / `sc-for` / `DCLogic` al código real.
- ❌ Cambiar la paleta o "modernizar" colores/tipografía.
- ❌ Unificar los dos mundos visuales en un mismo look.
- ❌ Inventar pantallas, copys o datos que no estén en los docs/prototipo.
- ❌ Colapsar las dos vistas de Historia clínica (lista y detalle) en una sola.
