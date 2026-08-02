/**
 * Genera `src/styles/escalas.js` a partir de `src/styles/tokens.css`.
 *
 * `tokens.css` es ahora la ÚNICA fuente del sistema de diseño: hasta la Fase 2A
 * convivía con `theme.js` —que alimentaba los estilos inline de las pantallas
 * sin migrar— y un generador mantenía los dos en sincronía. Ese archivo ya no
 * existe, así que el generador se dio vuelta: en vez de producir el CSS desde
 * JavaScript, lee el CSS y produce la lista de nombres.
 *
 * Por qué sigue generándose y no se escribe a mano: `escalas.js` le dice a
 * tailwind-merge qué nombres pertenecen a cada escala. Si alguien agrega un
 * token de color a `tokens.css` y olvida sumarlo acá, `cn()` deja de deduplicar
 * ese color y los overrides por `className` empiezan a fallar en silencio —
 * exactamente el tipo de bug que no se ve hasta que alguien mira una captura.
 *
 *     npm run escalas
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const ORIGEN = resolve(AQUI, "../src/styles/tokens.css");
const DESTINO = resolve(AQUI, "../src/styles/escalas.js");

const css = readFileSync(ORIGEN, "utf8");

// Sólo el bloque `@theme static`: el `.dark` de abajo redefine los mismos
// nombres y contarlos otra vez duplicaría toda la escala de color.
const tema = css.slice(css.indexOf("@theme static"), css.indexOf("\n}", css.indexOf("@theme static")));

/** Nombres declarados bajo un prefijo, en orden de aparición y sin repetir. */
function nombres(prefijo) {
  const re = new RegExp(`--${prefijo}-([a-z0-9-]+)\\s*:`, "g");
  const vistos = [];
  for (const m of tema.matchAll(re)) {
    // `--color-*: initial` es el borrado de la escala de Tailwind, no un token.
    if (m[1] === "*") continue;
    if (!vistos.includes(m[1])) vistos.push(m[1]);
  }
  return vistos;
}

const escalas = {
  color: nombres("color"),
  text: nombres("text"),
  spacing: nombres("spacing"),
  radius: nombres("radius"),
  shadow: nombres("shadow"),
  font: nombres("font"),
};

const js = `/*
 * ARCHIVO GENERADO — no editar a mano.
 * Fuente: src/styles/tokens.css · Regenerar con: npm run escalas
 *
 * Nombres de las escalas del sistema de diseño, para configurar tailwind-merge.
 * Sin esto no sabe que \`rounded-pill\` pertenece al grupo del radio ni que
 * \`text-danger\` es un color, y al combinar clases deja las dos en conflicto en
 * vez de quedarse con la última — que es justo lo que rompe los overrides por
 * className en los componentes.
 */
export const escalas = {
${Object.entries(escalas)
  .map(([k, v]) => `  ${k}: [${v.map((n) => `"${n}"`).join(", ")}],`)
  .join("\n")}
};
`;

writeFileSync(DESTINO, js, "utf8");
for (const [k, v] of Object.entries(escalas)) {
  console.log(`  ${k.padEnd(8)} ${v.length} nombres`);
}
console.log(`escalas.js regenerado desde tokens.css`);
