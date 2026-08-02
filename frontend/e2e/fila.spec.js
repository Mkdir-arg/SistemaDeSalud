import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

/**
 * Fila de espera: la pantalla piloto de la migración y el recorrido operativo
 * más importante de la guardia. Si esto se rompe, el médico no puede llamar
 * pacientes.
 */
test.describe("Fila de espera", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "medico");
    await page.goto("/filas");
    await expect(page.getByRole("heading", { name: "Fila de espera" })).toBeVisible();
  });

  test("muestra la cola con los urgentes primero", async ({ page }) => {
    const filas = page.locator("ul li button");
    await expect(filas.first()).toBeVisible();
    expect(await filas.count()).toBeGreaterThan(0);

    // Si hay algún urgente en la cola, tiene que estar al frente: es toda la
    // promesa del triage.
    const urgentes = page.locator("ul li button", { has: page.getByText("urgente") });
    if (await urgentes.count()) {
      await expect(filas.first().getByText("urgente")).toBeVisible();
    }
  });

  /**
   * OJO: este test CONSUME cola. Llama a un paciente de verdad, contra el motor
   * real, y ese paciente no vuelve. Es a propósito —llamar es la acción central
   * de la guardia y simularla no probaría nada—, pero implica que la suite no es
   * idempotente: cada corrida completa gasta un lugar de la fila.
   *
   * El chequeo previo (e2e/setup.js) verifica que quede cola suficiente y avisa
   * cuándo hay que volver a sembrar.
   */
  test("llamar al siguiente lo saca de la cola y abre su caso", async ({ page }) => {
    const filas = page.locator("ul li button");
    const antes = await filas.count();

    await page.getByRole("button", { name: /Llamar siguiente/ }).first().click();
    await expect(page).toHaveURL(/\/casos\/\d+/);

    await page.goto("/filas");
    await expect(page.getByRole("heading", { name: "Fila de espera" })).toBeVisible();
    await expect.poll(() => page.locator("ul li button").count()).toBe(antes - 1);
  });

  /**
   * La pantalla tiene que abrir en un área donde la persona pueda llamar.
   *
   * La fila lista TODAS las áreas con gente esperando —un jefe quiere el
   * panorama—, pero arrancar en una ajena convierte la acción principal en un
   * error: el médico entraba, apretaba «Llamar siguiente» y recibía «No integrás
   * ningún grupo responsable de este paso». Sin este test, el orden de las áreas
   * decide si la pantalla sirve o no.
   */
  test("abre en un área donde el médico puede llamar", async ({ page }) => {
    // Si aparece el aviso de área ajena, la pantalla arrancó en la equivocada.
    await expect(page.getByText(/no es tuya/)).toBeHidden();

    // Y la prueba de fuego: llamar funciona sin cambiar de área.
    await page.getByRole("button", { name: /Llamar siguiente/ }).first().click();
    await expect(page).toHaveURL(/\/casos\/\d+/);
  });

  test("se puede operar en tablet y en móvil", async ({ page }) => {
    for (const width of [1024, 390]) {
      await sinDesborde(page, width);
      await expect(page.getByRole("button", { name: /Llamar/ }).first()).toBeVisible();
    }
  });
});
