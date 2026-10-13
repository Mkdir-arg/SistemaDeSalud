import { test, expect } from "@playwright/test";
import { readFileSync, accessSync } from "node:fs";

if (!process.env.PADRON130_MANIFEST || !process.env.PADRON130_PASSWORD || !process.env.PADRON130_XLSX) {
  throw new Error("Preflight padrón130: faltan PADRON130_MANIFEST, PADRON130_PASSWORD y/o PADRON130_XLSX externos del entorno aislado autorizado. No se omiten pruebas.");
}
accessSync(process.env.PADRON130_XLSX);
const datos = JSON.parse(readFileSync(process.env.PADRON130_MANIFEST, "utf8"));
if (datos.escenario !== "padron130-v1" || !datos.fecha_carga || !datos.financiadores?.A?.id || !datos.financiadores?.B?.id) throw new Error("El manifiesto no pertenece al escenario aislado padrón130.");
for (const perfil of ["admin", "operador", "salud", "cobranza", "auditor", "orgB"]) {
  if (!datos.usuarios?.[perfil]?.email) throw new Error(`Falta la cuenta ficticia ${perfil} en el manifiesto.`);
}
for (const caso of ["titular", "conyuge", "estudiante", "integrante_5", "monotributo", "continuidad", "desempleo", "finalizado", "futuro", "orgB"]) {
  if (!datos.afiliados?.[caso]?.id) throw new Error(`Falta el caso ficticio ${caso} en el manifiesto.`);
}
const organizacion = datos.financiadores.A.id;
const rutaAPI = (caso) => `/api/financiadores/${organizacion}/padron/${datos.afiliados[caso].id}/`;
const rutaUI = (caso, contexto = "") => `/financiadores/padron/${datos.afiliados[caso].id}?financiador=${organizacion}${contexto}`;

async function loginUI(page, perfil = "operador") {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.usuarios[perfil].email);
  await page.getByLabel(/^Contraseña/).fill(process.env.PADRON130_PASSWORD);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
}
async function autenticacionAPI(request, perfil = "operador") {
  const respuesta = await request.post("/api/auth/token/", { data: { email: datos.usuarios[perfil].email, password: process.env.PADRON130_PASSWORD } });
  expect(respuesta.status(), `Cuenta ficticia ${perfil} disponible`).toBe(200);
  const { access } = await respuesta.json();
  return { Authorization: `Bearer ${access}` };
}
async function leer(request, ruta, headers) {
  const respuesta = await request.get(ruta, { headers });
  expect(respuesta.status()).toBe(200);
  return respuesta.json();
}
test.beforeAll(async ({ request }) => {
  const headers = await autenticacionAPI(request);
  const ficha = await leer(request, rutaAPI("titular"), headers);
  expect(ficha.id).toBe(datos.afiliados.titular.id);
  expect(ficha.revision).toBeGreaterThan(0);
  expect(ficha.permisos).toEqual(expect.objectContaining({ salud_consulta: false, cobranza_consulta: false }));
});

