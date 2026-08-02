import { expect, test } from "@playwright/test";

import { desbordaHorizontal, entrarPlataforma, fallosDeContraste } from "./apoyo";

/**
 * Directorio de plataforma: lo que ve el super admin antes de entrar a una
 * institución. Tiene su propio armazón, así que no lo cubre `shell.spec.js`.
 */
test.describe("Directorio de plataforma", () => {
  test.beforeEach(async ({ page }) => {
    await entrarPlataforma(page);
  });

  test("lista instituciones y deja entrar a una", async ({ page }) => {
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await page.getByRole("button", { name: /Ingresar/ }).first().click();
    await page.waitForURL(/\/inicio/);
  });

  /**
   * El buscador tiene que consultar al SERVIDOR, no filtrar la página que ya
   * está en pantalla. Es el error que esta pantalla tenía —y que ya había
   * aparecido en otras tres—: con la API paginando de a 25, filtrar en el cliente
   * busca solo dentro de esas 25 y el resto no existe.
   */
  test("el buscador filtra contra el servidor", async ({ page }) => {
    const pedidos = [];
    page.on("request", (r) => {
      const u = new URL(r.url());
      if (u.pathname.includes("/instituciones/") && u.searchParams.has("search")) {
        pedidos.push(u.searchParams.get("search"));
      }
    });

    await page.getByLabel("Buscar institución").fill("zzzz-no-existe");
    await expect(page.getByText("Ninguna institución coincide")).toBeVisible();

    expect(pedidos).toContain("zzzz-no-existe");
    // Y queda en la URL, así que la búsqueda se puede compartir y sobrevive a F5.
    await expect(page).toHaveURL(/q=zzzz-no-existe/);
  });

  test("el total del subtítulo es el del servidor, no el de la página", async ({ page }) => {
    const porApi = await page.evaluate(async () => {
      const r = await fetch("/api/instituciones/?page_size=1", {
        headers: { Authorization: `Bearer ${localStorage.getItem("cauce.access")}` },
      });
      return (await r.json()).count;
    });
    const palabra = porApi === 1 ? "institución" : "instituciones";
    await expect(page.getByText(`${porApi} ${palabra} en la plataforma`)).toBeVisible();
  });

  test("la vista queda en la URL", async ({ page }) => {
    await page.getByRole("button", { name: "Usuarios" }).click();
    await expect(page).toHaveURL(/vista=usuarios/);
    await expect(page.getByRole("heading", { name: "Usuarios" })).toBeVisible();

    // Y al recargar sigue en la misma vista.
    await page.reload();
    await expect(page.getByRole("heading", { name: "Usuarios" })).toBeVisible();
  });

  test("no desborda en horizontal en ningún ancho", async ({ page }) => {
    for (const width of [1440, 1024]) {
      await page.setViewportSize({ width, height: 800 });
      await expect.poll(() => desbordaHorizontal(page)).toBe(false);
    }
  });

  for (const tema of ["claro", "oscuro"]) {
    test(`sin fallos de contraste AA (${tema})`, async ({ page }) => {
      await page.evaluate((t) => localStorage.setItem("cauce.tema", t), tema);
      await page.reload();
      await expect(page.getByRole("heading", { name: "Instituciones" })).toBeVisible();
      await expect(page.locator('[role="status"]')).toHaveCount(0);

      const fallos = await fallosDeContraste(page);
      expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
    });
  }
});
