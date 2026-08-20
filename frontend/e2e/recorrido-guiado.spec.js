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

// El panel del recorrido en marcha. La `section` importa: el diálogo de arranque
// también lleva `data-tour-panel` —lo necesita para que el actor no confunda un
// clic ahí con que la persona tomó el control— y sin acotar por etiqueta el
// selector matchea los dos.
const PANEL = "section[data-tour-panel]";

/** Arranca el recorrido: tres clics en la ficha del super admin. */
async function arrancarRecorrido(page) {
  const disparador = page.locator('[data-demo-trigger="super-admin"]').first();
  await disparador.click({ clickCount: 3, delay: 60 });

  // Si la escuela ya tiene datos de una corrida anterior, el recorrido pregunta
  // antes de borrar. Para el test siempre queremos la construcción completa.
  //
  // Se espera por lo que llegue primero: `isVisible()` es instantáneo y no
  // acepta timeout, así que preguntarle de una devuelve `false` mientras el
  // recorrido todavía está consultando si hay datos, y el diálogo queda abierto
  // para siempre con el test mirando un recorrido que nunca arrancó.
  const desdeCero = page.getByRole("button", { name: "Empezar de cero" });
  const panel = page.locator(PANEL);
  await Promise.race([
    desdeCero.waitFor({ state: "visible", timeout: 20_000 }).catch(() => {}),
    panel.waitFor({ state: "visible", timeout: 20_000 }).catch(() => {}),
  ]);
  if (await desdeCero.isVisible()) await desdeCero.click();
  await expect(panel).toBeVisible();
}

/** El recorrido a 2×, que es la mitad de espera con el mismo comportamiento. */
async function acelerar(page) {
  await page.locator(PANEL).getByLabel("Velocidad del recorrido").selectOption("2");
}

/**
 * El control que está debajo de una etiqueta de formulario, como lo busca el actor.
 *
 * Filtra por un `div` hijo con ese texto, no por el texto del `<label>` entero.
 * La diferencia no es cosmética: el `textContent` de un label con `<select>`
 * adentro incluye el texto de todas sus `<option>`, así que buscar «Profesional»
 * en el label completo devuelve el desplegable de *Tipo* —que tiene una opción
 * llamada Profesional— y el test comprueba el campo equivocado. Es la misma
 * trampa que esquiva `textoDeEtiqueta` en actor.js, que lee sólo el primer hijo.
 */
function campo(page, etiqueta) {
  return page.locator('[role="dialog"] label')
    .filter({ has: page.locator("div", { hasText: etiqueta }) })
    .locator("input, select, textarea").first();
}

test.describe("Recorrido guiado", () => {
  // Construye una institución entera desde el navegador: son varios minutos de
  // formularios, no un click.
  test.setTimeout(420_000);

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
   * Ningún paso puede caer al sembrado.
   *
   * Este es el test que más paga de los cinco, y por una razón incómoda: la red
   * de seguridad —sembrar al cerrar cada paso— hace que un guion roto se vea
   * igual que uno que funciona. La institución queda cargada, el recorrido llega
   * al final, y nadie se enteraría de que el paso de usuarios no actuó nada
   * porque el botón dice «Crear usuario» y el guion buscaba «Nuevo usuario».
   * Pasó, y así se encontró.
   *
   * Por eso el actor cuenta lo que no pudo actuar y lo muestra en el panel: es la
   * única señal de que la actuación se rompió, y acá se la comprueba paso a paso.
   */
  test("no cae al sembrado en ningún paso", async ({ page }) => {
    await arrancarRecorrido(page);
    await acelerar(page);

    const panel = page.locator(PANEL);
    const fallos = new Set();
    const vistos = new Set();

    // Se muestrea el panel mientras el recorrido corre: es la forma de ver el
    // aviso de un paso que ya terminó, que en el paso siguiente desaparece.
    // Tres lecturas vacías seguidas, no una: cuando el guion navega, el panel se
    // vuelve a montar y una lectura suelta puede caer justo en ese hueco. Cortar
    // ahí daba el test por terminado en el paso 7 con cero fallos, que es
    // exactamente el falso verde que este test existe para no dar.
    let vacias = 0;
    for (let i = 0; i < 230 && vacias < 3; i += 1) {
      // El timeout corto no es cosmético: `innerText()` sin él espera a que el
      // elemento aparezca, y cuando el recorrido termina y desmonta el panel se
      // queda esperando hasta que muere el test entero.
      const texto = await panel.innerText({ timeout: 1200 }).catch(() => "");
      if (!texto) {
        vacias += 1;
        await page.waitForTimeout(700);
        continue;
      }
      vacias = 0;
      const paso = (texto.match(/(\d+) de \d+/) || [])[1];
      if (paso) vistos.add(paso);
      const sinActuar = texto.match(/(\d+) sin actuar/);
      if (sinActuar) fallos.add(`paso ${paso}: ${sinActuar[1]} sin actuar`);
      await page.waitForTimeout(1100);
    }

    expect([...fallos]).toEqual([]);
    // Y llegó hasta el final: un recorrido que se cuelga en el paso 3 también
    // daría cero fallos.
    expect(vistos.size).toBeGreaterThanOrEqual(15);
  });

  /**
   * Las pantallas de sólo mirar tienen que tener algo que mirar.
   *
   * Internación y Farmacia salían con el cartel de vacío, y explicar una
   * pantalla vacía es lo que hacía que el texto sonara a folleto: «muestra camas,
   * estadías y disponibilidad» sobre un recuadro que no muestra nada. La app no
   * tiene por dónde cargar camas ni insumos, así que el escenario los siembra
   * antes de mostrar la pantalla.
   */
  test("internación y farmacia llegan con datos, no con el cartel de vacío", async ({ page }) => {
    await arrancarRecorrido(page);
    await acelerar(page);

    // Las camas del área de internación de la escuela.
    await page.waitForURL(/\/internacion/, { timeout: 240_000 });
    await expect(page.getByText("101-A").first()).toBeVisible({ timeout: 30_000 });

    // Y en farmacia, la gasa que dejamos por debajo del mínimo a propósito: es
    // lo que hace que la pestaña «Qué resolver» tenga algo que resolver.
    await page.waitForURL(/\/farmacia/, { timeout: 90_000 });
    await expect(page.getByText(/Gasa estéril/).first()).toBeVisible({ timeout: 30_000 });
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
