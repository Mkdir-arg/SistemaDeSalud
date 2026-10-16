import { expect, test } from "@playwright/test";

const ANTERIOR = { access: "access-sintetico-anterior", refresh: "refresh-sintetico-anterior" };
const ROTADA = { access: "access-sintetico-rotado", refresh: "refresh-sintetico-rotado" };
const NUEVA = { access: "access-sintetico-otra-sesion", refresh: "refresh-sintetico-otra-sesion" };
const BORRADOR = "salud.alta-afiliado.172.12";
const lista = results => ({ count: results.length, results, next: null, previous: null });

async function escenario(page, { renovar = false, falloCierre = false } = {}) {
  const cierres = [];
  let avisarRenovacion, responderRenovacion;
  const renovacionIniciada = new Promise(resolve => { avisarRenovacion = resolve; });
  const respuestaRenovacion = new Promise(resolve => { responderRenovacion = resolve; });
  const institucion = { id: 12, nombre: "Institución sintética logout" };
  await page.addInitScript(({ tokens, inst, borrador }) => {
    sessionStorage.setItem("salud.access", tokens.access);
    sessionStorage.setItem("salud.refresh", tokens.refresh);
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
    localStorage.setItem(borrador, "Borrador exclusivamente sintético");
  }, { tokens: ANTERIOR, inst: institucion, borrador: BORRADOR });
  await page.route("**/api/**", async ruta => {
    const pathname = new URL(ruta.request().url()).pathname;
    if (!pathname.startsWith("/api/")) return ruta.continue();
    if (pathname === "/api/auth/token/refresh/") {
      avisarRenovacion();
      await respuestaRenovacion;
      return ruta.fulfill({ json: ROTADA });
    }
    if (pathname === "/api/auth/logout/") {
      cierres.push({ datos: ruta.request().postDataJSON(), headers: ruta.request().headers() });
      if (falloCierre) return ruta.abort("failed");
      // Modelo del contrato JTI: el refresh consumido no revoca al ganador.
      const vigente = renovar ? ROTADA.refresh : ANTERIOR.refresh;
      return ruta.fulfill({ status: cierres.at(-1).datos.refresh === vigente ? 204 : 401 });
    }
    if (pathname === "/api/auth/token/") return ruta.fulfill({ json: NUEVA });
    if (pathname === "/api/usuarios/me/") return ruta.fulfill({ json: {
      id: ruta.request().headers().authorization === `Bearer ${NUEVA.access}` ? 173 : 172,
      email: "logout-ui@example.test", nombre_completo: "Persona sintética",
      capacidades_por_institucion: { 12: ["diseno_flujos"] }, roles_por_institucion: { 12: ["configurador"] }, financiadores: [],
    } });
    if (pathname === "/api/formularios/" && renovar && ruta.request().headers().authorization === `Bearer ${ANTERIOR.access}`) {
      return ruta.fulfill({ status: 401, json: { detail: "Access sintético vencido" } });
    }
    if (pathname === "/api/instituciones/") return ruta.fulfill({ json: lista([institucion]) });
    return ruta.fulfill({ json: lista([]) });
  });
  return { cierres, renovacionIniciada, liberarRenovacion: () => responderRenovacion() };
}

const credenciales = page => page.evaluate(() => ({ access: sessionStorage.getItem("salud.access"), refresh: sessionStorage.getItem("salud.refresh") }));

test("logout espera refresh vigente y su respuesta tardía no altera otra sesión", async ({ page }) => {
  const servidor = await escenario(page, { renovar: true });
  await page.goto("/formularios");
  await servidor.renovacionIniciada;
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await credenciales(page)).toEqual({ access: null, refresh: null });
  expect(await page.evaluate(clave => localStorage.getItem(clave), BORRADOR)).toBeNull();
  expect(servidor.cierres).toHaveLength(0);
  await page.getByLabel(/^Email/).fill("otra-persona@example.test");
  await page.getByLabel(/^Contraseña/).fill("Clave-sintética-de-prueba");
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login$/);
  expect(await credenciales(page)).toEqual(NUEVA);
  servidor.liberarRenovacion();
  await expect.poll(() => servidor.cierres.length).toBe(1);
  expect(servidor.cierres[0].datos).toEqual({ refresh: ROTADA.refresh });
  expect(servidor.cierres[0].headers.authorization).toBeUndefined();
  expect(servidor.cierres[0].headers["x-plexo-simulacion"]).toBeUndefined();
  expect(servidor.cierres[0].headers.cookie).toBeUndefined();
  expect(await credenciales(page)).toEqual(NUEVA);
  await expect(page.getByRole("button", { name: "Salir", exact: true })).toBeVisible();
});

test("fallo de red al cerrar oculta la vista y avisa que el cierre remoto no está confirmado", async ({ page }) => {
  const servidor = await escenario(page, { falloCierre: true });
  await page.goto("/formularios");
  await page.getByRole("button", { name: "Salir", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("alert")).toContainText("no se pudo confirmar el cierre en el servidor");
  expect(await credenciales(page)).toEqual({ access: null, refresh: null });
  expect(servidor.cierres).toHaveLength(1);
  await expect(page.getByRole("button", { name: "Editar datos", exact: true })).toHaveCount(0);
});

for (const causa of ["inactividad", "otra pestaña"]) {
  test(`bloqueo por ${causa} es local y conserva borradores sin revocar remotamente`, async ({ page }) => {
    const servidor = await escenario(page);
    if (causa === "inactividad") await page.clock.install();
    await page.goto("/formularios");
    await expect(page.getByText("No hay formularios", { exact: true })).toBeVisible();
    if (causa === "inactividad") await page.clock.fastForward(16 * 60_000);
    else await page.evaluate(() => { const canal = new BroadcastChannel("salud-sesion"); canal.postMessage("bloquear"); canal.close(); });
    await expect(page.getByRole("button", { name: "Reanudar sesión", exact: true })).toBeVisible();
    expect(await credenciales(page)).toEqual({ access: null, refresh: null });
    expect(await page.evaluate(clave => localStorage.getItem(clave), BORRADOR)).toBe("Borrador exclusivamente sintético");
    expect(servidor.cierres).toHaveLength(0);
  });
}
