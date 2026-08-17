/** Caso 7 · Turnos programados. Temporal: borrar al terminar. */
import { test, expect } from "@playwright/test";
import { esperarPantalla } from "./apoyo.js";

const AGENDA = "Consultorio de Prueba · Cardiología";

async function login(page, email, pass = "demo1234") {
  await page.goto("/login");
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', pass);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  const btn = page.getByRole("button", { name: /Ingresar/ }).first();
  await Promise.race([
    page.waitForURL(/\/inicio/).catch(() => {}),
    btn.waitFor({ state: "visible" }).catch(() => {}),
  ]);
  if (await btn.isVisible().catch(() => false)) {
    // Elegir Hospital Central en el directorio de plataforma.
    await page.getByRole("row", { name: /Hospital Central/ })
      .getByRole("button", { name: /Ingresar/ }).click();
  }
  await page.waitForURL(/\/inicio/);
  await esperarPantalla(page);
}

test("A · crear la agenda y sus franjas", async ({ page }) => {
  test.setTimeout(180_000);
  await login(page, "admin@cauce.local", "admin1234");

  await page.locator("aside").getByRole("link", { name: "Estructura organizativa", exact: true }).click();
  await esperarPantalla(page);
  await page.screenshot({ path: "e2e/_tmp_A1.png", fullPage: true });

  await page.getByText("Cardiología", { exact: true }).first().click();
  await esperarPantalla(page);

  await page.getByRole("tab", { name: "Agendas" }).click();
  await page.screenshot({ path: "e2e/_tmp_A3.png", fullPage: true });

  await page.getByRole("button", { name: "Crear agenda" }).click();
  await page.getByLabel("Nombre").fill(AGENDA);
  await page.getByLabel("Tipo").selectOption("profesional");
  await page.getByLabel("Profesional", { exact: true }).selectOption({ label: "Laura Méndez" });
  await page.getByLabel("Flujo que se abre al presentarse").selectOption({ label: "Atención cardiológica" });
  await page.getByLabel("Duración del turno (min)").fill("20");
  await page.getByLabel("Sobreturnos por horario").fill("2");
  await page.screenshot({ path: "e2e/_tmp_A4.png", fullPage: true });
  await page.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page.getByText("Agenda creada.")).toBeVisible();

  // Franjas: lunes 09–11 (hoy) y martes 09–11 (mañana).
  await page.getByRole("button", { name: /Horarios \(/ }).last().click();
  for (const [dia, desde, hasta] of [["Lunes", "09:00", "11:00"], ["Martes", "09:00", "11:00"]]) {
    await page.getByLabel("Día").selectOption({ label: dia });
    await page.getByLabel("Desde").fill(desde);
    await page.getByLabel("Hasta").fill(hasta);
    await page.screenshot({ path: `e2e/_tmp_A5_${dia}.png`, fullPage: true });
    await page.getByRole("button", { name: "Agregar", exact: true }).click();
    await expect(page.getByText("Franja agregada.")).toBeVisible();
  }
  await page.screenshot({ path: "e2e/_tmp_A6.png", fullPage: true });
  await page.getByRole("button", { name: "Listo" }).click();
  await page.screenshot({ path: "e2e/_tmp_A7.png", fullPage: true });
});
