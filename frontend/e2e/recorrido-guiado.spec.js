import { expect, test } from "@playwright/test";

import { entrarPlataforma } from "./apoyo";

/**
 * El recorrido guiado, actuado.
 *
 * Lo que este spec cuida no es que la institución quede cargada —eso lo lograba
 * también la versión anterior, sembrando por API— sino que quede cargada PORQUE
 * el recorrido completó los formularios de la app. Por eso cada aserción mira la
 * pantalla en el momento del acto: el diálogo abierto, el valor dentro del input,
 * el desplegable con el profesional elegido.
 *
 * Si alguien vuelve a sembrar por atrás y deja el panel diciendo «Actuando», los
 * tres primeros tests siguen pasando y estos fallan. Es el punto.
 */

const PANEL = "[data-tour-panel]";

/** Arranca el recorrido: tres clics en la ficha del super admin. */
async function arrancarRecorrido(page) {
  const disparador = page.locator('[data-demo-trigger="super-admin"]').first();
  await disparador.click({ clickCount: 3, delay: 60 });

  // Si la escuela ya tiene datos de una corrida anterior, el recorrido pregunta
  // antes de borrar. Para el test siempre queremos la construcción completa.
  const desdeCero = page.getByRole("button", { name: "Empezar de cero" });
  if (await desdeCero.isVisible({ timeout: 4000 }).catch(() => false)) {
    await desdeCero.click();
  }
  await expect(page.locator(PANEL)).toBeVisible();
}

/** El recorrido a 2×, que es la mitad de espera con el mismo comportamiento. */
async function acelerar(page) {
  await page.locator(PANEL).getByRole("button", { name: "1×" }).click();
}

/** El control que está debajo de una etiqueta de formulario, como lo busca el actor. */
function campo(page, etiqueta) {
  return page.locator('[role="dialog"] label', { hasText: etiqueta })
    .locator("input, select, textarea").first();
}

test.describe("Recorrido guiado", () => {
  // Construye una institución entera desde el navegador: son varios minutos de
  // formularios, no un click.
  test.setTimeout(300_000);

  test.beforeEach(async ({ page }) => {
    await entrarPlataforma(page);
  });

  test("completa el formulario de alta en pantalla, no por atrás", async ({ page }) => {
    await arrancarRecorrido(page);
    await acelerar(page);

    // El primer acto es sobre el directorio: abre el alta de institución.
    const dialogo = page.getByRole("dialog", { name: "Nueva institución" });
    await expect(dialogo).toBeVisible({ timeout: 30_000 });

    // La prueba de que se ACTUÓ: el nombre está dentro del input, escrito, antes
    // de que exista la institución. Sembrando por API el diálogo no se abre.
    await expect(campo(page, "Nombre")).toHaveValue("Hospital Escuela Cauce", { timeout: 30_000 });
    await expect(campo(page, "CUIT")).toHaveValue("30-00000000-7", { timeout: 20_000 });

    // Y el panel dice qué está haciendo, no un ítem de una lista con temporizador.
    await expect(page.locator(PANEL)).toContainText("Actuando");
  });

  test("escribe el área en el diálogo y la deja en la lista", async ({ page }) => {
    await arrancarRecorrido(page);
    await acelerar(page);

    await expect(page.getByRole("dialog", { name: "Nueva área" })).toBeVisible({ timeout: 90_000 });
    await expect(campo(page, "Nombre")).toHaveValue("Guardia escuela", { timeout: 30_000 });
    await expect(campo(page, "Responsable / jefe")).toHaveValue("Jefatura de guardia", { timeout: 20_000 });

    // Guardar cierra el diálogo y el área aparece en la estructura.
    await expect(page.getByRole("dialog", { name: "Nueva área" })).toBeHidden({ timeout: 40_000 });
    await expect(page.getByText("Guardia escuela").first()).toBeVisible({ timeout: 30_000 });

    // Lo sembrado se declara en el panel en vez de tildarse en silencio.
    await expect(page.locator(PANEL)).toContainText(/otras cuatro áreas|Sembrando/, { timeout: 60_000 });
  });

  /**
   * El paso que la demo existe para mostrar: la agenda con su profesional y su
   * flujo. Depende de todos los anteriores —sin usuario no hay a quién asignar,
   * sin flujo publicado no hay qué abrir—, así que si algo se rompió antes, se
   * rompe acá.
   */
  test("asigna el profesional y el flujo en el formulario de la agenda", async ({ page }) => {
    await arrancarRecorrido(page);
    await acelerar(page);

    const dialogo = page.getByRole("dialog", { name: /Nueva agenda/ });
    await expect(dialogo).toBeVisible({ timeout: 240_000 });

    await expect(campo(page, "Nombre")).toHaveValue("Consultorio escuela", { timeout: 30_000 });

    // El desplegable queda en la persona elegida por su texto, no en un id.
    const profesional = campo(page, "Profesional");
    await expect(profesional).toHaveValue(/\d+/, { timeout: 30_000 });
    await expect(profesional.locator("option:checked")).toContainText("Vera");

    const flujo = campo(page, "Flujo que se abre al presentarse");
    await expect(flujo.locator("option:checked")).toContainText("Guardia escuela", { timeout: 30_000 });

    await expect(dialogo).toBeHidden({ timeout: 40_000 });
    await expect(page.getByText("Consultorio escuela").first()).toBeVisible({ timeout: 30_000 });
  });

  /**
   * El recorrido no puede quedarse con el volante. Si alguien toca la app, el
   * actor suelta: un cursor fantasma escribiendo mientras la persona intenta
   * usar la pantalla es peor que no tener recorrido.
   */
  test("suelta el control cuando la persona toca la app", async ({ page }) => {
    await arrancarRecorrido(page);

    await expect(page.locator(PANEL)).toContainText("Actuando", { timeout: 30_000 });
    await page.mouse.click(12, 12);

    await expect(page.locator(PANEL)).toContainText("Tomaste el control", { timeout: 10_000 });
    await expect(page.locator(PANEL)).toContainText("en tus manos");
    await expect(page.locator(PANEL).getByRole("button", { name: "Que siga el recorrido" })).toBeVisible();
  });
});
