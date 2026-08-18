import { expect, test } from "@playwright/test";

import { entrar, entrarPlataforma, esperarPantalla, fijarTema } from "./apoyo";

/**
 * Capturas de TODAS las pantallas reales, para la presentación.
 *
 * No prueba nada: mira y guarda. Igual comprueba dos cosas antes de cada foto
 * —que la pantalla no esté en estado de error y que tenga contenido— con
 * `expect.soft`, así la corrida saca todas las capturas y al final dice cuáles
 * no sirven para llevar a la presentación en vez de cortar en la primera.
 *
 * Requiere el stack levantado y la demo sembrada:
 *   docker compose up -d
 *   docker compose exec backend python manage.py seed_volumen --rehacer
 *
 * Se corre con:  npx playwright test e2e/capturas.spec.js
 */

const CARPETA = "../diseño/docs/captures-app";
const API = process.env.CAUCE_API || "http://127.0.0.1:8000";

/*
 * Por qué NO 1440x900 a 1x:
 *
 * - La altura es el problema real. Pantallas como el constructor de formularios
 *   dan a cada panel su propio scroll: con 900 px de alto la captura sale con
 *   cuatro barras de scroll y media lista cortada. Con 1120 entra el contenido.
 * - `deviceScaleFactor: 2` saca el PNG al doble de píxeles. Un 1600x1120 a 1x
 *   puesto en un slide de 1920 se agranda un 20% y el texto queda blando; a 2x
 *   se reduce y queda nítido.
 *
 * El DPR no se puede cambiar con `setViewportSize`, así que va por `test.use`.
 */
test.use({ viewport: { width: 1600, height: 1120 }, deviceScaleFactor: 2 });

/*
 * A propósito NO es `mode: "serial"`. Los tests son independientes —cada uno
 * entra con su usuario y navega solo— y en serial una pantalla que sale mal
 * saltea todas las que siguen: la primera corrida sacó 15 de 29 capturas por un
 * fallo en /inicio. La corrida tiene que sacar todo lo que pueda y recién al
 * final decir qué no sirve. El orden igual está garantizado por `workers: 1`.
 */

/** `expect` que no corta la corrida: junta los fallos y los informa al final. */
const blando = expect.configure({ soft: true });

test.beforeEach(async ({ page }) => {
  // Tema claro desde antes del primer pintado: el script del <head> lo lee de
  // localStorage, así que ponerlo después obliga a recargar. Vale también para
  // las pantallas sin sesión, donde `fijarTema` no se puede usar (pide el aside).
  await page.addInitScript(() => localStorage.setItem("cauce.tema", "claro"));
  // Sin animaciones en curso las capturas son reproducibles.
  await page.emulateMedia({ reducedMotion: "reduce" });
});

/** Guarda la captura y avisa si la pantalla no es presentable. */
async function foto(page, nombre) {
  // `.then(() => true)`: el FontFaceSet no es serializable y `evaluate` fallaría.
  await page.evaluate(() => document.fonts.ready.then(() => true));

  /*
   * Esperar a que la pantalla tenga contenido, en vez de medirla de una.
   *
   * `esperarPantalla` puede pasar de largo: comprueba que no haya ningún
   * `role="status"` y, apenas recargada, React todavía no montó los esqueletos.
   * Cuenta cero, pasa, y la foto sale con los esqueletos puestos — fue
   * exactamente lo que pasó con /inicio del médico. Acá se espera el resultado
   * (texto en pantalla y ningún cargador vivo), que es lo que la foto necesita.
   */
  await blando
    .poll(
      async () => {
        if (await page.locator('[role="status"]').count()) return 0;
        const main = await page.locator("main").last().innerText().catch(() => "");
        return (main || (await page.locator("body").innerText())).trim().length;
      },
      { message: `${nombre}: la pantalla quedó cargando o salió vacía`, timeout: 20_000 },
    )
    .toBeGreaterThan(40);

  /*
   * Después de esperar: si la pantalla cargó un error, el error ES el contenido.
   *
   * Se busca por `role="alert"` y no por el texto del error. Antes el patrón
   * incluía `403|500` y marcó como fallida la lista de historias clínicas: matcheó
   * el DNI de un paciente. Los únicos tres `role="alert"` de la app son estados de
   * error (el general, el de login y el de la pantalla de llamados), así que
   * encontrarlo es señal de que algo falló y no de que había un número parecido.
   */
  const error = page.locator('[role="alert"]').first();
  blando(await error.isVisible().catch(() => false), `${nombre}: la pantalla está en estado de error`).toBe(false);

  await page.screenshot({ path: `${CARPETA}/${nombre}`, fullPage: false });
}

