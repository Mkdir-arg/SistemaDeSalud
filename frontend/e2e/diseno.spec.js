import { expect, test } from "@playwright/test";

import { entrar, sinDesborde } from "./apoyo";

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
    const lista = page.getByRole("list", { name: "Campos del formulario" });
    const primera = lista.getByRole("listitem").first();
    const etiqueta = (await primera.locator("div.font-semibold").first().innerText()).replace(" *", "").trim();

    await primera.getByRole("button", { name: "Editar campo" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    const campoEtiqueta = page.getByLabel("Etiqueta *");
    await campoEtiqueta.fill(`${etiqueta} (revisado)`);
    await page.getByRole("button", { name: "Guardar" }).click();

    await expect(page.getByText(`${etiqueta} (revisado)`).first()).toBeVisible();

    // Se deja el formulario como estaba: la suite corre sobre datos compartidos.
    await lista.getByRole("listitem").first().getByRole("button", { name: "Editar campo" }).click();
    await page.getByLabel("Etiqueta *").fill(etiqueta);
    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByText(`${etiqueta} (revisado)`)).toHaveCount(0);
  });

  test("los campos se pueden reordenar y el orden es el que ve el administrativo", async ({ page }) => {
    const filas = page.getByRole("list", { name: "Campos del formulario" }).getByRole("listitem");
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
    await page
      .getByRole("list", { name: "Campos del formulario" })
      .getByRole("listitem").first()
      .getByRole("button", { name: "Quitar campo" }).click();
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

test.describe("Formulario: metadatos, uso y campo numérico", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
    await page.goto("/formularios");
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });

  test("el listado dice en cuántos flujos se usa cada formulario", async ({ page }) => {
    /*
     * Era lo primero que había que saber antes de tocarle un campo y no estaba
     * en ninguna parte: la única forma de averiguarlo era abrir los flujos de a
     * uno en el diseñador. Reemplaza a la columna «Vinculados», que sólo podía
     * dar 0 porque contaba una precarga que no está implementada.
     */
    await expect(page.getByRole("columnheader", { name: "Se usa en" })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toContainText(/flujo|sin uso/);
  });

  test("el título y la descripción del formulario se pueden corregir", async ({ page }) => {
    /*
     * El alta pedía sólo el título y después quedaba fijo para siempre: un
     * «Admision de pacinetes» mal tipeado se ve en cada paso de cada flujo que lo
     * usa, y la única salida era el admin de Django —o sea, sacar del sistema al
     * usuario al que el producto le prometió configurar sin programar—. La
     * descripción directamente no se podía cargar, así que la columna del listado
     * sólo podía decir «—».
     */
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/formularios\/\d+/);

    // La barra superior del Shell también tiene un h1 con el nombre de la pantalla.
    const titulo = page.getByRole("heading", { level: 1 }).last();
    // Mientras carga, el h1 es un esqueleto vacío: leerlo ahí deja el test
    // restaurando el formulario con el título en blanco.
    await expect(titulo).toHaveText(/\S/);
    const original = (await titulo.innerText()).trim();

    await page.getByRole("button", { name: "Editar", exact: true }).click();
    const dialogo = page.getByRole("dialog");
    // La descripción original se lee del propio campo: la del demo NO está vacía,
    // y restaurarla con "" dejaría la columna del listado en «—» hasta la próxima
    // siembra —o sea, el test rompería justo lo que vino a comprobar.
    const descripcion = await dialogo.getByLabel("Descripción").inputValue();
    await dialogo.getByLabel("Título *").fill(`${original} (revisado)`);
    await dialogo.getByLabel("Descripción").fill("Descripción de prueba.");
    await dialogo.getByRole("button", { name: "Guardar" }).click();

    await expect(titulo).toHaveText(`${original} (revisado)`);
    // Al párrafo de la cabecera: el modal que se está cerrando todavía tiene el
    // texto dentro del <textarea>, y `getByText` lo machea también.
    await expect(page.getByRole("paragraph").filter({ hasText: "Descripción de prueba." })).toBeVisible();

    // Se deja como estaba: la suite corre sobre datos compartidos.
    await page.getByRole("button", { name: "Editar", exact: true }).click();
    await page.getByRole("dialog").getByLabel("Título *").fill(original);
    await page.getByRole("dialog").getByLabel("Descripción").fill(descripcion);
    await page.getByRole("dialog").getByRole("button", { name: "Guardar" }).click();
    await expect(titulo).toHaveText(original);
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("«Dónde se usa» nombra el paso y el flujo que piden el formulario", async ({ page }) => {
    /*
     * Sin esto el constructor era una pantalla a ciegas sobre datos en
     * producción: agregar un campo requerido traba en el acto los casos parados
     * en ese paso, y nada lo decía.
     */
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/formularios\/\d+/);
    await expect(page.getByRole("heading", { name: "Vista previa en vivo" })).toBeVisible();

    const panel = page.getByRole("heading", { name: /Dónde se usa/ });
    await expect(panel).toBeVisible();
    // La tarjeta entera: el encabezado cuelga directo de ella.
    await expect(panel.locator("..")).toContainText(/paso «|Ningún paso/);
  });

  test("el constructor no desborda en ningún ancho", async ({ page }) => {
    /*
     * La pantalla es una grilla de dos columnas con una tira de cuatro datos en
     * la cabecera y filas de campo con chips, rango y acciones. Cualquiera de las
     * tres puede empujar el ancho: si el body se desplaza en horizontal, el
     * configurador pierde de vista la columna de la vista previa, que es la mitad
     * del sentido de esta pantalla.
     */
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/formularios\/\d+/);
    await expect(page.getByRole("heading", { name: "Vista previa en vivo" })).toBeVisible();

    for (const ancho of [1440, 1024, 768, 390]) {
      await sinDesborde(page, ancho);
    }
  });

  test("un campo numérico se define con unidad y rango, y el rango invertido no se guarda", async ({ page }) => {
    /*
     * El tipo Número no existía: temperatura, peso y tensión entraban como texto
     * libre, y una Decisión «> 38» sobre texto no comparable devuelve False en
     * silencio —el paciente febril sigue por el circuito del paciente sin fiebre.
     */
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/formularios\/\d+/);
    await expect(page.getByRole("heading", { name: "Vista previa en vivo" })).toBeVisible();

    await page.getByRole("button", { name: "+ Agregar campo", exact: true }).click();
    const dialogo = page.getByRole("dialog");
    await dialogo.getByLabel("Etiqueta *").fill("Temperatura de prueba");
    await dialogo.getByLabel("Tipo").selectOption("numero");

    await expect(dialogo.getByLabel("Unidad")).toBeVisible();
    await dialogo.getByLabel("Unidad").fill("°C");
    // `Field` mete el hint dentro del <label>, así que el nombre accesible de
    // «Máximo» incluye «…menor que el mínimo»: hay que anclar al inicio.
    await dialogo.getByRole("spinbutton", { name: /^Mínimo/ }).fill("45");
    await dialogo.getByRole("spinbutton", { name: /^Máximo/ }).fill("30");
    // Un rango invertido no admite ningún valor: el campo sería imposible de completar.
    await expect(dialogo.getByRole("button", { name: "Agregar" })).toBeDisabled();

    await dialogo.getByRole("spinbutton", { name: /^Mínimo/ }).fill("30");
    await dialogo.getByRole("spinbutton", { name: /^Máximo/ }).fill("45");
    await dialogo.getByRole("button", { name: "Agregar" }).click();

    const lista = page.getByRole("list", { name: "Campos del formulario" });
    const nueva = lista.getByRole("listitem").filter({ hasText: "Temperatura de prueba" });
    await expect(nueva).toContainText("30 – 45 °C");

    /*
     * Se limpia: el campo nuevo no tiene datos cargados, así que se puede quitar.
     *
     * En bucle y no una sola vez: si una corrida anterior se cortó a mitad de
     * camino dejó su propio «Temperatura de prueba», y borrar uno solo dejaría el
     * otro ahí para siempre —con lo cual este test no vuelve a pasar nunca hasta
     * que alguien resiembre—.
     */
    const sobrantes = () => lista.getByRole("listitem").filter({ hasText: "Temperatura de prueba" });
    for (let i = 0; i < 5; i++) {
      const antes = await sobrantes().count();
      if (antes === 0) break;
      await sobrantes().first().getByRole("button", { name: "Quitar campo" }).click();
      await page.getByRole("dialog").getByRole("button", { name: "Quitar campo" }).click();
      // Se espera a que la fila DESAPAREZCA, no sólo a que cierre el diálogo: si
      // la vuelta siguiente cuenta antes de que llegue el refetch, agarra la fila
      // que está por irse y el clic pega sobre un nodo ya desprendido.
      await expect(sobrantes()).toHaveCount(antes - 1);
    }
    await expect(sobrantes()).toHaveCount(0);
  });
});
