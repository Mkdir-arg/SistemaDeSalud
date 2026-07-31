/**
 * Genera `src/styles/tokens.css` a partir de `src/theme.js`.
 *
 * Por qué generado y no escrito a mano: durante la migración a Tailwind conviven
 * las dos capas —los ~1.100 estilos inline siguen leyendo `theme.js` mientras las
 * pantallas migradas usan clases— y dos listas de colores mantenidas a mano
 * divergen sin que nadie se entere. Con esto hay **una sola fuente**: `theme.js`.
 *
 * Cuando termine la Fase 1 y `theme.js` desaparezca, este script se borra y
 * `tokens.css` pasa a mantenerse a mano.
 *
 *     npm run tokens
 */
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  avatarColors, badgeTone, badgeToneOscuro, color, font, nodeCat, oscuro, radius,
  semantico, shadow, space, type,
} from "../src/theme.js";

const AQUI = dirname(fileURLToPath(import.meta.url));
const DESTINO = resolve(AQUI, "../src/styles/tokens.css");
// Segunda salida: los nombres de las escalas, para que tailwind-merge sepa que
// `rounded-pill` es un radio y `text-danger` un color. Sin esto, cn() no puede
// deduplicar clases en conflicto de las escalas propias y gana la que no toca.
const DESTINO_JS = resolve(AQUI, "../src/styles/escalas.js");

/** `accentHover` → `accent-hover` · `slate900` → `slate-900` */
const kebab = (s) =>
  s.replace(/([a-z])([A-Z])/g, "$1-$2").replace(/([a-zA-Z])(\d)/g, "$1-$2").toLowerCase();

const px = (n) => (typeof n === "number" ? `${n}px` : n);

const bloque = (titulo, lineas) => `  /* ${titulo} */\n${lineas.join("\n")}\n`;

const partes = [];

// Colores de marca y neutros (capa literal).
partes.push(bloque(
  "Marca y neutros (literales)",
  Object.entries(color).map(([k, v]) => `  --color-${kebab(k)}: ${v};`),
));

// Capa semántica: la que usan los componentes migrados y la única que cambia
// entre temas.
partes.push(bloque(
  "Semánticos (los usa el código migrado; el tema oscuro solo redefine estos)",
  Object.entries(semantico).map(([k, v]) => `  --color-${kebab(k)}: ${v};`),
));

// Tonos semánticos de badge (estado de caso, de versión, etc.).
partes.push(bloque(
  "Badges por tono semántico",
  Object.entries(badgeTone).flatMap(([tono, { bg, fg }]) => [
    `  --color-badge-${tono}-bg: ${bg};`,
    `  --color-badge-${tono}-fg: ${fg};`,
  ]),
));

// Las 10 categorías de nodo del diseñador de flujos.
partes.push(bloque(
  "Categorías de nodo (diseñador de flujos)",
  Object.entries(nodeCat).flatMap(([cat, v]) => [
    `  --color-nodo-${cat}-sol: ${v.sol};`,
    `  --color-nodo-${cat}-tint: ${v.tint};`,
    `  --color-nodo-${cat}-bd: ${v.bd};`,
  ]),
));

partes.push(bloque(
  "Avatares (paleta rotativa)",
  avatarColors.map((c, i) => `  --color-avatar-${i + 1}: ${c};`),
));

partes.push(bloque(
  "Tipografía",
  Object.entries(font).map(([k, v]) => `  --font-${kebab(k)}: ${v};`),
));

partes.push(bloque(
  "Escala tipográfica (7 pasos)",
  Object.entries(type).map(([k, v]) => `  --text-${kebab(k)}: ${px(v)};`),
));

partes.push(bloque(
  "Espaciado nombrado (la escala numérica de Tailwind sigue disponible)",
  Object.entries(space).map(([k, v]) => `  --spacing-${kebab(k)}: ${px(v)};`),
));

partes.push(bloque(
  "Radios",
  Object.entries(radius).map(([k, v]) => `  --radius-${kebab(k)}: ${px(v)};`),
));

partes.push(bloque(
  "Elevación",
  Object.entries(shadow).map(([k, v]) => `  --shadow-${kebab(k)}: ${v};`),
));

