import { expect, test } from "@playwright/test";

import { entrar, esperarPantalla } from "./apoyo";

/**
 * La historia clínica en la pantalla donde se la lee de verdad.
 *
 * Todo lo de acá es sobre lo que el médico VE antes de prescribir: si la alergia
 * está a tres pantallas de scroll, si un borrador se distingue de un asiento
 * firmado, si un estudio pedido se puede confundir con uno hecho. Ninguna de
 * esas cosas la ve un test de backend —el dato viaja bien; lo que fallaba era
 * mostrarlo—.
 *
 * Los estados que el demo no tiene (un borrador sin firmar, un estudio
 * pendiente) se fuerzan con `page.route`, igual que hace legales.spec.js: son
 * justo los estados que van a aparecer el día que alguien use esto en serio, y
 * depender de que el seed los genere es depender de otra cosa.
 */

const CIUDADANO = 28;

function entrada(i, extra = {}) {
  return {
    id: 1000 + i,
    historia: 9999,
    titulo: `Control ambulatorio ${i}`,
    contenido: "Paciente estable, continúa con el mismo esquema. ".repeat(3),
    autor: 5,
    autor_nombre: "Ana Ruiz",
    caso: null,
    firmada: true,
    matricula: "MP 12345",
    fecha: "2026-07-0" + ((i % 9) + 1) + "T10:00:00Z",
    firmada_at: "2026-07-01T10:05:00Z",
    sello: "abc123",
    sello_version: "salud-sha256-v2",
    integra: true,
    revision: `rev1-sintetica-${i}`,
    ...extra,
  };
}

/** Una historia con volumen, una alergia y los tres estados de estudio. */
function historiaDePrueba(extra = {}) {
  return {
    count: 1,
    results: [
      {
        id: 9999,
        ciudadano: CIUDADANO,
        alergias: "Penicilina",
        condiciones: "HTA",
        antecedentes_por: 5,
        antecedentes_por_nombre: "Ana Ruiz",
        antecedentes_at: "2026-07-01T10:00:00Z",
        creada: "2020-01-01T10:00:00Z",
        entradas: Array.from({ length: 10 }, (_, i) => entrada(i)),
        estudios: [
          { id: 1, historia: 9999, tipo: "TAC de cerebro", resultado: "", resultado_display: "", realizado: false, archivo: "", autor: "Laura Méndez", fecha: "2026-08-15" },
          { id: 2, historia: 9999, tipo: "Rx de tórax", resultado: "", resultado_display: "", realizado: true, archivo: "", autor: "Laura Méndez", fecha: "2026-08-10" },
          { id: 3, historia: 9999, tipo: "Laboratorio", resultado: "normal", resultado_display: "Normal", realizado: true, archivo: "", autor: "Laura Méndez", fecha: "2026-08-01" },
        ],
        recetas: [],
        ...extra,
      },
    ],
  };
}

async function conHistoria(page, historia) {
  await page.route(
    (url) => url.pathname === "/api/historias-clinicas/",
    (ruta) => ruta.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(historia),
    }),
  );
}