/**
 * Espera a que el menú del rol esté resuelto.
 *
 * Las capacidades del rol llegan en una llamada aparte de la sesión, y hasta que
 * contesta el Shell no tiene grupos de menú, el rótulo del rol dice «Usuario» y
 * /inicio cae en el panel de institución en vez de «Mi trabajo». No alcanza con
 * esperar a que no quede nada cargando: ese estado intermedio no tiene esqueletos
 * ni spinner, así que pasa los dos filtros y la foto sale de OTRA pantalla —fue lo
 * que pasó con /inicio del médico, capturado con el menú vacío.
 *
 * Se espera un grupo del menú, que es señal positiva: todos los roles que se
 * capturan tienen al menos uno, y el estado sin capacidades no tiene ninguno.
 */
async function esperarMenu(page) {
  await expect(page.locator("aside").first().getByText(/^(SISTEMA|TRABAJO|REGISTROS)$/).first()).toBeVisible();
}

/** Pantalla de lista o detalle dentro de la sesión: navegar, esperar, sacar. */
async function pantalla(page, ruta, nombre) {
  await page.goto(ruta);
  await fijarTema(page, "claro"); // recarga y espera a que no quede nada cargando
  await esperarMenu(page); // ...y que el rol haya resuelto su menú
  await foto(page, nombre);
}

/** Abre la primera fila de la tabla y espera la URL de detalle. */
async function primeraFila(page, urlDetalle) {
  const fila = page.locator("tbody tr").first();
  await expect(fila).toBeVisible();
  await fila.click();
  await page.waitForURL(urlDetalle);
  await esperarPantalla(page);
}

// --------------------------------------------------------------------------- //
// Sin sesión
// --------------------------------------------------------------------------- //
test("01 login", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await foto(page, "01-login.png");
});

test("17 pantalla de llamados", async ({ page, request }) => {
  // Es una TV de sala de espera: se captura a su tamaño real, como en pantalla.spec.js.
  await page.setViewportSize({ width: 1920, height: 1080 });
  // Mismo camino que `pantalla.spec.js`: se le pide el token a un nodo con fila.
  const auth = await request.post(`${API}/api/auth/token/`, {
    data: { email: "admin@cauce.local", password: "admin1234" },
  });
  const { access } = await auth.json();
  const nodos = await request.get(`${API}/api/nodos/?tipo=atencion&page_size=100`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const lista = (await nodos.json()).results;
  const sala = lista.find((n) => n.config?.con_fila) || lista[0];
  const r = await request.post(`${API}/api/nodos/${sala.id}/pantalla/`, {
    headers: { Authorization: `Bearer ${access}` },
  });
  const { token } = await r.json();

  await page.goto(`/pantalla/${token}`);
  // Esta pantalla no tiene aside: la señal de lista es que dejó de conectar.
  await expect(page.getByText("Conectando…")).toBeHidden();
  await expect(page.getByText(/Aguarde a ser llamado|LLAMANDO|URGENTE/).first()).toBeVisible();
  await foto(page, "17-pantalla-llamados.png");
});

// --------------------------------------------------------------------------- //
// Super admin: directorio de plataforma (antes de elegir institución)
// --------------------------------------------------------------------------- //
test("02 directorio de plataforma", async ({ page }) => {
  await entrarPlataforma(page);
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await expect(page.locator('[role="status"]')).toHaveCount(0);
  await foto(page, "02-directorio.png");
});

test("03 alta de institución", async ({ page }) => {
  await entrarPlataforma(page);
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.getByRole("button", { name: "Nueva institución" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await foto(page, "03-alta-institucion.png");
});

// --------------------------------------------------------------------------- //
// Admin dentro de la institución
// --------------------------------------------------------------------------- //
test.describe("admin", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "admin");
  });

  test("04 tablero", async ({ page }) => {
    await pantalla(page, "/dashboard", "04-tablero.png");
  });

  test("05 estructura", async ({ page }) => {
    await pantalla(page, "/estructura", "05-estructura.png");
  });

  test("06 administración", async ({ page }) => {
    await pantalla(page, "/administracion", "06-administracion.png");
  });

  test("07 formularios", async ({ page }) => {
    await pantalla(page, "/formularios", "07-formularios.png");
  });

  test("08 detalle de formulario", async ({ page }) => {
    await page.goto("/formularios");
    await esperarPantalla(page);
    await esperarMenu(page);
    await primeraFila(page, /\/formularios\/\d+/);
    await foto(page, "08-formulario-detalle.png");
  });

  test("09 flujos", async ({ page }) => {
    await pantalla(page, "/flujos", "09-flujos.png");
  });

  test("10 y 11 diseñador de flujos", async ({ page }) => {
    await page.goto("/flujos");
    await esperarPantalla(page);
    await esperarMenu(page);
    await page.locator("tbody tr").first().click();
    await page.waitForURL(/\/flujos\/\d+/);
    // El lienzo está listo cuando hay nodos dibujados (igual que editor.spec.js).
    await expect(page.locator("[data-nodo]").first()).toBeVisible();
    await foto(page, "10-flujo-editor.png");

    // La configuración del nodo es una ventana: se abre con doble clic.
    await page.locator("[data-nodo]").nth(1).dblclick();
    await expect(page.getByRole("dialog")).toBeVisible();
    await foto(page, "11-flujo-editor-nodo.png");
  });

  test("12 mapa de flujos", async ({ page }) => {
    await pantalla(page, "/mapa", "12-mapa-flujos.png");
  });

  test("28 registro de accesos", async ({ page }) => {
    await pantalla(page, "/accesos", "28-accesos.png");
  });
});

