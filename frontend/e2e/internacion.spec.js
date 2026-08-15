import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla, sinDesborde } from "./apoyo";

/**
 * Tablero de camas.
 *
 * Es la pantalla que enfermería deja abierta en un monitor toda la guardia y de
 * la que sale la decisión de aceptar o no otro paciente. Un número que no
 * corresponde a lo que se está mirando, o una cama que figura de una forma y
 * está de otra, se paga con un paciente sin lugar.
 */
test.describe("Internación", () => {
  const cabecera = (page) => page.locator("section").first();

  async function abrir(page) {
    await entrar(page, "enfermeria");
    await page.goto("/internacion");
    await esperarPantalla(page);
    // Por nivel: el encabezado de la barra superior también se llama «Internación».
    await expect(page.getByRole("heading", { name: "Internación", level: 2 })).toBeVisible();
  }

  test("el porcentaje grande es el del sector filtrado, y lo dice", async ({ page }) => {
    /*
     * Filtrar por sector es un acto deliberado: alguien quiere saber cómo está
     * UTI. Si el número más grande de la pantalla sigue siendo el del hospital
     * entero y nada lo aclara, se lee 33 % con UTI al 100 % y se acepta una
     * derivación que no tiene dónde ir.
     */
    await abrir(page);
    await expect(cabecera(page).getByText("ocupación · todo el hospital")).toBeVisible();

    await page.getByLabel("Sector").selectOption({ label: "UTI" });
    await expect(cabecera(page).getByText("ocupación · UTI")).toBeVisible();

    // Y el número tiene que ser el mismo que muestra la tarjeta de ese sector:
    // con el filtro puesto queda una sola sección de sector abajo.
    const grande = await cabecera(page).getByText(/^\d+%$/).first().innerText();
    const delSector = await page.locator("section").nth(1).getByText(/^\d+%$/).first().innerText();
    expect(grande).toBe(delSector);
  });

  test("dice de cuándo son los datos y se puede actualizar a mano", async ({ page }) => {
    /*
     * El tablero queda solo en un monitor. Sin marca de frescura, una foto de
     * hace cuatro horas se ve idéntica a una de recién: la cama que alguien
     * ocupó desde el detalle del caso sigue verde y dos personas mandan dos
     * pacientes al mismo lugar. La marca importa incluso con refresco
     * automático: si se cae la red, es lo único que lo delata.
     */
    await abrir(page);
    await expect(cabecera(page).getByText(/Actualizado (recién|hace )/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Actualizar" })).toBeEnabled();
  });

  test("la cama fuera de servicio muestra el motivo entero", async ({ page }) => {
    /*
     * Truncado a doce caracteres, «Pérdida de agua — …» no alcanza para decidir
     * lo único que hay que decidir: si la cama vuelve hoy o es obra hasta fin de
     * mes. El tooltip no cuenta: no aparece con teclado ni en tablet, que es
     * donde se opera esta pantalla.
     */
    await abrir(page);
    const motivo = page.getByText("Pérdida de agua — mantenimiento").first();
    await expect(motivo).toBeVisible();

    const cortado = await motivo.evaluate((el) => el.scrollWidth > el.clientWidth + 1);
    expect(cortado, "el motivo se está cortando en una sola línea").toBe(false);
  });

  test("sacar una cama de servicio se puede apretar con guantes", async ({ page }) => {
    /*
     * Es el único control de la ficha de una cama libre y se opera en tablet: con
     * 28 px o no se acierta, o se acierta sin querer y una cama en uso normal
     * queda marcada fuera de servicio.
     */
    await abrir(page);
    const boton = page.getByRole("button", { name: /Marcar la cama .* fuera de servicio/ }).first();
    const caja = await boton.boundingBox();
    expect(caja.width).toBeGreaterThanOrEqual(44);
    expect(caja.height).toBeGreaterThanOrEqual(44);
  });

  test("no desborda en ningún ancho", async ({ page }) => {
    await abrir(page);
    for (const width of [1440, 1024, 390]) {
      await sinDesborde(page, width);
    }
  });
});