test.describe("Historia clínica en el celular", () => {
  test("la alergia se ve en la cabecera, sin scrollear", async ({ page }) => {
    /*
     * El panel de ANTECEDENTES sólo es columna a partir de 1024 px; abajo de eso
     * cae DESPUÉS de toda la evolución. Medido a 390 px sobre un paciente con
     * diez entradas, el título arrancaba a 2355 px del inicio: casi tres
     * pantallas. El médico ve el nombre, los contadores y la primera evolución,
     * y prescribe desde ahí.
     */
    await entrar(page, "medico");
    await conHistoria(page, historiaDePrueba());
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);

    const alergia = page.getByText(/^⚠ Alergia:/).first();
    await expect(alergia).toBeVisible();
    const caja = await alergia.boundingBox();
    expect(caja.y, "la alergia quedó abajo del pliegue en un celular").toBeLessThan(500);
  });

  test("el bloque de identificación no queda estrangulado", async ({ page }) => {
    /*
     * El botón «Registrar atención» es hermano de la identificación en un
     * `flex-wrap` y no bajaba de línea: el bloque del medio se encogía a 60 px,
     * el nombre salía en dos líneas y el documento en cuatro renglones.
     * Confirmar que se escribe en la historia del paciente correcto es el
     * chequeo de seguridad más básico que hay.
     */
    await entrar(page, "medico");
    await conHistoria(page, historiaDePrueba());
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);

    // El bloque de identificación es el hermano anterior del botón: se lo mide
    // desde ahí y no por su clase, que es lo que se está cambiando.
    const ancho = await page
      .getByRole("button", { name: "Registrar atención" })
      .evaluate((el) => el.previousElementSibling.getBoundingClientRect().width);
    expect(ancho, "la identificación del paciente quedó en una columna ilegible").toBeGreaterThan(200);
  });

  test("el padrón no se corre para el costado ni corta el botón de alta", async ({ page }) => {
    /*
     * El buscador tenía ancho fijo de 280 px dentro de un flex sin wrap: a 390 px
     * el botón de alta terminaba 58 px afuera y para llegar a él había que
     * arrastrar el panel entero de la app, que se lee como pantalla rota. La
     * guarda de desborde no lo veía porque el que desbordaba era un contenedor
     * con `overflow-auto`, no el documento.
     */
    await entrar(page, "medico");
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto("/pacientes");
    await esperarPantalla(page);

    const boton = page.getByRole("button", { name: "+ Registrar paciente" });
    const caja = await boton.boundingBox();
    expect(caja.x + caja.width, "el botón de alta queda cortado a la derecha").toBeLessThanOrEqual(390);
  });
});

