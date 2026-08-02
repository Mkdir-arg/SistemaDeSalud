import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * Bandeja de tareas. Lo importante es que cada pestaña sea un filtro DEL
 * SERVIDOR: antes la pantalla traía todos los casos de la institución y separaba
 * las bandejas en el navegador, así que repartía los primeros 25 de la API.
 */
test.describe("Bandeja", () => {
  test.beforeEach(async ({ page }) => {
    // Admisión de guardia: tiene casos propios y casos para tomar.
    await entrar(page, "medico");
    await page.goto("/bandeja");
  });

  test("las dos pestañas muestran su cuenta", async ({ page }) => {
    const tablist = page.getByRole("tablist");
    await expect(tablist).toBeVisible();
    await expect(tablist.getByRole("tab", { name: /Mis casos/ })).toBeVisible();
    await expect(tablist.getByRole("tab", { name: /Sin asignar/ })).toBeVisible();
  });

  test("cambiar de pestaña queda en la URL y cambia el listado", async ({ page }) => {
    await page.getByRole("tab", { name: /Sin asignar/ }).click();
    await expect(page).toHaveURL(/bandeja=sin/);
    await expect(page.getByRole("tab", { name: /Sin asignar/ })).toHaveAttribute("aria-selected", "true");

    await page.reload();
    await expect(page.getByRole("tab", { name: /Sin asignar/ })).toHaveAttribute("aria-selected", "true");
  });

  test("cada bandeja recuerda su propia página", async ({ page }) => {
    // Con el super admin, porque es el único perfil con más de una página de
    // casos sin asignar: un médico de guardia opera por fila, así que su bandeja
    // «Sin asignar» está vacía por diseño.
    await entrar(page, "admin");
    await page.goto("/bandeja?bandeja=sin");

    const siguiente = page.getByLabel("Página siguiente");
    await expect(siguiente).toBeEnabled();
    await siguiente.click();
    await expect(page).toHaveURL(/band-sin_pag=2/);

    // La clave de la tabla lleva la pestaña, así que la página de una bandeja no
    // se le aplica a la otra.
    await page.getByRole("tab", { name: /Mis casos/ }).click();
    await expect(page).not.toHaveURL(/band-mios_pag=/);
    await expect(page).toHaveURL(/band-sin_pag=2/); // la otra sí la conserva
  });

  test("el alta de caso busca al paciente contra el servidor", async ({ page }) => {
    await page.getByRole("button", { name: /Nuevo caso/ }).click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();

    // El padrón no se trae entero: hay un buscador.
    const buscador = dialogo.locator('input[type="search"]');
    await expect(buscador).toBeVisible();
    await buscador.fill("Quiroga");
    await expect.poll(async () => {
      const opciones = await dialogo.locator('select[aria-label="Paciente"] option').allTextContents();
      return opciones.some((o) => /Quiroga/.test(o));
    }).toBe(true);

    await page.keyboard.press("Escape");
    await expect(dialogo).toBeHidden();
  });
});
