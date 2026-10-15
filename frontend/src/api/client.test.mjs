import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

// Ejecuta el módulo completo sin transformarlo ni iniciar Vite/navegador.
// import.meta.env y las superficies del navegador son explícitas y sintéticas.
const source = await readFile(new URL("./client.js", import.meta.url), "utf8");

async function cliente({ base, responder = () => new Response("archivo") } = {}) {
  const peticiones = [];
  const descargas = [];
  const storage = () => {
    const values = new Map();
    return {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, String(value)),
      removeItem: (key) => values.delete(key),
    };
  };
  class BrowserURL extends URL {
    static createObjectURL() { return "blob:synthetic"; }
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    localStorage: storage(), sessionStorage: storage(), URL: BrowserURL,
    window: { location: { href: "https://plexo.test/historia/1", origin: "https://plexo.test" } },
    document: {
      body: { appendChild() {} },
      createElement: () => ({ click() { descargas.push(this.download); }, remove() {} }),
    },
    fetch: async (url, options) => {
      peticiones.push({ url: String(url), ...options });
      return responder(String(url), options, peticiones.length);
    },
  });
  const module = new vm.SourceTextModule(source, {
    context,
    initializeImportMeta(meta) { meta.env = { VITE_API_URL: base }; },
  });
  await module.link(() => { throw new Error("Import inesperado en cliente HTTP"); });
  await module.evaluate();
  module.namespace.tokens.set({ access: "synthetic-access", refresh: "synthetic-refresh" });
  module.namespace.simulacion.set({ id: "synthetic-simulation" });
  return { ...module.namespace, peticiones, descargas };
}

test("descargas rechazan referencias externas antes de enviar credenciales o refrescar", async () => {
  const client = await cliente();
  for (const ref of [
    "https://externo.test/estudio.pdf",
    "//externo.test/api/archivos/descargar/estudio.pdf",
    "https://plexo.test.evil.test/api/archivos/descargar/a.pdf",
    "https://plexo.test:8443/api/archivos/descargar/a.pdf",
    "http://plexo.test/api/archivos/descargar/a.pdf",
    "https://usuario:clave@plexo.test/api/archivos/descargar/a.pdf",
    "data:application/pdf,contenido", "javascript:alert(1)",
    "\\\\externo.test\\archivo.pdf",
  ]) {
    await assert.rejects(client.api.downloadArchivo(ref), { status: 400 }, ref);
  }
  assert.equal(client.peticiones.length, 0);
  assert.equal(client.descargas.length, 0);
});

test("solo admite el endpoint de archivos, sin rutas vacías ni escapes normalizados", async () => {
  const client = await cliente();
  for (const ref of ["", "/api/usuarios/", "../usuarios/", "%2e%2e/usuarios/", "/api/archivos/descargar/", "a.pdf\n"]) {
    await assert.rejects(client.api.downloadArchivo(ref), { status: 400 }, ref);
  }
  assert.equal(client.peticiones.length, 0);
});

test("conserva claves y URLs legítimas del backend con autenticación y simulación", async () => {
  const client = await cliente();
  for (const ref of [
    "clinica/a.pdf", "/api/archivos/descargar/clinica/a.pdf",
    "https://plexo.test/api/archivos/descargar/clinica/a.pdf",
  ]) {
    await client.api.downloadArchivo(ref, "estudio.pdf");
  }
  assert.equal(client.descargas.length, 3);
  for (const request of client.peticiones) {
    assert.equal(new URL(request.url, "https://plexo.test").href, "https://plexo.test/api/archivos/descargar/clinica/a.pdf");
    assert.equal(request.headers.Authorization, "Bearer synthetic-access");
    assert.equal(request.headers["X-PLEXO-Simulacion"], "synthetic-simulation");
    assert.equal(request.redirect, "error");
  }
});

test("una API configurada en otro origen es el único destino confiable", async () => {
  const client = await cliente({ base: "https://api.plexo.test/api" });
  await client.api.downloadArchivo("https://api.plexo.test/api/archivos/descargar/a.pdf");
  await client.api.downloadArchivo("a.pdf");
  await assert.rejects(client.api.downloadArchivo("https://plexo.test/api/archivos/descargar/a.pdf"), { status: 400 });
  assert.equal(client.peticiones.length, 2);
  assert.ok(client.peticiones.every((request) => new URL(request.url).origin === "https://api.plexo.test"));
});

test("el reintento tras refresh tampoco permite redirects", async () => {
  const client = await cliente({
    responder: (url, options, index) => {
      if (url.endsWith("/auth/token/refresh/")) return Response.json({ access: "synthetic-renewed" });
      return index === 1 ? new Response("", { status: 401 }) : new Response("archivo");
    },
  });
  await client.api.downloadArchivo("a.pdf");
  const downloads = client.peticiones.filter((request) => !request.url.endsWith("/auth/token/refresh/"));
  assert.equal(downloads.length, 2);
  assert.equal(downloads[0].redirect, "error");
  assert.equal(downloads[1].redirect, "error");
  assert.equal(downloads[1].headers.Authorization, "Bearer synthetic-renewed");
  assert.equal(downloads[1].headers["X-PLEXO-Simulacion"], "synthetic-simulation");
  assert.equal(client.descargas.length, 1);
});

test("un rechazo de redirect no descarga ni dispara refresh", async () => {
  const client = await cliente({ responder: () => { throw new TypeError("redirect bloqueado"); } });
  await assert.rejects(client.api.downloadArchivo("a.pdf"), /redirect bloqueado/);
  assert.equal(client.peticiones.length, 1);
  assert.equal(client.peticiones[0].redirect, "error");
  assert.equal(client.descargas.length, 0);
});

test("credenciales públicas no envían JWT, simulación ni cookies", async () => {
  const client = await cliente({ responder: () => Response.json({ detail: "Solicitud recibida" }, { status: 202 }) });
  await client.api.public.post("/auth/recuperacion/", { email: "titular@example.test" });
  const request = client.peticiones[0];
  assert.equal(request.headers.Authorization, undefined);
  assert.equal(request.headers["X-PLEXO-Simulacion"], undefined);
  assert.equal(request.credentials, "omit");
  assert.equal(request.redirect, "error");
});

test("un enlace público rechazado no renueva ni borra la sesión existente", async () => {
  const client = await cliente({ responder: () => Response.json({ detail: "Enlace inválido" }, { status: 401 }) });
  await assert.rejects(client.api.public.post("/auth/restablecer/", { uid: "ficticio", token: "ficticio" }), { status: 401 });
  assert.equal(client.peticiones.length, 1);
  assert.equal(client.tokens.access, "synthetic-access");
  assert.equal(client.tokens.refresh, "synthetic-refresh");
});

test("una operación pública no depende de cambios de sesión locales mientras espera", async () => {
  let responder;
  const client = await cliente({ responder: () => new Promise((resolve) => { responder = resolve; }) });
  const solicitud = client.api.public.post("/auth/recuperacion/", { email: "titular@example.test" });
  client.tokens.clear();
  responder(Response.json({ detail: "Solicitud recibida" }, { status: 202 }));
  assert.equal((await solicitud).detail, "Solicitud recibida");
});
