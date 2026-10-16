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
