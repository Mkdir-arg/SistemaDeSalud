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
  avatarColors, badgeTone, color, font, nodeCat, radius, shadow, space, type,
} from "../src/theme.js";

const AQUI = dirname(fileURLToPath(import.meta.url));
const DESTINO = resolve(AQUI, "../src/styles/tokens.css");

/** `accentHover` → `accent-hover` · `slate900` → `slate-900` */
const kebab = (s) =>
  s.replace(/([a-z])([A-Z])/g, "$1-$2").replace(/([a-zA-Z])(\d)/g, "$1-$2").toLowerCase();

const px = (n) => (typeof n === "number" ? `${n}px` : n);

const bloque = (titulo, lineas) => `  /* ${titulo} */\n${lineas.join("\n")}\n`;

const partes = [];

// Colores de marca y neutros.
partes.push(bloque(
  "Marca y neutros",
  Object.entries(color).map(([k, v]) => `  --color-${kebab(k)}: ${v};`),
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
`;

writeFileSync(DESTINO, css, "utf8");

const vars = (css.match(/^\s+--/gm) || []).length;
console.log(`tokens.css generado desde theme.js — ${vars} variables.`);