test.describe("Estado de cada asiento de la evolución", () => {
  for (const ok of [true, false]) {
    test(`panel de verificación informa alcance sin certificar alteración (${ok})`, async ({ page }) => {
      await entrar(page, "medico");
      await conHistoria(page, historiaDePrueba({ entradas: [entrada(0, { sello_version: "salud-sha256-v1" })] }));
      await page.route("**/api/historias-clinicas/9999/verificar/", (ruta) => ruta.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ ok, firmadas: 1, selladas: 1, fuera_de_alcance: 0, problemas: [] }),
      }));
      await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
      await esperarPantalla(page);
      await page.getByRole("button", { name: "Verificar la historia", exact: true }).click();
      await expect(page.getByText(ok ? "No se detectaron diferencias" : "Hay problemas de verificación", { exact: true })).toBeVisible();
      await expect(page.getByText("Se compararon 1 entradas con sus sellos.", { exact: true })).toBeVisible();
      await expect(page.getByText("Los sellos históricos tienen límites de verificación.", { exact: true })).toBeVisible();
      await expect(page.getByText(/Sin alteraciones|Hay entradas alteradas/)).toHaveCount(0);
    });
  }

  for (const [nombre, entradas, etiquetas] of [
    ["sello histórico no se presenta como formato actual", [
      entrada(0, { sello_version: "salud-sha256-v1" }),
      entrada(1, { sello_version: "cauce-sha256-v1" }),
    ], ["Firmada · sello histórico", "Firmada · sello histórico"]],
    ["formato desconocido o ausente no acusa alteración ni certifica integridad", [
      entrada(0, { sello_version: "futuro-v3", integra: false }),
      entrada(1, { sello_version: undefined, integra: true }),
    ], ["Firmada · formato no compatible", "Firmada · formato no compatible"]],
    ["formato conocido distingue alteración, integridad y ausencia de sello", [
      entrada(0, { integra: false }),
      entrada(1),
      entrada(2, { sello: "", integra: null }),
    ], ["⚠ Alterada después de firmarse", "Firmada", "Firmada · no verificable"]],
  ]) {
    test(nombre, async ({ page }) => {
      await entrar(page, "medico");
      await conHistoria(page, historiaDePrueba({ entradas }));
      await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
      await esperarPantalla(page);
      for (const etiqueta of new Set(etiquetas)) {
        await expect(page.getByText(etiqueta, { exact: true })).toHaveCount(etiquetas.filter((e) => e === etiqueta).length);
      }
      if (nombre.startsWith("formato desconocido")) {
        await expect(page.getByText("⚠ Alterada después de firmarse", { exact: true })).toHaveCount(0);
        await expect(page.getByText("Firmada", { exact: true })).toHaveCount(0);
      }
    });
  }

  test("un borrador se distingue de una atención firmada", async ({ page }) => {
    /*
     * La única señal era la AUSENCIA de chapa, que se lee igual que «no cargó» o
     * «no aplica». Meses después, quien lee la evolución para reconstruir qué
     * pasó no puede separar el registro firmado del borrador de alguien, y ante
     * un reclamo esa diferencia es toda la diferencia.
     */
    await entrar(page, "medico");
    const h = historiaDePrueba();
    h.results[0].entradas[0] = entrada(0, {
      firmada: false, matricula: "", firmada_at: null, sello: "", integra: true,
      titulo: "Ingresó por guardia",
    });
    await conHistoria(page, h);
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);

    await expect(page.getByText("Sin firmar · borrador")).toBeVisible();
    await expect(page.getByText("Firmada", { exact: true }).first()).toBeVisible();
  });

  test("el borrador se puede corregir y firmar desde la pantalla", async ({ page }) => {
    /*
     * El modal de alta promete con todas las letras que «sin firmar queda como
     * borrador y se puede corregir», y desde la pantalla no se podía: la entrada
     * quedaba en la historia para siempre, sin marca y sin forma de terminarla
     * —no se borran por diseño—. La API ya lo aceptaba.
     */
    const perfilRecibido = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/usuarios/me/" && r.status() === 200);
    await entrar(page, "medico");
    const perfil = await (await perfilRecibido).json();
    const h = historiaDePrueba();
    h.results[0].entradas[0] = entrada(0, {
      firmada: false, matricula: "", firmada_at: null, sello: "", integra: true,
      titulo: "Ingresó por guardia",
      autor: perfil.id,
      autor_nombre: perfil.nombre_completo,
    });
    await conHistoria(page, h);

    let firmado = null;
    let pausarLectura = false;
    let liberarLectura;
    const lecturaDemorada = new Promise((resolve) => { liberarLectura = resolve; });
    await page.route(
      (url) => /\/api\/entradas-historia\/\d+\/$/.test(url.pathname),
      (ruta) => {
        if (ruta.request().method() === "GET") return ruta.fulfill({ status: 200, json: h.results[0].entradas[0] });
        firmado = ruta.request().postDataJSON();
        if (firmado.revision_esperada !== h.results[0].entradas[0].revision) return ruta.fulfill({ status: 409, json: { detail: "El borrador cambió." } });
        if ("contenido" in firmado) {
          h.results[0].entradas[0].contenido = firmado.contenido;
          h.results[0].entradas[0].revision = "rev1-actualizada";
          pausarLectura = true;
        }
        return ruta.fulfill({ status: 200, contentType: "application/json", body: "{}" });
      },
    );

    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);

    // Las acciones van EN la tarjeta del borrador: el «Editar» del panel de
    // antecedentes es otra cosa y machearía igual.
    const tarjeta = page.locator("h3", { hasText: "Ingresó por guardia" }).locator("xpath=../..");
    await expect(tarjeta.getByRole("button", { name: "Editar" })).toBeVisible();
    // Retener el refetch después del PATCH reproduce abrir Firmar sobre la
    // tarjeta anterior. Un refetch no puede sustituir el texto que se confirma.
    await page.route((url) => url.pathname === "/api/historias-clinicas/", async (ruta) => {
      if (pausarLectura) await lecturaDemorada;
      return ruta.fulfill({ status: 200, json: h });
    });
    await tarjeta.getByRole("button", { name: "Editar" }).click();
    const editor = page.getByRole("dialog", { name: "Corregir borrador" });
    await editor.getByLabel("Evolución / observaciones").fill("Contenido actualizado antes de firmar");
    await editor.getByRole("button", { name: "Guardar", exact: true }).click();
    await expect(editor).not.toBeVisible();
    await tarjeta.getByRole("button", { name: "Firmar" }).click();

    // Firmar no tiene deshacer: se confirma leyendo lo que se firma.
    const dialogo = page.getByRole("dialog", { name: "Firmar la atención" });
    await expect(dialogo.getByText(/no se puede editar/)).toBeVisible();
    liberarLectura();
    await expect(dialogo.getByRole("alert")).toContainText("El borrador cambió");
    await expect(dialogo.getByRole("button", { name: "Firmar", exact: true })).toBeDisabled();
    await expect(dialogo.getByLabel("Texto que se firmará")).not.toContainText("Contenido actualizado antes de firmar");
    await dialogo.getByRole("button", { name: "Revisar versión del servidor", exact: true }).click();
    await expect(dialogo.getByRole("region", { name: "Versión actual del servidor" })).toContainText("Contenido actualizado antes de firmar");
    await dialogo.getByRole("button", { name: "Leer esta versión para firmar", exact: true }).click();
    await expect(dialogo.getByLabel("Texto que se firmará")).toContainText("Contenido actualizado antes de firmar");
    await dialogo.getByRole("button", { name: "Firmar" }).click();

    await expect.poll(() => firmado, { message: "no se pidió la firma a la API" }).toEqual({ firmada: true, revision_esperada: "rev1-actualizada" });
  });

  test("un conflicto conserva el texto local y exige revisar el servidor antes de guardar", async ({ page }) => {
    const perfilRecibido = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/usuarios/me/" && r.status() === 200);
    await entrar(page, "medico");
    const perfil = await (await perfilRecibido).json();
    const borrador = entrada(0, { firmada: false, autor: perfil.id, titulo: "Borrador concurrente", contenido: "Texto leído", revision: "rev1-leida" });
    await conHistoria(page, historiaDePrueba({ entradas: [borrador] }));
    const escrituras = [];
    let lecturas = 0;
    await page.route((url) => /\/api\/entradas-historia\/\d+\/$/.test(url.pathname), (ruta) => {
      if (ruta.request().method() === "GET") {
        lecturas += 1;
        return lecturas === 1 ? ruta.fulfill({ status: 503, json: { detail: "Fallo sintético" } })
          : ruta.fulfill({ status: 200, json: { ...borrador, contenido: "Texto guardado desde otra pestaña", revision: "rev1-servidor" } });
      }
      escrituras.push(ruta.request().postDataJSON());
      return escrituras.length === 1 ? ruta.fulfill({ status: 409, json: { detail: "El borrador cambió." } })
        : ruta.fulfill({ status: 200, json: {} });
    });
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);
    await page.locator("#entrada-1000").getByRole("button", { name: "Editar", exact: true }).click();
    const editor = page.getByRole("dialog", { name: "Corregir borrador" });
    const textoLocal = editor.getByLabel("Evolución / observaciones");
    await textoLocal.fill("Mi texto local sin perder");
    await editor.getByRole("button", { name: "Guardar", exact: true }).click();
    await expect(editor.getByRole("alert")).toContainText("Tu texto no se perdió");
    await expect(textoLocal).toHaveValue("Mi texto local sin perder");
    await expect(editor.getByRole("button", { name: "Guardar", exact: true })).toBeDisabled();
    await editor.getByRole("button", { name: "Revisar versión del servidor", exact: true }).click();
    await expect(editor.getByText(/No se pudo consultar la versión actual/)).toBeVisible();
    await expect(textoLocal).toHaveValue("Mi texto local sin perder");
    await editor.getByRole("button", { name: "Revisar versión del servidor", exact: true }).click();
    await expect(editor.getByRole("region", { name: "Versión actual del servidor" })).toContainText("Texto guardado desde otra pestaña");
    await expect(textoLocal).toHaveValue("Mi texto local sin perder");
    await editor.getByRole("button", { name: "Continuar con mi texto revisado", exact: true }).click();
    await editor.getByRole("button", { name: "Guardar", exact: true }).click();
    await expect(editor).not.toBeVisible();
    expect(escrituras).toEqual([
      { titulo: "Borrador concurrente", contenido: "Mi texto local sin perder", revision_esperada: "rev1-leida" },
      { titulo: "Borrador concurrente", contenido: "Mi texto local sin perder", revision_esperada: "rev1-servidor" },
    ]);
  });

  for (const tipo of ["ajeno", "sin autor"]) {
    test(`un borrador ${tipo} conserva contenido pero no permite editar ni firmar`, async ({ page }) => {
      const perfilRecibido = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/usuarios/me/" && r.status() === 200);
      await entrar(page, "medico");
      const perfil = await (await perfilRecibido).json();
      const h = historiaDePrueba({ entradas: [entrada(0, {
        titulo: "Borrador de lectura", contenido: "Contenido clínico permitido para lectura",
        firmada: false, autor: tipo === "ajeno" ? Number(perfil.id) + 100000 : null,
        autor_nombre: tipo === "ajeno" ? "Otro profesional" : null,
        matricula: "", firmada_at: null, sello: "",
      })] });
      await conHistoria(page, h);
      await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
      await esperarPantalla(page);
      const tarjeta = page.locator("h3", { hasText: "Borrador de lectura" }).locator("xpath=../..");
      await expect(tarjeta.getByText("Contenido clínico permitido para lectura")).toBeVisible();
      await expect(tarjeta.getByRole("button", { name: "Editar", exact: true })).toHaveCount(0);
      await expect(tarjeta.getByRole("button", { name: "Firmar", exact: true })).toHaveCount(0);
      await expect(tarjeta.getByText(tipo === "ajeno" ? /Solo Otro profesional puede editar o firmar/ : /no tiene autor identificado: solo lectura/)).toBeVisible();
    });
  }

  test("en simulación la autoría del borrador corresponde al actor real", async ({ page }) => {
    const perfilRecibido = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/usuarios/me/" && r.status() === 200);
    await entrar(page, "medico");
    const perfil = await (await perfilRecibido).json();
    const institucionId = Number(Object.keys(perfil.capacidades_por_institucion || {}).find((id) => id !== "global"));
    const perfilSimulado = { ...perfil, id: Number(perfil.id) + 100000, simulacion: {
      id: "sesion-sintetica", ambito: "institucion", rol: "medico", etiqueta: "Médico",
      institucion: { id: institucionId, nombre: "Hospital sintético" },
      cuenta: { id: Number(perfil.id) + 100000, nombre: "Cuenta de referencia" },
      superusuario: { id: perfil.id, nombre: "Actor real" },
    } };
    await page.route((url) => url.pathname === "/api/usuarios/me/", (ruta) => ruta.fulfill({ status: 200, json: perfilSimulado }));
    await conHistoria(page, historiaDePrueba({ entradas: [entrada(0, {
      titulo: "Borrador del actor real", firmada: false, autor: perfil.id,
      matricula: "", firmada_at: null, sello: "",
    })] }));
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);
    const tarjeta = page.locator("h3", { hasText: "Borrador del actor real" }).locator("xpath=../..");
    await expect(tarjeta.getByRole("button", { name: "Editar", exact: true })).toBeVisible();
    await tarjeta.getByRole("button", { name: "Firmar", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Firmar la atención" }).getByText("Actor real", { exact: true })).toBeVisible();
    delete perfilSimulado.simulacion.superusuario;
    await page.reload();
    await esperarPantalla(page);
    await expect(tarjeta.getByRole("button", { name: "Editar", exact: true })).toHaveCount(0);
    await expect(tarjeta.getByRole("button", { name: "Firmar", exact: true })).toHaveCount(0);
    await expect(tarjeta.getByText(/No se pudo verificar tu identidad real/)).toBeVisible();
  });
});

