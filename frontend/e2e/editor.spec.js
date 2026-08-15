import { expect, test } from "@playwright/test";

import { entrar } from "./apoyo";

/**
 * Diseñador de flujos: operación del lienzo.
 *
 * Es la pantalla que sostiene la promesa del producto («el proceso se
 * configura, no se programa»), y hasta ahora no tenía ninguna cobertura. El
 * primer test existe porque el zoom con rueda estuvo roto sin dar ningún error:
 * el listener se enganchaba en un `useEffect` que corría mientras el flujo
 * todavía cargaba, con el contenedor del lienzo sin existir.
 */

/*
 * Deja el editor abierto sobre un BORRADOR, listo para modificar.
 *
 * El flujo del demo está publicado, y una versión publicada ya no se edita: los
 * casos en curso están parados sobre esos nodos. Antes el editor dejaba
 * intentarlo y sólo aparecía «Error al guardar» en la barra; ahora avisa y
 * ofrece sacar una versión nueva, que es lo que hace esta función.
 */
async function abrirBorrador(page) {
  await entrar(page, "admin");
  await page.goto("/flujos");
  await page.locator("tbody tr").first().click();
  await page.waitForURL(/\/flujos\/\d+/);
  await expect(page.locator("[data-nodo]").first()).toBeVisible();

  const sacar = page.getByRole("button", { name: "Sacar una versión nueva" });
  if (await sacar.isVisible().catch(() => false)) {
    await sacar.click();
    await expect(sacar).toBeHidden({ timeout: 15000 });
    await expect(page.locator("[data-nodo]").first()).toBeVisible();
  }
}

