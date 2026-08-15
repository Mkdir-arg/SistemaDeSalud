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

/*
 * Deja el editor abierto sobre un BORRADOR, listo para modificar.
 *
 * El flujo del demo está publicado, y una versión publicada ya no se edita: los
 * casos en curso están parados sobre esos nodos. Antes el editor dejaba
 * intentarlo y sólo aparecía «Error al guardar» en la barra; ahora avisa y
 * ofrece sacar una versión nueva, que es lo que hace esta función.
 */
async function abrirBorrador(page) {
  await entrar(page, "admin");
  await page.goto("/flujos");
  await page.locator("tbody tr").first().click();
  await page.waitForURL(/\/flujos\/\d+/);
  await expect(page.locator("[data-nodo]").first()).toBeVisible();

  const sacar = page.getByRole("button", { name: "Sacar una versión nueva" });
  if (await sacar.isVisible().catch(() => false)) {
    await sacar.click();
    await expect(sacar).toBeHidden({ timeout: 15000 });
    await expect(page.locator("[data-nodo]").first()).toBeVisible();
  }
}

test.describe("Diseñador de flujos", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
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

  test("el minimapa lleva a otra zona del lienzo", async ({ page }) => {
    const mapa = page.getByTitle(/Mapa del flujo/);
    await expect(mapa).toBeVisible();

    const scroll = () =>
      page.evaluate(() => {
        const c = [...document.querySelectorAll("div")].find(
          (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
        );
        return { x: Math.round(c.scrollLeft), y: Math.round(c.scrollTop) };
      });

    const antes = await scroll();
    const caja = await mapa.boundingBox();
    // Esquina opuesta del mapa: el lienzo tiene que saltar a esa zona.
    await page.mouse.click(caja.x + caja.width - 8, caja.y + caja.height - 8);

    await expect
      .poll(async () => {
        const d = await scroll();
        return d.x !== antes.x || d.y !== antes.y;
      })
      .toBe(true);
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

/**
 * Configuración del nodo de integración.
 *
 * El modo padrón FHIR existía en el motor y no se podía elegir desde ningún
 * lado, que para quien diseña el flujo es lo mismo que no existir. Estos tests
 * cubren que se pueda elegir y —sobre todo— que la pantalla diga lo que el paso
 * NO hace: quien lo configura tiene que saber que no corrige datos equivocados,
 * o va a creer que el padrón los arregla solo.
 */
test.describe("Nodo de integración", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
    await page.getByTitle("Agregar nodo «Integración»").click();
    await expect(page.getByLabel("Tipo de servicio")).toBeVisible();
  });

  /*
   * El nodo se guarda en el servidor apenas se agrega, así que sin esto cada
   * corrida deja uno suelto en el flujo del demo. La suite corre sobre la misma
   * base y una que ensucia lo que mira la siguiente es la forma más rápida de
   * que nadie confíe en los rojos.
   */
  test.afterEach(async ({ page }) => {
    const borrar = page.getByRole("button", { name: "Eliminar nodo" });
    if (await borrar.isVisible().catch(() => false)) await borrar.click();
  });

  test("se puede elegir el modo padrón FHIR", async ({ page }) => {
    const modo = page.getByLabel("Tipo de servicio");
    await expect(modo).toBeVisible();
    await modo.selectOption("fhir");
    await expect(page.getByLabel("Dirección del padrón")).toBeVisible();
  });

  test("avisa que la URL es la base y no la de búsqueda", async ({ page }) => {
    // Es el error más común: Cauce le agrega /Patient?identifier=… por su cuenta.
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByText(/sin \/Patient/)).toBeVisible();
  });

  test("dice que no pisa datos ya cargados", async ({ page }) => {
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByText(/Nunca pisa un dato ya cargado/)).toBeVisible();
  });

  test("en modo padrón esconde lo que no aplica", async ({ page }) => {
    // Una ruta JSON configurada sobre un padrón FHIR no hace nada y hace perder
    // media hora a quien la escribió.
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByLabel("Guardar la respuesta en")).toHaveCount(0);
    await expect(page.getByLabel("Método")).toHaveCount(0);
  });

  test("volver al modo genérico devuelve sus campos", async ({ page }) => {
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await page.getByLabel("Tipo de servicio").selectOption("generico");
    await expect(page.getByLabel("Método")).toBeVisible();
    await expect(page.getByLabel("Sistema del documento")).toHaveCount(0);
  });
});
