import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { jsPDF } from "jspdf";

const datos = JSON.parse(readFileSync(process.env.SALUD_PRESCRIPCIONES_MANIFEST, "utf8"));
if (datos.escenario !== "prescripciones-autorizacion-v1" ||
    !datos.escenarios.every((e) => Object.values(e.usuarios).every((email) => email.endsWith("@example.invalid")))) {
  throw new Error("Se requiere fixture ficticia dedicada.");
}
const documento = new jsPDF();
documento.text("Documento de prueba. Sin datos reales ni validez medica.", 15, 20);
const PDF = Buffer.from(documento.output("arraybuffer"));

test("runner de prescripciones no inicia el escenario de importación", async () => {
  const configuracion = (await import("../playwright.prescripciones-real.config.js")).default;
  expect(configuracion.webServer).toBeUndefined();
});

async function ingresar(page, escenario, rol) {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(escenario.usuarios[rol]);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

async function formulario(page, escenario) {
  await ingresar(page, escenario, "institucion");
  await page.goto(`/casos/${escenario.caso}#cobertura-caso`);
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await page.getByRole("combobox", { name: "Prestación a autorizar", exact: true }).selectOption(String(escenario.prestacion));
  await page.getByLabel("Justificación para el financiador", { exact: true }).fill("Solicitud completamente ficticia");
}

async function adjuntar(page) {
  await page.getByLabel("Prescripción (opcional)", { exact: true }).setInputFiles({
    name: "presentacion-original-ficticia.pdf", mimeType: "application/pdf", buffer: PDF,
  });
}

async function detalle(page, escenario, rol) {
  await ingresar(page, escenario, rol);
  await page.goto(`/financiadores/autorizaciones?financiador=${escenario.financiador}`);
  await page.getByRole("row").filter({ has: page.getByRole("button", { name: /^(Ver|Revisar)$/ }) })
    .getByRole("button", { name: /^(Ver|Revisar)$/ }).click();
  await expect(page.getByRole("heading", { name: "Prescripción presentada", exact: true })).toBeVisible();
}

test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "wait" }); });