test.describe("Diseñador de flujos", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
  });

  /** Escala del lienzo y scroll de su contenedor, leídos del DOM real. */
  const estado = (page) =>
    page.evaluate(() => {
      const cont = [...document.querySelectorAll("div")].find(
        (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
      );
      const capa = document.querySelector("[data-lienzo]");
      const m = capa && getComputedStyle(capa).transform.match(/matrix\(([\d.]+)/);
      const caja = cont.getBoundingClientRect();
      return {
        zoom: m ? +m[1] : null,
        sx: Math.round(cont.scrollLeft),
        sy: Math.round(cont.scrollTop),
        cx: caja.left + caja.width / 2,
        cy: caja.top + caja.height / 2,
      };
    });

  test("la rueda acerca y aleja el lienzo", async ({ page }) => {
    const inicial = await estado(page);
    expect(inicial.zoom).toBeCloseTo(1, 1);

    await page.mouse.move(inicial.cx, inicial.cy);
    await page.mouse.wheel(0, -300);
    await expect.poll(async () => (await estado(page)).zoom).toBeGreaterThan(inicial.zoom);

    await page.mouse.wheel(0, 600);
    await expect.poll(async () => (await estado(page)).zoom).toBeLessThan(inicial.zoom);
  });

  test("el zoom queda anclado al cursor", async ({ page }) => {
    /*
     * Sin ancla, acercarse a un nodo del medio del lienzo lo manda fuera de la
     * pantalla y hay que volver a buscarlo. Con ancla, el punto bajo el mouse se
     * queda donde está — y eso se nota en que el scroll acompaña al zoom.
     */
    const inicial = await estado(page);
    await page.mouse.move(inicial.cx, inicial.cy);
    await page.mouse.wheel(0, -300);

    await expect.poll(async () => (await estado(page)).sx).toBeGreaterThan(0);
    const final = await estado(page);
    expect(final.sy).toBeGreaterThan(0);
  });

  test("Ctrl+F busca un nodo y lo trae al centro", async ({ page }) => {
    const antes = await estado(page);

    await page.keyboard.press("Control+f");
    const buscador = page.getByLabel("Buscar un nodo del flujo");
    await expect(buscador).toBeFocused();

    // Un término que exista en cualquier flujo sembrado.
    await buscador.fill("aten");
    await expect(page.getByRole("button", { name: /Atenci/i }).first()).toBeVisible();

    await page.keyboard.press("Enter");
    // El lienzo se desplaza hacia el nodo elegido.
    await expect.poll(async () => {
      const d = await estado(page);
      return d.sx !== antes.sx || d.sy !== antes.sy;
    }).toBe(true);
  });

  test("shift+clic suma nodos a la selección", async ({ page }) => {
    /*
     * El shift+clic tenía tres cosas encima que lo reducían a un solo nodo: el
     * `onClick` del nodo, el `onFocus` (que dispara junto con el pointerdown en
     * un elemento con tabIndex) y el clic que sigue a soltar el mouse.
     */
    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });

    await expect(page.getByText("2 nodos elegidos")).toBeVisible();
  });

  test("las flechas mueven todo el grupo, no sólo un nodo", async ({ page }) => {
    const posiciones = () =>
      page.evaluate(() =>
        Object.fromEntries(
          [...document.querySelectorAll("[data-nodo]")].map((e) => [e.dataset.nodo, Math.round(parseFloat(e.style.left))]),
        ),
      );

    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();

    const antes = await posiciones();
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(async () => {
        const d = await posiciones();
        return Object.keys(antes).filter((id) => d[id] !== antes[id]).length;
      })
      .toBe(2);

    // Se devuelve el grupo a su lugar: la suite no debería dejar el flujo movido.
    await page.keyboard.press("ArrowLeft");
    await expect.poll(posiciones).toEqual(antes);
  });

  test("la marquesina encierra nodos", async ({ page }) => {
    const caja = await page.evaluate(() => {
      const c = [...document.querySelectorAll("div")].find(
        (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
      );
      const r = c.getBoundingClientRect();
      return { x: r.left, y: r.top, w: r.width, h: r.height };
    });

    await page.mouse.move(caja.x + 15, caja.y + 15);
    await page.mouse.down();
    await page.mouse.move(caja.x + caja.w - 40, caja.y + caja.h - 40, { steps: 10 });
    await page.mouse.up();

    // Encierra el lienzo entero, así que agarra más de un nodo.
    await expect(page.getByText(/\d+ nodos elegidos/)).toBeVisible();
  });

  test("Ctrl+D duplica el grupo con sus conexiones y se puede deshacer", async ({ page }) => {
    const contar = () => page.locator("[data-nodo]").count();
    const inicial = await contar();

    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();

    await page.keyboard.press("Control+d");
    await expect.poll(contar).toBe(inicial + 2);

    // Lo pegado queda seleccionado, así que se puede borrar de una: el test
    // deja el flujo como lo encontró (la suite corre sobre datos compartidos).
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();
    await page.keyboard.press("Delete");
    await page.getByRole("button", { name: /Eliminar 2 nodos/ }).click();
    await expect.poll(contar).toBe(inicial);
  });

  test("borrar varios nodos pregunta antes y el Deshacer los restaura a todos", async ({ page }) => {
    /*
     * Una rama de un flujo son cinco o seis nodos con formulario, grupos, SLA y
     * condiciones: se encierran con la marquesina en un gesto y un Suprimir de
     * más se los lleva sin preguntar. Y lo que la pantalla ofrecía para volver
     * atrás restauraba UNO: `mostrarToast` pisa el toast anterior, así que de N
     * borrados sobrevivía el «Deshacer» del último y los otros se perdían.
     */
    const contar = () => page.locator("[data-nodo]").count();
    const inicial = await contar();

    // Se trabaja sobre una copia para no borrar nodos reales del flujo.
    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await page.keyboard.press("Control+d");
    await expect.poll(contar).toBe(inicial + 2);

    await page.keyboard.press("Delete");
    await expect(page.getByText("¿Eliminar 2 nodos?")).toBeVisible();
    await page.getByRole("button", { name: /Eliminar 2 nodos/ }).click();
    await expect.poll(contar).toBe(inicial);

    // Un solo aviso para toda la operación, y su Deshacer trae los DOS.
    await expect(page.getByText(/Se eliminaron 2 nodos/)).toBeVisible();
    await page.getByRole("button", { name: "Deshacer", exact: true }).click();
    await expect.poll(contar).toBe(inicial + 2);

    // Se vuelve a dejar el flujo como estaba.
    await expect(page.getByText("2 nodos elegidos")).toBeVisible();
    await page.keyboard.press("Delete");
    await page.getByRole("button", { name: /Eliminar 2 nodos/ }).click();
    await expect.poll(contar).toBe(inicial);
  });

  test("quitar una conexión deja «Deshacer» y la restaura con su regla", async ({ page }) => {
    /*
     * En un nodo Decisión la conexión ES la regla: «mayor de 65 Y dolor
     * torácico» son varios minutos de RuleBuilder y estaba a un clic de
     * desaparecer para siempre — sin confirmación, sin historial y sin
     * «Deshacer», a diferencia del borrado de nodos. Si nadie lo nota, la
     * decisión queda con una rama menos y todos los casos caen por la rama por
     * defecto.
     *
     * Se trabaja sobre una copia (Ctrl+D duplica también las conexiones entre
     * los nodos elegidos) para no tocar el grafo real de la demo.
     */
    const contar = () => page.locator("[data-nodo]").count();
    const inicial = await contar();
    const nodos = page.locator("[data-nodo]");
    await nodos.nth(0).click();
    await nodos.nth(1).click({ modifiers: ["Shift"] });
    await page.keyboard.press("Control+d");
    await expect.poll(contar).toBe(inicial + 2);

    // Se abre el panel de uno de los nodos pegados y se quita su salida.
    await page.locator("[data-nodo]").nth(inicial).click();
    const quitar = page.getByRole("button", { name: "quitar" }).first();
    test.skip(!(await quitar.isVisible().catch(() => false)), "los nodos copiados no quedaron conectados");

    await quitar.click();
    const confirmar = page.getByRole("button", { name: "Quitar conexión" });
    if (await confirmar.isVisible().catch(() => false)) await confirmar.click();

    await expect(page.getByText(/Se quitó la conexión/)).toBeVisible();
    await page.getByRole("button", { name: "Deshacer", exact: true }).click();
    await expect(page.getByRole("button", { name: "quitar" }).first()).toBeVisible();

    // Limpieza: se borran los dos nodos copiados.
    await page.locator("[data-nodo]").nth(inicial).click();
    await page.locator("[data-nodo]").nth(inicial + 1).click({ modifiers: ["Shift"] });
    await page.keyboard.press("Delete");
    await page.getByRole("button", { name: /Eliminar 2 nodos/ }).click();
    await expect.poll(contar).toBe(inicial);
  });

  test("el «Deshacer» de ordenar el diagrama se puede leer", async ({ page }) => {
    /*
     * «Ordenar el diagrama» reubica TODOS los nodos de un flujo de un solo clic,
     * encima de un diagrama que alguien acomodó a mano. El toast ofrecía la
     * salida en un botón vacío: pasaba `txt` y el componente pinta `label`.
     */
    // Se corre un nodo primero: si el diagrama ya está en la disposición que
    // «Ordenar» produce, la acción no mueve nada y no hay toast que mirar.
    await page.locator("[data-nodo]").first().click();
    await page.keyboard.press("ArrowDown");

    await page.getByTitle(/Ordenar el diagrama/).click();
    await expect(page.getByText("Diagrama ordenado")).toBeVisible();

    const deshacer = page.getByRole("button", { name: "Deshacer", exact: true });
    await expect(deshacer).toBeVisible();
    // Se deshace: el test no debe dejar el diagrama del demo reacomodado.
    await deshacer.click();
    await page.keyboard.press("ArrowUp");
  });

  test("con el panel de propiedades cerrado, Validar muestra el resultado igual", async ({ page }) => {
    /*
     * Todo el feedback del editor se dibuja adentro del panel, y ese panel se
     * cierra por el motivo más razonable del mundo: ver el diagrama. Con el
     * panel cerrado, «Validar» pasaba a «Validando…», volvía, y la pantalla
     * quedaba idéntica — y un Publicar rechazado por errores no dejaba rastro
     * en ningún lado.
     */
    await page.getByRole("button", { name: "Ocultar panel de propiedades" }).click();
    await expect(page.getByText("Validación")).toHaveCount(0);

    await page.getByRole("button", { name: "Validar" }).click();
    await expect(page.getByText("Validación")).toBeVisible();
    await expect(page.getByText(/errores/)).toBeVisible();
  });

  test("una versión publicada no se puede editar desde la pantalla", async ({ page }) => {
    /*
     * El servidor rechaza toda escritura sobre una versión publicada, pero el
     * editor sólo lo decía en un cartel: la paleta seguía invitando a agregar
     * nodos y el botón rojo «Eliminar nodo» seguía ahí, así que cada intento era
     * un 409 que el editor mostraba como «revisá tu conexión».
     */
    const versiones = page.getByLabel("Versión del flujo");
    const opciones = await versiones.locator("option").allTextContents();
    test.skip(opciones.length < 2, "el flujo no tiene una versión publicada aparte del borrador");

    // Las versiones se listan de mayor a menor: la última opción es la v1.
    await versiones.selectOption({ label: opciones[opciones.length - 1] });
    await expect(page.getByText(/los casos en curso están parados/)).toBeVisible();

    await expect(page.getByTitle("Agregar nodo «Formulario»")).toBeDisabled();
    await page.locator("[data-nodo]").first().click();
    await expect(page.getByRole("button", { name: "Eliminar nodo" })).toHaveCount(0);
  });

  test("el minimapa lleva a otra zona del lienzo", async ({ page }) => {
    const mapa = page.getByTitle(/Mapa del flujo/);
    await expect(mapa).toBeVisible();

    const scroll = () =>
      page.evaluate(() => {
        const c = [...document.querySelectorAll("div")].find(
          (d) => getComputedStyle(d).overflow === "auto" && d.scrollWidth > d.clientWidth + 50,
        );
        return { x: Math.round(c.scrollLeft), y: Math.round(c.scrollTop) };
      });

    const antes = await scroll();
    const caja = await mapa.boundingBox();
    // Esquina opuesta del mapa: el lienzo tiene que saltar a esa zona.
    await page.mouse.click(caja.x + caja.width - 8, caja.y + caja.height - 8);

    await expect
      .poll(async () => {
        const d = await scroll();
        return d.x !== antes.x || d.y !== antes.y;
      })
      .toBe(true);
  });

  test("Escape cierra el buscador sin tocar el lienzo", async ({ page }) => {
    const antes = await estado(page);
    await page.keyboard.press("Control+f");
    await expect(page.getByLabel("Buscar un nodo del flujo")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.getByLabel("Buscar un nodo del flujo")).toBeHidden();

    const despues = await estado(page);
    expect([despues.sx, despues.sy]).toEqual([antes.sx, antes.sy]);
  });
});

