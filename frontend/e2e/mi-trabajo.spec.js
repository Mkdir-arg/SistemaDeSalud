import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

/**
 * «Mi trabajo»: la pantalla de inicio del operador y su worklist.
 * Es donde el médico ocupa su box y llama pacientes, así que si se rompe la
 * guardia no funciona.
 */
test.describe("Mi trabajo", () => {
  // Por rol de encabezado y no por texto: «Tu box» también aparece dentro del
  // aviso «Ocupá tu box (arriba, en Tu box)», y por texto suelto son 3 elementos.
  const seccion = (page, nombre) => page.getByRole("heading", { name: nombre });

  test("el médico ve su pulso, sus puestos y su box", async ({ page }) => {
    await entrar(page, "medico");
    await expect(seccion(page, "Pulso del área (hoy)")).toBeVisible();
    await expect(seccion(page, "Mis puestos")).toBeVisible();
    await expect(seccion(page, "Tu box")).toBeVisible();
  });

  test("no se puede llamar sin ocupar un box, y ocuparlo lo habilita", async ({ page }) => {
    await entrar(page, "medico");
    await expect(seccion(page, "Tu box")).toBeVisible();

    // Sin box: la fila explica por qué no se puede llamar.
    await expect(page.getByText(/Ocupá tu box/).first()).toBeVisible();

    await page.getByRole("button", { name: "Ocupar box" }).first().click();
    await expect(page.getByRole("button", { name: "Salir del box" })).toBeVisible();
    // Ya con box, aparece el botón de llamar.
    await expect(page.getByRole("button", { name: /Llamar siguiente|Sin pacientes en cola/ }).first()).toBeVisible();

    // Se libera para no dejar el box tomado para los demás tests.
    //
    // Si hay un paciente adentro, salir pide confirmación: el box queda libre y
    // otro puede llamar a alguien más a ese consultorio. Se confirma acá porque
    // el test justamente quiere dejarlo libre.
    await page.getByRole("button", { name: "Salir del box" }).click();
    const confirmar = page.getByRole("button", { name: "Salir igual" });
    if (await confirmar.isVisible().catch(() => false)) await confirmar.click();
    await expect(page.getByRole("button", { name: "Ocupar box" }).first()).toBeVisible();
  });

  test("el buscador de estado de paciente consulta al servidor", async ({ page }) => {
    await entrar(page, "medico");
    await page.getByRole("button", { name: /Estado de un paciente/ }).click();
    const dialogo = page.getByRole("dialog");
    await expect(dialogo).toBeVisible();

    await dialogo.locator('input[type="search"]').fill("Quiroga");
    await expect(dialogo.getByText(/Quiroga/).first()).toBeVisible();

    // Elegirlo muestra sus casos.
    await dialogo.getByText(/Quiroga/).first().click();
    await expect(dialogo.getByText("SUS CASOS")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialogo).toBeHidden();
  });

  test("las bandas se pliegan", async ({ page }) => {
    await entrar(page, "medico");
    const cabecera = page.locator('button[aria-expanded]').first();
    await expect(cabecera).toHaveAttribute("aria-expanded", "true");
    await cabecera.click();
    await expect(cabecera).toHaveAttribute("aria-expanded", "false");
  });

  test("no desborda en ningún ancho", async ({ page }) => {
    await entrar(page, "medico");
    for (const width of [1440, 1024, 390]) {
      await sinDesborde(page, width);
    }
  });
});