test("contacto persiste fuera de React, conserva contexto y deja auditoría real", async ({ page, request, browser }) => {
  const headers = await autenticacionAPI(request);
  const previo = await leer(request, rutaAPI("titular"), headers);
  const telefono = `demo130-${Date.now()}`;
  await loginUI(page);
  await page.goto(rutaUI("titular", "&estado=todos&regimen=dependencia&search=00100&padron_page=2"));
  await page.getByRole("button", { name: "Editar contacto", exact: true }).click();
  await page.getByRole("dialog").getByLabel("Teléfono", { exact: true }).fill(telefono);
  await page.getByRole("dialog").getByLabel("Motivo del cambio").fill("Ensayo ficticio: corrección de contacto 130");
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("region", { name: "Contacto", exact: true }).getByText(telefono, { exact: true })).toBeVisible();
  const guardado = await leer(request, rutaAPI("titular"), headers);
  expect(guardado.telefono).toBe(telefono);
  expect(guardado.revision).toBeGreaterThan(previo.revision);
  const historial = await leer(request, `${rutaAPI("titular")}historial/`, headers);
  expect(historial.results.some((evento) => evento.cambios?.telefono?.anterior === previo.telefono && evento.cambios?.telefono?.nuevo === telefono && evento.usuario_nombre && evento.motivo)).toBe(true);
  const nuevoContexto = await browser.newContext({ baseURL: "http://127.0.0.1:8230", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" });
  try {
    const nuevaPagina = await nuevoContexto.newPage();
    await loginUI(nuevaPagina);
    await nuevaPagina.goto(rutaUI("titular"));
    await expect(nuevaPagina.getByRole("region", { name: "Contacto", exact: true }).getByText(telefono, { exact: true })).toBeVisible();
  } finally { await nuevoContexto.close(); }
  await page.getByRole("region", { name: "Grupo familiar" }).getByRole("link", { name: datos.afiliados.conyuge.nombre, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/padron/${datos.afiliados.conyuge.id}\\?`));
  expect(new URL(page.url()).searchParams.get("padron_page")).toBe("2");
  expect(new URL(page.url()).searchParams.has("autorizaciones_page")).toBe(false);
  await page.getByRole("link", { name: "← Volver al padrón", exact: true }).click();
  expect(new URL(page.url()).searchParams.get("regimen")).toBe("dependencia");
  // Se restaura sólo el dato editado; el historial del ensayo permanece.
  const restaurar = await request.patch(rutaAPI("titular"), { headers, data: { revision: guardado.revision, motivo: "Ensayo ficticio: restaurar contacto", telefono: previo.telefono } });
  expect(restaurar.status()).toBe(200);
});

test("409 visible preserva edición y no vuelve a escribir una versión obsoleta", async ({ page, request }) => {
  const headers = await autenticacionAPI(request);
  await loginUI(page);
  await page.goto(rutaUI("titular"));
  await page.getByRole("button", { name: "Editar contacto", exact: true }).click();
  const previo = await leer(request, rutaAPI("titular"), headers);
  const cambio = await request.patch(rutaAPI("titular"), { headers, data: { revision: previo.revision, motivo: "Ensayo ficticio: concurrencia", telefono: `concurrente130-${Date.now()}` } });
  expect(cambio.status()).toBe(200);
  await page.getByRole("dialog").getByLabel("Teléfono", { exact: true }).fill("no-debe-guardarse");
  await page.getByRole("dialog").getByLabel("Motivo del cambio").fill("Ensayo ficticio: versión anterior");
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText("Otra persona modificó");
  await expect(page.getByRole("button", { name: "Guardar cambios", exact: true })).toBeDisabled();
  const actual = await leer(request, rutaAPI("titular"), headers);
  expect(actual.telefono).not.toBe("no-debe-guardarse");
  expect((await request.patch(rutaAPI("titular"), { headers, data: { revision: actual.revision, motivo: "Ensayo ficticio: restaurar contacto concurrente", telefono: previo.telefono } })).status()).toBe(200);
});

test("auditor, organización ajena y designaciones sensibles independientes", async ({ page, request, browser }) => {
  await loginUI(page, "auditor");
  await page.goto(rutaUI("titular"));
  await expect(page.getByRole("heading", { name: "Estado administrativo", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Editar / })).toHaveCount(0);
  // El seed designa explícitamente al auditor para lectura de ambos bloques.
  await expect(page.getByRole("heading", { name: "Condiciones de salud informadas", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cobranza administrativa informada", exact: true })).toBeVisible();
  const auditor = await autenticacionAPI(request, "auditor");
  const ficha = await leer(request, rutaAPI("titular"), auditor);
  expect(ficha).not.toHaveProperty("cbu");
  expect(ficha).not.toHaveProperty("cud");
  expect((await request.patch(rutaAPI("titular"), { headers: auditor, data: { revision: ficha.revision, motivo: "Ensayo negativo", telefono: "no" } })).status()).toBe(403);
  for (const bloque of ["salud", "cobranza"]) {
    const protegido = await leer(request, `${rutaAPI("titular")}${bloque}/`, auditor);
    expect((await request.patch(`${rutaAPI("titular")}${bloque}/`, { headers: auditor, data: { revision: protegido.revision, motivo: "Ensayo negativo de auditor" } })).status()).toBe(403);
  }
  for (const perfil of ["operador", "admin", "salud", "cobranza", "auditor"]) {
    const headers = await autenticacionAPI(request, perfil);
    for (const bloque of ["salud", "cobranza"]) {
      const respuesta = await request.get(`${rutaAPI("integrante_5")}${bloque}/`, { headers });
      const designado = perfil === bloque || ["admin", "auditor"].includes(perfil);
      expect(respuesta.status(), `${perfil} / ${bloque}`).toBe(designado ? 200 : 403);
      const historial = await request.get(`${rutaAPI("integrante_5")}${bloque}/historial/`, { headers });
      expect(historial.status()).toBe(designado ? 200 : 403);
    }
  }
  const ajeno = await autenticacionAPI(request, "orgB");
  expect([403, 404]).toContain((await request.get(rutaAPI("titular"), { headers: ajeno })).status());
  const contexto = await browser.newContext({ baseURL: "http://127.0.0.1:8230", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" });
  try {
    const operador = await contexto.newPage();
    const sensibles = [];
    operador.on("request", (peticion) => { if (/\/padron\/\d+\/(salud|cobranza)\//.test(peticion.url())) sensibles.push(peticion.url()); });
    await loginUI(operador);
    await operador.goto(rutaUI("integrante_5"));
    await expect(operador.getByRole("heading", { name: "Estado administrativo", exact: true })).toBeVisible();
    await expect(operador.getByRole("heading", { name: "Condiciones de salud informadas", exact: true })).toHaveCount(0);
    await expect(operador.getByRole("heading", { name: "Cobranza administrativa informada", exact: true })).toHaveCount(0);
    expect(sensibles).toEqual([]);
  } finally { await contexto.close(); }
});

test("baja administrativa y mora informada conservan derechos; legajo sin binario", async ({ page, request }) => {
  const headers = await autenticacionAPI(request);
  const continuidad = await leer(request, rutaAPI("continuidad"), headers);
  expect(continuidad.estado_administrativo).toBe("baja_administrativa");
  expect(continuidad.vigente).toBe(true);
  const monotributo = await leer(request, rutaAPI("monotributo"), headers);
  expect(monotributo.vigente).toBe(true);
  const cobranza = await autenticacionAPI(request, "cobranza");
  expect((await leer(request, `${rutaAPI("monotributo")}cobranza/`, cobranza)).situacion).toBe("deuda");
  await loginUI(page);
  await page.goto(rutaUI("continuidad"));
  await expect(page.getByRole("region", { name: "Ficha administrativa del padrón" }).getByText("Derechos actuales: Vigentes.", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Legajo administrativo" })).toContainText("sin archivo adjunto");
  const legajo = await leer(request, `${rutaAPI("estudiante")}legajo/`, headers);
  expect(legajo.results.some((documento) => documento.tipo === "estudio" && documento.adjunto === false)).toBe(true);
});

test("documento, CUIL, apellido y número buscan el mismo afiliado en servidor", async ({ page, request }) => {
  const headers = await autenticacionAPI(request);
  const titular = await leer(request, rutaAPI("titular"), headers);
  await loginUI(page);
  await page.goto(`/financiadores/padron?financiador=${organizacion}&estado=todos`);
  for (const termino of [titular.documento, titular.cuil, titular.apellidos, titular.numero]) {
    expect(termino).toBeTruthy();
    await page.getByRole("searchbox", { name: "Buscar por afiliado, documento o nombre", exact: true }).fill(termino);
    const consulta = page.waitForResponse((respuesta) => {
      const url = new URL(respuesta.url());
      return url.pathname === `/api/financiadores/${organizacion}/padron/` && url.searchParams.get("search") === termino;
    });
    await page.getByRole("searchbox", { name: "Buscar por afiliado, documento o nombre", exact: true }).press("Enter");
    const respuesta = await consulta;
    expect(respuesta.status()).toBe(200);
    expect((await respuesta.json()).results.some((item) => item.id === titular.id)).toBe(true);
    await expect(page.getByRole("link", { name: titular.nombre, exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByRole("combobox", { name: "Estado administrativo", exact: true }).selectOption("baja_administrativa");
  await expect.poll(async () => new URL(page.url()).searchParams.get("estado_administrativo")).toBe("baja_administrativa");
  await page.reload();
  await expect(page.getByRole("button", { name: "Quitar filtro Estado administrativo: Baja administrativa" })).toBeVisible();
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(page.getByRole("combobox", { name: "Estado administrativo", exact: true })).toHaveValue("baja_administrativa");
});

test("legajo y transición de trámite se escriben, recargan y auditan", async ({ page, request }) => {
  const headers = await autenticacionAPI(request);
  const previo = await leer(request, rutaAPI("estudiante"), headers);
  const legajoPrevio = await leer(request, `${rutaAPI("estudiante")}legajo/`, headers);
  const documento = legajoPrevio.results.find((item) => item.tipo === "estudio");
  expect(documento).toBeTruthy();
  const hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" });
  await loginUI(page);
  await page.goto(rutaUI("estudiante"));
  await page.getByRole("region", { name: "Legajo administrativo", exact: true }).getByRole("button", { name: "Editar presentación", exact: true }).first().click();
  const modal = page.getByRole("dialog");
  await modal.getByRole("combobox", { name: "Estado de presentación", exact: true }).selectOption("verificado");
  await modal.getByLabel("Fecha de verificación", { exact: true }).fill(hoy);
  await modal.getByLabel("Vencimiento", { exact: true }).fill(hoy);
  await modal.getByLabel("Motivo del cambio").fill("Ensayo ficticio: verificación de presentación");
  await modal.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(modal).toHaveCount(0);
  const escrito = await leer(request, `${rutaAPI("estudiante")}legajo/`, headers);
  expect(escrito.results.find((item) => item.id === documento.id)).toEqual(expect.objectContaining({ estado: "verificado", adjunto: false, verificado_en: hoy }));
  await page.getByRole("button", { name: "Editar trámite y credencial", exact: true }).click();
  await page.getByRole("dialog").getByRole("combobox", { name: "Estado del trámite", exact: true }).selectOption("completo");
  await page.getByRole("dialog").getByLabel("Motivo del cambio").fill("Ensayo ficticio: completar trámite documentado");
  await page.getByRole("dialog").getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.reload();
  const actualizado = await leer(request, rutaAPI("estudiante"), headers);
  expect(actualizado.estado_tramite).toBe("completo");
  expect(actualizado.desde).toBe(previo.desde);
  expect(actualizado.finalizado_en).toBe(previo.finalizado_en);
  expect((await leer(request, `${rutaAPI("estudiante")}historial/`, headers)).results.some((evento) => evento.cambios?.estado_tramite?.nuevo === "completo")).toBe(true);
  // Retirar primero la transición permite restaurar la presentación pendiente.
  const restaurado = await request.patch(rutaAPI("estudiante"), { headers, data: { revision: actualizado.revision, motivo: "Ensayo ficticio: restaurar trámite", estado_tramite: previo.estado_tramite } });
  expect(restaurado.status()).toBe(200);
  const { id, adjunto, ...camposDocumento } = documento;
  expect((await request.patch(`${rutaAPI("estudiante")}legajo/`, { headers, data: { ...camposDocumento, id, revision: (await restaurado.json()).revision, motivo: "Ensayo ficticio: restaurar presentación" } })).status()).toBe(200);
});

async function snapshotPadron(request, headers) {
  const filas = [];
  for (let page = 1; ; page += 1) {
    const data = await leer(request, `/api/financiadores/${organizacion}/padron/?estado=todos&page=${page}`, headers);
    filas.push(...data.results);
    if (!data.next) break;
  }
  return Promise.all(filas.map(async (afiliado) => ({ id: afiliado.id, revision: afiliado.revision, historial: (await leer(request, `/api/financiadores/${organizacion}/padron/${afiliado.id}/historial/`, headers)).count })));
}

test("XLSX v2 real: preview sin efectos, aplicación parcial, rechazos y repetición", async ({ page, request }) => {
  test.setTimeout(90000);
  const headers = await autenticacionAPI(request, "admin");
  const previo = await snapshotPadron(request, headers);
  const finalizado = await leer(request, rutaAPI("finalizado"), headers);
  await loginUI(page, "admin");
  await page.goto(`/financiadores/padron?financiador=${organizacion}&estado=todos`);
  await page.getByRole("button", { name: "Importar Excel", exact: true }).click();
  await expect(page.getByRole("dialog").getByLabel("Versión de plantilla")).toHaveCount(0);
  const plantillaDescarga = page.waitForEvent("download");
  await page.getByRole("dialog").getByRole("button", { name: "Descargar plantilla", exact: true }).click();
  const plantillaVigente = await plantillaDescarga;
  expect(plantillaVigente.suggestedFilename()).toBe("plantilla-padron.xlsx");
  expect(await plantillaVigente.failure()).toBeNull();
  expect([...readFileSync(await plantillaVigente.path()).subarray(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
  await page.getByRole("dialog").getByLabel("Archivo Excel (.xlsx)").setInputFiles(process.env.PADRON130_XLSX);
  const preview = page.waitForResponse((respuesta) => respuesta.request().method() === "POST" && new URL(respuesta.url()).pathname === `/api/financiadores/${organizacion}/importaciones/`);
  await page.getByRole("button", { name: "Revisar archivo", exact: true }).click();
  const lote = await (await preview).json();
  expect(lote.resumen.total).toBe(6);
  expect(lote.resumen.valida).toBe(2);
  expect((lote.resumen.rechazada || 0) + (lote.resumen.revision || 0)).toBe(4);
  expect(await snapshotPadron(request, headers)).toEqual(previo);
  await expect(page.getByRole("textbox", { name: /Motivo de revisión de fila/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Importar 2 filas válidas", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Se aplicaron 2 filas" })).toBeVisible();
  const aplicado = await snapshotPadron(request, headers);
  // Soporta reensayo: la muestra pudo aplicarse antes, pero no crea duplicados.
  expect(aplicado.length).toBeGreaterThanOrEqual(previo.length);
  expect(aplicado.length).toBeLessThanOrEqual(previo.length + 2);
  expect((await leer(request, rutaAPI("finalizado"), headers)).finalizado_en).toBe(finalizado.finalizado_en);
  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar filas rechazadas", exact: true }).click();
  const archivoRechazos = await descarga;
  expect(archivoRechazos.suggestedFilename()).toBe("filas-para-corregir.xlsx");
  expect(await archivoRechazos.failure()).toBeNull();
  const contenidoRechazos = readFileSync(await archivoRechazos.path());
  expect([...contenidoRechazos.subarray(0, 4)]).toEqual([0x50, 0x4b, 0x03, 0x04]);
  expect((await request.post(`/api/financiadores/${organizacion}/confirmar-importacion/`, { headers, data: { importacion: lote.id, revisiones_duplicados: {} } })).status()).toBe(200);
  expect(await snapshotPadron(request, headers)).toEqual(aplicado);
  const repetir = await request.post(`/api/financiadores/${organizacion}/importaciones/`, { headers, multipart: { tipo: "padron", clave: crypto.randomUUID(), archivo: { name: "ensayo-padron130.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: readFileSync(process.env.PADRON130_XLSX) } } });
  expect([200, 201]).toContain(repetir.status());
  const nuevoLote = await repetir.json();
  expect((await request.post(`/api/financiadores/${organizacion}/confirmar-importacion/`, { headers, data: { importacion: nuevoLote.id, revisiones_duplicados: {} } })).status()).toBe(200);
  expect(await snapshotPadron(request, headers)).toEqual(aplicado);
});
