import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const datos = JSON.parse(readFileSync(process.env.SALUD_FAMILIA_MANIFEST, "utf8"));
if (datos.escenario !== "familia-ostel-v1" || !datos.email.endsWith("@example.invalid")) {
  throw new Error("Se requiere el escenario ficticio dedicado de familias.");
}
const base = `/api/financiadores/${datos.organizacion}/`;

// StrictMode puede dejar un segundo GET en vuelo al completar una aserción.
// Esperar sus handlers antes de que Playwright descarte las respuestas del contexto.
test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "wait" }); });

async function cargar(page, caso) {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.email);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(`/financiadores/padron?financiador=${datos.organizacion}`);
  await page.getByRole("button", { name: "Importar Excel", exact: true }).click();
  await page.getByLabel("Formato del archivo", { exact: true }).selectOption("ostel");
  await page.getByRole("checkbox", { name: "Habilitar cobertura", exact: true }).uncheck();
  await page.getByLabel("Archivo Excel (.xlsx)", { exact: true }).setInputFiles(datos.casos[caso]);
  await page.getByRole("button", { name: "Revisar archivo", exact: true }).click();
  await page.getByRole("button", { name: "Importar 2 filas válidas", exact: true }).click();
  await expect(page.getByRole("button", { name: "Importar 0 filas válidas", exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: /^Aplicadas/ }).click();
  return page.getByRole("row").filter({ hasText: `Integrante ficticio ${caso}` });
}

test("propuesta explícita, cancelación sin escritura y confirmación real", async ({ page }) => {
  const escrituras = [];
  page.on("request", (r) => { if (r.url().includes("/familia-ostel/") && r.method() === "POST") escrituras.push(r.postDataJSON()); });
  const fila = await cargar(page, "normal");
  await fila.getByRole("button", { name: "Ver detalle", exact: true }).click();
  await expect(page.getByRole("dialog", { name: /^Detalle de/ })).toBeVisible();
  await page.keyboard.press("Escape");
  const abrir = fila.getByRole("button", { name: "Vincular familia", exact: true });
  await expect(abrir).toBeVisible();
  await abrir.focus();
  await page.keyboard.press("Enter");
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  await expect(dialogo.getByText("Titular ficticio normal", { exact: true })).toBeVisible();
  expect(escrituras).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(abrir).toBeFocused();
  await abrir.click();
  const confirmado = page.waitForResponse((r) => r.url().includes("/familia-ostel/") && r.request().method() === "POST");
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  const respuesta = await confirmado;
  expect(respuesta.status()).toBe(200);
  const ficha = await respuesta.json();
  expect(ficha.titular).toBe(escrituras[0].titular);
  expect(ficha.parentesco).toBe("");
  expect(ficha.cobertura_habilitada).toBe(false);
  await expect(dialogo.getByRole("status").filter({ hasText: "Vínculo confirmado" })).toBeVisible();
  expect(escrituras).toHaveLength(1);
});

async function fetchReal(route) {
  try { return await route.fetch(); }
  catch { throw new Error("No se pudo completar la petición al servidor ficticio."); }
}

test("revisión obsoleta requiere una propuesta nueva, no reintenta el vínculo", async ({ page, request }) => {
  const fila = await cargar(page, "conflicto");
  let alterada = false;
  const estados = [];
  await page.route("**/familia-ostel/**", async (route) => {
    const respuesta = await fetchReal(route);
    if (route.request().method() === "GET" && !alterada) {
      alterada = true;
      const propuesta = await respuesta.json();
      const headers = await route.request().allHeaders();
      const cambio = await request.patch(`${base}padron/${propuesta.titular}/`, { headers, data: {
        revision: propuesta.revision_titular, motivo: "Revisión ficticia concurrente", telefono: `Línea ficticia ${Date.now()}`,
      } });
      expect(cambio.status()).toBe(200);
    } else if (route.request().method() === "POST") estados.push(respuesta.status());
    await route.fulfill({ response: respuesta });
  });
  await fila.getByRole("button", { name: "Vincular familia", exact: true }).click();
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  await expect(dialogo.getByRole("alert")).toContainText("Consulte nuevamente");
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toHaveCount(0);
  expect(estados).toEqual([409]);
  await dialogo.getByRole("button", { name: "Consultar propuesta", exact: true }).click();
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  await expect(dialogo.getByRole("status").filter({ hasText: "Vínculo confirmado" })).toBeVisible();
  expect(estados).toEqual([409, 200]);
});

