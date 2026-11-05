import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const datos = JSON.parse(readFileSync(process.env.SALUD_BORRADORES_MANIFEST, "utf8"));
if (datos.escenario !== "borradores-derechos-v1" ||
    !Object.values(datos.usuarios).every((email) => email.endsWith("@example.invalid"))) {
  throw new Error("Se requiere fixture ficticia dedicada.");
}
const etiqueta = "Designar para Auditoría Médica de este financiador";
const designacion = "Designación de Auditoría Médica";
const ruta = `/api/financiadores/${datos.organizaciones[0]}/usuarios/`;

async function abrir(page, rol = "admin") {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.usuarios[rol]);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(`/financiadores/usuarios?financiador=${datos.organizaciones[0]}`);
}

async function guardar(page) {
  const respuesta = page.waitForResponse((r) => new URL(r.url()).pathname === ruta && r.request().method() === "POST");
  await page.getByRole("dialog").getByRole("button", { name: "Guardar", exact: true }).click();
  const r = await respuesta;
  expect(r.status()).toBe(201);
  await expect(page.getByRole("dialog").filter({ hasText: "Cambiar acceso al financiador" })).toHaveCount(0);
  return { body: r.request().postDataJSON(), resultado: await r.json() };
}

test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "wait" }); });

for (const [nombre, viewport] of [["escritorio", { width: 1365, height: 900 }], ["móvil", { width: 390, height: 844 }]]) {
  test(`${nombre}: designa, conserva al cambiar rol y revoca por teclado con persistencia real`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await abrir(page);
    await page.getByRole("button", { name: "Invitar usuario", exact: true }).click();
    const modal = page.getByRole("dialog");
    const control = modal.getByRole("checkbox", { name: etiqueta, exact: true });
    await expect(control).not.toBeChecked();
    const email = `designacion-${nombre === "móvil" ? "movil" : "desktop"}-${Date.now()}@example.invalid`;
    await modal.getByLabel("Correo electrónico", { exact: true }).fill(email);
    await modal.getByLabel("Nombre y apellido", { exact: true }).fill("Designación ficticia");
    await modal.getByRole("combobox", { name: "Rol", exact: true }).selectOption("auditor");
    const creado = await guardar(page);
    expect(creado.body.auditoria_medica).toBe(false);
    expect(creado.resultado.auditoria_medica).toBe(false);
    const fila = page.getByRole("row").filter({ hasText: email });
    await expect(fila.getByText(designacion, { exact: true })).toHaveCount(0);
    await fila.getByRole("button", { name: "Cambiar acceso" }).click();
    await expect(control).not.toBeChecked();
    await control.focus();
    await page.keyboard.press("Space");
    await expect(control).toBeFocused();
    await expect(control).toBeChecked();
    const concedido = await guardar(page);
    expect(concedido.resultado.auditoria_medica).toBe(true);
    expect(concedido.body.resuelve_autorizaciones).toBe(false);
    await expect(fila.getByText(designacion, { exact: true })).toBeVisible();
    await page.reload();
    await fila.getByRole("button", { name: "Cambiar acceso" }).click();
    await expect(control).toBeChecked();
    await modal.getByRole("combobox", { name: "Rol", exact: true }).selectOption("operador");
    expect((await guardar(page)).resultado.auditoria_medica).toBe(true);
    await fila.getByRole("button", { name: "Cambiar acceso" }).click();
    await control.focus();
    await page.keyboard.press("Space");
    expect((await guardar(page)).resultado.auditoria_medica).toBe(false);
    await page.reload();
    await expect(fila.getByText(designacion, { exact: true })).toHaveCount(0);
    await fila.getByRole("button", { name: "Cambiar acceso" }).click();
    await expect(control).not.toBeChecked();
    await modal.getByRole("button", { name: "Cancelar", exact: true }).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("auditoría administrativa no puede gestionar designaciones", async ({ page }) => {
  await abrir(page, "auditor");
  await expect(page).toHaveURL(new RegExp(`/financiadores/inicio\\?financiador=${datos.organizaciones[0]}$`));
  await expect(page.getByRole("button", { name: "Invitar usuario", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cambiar acceso" })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: etiqueta, exact: true })).toHaveCount(0);
});

test("cancelación y cambio de financiador no trasladan una designación pendiente", async ({ page }) => {
  await abrir(page);
  const fila = page.getByRole("row").filter({ hasText: datos.usuarios.auditor });
  await fila.getByRole("button", { name: "Cambiar acceso" }).click();
  const modal = page.getByRole("dialog");
  const control = modal.getByRole("checkbox", { name: etiqueta, exact: true });
  const inicial = await control.isChecked();
  await control.setChecked(!inicial);
  await modal.getByRole("button", { name: "Cancelar", exact: true }).click();
  await fila.getByRole("button", { name: "Cambiar acceso" }).click();
  await expect(control).toBeChecked({ checked: inicial });
  await page.goto(`/financiadores/usuarios?financiador=${datos.organizaciones[1]}`);
  await expect(modal).toHaveCount(0);
  await expect(fila).toBeVisible();
  await fila.getByRole("button", { name: "Cambiar acceso" }).click();
  await expect(control).not.toBeChecked();
  await modal.getByRole("button", { name: "Cancelar", exact: true }).click();
});

test("capacidad falsa inyectada: omite el campo sensible en alta y edición", async ({ page }) => {
  await abrir(page);
  await page.route("**/api/financiadores/**", async (route) => {
    if (new URL(route.request().url()).pathname !== "/api/financiadores/" || route.request().method() !== "GET") return route.continue();
    const respuesta = await route.fetch();
    const data = await respuesta.json();
    for (const org of Array.isArray(data) ? data : data.results) {
      if (org.id === datos.organizaciones[0]) org.gestiona_permisos_padron = false;
    }
    await route.fulfill({ response: respuesta, json: data });
  });
  await page.reload();
  for (const editar of [false, true]) {
    if (editar) await page.getByRole("row").filter({ hasText: datos.usuarios.auditor }).getByRole("button", { name: "Cambiar acceso" }).click();
    else await page.getByRole("button", { name: "Invitar usuario", exact: true }).click();
    const modal = page.getByRole("dialog");
    await expect(modal.getByRole("checkbox", { name: etiqueta, exact: true })).toHaveCount(0);
    if (!editar) {
      await modal.getByLabel("Correo electrónico", { exact: true }).fill(datos.usuarios.auditor);
      await modal.getByLabel("Nombre y apellido", { exact: true }).fill("Persona ficticia");
      await modal.getByRole("combobox", { name: "Rol", exact: true }).selectOption("auditor");
    }
    let body;
    await page.route("**/usuarios/", async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      body = route.request().postDataJSON();
      await route.fulfill({ status: 403, json: { detail: "Rechazo ficticio" } });
    });
    await modal.getByRole("button", { name: "Guardar", exact: true }).click();
    await expect(modal.getByRole("alert")).toContainText("Rechazo ficticio");
    expect(Object.hasOwn(body, "auditoria_medica")).toBe(false);
    expect(body.resuelve_autorizaciones).toBe(false);
    await modal.getByRole("button", { name: "Cancelar", exact: true }).click();
    await page.unroute("**/usuarios/");
  }
});

test("403 inyectado: un intento, error visible y estado real sin cambios", async ({ page }) => {
  await abrir(page);
  const consulta = () => page.waitForResponse((r) => new URL(r.url()).pathname === ruta && r.request().method() === "GET");
  const antes = consulta();
  await page.reload();
  const estado = await (await antes).json();
  const fila = page.getByRole("row").filter({ hasText: datos.usuarios.auditor });
  await fila.getByRole("button", { name: "Cambiar acceso" }).click();
  const modal = page.getByRole("dialog");
  const control = modal.getByRole("checkbox", { name: etiqueta, exact: true });
  const inicial = await control.isChecked();
  await control.setChecked(!inicial);
  let intentos = 0;
  await page.route("**/usuarios/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    intentos += 1;
    await route.fulfill({ status: 403, json: { detail: "Designación denegada ficticia" } });
  });
  await modal.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(modal.getByRole("alert")).toContainText("Designación denegada ficticia");
  expect(intentos).toBe(1);
  await modal.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page.unroute("**/usuarios/");
  const despues = consulta();
  await page.reload();
  expect(await (await despues).json()).toEqual(estado);
  await fila.getByRole("button", { name: "Cambiar acceso" }).click();
  await expect(control).toBeChecked({ checked: inicial });
});
