import { expect, test } from "@playwright/test";

import { esperarPantalla } from "./apoyo";

const AGENDA = "Dra. Suárez · Cardiología";
const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
const hoy = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const diaHoy = DIAS[(new Date().getDay() + 6) % 7];

async function entrarComo(page, email, pass = "demo1234") {
  await page.goto("/login");
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', pass);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  const ingresar = page.getByRole("button", { name: /Ingresar/ }).first();
  await Promise.race([
    page.waitForURL(/\/inicio/).catch(() => {}),
    ingresar.waitFor({ state: "visible" }).catch(() => {}),
  ]);
  if (await ingresar.isVisible().catch(() => false)) {
    const fila = page.locator("tr", { hasText: "Hospital Central" }).first();
    await fila.getByRole("button", { name: /Ingresar/ }).click();
  }
  await page.waitForURL(/\/inicio/);
}

test("A · crear la agenda y cargarle una franja", async ({ page }) => {
  test.setTimeout(120_000);
  await entrarComo(page, "admin@cauce.local", "admin1234");
  await page.goto("/estructura");
  await esperarPantalla(page);

  await page.getByText("Cardiología", { exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "Cardiología" })).toBeVisible();
  await page.getByRole("tab", { name: "Agendas" }).click();

  const yaEsta = await page.getByText(AGENDA, { exact: true }).isVisible().catch(() => false);
  if (!yaEsta) {
    await page.getByRole("button", { name: /Crear agenda/ }).click();
    await page.getByPlaceholder("Dra. Suárez, o Tomógrafo").fill(AGENDA);
    await page.getByLabel("Profesional", { exact: true }).selectOption({ label: "Laura Méndez" });
    await page.getByLabel("Flujo que se abre al presentarse").selectOption({ label: "Atención cardiológica" });
    await page.getByLabel("Duración del turno (min)").fill("20");
    await page.getByLabel("Sobreturnos por horario").fill("2");
    await page.getByRole("button", { name: "Crear", exact: true }).click();
    await expect(page.getByText("Agenda creada.")).toBeVisible();
  }

  const tarjeta = page.locator("div").filter({ hasText: AGENDA }).last();
  await expect(page.getByText(AGENDA, { exact: true })).toBeVisible();
  await page.screenshot({ path: "e2e/_tmp_c7_A1.png", fullPage: true });

  // Franjas
  const card = page.locator("div").filter({ has: page.getByText(AGENDA, { exact: true }) }).last();
  await card.getByRole("button", { name: /^Horarios \(/ }).click();
  await expect(page.getByRole("heading", { name: `Horarios · ${AGENDA}` })).toBeVisible();

  const yaFranja = await page.getByText(`${diaHoy} de 14:00 a 18:00`).isVisible().catch(() => false);
  if (!yaFranja) {
    await page.getByLabel("Día", { exact: true }).selectOption({ label: diaHoy });
    await page.getByLabel("Desde").fill("14:00");
    await page.getByLabel("Hasta").fill("18:00");
    await expect(page.getByText("Genera 12 turnos de 20 min.")).toBeVisible();
    await page.getByRole("button", { name: "Agregar", exact: true }).click();
    await expect(page.getByText("Franja agregada.")).toBeVisible();
  }
  await expect(page.getByText(new RegExp(`${diaHoy} de 14:00 a 18:00`))).toBeVisible();
  await page.screenshot({ path: "e2e/_tmp_c7_A2.png", fullPage: true });
  await page.getByRole("button", { name: "Listo" }).click();
  console.log("HOY", hoy, "DIA", diaHoy);
});