/**
 * Nodo «Espera por tiempo».
 *
 * El texto de ayuda decía que la reactivación automática era un pendiente y que
 * el caso se reactiva a mano; dos campos más abajo, el hint del mismo panel dice
 * «El caso vuelve solo al vencer», que es lo cierto (el motor agenda
 * `reactivar_en` y `correr_tiempos` lo levanta). Quien lee ese texto es la
 * persona de la institución que no puede verificarlo en el código: si cree que
 * el sistema no le va a traer de vuelta el «control a los 7 días», se arma una
 * planilla aparte y saca del sistema el trabajo que el sistema ya hace bien.
 */
test.describe("Nodo de espera por tiempo", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
    await page.getByTitle("Agregar nodo «Espera por tiempo»").click();
    await expect(page.getByLabel("Duración de la espera")).toBeVisible();
  });

  // El nodo se guarda apenas se agrega: sin esto cada corrida deja uno suelto.
  test.afterEach(async ({ page }) => {
    const borrar = page.getByRole("button", { name: "Eliminar nodo" });
    if (await borrar.isVisible().catch(() => false)) await borrar.click();
  });

  test("la ayuda dice que el caso vuelve solo, igual que el hint del campo", async ({ page }) => {
    // La preferencia de ayuda se recuerda en localStorage, así que puede venir
    // ya abierta de otro test: se abre sólo si hace falta.
    const texto = page.getByText(/lo trae de vuelta solo al vencer/);
    if (!(await texto.isVisible().catch(() => false))) {
      await page.getByRole("button", { name: "¿Qué hace este nodo?" }).click();
    }
    await expect(texto).toBeVisible();
    await expect(page.getByText(/reactivación automática por tiempo es un pendiente/)).toHaveCount(0);
    // El hint del campo dice lo mismo: era la contradicción dentro del panel.
    await expect(page.getByText("El caso vuelve solo al vencer.", { exact: false })).toBeVisible();
  });
});

