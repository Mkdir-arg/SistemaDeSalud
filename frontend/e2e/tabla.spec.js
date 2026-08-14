import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

/**
 * La tabla de Casos. Cubre el fallo que motivó construirla: las 17 pantallas
 * leían `results` y mostraban los primeros 25 de la API descartando el resto en
 * silencio (25 de 531, sin forma de llegar al resto).
 */
test.describe("Tabla de casos", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await page.goto("/casos");
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });

  const idsVisibles = (page) =>
    page.$$eval("tbody tr td:first-child", (tds) => tds.map((t) => t.textContent.trim()));

  /**
   * Total de casos según la API, para no clavar un número en el test.
   *
   * Se pide DESDE la página y acotado a la institución en la que está parada.
   * Pedirlo aparte como super admin devuelve los casos de todas las
   * instituciones: con un solo hospital coincidía por casualidad, y al sumar el
   * segundo el test empezó a comparar 570 contra los 528 que la tabla muestra
   * —correctamente— de su institución.
   */
  async function totalDeCasos(page) {
    return page.evaluate(async () => {
      const inst = JSON.parse(localStorage.getItem("cauce.institucion") || "null");
      const r = await fetch(
        `/api/casos/?page_size=1${inst ? `&institucion=${inst.id}` : ""}`,
        { headers: { Authorization: `Bearer ${localStorage.getItem("cauce.access")}` } },
      );
      return (await r.json()).count;
    });
  }

  test("informa el total real y no solo lo que entra en una página", async ({ page }) => {
    // El total se compara contra el que devuelve la API, no contra un número
    // fijo: el seed genera una cantidad que depende de decisiones al azar, y
    // clavarla en el test lo vuelve frágil ante cualquier cambio del generador.
    const total = await totalDeCasos(page);
    expect(total).toBeGreaterThan(100); // la demo tiene volumen

    const pie = page.locator("text=/Mostrando .* de /").first();
    await expect(pie).toContainText(String(total));
    expect(await idsVisibles(page)).toHaveLength(25);
  });

  test("se puede llegar a la segunda página y el estado queda en la URL", async ({ page }) => {
    const primera = await idsVisibles(page);
    await page.getByLabel("Página siguiente").click();
    await expect(page).toHaveURL(/casos_pag=2/);
    await expect.poll(async () => (await idsVisibles(page))[0]).not.toBe(primera[0]);
  });

  test("la página sobrevive a una recarga", async ({ page }) => {
    await page.getByLabel("Página siguiente").click();
    await expect(page).toHaveURL(/casos_pag=2/);
    // Se compara el RANGO del pie y no los ids: es la aserción directa de «sigo
    // en la página 2», y no se rompe si el orden tiene empates.
    await expect(page.locator("text=/Mostrando /").first()).toContainText("26–50");

    await page.reload();
    await expect(page.locator("text=/Mostrando /").first()).toContainText("26–50");
  });

  test("ordenar por una columna cambia el resultado y vuelve a la página 1", async ({ page }) => {
    const num = (s) => Number(s.replace("#", ""));
    const ids = async () => (await idsVisibles(page)).map(num);
    // Se espera a que la COLUMNA quede efectivamente ordenada, en vez de leer los
    // ids apenas se hace clic: la consulta tarda y hasta que llega se siguen
    // viendo los de la consulta anterior (`keepPreviousData`, a propósito).
    const ordenada = (dir) => async () => {
      const v = await ids();
      return v.length > 1 && v.every((x, i) => i === 0 || (dir > 0 ? v[i - 1] <= x : v[i - 1] >= x));
    };

    await page.getByLabel("Página siguiente").click();
    await expect(page).toHaveURL(/casos_pag=2/);

    await page.getByRole("button", { name: /Ordenar por Caso/ }).click();
    await expect(page).toHaveURL(/casos_ord=id/);
    await expect(page).not.toHaveURL(/casos_pag=/); // reordenar vuelve a la página 1
    await expect.poll(ordenada(1)).toBe(true);
    const asc = await ids();

    await page.getByRole("button", { name: /Ordenar por Caso/ }).click();
    await expect(page).toHaveURL(/casos_ord=-id/);
    await expect.poll(ordenada(-1)).toBe(true);
    const desc = await ids();

    expect(desc[0]).toBeGreaterThan(asc[0]);
  });

  test("filtrar por estado reduce el total", async ({ page }) => {
    const todos = await totalDeCasos(page);
    // El total se lee con `poll` porque la consulta filtrada tarda: leerlo una
    // sola vez justo después de elegir devuelve el total viejo y el test pasa o
    // falla según la latencia.
    const total = async () => {
      const t = await page.locator("text=/Mostrando /").first().textContent().catch(() => "");
      return Number((t.match(/de\s*(\d+)/) || [])[1] || 0);
    };
    expect(await total()).toBe(todos);

    await page.getByLabel("Filtrar por estado").selectOption({ label: "En espera" });
    await expect.poll(total).toBeLessThan(todos);
    expect(await total()).toBeGreaterThan(0);
  });

  test("buscar filtra y queda en la URL", async ({ page }) => {
    await page.locator('input[type="search"]').fill("Quiroga");
    await expect(page).toHaveURL(/q=Quiroga/);
    await expect(page.locator("text=/Mostrando .* de /").first()).toBeVisible();
  });

  test("la densidad compacta muestra más filas en pantalla", async ({ page }) => {
    const alto = () => page.$eval("tbody tr", (r) => r.getBoundingClientRect().height);
    const comoda = await alto();
    await page.getByRole("button", { name: /Compacta/ }).click();
    await expect.poll(alto).toBeLessThan(comoda);
  });

  test("no desborda en horizontal en ningún ancho", async ({ page }) => {
    for (const width of [1440, 1024, 768, 390]) {
      await sinDesborde(page, width);
    }
  });
});
