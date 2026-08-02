import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

/**
 * Supervisión: la vista del jefe de área.
 *
 * Lo que importa cubrir es que el filtrado sea del SERVIDOR. Antes la pantalla
 * pedía todos los casos de la institución y descartaba en el cliente los que no
 * podía supervisar, así que con volumen real filtraba sobre los primeros 25 que
 * devolvía la API y mostraba un puñado arbitrario.
 */
test.describe("Supervisión", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "jefe");
    await page.goto("/supervision");
  });

  test("lista solo casos activos del área, paginados", async ({ page }) => {
    const pie = page.locator("text=/Mostrando .* de |Sin resultados|No hay casos/").first();
    await expect(pie).toBeVisible();

    const texto = await pie.textContent();
    if (/Mostrando/.test(texto)) {
      const total = Number((texto.match(/de\s*(\d+)/) || [])[1] || 0);
      expect(total).toBeGreaterThan(0);
      // Menos que el total del sistema: está acotado al área del jefe.
      expect(total).toBeLessThan(531);
      // Ningún caso cerrado ni cancelado.
      const estados = await page.$$eval("tbody tr td:nth-child(3)", (tds) =>
        tds.map((t) => t.textContent.trim()));
      expect(estados.some((e) => /Cerrado|Cancelado/.test(e))).toBe(false);
    }
  });

  test("se puede cambiar la prioridad sin abrir el caso", async ({ page }) => {
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    const selector = fila.locator("select").first();
    await selector.selectOption("urgente");
    // No navegó: el clic en el control no debe propagarse a la fila.
    await expect(page).toHaveURL(/\/supervision/);
    await expect.poll(() => selector.inputValue()).toBe("urgente");
  });

  test("cancelar pide confirmación y el diálogo dice qué hace", async ({ page }) => {
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    await fila.getByRole("button", { name: "Cancelar" }).click();

    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();
    await expect(dialogo.getByRole("button", { name: "Cancelar el caso" })).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialogo).toBeHidden();
    await expect(page).toHaveURL(/\/supervision/);
  });

  test("no desborda en ningún ancho", async ({ page }) => {
    for (const width of [1440, 1024, 390]) {
      await sinDesborde(page, width);
    }
  });
});
