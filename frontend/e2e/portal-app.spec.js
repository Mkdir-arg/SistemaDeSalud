import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { desbordaHorizontal } from "./apoyo";

/**
 * App del paciente (#122) contra el backend real (`playwright.portal-app.config.js`).
 *
 * El escenario sale de `seed_portal_e2e`: Andrea Paniagua en Hospital Central,
 * con un turno a más de 24 h, uno a pocas horas, un estudio con archivo, uno
 * pendiente, la cobertura de Mutual del Valle confirmada y un caso de
 * cardiología en la sala de espera. Lo del lado del hospital (ver el turno,
 * llamar desde un box) va por la API institucional, con un usuario del hospital.
 */
const ESCENARIO = process.env.PORTAL_E2E_ESCENARIO;
const E = ESCENARIO ? JSON.parse(readFileSync(ESCENARIO, "utf-8")) : null;
const CLAVE = process.env.DEMO_PASSWORD || "demo1234";
const PROHIBIDOS = [/sacar (un |otro )?turno/i, /reprogram/i, /cambiar d[ií]a u horario/i, /\bQR\b/, /dar presente/i, /notificaci/i, /Clínica Modelo/];

test.skip(!E, "Falta PORTAL_E2E_ESCENARIO (el JSON de seed_portal_e2e).");
test.describe.configure({ mode: "serial" });

// El ingreso tiene límite de intentos por email: se ingresa por la pantalla una
// sola vez (la primera prueba) y el resto reusa una sesión pedida por la API.
let sesion = null;

async function ingresar(page) {
  if (!sesion) {
    const r = await page.request.post("/api/mi/cuenta/ingresar/", { data: { email: E.email, password: CLAVE } });
    expect(r.ok(), await r.text()).toBeTruthy();
    sesion = await r.json();
  }
  await page.addInitScript(({ access, refresh }) => {
    if (sessionStorage.getItem("hen.portal.access")) return;
    sessionStorage.setItem("hen.portal.access", access);
    sessionStorage.setItem("hen.portal.refresh", refresh);
  }, sesion);
  await page.goto("/mi/inicio");
  await expect(page.getByRole("heading", { name: "Hola, Andrea" })).toBeVisible();
}

async function ingresarPorPantalla(page) {
  await page.goto("/mi/ingresar");
  await page.getByLabel("Email").fill(E.email);
  await page.getByLabel("Contraseña").fill(CLAVE);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL("/mi/inicio");
}

/** Un pedido a la API del hospital con un usuario del hospital (no el token del portal). */
async function hospital(request, metodo, ruta, datos) {
  const token = await request.post("/api/auth/token/", { data: { email: E.llama, password: CLAVE } });
  expect(token.ok()).toBeTruthy();
  const { access } = await token.json();
  const r = await request[metodo](`/api${ruta}`, { data: datos, headers: { Authorization: `Bearer ${access}` } });
  expect(r.ok(), await r.text()).toBeTruthy();
  return r.json();
}

async function sinLoQueNoHay(page) {
  const texto = await page.locator("body").innerText();
  for (const patron of PROHIBIDOS) expect(texto, `no debería aparecer ${patron}`).not.toMatch(patron);
  expect(await desbordaHorizontal(page)).toBe(false);
}

test("entra y ve sus turnos, estudios y cobertura con la institución real", async ({ page }) => {
  await ingresarPorPantalla(page);
  await expect(page.getByRole("heading", { name: "Hola, Andrea" })).toBeVisible();
  await expect(page.getByLabel("Tu próximo turno")).toContainText("Hospital Central");
  await sinLoQueNoHay(page);

  await page.goto("/mi/turnos");
  // El cercano no se toca en ninguna prueba: el otro puede estar ya cancelado.
  await expect(page.locator(`a[href="/mi/turnos/${E.turno_cercano}"]`)).toContainText("Hospital Central");
  await sinLoQueNoHay(page);

  await page.goto("/mi/estudios");
  await expect(page.getByText("Hemograma completo")).toBeVisible();
  await expect(page.getByText(/Solicitado el \d{2}\/\d{2}, todavía sin resultado/)).toBeVisible();
  await expect(page.getByText("Normal", { exact: true })).toBeVisible();
  await sinLoQueNoHay(page);

  await page.goto("/mi/cobertura");
  await expect(page.getByText("Mutual del Valle")).toBeVisible();
  await expect(page.getByText("MV00011")).toBeVisible();
  await expect(page.getByText("Plan Integral", { exact: false })).toBeVisible();
  await expect(page.getByText("Confirmada por tu institución")).toBeVisible();
  await sinLoQueNoHay(page);

  await page.goto("/mi/cuenta");
  await expect(page.getByText("FIC199001")).toBeVisible();
  await sinLoQueNoHay(page);
});

test("un turno a menos de 24 horas no se puede cancelar y dice por qué", async ({ page }) => {
  await ingresar(page);
  await page.goto(`/mi/turnos/${E.turno_cercano}`);
  await expect(page.getByText(/Faltan menos de 24 horas/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancelar turno" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Agregar al calendario" })).toBeVisible();
});