// --------------------------------------------------------------------------- //
// Operación: médico de guardia
// --------------------------------------------------------------------------- //
test.describe("médico", () => {
  test.beforeEach(async ({ page }) => {
    await entrar(page, "medico");
  });

  test("13 mi trabajo", async ({ page }) => {
    await pantalla(page, "/inicio", "13-mi-trabajo.png");
  });

  test("14 bandeja", async ({ page }) => {
    await pantalla(page, "/bandeja", "14-bandeja.png");
  });

  test("15 filas", async ({ page }) => {
    await pantalla(page, "/filas", "15-filas.png");
  });

  test("16 detalle del puesto", async ({ page }) => {
    /*
     * Al puesto se llega desde «Mis puestos», que vive en /inicio (la fila no
     * enlaza a ningún puesto). Con más de un área, /inicio abre en «Mis áreas» y
     * hay que entrar a una primero.
     */
    await page.goto("/inicio");
    await esperarPantalla(page);
    await esperarMenu(page); // sin esto, /inicio puede ser todavía el panel de institución
    const areas = page.getByRole("heading", { name: "Mis áreas" });
    if (await areas.isVisible().catch(() => false)) {
      await page.getByText("Entrar →").first().click();
    }
    const puestos = page.getByRole("heading", { name: "Mis puestos" });
    await expect(puestos, "el médico no tiene puestos en la demo sembrada").toBeVisible();
    await puestos.locator("xpath=following-sibling::*[1]").locator("button").first().click();
    await page.waitForURL(/\/puesto\/\d+/);
    await esperarPantalla(page);
    await foto(page, "16-puesto.png");
  });

  test("18 casos", async ({ page }) => {
    await pantalla(page, "/casos", "18-casos.png");
  });

  test("19 detalle del caso", async ({ page }) => {
    await page.goto("/casos");
    await esperarPantalla(page);
    await esperarMenu(page);
    await primeraFila(page, /\/casos\/\d+/);
    await foto(page, "19-caso-detalle.png");
  });

  test("20 agenda", async ({ page }) => {
    /*
     * Elegir una agenda que atienda el día que se muestra.
     *
     * La pantalla abre con la primera agenda del listado y cada profesional
     * atiende ciertos días: la de Traumatología no atiende viernes, así que la
     * captura salía con «La agenda no atiende este día». No es un error —el
     * estado vacío es correcto— pero como lámina de «Turnos programados» no
     * muestra nada. Se prueban las agendas hasta dar con una que tenga turnos.
     */
    await page.goto("/agenda");
    await fijarTema(page, "claro");
    await esperarMenu(page);

    const agendas = page.locator("select").first();
    const vacia = page.getByText("La agenda no atiende este día");
    const opciones = await agendas.locator("option").evaluateAll((os) => os.map((o) => o.value));
    for (const valor of opciones) {
      await agendas.selectOption(valor);
      await esperarPantalla(page);
      if (!(await vacia.isVisible().catch(() => false))) break;
    }
    blando(
      await vacia.isVisible().catch(() => false),
      "20-agenda.png: ninguna de las agendas atiende hoy, la lámina sale vacía",
    ).toBe(false);

    await foto(page, "20-agenda.png");
  });

  test("21 internación", async ({ page }) => {
    await pantalla(page, "/internacion", "21-internacion.png");
  });

  test("22 farmacia", async ({ page }) => {
    await pantalla(page, "/farmacia", "22-farmacia.png");
  });

  test("23 red de traslados", async ({ page }) => {
    await pantalla(page, "/red", "23-red.png");
  });

  test("25 historia clínica", async ({ page }) => {
    await pantalla(page, "/historia", "25-historia.png");
  });

  test("26 detalle de la historia", async ({ page }) => {
    await page.goto("/historia");
    await esperarPantalla(page);
    await esperarMenu(page);
    await primeraFila(page, /\/historia\/\d+/);
    await foto(page, "26-historia-detalle.png");
  });

  test("27 legajo", async ({ page }) => {
    await pantalla(page, "/legajo", "27-legajo.png");
  });

  test("29 notificaciones", async ({ page }) => {
    await pantalla(page, "/notificaciones", "29-notificaciones.png");
  });
});

// --------------------------------------------------------------------------- //
// Jefe de área
// --------------------------------------------------------------------------- //
test("24 supervisión", async ({ page }) => {
  await entrar(page, "jefe");
  await pantalla(page, "/supervision", "24-supervision.png");
});
