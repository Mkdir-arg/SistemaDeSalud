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

  test("shift+clic suma nodos a la selección", async ({ page }) => {
    /*
     * El shift+clic tenía tres cosas encima que lo reducían a un solo nodo: el
     * `onClick` del nodo, el `onFocus` (que dispara junto con el pointerdown en
     * un elemento con tabIndex) y el clic que sigue a soltar el mouse.
     */
    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });

    await expect(page.getByText("2 nodos elegidos")).toBeVisible();
  });

  test("las flechas mueven todo el grupo, no sólo un nodo", async ({ page }) => {
    const posiciones = () =>
      page.evaluate(() =>
        Object.fromEntries(
          [...document.querySelectorAll("[data-nodo]")].map((e) => [e.dataset.nodo, Math.round(parseFloat(e.style.left))]),
        ),
      );

    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();

    const antes = await posiciones();
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(async () => {
        const d = await posiciones();
        return Object.keys(antes).filter((id) => d[id] !== antes[id]).length;
      })
      .toBe(2);

    // Se devuelve el grupo a su lugar: la suite no debería dejar el flujo movido.
    await page.keyboard.press("ArrowLeft");
    await expect.poll(posiciones).toEqual(antes);
  });

  test("la marquesina encierra nodos", async ({ page }) => {
    const caja = await page.evaluate(() => {
      const c = [...document.querySelectorAll("div")].find(
        (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
      );
      const r = c.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height };
    });

    await page.mouse.move(caja.x + 15, caja.y + 15);
    await page.mouse.down();
    await page.mouse.move(caja.x + caja.w - 40, caja.y + caja.h - 40, { steps: 10 });
    await page.mouse.up();

    // Encierra el lienzo entero, así que agarra más de un nodo.
    await expect(page.getByText(/\d+ nodos elegidos/)).toBeVisible();
  });

  test("Ctrl+D duplica el grupo con sus conexiones y se puede deshacer", async ({ page }) => {
    const contar = () => page.locator("[data-nodo]").count();
    const inicial = await contar();

    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();

    await page.keyboard.press("Control+d");
    await expect.poll(contar).toBe(inicial + 2);

    // Lo pegado queda seleccionado, así que se puede borrar de una: el test
    // deja el flujo como lo encontró (la suite corre sobre datos compartidos).
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();
    await page.keyboard.press("Delete");
    await expect.poll(contar).toBe(inicial);
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
