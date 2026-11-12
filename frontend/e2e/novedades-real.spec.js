import fs from "node:fs";
import { randomUUID } from "node:crypto";
import { test, expect } from "@playwright/test";

test.skip(!process.env.SALUD_NOVEDADES_MANIFEST, "Requiere fixture ficticia y servidores locales explícitos.");

async function iniciar(page, baseURL, rol = "operador") {
  expect(["127.0.0.1", "localhost"]).toContain(new URL(baseURL).hostname);
  const datos = JSON.parse(fs.readFileSync(process.env.SALUD_NOVEDADES_MANIFEST, "utf8"));
  expect(datos.purpose).toBe("salud-novedades-e2e");
  const respuesta = await page.request.post("/api/auth/token/", {
    data: { email: datos[rol], password: datos.password },
  });
  expect(respuesta.ok()).toBeTruthy();
  const sesion = await respuesta.json();
  await page.addInitScript(({ access, refresh }) => {
    sessionStorage.setItem("salud.access", access);
    sessionStorage.setItem("salud.refresh", refresh);
  }, sesion);
  return { ...datos, headers: { Authorization: `Bearer ${sesion.access}` } };
}

async function proponer(page, datos, org) {
  const respuesta = await page.request.post(`/api/financiadores/${org.id}/novedades/`, {
    headers: datos.headers, data: { clave: randomUUID(), afiliado: org.afiliado,
      fuente: "Fixture API ficticia", referencia: `FICTICIA-${randomUUID()}`, codigo: "ORIGINAL",
      descripcion: "Antecedente ficticio para el recorrido", motivo: "Preparación aislada del escenario" },
  });
  expect(respuesta.status()).toBe(201);
  return respuesta.json();
}

test("snapshot histórico sin cobertura declara el valor como no registrado", async ({ page, baseURL }, testInfo) => {
  const datos = await iniciar(page, baseURL);
  const org = datos.organizaciones[testInfo.project.name === "mobile-chromium" ? 1 : 0];
  await page.goto(`/financiadores/novedades?financiador=${org.id}`);
  await page.getByRole("button", { name: `Ver novedad ${org.legacy_novedad}`, exact: true }).click();
  const dialogo = page.getByRole("dialog", { name: `Novedad #${org.legacy_novedad}`, exact: true });
  const snapshot = page.locator("section").filter({ has: page.getByRole("heading", { name: "Al registrar", exact: true }) });
  await expect(dialogo).toBeVisible();
  await expect(snapshot.getByText("Cobertura: No registrado", { exact: true })).toBeVisible();
  await expect(snapshot.getByText(/Deshabilitada/)).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialogo).toHaveCount(0);
});

