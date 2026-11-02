import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const datos = JSON.parse(readFileSync(process.env.SALUD_BORRADORES_MANIFEST, "utf8"));
if (datos.escenario !== "borradores-derechos-v1" || !datos.usuarios.admin.endsWith("@example.invalid")) throw new Error("Se requiere fixture ficticia dedicada.");
async function abrir(page, rol = "admin") {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(datos.usuarios[rol]);
  await page.getByLabel(/^Contraseña/).fill(datos.password);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto(`/financiadores/borradores?financiador=${datos.organizaciones[0]}`);
}

test("administración consulta borradores sin activar derechos", async ({ page }) => {
  await abrir(page);
  await expect(page.getByRole("heading", { name: "Reglas de derechos", exact: true })).toBeVisible();
  await expect(page.getByText("Guardar una versión no aprueba ni activa derechos.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeVisible();
});


test.afterEach(async ({ page }) => { await page.unrouteAll({ behavior: "wait" }); });
async function completar(page, codigo) {
  await page.getByLabel("Código de regla", { exact: true }).fill(codigo);
  await page.getByLabel("Versión", { exact: true }).fill("1");
  await page.getByRole("combobox", { name: "Régimen", exact: true }).selectOption("dependencia");
  await page.getByLabel("Inicio técnico", { exact: true }).fill("2030-01-01");
  await page.getByLabel("Fuente informada", { exact: true }).fill("Fuente completamente ficticia");
  await page.getByLabel("Fecha de consulta técnica", { exact: true }).fill("2030-01-15");
  await page.getByLabel("Motivo del registro", { exact: true }).fill("Verificación ficticia no operativa");
}
async function guardar(page, codigo) {
  await completar(page, codigo);
  const respuesta = page.waitForResponse((r) => r.url().endsWith("/borradores-derechos/") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  expect((await respuesta).status()).toBe(200);
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true }).locator("..").getByText("Borrador", { exact: true })).toBeVisible();
  await expect(page.getByText("Borrador guardado. Los derechos no cambiaron.", { exact: true })).toBeVisible();
}

test("guarda versión real, conserva historial y navega desde el menú", async ({ page }) => {
  await abrir(page);
  await page.getByRole("link", { name: "Planes", exact: true }).click();
  await page.getByRole("link", { name: "Reglas de derechos", exact: true }).click();
  const codigo = `ficticio-desktop-${Date.now()}`;
  await guardar(page, codigo);
  await page.reload();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Activar|Aprobar/ })).toHaveCount(0);
});

test("consulta de auditor sin formulario de escritura", async ({ page }) => {
  await abrir(page, "auditor");
  await expect(page.getByText("Acceso de consulta. La administración del financiador puede registrar versiones.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Código de regla", { exact: true })).toHaveCount(0);
});

