import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * Diseñador de flujos: operación del lienzo.
 *
 * Es la pantalla que sostiene la promesa del producto («el proceso se
 * configura, no se programa»), y hasta ahora no tenía ninguna cobertura. El
 * primer test existe porque el zoom con rueda estuvo roto sin dar ningún error:
 * el listener se enganchaba en un `useEffect` que corría mientras el flujo
 * todavía cargaba, con el contenedor del lienzo sin existir.
 */
test.describe("Diseñador de flujos", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await page.goto("/flujos");
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/flujos\/\d+/);
    // El lienzo está listo cuando hay nodos dibujados.
    await expect(page.locator("[data-nodo]").first()).toBeVisible();
  });

  /** Escala del lienzo y scroll de su contenedor, leídos del DOM real. */
  const estado = (page) =>
    page.evaluate(() => {
      const cont = [...document.querySelectorAll("div")].find(
        (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
      );
      const capa = document.querySelector("[data-lienzo]");
      const m = capa && getComputedStyle(capa).transform.match(/matrix\(([\d.]+)/);
      const caja = cont.getBoundingClientRect();
      return {
        zoom: m ? +m[1] : null,
        sx: Math.round(cont.scrollLeft),
        sy: Math.round(cont.scrollTop),
        cx: caja.left + caja.width / 2,
        cy: caja.top + caja.height / 2,
      };
    });

  test("la rueda acerca y aleja el lienzo", async ({ page }) => {
    const inicial = await estado(page);
    expect(inicial.zoom).toBeCloseTo(1, 1);

    await page.mouse.move(inicial.cx, inicial.cy);
    await page.mouse.wheel(0, -300);
    await expect.poll(async () => (await estado(page)).zoom).toBeGreaterThan(inicial.zoom);

    await page.mouse.wheel(0, 600);
    await expect.poll(async () => (await estado(page)).zoom).toBeLessThan(inicial.zoom);
  });

  test("el zoom queda anclado al cursor", async ({ page }) => {
    /*
     * Sin ancla, acercarse a un nodo del medio del lienzo lo manda fuera de la
     * pantalla y hay que volver a buscarlo. Con ancla, el punto bajo el mouse se
     * queda donde está — y eso se nota en que el scroll acompaña al zoom.
     */
    const inicial = await estado(page);
    await page.mouse.move(inicial.cx, inicial.cy);
    await page.mouse.wheel(0, -300);

    await expect.poll(async () => (await estado(page)).sx).toBeGreaterThan(0);
    const final = await estado(page);
    expect(final.sy).toBeGreaterThan(0);
  });

  test("Ctrl+F busca un nodo y lo trae al centro", async ({ page }) => {
    const antes = await estado(page);

    await page.keyboard.press("Control+f");
    const buscador = page.getByLabel("Buscar un nodo del flujo");
    await expect(buscador).toBeFocused();

    // Un término que exista en cualquier flujo sembrado.
    await buscador.fill("aten");
    await expect(page.getByRole("button", { name: /Atenci/i }).first()).toBeVisible();

    await page.keyboard.press("Enter");
    // El lienzo se desplaza hacia el nodo elegido.
    await expect.poll(async () => {
      const d = await estado(page);
      return d.sx !== antes.sx || d.sy !== antes.sy;
    }).toBe(true);
  });

  test("Escape cierra el buscador sin tocar el lienzo", async ({ page }) => {
    const antes = await estado(page);
    await page.keyboard.press("Control+f");
    await expect(page.getByLabel("Buscar un nodo del flujo")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByLabel("Buscar un nodo del flujo")).toBeHidden();

    const despues = await estado(page);
    expect([despues.sx, despues.sy]).toEqual([antes.sx, antes.sy]);
  });
});
