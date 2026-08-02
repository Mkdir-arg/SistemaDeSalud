import { expect, test } from "@playwright/test";

import { desbordaHorizontal, entrar } from "./apoyo";

const asideVisible = (page) =>
  page.evaluate(() => {
    const a = document.querySelector("aside");
    return !!a && a.getBoundingClientRect().right > 1;
  });

/** El marco de todas las pantallas: si se rompe, se rompe todo. */
test.describe("Shell", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "medico");
    await page.goto("/filas");
    await expect(page.locator("aside")).toBeAttached();
  });

  test("en escritorio la barra lateral colapsa y se expande", async ({ page }) => {
    const ancho = () => page.$eval("aside", (a) => a.getBoundingClientRect().width);
    const expandida = await ancho();
    await page.getByRole("button", { name: "Colapsar menú" }).click();
    await expect.poll(ancho).toBeLessThan(expandida);
    await page.getByRole("button", { name: "Expandir menú" }).click();
    await expect.poll(ancho).toBe(expandida);
  });

  test("en tablet sigue siendo barra lateral", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    // `expect.poll` en vez de un temporizador: el relayout puede tardar más de
    // 400 ms bajo carga y ahí el test falla por el reloj, no por la pantalla.
    await expect.poll(() => asideVisible(page)).toBe(true);
    await expect.poll(() => desbordaHorizontal(page)).toBe(false);
  });

  test.describe("en móvil el menú es un cajón", () => {
    test.beforeEach(async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      // La barra lateral tiene que haber desaparecido: ésa es la señal de que el
      // layout móvil ya se aplicó, y es mucho más confiable que un temporizador.
      await expect.poll(() => asideVisible(page)).toBe(false);
    });

    test("arranca oculto y no desborda", async ({ page }) => {
      expect(await desbordaHorizontal(page)).toBe(false);
      expect(await asideVisible(page)).toBe(false);
    });

    test("la hamburguesa lo abre con el menú completo", async ({ page }) => {
      await page.getByRole("button", { name: "Abrir menú" }).click();
      await expect.poll(() => asideVisible(page)).toBe(true);
      // Completo, no una columna de iconos: aunque el menú esté colapsado en
      // escritorio, en el cajón se muestra entero.
      await expect(page.locator("aside").getByText("Historia clínica")).toBeVisible();
    });

    test("Escape lo cierra", async ({ page }) => {
      await page.getByRole("button", { name: "Abrir menú" }).click();
      await expect.poll(() => asideVisible(page)).toBe(true);
      await page.keyboard.press("Escape");
      await expect.poll(() => asideVisible(page)).toBe(false);
    });

    test("al navegar se cierra solo", async ({ page }) => {
      await page.getByRole("button", { name: "Abrir menú" }).click();
      await page.locator("aside").getByText("Historia clínica").click();
      await expect(page).toHaveURL(/\/historia/);
      await expect.poll(() => asideVisible(page)).toBe(false);
    });
  });
});