const css = `/*
 * ARCHIVO GENERADO — no editar a mano.
 * Fuente: src/theme.js · Regenerar con: npm run tokens
 *
 * Los tokens se declaran con @theme, así que Tailwind los publica como variables
 * CSS en :root **y** genera las utilidades correspondientes (bg-accent,
 * text-slate-600, rounded-lg, shadow-card…).
 *
 * Es \`@theme static\` y no \`@theme\` a propósito: por defecto Tailwind hace
 * tree-shaking y solo emite las variables que alguna utilidad usa. Mientras
 * convivan los estilos inline —que leen los tokens desde JS— y el CSS a mano, la
 * capa de tokens tiene que estar COMPLETA en :root, si no hay tokens que existen
 * en teoría y no en el navegador. Son ~96 variables: el costo es despreciable.
 *
 * Las escalas propias se declaran con \`*: initial\` antes de definirlas: eso borra
 * las de Tailwind y deja SOLO las del sistema de diseño. Es deliberado — la regla
 * del manual es «no inventar colores» y así \`bg-red-500\` directamente no existe.
 */
@theme static {
  /* Reemplazo total de las escalas por defecto de Tailwind. */
  --color-*: initial;
  --font-*: initial;
  --text-*: initial;
  --radius-*: initial;
  --shadow-*: initial;

  /* Palabras clave de color que no son del sistema pero hacen falta siempre. */
  --color-transparent: transparent;
  --color-current: currentColor;

${partes.join("\n")}}

/*
 * Tema oscuro. Se activa con la clase «dark» en el elemento html.
 *
 * Redefine SOLO la capa semántica, la marca y los badges: las utilidades leen
 * var(--color-…), así que cambiar la variable alcanza y no hace falta una
 * segunda clase por componente. Las escalas literales (slate-600, canvas…) no se
 * tocan: las siguen usando los estilos inline sin migrar, que no tienen modo
 * oscuro — adoptarlo es parte de migrar cada pantalla.
 *
 * Las categorías de nodo del diseñador tampoco se redefinen todavía: ese lienzo
 * se rehace entero en la Fase 2 y elegir ahora 30 colores que van a cambiar es
 * trabajo tirado.
 */
.dark {
${Object.entries(oscuro).map(([k, v]) => `  --color-${kebab(k)}: ${v};`).join("\n")}
${Object.entries(badgeToneOscuro)
  .flatMap(([t, { bg, fg }]) => [`  --color-badge-${t}-bg: ${bg};`, `  --color-badge-${t}-fg: ${fg};`])
  .join("\n")}

  /* Sombras: en oscuro una sombra negra no se ve. La elevación se percibe por
     el borde y por superficies más claras, así que se atenúan mucho. */
  --shadow-card: 0 1px 2px rgba(0, 0, 0, .4);
  --shadow-float: 0 8px 20px rgba(0, 0, 0, .5);
  --shadow-dropdown: 0 12px 32px rgba(0, 0, 0, .55);
  --shadow-modal: 0 18px 50px rgba(0, 0, 0, .65);
}

/* Interfaz nativa (scrollbars, controles de formulario) acorde al tema. */
.dark {
  color-scheme: dark;
}
`;

writeFileSync(DESTINO, css, "utf8");

// --------------------------------------------------------------------------- //
// Escalas para tailwind-merge
// --------------------------------------------------------------------------- //
const colores = [
  ...Object.keys(color).map(kebab),
  ...Object.keys(semantico).map(kebab),
  ...Object.keys(badgeTone).flatMap((t) => [`badge-${t}-bg`, `badge-${t}-fg`]),
  ...Object.keys(nodeCat).flatMap((c) => [`nodo-${c}-sol`, `nodo-${c}-tint`, `nodo-${c}-bd`]),
  ...avatarColors.map((_, i) => `avatar-${i + 1}`),
];

const lista = (xs) => `[${xs.map((x) => `"${x}"`).join(", ")}]`;

const js = `/*
 * ARCHIVO GENERADO — no editar a mano.
 * Fuente: src/theme.js · Regenerar con: npm run tokens
 *
 * Nombres de las escalas del sistema de diseño, para configurar tailwind-merge.
 * Sin esto no sabe que \`rounded-pill\` pertenece al grupo del radio ni que
 * \`text-danger\` es un color, y al combinar clases deja las dos en conflicto en
 * vez de quedarse con la última — que es justo lo que rompe los overrides por
 * className en los componentes.
 */
export const escalas = {
  color: ${lista(colores)},
  text: ${lista(Object.keys(type).map(kebab))},
  spacing: ${lista(Object.keys(space).map(kebab))},
  radius: ${lista(Object.keys(radius).map(kebab))},
  shadow: ${lista(Object.keys(shadow).map(kebab))},
  font: ${lista(Object.keys(font).map(kebab))},
};
`;

writeFileSync(DESTINO_JS, js, "utf8");

const vars = (css.match(/^\s+--/gm) || []).length;
console.log(`tokens.css   — ${vars} variables desde theme.js`);
console.log(`escalas.js   — ${colores.length} colores para tailwind-merge`);
