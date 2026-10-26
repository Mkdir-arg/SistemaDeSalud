import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

if (!process.env.SALUD_IMPORTACION_MANIFEST) throw new Error("Falta manifiesto ficticio del entorno PostgreSQL aislado.");
const datos = JSON.parse(readFileSync(process.env.SALUD_IMPORTACION_MANIFEST, "utf8"));
if (datos.escenario !== "importacion-respuesta-v1" || !datos.organizacion || !datos.email.endsWith("@example.invalid")) {
  throw new Error("El manifiesto no pertenece al escenario ficticio de importación.");
}
const base = `/api/financiadores/${datos.organizacion}/`;

async function fetchReal(route, opciones = {}) {
  try {
    return await route.fetch({ timeout: 60000, ...opciones });
  } catch {
    // Playwright incluye Authorization al imprimir errores de route.fetch.
    // Mantener el fallo explícito sin registrar credenciales, ni siquiera de test.
    throw new Error("La petición al servidor de prueba no pudo completarse.");
  }
}

async function acceso(page) {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.email);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(`/financiadores/padron?financiador=${datos.organizacion}`);
  await page.getByRole("button", { name: "Importar Excel", exact: true }).click();
  await page.getByLabel("Formato del archivo", { exact: true }).selectOption("ostel");
  await page.getByRole("checkbox", { name: "Habilitar cobertura", exact: true }).uncheck();
}

async function cargar(page, caso) {
  await acceso(page);
  await page.getByLabel("Archivo Excel (.xlsx)", { exact: true }).setInputFiles(caso.archivo);
  await page.getByRole("button", { name: "Revisar archivo", exact: true }).click();
  await expect(page.getByRole("button", { name: `Aplicar ${caso.validas} filas válidas`, exact: true })).toBeEnabled();
}

async function headers(request) {
  const respuesta = await request.post("/api/auth/token/", { data: { email: datos.email, password: datos.password } });
  expect(respuesta.status()).toBe(200);
  return { Authorization: `Bearer ${(await respuesta.json()).access}` };
}

async function persistido(request, id, h) {
  const respuesta = await request.get(`${base}importaciones/?tipo=padron`, { headers: h });
  expect(respuesta.status()).toBe(200);
  const lote = (await respuesta.json()).results.find((item) => item.id === id);
  expect(lote).toBeTruthy();
  return lote;
}

async function comprobarPadron(request, caso, cantidad, h) {
  const respuesta = await request.get(`${base}padron/?search=${encodeURIComponent(caso.prefijo)}&estado=todos`, { headers: h });
  expect(respuesta.status()).toBe(200);
  const padron = await respuesta.json();
  expect(padron.count).toBe(cantidad);
  for (const afiliado of padron.results) expect(afiliado.cobertura_habilitada).toBe(false);
}

test("UI real aplica varias tandas, conserva conflicto y persiste respuesta acotada", async ({ page, request }) => {
  const caso = datos.casos.normal;
  const respuestas = [];
  await page.route(`**${base}confirmar-importacion/**`, async (route) => {
    const respuesta = await fetchReal(route);
    respuestas.push(await respuesta.json());
    await route.fulfill({ response: respuesta });
  });
  await cargar(page, caso);
  await page.getByRole("button", { name: `Aplicar ${caso.validas} filas válidas`, exact: true }).click();
  await expect(page.getByRole("button", { name: "Aplicar 0 filas válidas", exact: true })).toBeDisabled({ timeout: 60000 });
  expect(respuestas.map((r) => r.modo_respuesta)).toEqual(["completa", "cambios", "cambios"]);
  expect(respuestas[1].filas).toBeUndefined();
  expect(respuestas[1].filas_cambiadas).toHaveLength(100);
  expect(respuestas[2].filas_cambiadas).toHaveLength(5);
  await expect(page.getByRole("button", { name: "Revisar fila", exact: true })).toHaveCount(1);
  await page.getByRole("combobox", { name: "Mostrar filas", exact: true }).selectOption("aplicada");
  await expect(page.getByRole("button", { name: "Ver detalle", exact: true })).toHaveCount(20);
  await page.getByRole("button", { name: "Ver detalle", exact: true }).first().click();
  await page.getByText("Ver valores originales del archivo", { exact: true }).click();
  await expect(page.getByText(`${caso.prefijo}-1`, { exact: true }).first()).toBeVisible();
  const h = await headers(request);
  const lote = await persistido(request, respuestas[0].id, h);
  expect(lote.resumen.aplicada).toBe(205);
  expect(lote.resumen.revision).toBe(1);
  expect(lote.filas.at(-1).original.CUIL).toBe("123");
  await comprobarPadron(request, caso, 205, h);
});

