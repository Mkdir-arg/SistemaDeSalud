import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";

// Ejecuta el módulo completo sin transformarlo ni iniciar Vite/navegador.
// import.meta.env y las superficies del navegador son explícitas y sintéticas.
const source = await readFile(new URL("./client.js", import.meta.url), "utf8");

const storage = () => {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
};

// Web Locks sintético: una cola por origen, compartida entre «pestañas».
const candados = () => {
  let cola = Promise.resolve();
  return { request: (_nombre, fn) => {
    const turno = cola.then(() => fn());
    cola = turno.catch(() => null);
    return turno;
  } };
};

async function cliente({
  base, responder = () => new Response("archivo"), abortSignal = AbortSignal,
  localStorage = storage(), navigator, persistir = false,
} = {}) {
  const peticiones = [];
  const descargas = [];
  if (persistir) localStorage.setItem("salud.persistir", "1");
  class BrowserURL extends URL {
    static createObjectURL() { return "blob:synthetic"; }
    static revokeObjectURL() {}
  }
  const context = vm.createContext({
    AbortSignal: abortSignal, setTimeout, clearTimeout,
    localStorage, sessionStorage: storage(), URL: BrowserURL,
    ...(navigator ? { navigator } : {}),
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

test("cierre explícito limpia localmente y revoca con refresh sin cabeceras de sesión", async () => {
  const client = await cliente({ responder: () => new Response(null, { status: 204 }) });
  const cerrado = client.api.cerrarSesion();
  assert.equal(client.tokens.access, null);
  assert.equal(client.tokens.refresh, null);
  assert.equal(await cerrado, true);
  assert.equal(client.peticiones.length, 1);
  const peticion = client.peticiones[0];
  assert.equal(peticion.url, "/api/auth/logout/");
  assert.deepEqual(JSON.parse(peticion.body), { refresh: "synthetic-refresh" });
  assert.equal(peticion.headers.Authorization, undefined);
  assert.equal(peticion.headers["X-PLEXO-Simulacion"], undefined);
  assert.equal(peticion.credentials, "omit");
  assert.equal(peticion.redirect, "error");
});

test("logout local usado por bloqueo no solicita revocación remota", async () => {
  const client = await cliente();
  client.api.logout();
  assert.equal(client.tokens.access, null);
  assert.equal(client.tokens.refresh, null);
  assert.equal(client.peticiones.length, 0);
});

test("cierre espera refresh rotado sin restaurarlo y no altera un login nuevo", async () => {
  let iniciar, terminar;
  const iniciado = new Promise(resolve => { iniciar = resolve; });
  const pendiente = new Promise(resolve => { terminar = resolve; });
  const client = await cliente({ responder: url => {
    if (url.endsWith("/auth/token/refresh/")) { iniciar(); return pendiente; }
    if (url.endsWith("/auth/logout/")) {
      const cierre = client.peticiones.at(-1);
      return new Response(null, { status: JSON.parse(cierre.body).refresh === "refresh-anterior-rotado" ? 204 : 401 });
    }
    if (url.endsWith("/auth/token/")) return Response.json({ access: "access-nueva-persona", refresh: "refresh-nueva-persona" });
    return Response.json({}, { status: 401 });
  } });
  const anterior = client.api.get("/usuarios/me/");
  const rechazada = assert.rejects(anterior, { status: 401 });
  await iniciado;
  const cierre = client.api.cerrarSesion();
  assert.equal(client.tokens.access, null);
  assert.equal(client.tokens.refresh, null);
  assert.equal(client.peticiones.filter(p => p.url.endsWith("/auth/logout/")).length, 0);
  await client.api.login("nueva-persona@example.test", "clave-sintética");
  terminar(Response.json({ access: "access-anterior-rotado", refresh: "refresh-anterior-rotado" }));
  assert.equal(await cierre, true);
  await rechazada;
  const remota = client.peticiones.find(p => p.url.endsWith("/auth/logout/"));
  assert.deepEqual(JSON.parse(remota.body), { refresh: "refresh-anterior-rotado" });
  assert.equal(client.tokens.access, "access-nueva-persona");
  assert.equal(client.tokens.refresh, "refresh-nueva-persona");
});

test("el límite de espera no restaura tokens ni envía un cierre tardío tras renovar", async () => {
  const limite = new AbortController();
  let iniciar, terminar;
  const iniciado = new Promise(resolve => { iniciar = resolve; });
  const pendiente = new Promise(resolve => { terminar = resolve; });
  const client = await cliente({ abortSignal: { timeout: () => limite.signal }, responder: url => {
    if (url.endsWith("/auth/token/refresh/")) { iniciar(); return pendiente; }
    return Response.json({}, { status: 401 });
  } });
  const rechazada = assert.rejects(client.api.get("/usuarios/me/"), { status: 401 });
  await iniciado;
  const cierre = client.api.cerrarSesion();
  limite.abort();
  assert.equal(await cierre, false);
  terminar(Response.json({ access: "access-anterior-rotado", refresh: "refresh-anterior-rotado" }));
  await rechazada;
  assert.equal(client.tokens.access, null);
  assert.equal(client.tokens.refresh, null);
  assert.equal(client.peticiones.filter(p => p.url.endsWith("/auth/logout/")).length, 0);
});

for (const fallo of ["red", 401, 503]) {
  test(`cierre ${fallo} conserva salida local e informa revocación no confirmada`, async () => {
    const client = await cliente({ responder: () => {
      if (fallo === "red") throw new TypeError("Fallo de red sintético");
      return Response.json({}, { status: fallo });
    } });
    assert.equal(await client.api.cerrarSesion(), false);
    assert.equal(client.tokens.access, null);
    assert.equal(client.tokens.refresh, null);
    assert.equal(client.peticiones.length, 1);
  });
}

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

for (const status of [429, 503]) {
  test(`refresh institucional con ${status} conserva tokens y permite reintentar`, async () => {
    let disponible = false;
    const client = await cliente({ responder: (url, options) => {
      if (url.endsWith("/auth/token/refresh/")) return disponible
        ? Response.json({ access: "synthetic-renewed", refresh: "synthetic-rotated" })
        : Response.json({ detail: "Fallo temporal sintético" }, { status });
      return options.headers.Authorization === "Bearer synthetic-renewed"
        ? Response.json({ id: 1 }) : new Response("", { status: 401 });
    } });
    await assert.rejects(client.api.get("/usuarios/me/"), { status });
    assert.equal(client.tokens.access, "synthetic-access");
    assert.equal(client.tokens.refresh, "synthetic-refresh");
    assert.equal(client.peticiones.length, 2);
    disponible = true;
    assert.equal((await client.api.get("/usuarios/me/")).id, 1);
    assert.equal(client.tokens.refresh, "synthetic-rotated");
  });
}

for (const status of [400, 401]) {
  test(`refresh institucional rechazado con${status} sí elimina las credenciales`, async () => {
    const client = await cliente({ responder: (url) => new Response("", {
      status: url.endsWith("/auth/token/refresh/") ? status : 401,
    }) });
    await assert.rejects(client.api.get("/usuarios/me/"), { status: 401 });
    assert.equal(client.tokens.access, null);
    assert.equal(client.tokens.refresh, null);
    assert.equal(client.peticiones.length, 2);
  });
}

test("dos401 concurrentes comparten el refresh503 sin borrar credenciales", async () => {
  let completar, iniciado;
  const listo = new Promise(resolve => { iniciado = resolve; });
  const pendiente = new Promise(resolve => { completar = resolve; });
  const client = await cliente({ responder: url => {
    if (url.endsWith("/auth/token/refresh/")) { iniciado(); return pendiente; }
    return new Response("", { status: 401 });
  } });
  const resultados = Promise.allSettled([client.api.get("/usuarios/me/"), client.api.get("/formularios/")]);
  await listo;
  completar(new Response("", { status: 503 }));
  for (const r of await resultados) {
    assert.equal(r.status, "rejected");
    assert.equal(r.reason.status, 503);
  }
  assert.equal(client.peticiones.filter(p => p.url.endsWith("/auth/token/refresh/")).length, 1);
  assert.equal(client.tokens.refresh, "synthetic-refresh");
  assert.equal(client.tokens.access, "synthetic-access");
});

test("fallo de red al renovar conserva la sesión y se puede recuperar", async () => {
  let caida = true;
  const client = await cliente({ responder: (url, options) => {
    if (url.endsWith("/auth/token/refresh/")) {
      if (caida) throw new TypeError("Fallo de red sintético");
      return Response.json({ access: "synthetic-renewed", refresh: "synthetic-rotated" });
    }
    return options.headers.Authorization === "Bearer synthetic-renewed"
      ? Response.json({ id: 1 }) : new Response("", { status: 401 });
  } });
  await assert.rejects(client.api.get("/usuarios/me/"), TypeError);
  assert.equal(client.tokens.refresh, "synthetic-refresh");
  assert.equal(client.tokens.access, "synthetic-access");
  caida = false;
  assert.equal((await client.api.get("/usuarios/me/")).id, 1);
});

test("una operación pública no depende de cambios de sesión locales mientras espera", async () => {
  let responder;
  const client = await cliente({ responder: () => new Promise((resolve) => { responder = resolve; }) });
  const solicitud = client.api.public.post("/auth/recuperacion/", { email: "titular@example.test" });
  client.tokens.clear();
  responder(Response.json({ detail: "Solicitud recibida" }, { status: 202 }));
  assert.equal((await solicitud).detail, "Solicitud recibida");
});

// Servidor sintético con refresh de un solo uso: el consumido responde 401 y
// la renovación ganadora sigue válida (#172, «conservar la renovación válida»).
function servidorDeUnSoloUso() {
  let vigente = "synthetic-refresh";
  // El access del cliente ya venció: el primer pedido de cada pestaña recibe 401.
  let acceso = "access-vigente-solo-tras-renovar";
  let ronda = 0;
  const demorados = [];
  const responder = (url, options) => {
    if (url.endsWith("/auth/token/refresh/")) {
      const enviado = JSON.parse(options.body).refresh;
      const respuesta = new Promise(resolve => demorados.push(() => {
        if (enviado !== vigente) return resolve(new Response("", { status: 401 }));
        ronda += 1;
        vigente = `refresh-rotado-${ronda}`;
        acceso = `access-rotado-${ronda}`;
        resolve(Response.json({ access: acceso, refresh: vigente }));
      }));
      return respuesta;
    }
    return options.headers.Authorization === `Bearer ${acceso}`
      ? Response.json({ id: 1 }) : new Response("", { status: 401 });
  };
  const esperarRefresh = async (cantidad) => {
    while (demorados.length < cantidad) await new Promise(r => setTimeout(r, 1));
  };
  return { responder, demorados, esperarRefresh, actual: () => ({ vigente, acceso }) };
}

async function dosPestanas({ conCandados }) {
  const compartido = storage();
  const server = servidorDeUnSoloUso();
  const navigator = conCandados ? { locks: candados() } : undefined;
  const opciones = { responder: server.responder, localStorage: compartido, navigator, persistir: true };
  const a = await cliente(opciones);
  const b = await cliente(opciones);
  return { a, b, server, compartido };
}

test("sin Web Locks, la pestaña que pierde la carrera de refresh no borra la sesión compartida", async () => {
  const { a, b, server } = await dosPestanas({ conCandados: false });
  // El servidor da el triunfo a la pestaña A y responde 401 a B después de
  // que A ya guardó su renovación en el almacén compartido.
  const pedidoA = a.api.get("/usuarios/me/");
  await server.esperarRefresh(1);
  const pedidoB = b.api.get("/formularios/");
  await server.esperarRefresh(2);
  server.demorados[0]();
  assert.equal((await pedidoA).id, 1);
  server.demorados[1]();
  assert.equal((await pedidoB).id, 1);
  assert.equal(a.tokens.refresh, server.actual().vigente);
  assert.equal(b.tokens.refresh, server.actual().vigente);
});

test("con Web Locks, una sola pestaña renueva y la otra reutiliza la renovación ganadora", async () => {
  const { a, b, server } = await dosPestanas({ conCandados: true });
  const pedidoA = a.api.get("/usuarios/me/");
  await server.esperarRefresh(1);
  const pedidoB = b.api.get("/formularios/");
  // B espera el candado: no presenta el refresh consumido.
  await new Promise(r => setTimeout(r, 5));
  assert.equal(server.demorados.length, 1);
  server.demorados[0]();
  assert.equal((await pedidoA).id, 1);
  assert.equal((await pedidoB).id, 1);
  const renovaciones = [...a.peticiones, ...b.peticiones].filter(p => p.url.endsWith("/auth/token/refresh/"));
  assert.equal(renovaciones.length, 1);
  assert.equal(b.tokens.access, server.actual().acceso);
});

test("con Web Locks, un refresh revocado sin renovación ajena sigue cerrando la sesión", async () => {
  const compartido = storage();
  const opciones = {
    responder: () => new Response("", { status: 401 }),
    localStorage: compartido, navigator: { locks: candados() }, persistir: true,
  };
  const a = await cliente(opciones);
  await assert.rejects(a.api.get("/usuarios/me/"), { status: 401 });
  assert.equal(a.tokens.access, null);
  assert.equal(a.tokens.refresh, null);
  assert.equal(compartido.getItem("salud.refresh"), null);
});
