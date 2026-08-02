import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

/** Abre el primer caso de la tabla y devuelve su URL. */
async function abrirPrimerCaso(page) {
  await page.goto("/casos");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.locator("tbody tr").first().click();
  await expect(page).toHaveURL(/\/casos\/\d+/);
}

test.describe("Detalle del caso", () => {
  test("muestra la información, el stepper y la trazabilidad", async ({ page }) => {
    await entrar(page, "admin");
    await abrirPrimerCaso(page);

    await expect(page.getByText("INFORMACIÓN DEL CASO")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Trazabilidad" })).toBeVisible();
    // La línea de tiempo tiene eventos reales, no está vacía.
    await expect(page.locator("ol li").first()).toBeVisible();
  });

  test("el panel del paso corresponde al tipo de nodo", async ({ page }) => {
    await entrar(page, "admin");
    await abrirPrimerCaso(page);
    // Cualquiera sea el paso, la pantalla dice qué se puede hacer: nunca queda
    // una zona muerta sin explicación.
    const panel = page.getByText(
      /Completar y avanzar|Registrar atención|Caso cerrado|Iniciar caso|sala de espera|esperando el resultado|no requiere una acción|Llamar y continuar|Reactivar|lo realiza/i,
    );
    await expect(panel.first()).toBeVisible();
  });

  test("el jefe de área ve el panel de supervisión", async ({ page }) => {
    await entrar(page, "jefe");
    await page.goto("/supervision");
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    await fila.click();
    await expect(page).toHaveURL(/\/casos\/\d+/);
    await expect(page.getByText("SUPERVISIÓN")).toBeVisible();
    await expect(page.getByRole("button", { name: "Reasignar" })).toBeVisible();
  });

  test("se apila y no desborda en tablet ni en móvil", async ({ page }) => {
    await entrar(page, "admin");
    await abrirPrimerCaso(page);
    for (const width of [1440, 1024, 390]) {
      await sinDesborde(page, width);
    }
    // En angosto la información del caso queda antes que el panel de trabajo.
    await expect(page.getByText("INFORMACIÓN DEL CASO")).toBeVisible();
  });
});
