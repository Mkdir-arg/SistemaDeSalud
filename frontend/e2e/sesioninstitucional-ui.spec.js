import { expect, test } from "@playwright/test";

const INSTITUCION = { id: 12, nombre: "Institución sintética de sesión" };
const ANTERIOR = { access: "access-ficticio-vencido", refresh: "refresh-ficticio-vigente" };
const NUEVA = { access: "access-ficticio-renovado", refresh: "refresh-ficticio-rotado" };

async function escenario(page, fallo) {
  let disponible = false;
  const renovaciones = [];
  await page.addInitScript(({ institucion, tokens }) => {
    sessionStorage.setItem("salud.access", tokens.access);
    sessionStorage.setItem("salud.refresh", tokens.refresh);
    localStorage.setItem("salud.institucion", JSON.stringify(institucion));
  }, { institucion: INSTITUCION, tokens: ANTERIOR });
  await page.route("**/api/**", ruta => {
    const pathname = new URL(ruta.request().url()).pathname;
    // El módulo /src/api/client.js de Vite DEV debe seguir cargándose como JS.
    if (!pathname.startsWith("/api/")) return ruta.continue();
    if (pathname === "/api/auth/token/refresh/") {
      renovaciones.push(ruta.request().postDataJSON());
      return ruta.fulfill({ status: disponible ? 200 : fallo, json: disponible ? NUEVA : { detail: "Fallo sintético de renovación" } });
    }
    if (pathname === "/api/usuarios/me/") {
      if (ruta.request().headers().authorization !== `Bearer ${NUEVA.access}`) {
        return ruta.fulfill({ status: 401, json: { detail: "Acceso sintético vencido" } });
      }
      return ruta.fulfill({ json: {
        id: 172, email: "sesion-ui@example.test", nombre_completo: "Persona sintética",
        is_superuser: false, capacidades_por_institucion: { 12: ["diseno_flujos"] },
        roles_por_institucion: { 12: ["configurador"] }, financiadores: [],
      } });
    }
    return ruta.fulfill({ json: { count: pathname === "/api/instituciones/" ? 1 : 0, results: pathname === "/api/instituciones/" ? [INSTITUCION] : [], next: null, previous: null } });
  });
  return { recuperar: () => { disponible = true; }, renovaciones };
}

const credencialesGuardadas = page => page.evaluate(() => ({
  access: sessionStorage.getItem("salud.access"), refresh: sessionStorage.getItem("salud.refresh"),
}));

for (const status of [429, 503]) {
  test(`renovación ${status} al iniciar conserva credenciales y permite recuperar la sesión`, async ({ page }) => {
    const servidor = await escenario(page, status);
    await page.goto("/formularios");
    const aviso = page.getByRole("alert");
    await expect(aviso).toContainText("No se pudo conectar con el servidor");
    await expect(page).toHaveURL(/\/formularios$/);
    expect(await credencialesGuardadas(page)).toEqual(ANTERIOR);
    expect(servidor.renovaciones.length).toBeGreaterThan(0);
    expect(servidor.renovaciones.every(r => r.refresh === ANTERIOR.refresh)).toBe(true);

    servidor.recuperar();
    await aviso.getByRole("button", { name: "Reintentar", exact: true }).click();
    await expect(page.getByText("No hay formularios", { exact: true })).toBeVisible();
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(await credencialesGuardadas(page)).toEqual(NUEVA);
    await expect(page).toHaveURL(/\/formularios$/);
  });
}

test("renovación 401 definitiva al iniciar elimina credenciales y solicita login", async ({ page }) => {
  const servidor = await escenario(page, 401);
  await page.goto("/formularios");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Ingresar", exact: true })).toBeVisible();
  expect(await credencialesGuardadas(page)).toEqual({ access: null, refresh: null });
  expect(servidor.renovaciones.length).toBeGreaterThan(0);
});

test("dos pestañas con sesión mantenida renuevan una sola vez y ninguna vuelve al login", async ({ context }) => {
  // Refresh de un solo uso (#172): el consumido responde 401 y la renovación
  // ganadora sigue válida. La pestaña que pierde no puede borrar el almacén.
  await context.addInitScript(({ institucion, tokens }) => {
    if (localStorage.getItem("salud.persistir")) return;
    localStorage.setItem("salud.persistir", "1");
    localStorage.setItem("salud.access", tokens.access);
    localStorage.setItem("salud.refresh", tokens.refresh);
    localStorage.setItem("salud.institucion", JSON.stringify(institucion));
  }, { institucion: INSTITUCION, tokens: ANTERIOR });
  const primera = await context.newPage();
  const segunda = await context.newPage();
  const renovaciones = [];
  let segundaConsulto;
  const segundaEnCarrera = new Promise(resolve => { segundaConsulto = resolve; });
  let vigente = ANTERIOR.refresh;
  await context.route("**/api/**", async ruta => {
    const pathname = new URL(ruta.request().url()).pathname;
    if (!pathname.startsWith("/api/")) return ruta.continue();
    if (pathname === "/api/auth/token/refresh/") {
      const enviado = ruta.request().postDataJSON().refresh;
      renovaciones.push(enviado);
      if (renovaciones.length === 1) {
        // Retener la primera renovación hasta que la otra pestaña también
        // necesite renovar: así se cruzan como en un vencimiento simultáneo.
        await segundaEnCarrera;
        await new Promise(r => setTimeout(r, 400));
      }
      if (enviado !== vigente) return ruta.fulfill({ status: 401, json: { detail: "Refresh sintético consumido" } });
      vigente = NUEVA.refresh;
      return ruta.fulfill({ json: NUEVA });
    }
    if (pathname === "/api/usuarios/me/") {
      if (ruta.request().frame().page() === segunda) segundaConsulto();
      if (ruta.request().headers().authorization !== `Bearer ${NUEVA.access}`) {
        return ruta.fulfill({ status: 401, json: { detail: "Acceso sintético vencido" } });
      }
      return ruta.fulfill({ json: {
        id: 172, email: "sesion-ui@example.test", nombre_completo: "Persona sintética",
        is_superuser: false, capacidades_por_institucion: { 12: ["diseno_flujos"] },
        roles_por_institucion: { 12: ["configurador"] }, financiadores: [],
      } });
    }
    return ruta.fulfill({ json: { count: pathname === "/api/instituciones/" ? 1 : 0, results: pathname === "/api/instituciones/" ? [INSTITUCION] : [], next: null, previous: null } });
  });

  await primera.goto("/formularios");
  await segunda.goto("/formularios");
  for (const pagina of [primera, segunda]) {
    await expect(pagina.getByText("No hay formularios", { exact: true })).toBeVisible();
    await expect(pagina).toHaveURL(/\/formularios$/);
  }
  expect(renovaciones.filter(r => r === ANTERIOR.refresh)).toHaveLength(1);
  expect(await primera.evaluate(() => [localStorage.getItem("salud.access"), localStorage.getItem("salud.refresh")]))
    .toEqual([NUEVA.access, NUEVA.refresh]);
});