test("móvil y teclado guardan una versión ficticia sin desbordar", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await abrir(page);
  const campo = page.getByLabel("Código de regla", { exact: true });
  await expect(campo).toBeEnabled();
  await campo.focus(); await page.keyboard.press("Tab");
  await expect(page.getByLabel("Versión", { exact: true })).toBeFocused();
  await guardar(page, `ficticio-movil-${Date.now()}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("respuesta perdida después del commit exige consultar, sin reintento automático", async ({ page }) => {
  await abrir(page);
  let escrituras = 0;
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    escrituras += 1;
    const real = await route.fetch();
    expect(real.status()).toBe(200);
    await route.abort();
  });
  const codigo = `ficticio-perdida-${Date.now()}`;
  await completar(page, codigo);
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("El resultado de una escritura fallida puede ser desconocido");
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  expect(escrituras).toBe(1);
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
  expect(escrituras).toBe(1);
});

test("una consulta anterior no contamina otro financiador", async ({ page }) => {
  await abrir(page);
  const codigo = `ficticio-ambito-${Date.now()}`;
  await guardar(page, codigo);
  let liberar, inicio;
  const espera = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { inicio = r; });
  await page.route(`**/financiadores/${datos.organizaciones[0]}/borradores-derechos/`, async (route) => {
    inicio(); await espera; await route.continue();
  });
  try {
    await page.reload(); await iniciada;
    await page.getByLabel("Financiador", { exact: true }).selectOption(String(datos.organizaciones[1]));
    await expect(page.getByRole("heading", { name: "Nueva versión", exact: true })).toBeVisible();
    const anterior = page.waitForResponse((r) => r.url().includes(`/financiadores/${datos.organizaciones[0]}/borradores-derechos/`));
    liberar(); await anterior;
    await expect(page.getByLabel("Financiador", { exact: true })).toHaveValue(String(datos.organizaciones[1]));
    await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toHaveCount(0);
  } finally { liberar(); }
});


test("doble clic durante POST mantiene una sola escritura", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-doble-${Date.now()}`);
  let liberar, inicio, escrituras = 0;
  const espera = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { inicio = r; });
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    escrituras += 1; inicio(); await espera; await route.continue();
  });
  try {
    await page.getByRole("button", { name: "Guardar borrador", exact: true }).evaluate((boton) => { boton.click(); boton.click(); });
    await iniciada;
    await expect(page.getByRole("button", { name: "Guardando…", exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Volver a consultar", exact: true })).toBeDisabled();
    expect(escrituras).toBe(1); liberar();
    await expect(page.getByText("Borrador guardado. Los derechos no cambiaron.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
    expect(escrituras).toBe(1);
  } finally { liberar(); }
});

test("403 y recarga fallida bloquean guardar hasta una consulta exitosa", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-403-${Date.now()}`);
  let escrituras = 0, fallaConsulta = false;
  await page.route("**/borradores-derechos/", async (route) => {
    if (route.request().method() === "POST") {
      escrituras += 1;
      return route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Permiso revocado ficticio" }) });
    }
    if (fallaConsulta) return route.fulfill({ status: 503, contentType: "application/json", body: "{}" });
    return route.continue();
  });
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Permiso revocado ficticio");
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  fallaConsulta = true;
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByText("No se pudo consultar el historial.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
  expect(escrituras).toBe(1); fallaConsulta = false;
  await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
  expect(escrituras).toBe(1);
});


test("simula plazo real de versión guardada sin cambiar derechos", async ({ page }) => {
  await abrir(page);
  const codigo = `ficticio-simulacion-${Date.now()}`;
  await guardar(page, codigo);
  const fila = page.getByRole("heading", { name: `${codigo} · v1`, exact: true }).locator("..");
  const boton = fila.getByRole("button", { name: "Simular plazo", exact: true });
  await boton.click();
  const dialogo = page.getByRole("dialog", { name: "Simular plazo", exact: true });
  await expect(dialogo).toBeVisible();
  await dialogo.getByLabel("Días corridos", { exact: true }).fill("7");
  await dialogo.getByLabel("Fecha de evaluación", { exact: true }).fill("2030-01-08");
  await dialogo.getByLabel("Fecha de referencia (opcional)", { exact: true }).fill("2030-01-01");
  await dialogo.getByLabel("Referencia de evidencia (opcional)", { exact: true }).fill("REF-FICTICIA");
  const respuesta = page.waitForResponse((r) => r.url().includes("/simular-plazo/") && r.request().method() === "POST");
  await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
  expect((await respuesta).status()).toBe(200);
  await expect(dialogo.getByText("Límite calculado: 2030-01-08", { exact: true })).toBeVisible();
  await expect(dialogo.getByText("Evaluación: en el límite.", { exact: true })).toBeVisible();
  await dialogo.getByLabel("Días corridos", { exact: true }).fill("9");
  await expect(dialogo.getByText("Límite calculado: 2030-01-08", { exact: true })).toHaveCount(0);
  await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
  await expect(dialogo.getByText("Límite calculado: 2030-01-10", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(boton).toBeFocused();
});


test("auditor simula evidencia faltante en móvil sin escribir versiones", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await abrir(page, "auditor");
  const boton = page.getByRole("button", { name: "Simular plazo", exact: true }).first();
  await boton.focus(); await page.keyboard.press("Enter");
  const dialogo = page.getByRole("dialog", { name: "Simular plazo", exact: true });
  await dialogo.getByLabel("Días corridos", { exact: true }).fill("0");
  await dialogo.getByLabel("Fecha de evaluación", { exact: true }).fill("2030-01-08");
  await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
  await expect(dialogo.getByText("Falta fecha de referencia o evidencia; no se calculó un límite.", { exact: true })).toBeVisible();
  await expect(dialogo.getByRole("button", { name: /Guardar|Activar|Aprobar/ })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(boton).toBeFocused();
});

async function abrirSimulacionLector(page) {
  await abrir(page, "auditor");
  await page.getByRole("button", { name: "Simular plazo", exact: true }).first().click();
  const dialogo = page.getByRole("dialog", { name: "Simular plazo", exact: true });
  await dialogo.getByLabel("Días corridos", { exact: true }).fill("7");
  await dialogo.getByLabel("Fecha de evaluación", { exact: true }).fill("2030-01-08");
  await dialogo.getByLabel("Fecha de referencia (opcional)", { exact: true }).fill("2030-01-01");
  await dialogo.getByLabel("Referencia de evidencia (opcional)", { exact: true }).fill("REF-FICTICIA");
  return dialogo;
}

test("cálculo pendiente no sobrevive cerrar y reabrir el diálogo", async ({ page }) => {
  const dialogo = await abrirSimulacionLector(page);
  let liberar, inicio, solicitudes = 0;
  const espera = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { inicio = r; });
  await page.route("**/simular-plazo/", async (route) => {
    solicitudes += 1;
    const real = await route.fetch(); expect(real.status()).toBe(200);
    inicio(); await espera; await route.fulfill({ response: real });
  });
  try {
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).evaluate((b) => { b.click(); b.click(); });
    await iniciada;
    await expect(dialogo.getByRole("button", { name: "Calculando…", exact: true })).toBeDisabled();
    expect(solicitudes).toBe(1);
    await page.keyboard.press("Escape");
    const boton = page.getByRole("button", { name: "Simular plazo", exact: true }).first();
    await expect(boton).toBeFocused(); await boton.click();
    const respuesta = page.waitForResponse((r) => r.url().includes("/simular-plazo/"));
    liberar(); await respuesta;
    await expect(dialogo.getByLabel("Días corridos", { exact: true })).toHaveValue("");
    await expect(dialogo.getByRole("status")).toHaveCount(0);
  } finally { liberar(); }
});

test("403 de simulación no conserva un cálculo positivo anterior", async ({ page }) => {
  const dialogo = await abrirSimulacionLector(page);
  await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
  await expect(dialogo.getByText("Límite calculado: 2030-01-08", { exact: true })).toBeVisible();
  await dialogo.getByLabel("Días corridos", { exact: true }).fill("9");
  await expect(dialogo.getByRole("status")).toHaveCount(0);
  await page.route("**/simular-plazo/", (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Consulta denegada ficticia" }) }));
  await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
  await expect(dialogo.getByRole("alert")).toContainText("Consulta denegada ficticia");
  await expect(dialogo.getByRole("status")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Simular plazo", exact: true }).first()).toBeFocused();
});


for (const dias of [7, 0]) {
  test(`plazo configurado se guarda en versión y alternativa no lo sobrescribe (${dias})`, async ({ page }) => {
    if (dias === 0) await page.setViewportSize({ width: 390, height: 844 });
    await abrir(page);
    const codigo = `ficticio-configurado-${Date.now()}`;
    await completar(page, codigo);
    await page.getByLabel("Plazo en días corridos (opcional)", { exact: true }).fill(String(dias));
    await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
    const fila = page.getByRole("heading", { name: `${codigo} · v1`, exact: true }).locator("..");
    await expect(fila).toBeVisible();
    await page.reload();
    await fila.getByRole("button", { name: "Simular plazo", exact: true }).click();
    const dialogo = page.getByRole("dialog", { name: "Simular plazo", exact: true });
    const usarConfigurado = dialogo.getByRole("checkbox", { name: /Usar plazo configurado/ });
    await expect(usarConfigurado).toBeChecked();
    await expect(dialogo.getByLabel("Días corridos", { exact: true })).toBeDisabled();
    await dialogo.getByLabel("Fecha de evaluación", { exact: true }).fill("2030-01-08");
    await dialogo.getByLabel("Fecha de referencia (opcional)", { exact: true }).fill("2030-01-01");
    await dialogo.getByLabel("Referencia de evidencia (opcional)", { exact: true }).fill("REF-FICTICIA");
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
    await expect(dialogo.getByText(`Límite calculado: ${dias === 0 ? "2030-01-01" : "2030-01-08"}`, { exact: true })).toBeVisible();
    await expect(dialogo.getByText("Origen del plazo: configuración guardada.", { exact: true })).toBeVisible();
    await usarConfigurado.focus(); await page.keyboard.press("Space");
    await expect(usarConfigurado).not.toBeChecked();
    await expect(dialogo.getByRole("status")).toHaveCount(0);
    await dialogo.getByLabel("Días corridos", { exact: true }).fill("9");
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
    await expect(dialogo.getByText("Límite calculado: 2030-01-10", { exact: true })).toBeVisible();
    await expect(dialogo.getByText("Origen del plazo: alternativa simulada; la versión no cambia.", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.reload(); await fila.getByRole("button", { name: "Simular plazo", exact: true }).click();
    await expect(usarConfigurado).toBeChecked();
    await expect(dialogo.getByLabel("Días corridos", { exact: true })).toHaveValue(String(dias));
  });
}

test("cierre pendiente y cambio de origen no conservan resultado anterior", async ({ page }) => {
  await abrir(page);
  const codigo = `ficticio-origen-${Date.now()}`;
  await completar(page, codigo);
  await page.getByLabel("Plazo en días corridos (opcional)", { exact: true }).fill("7");
  await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
  const fila = page.getByRole("heading", { name: `${codigo} · v1`, exact: true }).locator("..");
  const abrirModal = fila.getByRole("button", { name: "Simular plazo", exact: true });
  await abrirModal.click();
  const dialogo = page.getByRole("dialog", { name: "Simular plazo", exact: true });
  const configurado = dialogo.getByRole("checkbox", { name: /Usar plazo configurado/ });
  const completarFechas = async () => {
    await dialogo.getByLabel("Fecha de evaluación", { exact: true }).fill("2030-01-08");
    await dialogo.getByLabel("Fecha de referencia (opcional)", { exact: true }).fill("2030-01-01");
    await dialogo.getByLabel("Referencia de evidencia (opcional)", { exact: true }).fill("REF-FICTICIA");
  };
  await completarFechas();
  let liberar, iniciar, solicitudes = 0;
  const pendiente = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { iniciar = r; });
  await page.route("**/simular-plazo/", async (route) => {
    solicitudes += 1;
    if (solicitudes !== 1) return route.continue();
    expect(Object.hasOwn(route.request().postDataJSON(), "dias_corridos")).toBe(false);
    const real = await route.fetch(); expect(real.status()).toBe(200);
    iniciar(); await pendiente; await route.fulfill({ response: real });
  });
  try {
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
    await iniciada; await expect(configurado).toBeDisabled();
    await page.keyboard.press("Escape"); await expect(abrirModal).toBeFocused(); await abrirModal.click();
    await expect(configurado).toBeChecked();
    await configurado.focus(); await page.keyboard.press("Space");
    await expect(configurado).not.toBeChecked();
    await dialogo.getByLabel("Días corridos", { exact: true }).fill("0"); await completarFechas();
    const anterior = page.waitForResponse((r) => r.url().includes("/simular-plazo/"));
    liberar(); await anterior;
    await expect(dialogo.getByRole("status")).toHaveCount(0);
    await expect(configurado).not.toBeChecked();
    await expect(dialogo.getByLabel("Días corridos", { exact: true })).toHaveValue("0");
    const siguiente = page.waitForRequest((r) => r.url().includes("/simular-plazo/") && r.method() === "POST");
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
    expect((await siguiente).postDataJSON().dias_corridos).toBe(0);
    await expect(dialogo.getByText("Límite calculado: 2030-01-01", { exact: true })).toBeVisible();
    await expect(dialogo.getByText("Origen del plazo: alternativa simulada; la versión no cambia.", { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await configurado.focus(); await page.keyboard.press("Space");
    await expect(dialogo.getByRole("status")).toHaveCount(0);
    await dialogo.getByRole("button", { name: "Calcular simulación", exact: true }).click();
    await expect(dialogo.getByText("Límite calculado: 2030-01-08", { exact: true })).toBeVisible();
    await expect(dialogo.getByText("Origen del plazo: configuración guardada.", { exact: true })).toBeVisible();
    await page.keyboard.press("Escape"); await page.reload(); await abrirModal.click();
    await expect(configurado).toBeChecked();
    await expect(dialogo.getByLabel("Días corridos", { exact: true })).toHaveValue("7");
  } finally { liberar(); }
});

for (const movil of [false, true]) {
  test(`previsualiza sin guardar, limpia al editar y guarda por separado (${movil ? "móvil" : "desktop"})`, async ({ page }) => {
    if (movil) await page.setViewportSize({ width: 390, height: 844 });
    await abrir(page);
    const codigo = `ficticio-vista-${Date.now()}`;
    await completar(page, codigo);
    await page.getByLabel("Plazo en días corridos (opcional)", { exact: true }).fill("7");
    const ver = page.getByRole("button", { name: "Previsualizar propuesta", exact: true });
    await ver.focus(); await page.keyboard.press("Enter");
    const vista = page.getByRole("region", { name: "Vista previa de la propuesta", exact: true });
    await expect(vista).toBeVisible();
    await expect(vista).toContainText(`${codigo} · v1`);
    await expect(vista).toContainText("7 días corridos");
    await expect(vista).toContainText("No se guardaron versiones ni se modificaron derechos.");
    await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toHaveCount(0);
    await page.getByLabel("Plazo en días corridos (opcional)", { exact: true }).fill("0");
    await expect(vista).toHaveCount(0);
    await ver.click(); await expect(vista).toContainText("0 días corridos");
    await page.getByRole("button", { name: "Volver a consultar", exact: true }).click();
    await expect(vista).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
    await ver.click(); await expect(vista).toBeVisible();
    await page.getByRole("button", { name: "Guardar borrador", exact: true }).click();
    await expect(vista).toHaveCount(0);
    await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test("previsualización pendiente no contamina otro financiador ni duplica solicitudes", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-vista-ambito-${Date.now()}`);
  let liberar, iniciar, solicitudes = 0;
  const pendiente = new Promise((r) => { liberar = r; });
  const iniciada = new Promise((r) => { iniciar = r; });
  await page.route("**/borradores-derechos/previsualizar/", async (route) => {
    solicitudes += 1;
    const real = await route.fetch(); expect(real.status()).toBe(200);
    iniciar(); await pendiente; await route.fulfill({ response: real });
  });
  try {
    await page.getByRole("button", { name: "Previsualizar propuesta", exact: true }).evaluate((b) => { b.click(); b.click(); });
    await iniciada;
    expect(solicitudes).toBe(1);
    await expect(page.getByLabel("Código de regla", { exact: true })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeDisabled();
    await page.getByLabel("Financiador", { exact: true }).selectOption(String(datos.organizaciones[1]));
    const anterior = page.waitForResponse((r) => r.url().includes("/previsualizar/"));
    liberar(); await anterior;
    await expect(page.getByLabel("Código de regla", { exact: true })).toHaveValue("");
    await expect(page.getByRole("region", { name: "Vista previa de la propuesta", exact: true })).toHaveCount(0);
  } finally { liberar(); }
});

test("error de previsualización limpia resultado sin bloquear guardado como escritura desconocida", async ({ page }) => {
  await abrir(page); await completar(page, `ficticio-vista-error-${Date.now()}`);
  const ver = page.getByRole("button", { name: "Previsualizar propuesta", exact: true });
  await ver.click();
  const vista = page.getByRole("region", { name: "Vista previa de la propuesta", exact: true });
  await expect(vista).toBeVisible();
  await page.route("**/borradores-derechos/previsualizar/", (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Consulta denegada ficticia" }) }));
  await ver.click();
  await expect(page.getByRole("alert")).toContainText("Consulta denegada ficticia");
  await expect(vista).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar borrador", exact: true })).toBeEnabled();
});

for (const movil of [false, true]) {
  test(`Enter en campo conserva guardado, Enter en preview sólo consulta (${movil ? "móvil" : "desktop"})`, async ({ page }) => {
    if (movil) await page.setViewportSize({ width: 390, height: 844 });
    await abrir(page); const codigo = `ficticio-enter-${Date.now()}`; await completar(page, codigo);
    let consultas = 0, guardados = 0;
    page.on("request", (r) => {
      if (r.method() !== "POST") return;
      if (r.url().endsWith("/previsualizar/")) consultas += 1;
      else if (r.url().endsWith("/borradores-derechos/")) guardados += 1;
    });
    await page.getByRole("button", { name: "Previsualizar propuesta", exact: true }).focus();
    await page.keyboard.press("Enter");
    const vista = page.getByRole("region", { name: "Vista previa de la propuesta", exact: true });
    await expect(vista).toContainText(`${codigo} · v1`);
    expect(consultas).toBe(1); expect(guardados).toBe(0);
    await page.getByLabel("Motivo del registro", { exact: true }).focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: `${codigo} · v1`, exact: true })).toBeVisible();
    await expect(vista).toHaveCount(0);
    expect(consultas).toBe(1); expect(guardados).toBe(1);
  });
}