test("recorrido real de registro y conciliación sin efectos", async ({ page, baseURL }, testInfo) => {
  const datos = await iniciar(page, baseURL);
  const org = datos.organizaciones[testInfo.project.name === "mobile-chromium" ? 1 : 0];
  await page.goto(`/financiadores/novedades?financiador=${org.id}`);
  await expect(page.getByRole("button", { name: "Registrar novedad", exact: true })).toBeVisible();
  const antes = await page.request.get(`/api/financiadores/${org.id}/padron/`, { headers: datos.headers });
  expect(antes.ok()).toBeTruthy();
  const huella = await antes.json();
  await page.getByRole("button", { name: "Registrar novedad", exact: true }).click();
  const dialogo = page.getByRole("dialog");
  await dialogo.getByLabel("Buscar persona por documento o nombre").fill(org.documento);
  await expect(dialogo.getByRole("option", { name: /PERSONA FICTICIA [AB]/ })).toBeAttached();
  await dialogo.getByRole("combobox", { name: "Persona del padrón", exact: true }).selectOption(String(org.afiliado));
  await dialogo.getByLabel("Fuente", { exact: true }).fill("Fuente de navegador ficticia");
  await dialogo.getByLabel("Referencia externa").fill(`FICTICIA-${testInfo.project.name}-${Date.now()}`);
  await dialogo.getByLabel("Código informado").fill("SIN-EFECTOS");
  await dialogo.getByLabel("Fecha informada", { exact: true }).fill("2030-01-02");
  await dialogo.getByLabel("Descripción administrativa").fill("Evidencia ficticia para revisión administrativa.");
  await dialogo.getByLabel("Motivo del registro").fill("Comprobar registro sin modificar derechos.");
  const creadaPromise = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/api/financiadores/${org.id}/novedades/`));
  await dialogo.getByRole("button", { name: "Guardar propuesta" }).click();
  const creada = await creadaPromise;
  expect(creada.status()).toBe(201);
  const propuesta = await creada.json();
  await expect(page.getByRole("dialog", { name: `Novedad #${propuesta.id}`, exact: true })).toBeVisible();
  await dialogo.getByLabel("Motivo de la decisión").fill("Conciliación ficticia, sin aplicación al padrón.");
  const resueltaPromise = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/novedades/${propuesta.id}/resolver/`));
  await dialogo.getByRole("button", { name: "Conciliar sin aplicar efectos" }).click();
  const resuelta = await resueltaPromise;
  expect(resuelta.status()).toBe(200);
  expect((await resuelta.json()).efectos_aplicados).toBe(false);
  await expect(dialogo.getByText("Conciliada sin aplicación", { exact: true })).toBeVisible();
  await expect(dialogo.getByRole("region", { name: "Historial de la propuesta" }).getByRole("listitem")).toHaveCount(2);
  const despuesConciliar = await page.request.get(`/api/financiadores/${org.id}/padron/`, { headers: datos.headers });
  expect(await despuesConciliar.json()).toEqual(huella);
  const elegirEstado = dialogo.getByLabel("Estado de cobertura");
  await expect(elegirEstado).toBeEnabled();
  await elegirEstado.focus();
  await elegirEstado.press("ArrowDown");
  await elegirEstado.press("Enter");
  await expect(elegirEstado).toHaveValue("habilitar");
  await dialogo.getByLabel("Motivo de la decisión").fill("Habilitación explícita desde evidencia revisada.");
  const aplicacionPromise = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/novedades/${propuesta.id}/habilitacion-cobertura/`));
  await dialogo.getByRole("button", { name: "Aplicar decisión de cobertura", exact: true }).click();
  const aplicacion = await aplicacionPromise;
  expect(aplicacion.status()).toBe(200);
  const resultado = await aplicacion.json();
  expect(resultado.efectos_aplicados).toBe(false);
  expect(resultado.habilitacion_cobertura.resultado).toBe("cambiada");
  expect(resultado.habilitacion_cobertura.cobertura_habilitada).toBe(true);
  await expect(dialogo.getByText(/Cambio enlazado al historial del padrón/)).toBeVisible();
  const historial = await page.request.get(`/api/financiadores/${org.id}/padron/${org.afiliado}/historial/`, { headers: datos.headers });
  expect(historial.ok()).toBeTruthy();
  const filasHistorial = (await historial.json()).results;
  const evento = filasHistorial.find((fila) => fila.id === resultado.habilitacion_cobertura.historial_id);
  expect(evento).toMatchObject({ origen: "novedad", lote: propuesta.id,
    cambios: { cobertura_habilitada: { anterior: false, nuevo: true } } });
  const padronDespues = await page.request.get(`/api/financiadores/${org.id}/padron/${org.afiliado}/`, { headers: datos.headers });
  expect((await padronDespues.json()).cobertura_habilitada).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("novedades.png"), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(dialogo.getByRole("button", { name: "Cerrar", exact: true }).last()).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(dialogo).toHaveCount(0);
  await page.reload();
  await page.getByRole("button", { name: `Ver novedad ${propuesta.id}`, exact: true }).click();
  const reabierta = page.getByRole("dialog");
  await expect(reabierta.getByText("Conciliada sin aplicación", { exact: true })).toBeVisible();
  await expect(reabierta.getByText(/Cambio enlazado al historial del padrón/)).toBeVisible();
  await page.goto(`/financiadores/padron/${org.afiliado}?financiador=${org.id}&tab=historial`);
  const panelHistorial = page.getByRole("tabpanel", { name: "Historial" });
  await expect(panelHistorial.getByText(`Novedad #${propuesta.id}`, { exact: false })).toBeVisible();
  await expect(panelHistorial.getByText("Novedad del financiador", { exact: false })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("rectificación y descarte dejan historia sin sobrescribir evidencia", async ({ page, baseURL }) => {
  const datos = await iniciar(page, baseURL);
  const org = datos.organizaciones[0];
  const original = await proponer(page, datos, org);
  await page.goto(`/financiadores/novedades?financiador=${org.id}`);
  await page.getByRole("button", { name: `Ver novedad ${original.id}`, exact: true }).click();
  let dialogo = page.getByRole("dialog");
  await dialogo.getByRole("button", { name: "Registrar rectificación" }).click();
  await dialogo.getByLabel("Código informado").fill("RECTIFICADO");
  await dialogo.getByLabel("Motivo del registro").fill("Rectificación ficticia explícita.");
  const creadaPromise = page.waitForResponse((r) => r.request().method() === "POST" && r.url().endsWith(`/api/financiadores/${org.id}/novedades/`));
  await dialogo.getByRole("button", { name: "Guardar propuesta" }).click();
  const creada = await (await creadaPromise).json();
  await expect(page.getByRole("dialog", { name: `Novedad #${creada.id}`, exact: true })).toBeVisible();
  await expect(dialogo.getByText("Revisión de conflictos", { exact: true })).toBeVisible();
  await dialogo.getByLabel("Motivo de la decisión").fill("Se revisó el antecedente; no se aplica al padrón.");
  const conciliar = dialogo.getByRole("button", { name: "Conciliar sin aplicar efectos" });
  await expect(conciliar).toBeDisabled();
  await dialogo.getByRole("checkbox", { name: "Revisé expresamente los conflictos y coincidencias indicados" }).check();
  await conciliar.click();
  await expect(dialogo.getByText("Conciliada sin aplicación", { exact: true })).toBeVisible();
  await expect(dialogo.getByRole("button", { name: "Cerrar", exact: true }).last()).toBeEnabled();
  await dialogo.getByRole("button", { name: "Cerrar", exact: true }).last().click();
  await page.getByRole("button", { name: `Ver novedad ${original.id}`, exact: true }).click();
  await dialogo.getByLabel("Motivo de la decisión").fill("Descarte ficticio conservando el antecedente.");
  await dialogo.getByRole("button", { name: "Descartar propuesta" }).click();
  await expect(dialogo.getByText("Descartada", { exact: true })).toBeVisible();
  const guardada = await page.request.get(`/api/financiadores/${org.id}/novedades/${original.id}/`, { headers: datos.headers });
  const persistida = await guardada.json();
  expect(persistida.original).toEqual(original.original);
  expect(persistida.historia).toHaveLength(2);
});

test("auditoría consulta evidencia pero no recibe acciones de escritura", async ({ page, baseURL }) => {
  const datos = await iniciar(page, baseURL, "auditor");
  const org = datos.organizaciones[0];
  await page.goto(`/financiadores/novedades?financiador=${org.id}`);
  await expect(page.getByRole("list", { name: "Novedades registradas" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Registrar novedad", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: /^Ver novedad / }).first().click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo.getByRole("region", { name: "Evidencia original" })).toBeVisible();
  await expect(dialogo.getByRole("button", { name: "Registrar rectificación" })).toHaveCount(0);
  await expect(dialogo.getByRole("button", { name: "Conciliar sin aplicar efectos" })).toHaveCount(0);
});

test("detalle tardío no reaparece al cerrar y cambiar de financiador", async ({ page, baseURL }) => {
  const datos = await iniciar(page, baseURL);
  const [a, b] = datos.organizaciones;
  const propuesta = await proponer(page, datos, a);
  let liberar, inicio, completado;
  const espera = new Promise((resolve) => { liberar = resolve; });
  const iniciada = new Promise((resolve) => { inicio = resolve; });
  const finalizada = new Promise((resolve) => { completado = resolve; });
  await page.route(`**/api/financiadores/${a.id}/novedades/${propuesta.id}/`, async (route) => {
    const respuestaReal = await route.fetch();
    inicio();
    await espera;
    await route.fulfill({ response: respuestaReal });
    completado();
  });
  await page.goto(`/financiadores/novedades?financiador=${a.id}`);
  await page.getByRole("button", { name: `Ver novedad ${propuesta.id}`, exact: true }).click();
  await iniciada;
  await page.getByRole("dialog").getByRole("button", { name: "Cerrar", exact: true }).last().click();
  const abrirMenu = page.getByRole("button", { name: "Abrir menú", exact: true });
  if (await abrirMenu.isVisible()) await abrirMenu.click();
  await page.getByRole("combobox", { name: "Financiador", exact: true }).selectOption(String(b.id));
  await expect(page).toHaveURL(new RegExp(`financiador=${b.id}`));
  liberar();
  await finalizada;
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: `Ver novedad ${propuesta.id}`, exact: true })).toHaveCount(0);
});
