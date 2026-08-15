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

  test("la columna Prioridad ordena por gravedad, no alfabético", async ({ page }) => {
    /*
     * `prioridad` es un CharField: ordena alta < normal < urgente. El jefe toca
     * esta columna para hacer triage, ve urgentes arriba, da la lista por
     * revisada — y los casos en Alta quedan detrás de todos los normales, a
     * diecisiete páginas de distancia, sin ninguna señal de que falten.
     */
    await page.getByRole("button", { name: /^Ordenar por Prioridad/ }).click();
    await expect(page).toHaveURL(/sup_ord=prioridad_rank/);

    /*
     * Se ESPERA a que la tabla se reordene en vez de leerla enseguida.
     *
     * La tabla mantiene las filas anteriores mientras llega la página nueva
     * (`keepPreviousData`), a propósito, para no parpadear. Leerlas sin esperar
     * mide el orden viejo: el test fallaba con la lista sin ordenar aunque la
     * API ya devolvía bien.
     */
    const rango = { urgente: 0, alta: 1, normal: 2 };
    const rangos = () =>
      page.$$eval("tbody tr select", (ss) => ss.map((s) => s.value))
        .then((vs) => vs.map((v) => ({ urgente: 0, alta: 1, normal: 2 })[v]));

    await expect.poll(async () => {
      const r = await rangos();
      return r.length > 0 && r.every((v, i) => i === 0 || r[i - 1] <= v);
    }, { message: "la lista nunca quedó ordenada por gravedad" }).toBe(true);

    const valores = await page.$$eval("tbody tr select", (ss) => ss.map((s) => s.value));
    // Y ningún normal antes de un alta.
    expect(valores.indexOf("normal") === -1 || valores.lastIndexOf("alta") < valores.indexOf("normal")).toBe(true);
  });

  test("la columna Espera ordena por el reloj del paso, no por la edad del caso", async ({ page }) => {
    /*
     * `paso_desde` es lo que mide el SLA y lo que dispara los avisos de demora.
     * Ordenando por `creado`, la pantalla y las alertas dicen cosas distintas
     * sobre el mismo paciente: el jefe entra a buscar el caso que le avisaron y
     * lo encuentra en el medio de la lista.
     */
    await page.getByRole("button", { name: /^Ordenar por Espera/ }).click();
    await expect(page).toHaveURL(/sup_ord=paso_desde/);
  });

  test("con teclado, Enter sobre «Reasignar» ejecuta la acción y no navega al caso", async ({ page }) => {
    /*
     * La fila navega al caso con Enter y hace `preventDefault()`, que además
     * cancela la activación del botón. Enfermería y los jefes de guardia operan
     * por teclado con las manos ocupadas: sin esto no pueden reasignar ni
     * cancelar desde acá, y lo único que reciben es irse a otra pantalla.
     */
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    await fila.getByRole("button", { name: "Reasignar" }).focus();
    await page.keyboard.press("Enter");

    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page).toHaveURL(/\/supervision/);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
  });

  test("el modal de reasignar resuelve los candidatos contra el grupo responsable del paso", async ({ page }) => {
    /*
     * El backend exige integrar un grupo responsable del paso y devuelve 400 si
     * no; el modal ofrecía todo el staff del área —el administrativo incluido—,
     * con el primero ya preseleccionado. El jefe elegía, le rebotaba, elegía otro
     * y le rebotaba, y la pantalla nunca le decía cuál iba a andar.
     */
    const [respuesta] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/casos/") && r.request().method() === "GET"),
      page.reload(),
    ]);
    const primero = (await respuesta.json()).results?.[0];
    test.skip(!primero?.responsables?.length, "el primer caso de la lista no declara grupo responsable");

    await page.locator("tbody tr").first().getByRole("button", { name: "Reasignar" }).click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();
    // Nombra el grupo: es la diferencia entre «faltan personas» y «este paso solo
    // lo puede tomar este grupo».
    await expect(dialogo.getByText(new RegExp(primero.responsables[0].nombre))).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("no desborda en ningún ancho", async ({ page }) => {
    for (const width of [1440, 1024, 390]) {
      await sinDesborde(page, width);
    }
  });
});
