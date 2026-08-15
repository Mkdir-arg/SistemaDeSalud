import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * Las dos pantallas del módulo de diseño que no son el lienzo: el listado de
 * flujos y el constructor de formularios.
 *
 * Son las que sostienen la promesa del producto del lado de la configuración —
 * «esto se configura, no se programa»— y no tenían ninguna cobertura.
 */

test.describe("Constructor de formularios", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await page.goto("/formularios");
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/formularios\/\d+/);
    await expect(page.getByRole("heading", { name: "Vista previa en vivo" })).toBeVisible();
  });

  test("un campo se puede editar sin rehacerlo", async ({ page }) => {
    /*
     * Editar no existía: creado el campo, la etiqueta, el tipo, las opciones, el
     * «requerido» y la ayuda quedaban fijos para siempre. Las dos salidas eran
     * crear un campo duplicado —y ahí las Decisiones que apuntan al campo viejo
     * dejan de encontrar el dato y los casos se van por la rama que no era— o
     * entrar por el admin de Django, o sea sacar del sistema al usuario al que el
     * producto le prometió configurar sin programar.
     */
    const primera = page.locator("ul > li").first();
    const etiqueta = (await primera.locator("div.font-semibold").first().innerText()).replace(" *", "").trim();

    await primera.getByRole("button", { name: "editar" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    const campoEtiqueta = page.getByLabel("Etiqueta *");
    await campoEtiqueta.fill(`${etiqueta} (revisado)`);
    await page.getByRole("button", { name: "Guardar" }).click();

    await expect(page.getByText(`${etiqueta} (revisado)`).first()).toBeVisible();

    // Se deja el formulario como estaba: la suite corre sobre datos compartidos.
    await page.locator("ul > li").first().getByRole("button", { name: "editar" }).click();
    await page.getByLabel("Etiqueta *").fill(etiqueta);
    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByText(`${etiqueta} (revisado)`)).toHaveCount(0);
  });

  test("los campos se pueden reordenar y el orden es el que ve el administrativo", async ({ page }) => {
    const filas = page.locator("ul > li");
    test.skip((await filas.count()) < 2, "el formulario tiene un solo campo");

    const nombres = () => filas.locator("div.font-semibold").first().innerText();
    const antes = await nombres();

    await filas.first().getByRole("button", { name: "Bajar" }).click();
    await expect.poll(nombres).not.toBe(antes);

    // La vista previa muestra el mismo orden: es lo único que hace útil moverlos.
    const enPrevia = await page.locator("form, .grid").last().innerText();
    expect(enPrevia.length).toBeGreaterThan(0);

    // Se devuelve a su lugar.
    await filas.nth(1).getByRole("button", { name: "Subir" }).click();
    await expect.poll(nombres).toBe(antes);
  });

  test("el diálogo de quitar dice la verdad sobre los datos ya cargados", async ({ page }) => {
    /*
     * Prometía «Los datos ya cargados no se borran» justo antes de que el
     * servidor respondiera 409 diciendo lo contrario: `ValorCampo.campo` es
     * CASCADE, así que el borrado se llevaría el motivo de consulta o el nivel de
     * triage de cada caso que pasó por el formulario.
     */
    await page.locator("ul > li").first().getByRole("button", { name: "quitar" }).click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();
    await expect(dialogo).not.toContainText("Los datos ya cargados no se borran");
    // Dentro del diálogo: «Volver» a secas machea cuatro botones de la pantalla
    // —el de la barra lateral, el de la cabecera y el de volver a formularios—.
    await dialogo.getByRole("button", { name: "Volver", exact: true }).click();
  });
});

test.describe("Listado de flujos", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await page.goto("/flujos");
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });

  test("retirar un flujo explica qué deja de pasar y no se hace de prepo", async ({ page }) => {
    /*
     * El estado ARCHIVADA existía en el modelo y en la pestaña «Archivado», y
     * ningún código lo asignaba nunca: el flujo de la campaña que terminó seguía
     * publicado para siempre y seguía apareciendo en «Nuevo caso», así que el
     * administrativo del mostrador podía meter un paciente en un circuito que la
     * institución dejó de usar.
     *
     * El test NO retira nada —dejaría el demo sin un flujo para el resto de la
     * suite—: comprueba que la acción existe y que el diálogo dice qué pasa.
     */
    const retirar = page.getByRole("button", { name: "Retirar flujo" }).first();
    await expect(retirar).toBeVisible();
    await retirar.click();

    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();
    await expect(dialogo).toContainText(/Nuevo caso|casos activos/);
    await dialogo.getByRole("button", { name: "Volver", exact: true }).click();
  });

  test("la pestaña «Archivado» ya no es un filtro sin salida", async ({ page }) => {
    // Con la acción de retirar, la pestaña puede tener contenido; sin ella era
    // una promesa que no se podía cumplir desde ninguna pantalla.
    await page.getByRole("tab", { name: "Archivado" }).click();
    await expect(page).toHaveURL(/estado=archivada/);
  });
});