for (const [indice, nombre, viewport] of [[0, "escritorio", { width: 1365, height: 900 }], [1, "móvil", { width: 390, height: 844 }]]) {
  test(`${nombre}: ingreso real, estado institucional, descarga médica y operación sin contenido`, async ({ page, browser }) => {
    const escenario = datos.escenarios[indice];
    await page.setViewportSize(viewport);
    await formulario(page, escenario);
    await adjuntar(page);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const respuesta = page.waitForResponse((r) => r.url().includes("/autorizaciones-cobertura/con-prescripcion/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
    const r = await respuesta;
    expect(r.status()).toBe(201);
    expect(r.request().headers()["content-type"]).toContain("multipart/form-data;");
    const creada = await r.json();
    expect(creada.prescripcion_estado).toBe("presentada");
    expect(JSON.stringify(creada)).not.toContain("presentacion-original-ficticia.pdf");
    await page.getByRole("button", { name: `Ver solicitud ${creada.id}`, exact: true }).click();
    await expect(page.getByRole("heading", { name: "Prescripción presentada", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Descargar prescripción", exact: true })).toHaveCount(0);
    const medico = await browser.newPage({ viewport });
    const operador = await browser.newPage({ viewport });
    try {
      await detalle(medico, escenario, "medico");
      const boton = medico.getByRole("button", { name: "Descargar prescripción", exact: true });
      await boton.focus();
      const descarga = medico.waitForEvent("download");
      await medico.keyboard.press("Enter");
      const archivo = await descarga;
      expect(archivo.suggestedFilename()).toBe("prescripcion.pdf");
      expect(readFileSync(await archivo.path())).toEqual(PDF);
      expect(await medico.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await detalle(operador, escenario, "operador");
      await expect(operador.getByRole("button", { name: "Descargar prescripción", exact: true })).toHaveCount(0);
      await expect(operador.getByRole("button", { name: "Resolver solicitud", exact: true })).toBeVisible();
    } finally { await medico.close(); await operador.close(); }
  });
}

test("cancelar retira el archivo y conserva el contrato JSON anterior sin adjunto", async ({ page }) => {
  const escenario = datos.escenarios[2];
  await formulario(page, escenario);
  await adjuntar(page);
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await expect(page.getByLabel("Prescripción (opcional)", { exact: true })).toHaveValue("");
  const respuesta = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/autorizaciones-cobertura/" && r.request().method() === "POST");
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  const r = await respuesta;
  expect(r.status()).toBe(201);
  expect(r.request().postDataJSON()).toEqual({ caso: escenario.caso, prestacion: escenario.prestacion,
    cantidad: 1, justificacion: "Solicitud completamente ficticia", intento: expect.any(String), clave: expect.any(String) });
  expect((await r.json()).prescripcion_estado).toBeUndefined();
});

const rutaDescarga = /\/autorizaciones-cobertura\/\d+\/prescripcion\/\?/;

for (const [indice, decision, estado, viewport, conObservacion] of [
  [5, "aprobar", "Aprobada", { width: 1365, height: 900 }],
  [6, "rechazar", "Rechazada", { width: 390, height: 844 }],
  [7, "aprobar", "Aprobada", { width: 1365, height: 900 }, true],
  [8, "rechazar", "Rechazada", { width: 390, height: 844 }, true],
]) {
  test(`${conObservacion ? "observación y reenvío" : "evaluación médica"}: ${decision} resuelve la misma solicitud con designaciones independientes`, async ({ page, browser }, testInfo) => {
    const escenario = datos.escenarios[indice];
    await page.setViewportSize(viewport);
    await formulario(page, escenario);
    await adjuntar(page);
    const ingreso = page.waitForResponse((r) => r.url().includes("/con-prescripcion/") && r.request().method() === "POST");
    await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
    const presentada = await ingreso;
    expect(presentada.status()).toBe(201);
    const creada = await presentada.json();
    const lector = await browser.newPage({ viewport });
    const operador = await browser.newPage({ viewport });
    const evaluador = await browser.newPage({ viewport });
    try {
      await detalle(lector, escenario, "medico");
      await expect(lector.getByRole("button", { name: "Descargar prescripción", exact: true })).toBeVisible();
      await expect(lector.getByRole("button", { name: "Resolver solicitud", exact: true })).toHaveCount(0);
      await detalle(operador, escenario, "operador");
      await expect(operador.getByRole("button", { name: "Descargar prescripción", exact: true })).toHaveCount(0);
      await expect(operador.getByRole("button", { name: "Resolver solicitud", exact: true })).toBeVisible();
      await detalle(evaluador, escenario, "evaluador");
      if (conObservacion) {
        expect(creada.plazo_respuesta).toBeTruthy();
        await evaluador.getByRole("button", { name: "Resolver solicitud", exact: true }).click();
        await evaluador.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("observar");
        await evaluador.getByLabel("Motivo de la decisión", { exact: true }).fill("Aclarar referencia administrativa ficticia");
        const observacion = evaluador.waitForResponse((r) => r.url().includes(`/${creada.id}/resolver/`) && r.request().method() === "POST");
        await evaluador.getByRole("button", { name: "Registrar decisión", exact: true }).click();
        const observada = await observacion;
        expect(observada.status()).toBe(200);
        expect(await observada.json()).toMatchObject({ id: creada.id, estado: "observada", revision: 2, plazo_respuesta: creada.plazo_respuesta });
        await expect(evaluador.getByRole("dialog")).toHaveCount(0);
        await page.reload();
        await page.getByRole("button", { name: `Ver solicitud ${creada.id}`, exact: true }).click();
        await expect(page.getByRole("button", { name: "Descargar prescripción", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "Responder observación", exact: true }).click();
        await page.getByLabel("Justificación actualizada", { exact: true }).fill("Referencia aclarada sin transcribir contenido clínico");
        const reenvio = page.waitForResponse((r) => r.url().includes(`/${creada.id}/reenviar/`) && r.request().method() === "POST");
        await page.getByRole("button", { name: "Reenviar solicitud", exact: true }).focus();
        await page.keyboard.press("Enter");
        const reenviada = await reenvio;
        expect(reenviada.status()).toBe(200);
        expect(await reenviada.json()).toMatchObject({ id: creada.id, estado: "pendiente", revision: 3, prescripcion_estado: "presentada", plazo_respuesta: creada.plazo_respuesta });
        await expect(page.getByRole("dialog")).toHaveCount(0);
        await evaluador.reload();
        await evaluador.getByRole("row").filter({ has: evaluador.getByRole("button", { name: /^(Ver|Revisar)$/ }) })
          .getByRole("button", { name: /^(Ver|Revisar)$/ }).click();
      }
      const descarga = evaluador.waitForEvent("download");
      await evaluador.getByRole("button", { name: "Descargar prescripción", exact: true }).focus();
      await evaluador.keyboard.press("Enter");
      expect(readFileSync(await (await descarga).path())).toEqual(PDF);
      await evaluador.getByRole("button", { name: "Resolver solicitud", exact: true }).click();
      await evaluador.getByRole("combobox", { name: "Decisión", exact: true }).selectOption(decision);
      await evaluador.getByLabel("Motivo de la decisión", { exact: true }).fill("Referencia administrativa de evaluación ficticia");
      if (decision === "aprobar") {
        const hoy = new Date().toLocaleDateString("sv-SE", { timeZone: "America/Argentina/Buenos_Aires" });
        await evaluador.getByLabel("Evidencia de la decisión", { exact: true }).fill("Constancia de revisión ficticia. Sin contenido clínico.");
        await evaluador.getByLabel("Cantidad autorizada", { exact: true }).fill("1");
        await evaluador.getByLabel("Válida desde", { exact: true }).fill(hoy);
        await evaluador.getByLabel("Válida hasta", { exact: true }).fill(hoy);
      }
      expect(await evaluador.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      const resolucion = evaluador.waitForResponse((r) => r.url().includes(`/${creada.id}/resolver/`) && r.request().method() === "POST");
      await evaluador.getByRole("button", { name: "Registrar decisión", exact: true }).focus();
      await evaluador.keyboard.press("Enter");
      const respuesta = await resolucion;
      expect(respuesta.status()).toBe(200);
      const resuelta = await respuesta.json();
      expect(resuelta.id).toBe(creada.id);
      expect(resuelta.estado).toBe(estado.toLowerCase());
      expect(resuelta.revision).toBe(creada.revision + (conObservacion ? 3 : 1));
      expect(resuelta.plazo_respuesta).toBe(creada.plazo_respuesta);
      expect(resuelta.puede_resolver).toBe(false);
      expect(resuelta.historial.map((h) => h.accion)).toEqual(conObservacion ? ["solicitar", "observar", "reenviar", decision] : ["solicitar", decision]);
      expect(resuelta.cantidades).toEqual({ comprometida: 0, consumida: 0, disponible: decision === "aprobar" ? 1 : 0 });
      await expect(evaluador.getByRole("dialog")).toHaveCount(0);
      await page.reload();
      await expect(page.getByRole("button", { name: /^Ver solicitud \d+$/, exact: false })).toHaveCount(1);
      await page.getByRole("button", { name: `Ver solicitud ${creada.id}`, exact: true }).click();
      const modal = page.getByRole("dialog");
      await expect(modal.getByText(estado, { exact: true }).first()).toBeVisible();
      await expect(modal.getByRole("heading", { name: "Prescripción presentada", exact: true })).toBeVisible();
      await expect(modal.getByRole("button", { name: "Descargar prescripción", exact: true })).toHaveCount(0);
      await page.screenshot({ path: testInfo.outputPath(`evaluacion-${decision}.png`) });
    } finally { await lector.close(); await operador.close(); await evaluador.close(); }
  });
}

test("rechazo inyectado: error visible y ninguna descarga", async ({ page }) => {
  await detalle(page, datos.escenarios[3], "medico");
  let descargas = 0;
  page.on("download", () => { descargas += 1; });
  await page.route(rutaDescarga, (route) => route.fulfill({ status: 403, json: { detail: "Acceso denegado ficticio" } }));
  await page.getByRole("button", { name: "Descargar prescripción", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("Acceso denegado ficticio");
  expect(descargas).toBe(0);
});

test("respuesta demorada real no entrega archivo después de cerrar el detalle", async ({ page }) => {
  await detalle(page, datos.escenarios[3], "medico");
  let liberar, recibida;
  const espera = new Promise((resolve) => { liberar = resolve; });
  const llegada = new Promise((resolve) => { recibida = resolve; });
  let descargas = 0;
  page.on("download", () => { descargas += 1; });
  await page.route(rutaDescarga, async (route) => { recibida(); await espera; await route.continue(); });
  await page.getByRole("button", { name: "Descargar prescripción", exact: true }).click();
  await llegada;
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const respuesta = page.waitForResponse(rutaDescarga);
  liberar();
  const r = await respuesta;
  expect(r.status()).toBe(200);
  await r.finished();
  await page.evaluate(() => new Promise(requestAnimationFrame));
  expect(descargas).toBe(0);
});

test("respuesta perdida tras commit: reintento explícito conserva clave, archivo y solicitud", async ({ page }) => {
  const escenario = datos.escenarios[4];
  await formulario(page, escenario);
  await adjuntar(page);
  const claves = [];
  let solicitud;
  await page.route("**/autorizaciones-cobertura/con-prescripcion/", async (route) => {
    claves.push(route.request().postData().match(/name="clave"\r?\n\r?\n([^\r\n]+)/)?.[1]);
    if (claves.length === 1) {
      const respuesta = await route.fetch();
      expect(respuesta.status()).toBe(201);
      solicitud = (await respuesta.json()).id;
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  const form = page.locator("form").filter({ has: page.getByLabel("Prescripción (opcional)", { exact: true }) });
  await expect(form.getByRole("alert")).toBeVisible();
  expect(claves).toHaveLength(1);
  await expect(page.getByLabel("Prescripción (opcional)", { exact: true })).not.toHaveValue("");
  const respuesta = page.waitForResponse((r) => r.url().includes("/con-prescripcion/") && r.status() === 201);
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  expect((await (await respuesta).json()).id).toBe(solicitud);
  expect(claves).toHaveLength(2);
  expect(claves[0]).toMatch(/^[0-9a-f-]{36}$/);
  expect(claves[1]).toBe(claves[0]);
  await expect(page.getByRole("button", { name: /^Ver solicitud \d+$/ })).toHaveCount(1);
});
