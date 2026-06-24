# Sistema de diseño — tokens y componentes

Especificación lista para traducir a CSS variables / tema de código. Valores tomados del prototipo `Cauce - Procesos.dc.html`.

## 1. Design tokens

```css
:root {
  /* Marca */
  --accent:        #3949C0;   /* indigo 600 */
  --accent-hover:  #2D3A9E;   /* indigo 700 */
  --accent-50:     #ECEEFB;
  --accent-100:    #C7CDF2;

  /* Texto */
  --ink:        #14161C;
  --slate-900:  #1F2430;
  --slate-700:  #344054;
  --slate-600:  #475467;
  --slate-500:  #667085;
  --slate-400:  #98A0AE;
  --slate-300:  #A4ABB8;

  /* Superficies y líneas */
  --surface:    #FFFFFF;
  --canvas:     #F4F5F7;
  --subtle:     #FAFBFC;
  --border:     #E7E9EE;
  --border-2:   #E2E5EA;
  --divider:    #EEF0F3;
  --divider-2:  #F1F2F5;

  /* Semánticos (fondo / texto) */
  --st-neutral-bg:#EEF0F3; --st-neutral-fg:#475467;
  --st-info-bg:   #E8EEFB; --st-info-fg:   #2D3A9E;
  --st-amber-bg:  #FBF0DD; --st-amber-fg:  #A96A12;
  --st-green-bg:  #E6F5EC; --st-green-fg:  #1B7A4E;
  --st-gray-bg:   #F0F1F3; --st-gray-fg:   #9098A6;
  --st-error-bg:  #FCEBEB; --st-error-fg:  #B42318;

  /* Tipografía */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;

  /* Radios */
  --r-input: 9px;  --r-card: 13px;  --r-lg: 16px;  --r-pill: 999px;

  /* Sombras */
  --sh-card:  0 1px 3px rgba(16,24,40,.07);
  --sh-raise: 0 6px 18px rgba(16,24,40,.1);
  --sh-modal: 0 24px 60px rgba(16,24,40,.28);

  /* Espaciado base: múltiplos de 4 (4/6/8/11/14/16/18/20/22/26/30) */
}
```

### Categorías de nodo (mapa)
Ver tabla completa en `01-manual-de-marca.md §5`. En código conviene un objeto:
```js
const NODE = {
  inicio:  { sol:'#1F8A5B', tint:'#E9F6EF', bd:'#BBE3CD', tx:'#16794B' },
  form:    { sol:'#3949C0', tint:'#ECEEFB', bd:'#C7CDF2', tx:'#2D3A9E' },
  decision:{ sol:'#C98A2B', tint:'#FBF2E0', bd:'#EBD7AC', tx:'#A96A12' },
  accion:  { sol:'#2B8FD6', tint:'#E6F1FB', bd:'#BBD9F2', tx:'#1C6BA8' },
  derivar: { sol:'#0E8893', tint:'#E3F4F4', bd:'#B2DFE0', tx:'#0B6A72' },
  espera:  { sol:'#16B1C9', tint:'#E2F6F9', bd:'#B6E4EC', tx:'#0C7C8E' },
  tiempo:  { sol:'#0E9E8E', tint:'#E2F5F1', bd:'#B3E2D9', tx:'#0A6E62' },
  atencion:{ sol:'#D14B8F', tint:'#FCEAF2', bd:'#F2C4DA', tx:'#A8316E' },
  estado:  { sol:'#5B7A99', tint:'#EEF2F6', bd:'#CDD8E2', tx:'#3F586F' },
  fin:     { sol:'#475467', tint:'#EFF1F4', bd:'#D0D5DD', tx:'#344054' },
};
```

## 2. Componentes

### Botones
- **Primario:** alto 38–42px, `background var(--accent)`, texto blanco 13.5px/600, radio 9–10px, hover `--accent-hover`.
- **Secundario:** fondo blanco, borde `--border-2`, texto `--slate-700`, hover fondo `--subtle`.
- **Terciario / icon button:** 30–32px cuadrado, radio 7px, color `--slate-500`, hover fondo `--divider`.
- **Dashed (agregar):** borde `1.5px dashed var(--accent-100)`, texto acento, hover `#F3F4FC`.
- Estado deshabilitado (ej. Publicar con errores): fondo `--divider`, texto `--slate-400`, `cursor:not-allowed`.

