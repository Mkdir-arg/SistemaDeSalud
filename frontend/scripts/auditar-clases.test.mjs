import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, mkdtempSync, realpathSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, sep } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const script = join(dirname(fileURLToPath(import.meta.url)), "auditar-clases.mjs");

function ejecutarFixture(t, { fuente = 'const clase = "bg-accent";', chunks = [] } = {}) {
  const carpeta = mkdtempSync(join(tmpdir(), "salud-auditar-clases-"));
  const raiz = realpathSync(carpeta);
  t.after(() => {
    // Solo borrar la carpeta temporal exacta creada por esta prueba.
    const destino = realpathSync(carpeta);
    const rutaRelativa = relative(realpathSync(tmpdir()), destino);
    assert.equal(destino, raiz);
    assert.ok(rutaRelativa && !isAbsolute(rutaRelativa) && rutaRelativa !== ".." && !rutaRelativa.startsWith(`..${sep}`));
    rmSync(destino, { recursive: true });
  });
  mkdirSync(join(raiz, "scripts"));
  mkdirSync(join(raiz, "src"));
  mkdirSync(join(raiz, "dist", "assets"), { recursive: true });
  copyFileSync(script, join(raiz, "scripts", "auditar-clases.mjs"));
  const fuentePath = join(raiz, "src", "fixture.jsx");
  writeFileSync(fuentePath, fuente);
  // Tiempos explícitos, sin sleeps ni dependencia de resolución del filesystem.
  const ahora = Date.now() / 1000;
  utimesSync(fuentePath, ahora - 60, ahora - 60);
  for (const { nombre, css, viejo = false } of chunks) {
    const path = join(raiz, "dist", "assets", nombre);
    writeFileSync(path, css);
    utimesSync(path, ahora - (viejo ? 120 : 30), ahora - (viejo ? 120 : 30));
  }
  const resultado = spawnSync(process.execPath, [join(raiz, "scripts", "auditar-clases.mjs")], { encoding: "utf8", timeout: 10000 });
  assert.ifError(resultado.error);
  return resultado;
}

test("valida utilidades de todos los chunks, aunque el último solo tenga estilos locales", (t) => {
  const r = ejecutarFixture(t, { fuente: 'const clase = "bg-accent text-cifra";', chunks: [
    { nombre: "a-index.css", css: ".bg-accent{color:red}" },
    { nombre: "b-finanzas.css", css: ".text-cifra{font-size:20px}" },
    { nombre: "z-portal.css", css: ".padron-tabla{overflow:auto}" },
  ] });
  assert.equal(r.status, 0, r.stderr + r.stdout);
  assert.match(r.stdout, /Clases revisadas: 2/);
  assert.match(r.stdout, /Ninguna clase huérfana ni en colisión/);
});

test("una clase ausente de todos los chunks conserva exit1", (t) => {
  const r = ejecutarFixture(t, { chunks: [{ nombre: "index.css", css: ".text-cifra{}" }] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /HUÉRFANAS \(1\)/);
  assert.match(r.stdout, /bg-accent/);
});

test("un build viejo conserva exit2 antes de denunciar clases", (t) => {
  const r = ejecutarFixture(t, { chunks: [{ nombre: "index.css", css: ".bg-accent{}", viejo: true }] });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /más viejo que el código/);
  assert.doesNotMatch(r.stdout, /HUÉRFANAS/);
});

test("un chunk nuevo no oculta un chunk viejo que contiene la utilidad", (t) => {
  const r = ejecutarFixture(t, { chunks: [
    { nombre: "a-index.css", css: ".bg-accent{}", viejo: true },
    { nombre: "z-portal.css", css: ".padron-tabla{}" },
  ] });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /más viejo que el código/);
});

test("sin CSS conserva exit2 e instrucción de compilar", (t) => {
  const r = ejecutarFixture(t, { chunks: [{ nombre: "index.js", css: "// no CSS" }] });
  assert.equal(r.status, 2);
  assert.match(r.stderr, /No hay CSS compilado/);
});

test("una colisión real conserva exit1 aunque la clase tenga CSS", (t) => {
  const r = ejecutarFixture(t, { fuente: 'const clase = "max-w-md";', chunks: [{ nombre: "index.css", css: ".max-w-md{max-width:12px}" }] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /COLISIONES \(1\)/);
  assert.doesNotMatch(r.stdout, /HUÉRFANAS/);
});

test("los límites entre chunks no fabrican una clase inexistente", (t) => {
  const r = ejecutarFixture(t, { chunks: [
    { nombre: "a.css", css: ".bg-ac" },
    { nombre: "z.css", css: "cent{}" },
  ] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /HUÉRFANAS \(1\)/);
});
