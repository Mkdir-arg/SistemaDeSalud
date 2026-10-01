import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
const paciente = {
  id: 5, nombre: "Ana", apellido: "Prueba", documento: "12345678", institucion: 1,
  fecha_nacimiento: "1980-01-02", domicilio: "Calle Falsa 123", consentimiento: null,
  cobertura_administrativa: { habilitada: false, estado: "no_habilitada", afiliaciones: [] },
  alergias: "Penicilina", edad: 46,
};

async function preparar(page, { medico = false, sinHistoria = false } = {}) {
  const lecturas = [];
  await page.addInitScript(() => {
    sessionStorage.setItem("salud.access", "token-ficticio-interceptado");
    localStorage.setItem("salud.institucion", JSON.stringify({ id: 1, nombre: "Hospital Central", tipo: "Hospital" }));
  });
  await page.route("**/api/**", (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    if (req.method() !== "GET") return route.fulfill({ json: {} });
    lecturas.push(path);
    if (path === "/usuarios/me/") return route.fulfill({ json: {
      id: 30, nombre_completo: "Usuario de prueba", email: "usuario@example.test",
      capacidades_por_institucion: { 1: medico ? ["padron_admision", "historia_clinica"] : ["padron_admision"] },
      roles_por_institucion: { 1: [medico ? "medico" : "administrativo"] }, financiadores: [],
    } });
    if (path === "/instituciones/") return route.fulfill({ json: lista([{ id: 1, nombre: "Hospital Central", tipo: "Hospital" }]) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [] } });
    if (path === "/ciudadanos/") return route.fulfill({ json: lista([paciente]) });
    if (path === "/ciudadanos/5/") return route.fulfill({ json: paciente });
    if (path === "/historias-clinicas/") return route.fulfill({ json: lista(sinHistoria ? [] : [{
      id: 12, ciudadano: 5, alergias: "Penicilina", entradas: [], estudios: [], recetas: [],
    }]) });
    return route.fulfill({ json: lista([]) });
  });
  return lecturas;
}

test("administrativo ve Datos sin consultas clínicas, incluso con tab clínico en la URL", async ({ page }) => {
  const lecturas = await preparar(page);
  await page.goto("/pacientes");
  await expect(page.getByRole("link", { name: "Pacientes", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Historia clínica", exact: true })).toHaveCount(0);
  await expect(page.getByRole("columnheader", { name: "Alergias" })).toHaveCount(0);
  await page.goto("/pacientes/5?tab=evolucion");
  await expect(page.getByRole("tab", { name: "Datos" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tab", { name: "Evolución" })).toHaveCount(0);
  await expect(page.getByText(/Esta ficha no muestra evolución/)).toBeVisible();
  expect(lecturas.some((p) => p.includes("historias-clinicas") || p.includes("accesos-clinicos") || /\/ciudadanos\/5\/cobertura\//.test(p))).toBe(false);
});

test("médico ve alergias y abre Evolución desde la URL", async ({ page }) => {
  await preparar(page, { medico: true });
  await page.goto("/pacientes");
  await expect(page.getByRole("columnheader", { name: "Alergias" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Penicilina" })).toBeVisible();
  await page.goto("/pacientes/5?tab=evolucion");
  await expect(page.getByRole("tab", { name: "Evolución" })).toHaveAttribute("aria-selected", "true");
  for (const nombre of ["Estudios", "Recetas", "Cobertura", "Quién la miró"]) {
    await expect(page.getByRole("tab", { name: nombre })).toBeVisible();
  }
  await expect(page.getByText("Sin entradas de evolución")).toBeVisible();
});

test("paciente sin historia mantiene pestañas vacías y permite registrar atención", async ({ page }) => {
  await preparar(page, { medico: true, sinHistoria: true });
  await page.goto("/pacientes/5?tab=evolucion");
  await expect(page.getByRole("tab", { name: "Evolución" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Sin entradas de evolución")).toBeVisible();
  await page.getByRole("tab", { name: "Estudios" }).click();
  await expect(page.getByText("Sin estudios")).toBeVisible();
  await expect(page.getByRole("button", { name: "Registrar atención" })).toBeEnabled();
});

test("rutas anteriores preservan query y hash", async ({ page }) => {
  await preparar(page, { medico: true });
  for (const [antes, despues] of [
    ["/padron?q=x", "/pacientes?q=x"],
    ["/historia/5", "/pacientes/5?tab=evolucion"],
    ["/historia/5?tab=estudios#entrada-3", "/pacientes/5?tab=estudios#entrada-3"],
    ["/padron/5", "/pacientes/5"],
  ]) {
    await page.goto(antes);
    await expect(page).toHaveURL(new RegExp(`${despues.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`));
  }
});

test("cambiar de pestaña conserva una sola lectura auditada de la ficha", async ({ page }) => {
  const lecturas = await preparar(page, { medico: true });
  await page.goto("/pacientes/5");
  await expect(page.getByRole("tab", { name: "Datos" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "Evolución" }).click();
  await page.getByRole("tab", { name: "Estudios" }).click();
  await page.getByRole("tab", { name: "Datos" }).click();
  expect(lecturas.filter((p) => p === "/ciudadanos/5/")).toHaveLength(1);
});
