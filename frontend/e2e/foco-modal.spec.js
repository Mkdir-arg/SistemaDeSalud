import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * El foco no se escapa del diálogo mientras el diálogo está abierto.
 *
 * `Modal` es el diálogo de TODA la app: farmacia, internación, la historia
 * clínica y la supervisión abren el mismo componente. Sin trampa de foco, dos
 * tabulaciones de más dejan a la persona tipeando sobre la barra lateral de
 * atrás con el diálogo todavía arriba: un Enter ahí cambia de pantalla y se
 * pierde el recuento a medio cargar, sin aviso ni confirmación. Con un lector de
 * pantalla es peor, porque `aria-modal="true"` oculta el fondo y el foco recorre
 * elementos que no se anuncian.
 *
 * Se prueba sobre el diálogo de cancelación de Supervisión porque es el más
 * barato de abrir y el que menos toca: se cierra con Escape sin cancelar nada.
 */

/** ¿El foco sigue adentro del diálogo, o se fue al fondo? */
const focoAdentro = (page) =>
  page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'));

/** Descripción de dónde quedó el foco, para que el fallo diga algo. */
const donde = (page) =>
  page.evaluate(() => {
    const el = document.activeElement;
    return el ? `${el.tagName.toLowerCase()} «${(el.textContent || "").trim().slice(0, 30)}»` : "nada";
  });

test.describe("Foco del diálogo", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "jefe");
    await page.goto("/supervision");
  });

  test("tabular de mas no saca el foco del dialogo", async ({ page }) => {
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    await fila.getByRole("button", { name: "Cancelar" }).click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();

    // Diez tabulaciones sobre un diálogo con tres controles: cicla varias
    // vueltas. Sin la trampa, la tercera ya está en la barra lateral.
    for (let i = 1; i <= 10; i++) {
      await page.keyboard.press("Tab");
      expect(await focoAdentro(page), `el foco se fue a ${await donde(page)} en la tabulación ${i}`).toBe(true);
    }
    // Y hacia atrás, que es por donde se escapa el primer elemento.
    for (let i = 1; i <= 10; i++) {
      await page.keyboard.press("Shift+Tab");
      expect(await focoAdentro(page), `el foco se fue a ${await donde(page)} en la retro-tabulación ${i}`).toBe(true);
    }

    await page.keyboard.press("Escape");
    await expect(dialogo).toBeHidden();
  });

  test("al cerrar, el foco vuelve al boton que abrio el dialogo", async ({ page }) => {
    const fila = page.locator("tbody tr").first();
    await expect(fila).toBeVisible();
    const abrir = fila.getByRole("button", { name: "Cancelar" });
    await abrir.click();
    await expect(page.getByRole("dialog")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toBeHidden();
    // Si el foco queda en el <body>, la próxima tabulación arranca desde el
    // principio de la página: quien opera con teclado tiene que recorrer la
    // barra lateral entera para volver a la fila donde estaba.
    await expect(abrir).toBeFocused();
  });
});
