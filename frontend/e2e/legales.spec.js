import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla, sinDesborde } from "./apoyo";

/**
 * Las tres piezas legales, vistas desde la pantalla.
 *
 * En el backend ya están cubiertas. Acá se prueba lo que ningún test de motor
 * ve: que estén al alcance de quien tiene que usarlas y ocultas para quien no.
 * El registro de accesos dice quién miró la historia de quién —es tan sensible
 * como lo que audita—, así que que aparezca en el menú equivocado no es un
 * detalle de UI.
 */

test.describe("Registro de accesos", () => {
  test("abrir una historia queda registrado, con nombre y apellido", async ({ page }) => {
    /*
     * El circuito entero de la ley en un test: alguien mira la historia de una
     * persona y eso queda anotado. Es lo único que importa —leer una historia
     * no deja ninguna marca en ella—, y ninguna prueba de motor lo ve, porque
     * el rastro lo deja la pantalla al pedir el dato.
     *
     * Navegar por el sistema NO genera accesos, y está bien que no: registrar
     * la fila de espera o el tablero llenaría esto de ruido hasta volverlo
     * inútil. Por eso el test abre una historia de verdad en vez de dar por
     * sentado que entrar alcanza.
     */
    await entrar(page, "jefe");
    await page.goto("/historia");
    await esperarPantalla(page);
    // Se sigue al paciente por el documento y no por el apellido: la celda
    // empieza con las iniciales del avatar, que también son texto.
    const celda = await page.locator("tbody tr").first().locator("td").first().innerText();
    const dni = celda.match(/DNI\s+(\S+)/)[1];
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/historia\/\d+/);
    await esperarPantalla(page);

    await page.getByRole("link", { name: "Registro de accesos" }).click();
    await expect(page.getByRole("heading", { name: "Registro de accesos" })).toBeVisible();
    await esperarPantalla(page);
    await expect(page.locator("tbody").getByText(`DNI ${dni}`).first()).toBeVisible();
  });

  test("un médico no lo ve en el menú", async ({ page }) => {
    // El permiso del frontend copia a `PuedeAuditar` del backend. Si se abriera
    // de más, el menú ofrecería un link que responde 403.
    await entrar(page, "medico");
    await expect(page.getByRole("link", { name: "Registro de accesos" })).toHaveCount(0);
  });

  test("dice qué registra antes de que alguien saque conclusiones", async ({ page }) => {
    // Un listado del padrón y abrir la historia de una persona son «un acceso»
    // los dos en la tabla; sin la aclaración se leen igual.
    await entrar(page, "jefe");
    await page.goto("/accesos");
    await expect(page.getByText(/no la navegación general del sistema/)).toBeVisible();
  });

  test("no ofrece borrar ni editar nada", async ({ page }) => {
    // Un registro de auditoría con un botón de borrar no sirve para auditar.
    await entrar(page, "jefe");
    await page.goto("/accesos");
    await esperarPantalla(page);
    await expect(page.getByRole("button", { name: /Eliminar|Borrar|Editar/ })).toHaveCount(0);
  });

  test("no desborda en ancho de tablet ni de celular", async ({ page }) => {
    await entrar(page, "jefe");
    await page.goto("/accesos");
    await esperarPantalla(page);
    await sinDesborde(page, 1024);
    await sinDesborde(page, 390);
  });
});