### Inputs
- Alto 38–40px, borde 1px `--border-2`, radio 9px, padding 0 12px, 13.5px.
- Foco: `border-color: var(--accent)`, fondo blanco.
- Select: misma caja + chevron 13px `--slate-400` absoluto a la derecha (`appearance:none`).
- Textarea: alto 70px, `resize:none`.
- Toggle: pista 38×22 radio pill; ON `--accent`, OFF `#D8DBE2`; perilla 18px blanca.

### Badge de estado (pill)
`display:inline-flex; gap:6px; padding:3px 10px; radio 999px; 12px/600` + punto de 6px del color `fg`. Fondo/texto según mapa semántico.

### Tarjeta
Fondo blanco, borde 1px `--border`, radio 13–14px, `--sh-card`. Hover (si clickable): `--sh-raise` + `translateY(-1px)` + borde `--accent-100`.

### Tabla
- Header: fondo `--subtle`, borde inferior `--divider`, micro-rótulo 11px/700 tracking 0.4–0.5px `--slate-400`.
- Filas: `display:grid` con columnas explícitas + `gap:14px`, padding 13–16px 20px, borde inferior `--divider-2`, hover `--subtle`.
- Usar `minmax(px, fr)` en columnas de texto largo para que truncen con `text-overflow:ellipsis` y no colapsen.

### Tabs / segmentos
- **Tabs (subrayado):** padding 11–12px, 13.5px/600, borde inferior 2px (`--accent` activo / transparente), color activo `--accent` / inactivo `--slate-400`.
- **Segmented control:** contenedor `--subtle`+borde, items radio 7–9px; activo fondo blanco + sombra 1px, inactivo texto `--slate-500`.

### Stepper (progreso de caso — solo ejecución)
Círculos 24–28px en fila con conectores de 2px. Estados: *done* (relleno acento + check), *current* (borde acento + halo `0 0 0 4px rgba(57,73,192,.13)`), *todo* (borde gris, texto `--slate-300`).

### Timeline (trazabilidad)
Grid `18px 1fr`; punto de 11–13px del color del evento con anillo `0 0 0 1.5px <color>66`; línea vertical 2px `#EAECEF` entre puntos. Cada evento: título 13px/600 + meta (autor · caso · fecha) 11.5px `--slate-300`.

### Nodo de lienzo (solo diseño)
Caja `display:flex; gap:11px; padding:13px 15px; radio 14px`, color según categoría (variante Suave por defecto: fondo `tint`, borde `bd`, texto `tx`). Ícono + kicker (10.5px/700) + título (13.5px/600) + resumen (10.5px). Punto de validez 15px en esquina sup-der (verde/ámbar/rojo). Seleccionado: `box-shadow:0 0 0 3px rgba(57,73,192,.32), 0 8px 20px rgba(16,24,40,.14)`.

**Variantes de estilo de nodo (tweak):** Suave (tint) · Contorno (blanco + borde de color) · Sólido (relleno de color + texto blanco).

### Lienzo (canvas)
Fondo `--subtle` con grilla de puntos: `radial-gradient(circle,#D9DDE5 1.1px,transparent 1.1px); background-size:24px 24px`. Conexiones en `<svg>` con `marker-end` (flecha). Etiqueta de rama = pill pequeña sobre la flecha. Minimapa abajo-derecha, zoom abajo-izquierda (sticky).

### Modal
Overlay `rgba(20,22,28,.5)`, panel blanco radio 16px, `--sh-modal`, header con título 16px/700 + subtítulo, cuerpo con campos, footer con Cancelar (secundario) + acción (primario). Cerrar al click en overlay; `stopPropagation` en el panel.

## 3. Layout / shell

- **Sidebar** 248px, fondo blanco, borde derecho. Grupos con micro-rótulo (TRABAJO / REGISTROS / DISEÑO / SISTEMA). Ítem activo: fondo `--accent` + texto blanco. Pie con avatar + rol.
- **Header** 64px: título de sección + buscador central (max 380px) + selector de rol (segmented) + avatar.
- **Header de contexto de institución** (super admin): "Estás en: Hospital Central" + "Volver al directorio". Para admin de institución es fijo (sin salida).
- **Área de contenido:** scroll propio; pantallas con padding 24–30px. Las pantallas tipo lienzo/operación ocupan alto completo.

## 4. Motion

- Transiciones de hover/estado: 120ms.
- Animación de nodo (pulse al enfocar un problema): `transform:scale(1.06)` 0.55s ×2.
- Token de "Reproducir" flujo: dot que viaja entre centros de nodo con `transition: left/top .65s cubic-bezier(.5,0,.2,1)` + anillo `dRing` pulsante.
- Demo/pitch: entradas `fadeUp`/`pop` 0.5–0.7s con `animation-delay` escalonado por escena.
