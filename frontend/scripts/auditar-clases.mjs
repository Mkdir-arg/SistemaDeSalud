/**
 * Busca clases de Tailwind usadas en el código que NO generan CSS.
 *
 * Al reemplazar las escalas de Tailwind por las propias (`--text-*: initial` y
 * compañía), cualquier paso que no esté en el sistema de diseño deja de existir
 * y la clase se vuelve un no-op SILENCIOSO: no rompe el build, no avisa nada,
 * simplemente el estilo no se aplica.
 *
 * Ya pasó: `text-2xl` y `text-3xl` quedaron huérfanas al recortar la escala, y
 * durante varios días cinco pantallas mostraron sus cifras grandes al tamaño de
 * una etiqueta. Nadie lo vio hasta mirar una captura con atención.
 *
 * Uso: `npm run build && npm run auditar` (necesita el CSS ya compilado).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");

function archivos(dir, out = []) {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) archivos(p, out);
    else if (/\.jsx?$/.test(n)) out.push(p);
  }
  return out;
}

const distDir = join(RAIZ, "dist/assets");
let css;
try {
  const cssFile = readdirSync(distDir).filter((f) => f.endsWith(".css")).pop();
  css = readFileSync(join(distDir, cssFile), "utf8");
} catch {
  console.error("No hay CSS compilado en dist/assets. Corré `npm run build` primero.");
  process.exit(2);
}

// Prefijos de las escalas que reemplazamos: son los que pueden quedar huérfanos.
//
// La lista se corresponde una a una con los `*: initial` de tokens.css (color,
// font, text, radius, shadow). Las de espaciado y tamaño —`w-70`, `gap-2.5`,
// `p-3.5`— NO van acá: esa escala no se reemplazó, Tailwind sigue generándolas a
// demanda y ninguna puede quedar huérfana. Si algún día se resetea `--spacing`,
// hay que agregar sus prefijos.
const PREFIJOS = ["text", "rounded", "shadow", "font", "bg", "border", "fill", "stroke", "ring", "from", "to", "divide"];
const re = new RegExp(`\\b(?:${PREFIJOS.join("|")})-[a-z0-9-]+\\b`, "g");

const usadas = new Map(); // clase → [archivos]
for (const f of archivos(join(RAIZ, "src"))) {
  const src = readFileSync(f, "utf8");
  // Sólo dentro de className="..." o cadenas de clases.
  for (const m of src.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\}|\{([^}]*)\})/g)) {
    const texto = m[1] || m[2] || m[3] || "";
    for (const c of texto.match(re) || []) {
      // Se ignoran las variantes (hover:, md:): el nombre base es el mismo y el
      // escaneo lo cubre igual.
      if (!usadas.has(c)) usadas.set(c, []);
      const lista = usadas.get(c);
      const rel = relative(RAIZ, f).replace(/\\/g, "/");
      if (!lista.includes(rel)) lista.push(rel);
    }
  }
}

const huerfanas = [];
for (const [clase, files] of usadas) {
  // Basta con que el nombre aparezca en algún selector: puede llevar variante
  // (`hover\:bg-accent-100`), opacidad (`bg-ink\/45`) o valor arbitrario
  // (`border-l-\[3px\]`). Si NO aparece nunca, la clase no genera nada.
  if (!css.includes(clase)) huerfanas.push({ clase, files });
}

console.log(`Clases revisadas: ${usadas.size}`);
if (!huerfanas.length) {
  console.log("Ninguna clase huérfana.");
} else {
  console.log(`\nHUÉRFANAS (${huerfanas.length}) — la clase se escribe pero no genera CSS:`);
  for (const h of huerfanas.sort((a, b) => a.clase.localeCompare(b.clase))) {
    console.log(`  ${h.clase.padEnd(28)} ${h.files.join(", ")}`);
  }
  process.exit(1); // que falle: es lo único que distingue esto de un comentario
}
