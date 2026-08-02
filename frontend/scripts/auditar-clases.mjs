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
// Se corresponden una a una con los `*: initial` de tokens.css (color, font,
// text, radius, shadow): son las escalas reemplazadas, o sea las únicas donde un
// nombre inexistente queda huérfano.
const PREFIJOS_ESCALA = ["text", "rounded", "shadow", "font", "bg", "border", "fill", "stroke", "ring", "from", "to", "divide"];

// Ancho y alto: acá el problema no es que falte CSS sino que sobre del lado
// equivocado (ver COLISIONES más abajo). Se escanean para poder revisarlo.
const PREFIJOS_DIMENSION = ["max-w", "min-w", "max-h", "min-h", "w", "h", "size"];

const PREFIJOS = [...PREFIJOS_ESCALA, ...PREFIJOS_DIMENSION];
// El rango incluye MAYÚSCULAS a propósito.
//
// Los tokens se declaran en camelCase (`type.cifraLg`) y el generador los pasa a
// kebab (`--text-cifra-lg`), así que escribir `text-cifraLg` es el error más
// natural del mundo. Con `[a-z0-9-]+` el patrón cortaba en la mayúscula y
// validaba `text-cifra` —que existe—, dando por buena una clase que no genera
// nada. Tres pantallas pasaron la auditoría con sus cifras sin tamaño.
const re = new RegExp(`\\b(?:${PREFIJOS.join("|")})-[a-zA-Z0-9-]+\\b`, "g");

const usadas = new Map(); // clase → [archivos]
// Nombres que parecen clases pero no lo son. Mirar todas las cadenas del
// archivo trae algún falso positivo; se listan acá con el motivo en vez de
// volver atrás y perder la detección que sí importa.
const NO_SON_CLASES = new Set([
  "stroke-width",  // propiedad CSS dentro de un `transition`, en el editor de flujos
]);

for (const f of archivos(join(RAIZ, "src"))) {
  // Se sacan los comentarios: explican por qué NO se usa una clase, y ese
  // nombre no debería contar como uso (p. ej. «Tailwind no vería bg-avatar-x»).
  const src = readFileSync(f, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
  /*
   * Todas las cadenas del archivo, no sólo las de `className`.
   *
   * Muchas clases no se escriben en el atributo: viven en un objeto de
   * configuración («{ texto: "text-warn", barra: "bg-warn" }») y llegan al
   * `className` por una variable. Mirando sólo el atributo, esas quedaban sin
   * revisar — y así el tramo de aviso del tablero de camas estuvo sin color
   * desde que se escribió, con la auditoría en verde.
   *
   * El costo de mirar todas las cadenas es algún falso positivo si alguien
   * escribe un texto que parece una clase; hasta ahora no pasó, y el precio de
   * lo contrario ya se pagó.
   */
  for (const m of src.matchAll(/"([^"\n]*)"|'([^'\n]*)'|`([^`]*)`/g)) {
    const texto = m[1] || m[2] || m[3] || "";
    for (const c of texto.match(re) || []) {
      // Se ignoran las variantes (hover:, md:): el nombre base es el mismo y el
      // escaneo lo cubre igual.
      if (NO_SON_CLASES.has(c)) continue;
      if (!usadas.has(c)) usadas.set(c, []);
      const lista = usadas.get(c);
      const rel = relative(RAIZ, f).replace(/\\/g, "/");
      if (!lista.includes(rel)) lista.push(rel);
    }
  }
}

/*
 * Colisiones entre nuestros nombres de espaciado y las escalas de ancho/alto.
 *
 * Los tokens de espaciado se llaman `xs/sm/md/lg/xl/xxl` (`--spacing-md: 12px`) y
 * esos MISMOS nombres existen en la escala de contenedores de Tailwind
 * (`--container-md: 28rem`). En `max-w-md` gana el de espaciado, así que la clase
 * significa 12px en vez de 448px.
 *
 * Es peor que una clase huérfana: genera CSS perfectamente válido, así que
 * revisar «¿existe la clase?» no lo detecta. Pasó en el panel del login y en
 * TODOS los estados vacíos y de error de la app —el texto de detalle quedaba en
 * una columna de 12px— y sobrevivió a varias revisiones visuales.
 *
 * Para anchos hay que usar valor explícito: `max-w-[28rem]`.
 */
const DIMENSION = /^(?:max-w|min-w|max-h|min-h|w|h|size)-(?:xs|sm|md|lg|xl|xxl)$/;
const colisiones = [];
for (const [clase, files] of usadas) {
  if (DIMENSION.test(clase)) colisiones.push({ clase, files });
}

const huerfanas = [];
for (const [clase, files] of usadas) {
  // Basta con que el nombre aparezca en algún selector: puede llevar variante
  // (`hover\:bg-accent-100`), opacidad (`bg-ink\/45`) o valor arbitrario
  // (`border-l-\[3px\]`). Si NO aparece nunca, la clase no genera nada.
  if (!css.includes(clase)) huerfanas.push({ clase, files });
}

console.log(`Clases revisadas: ${usadas.size}`);

const listar = (titulo, items) => {
  console.log(`\n${titulo}`);
  for (const h of items.sort((a, b) => a.clase.localeCompare(b.clase))) {
    console.log(`  ${h.clase.padEnd(28)} ${h.files.join(", ")}`);
  }
};

if (huerfanas.length) {
  listar(`HUÉRFANAS (${huerfanas.length}) — la clase se escribe pero no genera CSS:`, huerfanas);
}
if (colisiones.length) {
  listar(
    `COLISIONES (${colisiones.length}) — el nombre lo resuelve la escala de espaciado,\n` +
      "así que el ancho/alto sale en píxeles sueltos. Usá valor explícito, p. ej. max-w-[28rem]:",
    colisiones,
  );
}

if (!huerfanas.length && !colisiones.length) {
  console.log("Ninguna clase huérfana ni en colisión.");
} else {
  process.exit(1); // que falle: es lo único que distingue esto de un comentario
}