test("respuesta perdida conserva incertidumbre y recuperación explícita idempotente", async ({ page }) => {
  const fila = await cargar(page, "perdida");
  const guardados = [];
  await page.route("**/familia-ostel/**", async (route) => {
    const respuesta = await fetchReal(route);
    if (route.request().method() === "POST") {
      guardados.push(await respuesta.json());
      if (guardados.length === 1) return route.abort("connectionreset");
    }
    await route.fulfill({ response: respuesta });
  });
  await fila.getByRole("button", { name: "Vincular familia", exact: true }).click();
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  await expect(dialogo.getByRole("alert")).toContainText("puede haberse registrado");
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toHaveCount(0);
  expect(guardados).toHaveLength(1);
  expect(guardados[0].titular).toBeTruthy();
  await dialogo.getByRole("button", { name: "Consultar propuesta", exact: true }).click();
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  await expect(dialogo.getByRole("status").filter({ hasText: "Vínculo confirmado" })).toBeVisible();
  expect(guardados).toHaveLength(2);
  expect(guardados[1].revision).toBe(guardados[0].revision);
});

test("móvil y teclado mantienen el diálogo acotado y devuelven el foco", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fila = await cargar(page, "movil");
  const abrir = fila.getByRole("button", { name: "Vincular familia", exact: true });
  await abrir.click();
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  await expect(dialogo.getByText("Titular ficticio movil", { exact: true })).toBeVisible();
  const caja = await dialogo.boundingBox();
  expect(caja.x).toBeGreaterThanOrEqual(0);
  expect(caja.x + caja.width).toBeLessThanOrEqual(390);
  await expect(dialogo.getByText(/CUIL/)).toHaveCount(0);
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    expect(await dialogo.evaluate((el) => el.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(abrir).toBeFocused();
  await expect(page.getByRole("dialog", { name: "Importar padrón", exact: true })).toBeVisible();
});

test("petición pendiente conserva contexto y un 403 descarta la propuesta sin reintento", async ({ page }) => {
  const fila = await cargar(page, "normal");
  let liberar, informar, esperado;
  const espera = new Promise((resolve) => { liberar = resolve; });
  const recibido = new Promise((resolve) => { informar = resolve; });
  const pedidos = [];
  await page.route("**/familia-ostel/**", async (route) => {
    if (route.request().method() === "GET") {
      const respuesta = await fetchReal(route);
      const query = new URL(route.request().url()).searchParams;
      esperado = { importacion: Number(query.get("importacion")), fila: Number(query.get("fila")), ...await respuesta.json() };
      await route.fulfill({ response: respuesta });
    } else {
      pedidos.push(route.request().postDataJSON());
      informar();
      await espera;
      await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Permiso ficticio denegado" }) });
    }
  });
  const abrir = fila.getByRole("button", { name: "Vincular familia", exact: true });
  await abrir.click();
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  await dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true }).click();
  await recibido;
  try {
    expect(pedidos).toEqual([esperado]);
    await expect(dialogo.getByRole("button", { name: "Cancelar", exact: true })).toBeDisabled();
    await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(dialogo).toBeVisible();
    await expect(page.getByLabel("Formato del archivo", { exact: true })).toBeDisabled();
  } finally { liberar(); }
  await expect(dialogo.getByRole("alert")).toContainText("Consulte nuevamente");
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toHaveCount(0);
  expect(pedidos).toHaveLength(1);
  await dialogo.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(dialogo).toHaveCount(0);
  await abrir.click();
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toBeEnabled();
  expect(pedidos).toHaveLength(1);
});

test("consulta pendiente bloquea cierre y cancelar permite consultar nuevamente", async ({ page }) => {
  const fila = await cargar(page, "movil");
  let liberar, consultas = 0;
  const espera = new Promise((resolve) => { liberar = resolve; });
  await page.route("**/familia-ostel/**", async (route) => {
    consultas++;
    await espera; // Incluye todos los GET iniciales duplicados por StrictMode.
    await route.fulfill({ response: await fetchReal(route) });
  });
  const abrir = fila.getByRole("button", { name: "Vincular familia", exact: true });
  await abrir.click();
  const dialogo = page.getByRole("dialog", { name: "Vincular familia OSTEL", exact: true });
  try {
    await expect(dialogo.getByRole("button", { name: "Cancelar", exact: true })).toBeDisabled();
    await page.keyboard.press("Escape");
    await expect(dialogo).toBeVisible();
  } finally { liberar(); }
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(dialogo).toHaveCount(0);
  const previas = consultas;
  await abrir.click();
  await expect(dialogo.getByRole("button", { name: "Confirmar vínculo", exact: true })).toBeEnabled();
  expect(consultas).toBeGreaterThan(previas);
});