test.describe("Consentimiento e integridad en la historia", () => {
  async function abrirUnaHistoria(page) {
    await page.goto("/historia");
    await esperarPantalla(page);
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/historia\/\d+/);
    await esperarPantalla(page);
  }

  test("el consentimiento se ve sin tener que buscarlo", async ({ page }) => {
    await entrar(page, "medico");
    await abrirUnaHistoria(page);
    await expect(page.getByText("CONSENTIMIENTO DE DATOS")).toBeVisible();
  });

  test("aclara que la urgencia no depende del consentimiento", async ({ page }) => {
    // Sin esto, un «revocado» en pantalla invita a dudar antes de atender.
    await entrar(page, "medico");
    await abrirUnaHistoria(page);
    await expect(page.getByText(/La atención de urgencia no depende/)).toBeVisible();
  });

  test("el alta avisa que no reemplaza a los registros anteriores", async ({ page }) => {
    // Acá no hay deshacer: tiene que quedar claro ANTES de guardar.
    await entrar(page, "medico");
    await abrirUnaHistoria(page);
    await page.getByRole("button", { name: /Registrar (consentimiento|revocación)/ }).click();
    await expect(page.getByText(/No reemplaza ni borra los anteriores/)).toBeVisible();
  });

  test("cada opción de «cómo se tomó» la acepta el backend", async ({ page }) => {
    /*
     * El selector repetía de este lado una lista que define el modelo, y se
     * había desincronizado: ofrecía «Electrónico», que no existe, y el alta
     * devolvía 400. Una lista duplicada se desincroniza sin que nada avise, así
     * que se manda cada opción de verdad contra la API.
     */
    await entrar(page, "medico");
    await abrirUnaHistoria(page);

    const fallidas = [];
    page.on("response", (r) => {
      if (r.url().includes("/api/consentimientos/") && r.request().method() === "POST" && !r.ok()) {
        fallidas.push(`${r.status()} al guardar`);
      }
    });

    await page.getByRole("button", { name: /Registrar (consentimiento|revocación)/ }).click();
    const modo = page.getByLabel("Cómo se tomó");
    const opciones = await modo.locator("option").evaluateAll((os) => os.map((o) => o.value));
    expect(opciones.length).toBeGreaterThan(1);

    for (const opcion of opciones) {
      await modo.selectOption(opcion);
      // `exact`: sin eso también machea «Registrar consentimiento», el botón
      // del panel que quedó detrás del modal.
      const guardar = page.getByRole("button", { name: "Registrar", exact: true });
      await guardar.click();
      // Que el modal se cierre es la señal de que guardó. El aviso de «Registrado»
      // no sirve: el de la vuelta anterior sigue en pantalla y machea igual.
      await expect(guardar).toBeHidden();
      await page.getByRole("button", { name: /Registrar (consentimiento|revocación)/ }).click();
    }
    expect(fallidas, `el backend rechazó opciones del selector: ${fallidas}`).toEqual([]);
  });

  test("se puede verificar que la historia no fue alterada", async ({ page }) => {
    await entrar(page, "medico");
    await abrirUnaHistoria(page);
    const boton = page.getByRole("button", { name: "Verificar la historia" });
    // Sólo hay panel de integridad si el paciente tiene historia abierta.
    if (!(await boton.isVisible().catch(() => false))) test.skip();
    await boton.click();
    await expect(page.getByText(/Sin alteraciones|Hay entradas alteradas/)).toBeVisible();
  });

  test("no canta «sin alteraciones» cuando no hay nada que comprobar", async ({ page }) => {
    /*
     * El backend devuelve `ok: true` porque no ENCONTRÓ problemas, y sin
     * entradas selladas no puede encontrar ninguno. La primera versión de este
     * panel mostraba «Sin alteraciones» en verde arriba de «0 de 11 selladas»:
     * un certificado de algo que no se comprobó, que es exactamente lo que el
     * sellado existe para no hacer.
     *
     * Se fuerza la respuesta en vez de depender del demo porque el demo ahora
     * sella todo, y este caso —historias anteriores al sellado— es justo el que
     * va a aparecer el día que alguien instale esto sobre datos viejos.
     */
    await entrar(page, "medico");
    await page.route("**/historias-clinicas/*/verificar/", (ruta) =>
      ruta.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, firmadas: 11, selladas: 0, problemas: [] }),
      }),
    );
    await abrirUnaHistoria(page);
    await page.getByRole("button", { name: "Verificar la historia" }).click();
    await expect(page.getByText("No verificable")).toBeVisible();
    await expect(page.getByText("Sin alteraciones")).toHaveCount(0);
  });

  test("el paciente puede saber quién miró su historia", async ({ page }) => {
    // Es el derecho concreto de la ley, y hay que poder contestarlo en el
    // momento en que lo pregunta.
    await entrar(page, "jefe");
    await abrirUnaHistoria(page);
    await page.getByRole("tab", { name: /Quién la miró/ }).click();
    await expect(
      page.getByText(/Nadie consultó esta historia/).or(page.locator("main").getByText(/Consulta de un/).first()),
    ).toBeVisible();
  });

  test("a quien no puede auditar se lo explica, no se le miente con una lista vacía", async ({ page }) => {
    // Una lista vacía diría «nadie la miró», que es lo contrario de la verdad.
    await entrar(page, "medico");
    await abrirUnaHistoria(page);
    await page.getByRole("tab", { name: /Quién la miró/ }).click();
    await expect(page.getByText("No tenés permiso para ver esta lista")).toBeVisible();
  });
});