test("descarga el archivo real del estudio", async ({ page }) => {
  await ingresar(page);
  await page.goto("/mi/estudios");
  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar Hemograma completo" }).click();
  const archivo = await descarga;
  expect(archivo.suggestedFilename()).toMatch(/^hemograma-\d{4}-\d{2}-\d{2}\.pdf$/);
  const contenido = readFileSync(await archivo.path());
  expect(contenido.subarray(0, 5).toString()).toBe("%PDF-");
  // Es el que sembró el backend, no uno armado en el navegador.
  expect(contenido.toString("latin1")).toContain("DOCUMENTO FICTICIO DE DEMOSTRACI");
});

test("el llamado de un box aparece en menos de 10 segundos sin recargar @modifica", async ({ page, request }) => {
  await ingresar(page);
  await page.goto("/mi/llamado");
  await expect(page.getByText("Estás en la sala de espera")).toBeVisible();
  await hospital(request, "post", `/casos/${E.caso}/llamar/`, { box_id: E.box });
  await expect(page.getByRole("alert")).toContainText("Te están llamando", { timeout: 10000 });
  await expect(page.getByRole("alert")).toContainText("Box 1");
  await expect(page.getByRole("alert")).toContainText("Hospital Central");
});

test("confirma un turno y el hospital lo ve confirmado por el paciente @modifica", async ({ page, request, browser }) => {
  await ingresar(page);
  await page.goto(`/mi/turnos/${E.turno_cancelable}`);
  await page.getByRole("button", { name: "Confirmar asistencia" }).click();
  await expect(page.getByText("Confirmaste tu asistencia")).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirmar asistencia" })).toHaveCount(0);

  const turno = await hospital(request, "get", `/turnos/${E.turno_cancelable}/`);
  expect([turno.estado, turno.confirmado_via]).toEqual(["confirmado", "portal"]);

  await page.reload();
  await expect(page.getByText("Confirmaste tu asistencia")).toBeVisible();

  // Y en la agenda del hospital, como la ve la administrativa: otra ventana,
  // con la sesión del sistema.
  const ventana = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" });
  const agenda = await ventana.newPage();
  await agenda.goto("/login");
  await agenda.fill('input[type="email"]', "admin@salud.local");
  await agenda.fill('input[type="password"]', CLAVE);
  await agenda.click('button[type="submit"]');
  await agenda.getByRole("row", { name: /Hospital Central/ }).getByRole("button", { name: /Ingresar/ }).click();
  await agenda.waitForURL(/\/inicio/);
  const dia = new Date(turno.inicio).toLocaleDateString("sv-SE", { timeZone: "America/Argentina/Buenos_Aires" });
  await agenda.goto(`/agenda?agenda=${turno.agenda}&fecha=${dia}&vista=dia`);
  await expect(agenda.getByText("Confirmado por el paciente").first()).toBeVisible();
  await ventana.close();
});

test("cancela un turno a más de 24 horas @modifica", async ({ page, request }) => {
  await ingresar(page);
  await page.goto(`/mi/turnos/${E.turno_cancelable}`);
  await page.getByRole("button", { name: "Cancelar turno" }).click();
  const dialogo = page.getByRole("dialog", { name: /^¿Cancelar tu turno de / });
  await expect(dialogo).toContainText("Hospital Central");
  await dialogo.getByRole("button", { name: "Sí, cancelar turno" }).click();
  await expect(page).toHaveURL("/mi/turnos");
  await expect(page.getByText("Cancelaste tu turno.")).toBeVisible();

  const turno = await hospital(request, "get", `/turnos/${E.turno_cancelable}/`);
  expect([turno.estado, turno.cancelado_via]).toEqual(["cancelado", "portal"]);
});

test("sin red muestra el error y deja reintentar", async ({ page }) => {
  await ingresar(page);
  let cortado = true;
  await page.route("**/api/mi/turnos/", (ruta) => (cortado ? ruta.abort("internetdisconnected") : ruta.fallback()));
  await page.goto("/mi/turnos");
  await expect(page.getByText("No pudimos cargar tus turnos.")).toBeVisible();
  cortado = false;
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.locator(`a[href="/mi/turnos/${E.turno_cercano}"]`)).toBeVisible();
});

test("sin estudios ni cobertura lo dice", async ({ page }) => {
  await ingresar(page);
  // El backend real siempre tiene datos para esta paciente: el vacío se fuerza acá.
  await page.route("**/api/mi/resultados/", (ruta) => ruta.fulfill({ json: { resultados: [] } }));
  await page.route("**/api/mi/cobertura/", (ruta) => ruta.fulfill({ json: { coberturas: [] } }));
  await page.goto("/mi/estudios");
  await expect(page.getByText("Todavía no tenés estudios")).toBeVisible();
  await page.goto("/mi/cobertura");
  await expect(page.getByText("No encontramos una cobertura vigente")).toBeVisible();
});

test("con la sesión vencida vuelve a ingresar", async ({ page }) => {
  await ingresar(page);
  await page.evaluate(() => {
    sessionStorage.setItem("hen.portal.access", "hp_vencido");
    sessionStorage.setItem("hen.portal.refresh", "hp_vencido");
  });
  await page.goto("/mi/turnos");
  await expect(page).toHaveURL("/mi/ingresar");
  await expect(page.getByText("Tu sesión venció. Ingresá de nuevo.")).toBeVisible();
});

test("la maqueta vieja lleva al portal", async ({ page }) => {
  await page.goto("/demo/app-clinica/turnos");
  await expect(page).toHaveURL("/mi");
});
