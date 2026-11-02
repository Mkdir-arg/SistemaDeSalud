import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const datos = JSON.parse(readFileSync(process.env.SALUD_BORRADORES_MANIFEST, "utf8"));
if (datos.escenario !== "borradores-derechos-v1" || !datos.usuarios.admin.endsWith("@example.invalid")) throw new Error("Se requiere fixture ficticia dedicada.");
async function abrir(page, rol = "admin") {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.usuarios[rol]);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(`/financiadores/borradores?financiador=${datos.organizaciones[0]}`);
}

test("administración consulta borradores sin activar derechos", async ({ page }) => {
  await abrir(page);
  await expect(page.getByRole("heading", { name: "Reglas de derechos", exact: true })).toBeVisible();
  await expect(page.getByText("Guardar una versión no aprueba ni activa derechos.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeVisible();
});


test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "wait" }); });
async function completar(page, codigo) {
  await page.getByLabel("Código de regla", { exact: true }).fill(codigo);
  await page.getByLabel("Versión", { exact: true }).fill("1");
  await page.getByRole("combobox", { name: "Régimen", exact: true }).selectOption("dependencia");
  await page.getByLabel("Inicio técnico", { exact: true }).fill("2030-01-01");
  await page.getByLabel("Fuente informada", { exact: true }).fill("Fuente completamente ficticia");
  await page.getByLabel("Fecha de consulta técnica", { exact: true }).fill("2030-01-15");
  await page.getByLabel("Motivo del registro", { exact: true }).fill("Verificación ficticia no operativa");
}
async function guardar(page, codigo) {
  await completar(page, codigo);
  const respuesta = page.waitForResponse((r) => r.url().endsWith("/borradores-derechos/") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  expect((await respuesta).status()).toBe(200);
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true }).locator("..").getByText("Borrador", { exact: true })).toBeVisible();
  await expect(page.getByText("Borrador guardado. Los derechos no cambiaron.", { exact: true })).toBeVisible();
}

test("guarda versión real, conserva historial y navega desde el menú", async ({ page }) => {
  await abrir(page);
  await page.getByRole("link", { name: "Planes", exact: true }).click();
  await page.getByRole("link", { name: "Reglas de derechos", exact: true }).click();
  const codigo = `ficticio-desktop-${Date.now()}`;
  await guardar(page, codigo);
  await page.reload();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Activar|Aprobar/ })).toHaveCount(0);
});

test("consulta de auditor sin formulario de escritura", async ({ page }) => {
  await abrir(page, "auditor");
  await expect(page.getByText("Acceso de consulta. La administración del financiador puede registrar versiones.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Código de regla", { exact: true })).toHaveCount(0);
});

test("móvil y teclado guardan una versión ficticia sin desbordar", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await abrir(page);
  const campo = page.getByLabel("Código de regla", { exact: true });
  await campo.focus(); await page.keyboard.press("Tab");
  await expect(page.getByLabel("Versión", { exact: true })).toBeFocused();
  await guardar(page, `ficticio-movil-${Date.now()}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("respuesta perdida después del commit exige consultar, sin reintento automático", async ({ page }) => {
  await abrir(page);
  let escrituras = 0;
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    escrituras += 1;
    const real = await route.fetch();
    expect(real.status()).toBe(200);
    await route.abort();
  });
  const codigo = `ficticio-perdida-${Date.now()}`;
  await completar(page, codigo);
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("El resultado de una escritura fallida puede ser desconocido");
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  expect(escrituras).toBe(1);
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
  expect(escrituras).toBe(1);
});

test("una consulta anterior no contamina otro financiador", async ({ page }) => {
  await abrir(page);
  const codigo = `ficticio-ambito-${Date.now()}`;
  await guardar(page, codigo);
  let liberar, inicio;
  const espera = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { inicio = r; });
  await page.route(`**/financiadores/${datos.organizaciones[0]}/borradores-derechos/`, async (route) => {
    inicio(); await espera; await route.continue();
  });
  try {
    await page.reload(); await iniciada;
    await page.getByLabel("Financiador", { exact: true }).selectOption(String(datos.organizaciones[1]));
    await expect(page.getByRole("heading", { name: "Nueva versión", exact: true })).toBeVisible();
    const anterior = page.waitForResponse((r) => r.url().includes(`/financiadores/${datos.organizaciones[0]}/borradores-derechos/`));
    liberar(); await anterior;
    await expect(page.getByLabel("Financiador", { exact: true })).toHaveValue(String(datos.organizaciones[1]));
    await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toHaveCount(0);
  } finally { liberar(); }
});


test("doble clic durante POST mantiene una sola escritura", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-doble-${Date.now()}`);
  let liberar, inicio, escrituras = 0;
  const espera = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { inicio = r; });
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    escrituras += 1; inicio(); await espera; await route.continue();
  });
  try {
    await page.getByRole("button", { name: "Guardar borrador", exact: true }).evaluate((boton) => { boton.click(); boton.click(); });
    await iniciada;
    await expect(page.getByRole("button", { name: "Guardando…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Volver a consultar", exact: true })).toBeDisabled();
    expect(escrituras).toBe(1); liberar();
    await expect(page.getByText("Borrador guardado. Los derechos no cambiaron.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
    expect(escrituras).toBe(1);
  } finally { liberar(); }
});

test("403 y recarga fallida bloquean guardar hasta una consulta exitosa", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-403-${Date.now()}`);
  let escrituras = 0, fallaConsulta = false;
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() === "POST") {
      escrituras += 1;
      return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Permiso revocado ficticio" }) });
    }
    if (fallaConsulta) return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    return route.continue();
  });
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Permiso revocado ficticio");
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  fallaConsulta = true;
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByText("No se pudo consultar el historial.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  expect(escrituras).toBe(1); fallaConsulta = false;
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
  expect(escrituras).toBe(1);
});