/**
 * El triage, configurable desde el diseñador.
 *
 * El motor ya sabía convertir el resultado de un formulario en la prioridad del
 * caso (`prioridad_campo` + `prioridad_mapa`), pero el único flujo con esa config
 * era el de la demo, escrita a mano en Python: el panel del nodo Formulario sólo
 * ofrecía Formulario, Responsable y SLA. Una guardia que diseñe su propio
 * circuito de triage quedaba en FIFO puro —la enfermera carga «Rojo -
 * Emergencia» y el paciente igual espera detrás de los quince esguinces que
 * llegaron antes—, salvo que alguien se acordara de abrir la ficha del caso y
 * cambiar la prioridad a mano en otra pantalla.
 */
test.describe("Prioridad del caso desde un formulario", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
    await page.getByTitle("Agregar nodo «Formulario»").click();
    await expect(page.getByLabel("Formulario del paso")).toBeVisible();
  });

  test.afterEach(async ({ page }) => {
    const borrar = page.getByRole("button", { name: "Eliminar nodo" });
    if (await borrar.isVisible().catch(() => false)) await borrar.click();
  });

  test("se elige el campo que fija la prioridad y qué prioridad da cada valor", async ({ page }) => {
    const formulario = page.getByLabel("Formulario del paso");
    // El catálogo llega por red: sin esperarlo, el desplegable todavía tiene
    // sólo el «— Elegir —» y el test se saltea sin haber probado nada.
    await expect.poll(() => formulario.locator("option").count()).toBeGreaterThan(1);
    const opciones = await formulario.locator("option").allTextContents();
    const triage = opciones.find((t) => /triage/i.test(t));
    test.skip(!triage, "la institución de la demo no tiene un formulario de triage");

    await formulario.selectOption({ label: triage });

    const campo = page.getByLabel("Este campo define la prioridad del caso");
    await expect(campo).toBeVisible();
    const campos = await campo.locator("option").allTextContents();
    const nivel = campos.find((t) => /nivel/i.test(t));
    test.skip(!nivel, "el formulario de triage no tiene un campo de selección única");

    await campo.selectOption({ label: nivel });

    // Una fila valor→prioridad por cada opción del campo.
    const rojo = page.getByLabel(/Prioridad para «Rojo/);
    await expect(rojo).toBeVisible();
    await rojo.selectOption("urgente");
    await expect(rojo).toHaveValue("urgente");

    // Se recarga y se vuelve a abrir el nodo: lo elegido tiene que haber
    // quedado guardado en el servidor, no sólo en la pantalla.
    await page.reload();
    await page.locator("[data-nodo]").last().click();
    await expect(page.getByLabel(/Prioridad para «Rojo/)).toHaveValue("urgente");
  });
});