test.describe("Estudios de la historia", () => {
  test("un estudio pedido y todavía no hecho lo dice", async ({ page }) => {
    /*
     * El motor crea el Estudio al SOLICITARLO y lo marca realizado recién al
     * cerrarse el sub-caso, con el resultado opcional: hay tres estados y la
     * pantalla dibujaba dos, con la ausencia de chapa tapando los dos opuestos.
     * Ver «TAC de cerebro · 15/08/2026 · Laura Méndez» sin ninguna marca lleva a
     * esperar un informe que nadie pidió, o a pedirlo de nuevo.
     */
    await entrar(page, "medico");
    await conHistoria(page, historiaDePrueba());
    await page.goto(`/pacientes/${CIUDADANO}?tab=estudios`);
    await esperarPantalla(page);

    await expect(page.getByText("Pendiente", { exact: true })).toBeVisible();
    await expect(page.getByText("Realizado · sin informe")).toBeVisible();
    await expect(page.getByText("Normal", { exact: true })).toBeVisible();
  });

  test("el contador de la cabecera separa los pedidos de los hechos", async ({ page }) => {
    // «3 estudios» mezclando pedidos con realizados es un número que no se puede
    // usar para nada.
    await entrar(page, "medico");
    await conHistoria(page, historiaDePrueba());
    await page.goto(`/pacientes/${CIUDADANO}?tab=evolucion`);
    await esperarPantalla(page);

    await expect(page.getByText("estudios · 1 pendiente")).toBeVisible();
  });
});

