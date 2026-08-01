import { expect, test } from "@playwright/test";

import { entrar, fallosDeContraste, fijarTema } from "./apoyo";

/**
 * Solo las pantallas ya migradas a la fundación nueva.
 *
 * Las que siguen con estilos inline usan la escala literal, que no cambia con el
 * tema y cuyo gris más claro no llega a AA: exigirles contraste ahora sería un
 * test rojo permanente que no informa nada. **Esta lista crece con cada pantalla
 * que se migra** — agregarla acá es parte de darla por terminada.
 */
const PANTALLAS = ["/filas", "/casos", "/supervision", "/notificaciones", "/bandeja", "/inicio"];

/** Rutas con parámetro: se resuelven en el momento contra datos reales. */
const DINAMICAS = [
  { nombre: "detalle de caso", resolver: async (page) => {
    await page.goto("/casos");
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/casos\/\d+/);
    return page.url();
  } },
];

test.describe("Tema", () => {
  test.beforeEach(async ({ page }) => {
    // El jefe de área es quien ve las tres pantallas de la lista: tiene trabajo,
    // registros y supervisión.
    await entrar(page, "jefe");
  });

  test("el conmutador cambia el tema y lo recuerda", async ({ page }) => {
    await page.goto("/filas");
    const esOscuro = () => page.evaluate(() => document.documentElement.classList.contains("dark"));

    await page.getByRole("button", { name: "Cambiar a tema oscuro" }).click();
    await expect.poll(esOscuro).toBe(true);

    await page.reload();
    // Se comprueba apenas carga el DOM: la clase la tiene que poner el script del
    // <head>, no React. Si dependiera de React habría un fogonazo blanco.
    expect(await esOscuro()).toBe(true);

    await page.getByRole("button", { name: "Cambiar a tema claro" }).click();
    await expect.poll(esOscuro).toBe(false);
  });

  test("en oscuro las superficies son más claras que el fondo", async ({ page }) => {
    await page.goto("/filas");
    await fijarTema(page, "oscuro");
    const { fondo, superficie } = await page.evaluate(() => ({
      fondo: getComputedStyle(document.body).backgroundColor,
      superficie: getComputedStyle(document.querySelector("section")).backgroundColor,
    }));
    const claridad = (rgb) => rgb.match(/\d+/g).slice(0, 3).reduce((a, b) => a + Number(b), 0);
    expect(claridad(fondo)).toBeLessThan(120); // realmente oscuro
    expect(claridad(superficie)).toBeGreaterThan(claridad(fondo)); // elevación correcta
  });

  // El contraste es requisito de pliego en licitación pública. Que sea un test
  // que falla y no algo que alguien tiene que acordarse de revisar.
  for (const tema of ["claro", "oscuro"]) {
    for (const ruta of PANTALLAS) {
      test(`sin fallos de contraste AA en ${ruta} (${tema})`, async ({ page }) => {
        await page.goto(ruta);
        await fijarTema(page, tema);
        const fallos = await fallosDeContraste(page);
        expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
      });
    }

    for (const { nombre, resolver } of DINAMICAS) {
      test(`sin fallos de contraste AA en ${nombre} (${tema})`, async ({ page }) => {
        await resolver(page);
        await fijarTema(page, tema);
        const fallos = await fallosDeContraste(page);
        expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
      });
    }
  }
});

/** Pantallas que requieren la capacidad `config`, así que las mira el super admin. */
test.describe("Tema · pantallas de configuración", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
  });

  for (const tema of ["claro", "oscuro"]) {
    test(`sin fallos de contraste AA en /dashboard (${tema})`, async ({ page }) => {
      await page.goto("/dashboard");
      await fijarTema(page, tema);
      const fallos = await fallosDeContraste(page);
      expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
    });
  }
});