/**
 * Aviso de proceso periódico detenido, en el tablero.
 *
 * Si el reloj del motor se muere, la aplicación sigue respondiendo y las
 * pantallas cargan: lo único que pasa es que los pacientes en espera por tiempo
 * dejan de volver. Nadie lo descubre hasta que alguien pregunta por un caso
 * parado hace tres días.
 */
test.describe("Procesos detenidos", () => {
  const DETENIDO = {
    servicios: {
      correr_tiempos: { estado: "atrasado", hace_segundos: 5400, detalle: "" },
      recordar_turnos: { estado: "al día", hace_segundos: 60, detalle: "" },
    },
    atrasados: ["correr_tiempos"],
  };

  async function conEstado(page, cuerpo, status) {
    await page.route("**/api/estado/", (r) =>
      r.fulfill({ status, contentType: "application/json", body: JSON.stringify(cuerpo) }),
    );
  }

  test("el tablero avisa cuando el reloj del motor se detuvo", async ({ page }) => {
    await entrar(page, "admin");
    await conEstado(page, DETENIDO, 503);
    await page.goto("/dashboard");
    await expect(page.getByText("Un proceso del sistema dejó de correr")).toBeVisible();
  });

  test("dice qué se rompe, no sólo qué se detuvo", async ({ page }) => {
    // «correr_tiempos está atrasado» no le dice nada a quien dirige un hospital.
    await entrar(page, "admin");
    await conEstado(page, DETENIDO, 503);
    await page.goto("/dashboard");
    await expect(page.getByText(/no vuelven al circuito/)).toBeVisible();
  });

  test("con todo al día no muestra ningún cartel", async ({ page }) => {
    /*
     * Un cartel verde permanente que dice «todo bien» se vuelve parte del fondo
     * en una semana, y entonces nadie lo mira el día que cambia. Lo que tiene
     * que llamar la atención es la excepción.
     */
    await entrar(page, "admin");
    await conEstado(page, { servicios: {}, atrasados: [] }, 200);
    await page.goto("/dashboard");
    await esperarPantalla(page);
    await expect(page.getByText(/proceso.* del sistema dejó|procesos del sistema dejaron/)).toHaveCount(0);
  });
});

/**
 * El egreso de internación pregunta POR QUÉ.
 *
 * Sin el motivo, todo egreso quedaba registrado como «alta» —incluido un
 * fallecimiento—. El recorrido del paciente miente justo en el lugar donde se
 * mira cuando alguien reclama, y no se puede contar mortalidad ni derivaciones
 * por sector, que es el dato que jefatura reporta hacia arriba.
 */
test.describe("Egreso de internación", () => {
  test("el egreso ofrece los motivos reales, no sólo «alta»", async ({ page }) => {
    await entrar(page, "medico");

    // El caso internado se busca por la API y no recorriendo la tabla: en la
    // primera página de Casos puede no haber ninguno, y el test se salteaba sin
    // haber probado nada.
    const caso = await page.evaluate(async () => {
      const tok = sessionStorage.getItem("cauce.access") ?? localStorage.getItem("cauce.access");
      const r = await fetch("/api/camas/?estado=ocupada&page_size=20", {
        headers: { Authorization: `Bearer ${tok}` },
      });
      const d = await r.json();
      return (d.results || d).map((c) => c.caso).find(Boolean) || null;
    });
    test.skip(!caso, "no hay ninguna cama ocupada en el demo");

    await page.goto(`/casos/${caso}`);
    await esperarPantalla(page);
    await page.getByRole("button", { name: "Egreso" }).click();

    const motivo = page.getByLabel("Motivo del egreso");
    await expect(motivo).toBeVisible();
    const opciones = await motivo.locator("option").allTextContents();
    expect(opciones).toContain("Fallecimiento");
    expect(opciones).toContain("Derivación a otra institución");
  });
});