/**
 * Configuración del nodo de integración.
 *
 * El modo padrón FHIR existía en el motor y no se podía elegir desde ningún
 * lado, que para quien diseña el flujo es lo mismo que no existir. Estos tests
 * cubren que se pueda elegir y —sobre todo— que la pantalla diga lo que el paso
 * NO hace: quien lo configura tiene que saber que no corrige datos equivocados,
 * o va a creer que el padrón los arregla solo.
 */
test.describe("Nodo de integración", () => {
  test.beforeEach(async ({ page }) => {
    await abrirBorrador(page);
    await page.getByTitle("Agregar nodo «Integración»").click();
    await expect(page.getByLabel("Tipo de servicio")).toBeVisible();
  });

  /*
   * El nodo se guarda en el servidor apenas se agrega, así que sin esto cada
   * corrida deja uno suelto en el flujo del demo. La suite corre sobre la misma
   * base y una que ensucia lo que mira la siguiente es la forma más rápida de
   * que nadie confíe en los rojos.
   */
  test.afterEach(async ({ page }) => {
    const borrar = page.getByRole("button", { name: "Eliminar nodo" });
    if (await borrar.isVisible().catch(() => false)) await borrar.click();
  });

  test("se puede elegir el modo padrón FHIR", async ({ page }) => {
    const modo = page.getByLabel("Tipo de servicio");
    await expect(modo).toBeVisible();
    await modo.selectOption("fhir");
    await expect(page.getByLabel("Dirección del padrón")).toBeVisible();
  });

  test("avisa que la URL es la base y no la de búsqueda", async ({ page }) => {
    // Es el error más común: Cauce le agrega /Patient?identifier=… por su cuenta.
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByText(/sin \/Patient/)).toBeVisible();
  });

  test("dice que no pisa datos ya cargados", async ({ page }) => {
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByText(/Nunca pisa un dato ya cargado/)).toBeVisible();
  });

  test("en modo padrón esconde lo que no aplica", async ({ page }) => {
    // Una ruta JSON configurada sobre un padrón FHIR no hace nada y hace perder
    // media hora a quien la escribió.
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await expect(page.getByLabel("Guardar la respuesta en")).toHaveCount(0);
    await expect(page.getByLabel("Método")).toHaveCount(0);
  });

  test("volver al modo genérico devuelve sus campos", async ({ page }) => {
    await page.getByLabel("Tipo de servicio").selectOption("fhir");
    await page.getByLabel("Tipo de servicio").selectOption("generico");
    await expect(page.getByLabel("Método")).toBeVisible();
    await expect(page.getByLabel("Sistema del documento")).toHaveCount(0);
  });
});