test.describe("Alta de paciente duplicado", () => {
  test("el DNI con puntos encuentra al paciente que ya está cargado", async ({ page }) => {
    /*
     * En Argentina el DNI se escribe con puntos: es como está impreso en el
     * documento que el administrativo tiene en la mano. El detector buscaba con
     * el texto tal cual y comparaba `c.documento === doc`, así que «30.111.222»
     * no macheaba «30111222» y la pantalla no avisaba nada. A partir de ahí hay
     * dos historias clínicas del mismo paciente y no se pueden fusionar.
     */
    await entrar(page, "medico");

    let buscado = null;
    await page.route(
      (url) => url.pathname === "/api/ciudadanos/" && url.searchParams.has("search"),
      (ruta) => {
        buscado = new URL(ruta.request().url()).searchParams.get("search");
        return ruta.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            results: [{
              id: 987654, institucion: 1, codigo: "", nombre: "Juan", apellido: "Pérez",
              documento: "30111222", fecha_nacimiento: "1974-09-11", obra_social: "PAMI",
              domicilio: "", creado: "2020-01-01T10:00:00Z", condiciones: "", alergias: "",
              entradas: 0, estudios: 0, recetas_activas: 0, ultima: null, consentimiento: null,
            }],
          }),
        });
      },
    );

    await page.goto("/pacientes?nuevo=1");
    await esperarPantalla(page);
    await page.getByLabel("Documento").fill("30.111.222");

    await expect(page.getByText(/Ese documento ya está cargado/)).toBeVisible();
    await expect(page.getByText(/Juan Pérez/)).toBeVisible();
    // La fecha de nacimiento, sin correrse un día: `new Date("1974-09-11")` es
    // medianoche UTC y en Argentina se mostraba como el 10.
    await expect(page.getByText(/11\/09\/1974/)).toBeVisible();
    expect(buscado, "se buscó al paciente con el documento sin normalizar").toBe("30111222");
  });
});