test("respuesta perdida después del commit se recupera con reintento explícito", async ({ page, request }) => {
  const caso = datos.casos.respuesta_perdida;
  const respuestas = [];
  const pedidos = [];
  await page.route(`**${base}confirmar-importacion/**`, async (route) => {
    pedidos.push(route.request().postDataJSON());
    const respuesta = await fetchReal(route); // API y commit reales.
    respuestas.push(await respuesta.json());
    if (pedidos.length === 2) await route.abort("connectionreset");
    else await route.fulfill({ response: respuesta });
  });
  await cargar(page, caso);
  await page.getByRole("button", { name: "Aplicar 205 filas válidas", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "La tanda puede haberse guardado" })).toBeVisible({ timeout: 60000 });
  expect(pedidos).toHaveLength(2);
  const h = await headers(request);
  expect((await persistido(request, respuestas[0].id, h)).resumen.aplicada).toBe(200);
  await page.getByRole("button", { name: "Aplicar 105 filas válidas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Aplicar 0 filas válidas", exact: true })).toBeDisabled({ timeout: 60000 });
  expect(pedidos).toHaveLength(3);
  expect(pedidos[2].huella_lote).toBeUndefined();
  expect(respuestas[2].modo_respuesta).toBe("completa");
  expect((await persistido(request, respuestas[0].id, h)).resumen.aplicada).toBe(205);
  await comprobarPadron(request, caso, 205, h);
});

test("otra sesión excluye una fila y el cliente recupera la evidencia actual", async ({ page, request }) => {
  const caso = datos.casos.otra_sesion;
  const h = await headers(request);
  const respuestas = [];
  await page.route(`**${base}confirmar-importacion/**`, async (route) => {
    if (respuestas.length === 1) {
      const fila = respuestas[0].filas.at(-1);
      const cambio = await request.post(`${base}subsanar-ostel/`, { headers: h, data: {
        importacion: respuestas[0].id, fila: fila.fila, revision: fila.revision, datos: fila.datos,
        motivo: "Exclusión ficticia desde otra sesión", accion: "omitir",
      } });
      expect(cambio.status()).toBe(200);
    }
    const respuesta = await fetchReal(route);
    respuestas.push(await respuesta.json());
    await route.fulfill({ response: respuesta });
  });
  await cargar(page, caso);
  await page.getByRole("button", { name: "Aplicar 101 filas válidas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Aplicar 0 filas válidas", exact: true })).toBeDisabled({ timeout: 60000 });
  expect(respuestas.map((r) => r.modo_respuesta)).toEqual(["completa", "completa"]);
  await page.getByRole("combobox", { name: "Mostrar filas", exact: true }).selectOption("omitida");
  await expect(page.getByRole("button", { name: "Ver detalle", exact: true })).toHaveCount(1);
  const lote = await persistido(request, respuestas[0].id, h);
  expect(lote.resumen.aplicada).toBe(100);
  expect(lote.resumen.omitida).toBe(1);
  expect(lote.filas.at(-1).correcciones.at(-1).motivo).toBe("Exclusión ficticia desde otra sesión");
  await comprobarPadron(request, caso, 100, h);
});

test("frontend acepta confirmaciones tradicionales completas de API real", async ({ page, request }) => {
  const caso = datos.casos.completa;
  const respuestas = [];
  await page.route(`**${base}confirmar-importacion/**`, async (route) => {
    const respuesta = await fetchReal(route, { postData: { importacion: route.request().postDataJSON().importacion } });
    respuestas.push(await respuesta.json());
    await route.fulfill({ response: respuesta });
  });
  await cargar(page, caso);
  await page.getByRole("button", { name: "Aplicar 101 filas válidas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Aplicar 0 filas válidas", exact: true })).toBeDisabled({ timeout: 60000 });
  expect(respuestas).toHaveLength(2);
  expect(respuestas.every((r) => Array.isArray(r.filas) && !r.modo_respuesta)).toBe(true);
  await comprobarPadron(request, caso, 101, await headers(request));
});
