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
    // Se cuenta por turno y no por botón: cada fila tiene además la flecha de
    // «adelantar un lugar», así que contar botones mide el doble y se rompe cada
    // vez que la fila suma un control.
    const enEspera = () => page.locator("ul li .font-mono").count();
    const antes = await enEspera();

    await page.getByRole("button", { name: /Llamar siguiente/ }).first().click();
    await expect(page).toHaveURL(/\/casos\/\d+/);

    await page.goto("/filas");
    await expect(page.getByRole("heading", { name: "Fila de espera" })).toBeVisible();
    await expect.poll(enEspera).toBe(antes - 1);
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

  /**
   * Adelantar a alguien que empeoró esperando. No consume cola: mueve, no llama.
   */
  test("se puede adelantar un lugar a quien esperando empeoró", async ({ page }) => {
    const turnos = () => page.locator("ul li .font-mono").allTextContents();
    const antes = await turnos();
    const flechas = page.locator('button[aria-label^="Adelantar"]:not([disabled])');
    const ultima = flechas.last();
    // Índice de la fila a la que pertenece esa flecha.
    const i = await ultima.evaluate(
      (b) => [...b.closest("ul").querySelectorAll("li")].indexOf(b.closest("li")) - 1,
    );
    await ultima.click();
    await expect.poll(async () => (await turnos()).indexOf(antes[i])).toBe(i - 1);
  });

  /**
   * La flecha se apaga cuando arriba hay alguien de otra urgencia: los urgentes
   * van primero siempre, así que ese movimiento se deshace solo. Estaba
   * habilitada y el toast avisaba «se adelantó un lugar» sin que nada cambiara.
   */
  test("no ofrece adelantar por encima de un urgente", async ({ page }) => {
    const filas = page.locator("ul li").filter({ has: page.locator(".font-mono") });
    const total = await filas.count();
    for (let i = 1; i < total; i++) {
      const urg = async (n) => (await filas.nth(n).textContent()).toLowerCase().includes("urgente");
      if ((await urg(i)) !== (await urg(i - 1))) {
        await expect(filas.nth(i).getByRole("button", { name: /^Adelantar/ })).toBeDisabled();
        return;
      }
    }
  });

  test("se puede operar en tablet y en móvil", async ({ page }) => {
    for (const width of [1024, 390]) {
      await sinDesborde(page, width);
      await expect(page.getByRole("button", { name: /Llamar/ }).first()).toBeVisible();
    }
  });
});
